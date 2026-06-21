#!/usr/bin/env python3
"""
Mac 微信 Cookie 自动提取工具（mitmproxy 方案）

原理：
  1. 启动 mitmproxy 本地代理（端口 8088）
  2. 用 networksetup 自动配置 macOS 系统代理
  3. 等待你在微信 App 里打开任意一篇公众号文章
  4. 自动拦截请求中的 Cookie（含 appmsg_token）并保存
  5. 恢复代理设置、退出

依赖：
  brew install mitmproxy   （第一次用时需要）

用法：
  python3 weixin_auth_mac.py

完成后 Cookie 保存到 ~/.config/weixin-archive/cookies.json，
之后运行 fetch_weixin_account.py 无需任何额外参数。
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

COOKIE_FILE  = Path.home() / ".config" / "weixin-archive" / "cookies.json"
PROXY_PORT   = 8088
TARGET_HOST  = "mp.weixin.qq.com"
TIMEOUT_SECS = 180  # 等待用户打开文章的最长时间


# ── 检查 mitmproxy ────────────────────────────────────────────

def check_mitmproxy() -> str:
    path = shutil.which("mitmdump")
    if not path:
        print("❌ 未找到 mitmproxy，请先安装：")
        print("   brew install mitmproxy")
        sys.exit(1)
    return path


# ── 获取活跃网络服务名 ─────────────────────────────────────────

def get_network_service() -> str:
    """返回当前连接的主网络服务名（Wi-Fi 或 以太网等）"""
    try:
        result = subprocess.run(
            ["networksetup", "-listallnetworkservices"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().splitlines()
        for name in ("Wi-Fi", "Ethernet", "USB 10/100/1000 LAN", "Thunderbolt Ethernet"):
            if any(name in l for l in lines):
                return name
        # 取第二行（跳过第一行说明）
        return lines[1] if len(lines) > 1 else "Wi-Fi"
    except Exception:
        return "Wi-Fi"


# ── macOS 系统代理 ────────────────────────────────────────────

def set_proxy(service: str, host: str, port: int) -> None:
    for proto in ("webproxy", "securewebproxy"):
        subprocess.run(
            ["networksetup", f"-set{proto}", service, host, str(port)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["networksetup", f"-set{proto}state", service, "on"],
            check=True, capture_output=True,
        )
    print(f"  [proxy] {service} → 127.0.0.1:{port}")


def unset_proxy(service: str) -> None:
    for proto in ("webproxy", "securewebproxy"):
        try:
            subprocess.run(
                ["networksetup", f"-set{proto}state", service, "off"],
                check=True, capture_output=True,
            )
        except Exception:
            pass
    print(f"  [proxy] {service} 代理已恢复")


# ── mitmproxy CA 证书安装 ─────────────────────────────────────

CERT_PATH = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"


def ensure_cert_generated() -> None:
    """运行一次 mitmdump 让它生成 CA 证书"""
    if CERT_PATH.exists():
        return
    print("  [cert] 首次运行，生成 mitmproxy CA 证书...")
    proc = subprocess.Popen(
        ["mitmdump", "--listen-port", str(PROXY_PORT + 1), "-q"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    proc.terminate()
    proc.wait()


def _login_keychain() -> str:
    """返回当前用户的 login keychain 路径"""
    p = Path.home() / "Library" / "Keychains" / "login.keychain-db"
    return str(p) if p.exists() else "login.keychain"


def install_cert() -> bool:
    """把 mitmproxy CA 证书加入用户 Login Keychain（无需 sudo，会弹钥匙串密码窗）"""
    if not CERT_PATH.exists():
        print("  [cert] 证书文件不存在，跳过")
        return False

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  接下来临时安装 mitmproxy 根证书到用户 Login Keychain    │")
    print("  │  • 不需要 sudo，但系统可能弹出钥匙串密码窗口             │")
    print("  │  • 证书仅存在于 Cookie 捕获期间，捕获后立即自动移除     │")
    print("  │  • 微信支付有独立证书固定保护，不受影响                  │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()

    keychain = _login_keychain()
    result = subprocess.run(
        [
            "security", "add-trusted-cert",
            "-d", "-r", "trustRoot",
            "-k", keychain,
            str(CERT_PATH),
        ]
    )
    if result.returncode == 0:
        print("  [cert] 证书已临时安装到 Login Keychain ✓")
        return True
    else:
        print("  [cert] 证书安装失败（可能被拒绝或钥匙串锁定）")
        print("         请手动运行：")
        print(f"         security add-trusted-cert -d -r trustRoot -k {keychain} {CERT_PATH}")
        return False


def remove_cert() -> None:
    """Cookie 捕获完成后立即从 Login Keychain 移除 mitmproxy CA 证书"""
    print("  [cert] 正在移除临时证书...")
    keychain = _login_keychain()
    result = subprocess.run(
        ["security", "delete-certificate", "-c", "mitmproxy", keychain],
        capture_output=True,
    )
    if result.returncode == 0:
        print("  [cert] 临时证书已移除 ✓")
    else:
        print("  ⚠️  请手动删除：打开「钥匙串访问」→ 登录 → 证书 → 搜索 mitmproxy → 删除")


# ── mitmproxy addon 脚本 ──────────────────────────────────────

def write_addon(capture_file: Path) -> Path:
    addon_code = textwrap.dedent(f"""\
        import json
        from pathlib import Path
        from mitmproxy import http

        TARGET = "{TARGET_HOST}"
        CAPTURE = Path("{capture_file}")
        KEYWORDS = ("appmsg_token", "pass_ticket", "uin=")

        class WeixinCapture:
            def request(self, flow: http.HTTPFlow) -> None:
                if TARGET not in flow.request.pretty_host:
                    return
                cookie = flow.request.headers.get("cookie", "")
                # 只保存包含关键字段的 Cookie
                if not any(kw in cookie for kw in KEYWORDS):
                    return
                CAPTURE.write_text(json.dumps({{"cookie": cookie}}, ensure_ascii=False))
                print(f"\\n✅ 已捕获 Cookie（{{len(cookie)}} bytes）")

        addons = [WeixinCapture()]
    """)
    tmp = Path(tempfile.mktemp(suffix="_weixin_addon.py"))
    tmp.write_text(addon_code)
    return tmp


# ── 主流程 ───────────────────────────────────────────────────

def main() -> None:
    print("=" * 55)
    print("  Mac 微信 Cookie 自动提取 — mitmproxy 方案")
    print("=" * 55)

    mitmdump = check_mitmproxy()
    service  = get_network_service()
    print(f"\n  网络服务: {service}")

    # 生成并安装证书
    ensure_cert_generated()
    cert_installed = install_cert()

    # 临时文件：cookie capture 输出
    capture_file = Path(tempfile.mktemp(suffix="_weixin_cookie.json"))
    addon_file   = write_addon(capture_file)

    # cert_installed 必须在 cleanup 闭包之前定义，且用列表包装以便闭包内修改
    cert_installed = [False]

    # 注册清理函数（Ctrl+C、正常退出、异常都执行）—— 先定义，后面随时可注册
    proc_ref = [None]

    def cleanup(sig=None, frame=None):
        print("\n\n  清理中...")
        if proc_ref[0] is not None:
            proc_ref[0].terminate()
            try:
                proc_ref[0].wait(timeout=3)
            except Exception:
                proc_ref[0].kill()
        unset_proxy(service)
        if cert_installed[0]:
            remove_cert()  # ← 安全关键：无论成功/失败/中断都移除证书
        addon_file.unlink(missing_ok=True)
        capture_file.unlink(missing_ok=True)
        if sig:
            sys.exit(0)

    signal.signal(signal.SIGINT,  cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 安装证书（在启动代理前完成，顺序很重要）
    cert_installed[0] = install_cert()

    # 设置系统代理
    print("\n[1/3] 配置系统代理...")
    set_proxy(service, "127.0.0.1", PROXY_PORT)

    # 启动 mitmdump
    # --allow-hosts: 只解密 mp.weixin.qq.com 的 HTTPS，其他域名原样透传（不解密）
    # 这是核心安全控制：银行/邮件等其他 App 的 HTTPS 流量不会被解密
    print(f"[2/3] 启动 mitmproxy（端口 {PROXY_PORT}，仅拦截 mp.weixin.qq.com）...")
    proc = subprocess.Popen(
        [
            mitmdump,
            "--listen-port", str(PROXY_PORT),
            "--allow-hosts", r"mp\.weixin\.qq\.com",  # 只解密微信公众号域名
            "-q",
            "-s", str(addon_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc_ref[0] = proc

    print()
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║  请在 Mac 微信 App 里随便打开一篇公众号文章       ║")
    print("  ║  脚本会自动拦截并保存登录 Cookie                  ║")
    print(f"  ║  等待时间：最多 {TIMEOUT_SECS} 秒                          ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print()

    # 等待 Cookie 被捕获
    print("[3/3] 等待微信请求...", end="", flush=True)
    deadline = time.time() + TIMEOUT_SECS
    captured_cookie = ""

    while time.time() < deadline:
        # 读取 mitmdump stdout（非阻塞轮询）
        if proc.poll() is not None:
            print("\n⚠️  mitmproxy 意外退出")
            break

        if capture_file.exists():
            try:
                data = json.loads(capture_file.read_text())
                captured_cookie = data.get("cookie", "")
                if captured_cookie:
                    break
            except Exception:
                pass

        print(".", end="", flush=True)
        time.sleep(2)

    # 清理代理和进程
    cleanup()

    if not captured_cookie:
        print("\n❌ 未能捕获 Cookie（超时或未打开文章）")
        print("   提示：确保在 macOS 系统偏好设置里证书已被信任")
        sys.exit(1)

    # 保存 Cookie
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(json.dumps({
        "cookie": captured_cookie,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "由 weixin_auth_mac.py 自动提取，有效期约 30 天",
    }, ensure_ascii=False, indent=2))

    print(f"\n💾 Cookie 已保存到: {COOKIE_FILE}")
    print(f"   Cookie 长度: {len(captured_cookie)} bytes")
    print()
    print("✅ 配置完成！后续批量抓取全自动，无需人工干预。")
    print()
    print("   验证（dry-run）：")
    print("   uv run --with 'curl_cffi==0.9.0,...' fetch_weixin_account.py \\")
    print("       --biz MzE5ODIxMjc5Ng== --account-name '翻倍翻倍再翻倍88' \\")
    print("       --since 2026-05-01 --dry-run --kb-root Knowledge_Wiki")


if __name__ == "__main__":
    main()
