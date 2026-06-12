#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["curl_cffi==0.9.0"]
# ///
"""
B 站 API 公共模块（WBI 签名 / curl_cffi TLS 指纹 / buvid 指纹）

由 fetch_bilibili.py 与 fetch_bilibili_dynamic.py 共用。
原始版本来源：OpenClaw_FinRobot bilibili_common.py（同算法，仅文件名加 _ 前缀表示内部模块）。
"""

import datetime as dt
import hashlib
import json
import os
import random
import tempfile
import time
import urllib.parse
from functools import lru_cache

from curl_cffi.requests import Session

# 中国 UP 主主要时区，文件名/目录名按这个时区切日
CN_TZ = dt.timezone(dt.timedelta(hours=8))

# WBI 混淆密钥置换表（B 站公开算法，固定值）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

IMPERSONATE = "chrome120"
REQUEST_INTERVAL = 1.0   # API 调用基础间隔（秒），实际使用 api_sleep() 加 jitter
HTTP_TIMEOUT = 15.0

# buvid 指纹本地缓存（跨调用复用，避免频繁向 /finger/spi 取新指纹）
_BUVID_CACHE_PATH = os.path.join(os.path.expanduser("~"), ".bilibili_buvid_cache.json")
_BUVID_TTL_DAYS = 7


def api_sleep(base: float = REQUEST_INTERVAL) -> None:
    """带 ±40% jitter 的 sleep，避免固定间隔特征。"""
    time.sleep(base * (0.6 + random.random() * 0.8))


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw))[:32]


def sign_wbi_params(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = get_mixin_key(img_key, sub_key)
    params = dict(sorted(params.items()))
    params["wts"] = int(time.time())
    query = urllib.parse.urlencode(params)
    wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = wbi_sign
    return params


@lru_cache(maxsize=1)
def get_wbi_keys(client: Session) -> tuple[str, str]:
    resp = client.get("https://api.bilibili.com/x/web-interface/nav")
    data = resp.json()["data"]
    img_url = data["wbi_img"]["img_url"]
    sub_url = data["wbi_img"]["sub_url"]
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
    return img_key, sub_key


def make_headers(sessdata: str | None = None) -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
    }
    if sessdata:
        headers["Cookie"] = f"SESSDATA={sessdata}"
    return headers


def get_sessdata(args_sessdata: str | None = None) -> str | None:
    raw = args_sessdata or os.environ.get("BILIBILI_SESSDATA")
    if not raw:
        return None
    candidates = [s.strip() for s in raw.split(",") if s.strip()]
    return random.choice(candidates) if candidates else None


def get_proxy() -> str | None:
    return os.environ.get("BILIBILI_PROXY")


def create_client(sessdata: str | None = None, proxy: str | None = None) -> Session:
    headers = make_headers(sessdata)
    proxy = proxy or get_proxy()
    kwargs: dict = {
        "impersonate": IMPERSONATE,
        "timeout": HTTP_TIMEOUT,
        "headers": headers,
    }
    if proxy:
        kwargs["proxy"] = proxy
    return Session(**kwargs)


def _load_buvid_cache() -> tuple[str, str] | None:
    """从本地缓存读取 buvid3/buvid4，TTL 内有效则返回 (b3, b4)，否则 None。"""
    try:
        with open(_BUVID_CACHE_PATH, "r") as f:
            cache = json.load(f)
        saved = dt.datetime.fromisoformat(cache["saved_at"])
        age_days = (dt.datetime.now(dt.timezone.utc) - saved).days
        if age_days < _BUVID_TTL_DAYS and cache.get("b3") and cache.get("b4"):
            return cache["b3"], cache["b4"]
    except (OSError, KeyError, ValueError):
        pass
    return None


def _save_buvid_cache(b3: str, b4: str) -> None:
    try:
        with open(_BUVID_CACHE_PATH, "w") as f:
            json.dump({"b3": b3, "b4": b4, "saved_at": dt.datetime.now(dt.timezone.utc).isoformat()}, f)
    except OSError:
        pass


def init_fingerprint(client: Session, sessdata: str | None = None) -> None:
    """设置 buvid3/buvid4 cookie。优先复用本地缓存（TTL 7天），过期才请求 /finger/spi。"""
    cached = _load_buvid_cache()
    if cached:
        b3, b4 = cached
    else:
        resp = client.get("https://api.bilibili.com/x/frontend/finger/spi")
        data = resp.json().get("data", {})
        b3 = data.get("b_3", "")
        b4 = data.get("b_4", "")
        if b3 and b4:
            _save_buvid_cache(b3, b4)
    cookie_parts = []
    if b3:
        cookie_parts.append(f"buvid3={b3}")
    if b4:
        cookie_parts.append(f"buvid4={b4}")
    if sessdata:
        cookie_parts.append(f"SESSDATA={sessdata}")
    if cookie_parts:
        client.headers["Cookie"] = "; ".join(cookie_parts)


# --- KB_ROOT 解析 + slug 工具 ---

INVALID_FS_CHARS = '<>:"/\\|?*\x00'


def resolve_kb_root(cli_arg: str | None = None) -> str:
    """KB_ROOT 解析顺序：CLI > env > 默认（脚本路径反推 Finance_Agent/Knowledge_Wiki）"""
    if cli_arg:
        return os.path.abspath(cli_arg)
    env = os.environ.get("KB_ROOT")
    if env:
        return os.path.abspath(env)
    # 默认：从本脚本路径反推 .../Finance_Agent/.claude/skills/media-archive/scripts/_bilibili_common.py
    here = os.path.abspath(__file__)
    # ../.../Finance_Agent/Knowledge_Wiki
    project_root = os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))
    return os.path.join(project_root, "Knowledge_Wiki")


def slugify(name: str, max_len: int = 60) -> str:
    """文件系统安全 slug：保留中文，剔除非法字符，空白转 -，截断长度"""
    s = name.strip()
    for ch in INVALID_FS_CHARS:
        s = s.replace(ch, "")
    s = s.replace(" ", "-").replace("\t", "-")
    while "--" in s:
        s = s.replace("--", "-")
    s = s.strip("-._")
    return s[:max_len] or "unknown"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def assert_kb_layout(kb_root: str) -> None:
    """预检 KB_ROOT 是否有 raw/ 三大子目录"""
    raw = os.path.join(kb_root, "raw")
    missing = [
        sub for sub in ("transcripts", "news", "assets")
        if not os.path.isdir(os.path.join(raw, sub))
    ]
    if not os.path.isdir(raw) or missing:
        missing_str = ",".join(missing) if missing else "directory"
        raise SystemExit(
            f"KB_ROOT={kb_root} 不像有效 Knowledge_Wiki "
            f"（缺少 raw/{missing_str}）。"
            "请检查 --kb-root 或 KB_ROOT 环境变量。"
        )


# --- 时间/路径/原子写工具（新布局共用） ---


def epoch_to_cn_date(epoch: int | float) -> str:
    """UTC epoch → UTC+8 日期字符串 YYYY-MM-DD。0/空返回空串。"""
    if not epoch:
        return ""
    return dt.datetime.fromtimestamp(int(epoch), CN_TZ).strftime("%Y-%m-%d")


def iso_utc_to_cn_date(iso_str: str) -> str:
    """UTC ISO 字符串（如 2026-03-15T02:23:00Z） → UTC+8 日期 YYYY-MM-DD。"""
    if not iso_str:
        return ""
    s = iso_str.rstrip("Z")
    try:
        d = dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
        return d.astimezone(CN_TZ).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def video_path(kb_root: str, uploader_slug: str, date: str, bvid: str) -> str:
    """<kb>/raw/transcripts/bilibili/<up>/videos/<YYYY>/<YYYY-MM>/<date>_<bvid>.json"""
    year = date[:4]
    year_month = date[:7]
    return os.path.join(
        kb_root, "raw", "transcripts", "bilibili",
        uploader_slug, "videos", year, year_month,
        f"{date}_{bvid}.json",
    )


def dynamic_daily_path(kb_root: str, uploader_slug: str, date: str) -> str:
    """<kb>/raw/transcripts/bilibili/<up>/dynamics/<YYYY>/<YYYY-MM>/<date>.json"""
    year = date[:4]
    year_month = date[:7]
    return os.path.join(
        kb_root, "raw", "transcripts", "bilibili",
        uploader_slug, "dynamics", year, year_month,
        f"{date}.json",
    )


def atomic_write_json(path: str, payload: dict) -> None:
    """临时文件 + os.replace，保证写入不留半文件。"""
    ensure_dir(os.path.dirname(path))
    fd, tmp = tempfile.mkstemp(
        prefix=".tmp.", suffix=".json",
        dir=os.path.dirname(path),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def merge_daily_dynamics(
    existing: dict | None,
    new_entries: list[dict],
    uid: str,
    uploader: str,
    date: str,
    fetched_at: str,
) -> dict:
    """C2b: 新值覆盖。返回合并后的完整日聚合 payload。

    - existing=None 表示首次创建
    - new_entries 是单条动态对象列表（已 parse_dynamic 过）
    - 同 dynamic_id 的条目用 new_entries 中的整体替换老值（last-write-wins）
    """
    by_id: dict[str, dict] = {}
    if existing:
        for type_list in existing.get("by_type", {}).values():
            for dyn in type_list:
                dyn_id = dyn.get("dynamic_id")
                if dyn_id:
                    by_id[dyn_id] = dyn

    for dyn in new_entries:
        dyn_id = dyn.get("dynamic_id")
        if dyn_id:
            by_id[dyn_id] = dyn

    new_by_type: dict[str, list] = {}
    for dyn in by_id.values():
        t = dyn.get("type", "unknown")
        new_by_type.setdefault(t, []).append(dyn)

    by_type_counts = {t: len(v) for t, v in new_by_type.items()}

    return {
        "source": "bilibili",
        "kind": "dynamic-daily",
        "uid": str(uid),
        "uploader": uploader,
        "date": date,
        "fetched_at": fetched_at,
        "stats": {
            "total": sum(by_type_counts.values()),
            "by_type": by_type_counts,
        },
        "by_type": new_by_type,
    }
