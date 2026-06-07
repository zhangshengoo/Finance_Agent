#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
一次性迁移：把 raw/transcripts/bilibili/ 平铺老格式迁到新四级布局。

老格式：
    raw/transcripts/bilibili/<uploader>_<bvid>.json           （视频）
    raw/transcripts/bilibili/<uploader>_dyn_<id>.json         （单条动态）

新格式：
    raw/transcripts/bilibili/<uploader-slug>/videos/<YYYY>/<YYYY-MM>/<date>_<bvid>.json
    raw/transcripts/bilibili/<uploader-slug>/dynamics/<YYYY>/<YYYY-MM>/<date>.json
      （动态按 published_at UTC+8 日期分桶聚合，C2b 合并写入）

用法：
    # dry-run（默认）：只打印迁移计划
    uv run migrate_bilibili_layout.py --kb-root /path/to/Knowledge_Wiki

    # 真跑：移文件到 .archive/、写新位置
    uv run migrate_bilibili_layout.py --kb-root /path/to/Knowledge_Wiki --apply
"""

import argparse
import json
import os
import shutil
import sys

from _bilibili_common import (
    assert_kb_layout,
    atomic_write_json,
    dynamic_daily_path,
    iso_utc_to_cn_date,
    merge_daily_dynamics,
    resolve_kb_root,
    slugify,
    video_path,
)


def scan_legacy(legacy_dir: str) -> list[str]:
    """只扫顶层 *.json，跳过 .archive/ 和子目录。"""
    if not os.path.isdir(legacy_dir):
        return []
    out = []
    for name in sorted(os.listdir(legacy_dir)):
        if name.startswith("."):
            continue
        full = os.path.join(legacy_dir, name)
        if os.path.isfile(full) and name.endswith(".json"):
            out.append(full)
    return out


def plan_video(kb_root: str, payload: dict) -> tuple[str | None, str | None]:
    """返回 (target_relpath, skip_reason)"""
    bvid = payload.get("bvid")
    if not bvid:
        return None, "missing bvid"
    uploader = payload.get("uploader", "")
    uid = str(payload.get("uid", ""))
    uploader_slug = slugify(uploader or f"uid-{uid}")
    date = iso_utc_to_cn_date(payload.get("published_at", ""))
    if not date:
        return None, "missing published_at"
    return os.path.relpath(video_path(kb_root, uploader_slug, date, bvid), kb_root), None


def plan_dynamic(kb_root: str, payload: dict) -> tuple[str | None, str | None]:
    uploader = payload.get("uploader", "")
    uid = str(payload.get("uid", ""))
    uploader_slug = slugify(uploader or f"uid-{uid}")
    date = iso_utc_to_cn_date(payload.get("published_at", ""))
    if not date:
        return None, "missing published_at"
    return os.path.relpath(dynamic_daily_path(kb_root, uploader_slug, date), kb_root), None


def archive_file(kb_root: str, src: str) -> str:
    """把老文件移到 raw/transcripts/bilibili/.archive/<原名>。返回 archive 相对路径。"""
    legacy_dir = os.path.dirname(src)
    archive_dir = os.path.join(legacy_dir, ".archive")
    os.makedirs(archive_dir, exist_ok=True)
    dst = os.path.join(archive_dir, os.path.basename(src))
    shutil.move(src, dst)
    return os.path.relpath(dst, kb_root)


def main():
    ap = argparse.ArgumentParser(description="迁移老 B 站 raw 文件到四级布局")
    ap.add_argument("--kb-root", default=None)
    ap.add_argument("--apply", action="store_true",
                    help="真跑（默认 dry-run）")
    args = ap.parse_args()

    kb_root = resolve_kb_root(args.kb_root)
    assert_kb_layout(kb_root)

    legacy_dir = os.path.join(kb_root, "raw", "transcripts", "bilibili")
    files = scan_legacy(legacy_dir)

    report = {
        "dry_run": not args.apply,
        "kb_root": kb_root,
        "scanned": len(files),
        "plan": {"videos": [], "dynamics_bucketed": {}},
        "migrated": {"videos": 0, "dynamics_files": 0, "dynamics_entries": 0},
        "archived": [],
        "errors": {},
    }

    # 视频：源 → 目标
    # 动态：先按 (uploader_slug, date) 分桶，再合并写入；每个桶可能涉及多个老文件
    dyn_buckets: dict[tuple[str, str, str, str], list[tuple[str, dict]]] = {}

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            report["errors"][os.path.basename(path)] = f"read failed: {e}"
            continue

        kind = payload.get("kind", "")
        if kind == "video":
            target, skip = plan_video(kb_root, payload)
            if skip:
                report["errors"][os.path.basename(path)] = skip
                continue
            report["plan"]["videos"].append({"from": os.path.relpath(path, kb_root), "to": target})

            if args.apply:
                abs_target = os.path.join(kb_root, target)
                if os.path.exists(abs_target):
                    report["errors"][os.path.basename(path)] = f"target exists: {target}"
                    continue
                atomic_write_json(abs_target, payload)
                arch = archive_file(kb_root, path)
                report["archived"].append(arch)
                report["migrated"]["videos"] += 1

        elif kind == "dynamic":
            target, skip = plan_dynamic(kb_root, payload)
            if skip:
                report["errors"][os.path.basename(path)] = skip
                continue
            uploader = payload.get("uploader", "")
            uid = str(payload.get("uid", ""))
            uploader_slug = slugify(uploader or f"uid-{uid}")
            date = iso_utc_to_cn_date(payload.get("published_at", ""))
            key = (uploader_slug, date, uid, uploader)
            dyn_buckets.setdefault(key, []).append((path, payload))

        else:
            report["errors"][os.path.basename(path)] = f"unknown kind: {kind}"

    # 处理动态桶：每个 (slug, date) 写一份日聚合
    for (uploader_slug, date, uid, uploader), entries in sorted(dyn_buckets.items()):
        target_rel = os.path.relpath(
            dynamic_daily_path(kb_root, uploader_slug, date), kb_root
        )
        report["plan"]["dynamics_bucketed"].setdefault(target_rel, []).extend(
            [os.path.relpath(p, kb_root) for p, _ in entries]
        )

        if args.apply:
            abs_target = os.path.join(kb_root, target_rel)
            if os.path.exists(abs_target):
                report["errors"][target_rel] = "target exists"
                continue

            # 老文件单条动态字段都在 payload 顶层，去掉 source/kind/uid/uploader/fetched_at
            # 提取剩下的动态字段
            new_entries = []
            for _src, p in entries:
                dyn = {k: v for k, v in p.items() if k not in (
                    "source", "kind", "uid", "uploader", "fetched_at",
                )}
                new_entries.append(dyn)

            try:
                merged = merge_daily_dynamics(
                    existing=None, new_entries=new_entries,
                    uid=uid, uploader=uploader, date=date,
                    fetched_at=_iso_now_compat(entries),
                )
                atomic_write_json(abs_target, merged)
                for src, _ in entries:
                    arch = archive_file(kb_root, src)
                    report["archived"].append(arch)
                report["migrated"]["dynamics_files"] += 1
                report["migrated"]["dynamics_entries"] += len(new_entries)
            except Exception as e:
                report["errors"][target_rel] = str(e)

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


def _iso_now_compat(entries: list) -> str:
    """优先用老文件里最新的 fetched_at；否则当前时间。"""
    fetched = [p.get("fetched_at", "") for _, p in entries if p.get("fetched_at")]
    if fetched:
        return max(fetched)
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    main()
