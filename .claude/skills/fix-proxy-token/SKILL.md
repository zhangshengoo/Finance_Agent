---
name: fix-proxy-token
description: >-
  修复本机 claude-max-proxy(:5678) 的 OAuth token 过期问题，让 TradingAgents-CN 引擎能正常调
  Claude。**只要**出现以下任一情况就用本技能，不要把命令甩给用户自己敲：proxy / 引擎报
  401 或 AuthenticationError；/health 的 token_hours 偏低或为负；引擎首个 LLM 调用就鉴权失败；
  跑个股/行业分析前发现 token 快过期（剩余 < 一次跑程时长）；用户说「proxy token 过期 / 刷新
  proxy token / proxy 401 / 重新授权 proxy / fix proxy token / 引擎连不上 Claude」。
  本技能**盲刷**：把 macOS Keychain 里的活凭证经重定向直接写进凭证文件来刷新 token，**全程不查看、不打印
  凭证明文**（write-only），并自动校验。属用户显式授权的、范围严格限定的凭证刷新自动化。
---

# Fix Proxy Token（claude-max-proxy :5678 token 盲刷）

TradingAgents-CN 引擎经本机 `claude-max-proxy`（`Third_Party/claude-max-proxy/`，监听 `:5678`，用 Claude Max 订阅 OAuth，零 API 费）调 Anthropic。proxy 从**文件** `~/.claude/.credentials.json` 读 `claudeAiOauth.accessToken`；但 macOS 上 `claude` 的活凭证在 **Keychain**（服务名 `Claude Code-credentials`）。proxy 自带的 `claude --print` 自动刷新只更新 Keychain、**不写回文件** → 文件 token 持续过期 → 引擎 401。本技能就是把这条链补上：**把 Keychain 的活凭证盲刷进文件**。

## 安全契约（这是本技能存在的全部意义，务必遵守）

1. **盲刷、绝不查看**：刷新 = 把 Keychain 项经**重定向**写进凭证文件。凭证明文**永不**进入你的上下文、**永不**打印到 stdout。
2. **绝不读凭证**：**禁止** `cat ~/.claude/.credentials.json`、`security find-generic-password -w ...`（不带重定向会把明文打到终端）、或任何会让凭证内容回显给你的命令。要做的只有「写」，没有「读」。
3. **失败不毁文件**：刷新先写临时文件，确认 `security` 成功且非空才 `mv` 覆盖正式文件 —— Keychain 被锁/拒绝/项缺失时，**不会**把仍可能有效的旧凭证截断成空。脚本已实现这点；**不要**直接用裸命令 `security ... > ~/.claude/.credentials.json`（它在 security 失败时会先把文件清空）。
4. **localhost 探活必须绕系统代理**：本机常开 v2rayN（TUN/系统代理），`curl` 打 `localhost:5678` 会被它串掉返回空。所有探活/补全一律加 `--noproxy '*'`。脚本已内置。

> 这是用户**显式授权**、范围**严格限定**于「Keychain→凭证文件盲刷」的自动化（用户原话：允许运行 `security find-generic-password -w -s "Claude Code-credentials" -a "$USER" > ~/.claude/.credentials.json`，不允许查看）。除此之外不做任何凭证读写。

## 主流程

几乎所有情况一条命令搞定（诊断→必要时刷新→校验）：

```bash
bash .claude/skills/fix-proxy-token/scripts/proxy_token.sh ensure
```

它会：① `status` 看 proxy 在不在、`token_hours` 够不够（默认阈值 0.3h≈18min）；② 不够就 `refresh` 盲刷；③ `verify` 用一次最小补全确认 HTTP 200。读它打印的状态行即可（永远不含凭证）。

### 分步（按需单独调用）

| 命令 | 作用 | 退出码 |
|---|---|---|
| `proxy_token.sh status` | 只诊断：proxy 是否在线 + token_hours | 0 OK / 2 proxy 离线 / 3 token 低 |
| `proxy_token.sh refresh` | 盲刷（Keychain→文件，安全临时文件）+ 复检 | 0 成功 / 4 Keychain 导出失败 |
| `proxy_token.sh verify` | 经 proxy 跑一次最小补全 | 0 HTTP200 / 5 失败 |
| `proxy_token.sh ensure` | 上面三步串起来（默认） | 综合 |

阈值可调：`MIN_HOURS=0.5 bash .../proxy_token.sh ensure`（跑深度档前想留足余量时调高）。

## 分支处理

- **proxy 离线**（`status` 返回 2 / `ensure` 提示 down）：先后台启动它，再重跑 `ensure`：
  ```bash
  cd Third_Party/claude-max-proxy && unset VIRTUAL_ENV && .venv/bin/python proxy.py
  ```
  用 `run_in_background: true` 起。启动日志里 `Token valid for: X hours` 为负=文件 token 已过期（正常，刷新即可）。
- **刷新后仍 401 / `refresh` 返回 4**（Keychain 里的也过期了）：这步必须**用户**操作 —— 在终端跑 `claude` 后 `/login` 重新走 OAuth 授权刷新 Keychain，完成后再 `bash .../proxy_token.sh ensure`。你只把这条指引交给用户，不代跑登录。
- **刷新成功但 token_hours 仍偏低**：Keychain 当前这枚 token 本就快过期；要长时间跑程（如标准/深度档），提示用户最好先在终端用一次 `claude` 触发其自身刷新，再 `ensure`。

## 跑分析前的预检用法

派发引擎（个股/行业分析、回测）前，先 `ensure` 一次确认 token 够整个跑程：一次快速档 ~6min、标准档 ~12min、深度档 ~更久。`token_hours × 60` 要明显大于跑程分钟数，否则跑到一半 token 过期会前功尽弃。够则直接派发，不够则先刷新（或提示用户 `/login`）。

## 关联

- 根因与运维细节：`.claude/skills/stock-analysis/references/proxy-ops.md`、记忆 `project_claude_max_proxy_ops`、`docs/tradingagents-cn/bugfix-log.md` #6。
- 注意区分本问题与 v2rayN 数据源误路由（`project_eastmoney_push2_v2rayn_misroute`，那是数据抓取，不是 :5678 鉴权）。
