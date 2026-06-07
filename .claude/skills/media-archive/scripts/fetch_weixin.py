#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "curl_cffi==0.9.0",
#   "readability-lxml==0.8.1",
#   "html2text==2024.2.26",
#   "beautifulsoup4==4.12.3",
#   "lxml==5.2.2",
# ]
# ///
"""
微信公众号文章抓取 → 落 raw/news/weixin/<account-slug>/<date>-<title-slug>.md
图片下载 → raw/assets/weixin/<account-slug>/<date>-<title-slug>-<idx>.<ext>

用法：
    uv run --with 'curl_cffi==0.9.0,readability-lxml==0.8.1,html2text==2024.2.26,beautifulsoup4==4.12.3,lxml==5.2.2' \
        fetch_weixin.py \
        --kb-root /path/to/Knowledge_Wiki \
        --url 'https://mp.weixin.qq.com/s/xxxxxxx'

参数：
    --kb-root         Knowledge_Wiki 根
    --url             公众号文章 URL（必填，须以 https://mp.weixin.qq.com/s/ 开头）
    --no-images       不下载图片（默认下载）
    --overwrite       已存在覆盖

输出：
    stdout 汇总 JSON: {written:"...", skipped:null, errors:{...}, meta:{...}}
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse

from curl_cffi.requests import Session
from bs4 import BeautifulSoup
from readability import Document
import html2text

from _bilibili_common import (
    HTTP_TIMEOUT,
    IMPERSONATE,
    assert_kb_layout,
    ensure_dir,
    resolve_kb_root,
    slugify,
)


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_weixin_client() -> Session:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://mp.weixin.qq.com/",
    }
    return Session(impersonate=IMPERSONATE, timeout=HTTP_TIMEOUT, headers=headers)


def parse_meta(html: str, url: str) -> dict:
    """从公众号 HTML 中提取标题/账号/作者/发布时间/__biz"""
    soup = BeautifulSoup(html, "lxml")

    # 标题
    title = ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if not title:
        h1 = soup.find("h1", id="activity-name") or soup.find("h1", class_="rich_media_title")
        if h1:
            title = h1.get_text(strip=True)

    # 公众号名
    account = ""
    site = soup.find("meta", attrs={"property": "og:site_name"})
    if site and site.get("content"):
        account = site["content"].strip()
    if not account:
        nick = (soup.find("a", id="js_name")
                or soup.find("strong", class_="profile_nickname")
                or soup.find("a", class_="rich_media_meta_nickname"))
        if nick:
            account = nick.get_text(strip=True)

    # 作者
    author = ""
    a_tag = soup.find("meta", attrs={"name": "author"})
    if a_tag and a_tag.get("content"):
        author = a_tag["content"].strip()
    if not author:
        a_em = soup.find("em", id="js_author_name") or soup.find("span", id="js_author_name")
        if a_em:
            author = a_em.get_text(strip=True)

    # 发布时间：优先 <em id="publish_time">，再 JS 变量 ct/publish_time
    published_at = ""
    pub_em = soup.find("em", id="publish_time")
    if pub_em:
        published_at = pub_em.get_text(strip=True)
    if not published_at:
        for pattern in (
            r"var\s+publish_time\s*=\s*['\"]([^'\"]+)['\"]",
            r"var\s+ct\s*=\s*\"(\d+)\"",
            r"\"publish_time\"\s*:\s*\"?(\d+)\"?",
        ):
            m = re.search(pattern, html)
            if m:
                v = m.group(1)
                if v.isdigit():
                    try:
                        published_at = dt.datetime.fromtimestamp(int(v)).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                else:
                    published_at = v
                break

    # 标准化日期到 YYYY-MM-DD（容错处理 "2026-05-15 08:30" 等）
    if published_at:
        m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", published_at)
        if m:
            published_at = m.group(1).replace("/", "-")
            # 补零
            parts = published_at.split("-")
            if len(parts) == 3:
                published_at = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"

    # __biz
    biz = ""
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if "__biz" in qs:
        biz = qs["__biz"][0]
    if not biz:
        m = re.search(r"var\s+biz\s*=\s*['\"]([^'\"]+)['\"]", html)
        if m:
            biz = m.group(1)

    return {
        "title": title,
        "account": account,
        "author": author,
        "published_at": published_at or dt.date.today().isoformat(),
        "account_biz": biz,
    }


def extract_content_html(html: str) -> str:
    """优先取 #js_content；失败回退 readability"""
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("div", id="js_content")
    if body:
        return str(body)
    return Document(html).summary(html_partial=True)


def rewrite_images(content_html: str) -> tuple[str, list[dict]]:
    """把公众号 data-src 改写为 src（lazy-load 修复），返回 (新 html, 图片 list)
    每张图 dict: {original_url, ext, placeholder}
    """
    soup = BeautifulSoup(content_html, "lxml")
    images = []
    for idx, img in enumerate(soup.find_all("img")):
        src = img.get("data-src") or img.get("src") or ""
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith(("http://", "https://")):
            continue
        ext_raw = (img.get("data-type") or "").lower()
        if ext_raw in ("jpeg", "jpg", "png", "gif", "webp"):
            ext = "jpg" if ext_raw == "jpeg" else ext_raw
        else:
            ext = "jpg"
            tail = src.rsplit("/", 1)[-1]
            if "." in tail:
                guess = tail.rsplit(".", 1)[-1].split("?")[0].lower()
                if guess in ("jpg", "jpeg", "png", "gif", "webp"):
                    ext = "jpg" if guess == "jpeg" else guess
        placeholder = f"__WEIXIN_IMG_{idx}__"
        images.append({"original_url": src, "ext": ext, "placeholder": placeholder, "local_path": None})
        img["src"] = placeholder
        # 移除 data-src 等让 html2text 安静
        for attr in ("data-src", "data-type", "data-w", "data-ratio", "data-s"):
            if attr in img.attrs:
                del img.attrs[attr]
    return str(soup), images


def html_to_markdown(content_html: str) -> str:
    h = html2text.HTML2Text()
    h.body_width = 0  # 不强制换行
    h.ignore_links = False
    h.ignore_images = False
    return h.handle(content_html).strip()


def download_images(
    client: Session,
    images: list[dict],
    out_dir: str,
    name_prefix: str,
    kb_root: str,
) -> dict:
    ensure_dir(out_dir)
    errors = {}
    for idx, img in enumerate(images):
        fname = f"{name_prefix}-{idx}.{img['ext']}"
        fpath = os.path.join(out_dir, fname)
        try:
            time.sleep(0.3)
            r = client.get(img["original_url"])
            r.raise_for_status()
            with open(fpath, "wb") as f:
                f.write(r.content)
            img["local_path"] = os.path.relpath(fpath, kb_root)
        except Exception as e:
            errors[f"img{idx}"] = str(e)
    return errors


def replace_placeholders(markdown: str, images: list[dict], md_dir: str, kb_root: str) -> str:
    """把 markdown 里的占位符换成相对 md 文件的图片相对路径"""
    for img in images:
        if img.get("local_path"):
            abs_img = os.path.join(kb_root, img["local_path"])
            rel = os.path.relpath(abs_img, md_dir)
            markdown = markdown.replace(img["placeholder"], rel.replace(os.sep, "/"))
        else:
            # 下载失败：保留原 URL 以便事后修补
            markdown = markdown.replace(img["placeholder"], img["original_url"])
    return markdown


def render_frontmatter(meta: dict, url: str, images: list[dict]) -> str:
    fm = [
        "---",
        "source: weixin",
        f'account: "{meta["account"]}"',
        f'account_biz: "{meta["account_biz"]}"',
        f'author: "{meta["author"]}"',
        f'title: "{meta["title"].replace(chr(34), chr(39))}"',
        f"published_at: {meta['published_at']}",
        f"url: {url}",
        f"fetched_at: {_iso_now()}",
    ]
    if images:
        fm.append("images:")
        for img in images:
            if img.get("local_path"):
                fm.append(f"  - {img['local_path']}")
    fm.append("---")
    return "\n".join(fm)


def main():
    ap = argparse.ArgumentParser(description="公众号文章 → raw/news/weixin/")
    ap.add_argument("--kb-root", default=None)
    ap.add_argument("--url", required=True)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if not args.url.startswith("https://mp.weixin.qq.com/s"):
        print(json.dumps({
            "written": None, "skipped": None,
            "errors": {"url": "URL 必须以 https://mp.weixin.qq.com/s 开头"},
            "meta": {"url": args.url},
        }, ensure_ascii=False))
        sys.exit(1)

    kb_root = resolve_kb_root(args.kb_root)
    assert_kb_layout(kb_root)

    errors = {}
    client = create_weixin_client()
    try:
        resp = client.get(args.url)
        if resp.status_code != 200:
            errors["http"] = f"status={resp.status_code}"
            print(json.dumps({
                "written": None, "skipped": None,
                "errors": errors, "meta": {"url": args.url},
            }, ensure_ascii=False))
            sys.exit(1)
        html = resp.text

        meta = parse_meta(html, args.url)
        if not meta["title"]:
            errors["parse"] = "未能解析标题（页面可能已被删除或风控）"
        if not meta["account"]:
            meta["account"] = "unknown-account"

        content_html = extract_content_html(html)
        rewritten_html, images = rewrite_images(content_html)
        markdown_body = html_to_markdown(rewritten_html)

        account_slug = slugify(meta["account"])
        title_slug = slugify(meta["title"] or "untitled", max_len=30)
        date = meta["published_at"]
        name_prefix = f"{date}-{title_slug}"

        md_dir = os.path.join(kb_root, "raw", "news", "weixin", account_slug)
        ensure_dir(md_dir)
        md_path = os.path.join(md_dir, f"{name_prefix}.md")
        if os.path.exists(md_path) and not args.overwrite:
            print(json.dumps({
                "written": None,
                "skipped": os.path.relpath(md_path, kb_root),
                "errors": errors, "meta": {**meta, "url": args.url, "kb_root": kb_root},
            }, ensure_ascii=False))
            return

        if not args.no_images and images:
            img_dir = os.path.join(kb_root, "raw", "assets", "weixin", account_slug)
            errors.update(download_images(client, images, img_dir, name_prefix, kb_root))

        markdown_body = replace_placeholders(markdown_body, images, md_dir, kb_root)
        frontmatter = render_frontmatter(meta, args.url, images)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(frontmatter + "\n\n# " + (meta["title"] or "Untitled") + "\n\n" + markdown_body + "\n")
    finally:
        client.close()

    print(json.dumps({
        "written": os.path.relpath(md_path, kb_root),
        "skipped": None,
        "errors": errors,
        "meta": {**meta, "url": args.url, "kb_root": kb_root, "image_count": len(images)},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
