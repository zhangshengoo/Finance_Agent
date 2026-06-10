#!/usr/bin/env bash
# 开发模式：编译 KB → data.json，起本地服务并打开浏览器。
# 用法：  ./frontend/serve.sh [端口]   (默认 8000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"

echo "▸ 编译知识库 → data.json"
python3 "$ROOT/Knowledge_Wiki/scripts/build_frontend_data.py"

# 释放端口（若被占用）
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▸ 端口 $PORT 已占用，释放中"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
fi

URL="http://localhost:$PORT"
echo "▸ 服务启动：$URL  (Ctrl+C 停止)"
( sleep 1; (open "$URL" >/dev/null 2>&1 || xdg-open "$URL" >/dev/null 2>&1) || true ) &
cd "$ROOT/frontend"
exec python3 -m http.server "$PORT"
