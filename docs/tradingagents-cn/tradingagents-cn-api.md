# TradingAgents-CN 个股分析接口文档（对外 Agent 调用）

> 面向**编排 / 调用方 Agent** 的接口参考。覆盖 CLI 与 Python 脚本两条调用路径，逐项说明分析深度、分析团队、模型配置、分析选项、情绪分析、风险评估、语言偏好等可配项。
>
> 代码定位（行号截至本次核对）：
> - 入口类 [`TradingAgentsGraph`](../TradingAgents-CN/tradingagents/graph/trading_graph.py#L201)
> - 默认配置 [`DEFAULT_CONFIG`](../TradingAgents-CN/tradingagents/default_config.py#L3)
> - CLI 入口 [`cli/main.py`](../TradingAgents-CN/cli/main.py)
> - 深度映射 [`cli/utils.py`](../TradingAgents-CN/cli/utils.py#L171) / [`web/utils/analysis_runner.py`](../TradingAgents-CN/web/utils/analysis_runner.py#L237)

---

## 0. TL;DR — 最小可用调用

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"]   = "anthropic"
config["backend_url"]    = "http://localhost:5678"   # 走 claude-max-proxy（本机订阅代理）
config["deep_think_llm"] = "claude-opus-4-8"
config["quick_think_llm"]= "claude-haiku-4-5-20251001"
config["max_debate_rounds"]      = 1
config["max_risk_discuss_rounds"]= 1
config["online_tools"]   = True

ta = TradingAgentsGraph(
    selected_analysts=["market", "fundamentals"],   # 分析团队
    debug=True,
    config=config,
)
final_state, decision = ta.propagate("601899", "2026-06-05")   # (ticker, date)
print(decision["action"], decision["target_price"], decision["confidence"])
```

> 仓库内已有封装脚本 [`TradingAgents-CN/analyze_stock.py`](../TradingAgents-CN/analyze_stock.py)，命令行用法：
> `MONGODB_ENABLED=false REDIS_ENABLED=false .venv/bin/python analyze_stock.py <代码> <日期>`

---

## 1. Python API 入口

### `TradingAgentsGraph(selected_analysts, debug, config)`

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `selected_analysts` | `list[str]` | `["market","social","news","fundamentals"]` | 分析团队，见 §3 |
| `debug` | `bool` | `False` | `True` 时流式打印每个节点 + 计时；产出 `full_states_log.json`（报告组装源） |
| `config` | `dict` | `DEFAULT_CONFIG` | 完整配置，见 §2 |

### `propagate(company_name, trade_date, progress_callback=None, task_id=None)`

| 参数 | 类型 | 说明 |
|---|---|---|
| `company_name` | `str` | 股票代码。A股 `^\d{6}$`(601899)，美股 `[A-Z]{1,5}`(AAPL)，港股 `^\d{4,5}\.HK$`(0700.HK)。市场由代码格式自动识别 |
| `trade_date` | `str`/`date` | `YYYY-MM-DD`，不可为未来日期 |
| `progress_callback` | `callable` | 可选，`fn(message)`，按节点推送进度 |
| `task_id` | `str` | 可选，性能数据追踪 ID |

**返回**：`(final_state: dict, decision: dict)` —— 见 §10。

---

## 2. 配置 Schema（`config` 全字段）

来源 [`default_config.py`](../TradingAgents-CN/tradingagents/default_config.py#L3)。所有键均可在调用前 `config[...] = ...` 覆盖。

| 键 | 默认 | 作用 |
|---|---|---|
| `llm_provider` | `"openai"` | LLM 供应商，见 §6 |
| `deep_think_llm` | `"o4-mini"` | **深度思考**模型（研究经理/风险经理/裁决）。本项目用 `claude-opus-4-8` |
| `quick_think_llm` | `"gpt-4o-mini"` | **快速**模型（分析师/辩论员）。本项目用 `claude-haiku-4-5-20251001` |
| `backend_url` | `"https://api.openai.com/v1"` | API 端点。订阅代理填 `http://localhost:5678` |
| `max_debate_rounds` | `1` | 多空辩论轮数（Bull↔Bear），总发言 = `2 × n`，见 §4 |
| `max_risk_discuss_rounds` | `1` | 风险讨论轮数（激进/保守/中性），总发言 = `3 × n`，见 §7 |
| `max_recur_limit` | `100` | LangGraph 递归上限 |
| `online_tools` | `false`(env) | 在线实时数据源（Tushare/AKShare 等）。建议 `True` |
| `online_news` | `true`(env) | 在线新闻抓取 |
| `realtime_data` | `false`(env) | 实时行情 |
| `memory_enabled` | `True`(可加) | ChromaDB 记忆；深度档位会自动设置，见 §4 |
| `results_dir` | `./results` | 结果输出目录（env `TRADINGAGENTS_RESULTS_DIR`） |
| `data_dir` / `data_cache_dir` | `~/Documents/TradingAgents/data` 等 | 数据与缓存目录 |

**模型级细调**（可选嵌套字典）：`config["deep_model_config"] = {"max_tokens":4000, "temperature":0.7, "timeout":180}`，`quick_model_config` 同理。
⚠️ `claude-opus-4-8` 不接受 `temperature`，框架已自动省略（见 trading_graph 的 `_anthropic_kwargs`）。

---

## 3. 分析团队 / 分析师（`selected_analysts`）

枚举 [`cli/models.py:AnalystType`](../TradingAgents-CN/cli/models.py#L10)，校验于 [`graph/setup.py`](../TradingAgents-CN/tradingagents/graph/setup.py#L65)。

| key | 角色 | 产出字段 | 备注 |
|---|---|---|---|
| `market` | 市场技术分析师 | `market_report` | MA/MACD/RSI/BOLL 等 |
| `social` | 社交情绪分析师 | `sentiment_report` | **A股不支持**，会被自动禁用（数据源限制）见 §6 |
| `news` | 新闻分析师 | `news_report` | Finnhub/Google News 等 |
| `fundamentals` | 基本面分析师 | `fundamentals_report` | PE/PB/ROE/财报等 |

> 任意子集均可，如 `["market","fundamentals"]`。A股建议不带 `social`。

---

## 4. 分析深度（research_depth 1–5）

**注意**：Python API **没有** `research_depth` 单一参数；深度是 CLI/Web 的"预设"，本质是对下表三个 config 键的组合赋值。对外 Agent 调用时，要么直接设这三个键，要么自己实现等价映射。

来源 [`cli/utils.py`](../TradingAgents-CN/cli/utils.py#L171) / [`analysis_runner.py`](../TradingAgents-CN/web/utils/analysis_runner.py#L237)。

| 档位 | 名称 | `max_debate_rounds` | `max_risk_discuss_rounds` | `memory_enabled` |
|---|---|---|---|---|
| 1 | 浅层·快速 | 1 | 1 | False |
| 2 | 基础 | 1 | 1 | True |
| 3 | 标准（Web 默认） | 1 | 2 | True |
| 4 | 深入 | 2 | 2 | True |
| 5 | 全面 | 3 | 3 | True |

> CLI 交互只暴露 1/3/5 三档；Python 可用 1–5 任意组合。轮数越高 = 辩论越充分但耗时越长（Opus 深度档单股约 9 分钟级）。

---

## 5. CLI 接口

入口 [`cli/main.py`](../TradingAgents-CN/cli/main.py#L143)（Typer 应用，`python -m cli.main` 或安装后 `tradingagents`）。交互式顺序提问：

1. **选择市场** — 美股 / A股(默认) / 港股
2. **股票代码** — 按市场格式校验
3. **分析日期** — `YYYY-MM-DD`，默认今天
4. **选择分析师** — 多选 checkbox（market/social/news/fundamentals；A股自动去 social）
5. **研究深度** — 1 浅层 / 3 中等 / 5 深度
6. **LLM 供应商** — 见 §6 `PROVIDER_OPTIONS`
7. **思考模型** — 分别选 quick / deep 模型

> CLI 适合人工体验；对外 Agent 编排建议直接走 §0 的 Python 路径（可参数化、可拿结构化返回）。

---

## 6. 情绪分析（`social`）

- 分析师 key = `social`，输出 `sentiment_report`。
- 工具链：`get_stock_sentiment_unified`（优先）→ `get_stock_news_openai`（在线兜底）→ `get_reddit_stock_info`（离线兜底）。
- **限制**：A股不支持，CLI/Web 检测到 A股代码会自动禁用该分析师。
- Web 有 `include_sentiment` 勾选项，但**不传给 Python API**——是否产出情绪报告取决于 `social` 是否在 `selected_analysts` 中。

---

## 7. 风险评估

风险团队（[`graph/setup.py`](../TradingAgents-CN/tradingagents/graph/setup.py#L165)）固定四角色，**始终运行**（无开关）：

| 角色 | 模型 | 说明 |
|---|---|---|
| 激进风险分析师 risky | quick | 看多/高收益视角 |
| 保守风险分析师 safe | quick | 看空/防御视角 |
| 中性风险分析师 neutral | quick | 平衡视角 |
| 风险经理 risk manager | **deep** | 最终裁决 → `final_trade_decision` |

- 由 `max_risk_discuss_rounds` 控制：总发言 = `3 × n`（三角色轮转）。
- 输出 `risk_debate_state`：含 `risky_history` / `safe_history` / `neutral_history` / `judge_decision` / `count`。
- Web 的 `include_risk_assessment` 勾选**不传给 Python API**——风险评估恒定开启。

---

## 8. 语言偏好

**无内置语言配置。** `DEFAULT_CONFIG` 和 `TradingAgentsGraph.__init__` 均无 language/lang/locale 参数。系统**原生中文输出**：

- 信号处理器 [`signal_processing.py`](../TradingAgents-CN/tradingagents/graph/signal_processing.py#L86) 在 system prompt 中**强制中文**（"绝对不允许使用英文 buy/hold/sell"）。
- 如需英文，必须在调用方自行加翻译层，框架不支持切换。

---

## 9. 模型配置 / 供应商

供应商选择逻辑 [`create_llm_by_provider`](../TradingAgents-CN/tradingagents/graph/trading_graph.py#L39)。

| `llm_provider` | 端点（默认） | 类型 |
|---|---|---|
| `openai` | api.openai.com/v1 | OpenAI 兼容 |
| `anthropic` | （ChatAnthropic，可设 `backend_url`） | 专用；opus-4-8 不传 temperature |
| `google` | generativelanguage.googleapis.com | 专用，transport=rest |
| `deepseek` | api.deepseek.com | 兼容 |
| `qwen`/`dashscope` | dashscope.aliyuncs.com/compatible-mode/v1 | 阿里百炼 |
| `glm` | open.bigmodel.cn/api/paas/v4 | 智谱 |
| `openrouter` | openrouter.ai/api/v1 | 兼容 |
| `siliconflow` / `aihubmix` / `ollama` / `qianfan` / `custom_openai` | 各自端点 | 兼容/自定义 |

- `deep_think_llm` 用于研究经理、风险经理、信号处理等**关键裁决**；`quick_think_llm` 用于各分析师/辩论员。
- **本项目验证路径**：`anthropic` + `backend_url=http://localhost:5678`（claude-max-proxy 把 Claude Max 订阅转 Anthropic Messages API），deep=`claude-opus-4-8`，quick=`claude-haiku-4-5-20251001`。已端到端跑通无 400/500。

---

## 10. 输出结构

### `final_state`（dict）关键字段 — [`agent_states.py`](../TradingAgents-CN/tradingagents/agents/utils/agent_states.py#L60)

| 字段 | 内容 |
|---|---|
| `market_report` | 技术面报告（选了 market 才有） |
| `sentiment_report` | 情绪报告（选了 social 才有） |
| `news_report` | 新闻报告（选了 news 才有） |
| `fundamentals_report` | 基本面报告（选了 fundamentals 才有） |
| `investment_debate_state` | 多空辩论（bull/bear history + judge） |
| `investment_plan` | 研究经理投资计划 |
| `trader_investment_plan` | 交易员执行计划 |
| `risk_debate_state` | 风险三方辩论 + 风险经理裁决 |
| `final_trade_decision` | 最终决策原文（风险经理产出） |
| `performance_metrics` | 各节点耗时/性能数据 |

### `decision`（dict）结构化决策 — [`signal_processing.py`](../TradingAgents-CN/tradingagents/graph/signal_processing.py#L90)

```jsonc
{
  "action": "买入 | 持有 | 卖出",   // 强制中文
  "target_price": 34.0,             // 数字，按股票币种
  "confidence": 0.75,               // 0–1，缺省 0.7
  "risk_score": 0.65,               // 0–1，缺省 0.5
  "reasoning": "决策理由摘要（中文）",
  "model_info": "ChatAnthropic:claude-opus-4-8"  // propagate 追加
}
```

> 解析失败时回退默认：`action="持有"`, `confidence=0.5`, `risk_score=0.5`。

---

## 11. CLI / Python vs Web 能力对照

| 能力 | Python API | CLI | Web |
|---|---|---|---|
| 分析团队 selected_analysts | ✅ 任意子集 | ✅ 多选 | ✅ 勾选 |
| 分析深度 1–5 | ⚠️ 需手设 3 个 config 键 | ✅ 1/3/5 | ✅ 1–5 滑杆 |
| 模型/供应商 | ✅ 全部 | ✅ 全部 | ✅ 部分（侧栏下拉） |
| 情绪分析 | ✅ 经 `social` | ✅ | ✅（A股禁用） |
| 风险评估 | ✅ 恒开，轮数可调 | ✅ | ✅（勾选仅 UI 语义） |
| 语言偏好 | ❌ 仅中文 | ❌ | ❌ |
| `include_sentiment`/`include_risk_assessment`/`custom_prompt` | ❌ Web 专属，不入 API | ❌ | ✅ |
| `market_type` | ⚠️ 由代码格式自动推断 | ✅ 显式选 | ✅ 显式选 |

**结论**：对外 Agent 调用应以 **Python API（§0）** 为准——它覆盖 Web/CLI 的全部"实质"能力（团队、深度、模型、情绪、风险），唯三例外是纯 UI 便利项（`include_*` 勾选、`custom_prompt`、`market_type` 显式选择），这些在 API 路径下分别等价于"是否选 social / 恒定开启 / 代码格式自动识别"。

---

## 12. 对外调用契约（建议给编排 Agent 的 JSON 入参）

```jsonc
{
  "ticker": "601899",            // 必填，A股6位/美股字母/港股xxxx.HK
  "date": "2026-06-05",          // 必填 YYYY-MM-DD，不可未来
  "analysts": ["market", "fundamentals"],  // 子集；A股勿含 social
  "depth": 1,                    // 1–5 → 映射 debate/risk 轮数+memory（见 §4）
  "provider": "anthropic",
  "deep_model": "claude-opus-4-8",
  "quick_model": "claude-haiku-4-5-20251001",
  "backend_url": "http://localhost:5678",
  "online_tools": true
}
```

映射规则：`depth` → 按 §4 表设 `max_debate_rounds`/`max_risk_discuss_rounds`/`memory_enabled`；其余键直填 `config`；`analysts` → `selected_analysts`；调用 `ta.propagate(ticker, date)`，返回 `decision`（§10）+ `final_state` 各报告字段。
