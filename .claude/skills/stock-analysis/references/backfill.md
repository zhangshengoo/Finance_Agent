# 缺失模块「直采补录」（不重跑整链）

> 按需加载。引擎跑完后，某个**事实类**模块可能是 `missing`——没选该分析师、或该数据源当次取数超时。用户想补全又不想等十几分钟重跑整链时，可对**事实类**模块做几秒级的直采补录。
>
> 本会话实例：688981 那次引擎只跑了 market+news+fundamentals（没含 social），§4 市场情绪 `missing`。用 `compose_cn_sentiment` 几秒补回真数据，状态 `missing→ok`。

## 能补什么、不能补什么

| 模块类型 | 模块 | 能否直采补录 |
|---|---|---|
| **事实类** | technical / fundamentals / news / **sentiment** | ✅ 这些是数据拉取，可从 `TradingAgents-CN/tradingagents/dataflows` 对应 provider 直采 |
| **判断类** | debate / trade-plan / risk / decision | ❌ 是多智能体**辩论/裁决产物**，没有「直采」一说——要补只能重跑引擎 |

**铁律**：直采补录只补**真数据**。判断类模块缺了就如实留 `missing`/`degraded`，**绝不**用 LLM 编出辩论/裁决来填。

## sentiment 直采（已验证入口）

`compose_cn_sentiment(ticker, curr_date)` 在 `tradingagents/dataflows/providers/china/sentiment_em.py`——东财人气榜 + 微博情绪 + 新闻关键词，**纯 akshare，不用 LLM、不用 proxy**，几秒返回：

```bash
unset VIRTUAL_ENV; MONGODB_ENABLED=false REDIS_ENABLED=false USE_MONGODB_STORAGE=false \
TradingAgents-CN/.venv/bin/python - <<'PY'
import os, sys, json
os.chdir("TradingAgents-CN"); sys.path.insert(0, os.getcwd())
from tradingagents.dataflows.providers.china.sentiment_em import compose_cn_sentiment
print(json.dumps(compose_cn_sentiment("<ticker>", "<date>"), ensure_ascii=False))
PY
```

返回 `{available, score, label, report_md}`。其它事实模块同理：从对应 provider 找几秒级的纯数据入口，**不要**走整张 graph。

## 注入时的「溯源诚实」（关键，别糊弄）

补录数据是真的，但它**不是该次引擎多智能体运行的产物**——必须如实区分，否则就是在伪造引擎审计链：

1. **改模块栅栏**：`<!-- module: sentiment | missing | … -->` → `| ok |`；来源字段改成直采来源，如 `sentiment_em·直采补录`（不要写成 `Social Analyst`，那会暗示它来自引擎那次运行）。
2. **正文加溯源引用块**（`>` 开头）：写明「直采补录：`<provider>`（数据源 + 日期）。**非**该次多智能体引擎产物——本次引擎跑 `<实际分析师集合>`，未含 social；引擎快照 `sentiment` 字段仍为 null；此处为同源真数据补采。」
3. **frontmatter `sources[]` 加一行**：`"sentiment_em:<ticker>:<date> (直采补录 §N)"`。
4. **绝不动引擎快照** `Knowledge_Wiki/raw/data/stock-snapshots/cn/<ticker>-<date>.json`——它是引擎那次运行的忠实审计记录，`sentiment` 该是 null 就保持 null。补录只改**编译视图**（`raw/analysis/stocks/<ticker>-<date>.md`）。
5. **正文别过度结构化**：补录内容通常很短，用加粗标签 + 列表即可，**别堆 `##` 标题**——前端会把重复 `##` 切成折叠章节，短模块那样反而累赘（前端按标题层级递归折叠，见 [report-template.md](report-template.md) 的渲染契约）。
6. **重建**：改完跑 `python3 frontend/build_dist.py`（含 `build_frontend_data.py`），§N 徽章即 `missing→ok`。

> 状态铁律不变：补录到位才标 `ok`，没补就留 `missing`。前端如实显徽章，**禁止臆造**。
