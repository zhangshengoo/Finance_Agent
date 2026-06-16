#!/usr/bin/env bash
# 启动 / 重启 frontend 本地服务（nohup 持久后台，睡眠不断）
# 用法：bash start-frontend.sh [端口]   默认 8000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8000}"
KB="$ROOT/Knowledge_Wiki"
PID_FILE="$ROOT/frontend/server.pid"
LOG_FILE="$ROOT/frontend/server.log"

# 停掉旧进程
if [ -f "$PID_FILE" ]; then
  OLD=$(cat "$PID_FILE")
  if kill -0 "$OLD" 2>/dev/null; then
    echo "▸ 停止旧进程 PID $OLD"
    kill "$OLD"
    sleep 0.5
  fi
fi
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▸ 端口 $PORT 仍被占用，强制释放"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
  sleep 0.5
fi

# 刷新清单
echo "▸ 刷新 frontend/manifest.json"
python3 - "$KB" "$ROOT/frontend/manifest.json" <<'PY'
import sys, json
from pathlib import Path
kb, out = Path(sys.argv[1]), Path(sys.argv[2])
SKIP = {"CLAUDE.md", "README.md", "_schema.md", "_areas-registry.md", "purpose.md"}
files = []
for p in sorted((kb / "wiki").rglob("*.md")):
    if p.name in SKIP or p.name.startswith("."): continue
    files.append(p.relative_to(kb).as_posix())
sd = kb / "raw" / "analysis" / "stocks"
if sd.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(sd.glob("*.md"))]
g = kb / "ontology" / "graph.jsonl"
if g.is_file(): files.append(g.relative_to(kb).as_posix())
bili = kb / "raw" / "transcripts" / "bilibili"
if bili.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(bili.glob("*/_previews/timeline.json"))]
out.write_text(json.dumps({"files": files}, ensure_ascii=False), encoding="utf-8")
print(f"  {len(files)} 个源文件")
PY

# nohup 启动
cd "$ROOT"
nohup python3 -m http.server "$PORT" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "▸ 服务已启动  PID=$(cat "$PID_FILE")  http://localhost:$PORT/frontend/"
echo "  日志：tail -f $LOG_FILE"
echo "  停止：kill \$(cat $PID_FILE)"
