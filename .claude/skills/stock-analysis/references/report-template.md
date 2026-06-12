# 研究报告固定模板（stock-analysis Step 4 产出物）

> 按需加载。这是 `stock-analysis` Skill 把引擎快照编译成「研究报告」的**固定模板**，供前端「个股分析」模块的**研究报告视图**确定性解析（数据 + 完整正文）。
>
> 设计目标：**尽量保留 TradingAgents-CN 完整输出**——每个模块栅栏内放引擎对应报告的**全文**（不截断），数值原子上浮到 frontmatter。落 `raw/analysis/stocks/<ticker>-<date>.md`，由 `Knowledge_Wiki/scripts/build_frontend_data.py` 解析成 `data.json` 的 `companies[].reports[]`。

## 两视图分工（与 wiki 公司页的关系）

| 视图 | 文件 | 角色 | 模块 |
|---|---|---|---|
| **研究报告输出**（前端默认） | `raw/analysis/stocks/<ticker>-<date>.md`（本模板） | 某次引擎运行的**全保真**产物（immutable） | 全部 8 个，含 missing/degraded 如实呈现 |
| **wiki 展示** | `wiki/companies/<TICKER>.md` | finance-ingest 蒸馏的**编译视图**（settled） | distilled 子集（通常 4 个） |

同一套前端渲染器（`renderAnalysisBody`）吃两种 view-model；切换由 toggle 控制，默认研究报告。

## Frontmatter（顶层扁平 · 禁止 `meta.frontend` 嵌套）

> stdlib 解析器会把嵌套 dict 降级为字符串，故原子一律顶层扁平（与 `docs/frontend-kb-binding.md` §2b.3 一致）。

```yaml
---
title: "<公司名>(<ticker>) 个股分析 · 研究报告 <date>"
type: "stock-report"            # 固定；build_frontend_data 按此识别
domain: "finance"
ticker: "<6位代码>"
name: "<公司名>"
exchange: "SSE | SZSE"
market: "cn"
as_of: "<date>"
created: <date>
updated: <date>
summary: "<一句话：档位 + 决策 + 目标价>"   # 必填（build_index 校验）
report_status: "complete | partial | sample"   # 真跑=complete；引擎部分失败=partial；占位演示=sample
engine: "TradingAgents-CN"
depth: <1-5>
run_config: "<analysts> ｜ 多空 N 轮 ｜ 风险 N 轮 ｜ <models>"
price: <number|null>            # 引擎技术面快照现价
change_pct: <number|null>
# --- 决策原子（引擎 decision；模型判断，非客观事实）---
ta_action: "买入|持有|卖出|null"
ta_target_price: <number|null>
ta_confidence: <0-1|null>
ta_risk_score: <0-1|null>
ta_as_of: "<date>"
ta_trend: "up|down|side|null"   # 取自 market 报告
ta_support: <number|null>
ta_resistance: <number|null>
ta_reason: "<decision.reasoning 原文，单行>"
decision_chain:                 # 决策溯源链；每项 "角色|文案|flag(可选 flip/final)"
  - "交易员|<trader_investment_plan 摘要>"
  - "投研经理|<investment judge 结论>|flip"   # flip=较前一环改变方向（前端标红）
  - "风控主席|<risk judge 结论>|final"        # final=最终裁决（前端标灰）
# --- 关键财务（fundamentals 报告；缺失→省略键或 null）---
pe_ttm: <number|null>
pb: <number|null>
roe: <number|null>              # 小数（0.103=10.3%）
roa: <number|null>
net_margin: <number|null>
gross_margin: <number|null>
debt_ratio: <number|null>
current_ratio: <number|null>
# --- 多空 / 催化 / 风险（YAML 块列表）---
bull: ["...", "..."]
bear: ["...", "..."]
catalysts: ["...", "..."]
risks: ["...", "..."]
sources:
  - "raw/data/stock-snapshots/cn/<ticker>-<date>.json"
  - "tradingagents-cn:<depth>:<date>"
related:
  - "[[sectors/<slug>]]"
---
```

## 正文：8 个注释栅栏模块（保留完整正文）

格式：`<!-- module: id | status | layer | 中文标题 | 来源 -->` … `<!-- /module -->`（栅栏渲染后不可见）。
栅栏内放对应引擎报告的**全文**；模块内首行 `### 标题` 在解析时被剥离（供 Obsidian 阅读）。

| # | id | layer | 引擎快照来源 | status 取值规则 |
|---|---|---|---|---|
| §1 | `technical` | fact | `reports.market` | 非空→ok；null→missing |
| §2 | `fundamentals` | fact | `reports.fundamentals` | 同上 |
| §3 | `news` | fact | `reports.news` | 未选 news 分析师 / null → missing |
| §4 | `sentiment` | opinion | `reports.sentiment` | 跑了 social（sentiment_em）→ok；未选 social / null → missing |
| §5 | `debate` | opinion | `debates.investment`（bull_history + bear_history + judge_decision 全文） | 有内容→ok |
| §6 | `trade-plan` | opinion | `reports.trader_investment_plan` | 同上 |
| §7 | `risk` | opinion | `debates.risk`（risky/safe/neutral + judge_decision 全文） | 分析师拒演/无实质内容→**degraded** |
| §8 | `decision` | opinion | `reports.final_trade_decision` + `decision` | ok；若 `decision.parse_fallback`→degraded |

**status 铁律**：缺失即缺失（missing）、降级即降级（degraded）——前端如实标徽章，**禁止臆造**填充。引擎跑挂的模块（news 未取数、risk 辩论拒演）正是靠这套 status 被前端忠实呈现。

正文骨架（事实段 / 判断段物理分离，与现有 SKILL Step 4 的分层一致）：

```markdown
# <公司名> (<ticker>) · 研究报告 <run> · <date>

## 客观事实
<!-- module: technical | ok | fact | §1 市场技术面 | Market Analyst -->
### §1 市场技术面
<market_report 全文>
<!-- /module -->
<!-- module: fundamentals | ok | fact | §2 基本面 | Fundamentals Analyst -->
…
<!-- module: news | missing | fact | §3 新闻舆情 | News Analyst -->
### §3 新闻舆情
未选 news 分析师 → 模块无数据（前端标灰，不臆造）。
<!-- /module -->
<!-- module: sentiment | ok | opinion | §4 市场情绪 | Social Analyst --> <sentiment_report 全文（东财人气+微博情绪）> <!-- /module -->

## TradingAgents-CN 分析判断（非客观事实）
> [!warning] 以下为多智能体辩论产出的主观判断，非市场事实。
<!-- module: debate | ok | opinion | §5 多空辩论 | Bull vs Bear --> <bull+bear+judge 全文> <!-- /module -->
<!-- module: trade-plan | ok | opinion | §6 交易员方案 | Trader --> <trader_investment_plan 全文> <!-- /module -->
<!-- module: risk | ok | opinion | §7 风险辩论 | Risky/Safe/Neutral --> <risky+safe+neutral+judge 全文> <!-- /module -->
<!-- module: decision | ok | opinion | §8 最终裁决 | Risk Manager --> <final_trade_decision 全文> <!-- /module -->
```

## 前端渲染契约（正文怎么被展示 —— 决定你该怎么写）

栅栏内的正文是**自由 markdown**，前端有一个零依赖渲染器自动处理，你**不需要**为某份报告调前端或纠结排版：

- **自动渲染**：标题、`**粗体**`、`` `代码` ``、GFM 表格（`| a | b |`）、有序/无序列表、`>` 引用、`---` 分隔线，全部渲染成排版正文（裸 `#`/`|` 不会以源码形式出现）。
- **按标题自动折叠 + 导航**：渲染器取「最浅且出现 ≥2 次」的标题层把模块切成**可折叠章节**，章节体内更深的重复标题继续**递归嵌套折叠**（至多 3 层），顶层附一排大纲 chips。长模块（如 depth5 的多空辩论）因此自动变成可逐层下钻的结构，无需你拆分。

**对你（Step 4 作者）的直接含义**：

1. **原样保留引擎的 `##/###` 标题层级**——它直接驱动嵌套折叠导航。**别手动压平、别拆成多个模块、别精简成摘要**（与「保留完整正文」一致）。引擎全文塞进栅栏即可。
2. **表格/列表照搬**就会渲染成真表格/列表；不用转换格式。
3. **短模块别硬堆 `##`**（补录/占位内容）——会被切成没必要的折叠；用加粗标签 + 列表即可。
4. **栅栏注释是唯一必须的锚点**：`<!-- module: id | status | layer | 标题 | 来源 -->…<!-- /module -->`。frontmatter 决策/财务原子**全部可缺省**（缺 → `null`，前端优雅降级显示「—」）；但**栅栏缺了，整个模块就不显示**。所以宁可栅栏齐全、字段留空，也别省栅栏。
5. **status/layer 大小写无关**（解析器归一化小写）；契约值 `status∈ok|degraded|missing`、`layer∈fact|opinion`。即便写了未知值，前端也兜底成 `•` 徽章、不报 `undefined`——但还是按契约值写。
6. **字段里别放保留字**：模块**标题不能含 `|`**、**来源不能含 `>`**（会截断栅栏匹配）。

> 一句话：模板对正文「零约束」——把引擎全文塞进栅栏、保留它原生的标题层级，前端就自动渲染 + 按标题折叠 + 导航。**换任何票号、任何报告形态都不用动前端或解析器**（已用不同票/不同模块数/英文标题/纯段落多形态验证过）。

样例见 `Knowledge_Wiki/raw/analysis/stocks/688981-2026-06-09.md`（真跑 depth5，8 模块全保真）。
