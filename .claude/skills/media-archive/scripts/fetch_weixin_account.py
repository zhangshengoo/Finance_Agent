#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "curl_cffi==0.9.0",
#   "readability-lxml==0.8.1",
#   "lxml-html-clean",
#   "html2text==2024.2.26",
#   "beautifulsoup4==4.12.3",
#   "lxml==5.2.2",
# ]
# ///
"""
批量抓取微信公众号文章（按日期范围）→ raw/weixin/<account-slug>/

Cookie 凭据（一次性保存，之后自动使用）：
    python weixin_auth.py --save "uin=xxx; key=yyy; pass_ticket=zzz; appmsg_token=aaa"

单账号用法：
    uv run --with '...' fetch_weixin_account.py \\
        --biz MzE5ODIxMjc5Ng== \\
        --since 2026-05-01 --until 2026-06-30 \\
        --kb-root /path/to/Knowledge_Wiki

多账号批量（batch 文件每行一个 biz，# 开头为注释）：
    uv run --with '...' fetch_weixin_account.py \\
        --batch-file accounts.txt \\
        --since 2026-05-01 --until 2026-06-30 \\
        --kb-root /path/to/Knowledge_Wiki

发现策略（自动按顺序降级）：
    1. profile_ext 分页 API（有 Cookie 时，最完整）
    2. Sogou 微信搜索（无需 Cookie，公开账号可用，可能有遗漏）
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from curl_cffi.requests import Session
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bilibili_common import (
    HTTP_TIMEOUT, IMPERSONATE, assert_kb_layout, resolve_kb_root,
)

# ── 常量 ────────────────────────────────────────────────────────
PROFILE_HOME = "https://mp.weixin.qq.com/mp/profile_ext"
SOGOU_SEARCH  = "https://weixin.sogou.com/weixin"
FETCH_SCRIPT  = Path(__file__).parent / "fetch_weixin.py"
COOKIE_FILE   = Path.home() / ".config" / "weixin-archive" / "cookies.json"
DEPS = (
    "curl_cffi==0.9.0,readability-lxml==0.8.1,lxml-html-clean,"
    "html2text==2024.2.26,beautifulsoup4==4.12.3,lxml==5.2.2"
)


# ── 日志 ────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ── Cookie 持久化 ────────────────────────────────────────────────

def load_cookie(explicit: str = "") -> str:
    """优先用显式参数，其次读 Cookie 文件"""
    if explicit:
        return explicit
    if COOKIE_FILE.exists():
        try:
            data = json.loads(COOKIE_FILE.read_text())
            c = data.get("cookie", "")
            if c:
                _log(f"[auth] 已从 {COOKIE_FILE} 加载 Cookie")
                return c
        except Exception:
            pass
    return ""


def save_cookie(cookie: str) -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(json.dumps({"cookie": cookie}, ensure_ascii=False, indent=2))
    _log(f"[auth] Cookie 已保存到 {COOKIE_FILE}")


# ── HTTP 客户端 ─────────────────────────────────────────────────

def make_client(cookie: str = "", mobile: bool = False) -> Session:
    ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
        "MicroMessenger/8.0.49 NetType/WIFI Language/zh_CN"
        if mobile else
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://mp.weixin.qq.com/",
        "User-Agent": ua,
    }
    if cookie:
        headers["Cookie"] = cookie
    return Session(impersonate=IMPERSONATE, timeout=HTTP_TIMEOUT, headers=headers)


# ── __biz 解析 ──────────────────────────────────────────────────

def resolve_biz(url: str | None, biz: str | None, cookie: str) -> str:
    if biz:
        return biz
    if not url:
        raise ValueError("必须提供 --biz 或 --url")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "__biz" in qs:
        return qs["__biz"][0]
    # 短链：跟随重定向后从 HTML 提取
    _log(f"[biz] 从短链提取 __biz: {url}")
    client = make_client(cookie)
    try:
        resp = client.get(url, allow_redirects=True)
        final_qs = urllib.parse.parse_qs(urllib.parse.urlparse(str(resp.url)).query)
        if "__biz" in final_qs:
            return final_qs["__biz"][0]
        for pat in (
            r'["\']?__biz["\']?\s*[:=]\s*["\']([^"\'&\s]+)["\']',
            r'var\s+biz\s*=\s*["\']([^"\']+)["\']',
        ):
            m = re.search(pat, resp.text)
            if m:
                return m.group(1)
    finally:
        client.close()
    raise ValueError(f"无法从 URL 提取 __biz: {url}")


# ── 文章列表解析 ────────────────────────────────────────────────

def ts_to_date8(ts: int) -> str:
    return dt.datetime.fromtimestamp(
        ts, tz=dt.timezone(dt.timedelta(hours=8))
    ).strftime("%Y-%m-%d")


def norm_url(raw: str) -> str:
    return raw.replace("\\u0026", "&").replace("&amp;", "&").lstrip("/").replace("//", "https://", 1) if raw.startswith("//") else raw


def parse_msg_list(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except Exception:
        return []
    articles = []
    for item in data.get("list", []):
        ext  = item.get("app_msg_ext_info", {})
        comm = item.get("comm_msg_info", {})
        pub_ts   = int(comm.get("datetime", 0))
        pub_date = ts_to_date8(pub_ts) if pub_ts else ""

        def add(e: dict) -> None:
            u = e.get("content_url", "")
            u = u.replace("\\u0026", "&").replace("&amp;", "&")
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith("http"):
                return
            articles.append({"title": e.get("title", ""), "url": u,
                              "ts": pub_ts, "date": pub_date})

        add(ext)
        for sub in ext.get("multi_app_msg_item_list", []):
            add(sub)
    return articles


# ── 发现策略 1: profile_ext（需 Cookie）────────────────────────

def _profile_home(client: Session, biz: str) -> tuple[list[dict], str]:
    params = {"action": "home", "__biz": biz, "scene": "124", "bizpsid": "0"}
    resp = client.get(PROFILE_HOME, params=params)
    resp.raise_for_status()
    html = resp.text

    # 公众号名
    account = ""
    soup = BeautifulSoup(html, "lxml")
    for sel in [
        lambda s: s.find("strong", class_="profile_nickname"),
        lambda s: s.find(id="js_name"),
    ]:
        tag = sel(soup)
        if tag:
            account = tag.get_text(strip=True)
            break

    # msgList JSON
    arts: list[dict] = []
    for pat in (
        r"var\s+msgList\s*=\s*'(\{.*?\})'",
        r"var\s+msgList\s*=\s*(\{.*?\})\s*;",
    ):
        m = re.search(pat, html, re.DOTALL)
        if m:
            raw = m.group(1)
            try:
                raw = raw.encode("raw_unicode_escape").decode("unicode_escape")
            except Exception:
                pass
            arts = parse_msg_list(raw)
            break

    return arts, account


def _profile_page(client: Session, biz: str, offset: int) -> tuple[list[dict], int, bool]:
    params = {
        "action": "getmsg", "__biz": biz, "f": "json",
        "offset": str(offset), "count": "10", "is_ok": "1", "scene": "124",
    }
    try:
        resp = client.get(PROFILE_HOME, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        _log(f"[profile] 分页请求失败: {e}")
        return [], offset, False

    if data.get("ret", -1) != 0:
        _log(f"[profile] ret={data.get('ret')} — Cookie 无效或已过期")
        return [], offset, False

    raw = data.get("general_msg_list", "{}")
    arts = parse_msg_list(raw if isinstance(raw, str) else json.dumps(raw))
    next_off = int(data.get("next_offset", offset))
    return arts, next_off, bool(arts) and next_off != offset


def discover_via_profile(biz: str, since: dt.date, until: dt.date, cookie: str) -> tuple[list[dict], str]:
    """用 profile_ext API 翻页（需 Cookie）。返回 (articles, account_name)"""
    client = make_client(cookie)
    all_arts: list[dict] = []
    account = ""
    try:
        home_arts, account = _profile_home(client, biz)
        _log(f"[profile] 首页 {len(home_arts)} 篇，账号={account!r}")
        all_arts.extend(home_arts)

        dated = [a for a in home_arts if a["ts"]]
        oldest = dt.date.fromisoformat(ts_to_date8(min(a["ts"] for a in dated))) if dated else until
        offset = len(home_arts)

        while oldest > since:
            time.sleep(1.5)
            _log(f"[profile] 翻页 offset={offset}，当前最早={oldest}")
            more, offset, has_more = _profile_page(client, biz, offset)
            if not has_more:
                break
            all_arts.extend(more)
            dated_more = [a for a in more if a["ts"]]
            if dated_more:
                oldest = dt.date.fromisoformat(ts_to_date8(min(a["ts"] for a in dated_more)))
    finally:
        client.close()
    return all_arts, account


# ── 发现策略 2: Sogou 微信搜索（无需 Cookie）──────────────────

def _sogou_account_id(client: Session, account_name: str) -> str | None:
    """通过账号名找到 Sogou 的 wid（账号标识），用于精确过滤"""
    params = {"type": "1", "query": account_name, "ie": "utf8"}
    try:
        resp = client.get(SOGOU_SEARCH, params=params)
        resp.raise_for_status()
        m = re.search(r'wap_profile_ext\.shtml\?openid=([^&"]+)', resp.text)
        if m:
            return m.group(1)
        # 备用：从账号卡片提取 wid
        m = re.search(r'"wid"\s*:\s*"([^"]+)"', resp.text)
        return m.group(1) if m else None
    except Exception as e:
        _log(f"[sogou] 账号 ID 查询失败: {e}")
        return None


def _sogou_articles_page(client: Session, query: str, page: int, account_id: str | None) -> list[dict]:
    """抓一页 Sogou 搜索结果"""
    params: dict = {"type": "2", "query": query, "ie": "utf8", "page": str(page)}
    if account_id:
        params["account"] = account_id
    try:
        resp = client.get(SOGOU_SEARCH, params=params)
        resp.raise_for_status()
    except Exception as e:
        _log(f"[sogou] 页 {page} 请求失败: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    arts = []
    for item in soup.select(".news-box .news-list li, #main .news-list li"):
        a_tag = item.select_one("h3 a, .txt-box h3 a")
        if not a_tag:
            continue
        url = a_tag.get("href", "")
        # Sogou 结果链接可能是 sogou 跳转链接，需还原
        if "weixin.sogou.com" in url:
            m = re.search(r'url=([^&]+)', url)
            if m:
                url = urllib.parse.unquote(m.group(1))
        if "mp.weixin.qq.com" not in url:
            continue
        title = a_tag.get_text(strip=True)

        # 日期：Sogou 结果里通常有 <span class="s2"> 1小时前 / 2026-06-01 </span>
        date_str = ""
        date_tag = item.select_one(".s2, .time, .news-time")
        if date_tag:
            raw_date = date_tag.get_text(strip=True)
            m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", raw_date)
            if m:
                date_str = m.group(1).replace("/", "-")
            elif "小时前" in raw_date or "分钟前" in raw_date:
                date_str = dt.date.today().isoformat()
            elif "昨天" in raw_date:
                date_str = (dt.date.today() - dt.timedelta(days=1)).isoformat()

        arts.append({"title": title, "url": url, "ts": 0, "date": date_str})

    return arts


def discover_via_sogou(
    account_name: str, biz: str, since: dt.date, until: dt.date
) -> list[dict]:
    """用 Sogou 搜索发现文章（无需 Cookie，但覆盖率低于 profile_ext）"""
    if not account_name:
        _log("[sogou] 未知账号名，跳过 Sogou 发现")
        return []

    _log(f"[sogou] 搜索账号 {account_name!r}")
    client = make_client()
    all_arts: list[dict] = []
    try:
        account_id = _sogou_account_id(client, account_name)
        _log(f"[sogou] account_id={account_id!r}")

        for page in range(1, 20):
            time.sleep(2.0)
            arts = _sogou_articles_page(client, account_name, page, account_id)
            if not arts:
                break

            # 过滤 __biz 不匹配的（多账号同名时去杂）
            if biz:
                arts = [a for a in arts if biz not in a["url"] or biz in a["url"]]
                # 精确：只保留 URL 里含有此 biz 的（若 URL 带 __biz 参数）
                filtered_biz = [
                    a for a in arts
                    if biz in urllib.parse.unquote(a["url"])
                ]
                if filtered_biz:
                    arts = filtered_biz

            all_arts.extend(arts)
            _log(f"[sogou] 第 {page} 页 {len(arts)} 篇，累计 {len(all_arts)}")

            # 这一页所有有日期的文章都早于 since，或晚于 until，停止翻页
            dated = [a for a in arts if a["date"]]
            if dated and all(
                dt.date.fromisoformat(a["date"]) < since
                for a in dated
            ):
                break
            if dated and all(
                dt.date.fromisoformat(a["date"]) > until
                for a in dated
            ):
                continue  # 结果还太新，继续翻页
    finally:
        client.close()

    return all_arts


# ── 统一发现入口 ─────────────────────────────────────────────────

def discover_articles(
    biz: str,
    since: dt.date,
    until: dt.date,
    cookie: str,
    account_name: str = "",
) -> list[dict]:
    """按策略顺序发现文章，合并去重，过滤日期范围"""
    all_arts: list[dict] = []

    if cookie:
        arts, discovered_name = discover_via_profile(biz, since, until, cookie)
        all_arts.extend(arts)
        if not account_name and discovered_name:
            account_name = discovered_name
        _log(f"[discover] profile_ext 发现 {len(arts)} 篇")
    else:
        _log("[discover] 无 Cookie，跳过 profile_ext")

    # Sogou 补充（有 Cookie 时仍可补充，无 Cookie 时作为主路径）
    sogou_arts = discover_via_sogou(account_name, biz, since, until)
    _log(f"[discover] Sogou 发现 {len(sogou_arts)} 篇")
    all_arts.extend(sogou_arts)

    # 去重（URL 为唯一键）+ 日期过滤
    seen: set[str] = set()
    result: list[dict] = []
    for a in all_arts:
        url = a["url"]
        if url in seen:
            continue
        seen.add(url)
        if a.get("date"):
            try:
                d = dt.date.fromisoformat(a["date"])
            except ValueError:
                continue
            if not (since <= d <= until):
                continue
        # 无日期的文章（ts=0）也保留，让 fetch_weixin 拿到真实日期后再判断
        result.append(a)

    return sorted(result, key=lambda x: x["ts"], reverse=True)


# ── 单篇抓取（子进程调用 fetch_weixin.py）───────────────────────

def fetch_article(url: str, kb_root: str, no_images: bool) -> dict:
    cmd = [
        "uv", "run", "--with", DEPS,
        str(FETCH_SCRIPT),
        "--kb-root", kb_root,
        "--url", url,
    ]
    if no_images:
        cmd.append("--no-images")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = (r.stdout or "").strip()
        if out:
            return json.loads(out)
        return {"written": None, "errors": {"stderr": (r.stderr or "")[-400:]}, "url": url}
    except subprocess.TimeoutExpired:
        return {"written": None, "errors": {"timeout": "120s"}, "url": url}
    except Exception as e:
        return {"written": None, "errors": {"exception": str(e)}, "url": url}


# ── 批量处理一个账号 ─────────────────────────────────────────────

def process_account(
    biz: str,
    since: dt.date,
    until: dt.date,
    kb_root: str,
    cookie: str,
    no_images: bool,
    delay: float,
    dry_run: bool,
    account_name: str = "",
) -> dict:
    _log(f"\n{'='*60}")
    _log(f"[account] biz={biz} name={account_name!r}  {since} ~ {until}")

    articles = discover_articles(biz, since, until, cookie, account_name)
    _log(f"[account] 共发现 {len(articles)} 篇文章")

    if dry_run:
        for a in articles:
            print(f"  {a['date']}  {a['title'][:60]}")
            print(f"           {a['url'][:80]}")
        return {"biz": biz, "discovered": len(articles), "dry_run": True}

    written, skipped, errors = [], [], []
    for i, a in enumerate(articles, 1):
        _log(f"  [{i}/{len(articles)}] {a['date']} {a['title'][:50]}")
        r = fetch_article(a["url"], kb_root, no_images)
        if r.get("written"):
            written.append(r["written"])
            _log(f"    ✓ {r['written']}")
        elif r.get("skipped"):
            skipped.append(r["skipped"])
            _log(f"    - 已存在: {r['skipped']}")
        else:
            errors.append({"url": a["url"], "error": r.get("errors", {})})
            _log(f"    ✗ {r.get('errors', {})}")
        if i < len(articles):
            time.sleep(delay)

    return {
        "biz": biz,
        "account": account_name,
        "total": len(articles),
        "written": written,
        "skipped": skipped,
        "errors": errors,
    }


# ── main ─────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="批量抓取公众号文章（日期范围，支持多账号）")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--biz", help="单账号 __biz")
    grp.add_argument("--url", help="任意一篇文章 URL（自动提取 __biz）")
    grp.add_argument("--batch-file", help="多账号批量：每行一个 biz（# 开头为注释）")
    ap.add_argument("--account-name", default="", help="公众号名（辅助 Sogou 搜索）")
    ap.add_argument("--since", required=True, help="起始日期 YYYY-MM-DD（含）")
    ap.add_argument("--until", default=None, help="截止日期 YYYY-MM-DD（含，默认今天）")
    ap.add_argument("--kb-root", default=None)
    ap.add_argument("--cookie", default="", help="WeChat Cookie（覆盖存储文件）")
    ap.add_argument("--save-cookie", metavar="COOKIE_STR",
                    help="保存 Cookie 字符串到 ~/.config/weixin-archive/cookies.json 后退出")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--delay", type=float, default=4.0, help="每篇文章间隔秒（默认 4）")
    ap.add_argument("--dry-run", action="store_true", help="只列出文章，不实际抓取")
    args = ap.parse_args()

    # 保存 Cookie 并退出
    if args.save_cookie:
        save_cookie(args.save_cookie)
        print(f"Cookie 已保存到 {COOKIE_FILE}")
        return

    # 加载 Cookie（显式 > 文件）
    cookie = load_cookie(args.cookie)
    if not cookie:
        _log("[auth] 未找到 Cookie，将仅使用 Sogou 发现（覆盖率有限）")
        _log(f"[auth] 提示：运行 python weixin_auth.py --save '<cookie>' 保存凭据")

    kb_root = resolve_kb_root(args.kb_root)
    assert_kb_layout(kb_root)

    since = dt.date.fromisoformat(args.since)
    until = dt.date.fromisoformat(args.until) if args.until else dt.date.today()

    # 构建账号列表
    accounts: list[tuple[str, str]] = []  # (biz, name)

    if args.batch_file:
        lines = Path(args.batch_file).read_text().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            b = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            accounts.append((b, name))
        _log(f"[batch] 读取 {len(accounts)} 个账号")
    else:
        tmp_client = make_client(cookie)
        try:
            biz = resolve_biz(args.url, args.biz, cookie)
        finally:
            tmp_client.close()
        accounts = [(biz, args.account_name)]

    # 批量处理
    all_results = []
    for biz, name in accounts:
        result = process_account(
            biz=biz, since=since, until=until,
            kb_root=kb_root, cookie=cookie,
            no_images=args.no_images, delay=args.delay,
            dry_run=args.dry_run, account_name=name,
        )
        all_results.append(result)
        if len(accounts) > 1:
            time.sleep(5.0)  # 账号间额外间隔

    print(json.dumps(
        all_results if len(all_results) > 1 else all_results[0],
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
