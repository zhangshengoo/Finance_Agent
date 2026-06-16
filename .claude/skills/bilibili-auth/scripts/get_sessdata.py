#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0", "qrcode==7.4.2", "pillow"]
# ///
"""
bilibili-auth — 通过「扫码登录」获取并校验 B 站 SESSDATA，落地到 ~/.bilibili_sessdata.json。

为什么是扫码：SESSDATA 是登录态 cookie，只能通过一次真实登录拿到。扫码是 B 站
官方 web 登录流程，最稳、跨平台、不碰账号密码、不触发 geetest 滑块。

凭据安全：拿到的 SESSDATA 只写本地缓存文件（chmod 600，仅本人可读），绝不外传。
这与本仓库「KB / 凭据只走本地」的红线一致。

工作流：
  generate → 渲染二维码（终端 ASCII + 自动打开 PNG + 打印 URL）
  poll     → 每 2s 轮询登录状态，打印「等待扫码 / 已扫码待确认 / 成功」
  validate → 用新 cookie 打 nav 接口，确认 isLogin==True（关键：避免拿到无效串）
  persist  → 写 ~/.bilibili_sessdata.json（含 uname/mid 便于核对），chmod 600

用法：
  # 扫码登录拿新 SESSDATA（默认）
  uv run scripts/get_sessdata.py
  # 只校验现有 env / 缓存里的 SESSDATA 还在不在线（不登录）
  uv run scripts/get_sessdata.py --check
  # 自定义超时 / PNG 路径
  uv run scripts/get_sessdata.py --timeout 240 --png /tmp/bili_qr.png

输出：最后一行是结果 JSON（ok / uname / mid / cache / sessdata_len）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

from curl_cffi.requests import Session
import qrcode

CACHE_PATH = os.path.join(os.path.expanduser("~"), ".bilibili_sessdata.json")
GEN_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
IMPERSONATE = "chrome120"

# poll 的 data.code 含义（B 站公开状态码）
POLL_MSG = {
    86101: "等待扫码…（请用手机 B 站 App 扫码）",
    86090: "已扫码，请在手机上点「确认登录」",
    0: "登录成功",
    86038: "二维码已失效",
}


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_client() -> Session:
    return Session(
        impersonate=IMPERSONATE,
        timeout=15.0,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        },
    )


def render_qr(url: str, png_path: str) -> str | None:
    """终端打印 ASCII 二维码 + 存 PNG 并在 macOS 上自动打开。返回 PNG 路径或 None。"""
    qr = qrcode.QRCode(border=2, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    try:
        qr.print_ascii(invert=True)  # 终端可直接扫（取决于字体/缩放）
    except Exception:
        pass
    try:
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(png_path)
        if sys.platform == "darwin":
            subprocess.run(["open", png_path], check=False)
        return png_path
    except Exception:
        return None


def generate_qr(client: Session) -> tuple[str, str]:
    j = client.get(GEN_URL).json()
    if j.get("code") != 0:
        raise SystemExit(f"二维码生成失败: code={j.get('code')} msg={j.get('message')}")
    d = j["data"]
    return d["url"], d["qrcode_key"]


def _extract_cookies(client: Session, redirect_url: str) -> dict:
    """成功后 cookie 优先从 session 取，兜底从 data.url 的 query 解析。"""
    out: dict[str, str] = {}
    for name in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"):
        try:
            v = client.cookies.get(name)
        except Exception:
            v = None
        if v:
            out[name] = v
    if redirect_url:
        q = parse_qs(urlparse(redirect_url).query)
        for name in ("SESSDATA", "bili_jct", "DedeUserID"):
            if name not in out and q.get(name):
                out[name] = q[name][0]
    return out


def poll(client: Session, qrcode_key: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    last_code = None
    while time.time() < deadline:
        j = client.get(POLL_URL, params={"qrcode_key": qrcode_key}).json()
        data = j.get("data", {})
        code = data.get("code")
        if code != last_code:
            print(f"  [{POLL_MSG.get(code, f'状态 {code}')}]", flush=True)
            last_code = code
        if code == 0:
            return _extract_cookies(client, data.get("url", ""))
        if code == 86038:
            raise SystemExit("二维码已失效，请重跑本脚本生成新码。")
        time.sleep(2)
    raise SystemExit(f"扫码超时（{timeout}s），请重跑。")


def validate(sessdata: str) -> dict:
    """用 SESSDATA 打 nav，确认登录态。返回 {isLogin,uname,mid,vip}。"""
    c = make_client()
    c.headers["Cookie"] = f"SESSDATA={sessdata}"
    d = c.get(NAV_URL).json().get("data", {})
    vip = d.get("vip") or {}
    vip_text = (vip.get("label") or {}).get("text") if isinstance(vip, dict) else None
    return {
        "isLogin": bool(d.get("isLogin")),
        "uname": d.get("uname"),
        "mid": d.get("mid"),
        "vip": vip_text or None,
    }


def persist(cookies: dict, nav: dict) -> dict:
    payload = {
        "sessdata": cookies.get("SESSDATA"),
        "bili_jct": cookies.get("bili_jct"),
        "dedeuserid": cookies.get("DedeUserID"),
        "uname": nav.get("uname"),
        "mid": nav.get("mid"),
        "saved_at": _now_iso(),
        "source": "bilibili-auth qrcode login",
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.chmod(CACHE_PATH, 0o600)  # cookie 是凭据，仅本人可读
    return payload


def _read_cached_sessdata() -> str | None:
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f).get("sessdata") or None
    except (OSError, ValueError):
        return None


def cmd_check() -> None:
    sd = os.environ.get("BILIBILI_SESSDATA") or _read_cached_sessdata()
    if not sd:
        print(json.dumps({"ok": False, "reason": "env 和缓存里都没有 SESSDATA，请先扫码登录"},
                         ensure_ascii=False))
        sys.exit(2)
    nav = validate(sd)
    ok = nav["isLogin"]
    print(json.dumps({"ok": ok, **nav,
                      "hint": None if ok else "SESSDATA 已过期，请重跑（不带 --check）扫码刷新"},
                     ensure_ascii=False))
    sys.exit(0 if ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="扫码获取并校验 B 站 SESSDATA")
    ap.add_argument("--timeout", type=int, default=180, help="扫码等待超时秒数（默认 180）")
    ap.add_argument("--check", action="store_true", help="只校验现有 env/缓存的 SESSDATA，不登录")
    ap.add_argument("--png", default="/tmp/bilibili_login_qr.png", help="二维码 PNG 落盘路径")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return

    client = make_client()
    url, key = generate_qr(client)
    print("=" * 60)
    print("请用【手机 B 站 App】扫码登录（不是微信/支付宝扫一扫）：")
    print(f"  二维码 URL: {url}")
    png = render_qr(url, args.png)
    if png:
        print(f"  已打开二维码图片: {png}")
    print("=" * 60)

    cookies = poll(client, key, args.timeout)
    sd = cookies.get("SESSDATA")
    if not sd:
        raise SystemExit("登录成功但未取到 SESSDATA cookie，请重跑。")

    nav = validate(sd)
    if not nav["isLogin"]:
        raise SystemExit(f"取到 SESSDATA 但 nav 校验未登录，疑似无效: {nav}")

    persist(cookies, nav)
    print(json.dumps(
        {"ok": True, "uname": nav.get("uname"), "mid": nav.get("mid"),
         "vip": nav.get("vip"), "cache": CACHE_PATH, "sessdata_len": len(sd)},
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
