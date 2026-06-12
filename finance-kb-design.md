# 金融理财专属知识库设计方案

> **遵循**：Karpathy [llm-wiki.md](karpathy_gist.md) 抽象模式 + llm_wiki (`~/code/llm_wiki/README_CN.md`) 工程实践
> **形态**：纯文件 + Git + Claude Code Skills（**不**部署 Tauri 桌面 App、**不**重造聊天 UI、**不**起本地 HTTP API）
> **覆盖范围**：金融理财全场景——
> - 公司研究（财报 / 业绩 / 管理层 / 行业地位）
> - 行业研究（产业链 / 周期位置 / 政策影响）
> - 宏观（利率 / 汇率 / 货币 / 财政）
> - 资产配置（股票 / 基金 / 债券 / 黄金 / 保险 / 现金）
> - 个人理财（账户 / 持仓 / 复盘 / 投资论点演进）

---

## 0. 设计原则

### 0.1 三条铁律（Karpathy gist，不可妥协）

1. **持久化 wiki = 编译产物**：知识只被 LLM 编译一次并持续保鲜，**不是**每次查询重新 RAG
2. **人类策展，LLM 维护**：人决定收录边界、问什么；LLM 负责摘要、交叉引用、归档、簿记
3. **三层不变**：`raw/`（不可变源）→ `wiki/`（LLM 生成）→ `purpose + schema`（方向与规则）

### 0.1.5 分层与受众（投影模型）

`raw/` 是唯一真理之源（一切外部产出经 `raw-intake` 归档），其余皆为它的投影：

| 层 | 角色 | 受众 |
|---|---|---|
| `raw` | 不可变源 | 机器/Agent（人不直接读） |
| `preview` | raw 的**展示投影**（单源可读化，喂前端） | 人——快速钻进"某一份源"看懂它 |
| `wiki` | raw 的**知识投影**（跨源综合） | **人 + Agent 双受众**——人读综合做决策、Agent 查询答题 |
| `ontology + vectors` | 机器检索/推理层 | Agent |
| `thoughts` | 主观沉淀 | 人（强制 private） |

**要点**：`wiki` 不是 Agent 私有层（机器层已由 ontology+vectors 承担），它是**人机共享的主综合**，必须人可审计——金融决策依赖于此。`preview` 只是"看懂单份 raw"的辅助，不替代人读综合。前端应同时呈现 wiki（综合，喂 `_index.json`）与 preview（单源下钻）。

### 0.2 不实现清单（明确剔除）

| 剔除项 | 原因 |
|---|---|
| Tauri 桌面 App | Claude Code 已是 Agent UI，App 是中间层包袱 |
| 多对话聊天系统 | Claude Code 终端会话即聊天 |
| 本地 HTTP API + Token | 直接读写文件，跨进程鉴权冗余 |
| sigma.js 图谱可视化 | Obsidian Graph View 已够 |
| 配置化上下文窗口比例 | Claude Code 自动处理 |
| KaTeX / i18n / 浏览器扩展 | UI 层投入，与 wiki 模式无关 |

### 0.3 保留清单（A 类 + B 类 + C 类）

**A 类 — gist 核心架构（始终启用）**
- 三层（raw/wiki/schema）/ 三操作（ingest/query/lint）
- `index.md` 内容目录 / `log.md` 时序日志（grep 友好）
- `[[wikilink]]` 交叉引用 / YAML frontmatter
- Obsidian 兼容

**B 类 — llm_wiki 工程增值（始终启用）**
- `purpose.md` 显式方向层
- **两步 CoT 摄入**（先分析后生成，可暂停人审）
- **SHA256 增量缓存**
- **持久化摄入队列 + 自动重试 ≤3 次**
- **Source 文件夹自动监听**（fswatch）
- **异步审核队列**（predefined actions + 预生成搜索查询）
- **Deep Research 闭环**（网搜 → 综合 → 自动回灌摄入）
- **多格式结构化提取**（PDF / DOCX / PPTX / XLSX / HTML → 结构化 Markdown）
- `sources[]` 级联清理 + 共享实体保护
- `overview.md` 每次摄入后自动重生成
- 财报 / 研报 / 个人理财场景模板

**C 类 — llm_wiki 高级检索能力（按 `_capabilities.yaml` 可选启用）**
- **向量语义搜索**（LanceDB 或 OpenAI 兼容 `/v1/embeddings`）
- **4 信号统计关联度**（直接链接 ×3 / 来源重叠 ×4 / Adamic-Adar ×1.5 / 类型亲和 ×1）
- **Louvain 社区检测**（在 4 信号加权图之上聚类）
- **图谱洞察**（惊奇连接 / 知识空白 / 桥接节点 → 触发 Deep Research 补全）

C 类与基础 typed ontology **并存互补**：typed 给确定语义，C 类给统计相似度与拓扑发现。

---

## 1. 路径与命名

- 知识库根：[Finance_Agent/kb/](kb/)
- **不**用 `~/code/llm_wiki/`（已迁出本仓库，保留为可选可视化前端参考）
- Git 仓库：`kb/.git`，独立于宿主项目
- Obsidian 仓库：直接打开 `kb/` 即可

---

## 2. 目录结构（金融理财特化）

```
Finance_Agent/kb/
├── CLAUDE.md                    # Claude Code 操作合同
├── README.md                    # 人类入口
├── purpose.md                   # 跟踪范围 / 关键问题 / 排除清单 / 演进论点
├── _schema.md                   # frontmatter 强校验规范
├── _areas-registry.md           # 归属决策树
├── _capabilities.yaml           # ★ C 类能力开关（向量 / 4 信号 / Louvain / 洞察）
├── _index.json                  # 自动生成全量索引
│
├── raw/                         # 不可变源
│   ├── filings/                 #   公司财报（10-K / 10-Q / 年报 / 季报 / 招股书）
│   ├── research/                #   卖方研报 / 行业研究
│   ├── transcripts/             #   电话会 / 业绩说明会纪要
│   ├── news/                    #   新闻 / 公告 / 政策文件
│   ├── data/                    #   行情快照 / 财务数据 CSV / JSON
│   ├── products/                #   理财产品说明书 / 基金合同 / 保险条款
│   ├── macro/                   #   宏观报告 / 央行声明 / 利率数据
│   ├── statements/              #   个人账户对账单 / 交易流水
│   └── assets/                  #   图片附件
│
├── wiki/                        # LLM 编译生成（typed entity pages）
│   ├── index.md                 #   内容目录（每次摄入更新）
│   ├── log.md                   #   时序日志（## [YYYY-MM-DD HH:MM] op | title）
│   ├── overview.md              #   全局概要（每次摄入重生成）
│   │
│   ├── companies/               #   公司实体页（一公司一文件，文件名 = ticker）
│   ├── sectors/                 #   行业 / 赛道
│   ├── indicators/              #   财务/估值/运营指标定义
│   ├── events/                  #   财报发布 / 政策 / 管理层变动 / 并购 / 黑天鹅
│   ├── filings-summary/         #   每份 raw 财报/研报的摘要页
│   ├── theses/                  #   投资论点（多空立场，含生命周期：active/superseded/closed）
│   ├── comparisons/             #   同业对比 / 产品对比 / 策略对比
│   ├── products/                #   理财产品 / 基金 / ETF / 保险画像
│   ├── portfolio/               #   个人持仓 / 资产配置快照与复盘
│   ├── macro/                   #   宏观主题页（利率周期 / 汇率 / 流动性）
│   ├── reports/                 #   深度研究产出
│   ├── syntheses/               #   跨资料综合
│   └── queries/                 #   保存为页的对话结论
│
├── thoughts/                    # ★ 思考层（高频写入 / 低成熟度 / 用户主观）
│   ├── _MOC.md                  #   思考层入口
│   ├── _inbox/                  #   30 秒草稿区，48h 内归位
│   ├── ideas/                   #   alpha 假设 / 投资想法池（seed → incubating → validated → promoted → archived）
│   │   ├── equity.md            #     按 domain 一文件池子
│   │   ├── macro.md
│   │   └── <domain>/            #     升级后独立文件 YYYY-MM-DD-<slug>.md
│   ├── questions/               #   待查证的开放问题（open → investigating → answered）
│   ├── decisions/               #   投资决策 ADR（proposed → decided → superseded → reverted）
│   ├── reflections/             #   周度 / 月度 / 季度 / 事件复盘
│   └── todos/                   #   待办（todo → doing → done → cancelled，带 deadline）
│
├── ontology/                    # 显式 typed knowledge graph（append-only JSONL）
│   ├── schema.yaml              #   节点/边类型（金融四层 + 理财扩展 + Thoughts）
│   ├── graph.jsonl              #   append-only 操作流水（op:create / op:relate / op:supersede）
│   └── relatedness.jsonl        #   [C 类] 4 信号关联度快照（可选生成，可重建）
│
├── scripts/
│   ├── build_index.py           # _index.json 生成 + frontmatter 校验（--validate / --strict）
│   ├── graph_build.py           # 回放 graph.jsonl → 当前图快照
│   ├── graph_append.py          # 追加 op:create / op:relate / op:supersede（不直接编辑 jsonl）
│   ├── relatedness_build.py     # [C 类] 4 信号关联度
│   ├── vector_build.py          # [C 类] 向量索引构建
│   ├── vector_query.py          # [C 类] 余弦 ANN 检索
│   ├── community_build.py       # [C 类] Louvain 社区
│   ├── graph_insights.py        # [C 类] 惊奇连接 / 知识空白 / 桥接
│   ├── cascade_delete.py        # raw 删除 → wiki 清理（共享实体保护）
│   ├── watch_raw.py             # fswatch raw/ → 入队
│   ├── queue_runner.py          # 持久化摄入队列 + 重试 ≤3
│   ├── ingest_cache.py          # SHA256 缓存管理
│   └── mcp_server.py            # ★ MCP server 入口（暴露 KB 为外部 Agent 工具）
│
├── .claude/
│   ├── settings.json
│   └── skills/
│       ├── finance-ingest/      # 两步 CoT 摄入（金融特化 prompt）
│       ├── earnings-summary/    # 财报专用摘要
│       ├── product-summary/     # 理财产品 / 基金 / 保险摘要
│       ├── company-page/        # 新建/更新公司画像
│       ├── thesis-archive/      # 把对话结论持久化为投资论点（含 supersede 流程）
│       ├── portfolio-snapshot/  # 持仓快照与配置复盘
│       ├── finance-research/    # Deep Research（强制 Phase 0 去重确认）
│       ├── thought-capture/     # ★ 沉淀 idea / question 到 thoughts/（交互式分步）
│       ├── decision-record/     # ★ 投资决策 ADR 落盘 + supersede 旧决策
│       ├── reflection/          # ★ 周/月/季度复盘 + 事件复盘
│       ├── lint-wiki/           # 健康巡检
│       ├── ontology/            # 图遍历 CLI 包装
│       └── kb-embed/            # [C 类] 自动 embedding 生成
│
├── templates/                   # 每个 page type 一个骨架模板
│   ├── company.md
│   ├── sector.md
│   ├── indicator.md
│   ├── event.md
│   ├── filing-summary.md
│   ├── thesis.md
│   ├── comparison.md
│   ├── product.md
│   ├── portfolio-snapshot.md
│   ├── macro-topic.md
│   ├── report.md                # 深度研究报告模板
│   ├── synthesis.md
│   ├── query.md
│   ├── thought-idea-pool.md     # ★ idea 池子文件
│   ├── thought-idea-standalone.md  # ★ idea 升级后独立文件
│   ├── thought-question.md      # ★ 开放问题
│   ├── thought-decision.md      # ★ 投资决策 ADR
│   ├── thought-reflection.md    # ★ 复盘
│   ├── thought-todo.md
│   └── prompts/
│       ├── ingest-analyze.md
│       ├── ingest-generate.md
│       ├── earnings.md
│       ├── product.md
│       └── research-phase0.md   # ★ Deep Research Phase 0 确认提案模板
│
├── _review/                     # 异步审核队列（LLM 标记待人判断项）
│   ├── pending/                 #   待处理
│   ├── insights/                #   [C 类] 图谱洞察产出
│   └── done/                    #   已处理归档
│
├── .ingest-queue/               # 持久化摄入队列
│   ├── pending.jsonl
│   ├── processing.jsonl
│   └── failed.jsonl
│
├── .ingest-cache/               # SHA256 缓存（gitignored）
│   └── hashes.json
│
├── .kb-vectors/                 # [C 类] LanceDB 向量库（gitignored）
│   └── kb.lance/
│
└── .obsidian/                   # 自动生成
```

---

## 3. Schema 强校验规范

### 3.1 必填字段（所有页面）

```yaml
---
title: "NVIDIA 2025 Q3 财报摘要"
type: "filing-summary"
domain: "finance"
created: 2026-06-02
updated: 2026-06-02
summary: "≤100 字一句话描述"
sources: ["raw/filings/2025Q3-NVDA-10Q.pdf"]
---
```

### 3.2 页面类型枚举

| type | 目录 | 命名 | 说明 |
|---|---|---|---|
| `company` | wiki/companies/ | `<TICKER>.md` | 公司实体（NVDA.md, 600519.md） |
| `sector` | wiki/sectors/ | `<slug>.md` | 行业 / 赛道 |
| `indicator` | wiki/indicators/ | `<slug>.md` | 指标定义（fcf.md, roe.md） |
| `event` | wiki/events/ | `<date>-<slug>.md` | 事件（2025-08-fed-cut.md） |
| `filing-summary` | wiki/filings-summary/ | `<date>-<ticker>-<type>.md` | 财报/研报摘要 |
| `thesis` | wiki/theses/ | `<slug>.md` | 投资论点 |
| `comparison` | wiki/comparisons/ | `<a>-vs-<b>.md` | 对比 |
| `product` | wiki/products/ | `<code>.md` | 理财产品 / 基金 / 保险 |
| `portfolio-snapshot` | wiki/portfolio/ | `<YYYY-MM>.md` | 持仓快照 / 复盘 |
| `macro-topic` | wiki/macro/ | `<slug>.md` | 宏观主题 |
| `report` | wiki/reports/ | `<date>-<slug>.md` | 深度研究 |
| `synthesis` | wiki/syntheses/ | `<slug>.md` | 跨资料综合 |
| `query` | wiki/queries/ | `<date>-<slug>.md` | 保存为页的对话结论 |
| `idea` | thoughts/ideas/`<domain>`/ | `<date>-<slug>.md` 或 `<domain>.md`（池子） | alpha 假设 / 投资想法 |
| `question` | thoughts/questions/ | `<date>-<slug>.md` | 待查证开放问题 |
| `decision` | thoughts/decisions/ | `<date>-<slug>.md` | 投资 / 调仓 / 配置决策 ADR |
| `reflection` | thoughts/reflections/ | `<date>-<period>.md` | 复盘（周/月/季/事件） |
| `todo` | thoughts/todos/ | `<slug>.md` | 待办（带 deadline） |

### 3.3 金融扩展字段

```yaml
# company 专用
ticker: "NVDA"
exchange: "NASDAQ"                 # NASDAQ | NYSE | HKEX | SSE | SZSE
sector: "semiconductors"
market: "us"                       # us | hk | cn | global
listed_since: 1999-01-22
market_cap_class: "mega"           # mega | large | mid | small

# event / filing-summary 专用
ticker: "NVDA"
reporting_period: "2025-Q3"
filing_type: "10-Q"                # 10-K | 10-Q | 8-K | earnings-call | research | news
issuer: "NVIDIA Corporation"
filed_at: 2025-11-19

# thesis 专用（含完整生命周期字段）
stance: "long"                     # long | short | watch | avoid
confidence: "medium"               # high | medium | low
horizon: "中期"                     # 短期 | 中期 | 长期
position_size: "core"              # core | satellite | trial
saved_from: "chat-2026-06-02"
status: "active"                   # active | superseded | closed | invalidated
opened_at: 2026-06-02              # 论点形成日
closed_at: null                    # 论点终结日（status=closed/invalidated 时必填）
supersedes: "theses/nvda-long-2025Q3.md"      # 取代的旧论点（可选）
superseded_by: null                # 被哪份新论点取代（旧 thesis 反向指针）
catalyst:                          # 触发买入/卖出的关键事件
  - "2025Q3 数据中心营收同比 +94%"
invalidation_criteria:             # 何种情况下论点失效
  - "数据中心营收同比增速跌破 20%"
  - "毛利率连续两季度下滑超 5pp"
review_at: 2026-12-01              # 计划复盘日

# indicator 专用
formula: "FCF = OCF - CapEx"
unit: "USD"                        # USD | CNY | HKD | %
direction: "higher-better"         # higher-better | lower-better | neutral

# product 专用（理财 / 基金 / 保险）
product_code: "000300"             # 基金代码 / 保险条款编号
product_type: "fund"               # fund | etf | structured | insurance | bond | bank-wealth
risk_level: "R3"                   # R1-R5（中国理财风险等级）
fee_rate: "1.5%"
underlying: ["sse-50"]
issuer: "易方达基金"

# portfolio-snapshot 专用
as_of: 2026-06-01
total_value: 1000000               # 单位 = unit
unit: "CNY"
allocation:
  - { asset: equity, weight: 0.55 }
  - { asset: bond,   weight: 0.25 }
  - { asset: cash,   weight: 0.20 }
benchmark: "csi-300"

# macro-topic 专用
region: "us"                       # us | cn | eu | jp | global
indicator_kind: "rate"             # rate | inflation | money | fx | growth
```

### 3.4 Thoughts 专属字段（thoughts/ 子目录下文档）

```yaml
# 通用（所有 thoughts/ 下文档）
visibility: "private"              # 默认 private，金融决策强烈建议保持
thought_type: "decision"           # idea | question | decision | reflection | todo | idea-pool
related: ["theses/nvda-long-2025-datacenter.md"]

# thought_type=idea 专用
idea_type: "research-idea"         # research-idea | product-idea | improvement | question-driven | hypothesis
value: "高"                         # 高 | 中 | 低
effort: "中"                        # 小 | 中 | 大
status: "seed"                     # seed → incubating → validated → promoted → archived
promoted_from: "thoughts/ideas/equity.md"   # 从哪个池子升级
promoted_to: "wiki/theses/<slug>.md"        # 升级到哪份正式 thesis（promoted 状态时）

# thought_type=question 专用
importance: "高"                    # 高 | 中 | 低
status: "open"                     # open → investigating → answered → wontfix
target_ticker: "NVDA"              # 可选：问题指向的实体
answer: null                       # answered 时填，链接到答复文档

# thought_type=decision 专用（投资 ADR）
status: "decided"                  # proposed → decided → superseded → reverted
decision_kind: "rebalance"         # buy | sell | rebalance | hedge | allocate | skip
ticker: "NVDA"                     # 涉及标的
position_change: "+30%"            # 仓位变更（可选）
decided_at: 2026-06-02
review_at: 2026-09-02              # 复盘日
supersedes: "thoughts/decisions/2026-05-15-nvda-trim.md"
rationale_sources: ["wiki/filings-summary/2025Q3-NVDA-10Q.md"]

# thought_type=reflection 专用
reflection_type: "monthly"         # weekly | monthly | quarterly | event | freeform
period_start: 2026-05-01
period_end: 2026-05-31
benchmark: "csi-300"               # 复盘对照基准（可选）

# thought_type=todo 专用
priority: "P1"                     # P0 | P1 | P2 | P3
deadline: 2026-07-01
status: "todo"                     # todo → doing → done → cancelled
```

**状态机汇总：**

| thought_type | status 流转 | 终态 |
|---|---|---|
| `idea` | seed → incubating → validated → promoted → archived | promoted（升级到 theses/）/ archived |
| `question` | open → investigating → answered → wontfix | answered / wontfix |
| `decision` | proposed → decided → superseded → reverted | superseded / reverted（保留审计轨迹） |
| `reflection` | active | active（无生命周期） |
| `todo` | todo → doing → done → cancelled | done / cancelled |
| `thesis`（wiki/） | active → superseded → closed/invalidated | superseded（被新 thesis 取代）/ closed（主动了结）/ invalidated（被证伪） |

---

## 4. `purpose.md` 模板（金融理财场景）

```markdown
# Purpose

## 目标
本知识库跟踪 <你的标的池 + 资产类别>，目的是 <例：构建可复用投资论点 + 持仓决策档案 + 资产配置框架>。

## 关注维度
- 经营杠杆 / 现金流质量 / 资本回报
- 产业链上下游传导
- 管理层变动与战略调整
- 监管政策 / 宏观流动性
- 估值分位与周期位置
- 个人配置与基准对比

## 排除清单
- 短线技术分析 / 日内择时
- 加密货币 / NFT
- 一级市场早期项目（非已上市标的）
- 未经证实的传闻 / 小道消息

## 关键问题（演进中）
- 当前所处货币周期阶段？
- AI 资本开支周期处于哪个位置？
- 中国消费降级 vs 升级的真实结构？
- 我个人组合相对基准超额来源？

## 论点指针（活跃论点）
- [[theses/nvda-long-2025-datacenter]]
- [[theses/cn-consumer-rotation-2026]]
- [[theses/personal-bond-overweight-rate-cut]]
```

每次摄入和查询，Claude 都先读 `purpose.md` —— 它决定**收录边界**与**注意力分配**。

---

## 4.5 `_areas-registry.md` — 归属决策树

> **目的：** wiki / thoughts 之间、各子目录之间的归属边界天天发生（"管理层 commentary 进 transcripts 还是 thesis？" "调仓想法是 idea 还是 decision？"）。这份注册表 = Skills 和 Agent 写入时的判断依据。

### 4.5.1 顶级分类职责

| 分类 | 目录 | 职责范围 | 典型内容 | visibility 默认 |
|---|---|---|---|---|
| Raw | `raw/` | 不可变源材料 | 财报 PDF / 研报 / 电话会 / 新闻 / 行情快照 / 产品说明书 / 对账单 | private |
| Wiki | `wiki/` | LLM 编译产物，typed entity 页面 | 公司画像 / 行业页 / 指标定义 / 财报摘要 / 投资论点 / 持仓快照 / 宏观主题 | private |
| Thoughts | `thoughts/` | 用户主观沉淀，高频写入低成熟度 | 假设池 / 待查证问题 / 决策 ADR / 复盘 / 待办 | **private（强制）** |

### 4.5.2 wiki/ 子目录归属

| 内容形态 | 目标目录 | 关键判据 |
|---|---|---|
| 单份财报/研报的摘要 | `wiki/filings-summary/` | 一对一对应一份 raw 文件，文件名含 `<date>-<ticker>-<type>` |
| 公司基本面综合 | `wiki/companies/` | 跨多份 filings 的稳定画像（一公司一文件） |
| 投资论点（含买卖立场） | `wiki/theses/` | 含 `stance: long/short/watch/avoid` |
| 行业/赛道画像 | `wiki/sectors/` | 跨多公司，含产业链 / 周期 / 政策 |
| 跨标的对比 | `wiki/comparisons/` | A vs B / A vs B vs C，文件名 `<a>-vs-<b>.md` |
| 个人持仓快照 | `wiki/portfolio/` | 含 `as_of` + `allocation[]`，月度生成 |
| 宏观主题 | `wiki/macro/` | 利率 / 汇率 / 流动性 / 通胀，跨标的 |
| 深度研究报告 | `wiki/reports/` | finance-research Skill 8 阶段流水线产出 |
| 跨资料综合 | `wiki/syntheses/` | 多份资料合成新洞察（非单一报告） |
| 保存的对话结论 | `wiki/queries/` | 对话产出价值高、值得复用 |

### 4.5.3 thoughts/ 子目录归属

| 内容形态 | 目标目录 | 关键判据 |
|---|---|---|
| 闪念 / 待孵化的 alpha 假设 | `thoughts/ideas/<domain>.md`（池子） | 内容 ≤ 8 行，status=seed |
| 深入孵化的假设 | `thoughts/ideas/<domain>/<date>-<slug>.md` | 内容深度足，准备验证，status=incubating+ |
| 待查证的开放问题 | `thoughts/questions/` | 形如 "X 是不是 Y" "为什么 Z"，期待 answer |
| 已做出的投资决策 | `thoughts/decisions/` | 已 commit 的行动，含 ADR 五要素（背景/选项/理由/后果/复盘） |
| 周/月/季度复盘 | `thoughts/reflections/` | 时间窗口固定，含 `period_start/period_end` |
| 待办（有 deadline） | `thoughts/todos/` | 含 `deadline:` 字段 |
| 不确定先扔哪里 | `thoughts/_inbox/` | 48h 内必须归位，超期 lint 报警 |

### 4.5.4 归属决策树

```
要归档的内容是什么？
│
├── 不可变源材料（PDF / 研报 / 新闻 / 对账单）？
│   → raw/<对应子目录>/
│
├── 闪念 / 想法 / 未验证假设？
│   ├── ≤8 行 → thoughts/ideas/<domain>.md（池子追加 callout）
│   └── 准备深入 → thoughts/ideas/<domain>/<date>-<slug>.md
│
├── 已做出的投资决策（含 catalyst + rationale）？
│   → thoughts/decisions/
│
├── 想成立但需要先验证的论点？
│   → 先 thoughts/ideas/，验证后 promoted_to wiki/theses/
│
├── 已成立的投资论点（含买卖立场）？
│   → wiki/theses/（含完整生命周期字段）
│
├── 待查证的开放问题？
│   → thoughts/questions/
│
├── 周记 / 月记 / 季度 / 事件复盘？
│   → thoughts/reflections/
│
├── 单份 raw 资料的摘要？
│   → wiki/filings-summary/
│
├── 跨多份资料的实体画像？
│   → wiki/{companies, sectors, products, macro}/
│
├── 跨标的对比？
│   → wiki/comparisons/
│
├── 深度研究产出（finance-research 8 阶段产出）？
│   → wiki/reports/
│
├── 保存的对话结论？
│   → wiki/queries/
│
└── 不确定？
    → thoughts/_inbox/，48h 内 review 归位；仍不确定征求用户意见
```

### 4.5.5 wiki vs thoughts 的边界判别

| 维度 | wiki/ | thoughts/ |
|---|---|---|
| 成熟度 | 中-高（已沉淀） | 低（孵化中） |
| 信息来源 | 编译自 raw + 综合 | 用户主观 + Agent 引导 |
| 写入频率 | 中（摄入触发） | 高（即时捕获） |
| 客观性 | 客观（数据+引用） | 主观（判断+假设） |
| 升级路径 | （终态） | → wiki/（idea → thesis） |
| visibility | private | **private 强制** |

**典型升级：** `thoughts/ideas/equity/2026-05-nvda-datacenter-cycle.md` 验证后 → `wiki/theses/nvda-long-2025-datacenter.md`，并在 idea 文件 frontmatter 写 `promoted_to: wiki/theses/...`。

---

## 5. C 类能力开关（`_capabilities.yaml`）

```yaml
vector_search:
  enabled: false                   # 默认关闭，规模到了再开
  backend: lancedb
  embedding:
    endpoint: "https://api.openai.com/v1/embeddings"
    model: "text-embedding-3-small"
    api_key_env: "OPENAI_API_KEY"
    dimensions: 1536
  auto_embed_on_ingest: true
  chunk: { size: 800, overlap: 120 }

relatedness_4signal:
  enabled: false
  weights:
    direct_link: 3.0
    source_overlap: 4.0
    adamic_adar: 1.5
    type_affinity: 1.0
  decay: 0.6
  top_k_per_node: 20

community_detection:
  enabled: false
  algorithm: louvain
  min_cohesion_warn: 0.15

graph_insights:
  enabled: false
  surprises: true                  # 跨社区 / 跨类型连接
  gaps: true                       # 孤立 / 稀疏社区 / 桥接节点
  output_dir: _review/insights/
```

---

## 6. 三个核心操作

### 6.1 Ingest — `finance-ingest` skill（两步 CoT）

```
Step 0  缓存检查（SHA256 → .ingest-cache/hashes.json，命中跳过）
        多格式提取
          PDF       → pymupdf / pdfplumber，表格保留为 Markdown table
          DOCX      → python-docx，标题层级 / 加粗 / 列表保留
          PPTX      → python-pptx，逐页提取
          XLSX      → openpyxl，多 sheet → 多 table
          HTML      → readability + turndown

Step 1  分析（Analyze）
        读: purpose.md + wiki/index.md + wiki/overview.md + 相关现存页 + templates/prompts/ingest-analyze.md
        出: 结构化分析草稿（实体 / 关键财务数据 / 与现有论点冲突 / 建议变更 / review_items / search_queries）
        落: .claude/state/ingest-<hash>.json
        暂停: 写入 _review/pending/ 等用户确认 / 修改

Step 2  生成（Generate）
        按 suggested_changes 写 / 更新文件（必带 sources[]）
        维护 [[wikilink]] 双向引用
        追加 wiki/log.md：## [2026-06-02 14:30] ingest | NVDA 2025 Q3 10-Q | 4 pages
        重生成 wiki/overview.md
        review_items → _review/pending/
        更新 .ingest-cache/hashes.json
        [C 类] 若 vector_search.enabled：kb-embed skill 自动生成 embedding
        Post-hook：build_index.py + graph_build.py + [C 类] relatedness_build.py
```

### 6.2 Query — 多阶段流水线

```
Stage 0   注入系统提示：purpose.md + wiki/index.md + wiki/overview.md

Stage 1   分词检索
          grep / glob 命中 wiki/* + raw/*
          标题匹配 +10 分；中文 CJK 二元组分词

Stage 1.5 [C 类，可选] 向量语义搜索
          通过 LanceDB 余弦 ANN
          发现关键词覆盖不到的语义近邻
          结果合并：增强已有匹配 + 添加新发现

Stage 2   图扩展
          a) 确定性：typed ontology traverse（始终）
          b) [C 类，可选] 探索性：4 信号关联度
             复合分 = 3·直接链接 + 4·来源重叠 + 1.5·Adamic-Adar + 1·类型亲和
             2 跳衰减传播 0.6

Stage 3   预算控制：按 (搜索分 + 图分) 排序，保留 top-N 页全文

Stage 4   read 全文（不分 chunk）+ 综合作答 + [[wikilink]] 引用

Stage 5   可选：thesis-archive / portfolio-snapshot / kb-archive 落地
```

**最小配置**（Stage 1 + 2a + 3-5）足以应对 < 几百页规模。Stage 1.5 + 2b 在规模上来或召回不足时开启。

### 6.3 Lint — `lint-wiki` skill

```
矛盾     跨页 claim 冲突（如「Q3 营收 30B」vs 旧页「指引 25B」未更新）
陈旧     新源已超越但旧页未 updated
孤儿     无入链页
缺页     被频繁 [[wikilink]] 引用但目标不存在
失链     [[wikilink]] 指向已删页
财报漏摄入  raw/filings/ 有但 wiki/filings-summary/ 缺
论点失效  thesis 引用的财报已被新数据反证
[C 类]   图谱洞察输出（_review/insights/）
```

底层校验：
```bash
python3 scripts/build_index.py --validate
python3 scripts/cascade_delete.py --check
python3 scripts/graph_build.py --validate
# [C 类] python3 scripts/graph_insights.py
# Claude 读 _index.json + log.md + overview.md 做语义层巡检
```

---

## 7. Ontology（金融四层 + Thoughts 扩展）

### 7.0 存储形态：append-only JSONL（审计流水）

> **关键设计：** `ontology/graph.jsonl` 是**操作流水**而非图快照。每行 = 一次 op（create / relate / supersede / archive）。当前图状态由 `graph_build.py` 回放流水生成（在内存中）。**永不重写**已有行。

**优势：**
- Git diff 友好 — 每次摄入只 append，不会有大块重写
- 演化可追溯 — `git log -p` 直接看图的演化史
- 可 replay — 任意时间点的图都能重建（debug / 复盘有用）
- 与 thesis supersede 流程天然契合

**操作 schema：**

```jsonl
{"ts":"2026-06-02T14:30:00Z","op":"create","entity":{"id":"comp_nvda","type":"Company","props":{"ticker":"NVDA","exchange":"NASDAQ","sector":"semiconductors"}}}
{"ts":"2026-06-02T14:30:01Z","op":"create","entity":{"id":"filing_2025q3_nvda_10q","type":"Filing","props":{"path":"raw/filings/2025Q3-NVDA-10Q.pdf","filed_at":"2025-11-19","reporting_period":"2025-Q3"}}}
{"ts":"2026-06-02T14:30:02Z","op":"relate","from":"comp_nvda","rel":"REPORTS","to":"filing_2025q3_nvda_10q"}
{"ts":"2026-06-02T14:30:03Z","op":"create","entity":{"id":"thes_nvda_long_2025_dc","type":"Thesis","props":{"path":"wiki/theses/nvda-long-2025-datacenter.md","stance":"long","status":"active"}}}
{"ts":"2026-06-02T14:30:04Z","op":"relate","from":"thes_nvda_long_2025_dc","rel":"THESIS_ABOUT","to":"comp_nvda"}
{"ts":"2026-06-02T14:30:05Z","op":"relate","from":"thes_nvda_long_2025_dc","rel":"CITES","to":"filing_2025q3_nvda_10q"}
{"ts":"2026-09-15T10:00:00Z","op":"supersede","from":"thes_nvda_long_2025_dc","by":"thes_nvda_long_2026_ai_inference","reason":"2026Q2 数据中心增速放缓，论点重心转向 inference"}
{"ts":"2026-09-15T10:00:01Z","op":"update_prop","entity":"thes_nvda_long_2025_dc","prop":"status","value":"superseded"}
```

**操作类型：**

| op | 说明 |
|---|---|
| `create` | 新建实体（含 id / type / props） |
| `relate` | 新建边（from / rel / to + 可选 props） |
| `update_prop` | 修改实体属性（如 status: active → superseded） |
| `supersede` | thesis / decision 专用，自动派生 SUPERSEDES 边 + 双方 status 更新 |
| `archive` | 实体软删除（保留历史） |
| `unrelate` | 删除边（罕用，必须有 reason） |

**写入接口：** Skills 不直接编辑 jsonl，统一调 `python3 scripts/graph_append.py <op> ...`，确保格式合规、自动加时戳。

### 7.1 节点与边类型（`ontology/schema.yaml`）

```yaml
nodes:
  # 金融四层
  Company:    { keys: [ticker, exchange] }
  Sector:     { keys: [slug] }
  Indicator:  { keys: [slug] }
  Event:      { keys: [date, slug] }
  Filing:     { keys: [path] }
  Thesis:     { keys: [slug] }
  Product:    { keys: [product_code] }       # 基金 / 理财产品 / 保险
  Portfolio:  { keys: [as_of] }              # 持仓快照
  Macro:      { keys: [slug] }               # 宏观主题

  # Thoughts 扩展
  Idea:       { keys: [path] }               # alpha 假设
  Question:   { keys: [path] }               # 待查证问题
  Decision:   { keys: [path] }               # 投资决策 ADR
  Reflection: { keys: [path] }               # 复盘

edges:
  # 金融层
  IN_SECTOR:     { from: Company,    to: Sector }
  REPORTS:       { from: Company,    to: Filing }
  MEASURES:      { from: Filing,     to: Indicator }
  AFFECTS:       { from: Event,      to: [Company, Sector, Macro] }
  PEER_OF:       { from: Company,    to: Company }
  THESIS_ABOUT:  { from: Thesis,     to: [Company, Sector, Product, Macro] }
  CITES:         { from: Thesis,     to: Filing }
  SUPERSEDES:    { from: Thesis,     to: Thesis,   acyclic: true }
  INVALIDATED_BY:{ from: Thesis,     to: [Filing, Event] }
  HOLDS:         { from: Portfolio,  to: [Company, Product] }
  TRACKS:        { from: Product,    to: [Sector, Company] }
  ISSUED_BY:     { from: Product,    to: Company }
  EXPOSED_TO:    { from: Portfolio,  to: Macro }

  # Thoughts 层
  PROMOTED_FROM: { from: Thesis,     to: Idea,         acyclic: true }   # thesis 来自 idea
  ABOUT:         { from: [Idea, Question, Decision, Reflection], to: [Company, Sector, Product, Thesis, Portfolio, Macro] }
  ANSWERED_BY:   { from: Question,   to: [Filing, Thesis, Report] }
  DECISION_ON:   { from: Decision,   to: [Company, Product, Portfolio] }
  DECISION_SUPERSEDES: { from: Decision, to: Decision, acyclic: true }
  REVIEWS:       { from: Reflection, to: [Decision, Thesis, Portfolio] }
  RATIONALE:     { from: Decision,   to: Filing }     # 决策的事实依据
```

### 7.2 边自动派生（确定性图）

| frontmatter / 正文来源 | 派生 op |
|---|---|
| `ticker: NVDA, sector: semi` | `create Company` + `relate IN_SECTOR` |
| `sources: [filings/X.pdf]` | `create Filing` + `relate REPORTS` |
| `type: thesis, ticker: NVDA` | `create Thesis` + `relate THESIS_ABOUT` |
| `type: thesis, supersedes: <path>` | `op: supersede` （自动更新双方 status） |
| `type: thesis, promoted_from: <idea-path>` | `relate PROMOTED_FROM` |
| `type: portfolio-snapshot, allocation[]` | `create Portfolio` + 多条 `relate HOLDS` |
| `type: decision, supersedes: <path>` | `op: supersede` + `update_prop status` |
| `type: question, target_ticker:` | `relate ABOUT` |
| `type: reflection, related: [decisions/...]` | `relate REVIEWS` |
| 正文 `[[wikilink]]` | 弱权重 `RELATES_TO` |

### 7.3 [C 类] 4 信号关联度

启用后 `scripts/relatedness_build.py` 产出 `ontology/relatedness.jsonl`（与 typed graph 并存）：

| 信号 | 默认权重 | 计算 |
|---|---|---|
| 直接链接 | ×3.0 | `[[wikilink]]` / `related[]` |
| 来源重叠 | ×4.0 | 共享 `sources[]` |
| Adamic-Adar | ×1.5 | `∑(1/log(deg(共同邻居)))` |
| 类型亲和 | ×1.0 | 相同 `type` 加分 |

金融场景下尤其有用：**「来源重叠 ×4」自动把同一份研报覆盖的公司聚在一起**，比手动维护 `[[wikilink]]` 高效。

### 7.4 [C 类] 向量索引

启用后：
- 写入：`finance-ingest` Step 2 写完页面 → `kb-embed` skill → 长页按 chunk 切 → 入 `.kb-vectors/kb.lance`
- 查询：Query Stage 1.5 调 `scripts/vector_query.py`
- 重建：`vector_build.py --rebuild` 全量；`--incremental` 仅处理 hash 变化页

### 7.5 [C 类] Louvain + 图谱洞察

- `community_build.py` 在 4 信号加权图上跑 Louvain → 每节点贴 `community_id`
- `graph_insights.py` 输出三类信号到 `_review/insights/`：
  - **惊奇连接**：跨社区 / 跨类型强关联（"为什么这只消费股和半导体公司这么近？"）
  - **知识空白**：孤立页（度 ≤ 1）/ 稀疏社区（内聚度 < 0.15）/ 桥接节点
  - 一键喂 `finance-research` 触发 Deep Research 补全

---

## 8. Skills 体系（`.claude/skills/`）

### 8.1 Skill 注册表

每个 SKILL.md 的 `description:` 字段含 2-3 个简洁中文触发短语即可，避免过多上下文占用。

| Skill | 触发词 | 阶段 | 说明 |
|---|---|---|---|
| `finance-ingest` | `摄入财报` / `处理 raw/...` | P1 | 两步 CoT + SHA256 + 多格式 |
| `earnings-summary` | `财报摘要` / `Q3 业绩` | P1 | 财报特化（关键财务指标对齐） |
| `product-summary` | `理财产品摘要` / `基金解读` | P1 | 理财产品提取（费率/风险/标的） |
| `company-page` | `新建公司 X` / `更新公司画像` | P0 | 模板化实体页 |
| `thesis-archive` | `存论点` / `保存为投资论点` | P0 | 对话结论 → `wiki/theses/`，支持 supersede 旧 thesis |
| `portfolio-snapshot` | `持仓快照` / `配置复盘` | P2 | 周期性快照 → 与基准对比 |
| `finance-research` | `深度研究 X` / `调研行业 Y` | P3 | **含强制 Phase 0**：网搜 + 综合 + 回灌 |
| `thought-capture` | ★ `沉淀这个 idea` / `记一下这个想法` | P0 | 交互式分步（一次只问一项），落 `thoughts/ideas/` 或 `thoughts/questions/` |
| `decision-record` | ★ `记录决策` / `落 ADR` | P1 | 投资决策 ADR + 自动 supersede 旧决策 |
| `reflection` | ★ `周复盘` / `月度复盘` | P2 | 周/月/季度/事件复盘，引用对应 decisions / theses |
| `lint-wiki` | `巡检` / `健康检查` | P2 | 矛盾 / 陈旧 / 孤儿 / 失链 / 论点失效 / inbox 超时 |
| `ontology` | `图谱` / `X 的邻居` | P2 | traverse / related / query / append-only 写入 |
| `kb-embed` | （内部，被 ingest 调用） | P3.5 | [C 类] 向量生成 |

### 8.2 Skill 编写工艺（来自 iKnowledge 经验）

每个 SKILL.md 顶部必须包含：

- **description（带触发词）**：2-3 个中文触发短语，覆盖最常见的口语表达即可
- **决策树（Decision Tree）**：什么时候用本 Skill / 什么时候用其它 Skill，明确边界
- **CRITICAL 红线**：违反会让用户停用 Skill 的 do/don't（例：`thesis-archive` 红线 = 不替用户加风险分析；`thought-capture` 红线 = 逐字保留用户原话，不重组语义）
- **分阶段工作流**：CLARIFY → EXTRACT → COMPOSE → REVIEW → INDEX → ONTOLOGY 六阶段范式（轻量任务可裁剪）
- **交互工艺**："一次只问一项" — 多字段录入时分步询问，禁止一条消息塞 5 个问题

### 8.3 `finance-research` 强制 Phase 0：KB 去重 + 范围确认

> **铁律：** 任何 WebSearch / WebFetch / 外部 Agent 搜索之前必须执行 Phase 0。未经用户确认禁止发起任何外部检索。研究报告是持久化沉淀，方向偏了浪费搜索成本和写作成本。

```
Phase 0: Scope Confirmation（强制，唯一可跳过条件：用户明确说"不用确认"）

Step 1  KB 去重检查（不联网）
        a) grep _index.json + wiki/index.md 关键词匹配
        b) ontology 查询：python3 scripts/graph_build.py query --type Report --where '{"tags":"<key>"}'
        c) Grep wiki/reports/ + wiki/syntheses/ 相关主题
        d) [C 类] 若启用向量：vector_query.py 语义近邻
        分三类输出：
          ▪ 高度重复（≥80% 覆盖） → 建议更新已有报告或缩小范围
          ▪ 部分重叠（30-80%） → 提案中标注已有内容，避免重复研究
          ▪ 无重复 → 继续

Step 2  整理研究提案（模板 templates/prompts/research-phase0.md）
        - 研究问题（一句话）
        - 研究范围（含 / 排除）
        - 已有相关内容（链接到 wiki/）
        - 预期深度（Quick 2-5min / Standard 5-10min / Deep 10-20min / UltraDeep 20-45min）
        - 关键子问题（3-5 个）
        - 预期产出结构
        - 已知约束（时间 / 来源偏好 / 语言）

Step 3  展示提案 → 停下等用户确认
        > "以上是我理解的研究范围，要调整吗？确认后我开始搜索。"

Step 4  根据反馈分支
        - 确认 → Phase 1 正式研究
        - 修正 → 更新提案重回 Step 3
        - "你看着办" / "直接开始" → 视为确认
```

### 8.4 `thought-capture` 交互工艺

iKnowledge 的 [thought-capture/SKILL.md](../../iKnowledge/.claude/skills/thought-capture/SKILL.md) 是分步交互典范，金融场景照搬：

```
Step 1  接住用户原话（CRITICAL：逐字引用，不重组、不提炼）
Step 2  确认 domain（equity / macro / portfolio / product / misc）
Step 3  形态：池子 callout（≤8 行）vs 独立文件（深度足）
Step 4  status / idea_type / value / effort 逐项问
Step 5  tags（建议 3-5 个）
Step 6  Actions（可为 0 个 / 多个独立 callout）
Step 7  Agent 扩展思考（2-3 个加粗短语 + 一句展开，等用户验收）
Step 8  触发场景（可选跳过）
```

**红线（违反停用）：** 逐字保留用户表达；不加可行性分析；不加用户没说的"相关工作"；允许补 markdown 排版，**不允许**合并条目 / 调整顺序 / 改写句式。

### 8.5 `decision-record` ADR 流程

每条决策 = `thoughts/decisions/<date>-<slug>.md`，结构固定：

```markdown
# Decision: <一句话>

## 背景
<触发决策的情境，引用 wiki/filings-summary / events>

## 选项
1. <方案 A>
2. <方案 B>
3. <方案 C — 含"不操作">

## 决策与理由
<选了哪个 + 为什么 + 关键 trade-off>

## 预期后果
- 上行: ...
- 下行: ...
- 反证条件: <满足时回滚>

## 复盘安排
review_at: <YYYY-MM-DD>
```

**supersede 流程：** 用户说"撤销 X 决策" / "调整之前的决策" → Skill 自动：
1. 创建新 decision 文件，frontmatter 写 `supersedes: thoughts/decisions/<old>.md`
2. 旧 decision frontmatter `status: decided → superseded`
3. 调 `graph_append.py supersede --from <new> --by <old>`
4. 追加到对应 reflection（如有当周复盘文件）

---

## 9. 自动化与脚本

### 9.1 基础脚本（A + B 类）

| 脚本 | 说明 |
|---|---|
| `build_index.py` | `_index.json` + frontmatter `--validate` / `--strict`（pre-commit 用） |
| `graph_build.py` | 回放 `graph.jsonl` → 内存图快照 + traverse / query / stats / validate 子命令 |
| `graph_append.py` | append-only 写入：`create` / `relate` / `update_prop` / `supersede` / `archive` / `unrelate`（自动时戳） |
| `cascade_delete.py` | raw 删除 → wiki 三重匹配清理 + 共享实体保护 |
| `watch_raw.py` | fswatch raw/ → `.ingest-queue/pending.jsonl` |
| `queue_runner.py` | 持久化队列串行处理，失败重试 ≤3 次 |
| `ingest_cache.py` | SHA256 缓存读写 |
| `mcp_server.py` | ★ MCP server 入口（暴露 KB 为外部 Agent 工具集） |

### 9.2 [C 类] 检索增强脚本

| 脚本 | 说明 |
|---|---|
| `relatedness_build.py` | 4 信号加权图 |
| `vector_build.py` / `vector_query.py` | LanceDB 向量索引 / ANN |
| `community_build.py` | Louvain 聚类 |
| `graph_insights.py` | 惊奇 / 空白 / 桥接，落 `_review/insights/` |

### 9.3 队列与缓存数据结构

```jsonc
// .ingest-queue/pending.jsonl —— 每行一个任务
{"id":"...","source":"raw/filings/X.pdf","enqueued_at":"...","retry":0}

// .ingest-cache/hashes.json
{
  "raw/filings/X.pdf": {
    "sha256": "abc...",
    "ingested_at": "2026-06-02T14:30:00Z",
    "wiki_pages": ["wiki/filings-summary/...", "wiki/companies/NVDA.md", ...]
  }
}
```

### 9.4 Git pre-commit hook

```bash
#!/bin/sh
python3 scripts/build_index.py --validate || exit 1
python3 scripts/graph_build.py
# [C 类] 若启用：python3 scripts/relatedness_build.py && python3 scripts/community_build.py
git add _index.json ontology/graph.jsonl ontology/relatedness.jsonl 2>/dev/null
```

---

## 10. `CLAUDE.md`（Agent 合同）

```markdown
# 金融理财 KB — Claude Code 操作手册

## 优先级
1. 任何操作前先读 [purpose.md](purpose.md)、[_schema.md](_schema.md)、[_areas-registry.md](_areas-registry.md)、[_capabilities.yaml](_capabilities.yaml)
2. 摄入 raw/ 必须走 finance-ingest 的两步 CoT，禁止单步直写 wiki
3. 写 wiki/* 时所有页必须有完整 frontmatter（含 sources[]）
4. 维护 [[wikilink]] 双向引用
5. 涉及 portfolio / thesis / decision 时尤其谨慎：这是个人决策档案，禁止杜撰数据
6. 写入 ontology 必须走 `scripts/graph_append.py`，**禁止**直接编辑 `graph.jsonl`
7. finance-research 必须先执行 Phase 0（KB 去重 + 提案确认），未确认禁止 WebSearch

## 归属判断（写入前必读）
- 不知道写哪个目录 → 查 [_areas-registry.md](_areas-registry.md) 决策树
- 边界模糊 / 临时性 → 先扔 [thoughts/_inbox/](thoughts/_inbox/)，48h 内归位

## 导航
- 内容目录：[wiki/index.md](wiki/index.md)
- 全局概要：[wiki/overview.md](wiki/overview.md)
- 操作日志：[wiki/log.md](wiki/log.md)
- 思考层入口：[thoughts/_MOC.md](thoughts/_MOC.md)
- 待审核：[_review/pending/](_review/pending/)
- [C 类] 图谱洞察：[_review/insights/](_review/insights/)
- 图遍历：`python3 scripts/graph_build.py traverse --from Company:NVDA --depth 2`
- 论点演化链：`python3 scripts/graph_build.py history --thesis <slug>`

## 检索策略
- grep [_index.json](_index.json) 找候选页
- ontology traverse 扩展邻居
- [C 类] 若启用 vector_search：合并向量命中
- 查论点时自动过滤 `status: superseded` / `invalidated`（除非用户明说要看历史）
- read 全文（不分 chunk）
- 答完询问是否 thesis-archive / decision-record / thought-capture

## 禁止
- 修改 raw/（不可变）
- 直接编辑 `ontology/graph.jsonl`（必须走 `graph_append.py`）
- 创建无 frontmatter 的 wiki / thoughts 页
- 杜撰财务数据 / 持仓数字 / 产品费率
- 修改 .ingest-cache/ / .ingest-queue/ / .kb-vectors/
- thoughts/ 写 `visibility: public`（默认且强制 private）
- 替用户给 thesis / idea 添油加醋（保持原话）

## 工具
- 校验：`python3 scripts/build_index.py --validate`
- 重建图快照：`python3 scripts/graph_build.py`
- 图写入：`python3 scripts/graph_append.py supersede --from <new> --by <old>`
- 级联清理：`python3 scripts/cascade_delete.py --path raw/...`
- 队列状态：`python3 scripts/queue_runner.py status`
- MCP server：`python3 scripts/mcp_server.py --transport stdio`
```

---

## 11. 实施路线图

| 阶段 | 工作量 | 产出 | 验收 |
|---|---|---|---|
| **P0 骨架** | 半天 | 目录（含 thoughts/）+ purpose.md + _schema.md + **_areas-registry.md** + CLAUDE.md + 15+ 页面模板（含 5 个 thought-*）+ build_index.py（含 `--validate --strict`） + Git pre-commit + .claude/skills/{company-page, thesis-archive} | 新建 NVDA.md 通过 `--validate`；pre-commit 拦截缺字段提交 |
| **P1 摄入 + Thoughts** | 1.5 天 | finance-ingest 两步 CoT + ingest_cache.py + 多格式提取 + earnings-summary + product-summary + **thought-capture + decision-record** + log/overview 维护 + **graph_append.py（append-only ontology）** | 扔一份真实 10-Q 跑出 ≥4 个互链 wiki 页；交互式录入一条 idea 落 thoughts/ideas/ |
| **P2 检索 + 维护** | 1 天 | ontology/schema.yaml（含 Thoughts 节点）+ graph_build.py（含 supersede 链回溯）+ ontology skill + **reflection skill** + lint-wiki（含 inbox 超时 / 失效论点 / decision review_at 到期）+ cascade_delete | `traverse Company:NVDA --depth 2` 出 4 层邻居；`history --thesis <slug>` 看 supersede 链；删 raw 自动清 wiki |
| **P3 自动化 + Phase 0** | 1 天 | watch_raw + queue_runner + _review/ 异步队列 + **finance-research（含强制 Phase 0：KB 去重 + 提案确认）** + Tavily/SerpApi/SearXNG | 新增 raw 文件自动入队；finance-research 在已有报告主题上自动建议复用而非重做 |
| **P3.5 [C 类] 检索增强** | 1 天 | vector_build.py + vector_query.py + kb-embed skill + relatedness_build.py + Query Stage 1.5/2b 集成 | 召回测试：开启前后对比，向量召回应能找到关键词覆盖不到的页 |
| **P4 [C 类] 图谱洞察** | 半天 | community_build.py + graph_insights.py + _review/insights/ + Insights → finance-research 触发链 | Louvain 输出社区；惊奇 / 空白 / 桥接清单可一键发起研究 |
| **P5 portfolio + 月度自动化** | 1 天 | portfolio-snapshot skill + 与基准对比 + 月度复盘自动化 + reflection 月报自动引用本月 decisions / thesis 变更 | 每月初自动生成持仓快照页 + 触发月度 reflection 草稿；review_at 到期的 decision 自动提醒 |
| **P6 MCP server** | 半天 | scripts/mcp_server.py + .claude/mcp-policy.yaml + 10 个 MCP tools + 权限校验 | 外部 Agent（Claude Desktop / Codex）能通过 MCP 查 KB；写决策类内容必经 _review/pending/ |

---

## 12. 与 Karpathy gist 的对照表

| Gist 要素 | 本方案落地 |
|---|---|
| Raw sources（不可变） | `raw/` 九类子目录（filings / research / transcripts / news / data / products / macro / statements / assets） |
| The wiki（LLM 写） | `wiki/` 十三类页面 + `thoughts/` 五类用户主观沉淀 |
| The schema | `CLAUDE.md` + `_schema.md` + `_areas-registry.md` + `_capabilities.yaml` |
| Ingest | `finance-ingest` 两步 CoT |
| Query | 5 阶段流水线（含可选向量 + 4 信号） |
| Lint | `lint-wiki` + 三个 validate 脚本 |
| index.md | `wiki/index.md` 自动维护 |
| log.md | `wiki/log.md` grep 友好 |
| `[[wikilink]]` | 全程强制 |
| YAML frontmatter | `_schema.md` 强校验 |
| Obsidian 兼容 | 是 |
| CLI 工具（qmd 类） | `scripts/` + ontology + 可选向量 |
| Web Clipper | Obsidian Web Clipper → `raw/news/` |
| Graph view | Obsidian Graph + 可选 llm_wiki App |
| Git 版本控制 | 是 |

---

## 13. 与 `~/code/llm_wiki/` App 的关系

- 本方案**不依赖**桌面 App
- App 仍可作为**可选可视化前端**：能打开任意 purpose/schema/raw/wiki 三层目录
- 想要交互式图谱时启 App 指向 `kb/`，**不冲突**（共享同一份 Markdown）

---

## 13.5 MCP Server 入口 — 给外部 Agent 用的工具集

> **定位：** 当 Claude Code 之外的 Agent（Finance_Agent 主体、其它 IDE、Claude Desktop、Codex、Cursor）需要访问本 KB 时，通过 MCP 协议暴露读写能力。Claude Code 直接读文件不需要 MCP，但**留这道口子**让 KB 成为多 Agent 可消费的知识层。

### 13.5.1 启动方式

```bash
# stdio 模式（本地 Agent 直连）
python3 scripts/mcp_server.py --transport stdio

# SSE 模式（远程 / 多客户端）
python3 scripts/mcp_server.py --transport sse --port 7878
```

### 13.5.2 暴露的工具（MCP tools）

| 工具名 | 作用 | 对应 Claude Code 内部能力 |
|---|---|---|
| `kb_search` | 关键词 + 元数据混合检索 | grep + `_index.json` 过滤 |
| `kb_read` | 按路径读 wiki / thoughts / raw 文件 | Read |
| `kb_vector_search`（[C 类]） | 语义近邻 | `vector_query.py` |
| `kb_graph_traverse` | typed graph 遍历 | `graph_build.py traverse` |
| `kb_graph_related` | 实体邻居 + [C 类] 4 信号关联 | `graph_build.py related` |
| `kb_get_thesis` | 取指定 thesis 当前状态 + 演化链（supersedes 链路） | 读 + 图回溯 |
| `kb_get_portfolio` | 取最新 portfolio-snapshot | 按 `as_of` 排序读 wiki/portfolio/ |
| `kb_ingest_enqueue` | 把 raw 文件入摄入队列 | append `.ingest-queue/pending.jsonl` |
| `kb_append_thought` | 创建 thought（idea / question / decision / reflection） | 调 `thought-capture` 等价逻辑 |
| `kb_lint` | 触发健康巡检并返回报告 | `lint-wiki` Skill |

### 13.5.3 权限模型

`scripts/mcp_server.py` 启动时读 `.claude/mcp-policy.yaml`：

```yaml
allow_read:  [wiki/, thoughts/, ontology/, _index.json, purpose.md]
allow_write: [thoughts/_inbox/, .ingest-queue/pending.jsonl, _review/pending/]
deny_write:  [raw/, wiki/, ontology/graph.jsonl]   # 写 ontology 必须经 graph_append.py
require_human_review:
  - thoughts/decisions/    # 决策类内容写入需要 _review 走人审
  - wiki/theses/           # thesis 不允许外部 Agent 直写
```

外部 Agent 想写决策/论点 → 落 `_review/pending/`，由 Claude Code 主会话人工确认后才进 wiki/。

### 13.5.4 价值

- Finance_Agent 主体（无论是 LangGraph / 自研 Agent / 还是另一个 Claude Code 会话）能查询本 KB
- 多 Agent 协作：研究 Agent 写 thoughts/ideas/，决策 Agent 读 ideas 出 thoughts/decisions/，执行 Agent 读 decisions 触发外部交易系统
- 暴露面受控：raw / wiki / ontology 写入永远走 Skills + 审核队列，避免外部 Agent 污染权威数据

---

## 14. 能力清单审核（回答你上一条问题）

你列举的 8 项能力在本方案中的支持状态：

| # | 能力 | 支持 | 类型 | 章节 | 实现要点 |
|---|---|---|---|---|---|
| 1 | **SHA256 增量缓存** | ✅ | B 基础 | §6.1 Step 0 / §9.3 | `.ingest-cache/hashes.json` 摄入前查重，未变跳过 |
| 2 | **持久化摄入队列 + 自动重试** | ✅ | B 基础 | §9.1 `queue_runner.py` / §9.3 | `.ingest-queue/{pending,processing,failed}.jsonl`，失败重试 ≤3 次 |
| 3 | **Source 文件夹自动监听** | ✅ | B 基础 | §9.1 `watch_raw.py` | `fswatch raw/` → 自动入队 + 删除触发 cascade_delete |
| 4 | **审核队列（异步人机协作）** | ✅ | B 基础 | §2 `_review/pending/` / §6.1 Step 1 | LLM 标记 review_items + predefined actions + 预生成搜索查询 |
| 5 | **Deep Research 闭环** | ✅ | B 基础 | §8 `finance-research` / §11 P3 | Tavily/SerpApi/SearXNG → 综合 → 自动走 finance-ingest 回灌 |
| 6 | **多格式结构化提取** | ✅ | B 基础 | §6.1 Step 0 | PDF (pymupdf/pdfplumber 保留表格) / DOCX (python-docx) / PPTX / XLSX / HTML |
| 7 | **图谱洞察（惊奇 / 空白 / 桥接）** | ✅ | **C 可选** | §7.4 / §9.2 `graph_insights.py` | 依赖 4 信号 + Louvain，输出到 `_review/insights/`，可一键喂 finance-research |
| 8 | **向量搜索（LanceDB）** | ✅ | **C 可选** | §7.3 / §9.2 `vector_build.py` + `vector_query.py` / §6.2 Stage 1.5 | 默认关闭；启用后 ingest 自动 embedding，Query Stage 1.5 余弦 ANN |

**默认状态**：1-6 永远启用（B 类基础）；7-8 默认关闭，规模上来或召回不足时通过 `_capabilities.yaml` 开关启用（零代码改动）。

附加保留的 C 类能力：**4 信号关联度**（§7.2）+ **Louvain 社区检测**（§7.4）也都已支持。

---

## 15. 一句话总结

> **三层 + 三操作 + purpose + 两步 CoT + sources 级联 + typed ontology（append-only）+ 持久化队列 + 审核队列 + Deep Research 回灌（强制 Phase 0）+ 多格式提取**
> 是基础。
>
> **Thoughts 五子模块（ideas / questions / decisions / reflections / todos）+ thesis 生命周期（supersedes 链）+ _areas-registry 归属决策树 + Skill 双语精确触发 + MCP server 外部入口**
> 让 KB 从"研报库"升级为"投资决策档案 + 多 Agent 协作底座"。
>
> **向量搜索 + 4 信号关联度 + Louvain + 图谱洞察**
> 是 `_capabilities.yaml` 一键启用的增强。
>
> 全程 Claude Code 原生，无 App、无 HTTP API、无重复造的聊天。
