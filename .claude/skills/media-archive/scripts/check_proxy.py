#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0"]
# ///
"""
B 站代理连通性验证脚本

验证 BILIBILI_PROXY 是否满足动态抓取要求：
  1. 代理是否可达（HTTP CONNECT）
  2. 出口 IP 是否为大陆 IP（ipinfo.io country == CN）
  3. B 站 /finger/spi buvid 接口是否返回 JSON
  4. B 站 /nav WBI key 接口是否正常（SESSDATA 有效性）
  5. 动态 /feed/space 接口是否返回 JSON items（核心验证）

用法：
    # 验证代理
    BILIBILI_PROXY=http://1.2.3.4:7890 \
    uv run --with 'curl_cffi==0.9.0' check_proxy.py --uid 1039025435

    # 无代理：验证直连（如本机已是 CN IP）
    uv run --with 'curl_cffi==0.9.0' check_proxy.py --uid 1039025435 --no-proxy
"""

import argparse
import json
import os
import sys

from curl_cffi.requests import Session
from _bilibili_common import (
    IMPERSONATE,
    HTTP_TIMEOUT,
    get_proxy,
    get_sessdata,
    make_headers,
    sign_wbi_params,
)

# ─────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}"); return False
def warn(msg): print(f"  {YELLOW}!{RESET} {msg}")


def make_client(sessdata, proxy):
    headers = make_headers(sessdata)
    kwargs = {"impersonate": IMPERSONATE, "timeout": HTTP_TIMEOUT, "headers": headers}
    if proxy:
        kwargs["proxy"] = proxy
    return Session(**kwargs)


def check_exit_ip(client) -> bool:
    print("\n[1] 出口 IP / 地区")
    try:
        r = client.get("https://ipinfo.io/json", timeout=10)
        d = r.json()
        ip      = d.get("ip", "?")
        country = d.get("country", "?")
        org     = d.get("org", "?")
        print(f"    IP={ip}  country={country}  org={org}")
        if country == "CN":
            ok("大陆 IP — 动态 API 可正常访问")
            return True
        else:
            fail(f"非大陆 IP（{country}）— 动态 /feed/space 会被拦截")
            return False
    except Exception as e:
        fail(f"ipinfo 请求失败: {e}")
        return False


def check_buvid(client, sessdata) -> bool:
    print("\n[2] B 站 buvid 指纹 + DedeUserID (/finger/spi + /nav)")
    try:
        r = client.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=10)
        if "<!DOCTYPE" in r.text[:20]:
            return fail("返回 HTML 拦截页（IP 被 B 站风控）")
        d = r.json()
        if d.get("code") == 0:
            b3 = d["data"].get("b_3", "")
            b4 = d["data"].get("b_4", "")
            ok(f"buvid3={b3[:16]}…  buvid4={b4[:16]}…")
            cookie = f"buvid3={b3}; buvid4={b4}"
            if sessdata:
                cookie += f"; SESSDATA={sessdata}"
            client.headers["Cookie"] = cookie
            # 取 DedeUserID
            nav_r = client.get("https://api.bilibili.com/x/web-interface/nav", timeout=10)
            nav_d = nav_r.json().get("data", {})
            mid = str(nav_d.get("mid", ""))
            if mid and mid != "0" and nav_d.get("isLogin"):
                client.headers["Cookie"] += f"; DedeUserID={mid}"
                ok(f"DedeUserID={mid} 已注入")
            return True
        return fail(f"code={d.get('code')} msg={d.get('message')}")
    except Exception as e:
        return fail(f"请求异常: {e}")


def check_nav(client) -> tuple[bool, str, str]:
    """返回 (ok, img_key, sub_key)"""
    print("\n[3] WBI Key + SESSDATA 有效性 (/x/web-interface/nav)")
    try:
        r = client.get("https://api.bilibili.com/x/web-interface/nav", timeout=10)
        if "<!DOCTYPE" in r.text[:20]:
            fail("返回 HTML 拦截页")
            return False, "", ""
        d = r.json()
        if d.get("code") != 0:
            fail(f"code={d.get('code')} msg={d.get('message')} — SESSDATA 可能过期")
            return False, "", ""
        data    = d["data"]
        uname   = data.get("uname", "?")
        is_login = data.get("isLogin", False)
        img_url = data.get("wbi_img", {}).get("img_url", "")
        sub_url = data.get("wbi_img", {}).get("sub_url", "")
        img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
        sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""
        if is_login:
            ok(f"已登录: {uname}  img_key={img_key[:8]}…")
        else:
            warn("未登录（SESSDATA 缺失或过期）— 动态抓取仍可尝试但成功率低")
        return True, img_key, sub_key
    except Exception as e:
        fail(f"请求异常: {e}")
        return False, "", ""


def check_dynamics(client, uid: str, img_key: str, sub_key: str) -> bool:
    print(f"\n[4] 动态 /feed/space (uid={uid}, limit=3)")
    params = {"host_mid": uid, "limit": 3, "timezone_offset": -480}
    if img_key and sub_key:
        params = sign_wbi_params(params, img_key, sub_key)
    try:
        r = client.get(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
            params=params,
            timeout=15,
        )
        if "<!DOCTYPE" in r.text[:20]:
            return fail("返回 HTML — 地区拦截或风控，动态无法抓取")
        d = r.json()
        code  = d.get("code", -1)
        items = d.get("data", {}).get("items", [])
        if code == 0 and items:
            first = items[0]
            modules = first.get("modules", {})
            author  = modules.get("module_author", {})
            uname   = author.get("name", "?")
            pub_ts  = author.get("pub_ts", 0)
            import datetime
            pub_dt = datetime.datetime.fromtimestamp(int(pub_ts)).strftime("%Y-%m-%d %H:%M") if pub_ts else "?"
            ok(f"返回 {len(items)} 条  最新: [{pub_dt}] {uname}")
            return True
        elif code == -352:
            return fail(f"code=-352 风控（buvid/UA 特征不够，需要等待或更换代理）")
        elif code == -799:
            return fail(f"code=-799 请求太频繁，等几分钟后重试")
        else:
            return fail(f"code={code} msg={d.get('message')}  items={len(items)}")
    except Exception as e:
        return fail(f"请求异常: {e}")


def main():
    ap = argparse.ArgumentParser(description="B 站代理连通性验证")
    ap.add_argument("--uid", default="1039025435", help="用于测试的 UP 主 UID")
    ap.add_argument("--sessdata", default=None, help="SESSDATA（默认读 cache/env）")
    ap.add_argument("--no-proxy", action="store_true", help="忽略 BILIBILI_PROXY，验证直连")
    args = ap.parse_args()

    sessdata = get_sessdata(args.sessdata)
    proxy    = None if args.no_proxy else get_proxy()

    print("=" * 52)
    print("  B 站动态抓取代理验证")
    print("=" * 52)
    print(f"  proxy   : {proxy or '(直连)'}")
    print(f"  sessdata: {'已设置 ' + sessdata[:8] + '…' if sessdata else '(未设置)'}")
    print(f"  uid     : {args.uid}")

    client = make_client(sessdata, proxy)

    results = {}
    results["ip_cn"]   = check_exit_ip(client)
    results["buvid"]   = check_buvid(client, sessdata)
    nav_ok, img_key, sub_key = check_nav(client)
    results["nav"]     = nav_ok
    results["dynamics"] = check_dynamics(client, args.uid, img_key, sub_key)

    print("\n" + "=" * 52)
    all_pass = all(results.values())
    if all_pass:
        print(f"  {GREEN}全部通过 — 可以运行 fetch_bilibili_dynamic.py{RESET}")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  {RED}未通过: {', '.join(failed)}{RESET}")
        if not results.get("ip_cn"):
            print(f"\n  修复建议：")
            print(f"    BILIBILI_PROXY=http://<CN代理IP>:<端口> \\")
            print(f"    uv run --with 'curl_cffi==0.9.0' check_proxy.py --uid {args.uid}")
    print("=" * 52)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
