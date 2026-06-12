#!/usr/bin/env bash
# 本地 live 模式（零编译）：生成源清单 manifest.json，从项目根起本地服务，
# 浏览器用 kb-parse.js 直接解析 KB 的 md/jsonl —— 不再编译 / 维护 data.json。
# 改任意 wiki/raw 下的 .md 内容，刷新浏览器即见（无需重建）。
# 新增 / 改名 / 删除文件后重跑本脚本即可刷新清单。
#   用法：  ./frontend/serve.sh [端口]   (默认 8000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"
KB="$ROOT/Knowledge_Wiki"

echo "▸ 生成源清单 frontend/manifest.json（live 解析，无需编译 data.json）"
python3 - "$KB" "$ROOT/frontend/manifest.json" <<'PY'
import sys, json
from pathlib import Path
kb, out = Path(sys.argv[1]), Path(sys.argv[2])
SKIP = {"CLAUDE.md", "README.md", "_schema.md", "_areas-registry.md", "purpose.md"}
files = []
# wiki/**/*.md（与 build_index SKIP_FILES 对齐）
for p in sorted((kb / "wiki").rglob("*.md")):
    if p.name in SKIP or p.name.startswith("."):
        continue
    files.append(p.relative_to(kb).as_posix())
# raw/analysis/stocks/*.md（研究报告视图）
sd = kb / "raw" / "analysis" / "stocks"
if sd.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(sd.glob("*.md"))]
# ontology 图谱
g = kb / "ontology" / "graph.jsonl"
if g.is_file():
    files.append(g.relative_to(kb).as_posix())
# B 站时间线（媒体）
bili = kb / "raw" / "transcripts" / "bilibili"
if bili.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(bili.glob("*/_previews/timeline.json"))]
out.write_text(json.dumps({"files": files}, ensure_ascii=False), encoding="utf-8")
print(f"  {len(files)} 个源文件")
PY

# 释放端口（若被占用）
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▸ 端口 $PORT 已占用，释放中"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
fi

URL="http://localhost:$PORT/frontend/"
echo "▸ 从项目根起服务：$URL  (Ctrl+C 停止)"
echo "  提示：改 .md 内容刷新即见；新增/改名文件后重跑本脚本刷新清单。"
( sleep 1; (open "$URL" >/dev/null 2>&1 || xdg-open "$URL" >/dev/null 2>&1) || true ) &
cd "$ROOT"
exec python3 -m http.server "$PORT"
