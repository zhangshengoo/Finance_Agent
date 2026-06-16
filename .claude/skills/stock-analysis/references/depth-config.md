# 分析档位 & 无头环境契约

> 按需加载。给 `stock-analysis` Skill 与 `stock-analyst-cn` subagent 共用：档位怎么映射、引擎怎么无头跑通。

## 1. 档位 → 引擎配置映射

TradingAgents-CN 的 Python API **没有** `research_depth` 单一参数；"深度"是 CLI/Web 的预设，本质是对三个 config 键的组合赋值。`run_stock_analysis.py` 的 `DEPTH_MAP` 已内置以下映射（对齐 `cli/utils.py:171` 与 `web/utils/analysis_runner.py:237`）：

| 档位 | 名称 | `max_debate_rounds` | `max_risk_discuss_rounds` | `memory_enabled` | 单股耗时（Opus，实测/估） |
|---|---|---|---|---|---|
| 1 | 快速 | 1 | 1 | False | **~5–6 分钟**（600519 实测 336s） |
| 2 | 基础 | 1 | 1 | True | ~6–7 分钟 |
| 3 | 标准（Web 默认） | 1 | 2 | True | ~7–9 分钟 |
| 4 | 深入 | 2 | 2 | True | ~9–11 分钟 ⚠️ 可能超 Bash 600s 上限 |
| 5 | 全面 | 3 | 3 | True | ~12+ 分钟 ⚠️ 大概率超 Bash 600s 上限 |

- 轮数越高 = 多空/风险辩论越充分但越慢。**注意：即便档位 1，深度思考模型（Opus）也用于风险经理/裁决，单 Risk Manager 节点就可能 ~45s**——所以快速档也要 5 分钟级，别按"2-3 分钟"设超时。
- `memory_enabled=True`（档位 ≥2）会初始化本地 **ChromaDB** 并启用**跨日连续记忆（功能 B，见 §1b）**；档位 1 关闭记忆，完全避开 ChromaDB。
- **subagent 的 Bash timeout 建议**（Bash 上限 600000ms=10min）：
  - 档位 1–2 → `480000ms`
  - 档位 3 → `540000ms`
  - 档位 4–5 → `600000ms`，**且很可能不够**。对档位 ≥4，优先 `run_in_background: true` 跑运行器再轮询（或直接降到档位 ≤3）。运行器会把结果写到 `--out`，后台跑完读文件即可。

## 1b. 连续记忆（功能 B）—— 复用原生 FinancialSituationMemory

档位 ≥2 时，引擎原生的 5 个记忆桶（多空研究员/交易员/投资裁决/风险经理）会在多空与风险辩论里调 `get_memories` 召回"类似情况下的历史教训"注入 prompt。**功能 B 把这条原生读链从"进程内即弃"升级为"跨日持久 + 按 ticker 锚定"**，让连续多日分析同一标的能复用历史：

| 维度 | 实现（全部复用原生，仅配置驱动） |
|---|---|
| 持久化 | `chromadb.PersistentClient`，落 `Knowledge_Wiki/.kb-vectors/ta-memory/`（已 gitignore，CLAUDE.md 登记为 skill 内部状态）。由 env `TRADINGAGENTS_MEMORY_PERSIST_DIR` 触发，runner 默认设好。 |
| ticker 分桶 | 集合名加后缀 `bull_memory__<ticker>` 等（`config["memory_namespace"]=ticker`），不同标的记忆不串味。 |
| 嵌入 | **DashScope `text-embedding-v4`**（1024 维，中文 SOTA 档）。与对话 LLM **解耦**：`config["memory_llm_provider"]=dashscope` 只用于 Embedding，**对话仍走 anthropic/claude-max-proxy**。⚠️ **DashScope 在本项目仅做 Embedding，绝不触碰 LLM 消费**（计费独立）。 |

- **冷启动**：某 ticker 第一次分析时记忆库为空（无可召回）；**连续性收益从第 2 次起显现**。完整价值需配合**功能 A（回测）**——A 用真实盈亏调原生 `reflect_and_remember` 把"带收益的教训"写进同一批桶，B 次日自动读到。A 尚未实现（单独回测脚本）。
- **相关 flag**（runner，均有默认值，常规无需传）：`--memory-persist-dir` / `--memory-embed-provider`（默认 dashscope）/ `--memory-embed-model`（默认 text-embedding-v4）。
- **已验证**：跨进程写→读命中（sim 0.83）、中文语义判别 3/3（区分度干净）。MiniLM 等英文本地模型对中文检索会退化成字面匹配 → 会喂错教训，故不采用。
- **⚠️ 嵌入超长（2026-06-12 修复，关键）**：真实 situation（四报告拼接 ≈1.4 万字符）超 text-embedding-v4 的 **8192 token 上限**，旧 `get_embedding`「永不截断」→ 静默返回零向量 → **记忆永远召不回**（B 此前只用短合成串验证未暴露）。已修：超 `EMBEDDING_SAFE_CHARS`(默认 7500) 走 `_embed_long_text` **分段归一化均值池化**（非截断，不丢 news/fundamentals）→ 单向量、写读一致。A 写/B 读共用此 chokepoint 一并修复。验证：全长嵌入非零、自匹配 sim=1.000、相关改写 0.385（优于截断 0.245）。改 memory.py 后跑真实长报告务必确认嵌入非零。

## 2. 分析师团队（`--analysts`）

| key | 角色 | 产出字段 | A 股 |
|---|---|---|---|
| `market` | 市场技术分析师 | `market_report`（MA/MACD/RSI/BOLL…） | ✅ |
| `fundamentals` | 基本面分析师 | `fundamentals_report`（PE/PB/ROE/财报…） | ✅ |
| `news` | 新闻分析师 | `news_report` | ✅ AKShare(东财) 预取 + Google News/WebSearch 兜底（Anthropic 走预取，已修） |
| `social` | 社交情绪分析师 | `sentiment_report` | ✅ `sentiment_em`（东财人气排名 + 微博情绪分），social_media_analyst 走 `is_china` |

默认 `market,social,news,fundamentals`（全 4 类，A 股均支持）。运行器**不再剔除 `social`**——A 股情绪真数据已接入（见 `analyze_stock_deep.py`、`dataflows/providers/china/sentiment_em.py`）。

## 3. 无头运行契约（运行器已封装）

`run_stock_analysis.py` 已把以下都处理好，调用方只需用对 venv + 传参：

- **必须用 TradingAgents-CN 自带 venv**：`TradingAgents-CN/.venv/bin/python`（Python 3.10，依赖已装）。**不要**用 `uv --python 3.12`——那套环境没有引擎依赖。
- **禁用外部 DB**：运行器在 import 前强制 `MONGODB_ENABLED=false / REDIS_ENABLED=false / USE_MONGODB_STORAGE=false`（连接惰性，由开关短路；`config/database_manager.py:88/128`）。所以**不需要**本机起 MongoDB/Redis。
- **.env 读取**：运行器 `chdir` 到 `--ta-root` 后 `load_dotenv(override=False)`，拿 `TUSHARE_TOKEN`（A 股行情/财务数据源）与 `ANTHROPIC_*`，且不会覆盖上面的禁用开关。
- **LLM 路径（已端到端验证）**：`llm_provider=anthropic` + `backend_url=http://localhost:5678`（claude-max-proxy 把 Claude Max 订阅转 Anthropic Messages API），`deep_think_llm=claude-opus-4-8`（裁决/风险经理），`quick_think_llm=claude-haiku-4-5-20251001`（分析师/辩论员）。
- **前置依赖**：claude-max-proxy 必须在 `:5678` 在线（`curl -s -o /dev/null -w "%{http_code}" http://localhost:5678/` 返回任意状态码即在线，404 正常——API 在 messages 路径）。

## 4. 调用示例

```bash
MONGODB_ENABLED=false REDIS_ENABLED=false \
TradingAgents-CN/.venv/bin/python \
  .claude/skills/stock-analysis/scripts/run_stock_analysis.py \
  --ticker 600519 --date 2026-06-08 --depth 1 \
  --analysts market,social,news,fundamentals \
  --out Knowledge_Wiki/raw/data/stock-snapshots/cn/600519-2026-06-08.json \
  --ta-root TradingAgents-CN
```

成功 → stdout 一行 `OK ticker=... action=... target_price=... elapsed=...`，并把完整结果写到 `--out`。
失败 → stdout/stderr `FAILED ...`，`--out` 写 `{"status":"failed","error":...}`，退出码非零。
