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
MANIFEST_ONLY=""; if [ "${1:-}" = "--manifest" ]; then MANIFEST_ONLY=1; PORT=8000; fi

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
# raw/analysis/backtests/**/*.md（回测 / 记忆环视图）
bt = kb / "raw" / "analysis" / "backtests"
if bt.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(bt.rglob("*.md"))]
# ontology 图谱
g = kb / "ontology" / "graph.jsonl"
if g.is_file():
    files.append(g.relative_to(kb).as_posix())
# B 站时间线（媒体）
bili = kb / "raw" / "transcripts" / "bilibili"
if bili.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(bili.glob("*/_previews/timeline.json"))]
# Serenity 研究报告（frontend 直读 JSON）
sr = kb / "raw" / "research" / "serenity"
if sr.is_dir():
    files += [p.relative_to(kb).as_posix() for p in sorted(sr.glob("*.json"))
              if not p.name.endswith(".provenance.json")]
out.write_text(json.dumps({"files": files}, ensure_ascii=False), encoding="utf-8")
print(f"  {len(files)} 个源文件")
PY

if [ -n "$MANIFEST_ONLY" ]; then echo "▸ 仅刷新清单 manifest.json（未起服务）"; exit 0; fi

# 释放端口（若被占用）
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "▸ 端口 $PORT 已占用，释放中"
  lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
fi

URL="http://localhost:$PORT/frontend/"
echo "▸ 从项目根起服务：$URL  (Ctrl+C 停止)"
echo "  iPhone/iPad (Tailscale): http://100.79.114.124:$PORT/frontend/"
echo "  提示：改 .md 内容刷新即见；新增/改名文件后重跑本脚本刷新清单。"
( sleep 1; (open "$URL" >/dev/null 2>&1 || xdg-open "$URL" >/dev/null 2>&1) || true ) &
cd "$ROOT"
# 本地开发服务：① 仅绑 127.0.0.1（本地-only，杜绝局域网可达）；② no-store 禁缓存；
# ③ /manifest.json 动态实时 glob；④ SSE 桥 GET /api/backtest/stream?ticker=&mode= 流式跑 run_backtest
#    （mode: export=M1 反思导出 / simulate=M2 净值模拟 --no-reflect；ticker 严格 ^\d{6}$、mode 白名单、
#     subprocess 参数数组不走 shell、串行锁防并发、ThreadingTCPServer 不阻塞）；⑤ 保留 POST /api/backtest（兼容）。
exec python3 - "$PORT" "$KB" "$ROOT" <<'PY'
import sys, json, re, subprocess, threading, http.server, socketserver
from pathlib import Path
from urllib.parse import urlparse, parse_qs
PORT = int(sys.argv[1]); KB = Path(sys.argv[2]); ROOT = Path(sys.argv[3])
SKIP = {"CLAUDE.md", "README.md", "_schema.md", "_areas-registry.md", "purpose.md"}
TICKER_RE = re.compile(r"^\d{6}$")
VENV = ROOT / "TradingAgents-CN" / ".venv" / "bin" / "python"
SCRIPT = ROOT / ".claude" / "skills" / "backtest-analysis" / "scripts" / "run_backtest.py"
TA_ROOT = ROOT / "TradingAgents-CN"
RUN_LOCK = threading.Lock()   # 串行化回测运行（防并发撞 proxy/内存）
def build_cmd(ticker, mode):
    cmd = [str(VENV), str(SCRIPT), "--ticker", ticker, "--mode",
           "simulate" if mode == "simulate" else "export", "--ta-root", str(TA_ROOT)]
    if mode == "simulate":
        cmd.append("--no-reflect")   # M2 净值：纯算价、零 LLM、不撞 proxy
    return cmd
def gen_manifest():
    files = []
    for p in sorted((KB / "wiki").rglob("*.md")):
        if p.name in SKIP or p.name.startswith("."):
            continue
        files.append(p.relative_to(KB).as_posix())
    for sub in ("raw/analysis/stocks", "raw/analysis/backtests"):
        d = KB / sub
        if d.is_dir():
            files += [p.relative_to(KB).as_posix() for p in sorted(d.rglob("*.md"))]
    g = KB / "ontology" / "graph.jsonl"
    if g.is_file():
        files.append(g.relative_to(KB).as_posix())
    bili = KB / "raw" / "transcripts" / "bilibili"
    if bili.is_dir():
        files += [p.relative_to(KB).as_posix() for p in sorted(bili.glob("*/_previews/timeline.json"))]
    sr = KB / "raw" / "research" / "serenity"
    if sr.is_dir():
        files += [p.relative_to(KB).as_posix() for p in sorted(sr.glob("*.json"))
                  if not p.name.endswith(".provenance.json")]
    return json.dumps({"files": files}, ensure_ascii=False).encode("utf-8")
def run_export(ticker):
    cmd = [str(VENV), str(SCRIPT), "--ticker", ticker, "--mode", "export", "--ta-root", str(TA_ROOT)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "export 超时（>240s）"}
    lines = (p.stdout or "").splitlines()
    okline = next((l for l in lines if l.startswith("OK ")), "")
    report = next((l.split("report :", 1)[1].strip() for l in lines if "report :" in l), "")
    tail = "\n".join(lines[-6:])
    ok = p.returncode == 0 and bool(okline)
    return {"ok": ok, "message": okline or (tail or "export 失败"), "report": report,
            "tail": tail, "code": p.returncode}
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def _sse(self, event, data):
        self.wfile.write(("event: %s\ndata: %s\n\n" % (
            event, json.dumps(data, ensure_ascii=False))).encode("utf-8"))
        self.wfile.flush()
    def _stream_backtest(self, ticker, mode):
        # SSE 流式跑 run_backtest：逐行 stdout → progress 事件；收尾 done 事件带 ok/report。串行锁防并发。
        if not RUN_LOCK.acquire(blocking=False):
            self._sse("error", {"message": "已有回测在运行，请稍候重试"}); return
        proc = None
        try:
            self._sse("start", {"ticker": ticker, "mode": mode})
            proc = subprocess.Popen(build_cmd(ticker, mode), cwd=str(ROOT),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
            okline, report, tail = "", "", []
            for line in proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    continue
                tail.append(line); tail[:] = tail[-8:]
                if line.startswith("OK "):
                    okline = line
                if "report :" in line:
                    report = line.split("report :", 1)[1].strip()
                self._sse("progress", {"line": line[:300]})
            code = proc.wait()
            ok = code == 0 and bool(okline)
            self._sse("done", {"ok": ok, "message": okline or ("\n".join(tail) or "失败"),
                               "report": report, "code": code})
        except (BrokenPipeError, ConnectionResetError):
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception as e:
            try: self._sse("error", {"message": repr(e)})
            except Exception: pass
        finally:
            RUN_LOCK.release()
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/backtest/stream":
            q = parse_qs(urlparse(self.path).query)
            ticker = (q.get("ticker") or [""])[0].strip()
            mode = (q.get("mode") or ["export"])[0].strip()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            if not TICKER_RE.match(ticker):
                self._sse("error", {"message": "ticker 非法（需 6 位数字）"}); return
            if mode not in ("export", "simulate"):
                self._sse("error", {"message": "mode 非法（export|simulate）"}); return
            self._stream_backtest(ticker, mode); return
        if path in ("/frontend/manifest.json", "/manifest.json"):
            body = gen_manifest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        return super().do_GET()
    def do_POST(self):
        if self.path.split("?")[0] == "/api/backtest":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._json({"ok": False, "message": "请求体非法"}, 400)
            ticker = str(data.get("ticker", "")).strip()
            if not TICKER_RE.match(ticker):
                return self._json({"ok": False, "message": "ticker 非法（需 6 位数字）"}, 400)
            return self._json(run_export(ticker))
        return self._json({"ok": False, "message": "not found"}, 404)
socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.daemon_threads = True
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), H) as httpd:
    print(f"  serving (0.0.0.0 · no-cache · 动态 manifest · POST /api/backtest · SSE /api/backtest/stream) on :{PORT}")
    httpd.serve_forever()
PY
