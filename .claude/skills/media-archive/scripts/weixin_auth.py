#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "curl_cffi==0.9.0",
#   "qrcode==7.4.2",
# ]
# ///
"""
微信网页版扫码登录 → 自动提取并保存 Cookie

用法：
    uv run --with 'curl_cffi==0.9.0,qrcode==7.4.2' weixin_auth.py

流程：
    1. 获取登录 UUID
    2. 终端显示二维码（用微信 App 扫码）
    3. 手机点击确认登录
    4. 自动提取 uin / skey / pass_ticket / appmsg_token
    5. 保存到 ~/.config/weixin-archive/cookies.json

Cookie 有效期约 30 天，到期后重新运行本脚本即可。
"""

import json
import os
import re
import sys
import time
import random
from pathlib import Path

from curl_cffi.requests import Session

try:
    import qrcode as _qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

COOKIE_FILE = Path.home() / ".config" / "weixin-archive" / "cookies.json"

JSLOGIN_URL = "https://login.wx.qq.com/jslogin"
POLL_URL    = "https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login"
# mp.weixin.qq.com 访问以获取 appmsg_token（用一个高流量公众账号触发）
PROFILE_URL = "https://mp.weixin.qq.com/mp/profile_ext"


# ── HTTP ────────────────────────────────────────────────────────

def make_session() -> Session:
    return Session(
        impersonate="chrome124",
        timeout=35,
        headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://wx.qq.com/",
        },
    )


# ── Step 1: 获取 UUID ───────────────────────────────────────────

def get_uuid(s: Session) -> str:
    ts = int(time.time() * 1000)
    resp = s.get(JSLOGIN_URL, params={
        "appid": "wx782c26e4c19acffb",
        "redirect_uri": "https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage",
        "fun": "new",
        "lang": "zh_CN",
        "_": str(ts),
    })
    m = re.search(r'uuid\s*=\s*"([^"]+)"', resp.text)
    if not m:
        raise RuntimeError(f"获取 UUID 失败:\n{resp.text}")
    return m.group(1)


# ── Step 2: 显示二维码 ──────────────────────────────────────────

def show_qrcode(uuid: str) -> None:
    qr_data = f"https://login.weixin.qq.com/l/{uuid}"
    qr_img_url = f"https://login.weixin.qq.com/qrcode/{uuid}"

    print("\n" + "=" * 50)
    print("  请用微信 App 扫描下方二维码登录")
    print("=" * 50 + "\n")

    if HAS_QRCODE:
        qr = _qrcode.QRCode(border=2, error_correction=_qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(qr_data)
        qr.make(fit=True)
        # invert=True 在黑色背景终端效果更好
        qr.print_ascii(invert=True)
    else:
        print(f"  二维码数据: {qr_data}")
        print(f"\n  或在浏览器打开扫码页: {qr_img_url}")

    print(f"\n  二维码图片 URL: {qr_img_url}")
    print()


# ── Step 3: 轮询登录状态 ────────────────────────────────────────

def poll_login(s: Session, uuid: str) -> str | None:
    """
    返回 redirect_uri（登录成功）或 None（超时/失败）。
    等待期间每隔 ~25s 超时后自动重试。
    """
    tip = 0
    scanned = False
    attempts = 0

    while attempts < 60:  # 最多等 ~10 分钟
        ts  = int(time.time() * 1000)
        r   = random.randint(-2_147_483_648, -1)
        try:
            resp = s.get(POLL_URL, params={
                "loginicon": "true",
                "uuid": uuid,
                "tip": str(tip),
                "r": str(r),
                "_": str(ts),
            }, timeout=30)
        except Exception:
            time.sleep(2)
            attempts += 1
            continue

        text = resp.text
        m = re.search(r"window\.code=(\d+)", text)
        if not m:
            time.sleep(2)
            attempts += 1
            continue

        code = int(m.group(1))

        if code == 200:
            uri_m = re.search(r'window\.redirect_uri="([^"]+)"', text)
            if uri_m:
                print("\n✅ 登录确认，正在获取 Cookie...")
                return uri_m.group(1)
            return None

        elif code == 201:
            if not scanned:
                print("✓ 已扫码，请在手机上点击「确认登录」", flush=True)
                scanned = True
            tip = 0

        elif code == 408:
            # 轮询超时，继续等
            print(".", end="", flush=True)
            tip = 1

        else:
            print(f"\n登录返回未知 code={code}，退出")
            return None

        time.sleep(1)
        attempts += 1

    print("\n⚠️  等待超时（超过 10 分钟）")
    return None


# ── Step 4: 跟随重定向，获取基础 Cookie ─────────────────────────

def _parse_set_cookie(resp) -> dict[str, str]:
    """从单个响应的 Set-Cookie header 解析 Cookie"""
    result: dict[str, str] = {}
    # curl_cffi 有时把多个 Set-Cookie 合并，有时是列表
    raw = resp.headers.get("set-cookie") or resp.headers.get("Set-Cookie") or ""
    if not raw:
        return result
    entries = raw if isinstance(raw, list) else [raw]
    for entry in entries:
        # 每条格式: name=value; Path=/; Domain=.qq.com; ...
        first = entry.split(";")[0].strip()
        if "=" in first:
            k, _, v = first.partition("=")
            k, v = k.strip(), v.strip()
            if k and v:
                result[k] = v
    return result


def do_login(s: Session, redirect_uri: str) -> dict:
    """手动逐跳跟随重定向，在每一跳采集 Set-Cookie 和 XML body。
    curl_cffi 的 allow_redirects=True 会在 libcurl 层跟随，
    Python 层 s.cookies 不一定会更新，所以改为手动跳转。
    """
    import urllib.parse as _up

    if "fun=new" not in redirect_uri:
        redirect_uri += "&fun=new&version=v2&lang=zh_CN"

    all_cookies: dict[str, str] = {}
    url = redirect_uri
    final_body = ""

    for step in range(8):
        print(f"      [debug] hop {step}: {url[:80]}")
        try:
            resp = s.get(url, allow_redirects=False, timeout=15)
        except Exception as e:
            print(f"      [debug] request error: {e}")
            break

        print(f"      [debug] status={resp.status_code}")

        # 采集这一跳的 Set-Cookie
        hop_cookies = _parse_set_cookie(resp)
        if hop_cookies:
            print(f"      [debug] Set-Cookie: {list(hop_cookies.keys())}")
            all_cookies.update(hop_cookies)

        # 也从 resp.cookies 采集（curl_cffi 有时会填）
        try:
            for k, v in resp.cookies.items():
                if v:
                    all_cookies[k] = v
        except Exception:
            pass

        final_body = resp.text or ""

        # 继续跟随重定向
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location") or resp.headers.get("location", "")
            if not location:
                break
            # 处理相对路径
            if location.startswith("/"):
                parsed = _up.urlparse(url)
                location = f"{parsed.scheme}://{parsed.netloc}{location}"
            url = location
        else:
            break

    # ── XML body 提取（最终跳的响应体，最可靠）
    # 格式: <error><ret>0</ret><skey>@xxx</skey><wxsid>xxx</wxsid><wxuin>123</wxuin><pass_ticket>xxx</pass_ticket>...
    for tag in ("pass_ticket", "skey", "wxsid", "wxuin"):
        if not all_cookies.get(tag):
            m = re.search(rf"<{tag}>([^<]+)</{tag}>", final_body)
            if m and m.group(1) not in ("", "0"):
                all_cookies[tag] = m.group(1)
                print(f"      [debug] XML body: {tag}=...")

    print(f"      [debug] Cookie keys: {sorted(all_cookies.keys())}")

    # 别名规范化
    for alias, src in (("uin", "wxuin"), ("key", "wxsid")):
        if src in all_cookies and alias not in all_cookies:
            all_cookies[alias] = all_cookies[src]

    return {k: v for k, v in all_cookies.items() if v}


# ── Step 5: 获取 appmsg_token ───────────────────────────────────

def get_appmsg_token(s: Session) -> str:
    """
    访问 mp.weixin.qq.com 触发 appmsg_token cookie 下发。
    使用一个任意公众号的 __biz 触发（不需要该账号真实存在）。
    """
    try:
        s.get(PROFILE_URL, params={
            "action": "home",
            "__biz": "MzI2NDY1MTA3NA==",
            "scene": "124",
        }, timeout=10)
        token = s.cookies.get("appmsg_token", "")
        if token:
            return token
        # 尝试从响应 HTML 提取
    except Exception as e:
        print(f"  [warn] appmsg_token 获取失败: {e}", file=sys.stderr)
    return ""


# ── 保存 Cookie ─────────────────────────────────────────────────

def build_cookie_str(cookies: dict, appmsg_token: str) -> str:
    parts = []
    for k, v in cookies.items():
        if v:
            parts.append(f"{k}={v}")
    if appmsg_token:
        parts.append(f"appmsg_token={appmsg_token}")
    return "; ".join(parts)


def save(cookie_str: str, cookies: dict, appmsg_token: str) -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cookie": cookie_str,
        "raw": {**cookies, "appmsg_token": appmsg_token},
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Cookie 有效期约 30 天，过期后重新运行 weixin_auth.py",
    }
    COOKIE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"\n💾 Cookie 已保存到: {COOKIE_FILE}")


# ── 主流程 ───────────────────────────────────────────────────────

def main() -> None:
    print("=" * 50)
    print("  微信网页版登录 — 自动 Cookie 配置工具")
    print("=" * 50)

    s = make_session()

    print("\n[1/4] 获取登录二维码...")
    uuid = get_uuid(s)
    print(f"      UUID: {uuid}")

    print("\n[2/4] 显示二维码（请用微信 App 扫描）")
    show_qrcode(uuid)

    print("[3/4] 等待扫码并确认登录...")
    redirect_uri = poll_login(s, uuid)
    if not redirect_uri:
        print("❌ 登录失败，请重试")
        sys.exit(1)

    print("\n[4/4] 提取 Cookie...")
    cookies = do_login(s, redirect_uri)

    # 只要拿到任何实质性 cookie 就继续（微信分片域导致 key 名不固定）
    if not cookies:
        print("❌ Cookie 提取失败，可能是登录被拒绝或 API 变更")
        sys.exit(1)

    uin_val = cookies.get("wxuin") or cookies.get("uin", "?")
    print(f"      基础 Cookie 获取成功: uin={str(uin_val)[:10]}...")

    print("      获取 appmsg_token...")
    appmsg_token = get_appmsg_token(s)
    if appmsg_token:
        print(f"      appmsg_token: {appmsg_token[:16]}...")
    else:
        print("      appmsg_token 未获取到（部分功能可能受限）")

    cookie_str = build_cookie_str(cookies, appmsg_token)
    save(cookie_str, cookies, appmsg_token)

    print("\n✅ 登录完成！后续抓取脚本将自动使用此 Cookie。")
    print(f"\n   验证方式（dry-run）：")
    print(f"   uv run --with '...' fetch_weixin_account.py \\")
    print(f"       --biz MzE5ODIxMjc5Ng== --since 2026-05-01 --dry-run \\")
    print(f"       --account-name '翻倍翻倍再翻倍88' --kb-root Knowledge_Wiki")


if __name__ == "__main__":
    main()
