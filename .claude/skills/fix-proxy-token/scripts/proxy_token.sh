#!/usr/bin/env bash
# proxy_token.sh — diagnose / blind-refresh / verify the claude-max-proxy OAuth token.
#
# SAFETY CONTRACT (the whole point of this script):
#   - "refresh" BLINDLY re-exports the macOS Keychain item "Claude Code-credentials"
#     into ~/.claude/.credentials.json. The credential plaintext is NEVER printed to
#     stdout and NEVER enters the calling agent's context — only status lines + exit codes.
#   - NEVER `cat` the creds file; NEVER run `security ... -w` without a redirect.
#   - refresh writes to a temp file first and only moves it into place when the export
#     succeeded AND is non-empty, so a failed/denied Keychain read can NOT truncate a
#     still-valid creds file (the naive `security ... > file` would clobber it on failure).
#   - all localhost probes use `curl --noproxy '*'`; a local v2rayN (TUN/system proxy)
#     otherwise intercepts localhost:5678 and returns empty.
set -uo pipefail

PROXY_URL="${PROXY_URL:-http://localhost:5678}"
CRED_FILE="${CRED_FILE:-$HOME/.claude/.credentials.json}"
KEYCHAIN_SERVICE="${KEYCHAIN_SERVICE:-Claude Code-credentials}"
MIN_HOURS="${MIN_HOURS:-0.3}"          # token below this many hours is considered "low"
QUICK_MODEL="${QUICK_MODEL:-claude-haiku-4-5-20251001}"

CURL=(curl -s --noproxy '*' --max-time 12)

_health_hours() {
  # echoes token_hours (may be negative/empty); never echoes any credential
  "${CURL[@]}" "$PROXY_URL/health" 2>/dev/null | python3 -c '
import sys, json
try:
    print(json.load(sys.stdin).get("token_hours", ""))
except Exception:
    print("")
' 2>/dev/null
}

cmd_status() {
  local h; h="$(_health_hours)"
  if [ -z "$h" ]; then
    echo "DOWN: proxy 未响应 $PROXY_URL — 先后台启动 proxy 再重试"
    return 2
  fi
  if awk -v h="$h" -v m="$MIN_HOURS" 'BEGIN{exit !((h+0) >= (m+0))}'; then
    echo "OK: token_hours=$h (>= ${MIN_HOURS}h)"
    return 0
  fi
  echo "LOW: token_hours=$h (< ${MIN_HOURS}h) — 需要刷新"
  return 3
}

cmd_refresh() {
  local tmp; tmp="$(mktemp)"
  # 盲刷：security 输出经重定向直接进临时文件，绝不回显；失败/空则不动正式文件
  if security find-generic-password -w -s "$KEYCHAIN_SERVICE" -a "$USER" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    mkdir -p "$(dirname "$CRED_FILE")"
    mv "$tmp" "$CRED_FILE"
    chmod 600 "$CRED_FILE" 2>/dev/null || true
    echo "REFRESHED: 已把 Keychain 凭证盲刷进凭证文件（内容未显示）"
  else
    rm -f "$tmp"
    echo "FAIL: Keychain 导出失败（项缺失 / 钥匙串被锁 / 被拒）。凭证文件保持不变。"
    echo "  → 若反复失败：Keychain 里的 token 也过期了，请在终端运行 'claude' 后用 /login 重新授权，再重试。"
    return 4
  fi
  # proxy 每个请求重读文件，无需重启；复检
  sleep 1
  cmd_status
}

cmd_verify() {
  local out code
  out="$("${CURL[@]}" -w $'\n%{http_code}' \
        "$PROXY_URL/v1/messages" \
        -H 'content-type: application/json' \
        -d "{\"model\":\"$QUICK_MODEL\",\"max_tokens\":4,\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}" \
        2>/dev/null)"
  code="$(printf '%s' "$out" | tail -n1)"
  if [ "$code" = "200" ]; then
    echo "VERIFY OK: proxy 跑通一次补全 (HTTP 200) — token 有效"
    return 0
  fi
  echo "VERIFY FAIL: HTTP ${code:-<无响应>} — token 可能仍无效（或 proxy 离线）"
  return 5
}

cmd_ensure() {
  local s
  cmd_status; s=$?
  if [ "$s" -eq 2 ]; then
    echo "  → proxy 离线：请先后台启动 (cd Third_Party/claude-max-proxy && unset VIRTUAL_ENV && .venv/bin/python proxy.py)，再重跑 ensure。"
    return 2
  fi
  if [ "$s" -ne 0 ]; then
    cmd_refresh || return $?
  fi
  cmd_verify
}

case "${1:-ensure}" in
  status)  cmd_status ;;
  refresh) cmd_refresh ;;
  verify)  cmd_verify ;;
  ensure)  cmd_ensure ;;
  *) echo "usage: $0 {status|refresh|verify|ensure}"; exit 64 ;;
esac
