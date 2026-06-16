#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0"]
# ///
"""
download_bili_audio.py — 用已验证的 curl_cffi + SESSDATA + buvid 通路下载 B 站视频的
DASH 音频流，避开 yt-dlp 的 412 风控。

为什么不用 yt-dlp：transcribe_bilibili.py 的 yt-dlp 下载器没接入 SESSDATA/buvid，
裸请求 webpage 直接 412。而 fetch_bilibili.py 这套 curl_cffi(impersonate) + buvid 指纹
+ SESSDATA 已被验证能稳定取数（本轮视频/动态全部抓成功）。本脚本复用同一套 client。

流程：
  1. init_fingerprint 设 buvid3/4 + SESSDATA
  2. view API 取 cid
  3. playurl API (fnval=16 DASH) 取音频流 baseUrl，挑最高码率
  4. 带 Referer 下载到 --out

用法：
  uv run --with 'curl_cffi==0.9.0' download_bili_audio.py --bvid BV1xxx --out /tmp/x.m4a
"""
from __future__ import annotations

import argparse
import sys
import time

from _bilibili_common import (
    api_sleep,
    create_client,
    get_sessdata,
    init_fingerprint,
)


def get_cid(client, bvid: str) -> tuple[int, str]:
    resp = client.get("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid})
    j = resp.json()
    if j.get("code") != 0:
        raise RuntimeError(f"view 失败 ({bvid}): code={j.get('code')} {j.get('message')}")
    data = j["data"]
    return data["cid"], data.get("title", "")


def get_audio_url(client, bvid: str, cid: int) -> tuple[str, int]:
    """取 DASH 音频流里码率最高的 baseUrl。返回 (url, bandwidth)。"""
    params = {"bvid": bvid, "cid": cid, "fnval": 16, "fnver": 0, "fourk": 1}
    resp = client.get("https://api.bilibili.com/x/player/playurl", params=params)
    j = resp.json()
    if j.get("code") != 0:
        raise RuntimeError(f"playurl 失败 ({bvid}): code={j.get('code')} {j.get('message')}")
    dash = j.get("data", {}).get("dash")
    if not dash or not dash.get("audio"):
        raise RuntimeError(f"无 DASH 音频流 ({bvid})；可能是付费/会员视频")
    best = max(dash["audio"], key=lambda a: a.get("bandwidth", 0))
    return best["baseUrl"], best.get("bandwidth", 0)


def download(client, url: str, out_path: str, bvid: str) -> int:
    headers = {
        "Referer": f"https://www.bilibili.com/video/{bvid}",
        "Origin": "https://www.bilibili.com",
    }
    total = 0
    with client.stream("GET", url, headers=headers) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"音频下载 HTTP {resp.status_code}")
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content():
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
    return total


def main():
    ap = argparse.ArgumentParser(description="下载 B 站 DASH 音频流（curl_cffi 通路）")
    ap.add_argument("--bvid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sessdata")
    args = ap.parse_args()

    sessdata = get_sessdata(args.sessdata)
    client = create_client(sessdata)
    try:
        for wait in (0, 30, 60):
            if wait:
                sys.stderr.write(f"[download_bili_audio] init buvid 等 {wait}s 重试...\n")
                time.sleep(wait)
            try:
                init_fingerprint(client, sessdata)
                break
            except Exception as e:
                sys.stderr.write(f"init_fingerprint 异常: {e}\n")

        cid, title = get_cid(client, args.bvid)
        api_sleep()
        url, bw = get_audio_url(client, args.bvid, cid)
        sys.stderr.write(f"[download_bili_audio] {args.bvid} cid={cid} 音频码率={bw} title={title[:30]}\n")
        size = download(client, url, args.out, args.bvid)
        print(f"OK {args.out} {size} bytes")
    finally:
        client.close()


if __name__ == "__main__":
    main()
