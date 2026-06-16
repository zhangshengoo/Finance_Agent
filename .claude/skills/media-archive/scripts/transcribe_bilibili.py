#!/usr/bin/env python3
"""
transcribe_bilibili.py — B站视频 ASR 转写，结果写回 raw/ JSON

调用方式：
  # 从 BV 号下载并转写（需要 yt-dlp 能访问 B站，可能遇 412 风控）
  python3 transcribe_bilibili.py --bvid BV1xxxxxx --kb-root /path/to/Knowledge_Wiki

  # 从已下载的音频文件转写
  python3 transcribe_bilibili.py --audio-file /path/to/audio.m4a --kb-root /path/to/Knowledge_Wiki

  # 指定已有 raw JSON 进行更新（否则自动在 KB 中查找）
  python3 transcribe_bilibili.py --bvid BV1xxxxxx --raw-json raw/transcripts/bilibili/xxx.json

依赖:
  - Third_Party/bili2text  (已内置 DashScopeQwenTranscriber + yt-dlp)
  - Third_Party/Qwen3-ASR-Toolkit (QwenASR class)
  - 环境变量 DASHSCOPE_API_KEY
  - 可选: BILIBILI_SESSDATA (提升下载成功率)

当 yt-dlp 遇到 HTTP 412 时，脚本会打印 BBDown 备用下载命令。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ── 路径注入 ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]          # Finance_Agent/
_BILI2TEXT_DIR = _PROJECT_ROOT / "Third_Party" / "bili2text"
_TOOLKIT_DIR   = _PROJECT_ROOT / "Third_Party" / "Qwen3-ASR-Toolkit"

for _p in [str(_BILI2TEXT_DIR / "src"), str(_TOOLKIT_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 设置 Python 解释器为 bili2text 的 venv（使 soundfile/pydub 等可用）
_VENV_PYTHON = _BILI2TEXT_DIR / ".venv" / "bin" / "python3"


def _ensure_bili2text():
    if not (_BILI2TEXT_DIR / "src" / "b2t").exists():
        print(f"[ERROR] bili2text not found at {_BILI2TEXT_DIR}")
        print("请先: git clone https://github.com/lanbinleo/bili2text Third_Party/bili2text")
        sys.exit(1)


def _ensure_api_key():
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not key:
        print("[ERROR] 未设置 DASHSCOPE_API_KEY 环境变量")
        sys.exit(1)
    return key


# ── KB_ROOT 解析 ──────────────────────────────────────────────────────────────
def _resolve_kb_root(kb_root_arg: str | None) -> Path:
    if kb_root_arg:
        return Path(kb_root_arg).expanduser().resolve()
    env = os.environ.get("KB_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    default = _PROJECT_ROOT / "Knowledge_Wiki"
    return default.resolve()


def _find_raw_json(kb_root: Path, bvid: str) -> Path | None:
    """在 KB 的 raw/transcripts/bilibili/ 下递归查找 bvid 对应的 JSON。"""
    pattern = f"*{bvid}*.json"
    matches = list(kb_root.glob(f"raw/transcripts/bilibili/**/{pattern}"))
    return matches[0] if matches else None


# ── 下载 ──────────────────────────────────────────────────────────────────────
def _download_audio(bvid: str, tmpdir: Path) -> Path:
    """
    用 bili2text 的 yt-dlp 下载器下载音频，返回 .m4a / .mp4 路径。
    遇到 412 时打印 BBDown 备用命令后抛出。
    """
    try:
        from b2t.config import Settings
        from b2t.downloaders import YtDlpDownloader
        from b2t.inputs import parse_source
    except ImportError as e:
        print(f"[ERROR] 无法导入 bili2text: {e}")
        print(f"请检查 {_BILI2TEXT_DIR} 是否正确安装")
        sys.exit(1)

    settings = Settings.from_workspace(tmpdir)
    downloader = YtDlpDownloader()
    source = parse_source(f"https://www.bilibili.com/video/{bvid}")

    # 注入 SESSDATA cookie（如有）
    sessdata = os.environ.get("BILIBILI_SESSDATA", "").strip()
    if sessdata:
        _inject_sessdata_cookie(sessdata, tmpdir)

    try:
        result = downloader.download(source, settings)
        return result.video_path
    except Exception as e:
        err = str(e)
        if "412" in err or "Precondition" in err.lower():
            print(f"\n[WARN] yt-dlp 遇到 B站 HTTP 412 风控，无法下载 {bvid}")
            print("备用方案 — 使用 BBDown 手动下载音频：")
            print(f"  BBDown -ia -c ~/.bilibili_sessdata.json {bvid}")
            print("下载完成后使用 --audio-file 参数传入文件路径")
        raise


def _inject_sessdata_cookie(sessdata: str, tmpdir: Path) -> None:
    """把 SESSDATA 写成 Netscape cookie 文件供 yt-dlp 使用（暂未接入 downloader）。"""
    cookie_file = tmpdir / "bili_cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        f".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\t{sessdata}\n",
        encoding="utf-8",
    )


# ── 转写 ──────────────────────────────────────────────────────────────────────
def _transcribe(audio_path: Path, api_key: str, model: str, prompt: str | None) -> dict:
    """调用 DashScopeQwenTranscriber 转写，返回 {text, language, duration_s}。"""
    try:
        from b2t.transcribers.dashscope_qwen import DashScopeQwenTranscriber
    except ImportError as e:
        print(f"[ERROR] 无法导入 DashScopeQwenTranscriber: {e}")
        sys.exit(1)

    t = DashScopeQwenTranscriber(api_key=api_key, model=model)
    print(f"[INFO] 开始转写: {audio_path.name}  model={model}")
    result = t.transcribe(audio_path, prompt=prompt)
    duration = result.get("raw_response", {}).get("duration_s", 0)
    print(f"[INFO] 转写完成: {len(result['text'])} 字  语言={result['language']}  时长={duration}s")
    return result


# ── raw JSON 更新 ────────────────────────────────────────────────────────────
def _make_asr_subtitle_data(transcript: dict, audio_path: Path) -> dict:
    """构造 subtitle_data 结构（ASR 来源）。body=null 表示无时间轴。"""
    return {
        "source": f"asr-{transcript['model']}",
        "model": transcript["model"],
        "language": transcript["language"],
        "duration_s": transcript.get("raw_response", {}).get("duration_s", 0),
        "audio_file": str(audio_path),
        "asr_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "body": None,   # ASR 当前无逐句时间轴
    }


def _update_raw_json(raw_json_path: Path, transcript: dict, audio_path: Path) -> None:
    """将 ASR 结果写回 raw/ JSON（不修改其他字段）。"""
    data = json.loads(raw_json_path.read_text(encoding="utf-8"))

    existing = data.get("subtitle_source", "none")
    if existing not in ("none", "asr-qwen3-flash", "asr-qwen3-asr-flash", ""):
        print(f"[INFO] 已有字幕 subtitle_source={existing!r}，将覆盖为 ASR 结果")

    src_tag = f"asr-{transcript['model']}"
    data["subtitle"] = transcript["text"]
    data["subtitle_source"] = src_tag
    data["subtitle_data"] = _make_asr_subtitle_data(transcript, audio_path)

    raw_json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] 已更新 {raw_json_path.relative_to(raw_json_path.parents[5])}")


def _create_raw_json(
    kb_root: Path, bvid: str, transcript: dict, audio_path: Path
) -> Path:
    """
    不存在 raw JSON 时创建最小 skeleton，写入 ASR 结果。
    完整元数据（uploader、title 等）需后续 fetch_bilibili.py 补全。
    """
    out_dir = kb_root / "raw" / "transcripts" / "bilibili" / "_asr_only"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{bvid}.json"

    src_tag = f"asr-{transcript['model']}"
    data = {
        "source": "bilibili",
        "kind": "video",
        "bvid": bvid,
        "uid": "",
        "uploader": "",
        "title": "",
        "published_at": "",
        "duration_seconds": transcript.get("raw_response", {}).get("duration_s", 0),
        "description": "",
        "subtitle": transcript["text"],
        "subtitle_source": src_tag,
        "subtitle_data": _make_asr_subtitle_data(transcript, audio_path),
        "fetched_at": "",
        "link": f"https://www.bilibili.com/video/{bvid}",
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 已创建 {out_path}")
    print("[WARN] skeleton JSON（metadata 缺失），建议运行 fetch_bilibili.py --bvid 补全")
    return out_path


# ── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="B站视频 ASR 转写，结果落 raw/ JSON"
    )
    parser.add_argument("--bvid", help="B站 BV 号（下载音频 OR 关联现有 raw JSON）")
    parser.add_argument("--audio-file", type=Path, help="已下载的音频文件路径（同时给 --bvid 则用于 raw JSON 关联）")

    parser.add_argument("--kb-root", help="Knowledge_Wiki 根目录（默认读 KB_ROOT 环境变量）")
    parser.add_argument("--raw-json", type=Path, help="要更新的 raw JSON 路径（省略时自动查找）")
    parser.add_argument(
        "--model", default="qwen3-asr-flash",
        help="DashScope ASR 模型（默认 qwen3-asr-flash）"
    )
    parser.add_argument("--prompt", help="提示词（金融术语等），提升识别准确率")
    args = parser.parse_args()

    if not args.bvid and not args.audio_file:
        parser.error("至少提供 --bvid 或 --audio-file 其中之一")

    _ensure_bili2text()
    api_key = _ensure_api_key()
    kb_root = _resolve_kb_root(args.kb_root)

    if not kb_root.exists():
        print(f"[ERROR] KB_ROOT 不存在: {kb_root}")
        sys.exit(1)

    tmpdir = Path(tempfile.mkdtemp(prefix="b2t_skill_"))
    try:
        # 1. 获取音频
        if args.audio_file:
            audio_path = args.audio_file.resolve()
            bvid = args.bvid or ""
        else:
            bvid = args.bvid
            print(f"[INFO] 下载 {bvid} ...")
            audio_path = _download_audio(bvid, tmpdir)

        if not audio_path.exists():
            print(f"[ERROR] 音频文件不存在: {audio_path}")
            sys.exit(1)

        # 2. 转写
        transcript = _transcribe(audio_path, api_key, args.model, args.prompt)

        # 3. 写回 raw/
        if args.raw_json:
            raw_json_path = args.raw_json
        elif bvid:
            raw_json_path = _find_raw_json(kb_root, bvid)
        else:
            raw_json_path = None

        if raw_json_path and raw_json_path.exists():
            _update_raw_json(raw_json_path, transcript, audio_path)
        else:
            if not bvid:
                bvid = audio_path.stem
            raw_json_path = _create_raw_json(kb_root, bvid, transcript, audio_path)

        print("\n下一步建议：")
        print(f"  raw-preview: render_preview.py --source {raw_json_path.relative_to(kb_root)}")
        print(f"  或摄入 wiki: finance-ingest")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
