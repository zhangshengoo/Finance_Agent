# 回测 + 交易模拟 + 记忆功能 A — 设计方案

> 状态：**M1 前端单元已端到端落地并实证（2026-06-16）**；M2 引擎已实现、前端待接。代码 `.claude/skills/backtest-analysis/`（run_backtest.py + SKILL.md）+ `frontend/`（index.html / kb-parse.js / serve.sh）。基于对 TradingAgents-CN 引擎、本项目 stock-analysis skill/runner、Knowledge_Wiki、frontend 四个子系统的逐文件调研。
> 目标读者：实现者（含未来的自己）。
>
> **实现状态**：
> - ✅ **M1 单决策反思**：价格层(Tushare 真实数据) + curr_state 重建 + 原生 reflect_and_remember + trades.jsonl + 幂等台账。验证：reflect 写→跨进程读回 5/5 桶 sim=1.000。
> - ✅ **M1 导出 `--mode export`（2026-06-16 新增）**：reflect 把教训写进 ChromaDB 后**只读回读**（chromadb exact-match situation，零 embedding/零 LLM）+ Tushare 重算收益 → 落机器产物 `raw/data/backtests/cn/.../ {trades.json,lessons.json,config.json}` + 前端可读报告 `raw/analysis/backtests/cn/<ticker>-<runid>.md`（`type: backtest-report`，flat frontmatter + 正文 `<!-- backtest-json -->` 块）。**M1 内容全部走现有链路生成，不另起生成。**
> - ✅ **前端「回测 / 记忆环」单元（2026-06-16 落地）**：挂个股详情，与「研究报告输出 / wiki」并列同一套 md 解析（`kb-parse.js` backtest-report 分支 → `companies[].backtests[]`；`index.html renderBacktest()` 反思表 + 5 桶教训卡，配色对齐 `eqVCol`）。
> - ✅ **浏览器一键生成（2026-06-16）**：`serve.sh` 改为 **仅绑 127.0.0.1** + no-store + **动态 `/manifest.json`**（实时 glob，新报告刷新即见）+ **`POST /api/backtest {ticker}`**（ticker 校验 `^\d{6}$`、subprocess 参数数组不走 shell、跑 export）。前端「⟳ 生成 / 刷新回测报告」按钮 → `genBacktest()` → 重载 KB 停在回测页。**实证：601899 06-10 买入持 3 日 +13.03%（@27.70→@31.31, Tushare qfq）→ 5/5 桶教训读回 → 前端渲染。**
> - ✅ **M2 前向组合模拟（引擎层）**：组合状态机(现金/持仓/T+1/加权成本/费率) + 每日 mark-to-market 净值曲线 + 指标(总收益/CAGR/Sharpe/maxDD/胜率) + **平仓时真实持有期收益 reflect-on-close**。验证：账目逐笔核对正确，reflect-on-close 600519 +1.02% → 5/5 桶 sim=1.000。**前端面板待接（M2 净值曲线/指标尚未 renderBacktest）。**
> - ✅ **嵌入超长修复**（见 §11，关键）：发现并修复一个静默拖垮功能 A/B 的零向量 bug。
> - ⏳ **仍待实现**：M2 前端面板（净值曲线 + 指标）；raw-intake 溯源 ledger handoff（当前 export 由 runner 直写 raw/analysis）；finance-ingest→wiki/reports + ontology Backtest 节点编译。
> - §10 的两个分叉决策已确认（M1 优先）；前端触发选定 **Option B 轻量版**（127.0.0.1 端点直跑 export，非 SSE——因 export 只需数秒），经用户显式确认后实现。

---

## 1. 目标与定位

把已经落地的"连续记忆功能 B（读半边）"补全成完整记忆环，并围绕个股分析做**交易模拟 / 回测**，前端可视化并（可选）支持从浏览器一键触发。

三件事，一条主线：

1. **引入功能 A（记忆写半边）**——用真实盈亏调引擎原生 `reflect_and_remember`，把"带收益的历史教训"写进 per-ticker 记忆桶；功能 B 次日分析同一标的时自动召回。**A 是本方案的内核**。
2. **交易模拟 / 回测**——以个股分析产出的决策（买入/持有/卖出）为信号，模拟持仓、算实现收益、出净值曲线与指标。
3. **前端展示 + 交互触发**——新增回测面板（净值曲线 / 成交 / 指标 / 记忆教训），并可选地从浏览器调用 Claude Code 跑 Agent。

**一句话架构定位**：A 是"决策 → 真实收益 → 写教训 → 下次召回"的闭环；回测是"在历史/未来上批量产生决策并度量收益"的引擎；前端是只读渲染 + 触发器。三者复用 TradingAgents-CN 原生设施，**不另起记忆/回测系统**。

---

## 2. 关键事实（调研结论，决定一切设计）

### 2.1 功能 A 的原生入口已存在、且休眠

- `TradingAgentsGraph.reflect_and_remember(returns_losses)` — `trading_graph.py:1165`。读 `self.curr_state`，对 5 个组件各发 **1 次 quick-LLM 调用**（共 5 次），把 `(situation, lesson)` 写进 5 个记忆桶。
- 全仓库**唯一引用是 `main.py:26` 的一行注释** `# ta.reflect_and_remember(1000)` → 证明写半边从未被调用，正是"沉睡的另一半"。
- `returns_losses` **无类型**，仅被 f-string 插进 prompt（`Returns: {returns_losses}`），代码从不解析/比较——"决策对不对"由 LLM 按 system prompt 判断。可传 `float`（如 `0.087` / `-0.12`）或带符号的短串（如 `"realized +8.7% over 5 trading days (BUY)"`）。
- `Reflector(quick_thinking_llm)` 与 `FinancialSituationMemory(name, config)` **都可独立构造**，不需要跑 propagate。所以 A 有两条实现路径：
  - **Path A（推荐）**：照 runner 建一个 `TradingAgentsGraph(config, memory_enabled=True)`，手动 `ta.curr_state = <重建的扁平 dict>`，调 `ta.reflect_and_remember(ret)`。最省心，完全走原生。
  - **Path B（更轻）**：直接 `Reflector(quick_llm)` + 5 个 `FinancialSituationMemory`，逐个 `reflect_*`。少建图，但要自己拼 5 个 mem。

### 2.2 reflect 读的就是 8 个字段（其余 AgentState 无关）

`_extract_current_situation` + 5 个 `reflect_*` **硬下标**访问（缺键直接 KeyError），重建 `curr_state` 只需：

```
market_report, sentiment_report, news_report, fundamentals_report,   # 4 份分析报告
trader_investment_plan,                                               # 交易员计划
investment_debate_state.{bull_history, bear_history, judge_decision}, # 多空辩论
risk_debate_state.judge_decision                                     # 风险裁决
```

**snapshot → curr_state 映射（注意 key 改名 + None 要变 ''）：**

| snapshot 路径 | curr_state 扁平键 |
|---|---|
| `reports.market` | `market_report` |
| `reports.sentiment` | `sentiment_report` |
| `reports.news` | `news_report` |
| `reports.fundamentals` | `fundamentals_report` |
| `reports.trader_investment_plan` | `trader_investment_plan` |
| `debates.investment.bull_history` | `investment_debate_state.bull_history` |
| `debates.investment.bear_history` | `investment_debate_state.bear_history` |
| `debates.investment.judge_decision` | `investment_debate_state.judge_decision` |
| `debates.risk.judge_decision` | `risk_debate_state.judge_decision` |

> snapshot 里未选分析师的报告是 `null`（如 600519 的 news/sentiment）。**必须保留键、把 None 强制成 `''`**，否则 reflect 的 f-string 嵌入会退化 / KeyError。

### 2.3 真实收益怎么算（A 股价格源）

- `get_tushare_provider()`（singleton，已连）→ `await provider.get_historical_data(symbol, start, end)`，返回 **qfq 前复权** DataFrame，`close` 列、`date` 为升序 DatetimeIndex。`收益 = (close[eval] - close[decision]) / close[decision]`。
- **是 async**：用 `loop.run_until_complete(...)` 包成同步（仓库一贯做法）。空/错返回 `None`，要判空。
- **坑**：无交易日历（仓库从不调 `trade_cal`）；停牌当天 DataFrame **直接没有该行**（`df.loc[date]` 会 KeyError，不是 NaN）；涨跌停对 close-to-close 收益可接受但要知道会被截断。→ **取一段区间** `[decision-buffer, eval+buffer]` 一次拉回，用 `index.asof` 贴到最近交易日；长停牌超过 max-gap 就标记该决策"不可评估"。
- `decision.target_price` 可能是引擎**编造**的（`_smart_price_estimation`，如 current×1.15）——**收益只用真实 close，绝不用 target_price**。

### 2.4 snapshot 是回测的完整输入

- 路径 `Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-<date>.json`，schema `stock-analysis-runner/v1`。含全部 4 报告 + 两个辩论 state + 交易员计划 + `decision{action(中文买入/持有/卖出), target_price, confidence, risk_score}`。**重建 curr_state 跑 reflect 所需的一切都在里面，无需重跑引擎。**
- **现状：每只票只有 1 个 snapshot、单日**（600519@06-08、601899@06-10、688981@06-09），**没有任何单票的多日序列**。→ 真正的"序列回测"必须自己产生决策序列。
- snapshot 里**没有价格数据**（价格只在报告正文里），收益要独立从 Tushare 取。
- `action=持有 且 confidence==0.5 且 risk_score==0.5` 是解析失败回退的指纹，回测应视为可疑。

### 2.5 记忆桶对齐（A 写的桶必须 = B 读的桶）

A 的 config 必须和功能 B **逐项一致**，否则 B 查到的是另一个/空集合，环就断了：

- 持久化目录：`Knowledge_Wiki/.kb-vectors/ta-memory`（env `TRADINGAGENTS_MEMORY_PERSIST_DIR`，**import 引擎前**设好，singleton 一次定生死）。
- `memory_namespace = ticker` → 桶名 `bull_memory__<ticker>` 等。
- `memory_llm_provider = dashscope` + `memory_embedding_model = text-embedding-v4`（1024 维）。**A 写、B 读必须同一嵌入模型**，否则余弦相似度无意义。
- `memory_enabled = True`（gates 建桶）。depth1 历史 snapshot 当时没建桶，但 reflect 在建图时实例化 mem，所以 A 重新建图开 memory 即可写。
- **硬约束（贯穿全项目）：DashScope 仅做 Embedding，绝不碰 LLM 对话**。reflect 的 5 次 quick-LLM 走 anthropic / claude-max-proxy:5678；embedding 走 dashscope。计费独立。
- **静默写垃圾风险**：DASHSCOPE_API_KEY 缺失/欠费时 `get_embedding` 返回 1024 维零向量，`add_situations` 仍"成功"但该行**永远召不回**。A 跑完必须验证 DashScope 真活着。
- **幂等**：`add_situations` append-only、`ids=str(count+i)`、**无去重**。重跑同一 snapshot 会写重复行。→ 维护 sidecar 台账记录已 reflect 的 `(ticker, snapshot-date, horizon)`。

### 2.6 ⚠️ 方法论关键：重跑历史 = 前瞻偏差（lookahead bias）

引擎 `online_tools=True`，news/sentiment 分析师抓的是**当前**新闻/东财人气/微博情绪。让它分析某只票"as of 2025-01-01"时，价格能按日期约束，但**舆情类数据会泄漏未来**。所以**在过去日期上重跑引擎来造决策序列，方法论上不成立**（它"知道"后来发生了什么）。

这直接决定了回测语义的取舍（见 §4）：真正干净的是**前向纸面交易（forward paper-test）**，从今天起按节奏跑、累积真实样本外决策序列；而"重跑古早历史"只能当近似演示并显式标注。

### 2.7 KB 存储规约（落盘必须守的不变量）

- `raw/` 不可变、被 `build_index.py` SKIP（不校验 frontmatter）。机器产物（成交、净值、config）放 `raw/data/`；重跑 = 新 runid 新文件，绝不覆盖。
- 分析类 skill **绝不直接写 `wiki/`**：走 `analysis → raw-intake（落 raw/ + 溯源 ledger）→ finance-ingest（两步 CoT）→ wiki/`。回测 skill 属"分析/产出"角色 → 放**项目根 `.claude/skills/`**，不放 `Knowledge_Wiki/.claude/skills/`。
- 前端 frontmatter 解析器是 stdlib mini-YAML：**嵌套 dict 会退化成字符串**。净值曲线 / 成交（array-of-objects）**不能放 YAML**，要放正文 JSON 块或 sibling `.json`。
- ontology 只经 `graph_append.py`：建 1 个 `Backtest` 节点 + `EVALUATES/COVERS` 边；**绝不给每笔成交/每个净值点建节点**；新节点/边类型要先登记 `ontology/schema.yaml`。
- 永不编造：每个 Sharpe/CAGR/回撤都要能经 `sources[]` 追到 raw JSON；引擎没产出的 = `null` / `[UNSOURCED]`。

### 2.8 前端现状（决定怎么接面板）

- 纯 vanilla JS 单文件 `frontend/index.html`（无框架/无构建）。`data.json`/`build_dist.py`/`dist/` 已删（commit 08d3f1f）→ **live-parse**：`serve.sh` 生成 `manifest.json`（文件清单）→ 浏览器逐个 fetch → `kb-parse.js` 现场解析成 KB 对象。
- **必须 serve.sh 起本地服务**（`file://` 被浏览器 block），fetch 前缀硬编码 `/Knowledge_Wiki/`，从项目根 serve。
- `serve.sh` 是 **GET-only 静态服务器**（`python3 -m http.server`），**物理上不能收 POST**。一键触发 = 新组件。
- "个股分析 / equity"页签是现成范本：决策 pill、信心/风险表盘、provenance、fact/judgment 分层、多 run `<select>`、"研究报告 ⇄ wiki"切换。回测面板照抄此结构。
- 已有 `prototype-stock-analysis.html` 静态 mockup 作为设计源——回测也先做 `prototype-backtest.html` 再 wire。
- **本地 only 是硬不变量**（memory `feedback_finance_kb_local_only`）：KB/前端绝不公网，外发前必停下确认。**禁止从浏览器读 `.kb-vectors`**（skill 内部态）——记忆教训只能由回测 runner 导出成 KB 文件再被前端读。

### 2.9 从浏览器调用 Claude Code（无头）

- `claude -p "<prompt>" --output-format stream-json --permission-mode dontAsk --allowedTools 'Bash(...)' 'Read' 'Write'` → 输出 NDJSON，可经 SSE 实时转发给浏览器。
- **Skill 不能当参数直接调**（`claude -p 'run /stock-analysis'` 无效）：要在 prompt 里描述任务让模型自己触发 skill；SDK 可 `skills=['backtest-analysis']` 白名单 + 措辞引导。
- headless **不会弹权限**：没预批的工具会**卡死等 stdin**。必须 `--permission-mode dontAsk` + 显式 `--allowedTools`。
- `--dangerously-skip-permissions` **不是沙箱**，不防 `rm -rf`，本机别用；用 dontAsk + 白名单收敛。
- 鉴权用当前用户 `~/.claude`（Claude 订阅），不需要把 key 给前端。
- 长任务（~17min）+ SSE ~30s idle 超时 → 每 10s 发心跳/进度；并发要排队串行（token/内存）。

---

## 3. 三种回测语义（按成本与方法论严谨度分层）

| 模式 | 做什么 | 引擎重跑？ | 成本 | 方法论 | 定位 |
|---|---|---|---|---|---|
| **M1 单决策反思（lesson-write）** | 对已有 snapshot 决策，从 Tushare 取前向收益，模拟这一笔，调 reflect 写教训 | ❌ | 极低（5 次 quick-LLM + 1 次 Tushare/决策） | 干净（决策是当时真做的，只是事后量收益） | **A 的最小闭环，立即可交付** |
| **M2 前向纸面交易（forward paper-test）** | 从今天起按节奏（周/月）跑分析，累积真实样本外决策序列，模拟组合净值，收益兑现后 reflect | ✅（向前，按节奏） | 中（受节奏×标的数约束） | 干净（真·样本外） | **真正的"交易模拟"，持续喂 A** |
| **M3 历史 walk-forward 重跑** | 在过去日期上重跑引擎造决策序列，模拟组合 | ✅（×N 历史日期） | 极高（17min×N×M） | ⚠️ 前瞻偏差（§2.6） | 仅近似演示，需关 online_tools + 点时数据，否则只能标注"含未来泄漏" |

**推荐落地顺序：M1 先行（内核 A）→ M2 持续积累（真回测）→ M3 仅在显式确认 + 加偏差标注后做。**

---

## 4. 架构总览

```
                ┌─────────────────────────────────────────────────────────────┐
                │                    个股分析 (已存在)                          │
                │  stock-analysis skill → run_stock_analysis.py → 引擎 propagate │
                │  产出 snapshot: raw/data/stock-snapshots/cn/<ticker>-<date>.json│
                └───────────────────────────┬─────────────────────────────────┘
                                            │ 决策 + 4报告 + 辩论 state
                                            ▼
   ┌────────────────────────────  回测 / 交易模拟 (新增)  ────────────────────────────┐
   │                                                                                 │
   │  run_backtest.py  (项目根 .claude/skills/backtest-analysis/scripts/)             │
   │   ├─ 复用 runner 的 env preamble (Mongo/Redis off, persist dir, chdir, dotenv)   │
   │   ├─ 价格层: get_tushare_provider().get_historical_data → 前向真实收益            │
   │   ├─ 组合模拟: 复用 paper.py 的 PnL 公式 (realized=(price-avg_cost)*qty, T+1)     │
   │   ├─ 功能 A: 重建 curr_state → ta.reflect_and_remember(signed_return)            │
   │   │          写入 bull_memory__<ticker> 等 (= 功能 B 读的桶)                      │
   │   └─ 幂等台账: 记录已 reflect 的 (ticker,date,horizon)                            │
   │                                                                                 │
   └───────────────┬───────────────────────────────────────────┬─────────────────┘
                  │ 机器产物                                    │ 记忆写入
                  ▼                                            ▼
   raw/data/backtests/<market>/<id>/{config.json,             .kb-vectors/ta-memory/
     trades.jsonl, equity_curve.json}   (不可变)               (ChromaDB, gitignored)
                  │                                            ▲
                  │ raw-intake (envelope + ledger 溯源)          │ 功能 B 次日 get_memories 召回
                  ▼                                            │
   raw/analysis/backtests/<id>.md (type: backtest-report)  ───┘
                  │ finance-ingest (两步 CoT)
                  ▼
   wiki/reports/<date>-backtest.md (type: report, frontmatter+sources[])
   ontology: 1×Backtest 节点 + EVALUATES/COVERS 边 (graph_append.py)
                  │
                  ▼
   ┌─────────────────────────  前端 (frontend, live-parse, local-only)  ─────────────┐
   │  serve.sh manifest 加 raw/analysis/backtests/*.md                                │
   │  kb-parse.js 加 parser 分支 → companies[].backtests[]                            │
   │  index.html 加 renderBacktest(): SVG 净值曲线 + 成交表 + 指标卡 + 记忆教训卡       │
   │  交互触发: (A) 复制命令 [默认] / (B) 127.0.0.1 SSE bridge → claude -p [需确认]    │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 组件设计

### 5.1 `run_backtest.py`（功能 A 驱动 + 收益 + 模拟）

**位置**：`.claude/skills/backtest-analysis/scripts/run_backtest.py`（项目根 skill）。

**复用而非重写 runner 主体**：把 `run_stock_analysis.py:162-212` 的 env/config preamble 抽成共享 helper（或先 copy 一份），保证：

```python
# import tradingagents 之前
os.environ["MONGODB_ENABLED"] = os.environ["REDIS_ENABLED"] = os.environ["USE_MONGODB_STORAGE"] = "false"
os.environ["TRADINGAGENTS_MEMORY_PERSIST_DIR"] = <persist_dir>     # = 功能B同一目录
os.chdir(ta_root); sys.path.insert(0, ta_root); load_dotenv(ta_root/".env", override=False)
# config
config["memory_enabled"] = True
config["memory_namespace"] = ticker
config["memory_llm_provider"] = "dashscope"
config["memory_embedding_model"] = "text-embedding-v4"
config["llm_provider"] = "anthropic"; config["backend_url"] = "http://localhost:5678"
```

跑 `TradingAgents-CN/.venv/bin/python`（Py3.10），不用 uv 3.12。

**CLI（建议）**：

```
--ticker 600519              # 必填
--mode  reflect|simulate     # reflect=M1单决策, simulate=M2/M3组合
--snapshots <glob|dir>       # 默认 Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-*.json
--horizons 5,20              # 前向评估窗口(交易日)，可多个
--benchmark 000300.SH        # 沪深300，可空
--out <abs path>             # 机器产物 + 报告输出目录
--ta-root TradingAgents-CN
--memory-persist-dir / --memory-embed-* # 默认对齐功能B，常规不传
--no-reflect                 # 只算收益不写记忆(干跑/调试)
--dry-run                    # 不调LLM不写盘，打印将做什么
```

**reflect 子流程（M1 内核）**，对每个 (snapshot, horizon)：

1. 读 snapshot；若 `status==failed` 或 `decision.action==持有 且 0.5/0.5 指纹` → 跳过（标 non-evaluable）。
2. 查幂等台账，已 reflect 过 `(ticker,date,horizon)` → 跳过（除非 `--force`）。
3. 价格：`get_historical_data(ticker, date-3d, date+horizon+5d)`，贴最近交易日取 `close[entry]`、`close[exit]`；停牌/超 max-gap → 标 non-evaluable 并跳过 reflect。
4. `raw_ret = (close_exit - close_entry)/close_entry`；按动作签名：买入→`+raw_ret`，卖出→`-raw_ret`，持有→`0` 或相对基准。生成 `returns_losses` 短串（含方向+百分比+天数+动作）。
5. 重建 `curr_state`（§2.2 映射，None→''）。
6. `ta = TradingAgentsGraph(config, memory_enabled=True)`；`ta.curr_state = state`；**先探活 DashScope**（嵌入一句测试串看是否非零向量）；`ta.reflect_and_remember(returns_losses)`。
7. 追加 trades.jsonl 一行 + 幂等台账一行。

**simulate 子流程（M2/M3 组合）**：按日期序遍历决策序列，用 paper.py 公式维护 `cash / positions[{ticker,qty,avg_cost}] / equity`，买入按 confidence 定仓、T+1 可用量；每日 mark-to-market 出 `equity_curve[{date,equity,benchmark,drawdown}]`；每笔平仓的真实收益喂 reflect。指标：total_return / CAGR / Sharpe / max_drawdown / win_rate / vs_benchmark。

**输出**：stdout 一行 `OK ticker=... mode=... trades=N reflected=M elapsed=...`；机器产物写 `raw/data/backtests/...`；可读报告写 `raw/analysis/backtests/...md`（见 §5.2）。

### 5.2 KB 存储布局（守 §2.7 不变量）

```
raw/data/backtests/cn/<ticker>-<runid>/        # runid = 运行时间戳, 不可变
  config.json        # 输入: ticker, mode, horizons, benchmark, snapshots[], params
  trades.jsonl       # 一行一笔: {trade_id, ticker, side, entry_date, entry_close,
                     #            exit_date, exit_close, return_pct, holding_days,
                     #            reflected:bool, returns_losses_str, non_evaluable?}
  equity_curve.json  # M2/M3: [{date, equity, benchmark, drawdown}]  (M1 可省)
raw/analysis/backtests/cn/<ticker>-<runid>.md  # type: backtest-report (新类型)
                     # flat frontmatter atoms: cagr, sharpe, max_drawdown, win_rate,
                     #   total_return, benchmark_return, n_trades, start, end, run_status
                     # 正文: 模块栅栏 + equity_curve/trades 用 ```json 块嵌入 (数组不能进YAML)
                     # sources[]: 指回 raw/data/backtests/... + 引擎 run id
```

- 经 **raw-intake** 落盘 + 写 `raw/.intake/ledger.jsonl` 溯源（sha256）。
- **finance-ingest** 两步 CoT 编译出 `wiki/reports/<date>-<ticker>-backtest.md`（`type: report`，6 必填字段 + `sources[]`），跑 `build_index.py --validate`。
- ontology：`graph_append.py create --type Backtest --id bt-<ticker>-<runid> --props '{...}'`；`relate --from bt-... --rel COVERS --to <Company>`；若验证某 Thesis 则 `--rel EVALUATES`。**先在 `ontology/schema.yaml` 登记 `Backtest` 节点 + `EVALUATES/COVERS` 边**。绝不给每笔成交建节点。
- `backtest-report` 是新 page-type → 要加进 `_schema.md` 的 type enum + per-type 扩展字段。

### 5.3 `backtest-analysis` Skill（项目根）

`.claude/skills/backtest-analysis/SKILL.md` + `scripts/run_backtest.py` + `references/`。职责：触发回测、读机器产物、生成 ≤200 行 schema 化摘要、**handoff 给 raw-intake → finance-ingest**（不自己写 wiki）。trigger 短语写进 description（"回测""交易模拟""backtest"）。可配一个 `backtest-analyst-cn` subagent（仿 `stock-analyst-cn`）跑无头 runner、轮询、读文件。

---

## 6. 前端设计

### 6.1 回测面板（复用 equity 页签结构）

- **首选做成 equity detail 的第 3 个子视图**（与"研究报告 / wiki"切换并列），因为回测天然是 per-ticker，run-selector + report_status badge UI 已现成（`index.html:1073-1099`）。也可做独立 `<section id="v-backtest">` + nav 项 + `renderBacktest()` 加进 `boot()`。
- **净值曲线无需库**：照抄已有手绘 SVG（constellation，`index.html:498`，viewBox 0 0 980 520），`<polyline>` 画 `equity_curve[{date,value}]`，基准叠加，复用 CSS 变量 `--accent`（曲线）/`--c-company`（基准）/`--warn`（回撤带）。
- **指标卡**：复用 `inst(lab,val,sub,accent)`（`index.html:625`）做 `.instruments` 网格：总收益 / CAGR / Sharpe / 最大回撤 / 胜率 / vs 基准。
- **成交表**：复用 `mdHtml()` GFM 表 或简单列表，买=红 / 卖=绿 / 持有=灰 pill（对齐 `EQ_VCLS/eqVCol`，`index.html:892`）。
- **记忆教训卡**：渲染在已有 fact/judgment 分层下（`renderAnalysisBody` 的 ⚠ "模型判断非事实" banner，`index.html:1051`）。每条 `{bucket, outcome_pnl, lesson_text}` 按桶配色。**教训由 runner 导出进 KB 文件**（绝不从浏览器读 `.kb-vectors`）。
- **诚实标注**：复用 `sample/partial/ok` badge——没真跑的回测渲染成 `report_status: sample` 占位，绝不编造净值曲线。

### 6.2 数据通路

- `serve.sh` 的 manifest globber（`serve.sh:24-35`）加 `raw/analysis/backtests/**/*.md`。
- `kb-parse.js` 加 parser 分支（仿 `reportsByTicker` `L266-306`）→ `companies[].backtests[]`。
- `docs/kb/frontend-kb-binding.md` 加 **§2c 回测契约**：flat frontmatter 指标 atoms + 正文 `json` 块装 `equity_curve`/`trades`（array-of-objects 进不了 mini-YAML）。
- 加新文件后 **重跑 serve.sh** 刷新 manifest（manifest 是启动时快照，只有文件内容是 live）。
- 先做 `prototype-backtest.html` 静态 mockup 定布局，再 wire 进 `renderBacktest()`/`kbParse`。

### 6.3 交互触发（调用 Claude Code）— 两选项

**Option A — 复制命令（默认，零新增攻击面）**
面板按钮把预填好的命令（ticker/horizons/period）拷到剪贴板，用户粘进 Claude Code → 触发 `backtest-analysis` skill → 无头跑 runner → 写 `raw/analysis/backtests/*` → 刷新浏览器即见（内容 live-parse；若是新文件则重跑 serve.sh）。**契合现有"Agent 写 KB、前端渲染 KB"架构，无需任何新服务。**

**Option B — 127.0.0.1 SSE 桥（真·一键，需显式确认后才建）**
独立小服务 `frontend/bridge.py`（`BaseHTTPRequestHandler` 或 aiohttp），**仅绑 `127.0.0.1`**：

```
POST /backtest {ticker, horizons, mode}   →  spawn:
  claude -p "<触发 backtest-analysis 的措辞>" \
     --output-format stream-json --permission-mode dontAsk \
     --allowedTools 'Bash(...venv/bin/python ...run_backtest.py*)' 'Read' 'Write'
  → 把 NDJSON 逐行经 SSE (text/event-stream) 转发给浏览器
  → 每 10s 发心跳; 任务串行排队; 完成发 result 事件
```

安全要点：绑 loopback（`curl http://<hostname>:8000` 必须失败）；`dontAsk`+白名单收敛工具；不暴露任何 key 给前端 JS；长任务 async + 进度条吃 SSE。**这是新网络组件——按 `feedback_finance_kb_local_only`，建之前必须停下来跟你确认。**

> 默认走 A；B 作为可选增强，且仅在你确认后实现。

---

## 7. 不变量合规清单

| 不变量 | 本方案怎么守 |
|---|---|
| 本地 only，绝不公网 | 前端 serve.sh / 桥仅绑 127.0.0.1；外发前停确认 |
| raw/ 不可变 | 回测产物写 raw/data + raw/analysis，重跑=新 runid，绝不覆盖 |
| 不直接写 wiki/ | analysis→raw-intake→finance-ingest→wiki/reports |
| ontology 只经 graph_append.py | 1×Backtest 节点 + 边；先登记 schema.yaml；不给成交建节点 |
| 永不编造 | 指标全部 sources[] 可溯；缺=null/[UNSOURCED]；sample badge |
| DashScope 仅 Embedding | reflect 的 5 次 quick-LLM 走 anthropic:5678；嵌入走 dashscope；跑前探活防零向量 |
| 引擎重跑很贵 | M1 不重跑；M2 节奏化；M3 显式确认；优先 run_in_background 轮询 |
| 不碰 .kb-vectors（前端） | 记忆教训由 runner 导出进 KB 文件再渲染 |
| 幂等 | sidecar 台账记 (ticker,date,horizon)，防重复写记忆 |

---

## 8. 分阶段落地计划

- **P0 — 价格层 + 收益（无 LLM、可独立验证）**：Tushare 同步 wrapper + 交易日贴齐 + 停牌守卫；对现有 3 个 snapshot 算前向收益打印。**产出**：`returns` 工具 + 单测式验证脚本。零引擎成本。
- **P1 — 功能 A（M1 内核）**：`run_backtest.py --mode reflect`，重建 curr_state + DashScope 探活 + `reflect_and_remember` + trades.jsonl + 幂等台账。**用 temp persist dir 验证**写→读命中（仿功能 B 验证），确认不污染正式记忆库。**产出**：记忆环闭合，A 落地。
- **P2 — KB 落盘 + 报告**：raw/data/backtests 布局 + raw-intake handoff + backtest-report 类型 + finance-ingest → wiki/reports + ontology 节点。跑 `build_index.py --validate`。
- **P3 — 前端面板**：`prototype-backtest.html` → `renderBacktest()` + kb-parse 分支 + serve.sh manifest + binding §2c。Option A 复制命令交互。
- **P4 — 组合模拟（M2 前向）**：simulate 子流程 + 净值曲线 + 指标；按节奏积累样本外序列。
- **P5（可选，需确认）**：127.0.0.1 SSE 桥一键触发；M3 历史重跑（加前瞻偏差标注）。

每阶段独立可交付、可验证；P0/P1 不依赖前端，P3 不依赖 P4。

---

## 9. 风险与开放问题

1. **前瞻偏差（§2.6）**——M3 重跑历史不严谨。**缓解**：主推 M1（事后量收益）+ M2（前向样本外）；M3 仅演示且标注。
2. **持有(HOLD)收益怎么记**——0 收益对 reflect 价值低。**选项**：相对基准的超额、或干脆只 reflect 买/卖决策。需你定调。
3. **horizon 选择**——5 日/20 日/到下一次决策？影响"教训"的含义。建议多 horizon 并存、各写一条带天数的教训。
4. **claude-max-proxy token 过期**（memory `project_claude_max_proxy_ops`）——reflect 的 quick-LLM 走 :5678，401 会让整批失败。**缓解**：跑前 curl 探活 + 批前小样验证。
5. **Tushare 限频/积分**——批量多票多日会撞每分钟上限。**缓解**：每票一次宽区间拉取 + 24h 缓存 + 退避。
6. **记忆库污染**——回测误写正式 `.kb-vectors/ta-memory` 难回滚（append-only）。**缓解**：P1 用 temp dir 验证；正式跑加 `--dry-run` 预演 + 幂等台账。

---

## 10. 需要你拍板的两个决策（落地前）

**决策一：首期回测语义范围**
- (推荐) 先做 **M1 单决策反思** —— 最便宜、立刻闭合功能 A，复用现有 snapshot，无引擎重跑。之后再上 M2 前向组合。
- 直接做 **M1 + M2 前向纸面交易** —— 含组合净值曲线，但要按节奏持续跑、周期更长。
- 加 **M3 历史重跑** —— 有完整历史净值但贵且有前瞻偏差（需接受标注）。

**决策二：前端交互触发方式**
- (推荐) **Option A 复制命令** —— 零新增服务/攻击面，契合现架构。
- **Option B 127.0.0.1 SSE 桥** —— 真一键，但是新网络组件，按本地 only 不变量需你显式批准后才建。

> 此外 §9 的"HOLD 怎么记""horizon 取值"两个小问题也欢迎你定调；不定则按推荐默认（只 reflect 买/卖 + 多 horizon）。

---

## 11. 嵌入超长处理：分段归一化均值池化（关键修复）

**问题（实现 M1 验证时发现）**：记忆的检索 KEY = `situation` = market+sentiment+news+fundamentals 四份报告拼接 ≈ **1.4 万字符**，超 DashScope `text-embedding-v4` 的 **8192 token 上限**（实测全长被 `400 Range of input length should be [1,8192]` 拒）。memory.py `get_embedding` 旧逻辑标注「永不截断」且无 OpenAI fallback → **静默返回 1024 维零向量** → 存进去就是零向量、**永远召不回**。这是 A（reflect 写）/ B（get_memories 读）**共用的 chokepoint**，故两端都坏；B 此前「sim 0.83 已验证」是用短合成串测的，从未跑真实长报告，bug 一直潜伏。

**方案选型**：

| 方案 | 丢信息？ | 成本 | 确定性 | 检索逻辑改动 |
|---|---|---|---|---|
| 截断（首版临时修） | ❌ 丢 news+fundamentals | 1 次嵌入 | ✓ | 无 |
| **分段+归一化均值池化** ✅采用 | ✅ 不丢 | 2-3 次嵌入(便宜) | ✓ | 无（仍单向量） |
| 多向量（每段存一行） | ✅ 不丢 | N 行存储 | ✓ | 大改 ChromaDB 用法 + 去重 |
| LLM 摘要后嵌入 | 压缩保留 | +1 LLM 调用 | ❌ 摘要不稳定 | 无；但 B 读热路径太贵 |

**采用「分段 + L2 归一化均值池化」**（`memory.py` `_embed_long_text` + `_chunk_text`）：超 `EMBEDDING_SAFE_CHARS`(默认 7500) 的文本按段落贪心切成 ≤上限的若干块 → 各块递归走单段嵌入 → 每块 L2 归一化后等权平均 → 再归一化成**单个向量**。是「长文档嵌入」的标准做法：**捕获全部四段语义（不像截断丢弃 news/fundamentals）**、写读用同一 chunk 规则保证一致、单向量存储不改 ChromaDB 检索逻辑。

**验证**：全长 13971 字符 → 1024 维全非零；自匹配 sim=**1.000**；涉及基本面/消息面的改写查询 sim=**0.385**（优于截断版的 0.245——因 news+fundamentals 现在也进了向量）。

**实现位置**：`TradingAgents-CN/tradingagents/agents/utils/memory.py::get_embedding`（dispatcher）→ `_embed_long_text` / `_chunk_text`。env `EMBEDDING_SAFE_CHARS` 可调（默认 7500，安全留在 8192 token 内）。**改 memory.py 后跑真实长报告务必确认嵌入非零。**
