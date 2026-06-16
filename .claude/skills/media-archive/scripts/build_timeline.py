#!/usr/bin/env python3
"""
build_timeline.py — 把某 UP 主的 raw 媒体源聚合成「创作者时间线清单」

设计定位（见 frontend/media-timeline-architecture.html 的「时间线轨」）：
  - 媒体源流是按创作者的【时序源材料】，不该被逐条强行编译进 wiki/。
  - 本脚本产出 raw 的【派生镜像】 timeline.json：每条一行高度概括，
    与 _previews/ 同等地位 —— 派生、可重建、不写 wiki / ontology / _index.json。
  - 数据全部来自 raw/ 的 JSON（权威字段）+ _previews/ 的 md（TL;DR / mentions / 操作表）。
    没有 _preview 的源也照样进时间线（降级：tldr 为空，仅用 raw 字段）。
  - has_wiki / 深度链接【不在此处算】—— 那是前端构建期（build_frontend_data.py）读 wiki 叠加的事。

输出：raw/transcripts/bilibili/<up>/_previews/timeline.json （每个 UP 主一份）

用法：
  python3 build_timeline.py                      # 全量重建所有 UP 主
  python3 build_timeline.py --up 战国时代_姜汁汽水   # 只重建指定 UP 主
  python3 build_timeline.py --kb-root /path/to/Knowledge_Wiki

仅用 Python 标准库。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


# --------------------------------------------------------------------------
# KB_ROOT 解析（media-archive 约定：--kb-root > $KB_ROOT > 由 __file__ 反推）
# --------------------------------------------------------------------------
def resolve_kb_root(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser().resolve()
    if os.environ.get("KB_ROOT"):
        return Path(os.environ["KB_ROOT"]).expanduser().resolve()
    # .claude/skills/media-archive/scripts/build_timeline.py -> parents[4] = 项目根
    project_root = Path(__file__).resolve().parents[4]
    return project_root / "Knowledge_Wiki"


# --------------------------------------------------------------------------
# 轻量 frontmatter / body 切分（不依赖 PyYAML，也不依赖 KB scripts）
# --------------------------------------------------------------------------
def split_md(text: str):
    """返回 (frontmatter_text, body_text)。无 frontmatter 时 fm 为空串。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end].lstrip("\n")
            body = text[end + 4:]
            return fm, body
    return "", text


_STRIP_HL = lambda s: s.replace("==", "").strip()


def fm_list(fm_text: str, key: str) -> list:
    """从 frontmatter 抓 'key: [a, b, c]'（含缩进，用于嵌套 mentions 的子键）。"""
    m = re.search(rf"^\s*{re.escape(key)}:\s*\[(.*?)\]\s*$", fm_text, re.MULTILINE)
    if not m or not m.group(1).strip():
        return []
    return [_STRIP_HL(x) for x in m.group(1).split(",") if _STRIP_HL(x)]


def fm_scalar(fm_text: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", fm_text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def extract_tldr(body: str) -> list[str]:
    """抓 '> [!abstract] ... TL;DR' callout 内的编号 / 项目要点。"""
    lines = body.splitlines()
    out, capturing = [], False
    for ln in lines:
        s = ln.rstrip()
        if re.match(r"^>\s*\[!abstract\]", s):
            capturing = True
            continue
        if capturing:
            if not s.lstrip().startswith(">"):
                break  # callout 结束（遇到非 > 行）
            inner = s.lstrip()[1:].strip()        # 去掉前导 '>'
            inner = re.sub(r"^\d+\.\s*", "", inner)  # 去编号 '1. '
            inner = re.sub(r"^[-*]\s*", "", inner)   # 去项目符号
            inner = _STRIP_HL(inner)
            if inner:
                out.append(inner)
    return out


def extract_mentions(fm_text: str) -> list[str]:
    """合并 frontmatter mentions 的 macro + sectors + companies（去重保序）。"""
    merged, seen = [], set()
    for key in ("macro", "sectors", "companies"):
        for v in fm_list(fm_text, key):
            if v not in seen:
                seen.add(v)
                merged.append(v)
    return merged


def extract_up_actions(body: str) -> list[dict]:
    """抓 '**UP 主操作' 后的 markdown 表格（仅视频 preview 有）。

    表头固定为：标的 | 当前位置 | 动作 | 目标 / 止损 | 风险 / 失效条件
    """
    idx = body.find("UP 主操作")
    if idx == -1:
        return []
    seg = body[idx:]
    actions = []
    for ln in seg.splitlines():
        ln = ln.strip()
        if not ln.startswith("|"):
            if actions:        # 表格已结束
                break
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if not cells or "标的" in cells[0] or set(cells[0]) <= set("-: "):
            continue           # 表头 / 分隔行
        target = _STRIP_HL(cells[0])
        if not target:
            continue
        actions.append({
            "target": target,
            "position": _STRIP_HL(cells[1]) if len(cells) > 1 else "",
            "action": _STRIP_HL(cells[2]) if len(cells) > 2 else "",
            "plan": _STRIP_HL(cells[3]) if len(cells) > 3 else "",
        })
    return actions


# --------------------------------------------------------------------------
# preview v0.3：类型化知识点树（knowledge-tree JSON 块）+ 立场萃取
# --------------------------------------------------------------------------
_KT_RE = re.compile(
    r"<!--\s*knowledge-tree[^>]*-->\s*```json\s*(\{.*?\})\s*```",
    re.DOTALL,
)


def extract_knowledge_tree(body: str) -> dict:
    """抓 preview 正文里的 `<!-- knowledge-tree v0.3 -->` + ```json 块。

    返回 {"summary": str|None, "topics": [...]}；缺失或解析失败时返回空结构。
    每个 topic = {t, icon?, nodes:[{type, target?, dir?, head?, detail?, chain?,
                  action?, target_price?, stop_loss?}]}。类型不限，前端兜底到「其他」。
    """
    m = _KT_RE.search(body or "")
    if not m:
        return {"summary": None, "topics": []}
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return {"summary": None, "topics": []}
    topics = data.get("topics") or []
    if not isinstance(topics, list):
        topics = []
    summary = data.get("summary")
    return {"summary": summary.strip() if isinstance(summary, str) else None,
            "topics": topics}


def _norm_target(name: str) -> str:
    """标的归一：去括号说明（'黄金（纽约期货金）' -> '黄金'），用于立场聚合。"""
    return re.split(r"[（(]", str(name or ""), maxsplit=1)[0].strip()


def derive_stances(topics: list) -> list[dict]:
    """从知识点树萃取立场：按标的聚合带 target 且含方向/价位/操作信号的节点。

    立场 = type∈{trend,view,action}（或任意带 dir/target_price/stop_loss/action 的）
    且带 target 的节点投影。dir 仅取显式 long/short（不从「减持」等动作臆测方向）。
    一份数据两处用——演化图与立场徽章都吃它，统一走 ②③，不依赖 wiki。
    """
    agg: dict[str, dict] = {}
    order: list[str] = []
    for topic in topics:
        for n in (topic.get("nodes") or []):
            tgt = _norm_target(n.get("target", ""))
            if not tgt:
                continue
            dir_ = n.get("dir")
            has_signal = bool(dir_ or n.get("target_price")
                              or n.get("stop_loss") or n.get("action"))
            if not has_signal:
                continue
            if tgt not in agg:
                agg[tgt] = {"target": tgt, "dir": None, "target_price": None,
                            "stop_loss": None, "actions": []}
                order.append(tgt)
            s = agg[tgt]
            if dir_ in ("long", "short") and not s["dir"]:
                s["dir"] = dir_
            if n.get("target_price"):
                s["target_price"] = str(n["target_price"])
            if n.get("stop_loss"):
                s["stop_loss"] = str(n["stop_loss"])
            if n.get("action") and n["action"] not in s["actions"]:
                s["actions"].append(n["action"])
    return [agg[t] for t in order]


def preview_path_for(raw_path: Path, up_dir: Path) -> Path:
    """raw <up>/videos/Y/M/x.json -> <up>/_previews/videos/Y/M/x.md"""
    rel = raw_path.relative_to(up_dir)
    return up_dir / "_previews" / rel.with_suffix(".md")


# --------------------------------------------------------------------------
# 单条 item 构建
# --------------------------------------------------------------------------
def kb_rel(path: Path, kb_root: Path) -> str:
    return path.resolve().relative_to(kb_root).as_posix()


def build_video_item(raw_path: Path, up_dir: Path, kb_root: Path) -> dict | None:
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    pv = preview_path_for(raw_path, up_dir)
    tldr, mentions, actions, sub_chars = [], [], [], None
    kt = {"summary": None, "topics": []}
    preview_rel = None
    if pv.exists():
        fm, body = split_md(pv.read_text(encoding="utf-8"))
        tldr = extract_tldr(body)
        mentions = extract_mentions(fm)
        actions = extract_up_actions(body)
        sub_chars = fm_scalar(fm, "subtitle_chars")
        kt = extract_knowledge_tree(body)
        preview_rel = kb_rel(pv, kb_root)
    date = (raw.get("published_at") or "")[:10]
    stances = derive_stances(kt["topics"])
    return {
        "date": date,
        "kind": "video",
        "id": raw.get("bvid") or raw_path.stem,
        "title": raw.get("title") or raw_path.stem,
        "summary": kt["summary"],
        "tldr": tldr,
        "topics": kt["topics"],
        "stances": stances,
        "mentions": mentions,
        "up_actions": actions,
        "is_trade": bool(actions) or bool(stances),
        "stats": {
            "duration": raw.get("duration_seconds"),
            "subtitle_chars": int(sub_chars) if sub_chars and sub_chars.isdigit() else None,
        },
        "src": kb_rel(raw_path, kb_root),
        "preview": preview_rel,
        "link": f"https://www.bilibili.com/video/{raw.get('bvid')}" if raw.get("bvid") else None,
    }


_TRADE_HINT = re.compile(r"止损|减持|加仓|杠杆|做多|做空|建仓|清仓|止盈")


def build_dynamic_item(raw_path: Path, up_dir: Path, kb_root: Path) -> dict | None:
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    pv = preview_path_for(raw_path, up_dir)
    tldr, mentions = [], []
    kt = {"summary": None, "topics": []}
    total_images = ad_count = 0
    preview_rel = title = None
    if pv.exists():
        fm, body = split_md(pv.read_text(encoding="utf-8"))
        tldr = extract_tldr(body)
        mentions = extract_mentions(fm)
        total_images = int(fm_scalar(fm, "total_images") or 0)
        ad_count = int(fm_scalar(fm, "ad_count") or 0)
        kt = extract_knowledge_tree(body)
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1:
            title = h1.group(1).split("·", 1)[-1].strip()
        preview_rel = kb_rel(pv, kb_root)
    date = raw.get("date") or raw_path.stem
    total = (raw.get("stats") or {}).get("total")
    stances = derive_stances(kt["topics"])
    joined = " ".join(tldr)
    return {
        "date": date,
        "kind": "dynamic",
        "id": date,
        "title": title or f"{date} 动态聚合",
        "summary": kt["summary"],
        "tldr": tldr,
        "topics": kt["topics"],
        "stances": stances,
        "mentions": mentions,
        "up_actions": [],
        "is_trade": bool(_TRADE_HINT.search(joined)) or bool(stances),
        "stats": {"total": total, "images": total_images, "ad": ad_count},
        "src": kb_rel(raw_path, kb_root),
        "preview": preview_rel,
        "link": None,
    }


# --------------------------------------------------------------------------
# 单个 UP 主 → timeline.json
# --------------------------------------------------------------------------
def build_for_uploader(up_dir: Path, kb_root: Path) -> dict:
    items = []
    videos_dir = up_dir / "videos"
    if videos_dir.is_dir():
        for jp in sorted(videos_dir.rglob("*.json")):
            it = build_video_item(jp, up_dir, kb_root)
            if it:
                items.append(it)
    dynamics_dir = up_dir / "dynamics"
    if dynamics_dir.is_dir():
        for jp in sorted(dynamics_dir.rglob("*.json")):
            it = build_dynamic_item(jp, up_dir, kb_root)
            if it:
                items.append(it)
    items.sort(key=lambda x: (x["date"], x["kind"]))

    # 从任一源拿 uploader / uid（raw 权威）
    uploader = up_dir.name
    uid = None
    probe = next((up_dir / "videos").rglob("*.json"), None) if (up_dir / "videos").is_dir() else None
    if probe is None and (up_dir / "dynamics").is_dir():
        probe = next((up_dir / "dynamics").rglob("*.json"), None)
    if probe is not None:
        try:
            p = json.loads(probe.read_text(encoding="utf-8"))
            uploader = p.get("uploader") or uploader
            uid = p.get("uid")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "source": "bilibili",
        "uploader": uploader,
        "uid": uid,
        "generated": None,   # 时间戳由调用方/CI 盖，保持可复现
        "count": len(items),
        "n_videos": sum(1 for i in items if i["kind"] == "video"),
        "n_dynamics": sum(1 for i in items if i["kind"] == "dynamic"),
        "items": items,
    }


def iter_uploader_dirs(bili_root: Path):
    if not bili_root.is_dir():
        return
    for child in sorted(bili_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if (child / "videos").is_dir() or (child / "dynamics").is_dir():
            yield child


def main():
    ap = argparse.ArgumentParser(description="聚合 raw 媒体源 → 创作者 timeline.json")
    ap.add_argument("--kb-root", help="Knowledge_Wiki 根目录")
    ap.add_argument("--up", help="只重建指定 UP 主目录名（默认全部）")
    args = ap.parse_args()

    kb_root = resolve_kb_root(args.kb_root)
    bili_root = kb_root / "raw" / "transcripts" / "bilibili"
    if not bili_root.is_dir():
        print(f"✗ 未找到 {bili_root}（KB_ROOT 是否指向有效 Knowledge_Wiki？）", file=sys.stderr)
        sys.exit(1)

    targets = list(iter_uploader_dirs(bili_root))
    if args.up:
        targets = [d for d in targets if d.name == args.up]
        if not targets:
            print(f"✗ 未找到 UP 主目录：{args.up}", file=sys.stderr)
            sys.exit(1)

    if not targets:
        print("（无 UP 主目录，未生成任何 timeline.json）")
        return

    for up_dir in targets:
        data = build_for_uploader(up_dir, kb_root)
        out = up_dir / "_previews" / "timeline.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ {kb_rel(out, kb_root)}  "
              f"({data['count']} 条：{data['n_videos']} 视频 + {data['n_dynamics']} 动态)")


if __name__ == "__main__":
    main()
