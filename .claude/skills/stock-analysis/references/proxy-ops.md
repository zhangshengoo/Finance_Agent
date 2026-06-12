# claude-max-proxy 运维契约（引擎可达性前置）

> 按需加载。`stock-analysis` 在 **Step 2 派发 subagent 之前**必须确保引擎能调到模型，否则会浪费一整次运行（5–12 分钟）才发现连不上。
>
> 为什么需要它：TradingAgents-CN 引擎的 `backend_url=http://localhost:5678`——它不直连 Anthropic，而是经 **claude-max-proxy**（把你的 Claude Max 订阅转成 Anthropic Messages API）。proxy 不在线 / token 过期，引擎所有 LLM 调用全挂。

## 它在哪、怎么跑

- 位置：`Third_Party/claude-max-proxy/`（项目内）。入口 `proxy.py`，端口默认 `5678`（`PORT` 环境变量可覆盖）。
- 它从 `~/.claude/.credentials.json` 读 `claudeAiOauth.accessToken`，加 OAuth beta 头转发到 `api.anthropic.com`。
- 用它自带的 venv 跑（不是项目其它 venv）：`Third_Party/claude-max-proxy/.venv/bin/python`。

## 派发前预检（Step 2 必做）

**1) 探活**——任意 HTTP 状态码都算在线（`404` 正常，API 在 messages 路径，根路径本就没有）：

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/
```

返回任意数字（包括 404）→ 在线，直接派发 subagent。返回空 / `000` / connection refused → **离线，走下一步自启**。

**2) 不在线则自启**（后台跑；`unset VIRTUAL_ENV` 是因为当前 shell 可能已激活别的 venv，会污染 proxy 的依赖解析）：

```bash
cd Third_Party/claude-max-proxy && unset VIRTUAL_ENV && .venv/bin/python proxy.py
```

用 `run_in_background: true` 起，然后再探活一次确认 `5678` 起来了，再派发。

> 把后台进程的 stdout/stderr 丢弃（`>/dev/null 2>&1`）再起——proxy 每个请求都打日志，长会话会把 harness 的 task 临时盘写满（本会话踩过：`tasks` 目录 ENOSPC）。

## 401 AuthenticationError —— token 过期（高频坑）

**症状**：proxy 在线（探活 200/404），但引擎运行里报 `AuthenticationError` / HTTP 401。

**根因**：macOS 把**活的**凭证存在 **Keychain**（服务名 `Claude Code-credentials`），而 proxy 读的是**文件** `~/.claude/.credentials.json`。`claude` 刷新 token 后只更新 Keychain，文件就**过期了**。本会话第一次真跑就因为文件里的 token 过期 ~22 小时而 401。

**修复（这是用户操作，不是 Agent 操作）**：把 Keychain 里的活凭证导出覆盖到文件，然后重启 proxy。

```bash
# ⚠️ 凭证操作：由用户在自己的终端运行。Agent 不读取 / 不提取凭证明文，只把命令交给用户。
security find-generic-password -w -s "Claude Code-credentials" -a "$USER" > ~/.claude/.credentials.json
```

> **安全红线**：Agent **绝不**读取 `~/.claude/.credentials.json`、**绝不**调 `security` 提取 Keychain 明文——harness 会拦，且这是用户私密凭证。Agent 的职责到「把上面这条命令原样呈现给用户、请其自行执行」为止；用户跑完并重启 proxy 后，Agent 再探活继续。若用户跑完仍 401，提示其重新走一遍 Claude Code 授权登录（刷新 Keychain 后再导出）。

## 给 Agent 的判定速查

| 探活结果 | 引擎报错 | 处置 |
|---|---|---|
| 任意 HTTP 码 | 无 | 在线，直接派发 |
| 空 / refused | — | 自启 proxy（上方命令，后台），再探活 |
| 200/404 | 401 / AuthenticationError | token 过期 → 把 keychain 导出命令交用户跑，等其重启 proxy 后再继续 |
| 200/404 | 其它 5xx / 超时 | 非鉴权问题，按 subagent 失败策略重试一次 |
