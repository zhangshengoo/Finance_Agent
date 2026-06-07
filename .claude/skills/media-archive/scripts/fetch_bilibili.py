#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0"]
# ///
"""
B 站视频抓取 → 落 raw/transcripts/bilibili/<uploader-slug>_<bvid>.json

用法：
    # 抓单个视频（含字幕）
    uv run --with 'curl_cffi==0.9.0' fetch_bilibili.py \
        --kb-root /path/to/Knowledge_Wiki \
        --bvid BV1xxxxxx --with-subtitle

    # 抓 UP 主最近 N 个视频（含字幕）
    uv run --with 'curl_cffi==0.9.0' fetch_bilibili.py \
        --kb-root /path/to/Knowledge_Wiki \
        --uid 1039025435 --count 3 --with-subtitle

参数：
    --kb-root   Knowledge_Wiki 根（默认读 KB_ROOT，再默认推 Finance_Agent/Knowledge_Wiki）
    --uid       UP 主 UID
    --bvid      单视频 BV 号
    --count     UP 主模式下抓取数量（含字幕时建议 ≤ 5）
    --with-subtitle  同时抓字幕
    --sessdata  B 站 SESSDATA Cookie（默认读 BILIBILI_SESSDATA）
    --overwrite 已存在的 raw 文件是否覆盖（默认 False，存在即报错跳过）

输出：
    stdout 打印汇总 JSON：{written:[...], skipped:[...], errors:{...}, meta:{...}}
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
    epoch_to_cn_date,
    get_sessdata,
    get_wbi_keys,
    init_fingerprint,
    resolve_kb_root,
    sign_wbi_params,
    slugify,
    video_path,
)


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _epoch_to_iso(epoch: int | float) -> str:
    if not epoch:
        return ""
    return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_videos(client: Session, uid: str, count: int) -> tuple[list[dict], str]:
    """获取 UP 主最近视频列表（WBI 签名，含 412 重试）"""
    img_key, sub_key = get_wbi_keys(client)
    params = {"mid": uid, "ps": min(count, 50), "pn": 1, "order": "pubdate"}
    signed = sign_wbi_params(params, img_key, sub_key)

    resp = client.get("https://api.bilibili.com/x/space/wbi/arc/search", params=signed)
    j = resp.json() if resp.status_code != 412 else None
    blocked = resp.status_code == 412 or (j and j.get("code") == -412)

    if blocked:
        for wait in (30, 60):
            sys.stderr.write(f"[fetch_bilibili] 412 风控，等 {wait}s 重试...\n")
            sys.stderr.flush()
            time.sleep(wait)
            get_wbi_keys.cache_clear()
            img_key, sub_key = get_wbi_keys(client)
            signed = sign_wbi_params(params, img_key, sub_key)
            resp = client.get("https://api.bilibili.com/x/space/wbi/arc/search", params=signed)
            if resp.status_code == 412:
                continue
            j = resp.json()
            if j.get("code") != -412:
                break
        else:
            raise RuntimeError("412 风控两次重试仍失败")

    if j is None:
        j = resp.json()
    if j.get("code") != 0:
        raise RuntimeError(f"列表失败 code={j.get('code')} msg={j.get('message')}")

    vlist = j["data"]["list"]["vlist"]
    uploader = vlist[0].get("author", "") if vlist else ""
    videos = [
        {
            "bvid": v["bvid"],
            "title": v["title"],
            "pubdate": v["created"],
            "duration_seconds": v["length"],
            "description": v.get("description", ""),
        }
        for v in vlist[:count]
    ]
    return videos, uploader


def _select_best_subtitle(subs: list[dict]) -> dict | None:
    valid = [s for s in subs if s.get("subtitle_url")]
    if not valid:
        return None
    cc = [s for s in valid if s.get("type") == 0]
    ai = [s for s in valid if s.get("type") == 1]
    for group in (cc, ai):
        for s in group:
            if "zh" in s.get("lan", ""):
                return s
        if group:
            return group[0]
    return valid[0]


def get_video_info(client: Session, bvid: str) -> dict:
    resp = client.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid})
    j = resp.json()
    if j.get("code") != 0:
        raise RuntimeError(f"view 失败 ({bvid}): {j.get('message')}")
    return j["data"]


def get_subtitle(client: Session, bvid: str, cid: int) -> tuple[str | None, str]:
    """返回 (字幕全文, 字幕来源 cc-zh/ai-zh/...)；无字幕返回 (None, 'none')"""
    resp = client.get("https://api.bilibili.com/x/player/wbi/v2", params={"bvid": bvid, "cid": cid})
    j = resp.json()
    if j.get("code") != 0:
        return None, "none"
    subs = j.get("data", {}).get("subtitle", {}).get("subtitles", [])
    if not subs:
        return None, "none"
    chosen = _select_best_subtitle(subs)
    if not chosen:
        return None, "none"
    src_tag = ("cc-" if chosen.get("type") == 0 else "ai-") + chosen.get("lan", "unk")

    url = chosen["subtitle_url"]
    if url.startswith("//"):
        url = "https:" + url
    r = client.get(url)
    body = r.json().get("body", [])
    if not body:
        return None, src_tag
    return " ".join(item["content"] for item in body), src_tag


def write_video_json(
    kb_root: str,
    video: dict,
    uid: str,
    uploader: str,
    overwrite: bool,
) -> tuple[str | None, str | None]:
    """写视频到 <up>/videos/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>_<BVID>.json
    返回 (written_path, skipped_reason)
    """
    uploader_slug = slugify(uploader or f"uid-{uid}")
    pubdate_epoch = video.get("pubdate", 0)
    cn_date = epoch_to_cn_date(pubdate_epoch)
    if not cn_date:
        return None, f"missing published_at for {video.get('bvid')}"

    out_path = video_path(kb_root, uploader_slug, cn_date, video["bvid"])
    if os.path.exists(out_path) and not overwrite:
        return None, f"already exists: {os.path.relpath(out_path, kb_root)}"

    payload = {
        "source": "bilibili",
        "kind": "video",
        "bvid": video["bvid"],
        "uid": str(uid),
        "uploader": uploader,
        "title": video.get("title", ""),
        "published_at": _epoch_to_iso(pubdate_epoch),
        "duration_seconds": video.get("duration_seconds", ""),
        "description": video.get("description", ""),
        "subtitle": video.get("subtitle"),
        "subtitle_source": video.get("subtitle_source", "none"),
        "fetched_at": _iso_now(),
        "link": f"https://www.bilibili.com/video/{video['bvid']}",
    }
    atomic_write_json(out_path, payload)
    return os.path.relpath(out_path, kb_root), None


def main():
    ap = argparse.ArgumentParser(description="B 站视频 → raw/transcripts/bilibili/")
    ap.add_argument("--kb-root", default=None)
    ap.add_argument("--uid")
    ap.add_argument("--bvid")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--with-subtitle", action="store_true")
    ap.add_argument("--sessdata")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if not args.uid and not args.bvid:
        ap.error("必须指定 --uid 或 --bvid")

    kb_root = resolve_kb_root(args.kb_root)
    assert_kb_layout(kb_root)

    sessdata = get_sessdata(args.sessdata)
    client = create_client(sessdata)

    written: list[str] = []
    skipped: list[str] = []
    errors: dict[str, str] = {}
    meta = {"uid": args.uid or "", "uploader": "", "kb_root": kb_root}

    try:
        # 先取 buvid 指纹 cookie；空间/WBI 接口在没有 buvid 时会概率触发 412
        for _wait in (0, 30, 60):
            if _wait:
                sys.stderr.write(f"[fetch_bilibili] init buvid 等 {_wait}s 重试...\n")
                sys.stderr.flush()
                time.sleep(_wait)
            try:
                init_fingerprint(client, sessdata)
                break
            except Exception as e:
                sys.stderr.write(f"init_fingerprint 异常: {e}\n")
        if args.bvid:
            try:
                info = get_video_info(client, args.bvid)
                owner = info.get("owner", {})
                uploader = owner.get("name", "")
                uid = str(owner.get("mid", ""))
                meta["uploader"] = uploader
                meta["uid"] = meta["uid"] or uid
                video = {
                    "bvid": args.bvid,
                    "title": info.get("title", ""),
                    "pubdate": info.get("pubdate", 0),
                    "duration_seconds": info.get("duration", 0),
                    "description": info.get("desc", ""),
                }
                if args.with_subtitle:
                    cid = info["cid"]
                    time.sleep(REQUEST_INTERVAL)
                    sub, src = get_subtitle(client, args.bvid, cid)
                    video["subtitle"] = sub
                    video["subtitle_source"] = src
                else:
                    video["subtitle"] = None
                    video["subtitle_source"] = "none"
                path, skip = write_video_json(kb_root, video, uid, uploader, args.overwrite)
                if path:
                    written.append(path)
                elif skip:
                    skipped.append(skip)
            except Exception as e:
                errors[args.bvid] = str(e)

        else:
            try:
                videos, uploader = get_videos(client, args.uid, args.count)
                meta["uploader"] = uploader
            except Exception as e:
                print(json.dumps(
                    {"written": [], "skipped": [], "errors": {"list": str(e)}, "meta": meta},
                    ensure_ascii=False,
                ))
                sys.exit(1)

            for v in videos:
                bvid = v["bvid"]
                try:
                    if args.with_subtitle:
                        time.sleep(REQUEST_INTERVAL)
                        info = get_video_info(client, bvid)
                        cid = info["cid"]
                        time.sleep(REQUEST_INTERVAL)
                        sub, src = get_subtitle(client, bvid, cid)
                        v["subtitle"] = sub
                        v["subtitle_source"] = src
                    else:
                        v["subtitle"] = None
                        v["subtitle_source"] = "none"
                    path, skip = write_video_json(kb_root, v, args.uid, uploader, args.overwrite)
                    if path:
                        written.append(path)
                    elif skip:
                        skipped.append(skip)
                except Exception as e:
                    errors[bvid] = str(e)
    finally:
        client.close()

    print(json.dumps(
        {"written": written, "skipped": skipped, "errors": errors, "meta": meta},
        ensure_ascii=False, default=str,
    ))


if __name__ == "__main__":
    main()
