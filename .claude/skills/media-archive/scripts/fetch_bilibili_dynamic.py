#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0"]
# ///
"""
B 站动态抓取 → 落 raw/transcripts/bilibili/<uploader-slug>_dyn_<id>.json
图片下载 → raw/assets/bilibili/<uid>/<dynamic_id>_<idx>.<ext>

用法：
    uv run --with 'curl_cffi==0.9.0' fetch_bilibili_dynamic.py \
        --kb-root /path/to/Knowledge_Wiki \
        --uid 1039025435 --count 10 --download-images

参数：
    --kb-root   Knowledge_Wiki 根
    --uid       UP 主 UID（必填）
    --count     抓取数量
    --types     过滤类型，逗号分隔（draw,word,forward,video,article）
    --download-images   下载图片到 raw/assets/bilibili/<uid>/
    --sessdata  B 站 SESSDATA Cookie
    --overwrite 已存在覆盖

输出：
    stdout 汇总 JSON: {written:[...], skipped:[...], errors:{...}, meta:{...}}
"""

import argparse
import datetime as dt
import json
import os
import sys
import time

from curl_cffi.requests import Session
from _bilibili_common import (
    REQUEST_INTERVAL,
    assert_kb_layout,
    atomic_write_json,
    create_client,
    dynamic_daily_path,
    ensure_dir,
    get_sessdata,
    init_fingerprint,
    iso_utc_to_cn_date,
    merge_daily_dynamics,
    resolve_kb_root,
    slugify,
)

DYNAMIC_TYPE_MAP = {
    "DYNAMIC_TYPE_DRAW": "draw",
    "DYNAMIC_TYPE_WORD": "word",
    "DYNAMIC_TYPE_FORWARD": "forward",
    "DYNAMIC_TYPE_AV": "video",
    "DYNAMIC_TYPE_ARTICLE": "article",
    "DYNAMIC_TYPE_PGC": "pgc",
    "DYNAMIC_TYPE_MUSIC": "music",
    "DYNAMIC_TYPE_COMMON_SQUARE": "common",
    "DYNAMIC_TYPE_LIVE": "live",
    "DYNAMIC_TYPE_LIVE_RCMD": "live_rcmd",
    "DYNAMIC_TYPE_UGC_SEASON": "ugc_season",
    "DYNAMIC_TYPE_NONE": "none",
}
CONTENT_TYPES = {"draw", "word", "forward", "video", "article"}

AD_KEYWORDS = [
    "直播预告", "直播间", "开播", "来直播间",
    "课程", "训练营", "报名", "私信咨询",
    "加群", "加微信", "微信号", "VX",
    "二维码", "扫码", "领取福利",
    "优惠", "折扣", "限时", "包邮",
    "带货", "好物推荐", "种草",
    "星球", "知识星球", "付费专栏",
]
CHART_HINT_KEYWORDS = ["K线", "走势", "技术面", "MACD", "均线", "支撑", "压力",
                       "布林", "RSI", "KDJ", "量能", "缩量", "放量", "趋势线"]
RESEARCH_HINT_KEYWORDS = ["研报", "机构", "评级", "目标价", "盈利预测", "财报",
                          "年报", "季报", "业绩", "营收", "净利", "毛利率"]
DATA_HINT_KEYWORDS = ["数据", "统计", "排名", "涨幅榜", "资金流", "北向",
                      "融资融券", "龙虎榜", "成交额", "换手率"]


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_to_iso(epoch: int | float) -> str:
    if not epoch:
        return ""
    return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_text(desc):
    return desc.get("text", "") if desc else ""


def _extract_opus_text(major):
    if not major or major.get("type") != "MAJOR_TYPE_OPUS":
        return ""
    return major.get("opus", {}).get("summary", {}).get("text", "")


def _extract_images(major):
    if not major:
        return []
    t = major.get("type", "")
    if t == "MAJOR_TYPE_DRAW":
        return [
            {"url": i["src"], "width": i.get("width", 0),
             "height": i.get("height", 0), "size_kb": i.get("size", 0)}
            for i in major.get("draw", {}).get("items", []) if i.get("src")
        ]
    if t == "MAJOR_TYPE_OPUS":
        return [
            {"url": p.get("url") or p.get("src", ""),
             "width": p.get("width", 0), "height": p.get("height", 0),
             "size_kb": p.get("size", 0)}
            for p in major.get("opus", {}).get("pics", [])
            if p.get("url") or p.get("src")
        ]
    return []


def _extract_video_ref(major):
    if not major or major.get("type") != "MAJOR_TYPE_ARCHIVE":
        return None
    a = major.get("archive", {})
    return {
        "bvid": a.get("bvid", ""), "title": a.get("title", ""),
        "cover": a.get("cover", ""), "duration": a.get("duration_text", ""),
        "desc": a.get("desc", ""),
    }


def _extract_article_ref(major):
    if not major or major.get("type") != "MAJOR_TYPE_ARTICLE":
        return None
    a = major.get("article", {})
    return {
        "id": a.get("id", 0), "title": a.get("title", ""),
        "desc": a.get("desc", ""), "covers": a.get("covers", []),
        "url": a.get("jump_url", ""),
    }


def _is_paid_dynamic(item: dict) -> bool:
    raw_type = item.get("type", "")
    if raw_type not in ("DYNAMIC_TYPE_DRAW", "DYNAMIC_TYPE_WORD"):
        return False
    return item.get("modules", {}).get("module_dynamic", {}).get("desc") is None


def fetch_dynamic_detail(client: Session, dyn_id: str):
    time.sleep(REQUEST_INTERVAL)
    try:
        r = client.get(
            "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail",
            params={"id": dyn_id, "features": "itemOpusStyle,onlyfansVote"},
        )
        if r.status_code == 412:
            return None
        j = r.json()
        if j.get("code") != 0:
            return None
        return j.get("data", {}).get("item")
    except Exception:
        return None


def parse_dynamic(item: dict):
    raw_type = item.get("type", "")
    dtype = DYNAMIC_TYPE_MAP.get(raw_type)
    if not dtype or dtype not in CONTENT_TYPES:
        return None

    dyn_id = item.get("id_str", "")
    mods = item.get("modules", {})
    pub_ts = mods.get("module_author", {}).get("pub_ts", 0)
    md = mods.get("module_dynamic", {})
    text = _extract_text(md.get("desc")) or _extract_opus_text(md.get("major"))
    images = _extract_images(md.get("major"))
    video_ref = _extract_video_ref(md.get("major"))
    article_ref = _extract_article_ref(md.get("major"))

    ms = mods.get("module_stat") or {}
    stats = {
        "like": (ms.get("like") or {}).get("count", 0),
        "comment": (ms.get("comment") or {}).get("count", 0),
        "forward": (ms.get("forward") or {}).get("count", 0),
    }

    is_ad = bool(text and any(kw in text for kw in AD_KEYWORDS))

    content_hints = []
    if text:
        if any(kw in text for kw in CHART_HINT_KEYWORDS):
            content_hints.append("chart_likely")
        if any(kw in text for kw in RESEARCH_HINT_KEYWORDS):
            content_hints.append("research_likely")
        if any(kw in text for kw in DATA_HINT_KEYWORDS):
            content_hints.append("data_likely")

    image_hints = []
    for img in images:
        w, h = img.get("width", 0), img.get("height", 0)
        if w and h:
            r = w / h
            if r > 1.5:
                image_hints.append("wide")
            elif r < 0.5:
                image_hints.append("tall")
            elif w < 400 and h < 400:
                image_hints.append("small")
            else:
                image_hints.append("normal")
        else:
            image_hints.append("unknown")

    result = {
        "dynamic_id": dyn_id,
        "type": dtype,
        "published_at": _epoch_to_iso(pub_ts),
        "text": text,
        "images": [
            {"original_url": i["url"], "width": i["width"],
             "height": i["height"], "local_path": None}
            for i in images
        ],
        "video_ref": video_ref,
        "article_ref": article_ref,
        "stats": stats,
        "is_ad": is_ad,
        "content_hints": content_hints,
        "image_hints": image_hints,
        "link": f"https://t.bilibili.com/{dyn_id}",
    }
    if dtype == "forward":
        orig = item.get("orig")
        result["forward_original"] = parse_dynamic(orig) if orig else None
    return result


def get_dynamics(client, uid, count, types_filter, sessdata):
    if types_filter is None:
        types_filter = CONTENT_TYPES
    results, errors, uploader = [], {}, ""
    offset = ""
    for _page in range(10):
        if len(results) >= count:
            break
        time.sleep(REQUEST_INTERVAL)
        params = {"host_mid": uid}
        if offset:
            params["offset"] = offset
        try:
            resp = client.get(
                "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
                params=params,
            )
        except Exception as e:
            sys.stderr.write(f"[fetch_bilibili_dynamic] 请求异常 (视为412): {e}\n")
            resp = None

        j = None
        if resp is not None and resp.status_code != 412:
            try:
                j = resp.json()
            except Exception:
                pass
        blocked = resp is None or resp.status_code == 412 or (j and j.get("code") == -412)

        if blocked:
            retried = False
            for wait in (30, 60):
                sys.stderr.write(f"[fetch_bilibili_dynamic] 412 风控，等 {wait}s 重试...\n")
                sys.stderr.flush()
                time.sleep(wait)
                try:
                    init_fingerprint(client, sessdata)
                except Exception:
                    continue
                time.sleep(REQUEST_INTERVAL)
                try:
                    resp = client.get(
                        "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space",
                        params=params,
                    )
                except Exception:
                    continue
                if resp.status_code == 412:
                    continue
                try:
                    j = resp.json()
                except Exception:
                    continue
                if j.get("code") != -412:
                    retried = True
                    break
            if not retried:
                errors["api"] = "412 风控两次重试仍失败"
                break

        if j is None:
            errors["api"] = "无法解析响应"
            break
        if j.get("code") != 0:
            errors["api"] = f"code={j.get('code')} msg={j.get('message')}"
            break

        data = j.get("data", {})
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if len(results) >= count:
                break
            if not uploader:
                uploader = item.get("modules", {}).get("module_author", {}).get("name", "")
            try:
                if _is_paid_dynamic(item):
                    detail = fetch_dynamic_detail(client, item.get("id_str", ""))
                    if detail:
                        item = detail
                parsed = parse_dynamic(item)
                if parsed and parsed["type"] in types_filter:
                    results.append(parsed)
            except Exception as e:
                errors[item.get("id_str", "unknown")] = str(e)

        if not data.get("has_more"):
            break
        offset = data.get("offset", "")
        if not offset:
            break
    return results, errors, uploader


def download_one(client, url, dst_path):
    if url.startswith("//"):
        url = "https:" + url
    time.sleep(0.3)
    r = client.get(url)
    r.raise_for_status()
    with open(dst_path, "wb") as f:
        f.write(r.content)


def download_images(client, dynamics, image_dir, kb_root):
    """下载图片，回填每张 image 的 local_path（相对 kb_root 的 POSIX 路径）"""
    ensure_dir(image_dir)
    errors = {}

    def _process(items_list, dyn_id):
        for idx, img in enumerate(items_list):
            url = img["original_url"]
            ext = "jpg"
            tail = url.rsplit("/", 1)[-1]
            if "." in tail:
                e = tail.rsplit(".", 1)[-1].split("?")[0].lower()
                if e in ("jpg", "jpeg", "png", "gif", "webp"):
                    ext = e
            fname = f"{dyn_id}_{idx}.{ext}"
            fpath = os.path.join(image_dir, fname)
            try:
                download_one(client, url, fpath)
                img["local_path"] = os.path.relpath(fpath, kb_root)
            except Exception as e:
                errors[f"{dyn_id}_img{idx}"] = str(e)

    for dyn in dynamics:
        if dyn.get("images"):
            _process(dyn["images"], dyn["dynamic_id"])
        orig = dyn.get("forward_original")
        if orig and orig.get("images"):
            _process(orig["images"], orig["dynamic_id"])
    return errors


def bucket_by_cn_date(dynamics: list[dict]) -> dict[str, list[dict]]:
    """把动态按 published_at(UTC+8) 日期分桶。无 published_at 的归入 'unknown' 桶。"""
    buckets: dict[str, list[dict]] = {}
    for dyn in dynamics:
        date = iso_utc_to_cn_date(dyn.get("published_at", "")) or "unknown"
        buckets.setdefault(date, []).append(dyn)
    return buckets


def write_daily_dynamics(
    kb_root: str,
    date: str,
    bucket: list[dict],
    uid: str,
    uploader: str,
    rebuild: bool,
) -> tuple[str, dict]:
    """把一天的动态桶写入日聚合文件（C2b 合并或重建）。

    返回 (相对路径, info{action, total})
    """
    uploader_slug = slugify(uploader or f"uid-{uid}")
    out_path = dynamic_daily_path(kb_root, uploader_slug, date)

    existing = None
    action = "created"
    if os.path.exists(out_path) and not rebuild:
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            action = "merged"
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(f"读取老文件失败 {out_path}: {e}")
    elif os.path.exists(out_path) and rebuild:
        action = "rebuilt"

    payload = merge_daily_dynamics(
        existing=existing,
        new_entries=bucket,
        uid=uid,
        uploader=uploader,
        date=date,
        fetched_at=_iso_now(),
    )
    atomic_write_json(out_path, payload)
    return (
        os.path.relpath(out_path, kb_root),
        {"action": action, "total": payload["stats"]["total"]},
    )


def main():
    ap = argparse.ArgumentParser(description="B 站动态 → raw/transcripts/bilibili/")
    ap.add_argument("--kb-root", default=None)
    ap.add_argument("--uid", required=True)
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--types", help="draw,word,forward,video,article")
    ap.add_argument("--download-images", action="store_true")
    ap.add_argument("--sessdata")
    ap.add_argument(
        "--rebuild", action="store_true",
        help="忽略老日聚合文件、按本次抓取重建（默认是 C2b 合并）",
    )
    args = ap.parse_args()

    kb_root = resolve_kb_root(args.kb_root)
    assert_kb_layout(kb_root)

    sessdata = get_sessdata(args.sessdata)
    types_filter = set(args.types.split(",")) if args.types else None

    client = create_client(sessdata)
    written, skipped = [], []
    errors: dict[str, str] = {}
    meta = {"uid": args.uid, "uploader": "", "kb_root": kb_root}

    try:
        for wait in (0, 30, 60):
            if wait:
                sys.stderr.write(f"[fetch_bilibili_dynamic] init buvid 等 {wait}s 重试...\n")
                sys.stderr.flush()
                time.sleep(wait)
            try:
                init_fingerprint(client, sessdata)
                break
            except Exception as e:
                sys.stderr.write(f"init_fingerprint 异常: {e}\n")
        else:
            print(json.dumps(
                {"written": [], "skipped": [], "errors": {"init": "buvid 指纹获取失败"}, "meta": meta},
                ensure_ascii=False,
            ))
            sys.exit(1)

        results, fetch_errors, uploader = get_dynamics(
            client, args.uid, args.count, types_filter, sessdata
        )
        meta["uploader"] = uploader
        errors.update(fetch_errors)

        if args.download_images and results:
            image_dir = os.path.join(kb_root, "raw", "assets", "bilibili", str(args.uid))
            img_errors = download_images(client, results, image_dir, kb_root)
            errors.update(img_errors)

        buckets = bucket_by_cn_date(results)
        for date, bucket in sorted(buckets.items()):
            if date == "unknown":
                for dyn in bucket:
                    errors[dyn.get("dynamic_id", "unknown")] = "missing published_at"
                continue
            try:
                path, info = write_daily_dynamics(
                    kb_root, date, bucket, args.uid, uploader, args.rebuild,
                )
                written.append({"path": path, **info})
            except Exception as e:
                errors[f"daily-{date}"] = str(e)
    finally:
        client.close()

    print(json.dumps(
        {"written": written, "skipped": skipped, "errors": errors, "meta": meta},
        ensure_ascii=False, default=str,
    ))


if __name__ == "__main__":
    main()
