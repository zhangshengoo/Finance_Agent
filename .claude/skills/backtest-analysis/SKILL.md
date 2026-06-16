---
name: backtest-analysis
description: A 股回测 / 交易模拟 Skill（M1 单决策反思 · 记忆功能 A 写半边）。读已有个股分析 snapshot，用 Tushare 真实前向收益调 TradingAgents-CN 原生 reflect_and_remember，把「带收益的历史教训」写进 per-ticker 记忆桶（= 连续记忆功能 B 次日召回的同一批桶），闭合记忆环；再 export 把教训回读导出成前端可读报告（前端「回测/记忆环」单元 + 一键生成已落地）。不重跑引擎。触发词：回测 X / 交易模拟 X / 复盘 X 的决策 / 用真实收益反思 / 记忆功能A / 生成回测报告 X / 刷新 X 的回测 / backtest X / reflect on past decisions。
---

# Backtest Analysis (M1 · 单决策反思 · A 股 only)

> 本 skill 是 **Agent 的回测 / 交易模拟能力**，与 `stock-analysis`、`industry-analysis` 并列在项目根 `.claude/skills/`。它**不重跑引擎**，而是对已有个股分析 snapshot：① 从 Tushare 取真实前向收益；② 重建 `curr_state` 调引擎**原生** `reflect_and_remember` 把教训写进 per-ticker 记忆桶。这正是连续记忆**功能 A（写半边）**——功能 B（读半边）已上线，A 写入后次日同票分析自动召回。
>
> **完整设计 / 坑位**：[backtest-feature-design.md](../../../docs/tradingagents-cn/backtest/backtest-feature-design.md) + [backtest-feature-framework.html](../../../docs/tradingagents-cn/backtest/backtest-feature-framework.html) + 前端单元设计 [backtest-frontend-demo.html](../../../docs/tradingagents-cn/backtest/backtest-frontend-demo.html)。
>
> **三档回测语义**：**M1 单决策反思**（本 skill，最小闭环，无引擎重跑）→ M2 前向组合模拟（净值曲线，引擎层已实现 `--mode simulate`，前端待接）→ M3 历史重跑（含前瞻偏差，仅演示）。
>
> **M1 已端到端落地**：`--mode reflect`（算真实收益 + 写 5 桶记忆）→ `--mode export`（**读回**教训 + 重算收益 → 落前端可读 `raw/analysis/backtests/cn/<ticker>-<runid>.md`）→ 前端「回测 / 记忆环」单元（反思表 + 5 桶教训卡，与「研究报告输出」同一套 md 解析）→ 浏览器**一键生成**（serve.sh 仅绑 `127.0.0.1` 的 `POST /api/backtest` 直接跑 export）。

## Trigger Words

- 中文：「回测 X」「对 X 做交易模拟」「复盘 X 的决策对不对」「用真实收益反思 X」「把 X 的教训写进记忆」「记忆功能 A」
- 英文：backtest X / trading simulation X / reflect on X's past decisions / close the memory loop

## Scope（M1 边界）

- **仅 A 股**：代码 `^\d{6}$`。非 A 股 → 告知推后并停止。
- **输入 = 已有 snapshot**：`Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-*.json`（由 `stock-analysis` 产出）。**本 skill 不产生新分析、不跑 propagate**。无 snapshot → 提示先跑 `stock-analysis`。
- **只反思 买/卖 决策**：`持有` 默认跳过（收益≈0 对反思价值低）；解析回退指纹 `持有/0.5/0.5` 跳过。`--include-hold` 可改。
- **horizon = 交易日**：默认 `5,20`。前向价格不足（评估日在未来）/ 长停牌 → 标 `non_evaluable` 跳过，**不杜撰收益**。
- **两种模式**：`--mode reflect`（算真实收益 + 写 5 桶记忆，机器产物 `raw/data/backtests/cn/<ticker>-<runid>/{trades.jsonl,config.json}`）；`--mode export`（**读回**已写教训 + 重算收益 → `raw/data/.../ {trades.json,lessons.json,config.json}` + **前端可读报告** `raw/analysis/backtests/cn/<ticker>-<runid>.md`）。
- **前端单元已落地**：「回测 / 记忆环」挂在个股详情，与「研究报告输出 / wiki」并列，渲染反思表 + 5 桶教训卡；浏览器**一键生成**经 serve.sh 仅绑 `127.0.0.1` 的 `POST /api/backtest` 跑 export。**仍后续**：wiki/reports 编译 + ontology Backtest 节点（见不做清单）。

## Guardrails（硬红线）

1. **DashScope 仅做 Embedding**：reflect 的 5×quick-LLM 走 anthropic/claude-max-proxy:5678；嵌入走 dashscope(text-embedding-v4)。**绝不让 DashScope 触碰 LLM 对话**，计费独立。
2. **探活防写垃圾**：DashScope 欠费/缺 key 时 `get_embedding` 返回零向量、写入永远召不回。运行器在 reflect 前**强制探活**，零向量直接退出（exit 2）——不要绕过。
3. **禁止杜撰收益**：收益只用 Tushare 真实 qfq close 算；目标价是引擎可能编造的（`_smart_price_estimation`），**绝不用 target_price 当收益**。前向不足/停牌 → `non_evaluable`，不猜。
4. **幂等防污染**：`add_situations` append-only 无去重；运行器用 `<persist_dir>/reflect-ledger.jsonl` 记 `(ticker,date,horizon)` 防重复写。**首次/调试务必用 temp `--memory-persist-dir`**，验证通过再对正式库 `Knowledge_Wiki/.kb-vectors/ta-memory` 跑。
5. **记忆配置必须与功能 B 逐项一致**：同 persist dir、`memory_namespace=ticker`、`text-embedding-v4`。错配 → B 查到空集合，环断。
6. **proxy 预检**：reflect 经 :5678 调 Claude，离线/401 会整批失败。运行前探活（见下）。

## 路径约定（本 skill 在项目根 `.claude/skills/`）

运行时 CWD = `Finance_Agent` 项目根。

- 知识库读写加 `Knowledge_Wiki/` 前缀；snapshot 输入 `Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-*.json`；机器产物 `Knowledge_Wiki/raw/data/backtests/cn/<ticker>-<runid>/`；前端可读报告 `Knowledge_Wiki/raw/analysis/backtests/cn/<ticker>-<runid>.md`（export 默认 `--report-dir`）。
- 自带脚本 `.claude/skills/backtest-analysis/scripts/run_backtest.py`。
- 引擎用自带 venv `TradingAgents-CN/.venv/bin/python`（Py3.10），**不是** uv 3.12。
- 记忆持久化目录默认 `Knowledge_Wiki/.kb-vectors/ta-memory`（gitignored，skill 内部态）。

## Workflow

### Step 1: Scope

1. 提取 6 位 A 股代码；校验 `^\d{6}$`，非 A 股停止。
2. 确认 horizon（默认 5,20 交易日）。
3. `ls Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-*.json` 确认有 snapshot；没有 → 提示先 `stock-analysis`。
4. **决定 persist dir**：首次/验证用 temp（如 `/tmp/bt-verify-mem`）；确认无误再用正式 `Knowledge_Wiki/.kb-vectors/ta-memory`（默认）。

### Step 2: 预检（proxy + 时间现实）

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/   # 任意码=在线(404正常)；空=离线
# 离线 → 后台自启：cd Third_Party/claude-max-proxy && .venv/bin/python proxy.py >/dev/null 2>&1 &
```

- **401 / AuthenticationError** = Claude Max OAuth token 过期（高频坑）。`claude --print` 自动刷新常失效，需**用户**重新授权（终端跑 `claude` → `/login`；若 shell 设了 `ANTHROPIC_API_KEY` 短路 OAuth，先 `unset`）。Agent 不读凭证明文。
- **时间现实**：snapshot 日期 + horizon 若落在未来则取不到价格（`non_evaluable`）。要验证 A 闭环机制而非真实收益时，用 `--force-return "<串>"` 合成收益（跳过价格层）。

### Step 3: 跑反思（功能 A 写入）

```bash
TradingAgents-CN/.venv/bin/python .claude/skills/backtest-analysis/scripts/run_backtest.py \
  --ticker <ticker> --mode reflect --horizons 5,20 \
  --out Knowledge_Wiki/raw/data/backtests/cn/<ticker>-<runid> \
  --ta-root TradingAgents-CN
# 验证/首跑加：--memory-persist-dir /tmp/bt-verify-mem
# 价格层干跑(不写记忆)：--no-reflect ；干跑不调LLM：--dry-run
```

运行器自动：env preamble（Mongo/Redis off + persist dir + chdir + dotenv）→ 拉一次宽区间价格 → 建图(memory_enabled) → **DashScope 探活** → 逐 (snapshot,horizon) 算签名收益 + 重建 curr_state + `reflect_and_remember` → 写 trades.jsonl + config.json + ledger。

成功 stdout：`OK ticker=... reflected=N skipped=M trades=K out=...`。

### Step 4: 验证写入（跨进程读回，推荐首跑必做）

新进程对同一 persist dir / namespace 调 `get_memories` 确认命中（仿功能 B 验证）：

```bash
TradingAgents-CN/.venv/bin/python <verify 脚本> <ticker> <persist_dir> <snapshot.json>
# 期望：5/5 桶 count>0，原situation 查询高相似 + 取回教训文本；DashScope 嵌入非零
```

### Step 5: 导出前端可读报告（`--mode export`）

reflect 把教训写进了 ChromaDB（前端读不到）。export **只读**把它取回来 + 重算收益 → 落前端报告。**不重跑引擎、不重写桶、不调 LLM**（用 chromadb exact-match 读桶 + Tushare 算价，几秒）。

```bash
TradingAgents-CN/.venv/bin/python .claude/skills/backtest-analysis/scripts/run_backtest.py \
  --ticker <ticker> --mode export --ta-root TradingAgents-CN
# 默认产物 raw/data/backtests/cn/<ticker>-<runid>/{trades.json,lessons.json,config.json}
#       报告 raw/analysis/backtests/cn/<ticker>-<runid>.md（type: backtest-report）
```

- 导出按**台账**（reflect-ledger.jsonl）里已反思的 `(date,horizon)` 重算收益 + 读回 5 桶教训；exact-match situation 命中即 `matched`，否则取桶内最新一条。
- 报告 `.md` = flat frontmatter（type/ticker/mode/run_status/snapshot_date/horizons/headline_return_pct/sources）+ 正文 `<!-- backtest-json -->` json 块（trades + 精简 lessons）。**数组进不了 mini-YAML，故放 json 块**。
- 成功 stdout：`OK ticker=... mode=export reflected=N non_eval=M lessons=K/5 headline=±%`。

### Step 6: 前端展示 / 一键生成

- **展示**：前端「回测 / 记忆环」单元自动 live-parse `raw/analysis/backtests/**/*.md`（serve.sh 的 `/manifest.json` **动态实时 glob**，新报告刷新即见，无需重跑脚本）。
- **一键生成**：浏览器单元里点「⟳ 生成 / 刷新回测报告」→ `POST /api/backtest {ticker}` → serve.sh（**仅绑 127.0.0.1**）跑上面的 export → 重载 KB 停在回测页。ticker 严格校验 `^\d{6}$`、subprocess 参数数组不走 shell。
- 回报用户：reflected N 条教训已写入 `<ticker>` 记忆桶；次日同票 `stock-analysis`（depth≥2）自动召回；前端「回测 / 记忆环」可看反思表 + 5 桶教训。

## 不做清单（明确推后）

- ❌ 港股 / 美股（→ 后续）
- ❌ M2 前向组合模拟前端（引擎层 `--mode simulate` 已实现：净值曲线 + 指标 + reflect-on-close；前端面板待接）
- ❌ M3 历史 walk-forward 重跑（前瞻偏差，仅演示，需显式确认 + 标注）
- ❌ wiki/reports 编译 + ontology Backtest 节点（经 raw-intake → finance-ingest，后续）
- ❌ 直写 wiki（须经 raw-intake → finance-ingest）
- ❌ 用 DashScope 跑对话 LLM（仅 Embedding）

## References

- [docs/tradingagents-cn/backtest/backtest-feature-design.md](../../../docs/tradingagents-cn/backtest/backtest-feature-design.md) — 完整设计、API、坑位、存储布局、分阶段。
- [docs/tradingagents-cn/backtest/backtest-feature-framework.html](../../../docs/tradingagents-cn/backtest/backtest-feature-framework.html) — 可视化技术框架图（含 M1 流程 + M2 设计）。
- [docs/tradingagents-cn/backtest/backtest-frontend-demo.html](../../../docs/tradingagents-cn/backtest/backtest-frontend-demo.html) — 前端「回测 / 记忆环」单元设计（M1 实证版）。
- 前端接线：`frontend/index.html`（`renderBacktest()` + `genBacktest()`）、`frontend/kb-parse.js`（backtest-report 解析分支）、`frontend/serve.sh`（动态 manifest + `POST /api/backtest`）。
- [../stock-analysis/references/depth-config.md](../stock-analysis/references/depth-config.md) §1b — 连续记忆功能 B（A 的读半边）+ 记忆 flag 对齐。
