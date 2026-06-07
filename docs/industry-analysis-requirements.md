# Skill 需求：industry-analysis（A/HK/US 跨市场行业分析）

> 版本 v0.7 · 2026-06-04 · 状态：**第一版锚定 = fork Anthropic 骨架 + 极简本土化**，远期规划保留
> **第一版骨架来源**：[anthropics/financial-services](https://github.com/anthropics/financial-services) @ `120a31d`（Apache 2.0）→ 详见 [anthropic-skills-appendix.md](anthropic-skills-appendix.md) **附录 A**
> 参考实现：`OpenClaw_FinRobot/finrobot/agents/coordinator/skills/industry-analysis/`、`market-agent/skills/industry-analysis/scripts/industry_analysis.py`、`shared/data_fetcher.py`、`report-agent/templates/industry_report.md`
> 调研：`iKnowledge/Reports/Finance/industry-analysis-module-survey.md`、`ai-industry-chain-investment-agent-survey.md`、`a-share-stock-analysis-skills.md`

## 〇、第一版极简锚定（v0.7）

**核心策略**：第一版 = **fork Anthropic `sector-overview` Skill 骨架 + 5 处本土化注入**，把所有差异化护城河（跨市场 / ontology / 4 分镜 / 8 红旗 / 完整防腐工具栈）**推到 P1+**。目标是"1 周内端到端跑通'分析半导体'，出一份合格的 `wiki/sectors/半导体.md`"，而非一次做出完美方案。

### 第一版（P0）in scope

- ✅ Fork [附录 A.4](anthropic-skills-appendix.md) 列出的 7 个 Anthropic 资产到 `.claude/skills/industry-analysis/references/`
- ✅ **A 股单一市场**（HK/US 推到 P1）
- ✅ **单一 Subagent** `industry-collector-cn`，套 `sector-reader.yaml` 的 `output_schema` 模式
- ✅ 接入 **`cn-financial-mcp` 单 MCP**（其他 MCP 推到 P1+）
- ✅ 沿用 Anthropic `sector-overview` **6 步工作流**（不引入八维度 / 4 分镜的新结构）
- ✅ 注入 5 处本土化（见第十七节 P0 详表）
- ✅ 输出 `wiki/sectors/<slug>.md`（完整 frontmatter + sources[] + wikilinks）

### 第一版（P0）out of scope

| 推后到 | 内容 |
|---|---|
| **P1** | HK/US Subagent + 跨市场 crosswalk + `cross_market_peers[]` |
| **P2** | 5 类 ontology 边（supplies / packaged_by / ...）+ 4 分镜 CoT-1 + 行业基准表（feiyuggg）+ rotation_phase.py + red_flags.py 双轨 |
| **P3** | 13F / 事件传导 / 雪球 scraper / pptx-author |
| **永不做** | SQLite industry_store / 飞书 `<font color>` / OpenClaw IDENTITY-SOUL-HEARTBEAT 四件套 |

### 阅读指南

- 看第一版（P0）实现 → 只读 [〇](#零第一版极简锚定v07)、[一](#一目标)、[十七](#十七实施-phase-优先级)、[附录 A](anthropic-skills-appendix.md)
- 看远期方案/护城河设计 → 读 [二](#二形态决策skill--并行-subagent非纯多-agent--非纯单-skill)~[十六](#十六finrobot-复用清单已实地验证可用)（这些是 P1+ 的目标态参考，第一版不实施）

### v0.6 → v0.7 关键变化

| 章节 | v0.6 | v0.7 |
|---|---|---|
| 第一版 P0 范围 | fork + 8 维度 + 5 ontology 边 + 骨架/结论分离 + FinRobot 完整防腐 | **只 fork + 6 步 + 1 个 Subagent + 1 个 MCP + 5 处本土化** |
| 三市场 | P0 设计 cn/hk/us 三 Subagent | **P0 只做 cn**，hk/us 移到 P1 |
| 防腐工具 | P0 拷 6 工具 + molezzz 字段层 | **P0 只拷 `safe_float` + `safe_call` 2 个**，其他移到 P2 |
| 8 维度 | P0 全做 | **P0 对齐 Anthropic 6 步**，八维度作为 P2 演进目标 |
| ontology 5 边 | P0 落地 | **P0 不做**，移到 P2 |

## 一、目标

为 Knowledge_Wiki 补一条 **A 股 / 港股 / 美股 三市场行业分析** 能力（**第一版只做 A 股**），输出落到 `wiki/sectors/<slug>.md`，沉淀产业链结构、龙头股、估值分位、轮动阶段、景气信号，与 `wiki/companies/` `wiki/theses/` `wiki/comparisons/` 双向 wikilink。**主要解决**：当前仅有个股画像（NVDA 单页），缺少行业层抓手，无法做自上而下赛道筛选与跨市场传导分析。

## 二、形态决策：Skill + 并行 Subagent（非纯多 Agent / 非纯单 Skill）

> **第一版（P0）**：Skill + **1 个** Subagent（仅 cn）。三 Subagent 并行 dispatch 是 P1 目标态。下表与第七节"5 Phase 工作流"是 P1+ 的描述，第一版只走 [Anthropic 6 步](#a61-sector-overview-skill).

```
L0  Skill `industry-analysis`             ← 流程编排 + 两步 CoT 推理（主上下文）
L1  Subagent `industry-collector-{cn|hk|us}` ← 三市场并行采集（context 隔离）
L2  MCP 矩阵                               ← 数据接入（Subagent 内调用）
L3  纯脚本（snapshot_store / red_flags / rotation_phase / taxonomy_mapper）
```

**决策对照**：

| 方案 | 取舍 |
|---|---|
| 纯多 Agent（FinRobot/OpenClaw 模式）| ⚠️ 部分过度工程，但其"骨架/结论分离"与"Schema 字段禁止变更表"**单 Skill 形态也需要**，应保留思想、降低形态复杂度（详见第十六节-甲/乙）|
| 纯单 Skill（finance-ingest 模式）| ❌ 三市场 ×10 维度数据塞主上下文会炸 token，且无法并行 |
| **Skill + 并行 Subagent** | ✅ 主 Skill 只收摘要，Subagent 隔离重 context；复用 finance-ingest 两步 CoT 范式 |

**Claude Code 机制利用**：单消息内同时发起 3 个 Subagent 调用 → 三市场并行采集；Subagent 扁平不嵌套（官方约束），正好够用。

## 三、跨市场分类体系

> **第一版（P0）**：只用 **申万一级 31 行业**（直接从 FinRobot `coordinator/skills/industry-analysis/SKILL.md:17` 拷贝行业名表 + 模糊匹配代码到 `wiki/sectors/_taxonomy.md` 的 cn 部分）。GICS/HSIII 与 crosswalk 是 P1 内容，**第一版不写**。

| 市场 | 一级分类 | 首选 MCP | 数量 |
|---|---|---|---|
| A 股 | 申万一级 | `cn-financial-mcp` / `akshare-one-mcp` | 31 |
| 港股 | 恒生行业 HSIII | `Longbridge MCP` / `akshare-one-mcp` | 12 |
| 美股 | GICS Sector / Industry Group | `Finnhub MCP` / `FMP MCP` | 11/25 |

`wiki/sectors/_taxonomy.md` 同时承载 **三市场 crosswalk + 行业基准表**（feiyuggg 模式：每行业一组 PE/PB/ROE/毛利率"正常区间"），解决"PE 22 算高还是低"无锚问题。crosswalk 例：半导体 ↔ 电子 ↔ Technology/Semiconductors，NVDA 涨跌可映射沪电股份/中芯国际。

**数据集导入路径**（A5）：
- **GICS 4 层完整 JSON**（11 sector × 25 industry group × 74 industry × 163 sub-industry）：直接抄 GitHub Gist [`uknj/c9bcf66ab379a35fcc8758f9a6c86ceb`](https://gist.github.com/uknj/c9bcf66ab379a35fcc8758f9a6c86ceb)（2023-03-17 版本），本地拷贝锁版本
- **申万 31 一级 + 港股通扩展**：从申万官网 PDF 导出（2020-07 后版本，含 A 股 + 港股通统一分类）
- **HSIII 12 大类**：从恒生指数公司官网手抄（公开生态无开源 dump）
- **crosswalk 中间映射层**：用 **GICS Industry Group 25** 作为中间层（粒度最接近申万一级 + HSIII，避免直接三对三互查的组合爆炸）

## 四、数据接入层：MCP 矩阵 + AKShare 兜底

| 用途 | 首选 MCP | 备份 / 兜底 |
|---|---|---|
| A 股深度（**P0 接**）| **`cn-financial-mcp`**（42 tools，自带 AKShare→东财→新浪→腾讯→同花顺多源 fallback）| AKShare via `uv run` |
| A/H/U 统一报价 | `akshare-one-mcp`（唯一三市场覆盖）| `Tiger MCP` |
| 港股交易级 | `Longbridge MCP`（110 tools）| `akshare-one-mcp` |
| 美股新闻/催化剂 | `Finnhub MCP` | `Yahoo Finance MCP` |
| 美股基本面 | `FMP MCP` | `Yahoo Finance MCP` |
| 美股 filings / 13F | `SEC EDGAR MCP` | — |
| 聚合层（可选） | `openbb-mcp-server`（discovery-based 激活）| — |

**P0 唯一接 `cn-financial-mcp`**，其余按 Phase 推进。自写脚本只保留 4 个无 MCP 对应的小模块：snapshot_store / taxonomy_mapper / rotation_phase / red_flags。

**数据优先级硬约束**（B3，借鉴 Anthropic 官方 `comps-analysis` Skill）：

| 优先级 | 数据源 | 适用情形 |
|---|---|---|
| **P1** | MCP（cn-financial / Longbridge / Finnhub / FMP / SEC EDGAR / akshare-one） | 默认首选 |
| **P2** | AKShare via `uv run` 直调 | MCP 失败时兜底 |
| **P3** | WebSearch / WebFetch | **仅 MCP + AKShare 全部失败时使用**，且必须在输出 JSON 的 `_meta.fallback_to_web_search = true` 标记审计 |

**禁止**：行业资金流 / 估值分位 / 龙头股市值 / PE/PB 等数值字段从 WebSearch 提取（精度不可靠）。WebSearch 仅可用于"景气与政策""新闻"等定性字段。

## 五、八维度数据模型

| # | 维度 | 数据形态 | 责任方 |
|---|---|---|---|
| 1 | 产业链结构 | 上游→中游→下游节点 + 跨市场对应 | 主 Skill（ontology + WebSearch + asset-describe）|
| 2 | 龙头股排名 | TOP10 按市值/营收/份额 | **Subagent**（市场对应）|
| 3 | 估值横向对比 | PE/PB/股息率 + 行业基准对照 | **Subagent** |
| 4 | 估值历史分位 | 3 年 PE/PB 分位数 | **Subagent**（读本地 jsonl）|
| 5 | 行情与资金 | MA/涨跌/主力净流入/北向（A 股）| **Subagent** |
| 6 | 轮动阶段 | 强势/新兴/衰退/底部 | **Subagent**（调 rotation_phase.py）|
| 7 | 景气与政策 | PMI/产能/订单 + 监管 + 地缘 | 主 Skill（知识库 grep + WebSearch + Finnhub 新闻）|
| 8 | 竞争格局 + 风险红旗 | CR3/CR5 + 毛利趋势 + 8 红旗 | **Subagent**（调 red_flags.py）|

维度 2-6、8 = Subagent 内结构化采集；维度 1、7 = 主 Skill CoT-1 综合。**8 红旗**（应收暴增/现金流背离/存货堆积/毛利异常/审计师变更/关联交易/商誉减值/对赌）放龙头股 quick-check。

## 六、关键 trick：**「骨架先填数值，结论后补」**（抄自 FinRobot）

FinRobot 实战验证的反幻觉 pattern：

```
Phase 1  Subagent 输出 JSON 骨架，所有数值字段填实，结论字段为空：
         { pe_ttm: 22.3,  judgment: ""    ← Subagent 不写
           pct_chg_5d: 2.3, trend: ""     ← Subagent 不写
           score: null,    conclusion: "" }

Phase 3  CoT-2 在骨架基础上**只补结论字段，禁止改任何数值**：
         { pe_ttm: 22.3,  judgment: "估值3年65分位..."  ← LLM 写
           pct_chg_5d: 2.3, trend: "多头排列..."        ← LLM 写
           score: 72,      conclusion: "..."         }
```

→ 数值层与判断层强分离 = LLM 想编也编不了数。

CoT-1 的"4 分镜"（policy/valuation/capital/sentiment）落到 `judgment` 字段内嵌结构，借 oficcejo 智策板块拆解：

```json
{ "valuation": { "pe_ttm": 22.3, ..., "judgment": {
    "policy": "...",     "valuation": "...",
    "capital": "...",    "sentiment": "..." }}}
```

CoT-2 融合骨架 + 4 分镜 + 维度 1 产业链结构 → sector 页正文。

### Phase 2 analyst-agent 完整 prompt 模板（B2，拷自 FinRobot SKILL.md L88-114）

```
请在骨架基础上补充以下空字段（禁止修改已有数值）：

[必须补充的 11 个空字段]
- score (int 0-100)
- conclusion (string)
- valuation.judgment (string)
- trend.direction / trend.support / trend.resistance / trend.judgment (string)
- top_stocks[].highlight (每只股票一句话亮点)
- fund_flow.main_trend / fund_flow.institution (基于 _data 中的数值写文字描述)
- prosperity.* (level / macro / supply_demand / policy / evidence[])
- competition.* (leaders[] / summary / margin_trend)
- risks (数组，每条必须是 {level: "高|中|低", content: string} 结构)
- research_highlights.* (summary / sources[] / cross_validation)
- advice.* (position_strategy / stock_selection / risk_control)

[字段名严格约束 — 禁止变体]
- score 禁止变为 {overall: N} 对象
- risks 禁止变为 string[]，必须 {level, content}[]
- top_stocks[].symbol 禁止用 code 字段名
- top_stocks[].pct_chg 禁止用 change_1d / change_120d 等变体
- valuation.pe_ttm / pe_percentile_3y / pe_rank_in_31 字段名禁止漂移
- trend.pct_chg_5d / pct_chg_20d / pct_chg_60d 字段名禁止漂移
- 数值字段禁止从 number 变为 string（如 "22.3" 而非 22.3）

[输出契约]
输出完整 JSON（含骨架中已有的数值字段 + 你补充的结论字段），去掉 _data 和 _meta 字段。
JSON 顶层必须含 type: "industry_analysis"。
```

→ 完整可拷贝 prompt 见 `OpenClaw_FinRobot/finrobot/agents/coordinator/skills/industry-analysis/SKILL.md` L40-114，含 "禁止变更字段类型表" 完整版。

## 七、Skill 工作流（5 Phase）

```
触发词：「分析 X 行业」「X 板块画像」「半导体产业链」「行业对比 A vs B」
  ↓
Phase 0  归属确认 + KB 去重 + taxonomy crosswalk 解析（主 Skill）
  ↓
Phase 1  【单消息内并行 dispatch 3 个 Subagent】
         ├── industry-collector-cn  →  采集 A 股维度 2-6,8 → 写 jsonl
         ├── industry-collector-hk  →  采集 港股维度 2-6,8 → 写 jsonl
         └── industry-collector-us  →  采集 美股维度 2-6,8 → 写 jsonl
         三个 Subagent 各自返回 ≤200 行摘要回执到主上下文
  ↓
Phase 2  主 Skill 补维度 1（产业链结构 / ontology grep）+ 维度 7（景气政策 / WebSearch）
  ↓
Phase 3  CoT-1 输出 4 分镜 JSON 草稿
  ↓
Phase 4  CoT-2 生成 wiki/sectors/<slug>.md（完整 frontmatter + sources[] + wikilinks）
  ↓
Phase 5  ontology graph_append.py 写 5 类新边 + 询问是否触发 thesis-archive / company-page
```

## 八、Subagent 边界定义（`.claude/agents/industry-collector-*.md`）

每个 Subagent 独立 system prompt，限定职责：

| 字段 | 内容 |
|---|---|
| **可用 MCP** | 仅市场对应的 MCP（cn 用 cn-financial / akshare；hk 用 Longbridge / akshare；us 用 Finnhub / FMP / EDGAR）|
| **可用脚本** | `snapshot_store.py` `rotation_phase.py` `red_flags.py` `taxonomy_mapper.py` |
| **禁止** | 调用 WebSearch / 写 wiki/ / 写 ontology / 跨市场调用 |
| **输出契约** | 落盘 `raw/data/industry-snapshots/<market>/<slug>-YYYYMMDD.jsonl`，返回摘要含 jsonl 路径 + 关键数字 ≤200 行 |
| **失败策略** | 单一字段失败标 `null`，整体失败返回 `{status: "partial", missing: [...]}` |

## 九、ontology 扩展（差异化护城河）

公开生态无任何产业链关系图谱。本 Skill **P0 新增 5 种边**到 [ontology/graph.jsonl](Knowledge_Wiki/ontology/graph.jsonl)：

| 边类型 | 语义 | 例 |
|---|---|---|
| `supplies` | A 向 B 供货 | ASML → TSM（EUV）|
| `packaged_by` | A 由 B 封装 | NVDA-B200 → TSM-CoWoS |
| `uses_component` | A 用了 B 组件 | GB200 → HBM3e |
| `benefits_from` | A 受益于 B 主题 | 中际旭创 → AI-Optical-Demand |
| `exposed_to` | A 暴露在 B 风险/需求 | 工业富联 → NVDA-OEM-Demand |

→ 让 NVDA earnings 自动推导出 A/H 衍生受益标的，是 sector 页之上的元能力。

## 十、wiki/sectors 页结构

frontmatter 必含：`type: sector` / `market: cn|hk|us` / `taxonomy_code`（`SW:801080` / `HSIII:11` / `GICS:45`）/ `cross_market_peers[]`（跨市场对位 wikilink）/ `as_of` / `sources[]` / `leaders[]` / `upstream[]` / `downstream[]` / `rotation_phase` / `status`。正文 8 节对齐数据模型，公司提及强制 `[[companies/TICKER]]`。

## 十一、持久化与历史回溯

- **快照** `raw/data/industry-snapshots/<market>/<slug>-YYYYMMDD.jsonl`：Subagent ↔ 主 Skill 的状态总线 + 历史序列
- **历史分位**：≥30 条启用分位计算，否则标 `pending_accumulation`
- **去重**：同 slug 24h 内复用最新快照，`--force` 强刷
- **绕过 finance-ingest**：机器采集非源材料，不进两步 CoT 摄入流程

## 十二、防腐与可维护性（FinRobot 完整工具栈 + molezzz 字段层 fallback）

所有字段抽取强制走分层封装，**共用工具区**写到 `taxonomy_mapper.py`：

**FinRobot 6 工具组合**（B1，拷自 `OpenClaw_FinRobot/finrobot/shared/data_fetcher.py` L52-575 与 `industry_analysis.py` L55-92）：

- `safe_float(val, default=None)` — 处理 None / NaN / "-" / "--" / "nan" / "" 等 AKShare 垃圾值，限定精度 `round(f, 4)`
- `safe_int(val, default=None)` — 复用 safe_float
- `safe_call(fn, *args, max_retries=1, label="", **kwargs)` — 指数退避 + 随机抖动 + 日志标签，统一替代各脚本中重复的 `_safe_call`
- `normalize_stock_code(stock_code: str) -> str` — A/H/U 三市场代码标准化，特别处理 `HK1810 → HK01810` 5 位补零、`.SH/.SZ/.HK` 后缀剥离
- `CircuitBreaker` 类 — 熔断器降级（防止上游接口反复失败拖垮整个 Subagent）
- `_kline_fallback_chain` — 多数据源优先级链（K 线 / 估值 / 资金流分别独立 fallback chain）

**molezzz 字段层 fallback**（保留，与 FinRobot 工具栈不重叠）：

- `_call_api_candidates([(tool, kwargs), ...])` — 多候选 MCP tool fallback，应对接口改名
- `_pick(item, keys_list)` — DataFrame/JSON 字段多候选提取，应对返回结构漂移

**调用约束**：
- 所有数值字段提取必须走 `safe_float` / `safe_int`
- 所有外部 API 调用必须走 `safe_call`
- 所有股票代码字段必须先经 `normalize_stock_code` 标准化再使用
- DataFrame 列名提取必须走 `_pick` 避免列名漂移

## 十三、与既有 Skill 协作

| Skill | 协作点 |
|---|---|
| `finance-ingest` | sector 引用研报 → 先 ingest → 再被 `sources[]` 引用 |
| `company-page` | 龙头股未建页 → 批量建 stub |
| `thesis-archive` | sector 判断达 thesis 级 → 沉淀 `wiki/theses/` |
| `asset-describe` | 产业链图/份额饼图截图先 caption 缓存再嵌入 |
| `wiki/queries/` | 沉淀"如何完成跨市场行业对比"操作手册（OpenBB Skill-Guides 模式）|

## 十四、约束与禁止

1. **禁止杜撰** 份额/营收/估值，缺失字段 `null` 不补 LLM 估计
2. **禁止跳过** Phase 0 去重 — 同名 sector 必须走 supersede
3. **跨市场不混表** — A/H/U 各自独立 frontmatter，跨市场对比走 `wiki/comparisons/`
4. **MCP 多源 fallback** — 首选失败回退备份，再失败标 `_source: unavailable`，不编造
5. **Subagent 严守边界** — 不写 wiki / 不写 ontology / 不调 WebSearch
6. **首版不接** vector_search / 4 信号关联度（_capabilities 默认关闭）
7. **港股 L2 / 美股期权 OI 空白接受** — 公开生态无开源方案，不强求

## 十五、交付物清单

**Skill 容器**
- `.claude/skills/industry-analysis/SKILL.md`
- `.claude/skills/industry-analysis/references/mcp-matrix.md`（MCP tool 速查 + fallback 链）
- `.claude/skills/industry-analysis/references/cot-prompts.md`（4 分镜 CoT-1 / sector 页 CoT-2 模板）

**Subagent 定义**
- `.claude/agents/industry-collector-cn.md`
- `.claude/agents/industry-collector-hk.md`
- `.claude/agents/industry-collector-us.md`

**共享脚本**
- `.claude/skills/industry-analysis/scripts/snapshot_store.py`（jsonl + 分位）
- `.claude/skills/industry-analysis/scripts/taxonomy_mapper.py`（三市场 crosswalk + 防腐两层）
- `.claude/skills/industry-analysis/scripts/rotation_phase.py`（QuantsPlaybook 因子裁剪）
- `.claude/skills/industry-analysis/scripts/red_flags.py`（**双轨实现**，A3）：
  - **量化轨**：抄 [WongYC19/QuickView](https://github.com/WongYC19/QuickView) 的 Python 实现：
    - **Beneish M-Score（8 比率）**：DSRI / GMI / AQI / SGI / DEPI / SGAI / TATA / LVGI — 盈利操纵检测，正好 8 个
    - **Altman Z-Score**（5 比率）：破产风险
    - **Piotroski F-Score**（9 项 0-1）：财务健康度
    - 替换数据源为 AKShare 财务数据；返回 `{model, score, flag_level, ratios: {...}}`
  - **定性轨**：v0.4 原 8 红旗（应收暴增/现金流背离/存货堆积/毛利异常/审计师变更/关联交易/商誉减值/对赌）作为 SOUL.md / SKILL.md prompt 中的 LLM 推理 checklist
  - CLI：`red_flags.py --ticker <code> --mode quantitative|qualitative|both`

**KB 层补丁**
- `Knowledge_Wiki/templates/sector.md` 增补 cross-market + rotation_phase + 8 维度章节
- `Knowledge_Wiki/wiki/sectors/_taxonomy.md` 三市场分类 + 行业基准表
- `Knowledge_Wiki/_areas-registry.md` 补 sector 跨市场决策分支
- `Knowledge_Wiki/ontology/schema.yaml` 新增 5 种边类型定义

## 十六-甲、Anthropic 官方 `financial-services` 仓库映射（A1）

> 仓库：[anthropics/financial-services](https://github.com/anthropics/financial-services)（2026-05-05 发布，Apache 2.0）
> 定位：机构级金融 Agent 模板，Claude Code 原生 Skill / Subagent / Agent 三层架构
> **v0.6 重要更新**：从"方法论参照"升级为"**第一版 Skill 骨架来源**"——SKILL.md 全文已克隆到 `/tmp/anthropics-financial-services/`，fork 清单与本土化路径详见 [`anthropic-skills-appendix.md`](anthropic-skills-appendix.md) **附录 A**

### `sector-overview` Skill 6 步 ↔ 本 Skill 八维度字段映射

| Anthropic 6 步 | 本 Skill 八维度对应 |
|---|---|
| 1. Scope Definition | Phase 0 归属确认 + taxonomy crosswalk 解析 |
| 2. Market Overview（TAM + 行业结构 + secular drivers + risks + disruption） | 维度 1（产业链结构） + 维度 7（景气与政策） |
| 3. Competitive Landscape（TOP 玩家表格 + 竞争方式 + 强弱） | 维度 2（龙头股排名） + 维度 8（竞争格局） |
| 4. Valuation Context（sector 倍数 + 溢价/折价 + 近期 deal multiples） | 维度 3（估值横向对比） + 维度 4（估值历史分位） |
| 5. Investment Implications（机会 + 主题 + 争论 + catalyst） | CoT-2 综合结论 + advice 字段 |
| 6. Output（Word / PPT + 图表） | wiki/sectors/<slug>.md（Obsidian 渲染） |

### 11 个 MCP 连接器速查（机构级数据源，未来如需融合可对接）

| Provider | 端点 | 主要用途 |
|---|---|---|
| Daloopa | `mcp.daloopa.com/server/mcp` | Comps、行业倍数、可比公司筛选 |
| Morningstar | `mcp.morningstar.com/mcp` | 股票研究、同业分析、sector data |
| S&P Global / Kensho | `kfinance.kensho.com/integrations/mcp` | 行业 tear sheet、财报预览、市场数据 |
| FactSet | `mcp.factset.com/mcp` | 基本面、同业倍数、行业基准 |
| Moody's | `api.moodys.com/genai-ready-data/m1/mcp` | 信用分析、行业风险评估 |
| MT Newswires | `vast-mcp.blueskyapi.com/mtnewswires` | 市场情绪、行业新闻 |
| Aiera | `mcp-pub.aiera.com` | 财报电话会议转录、sector commentary |
| LSEG | `api.analytics.lseg.com/lfa/mcp` | 债券 RV、外汇 carry、宏观、sector 监测 |
| PitchBook | `premium.mcp.pitchbook.com/mcp` | M&A 先例、买方宇宙、deal flow |
| Chronograph | `ai.chronograph.pe/mcp` | 组合基准、同业表现 |
| Egnyte/Box | 文档存储 | 内部研究、专有分析 |

**注**：11 个全部机构付费数据源，免费用户无法直接接入。本 Skill 选择 `cn-financial-mcp` + AKShare + Longbridge + Finnhub + FMP 是面向个人 / 开源的镜像路线，**预先建立此映射便于未来如需机构级数据源时无架构重构成本**。

### 关键差异化护城河确认

| 维度 | Anthropic 官方 | 本 Skill v0.5 |
|---|---|---|
| 跨市场（A/H/U） | ❌ 仅 GICS 美股逻辑 | ✅ 三市场 crosswalk + 行业基准表 |
| 产业链 ontology 关系图谱 | ❌ 无产业链建模 | ✅ 5 种边（supplies / packaged_by / uses_component / benefits_from / exposed_to） |
| 个人 / 开源数据源 | ❌ 11 MCP 全部付费 | ✅ AKShare + 开源 MCP 矩阵 |
| 知识库双向 wikilink | ❌ Word/PPT 输出 | ✅ Obsidian wikilink |

→ **第三节 + 第九节 + 知识库 wikilink 是本 Skill 相对 Anthropic 官方的最大差异化优势，应优先级最高、设计最充分。**

## 十六-乙、oficcejo/aiagents-stock 4 Agent 借鉴（A2）

> 项目：[oficcejo/aiagents-stock](https://github.com/oficcejo/aiagents-stock)（1,393 stars，2026-04 仍活跃）
> 定位：**公开开源生态唯一端到端可借鉴的板块多 Agent 实现**
> 关键文件：`sector_strategy_data.py` / `sector_strategy_agents.py` / `sector_strategy_engine.py`

### 4 Agent ↔ 本 Skill 八维度映射

| oficcejo 4 Agent | 本 Skill 维度对应 | 输入 | 关注点 |
|---|---|---|---|
| 宏观策略师 / Macro Strategist | 维度 7（景气与政策） | market_data + news_data | 3-5 条最重要新闻、利好利空判断 |
| 板块诊断师 / Sector Diagnostician | 维度 3 + 维度 4（估值） + 维度 2（龙头） | sectors_data + concepts_data + market_data | 最强 5 板块（涨幅 + 换手 + 领涨股）、估值合理性 |
| 资金流向分析师 / Fund Flow Analyst | 维度 5（行情与资金） | fund_flow_data + north_flow_data + sectors_data | 主力净流入 TOP5 + 北向 + 推荐 3-5 强势板块 |
| 市场情绪解码员 / Sentiment Decoder | CoT-1 sentiment 分镜 | market_data + sectors_data + concepts_data | 情绪 0-100 分量化 + 涨停数 + 最热 3-5 概念 |

→ oficcejo 4 Agent 与本 Skill 的"4 分镜（policy / valuation / capital / sentiment）"**逻辑同构**：oficcejo 是 4 个并行对等 Agent；本 Skill 是单 Subagent 内 `judgment` 字段下的 4 个子字段，形态不同但语义一致。

### 强制 JSON 三段输出（候选 `rotation_phase.py` / 综合结论结构）

```json
{
  "long_short": {
    "bullish": [{"sector": "...", "direction": "...", "reason": "...", "confidence": "...", "risk": "..."}],
    "bearish": [...], "neutral": [...]
  },
  "rotation": {
    "current_strong": [{"sector": "...", "stage": "leading|improving|...", "logic": "...", "time_window": "...", "advice": "..."}],
    "potential": [...], "declining": [...]
  },
  "heat": {
    "hottest": [{"sector": "...", "score": 85, "trend": "...", "sustainability": "..."}],
    "heating": [...], "cooling": [...]
  },
  "summary": {
    "market_view": "...", "key_opportunity": "...", "major_risk": "...", "strategy": "..."
  }
}
```

→ **可作为 CoT-2 综合结论字段或 `rotation_phase.py` 的输出契约候选参考**（A4 已 Reject，但本结构仍可作为 sector 页"综合结论"小节的 schema 参考）。

### 7 个 AKShare 函数名速查（A 股侧补 cn-financial-mcp 兜底）

```python
# 板块数据
stock_board_industry_name_em        # 东财行业板块列表
stock_board_concept_name_em         # 东财概念板块列表
stock_sector_fund_flow_rank         # 行业资金流排名

# 全市场快照
stock_zh_a_spot_em                  # A 股实时行情
stock_zh_index_spot_em              # A 股指数行情
stock_hsgt_fund_flow_summary_em     # 沪深港通资金流汇总（北向）

# 新闻
stock_news_em                       # 东财个股/板块新闻
```

→ 当 `cn-financial-mcp` 失败时，industry-collector-cn Subagent 直接 `uv run` 调 AKShare 这 7 个函数兜底。

## 十六、FinRobot 复用清单（已实地验证可用）

| 资产 | FinRobot 路径 | 复用方式 |
|---|---|---|
| **骨架先填数值，结论后补** 工作流 | `coordinator/skills/industry-analysis/SKILL.md` Phase 1-2 | **最高价值**。直接套用为本 Skill Phase 1+3 |
| **industry_analysis JSON Schema** | 同上 line 40-72 含"禁止变更字段类型表" | 拷进 `cot-prompts.md`，加 `market` `cross_market_peers[]` |
| **Subagent task prompt 模板** | 同上 Phase 1-3 spawn 块 | "传骨架 + 上下文 → 只补 X/Y/Z 字段"范式套用 |
| `safe_float` / `safe_int` / `_retry_call` / `normalize_stock_code` | `shared/data_fetcher.py:52-100` + `industry_analysis.py:55-91` | **整段拷贝**到 `taxonomy_mapper.py`，最后一个支持 `HK01810` 港股代码归一化 |
| **申万 31 行业名称表 + 模糊匹配** | `coordinator/skills/industry-analysis/SKILL.md:17` | 直接落 `wiki/sectors/_taxonomy.md` 的 cn 部分 |
| **8 节报告章节结构** | `report-agent/templates/industry_report.md:29-99` | 套进 `Knowledge_Wiki/templates/sector.md`，去飞书 `<font color>`，改 Obsidian callout |
| **资金/估值字段单位约定** | 同上 + `industry_report.md` 表格 | `market_cap_yi`（亿）、`pe_percentile_3y`、`net_inflow_yi` 字段名直接沿用 |

**不复用**：SQLite `industry_store.py`（用 jsonl 替代）/ 飞书 `<font color>` 着色 / OpenClaw IDENTITY/SOUL/HEARTBEAT 四件套（Claude Code 单 .md 即可）/ 仅 A 股分类。

## 十七、实施 Phase 优先级

> **P0 第一版策略**：fork [anthropics/financial-services](https://github.com/anthropics/financial-services) 的核心骨架 + **仅做 5 处本土化注入**，**严格少做**。不做 ontology、不做 4 分镜、不做 8 红旗、不做 cross-market。fork 命令见 [附录 A.4](anthropic-skills-appendix.md#a4-p0-骨架推荐组合必装清单)。

### P0（第一版，1 周）——极简跑通

**P0.1 Fork 上游骨架（30 分钟）**

执行 [附录 A.4](anthropic-skills-appendix.md#a4-p0-骨架推荐组合必装清单) 命令拷贝 7 个文件到 `.claude/skills/industry-analysis/references/` 与 `.claude/agents/`。**不重写任何 Skill 文本**，原版直接用，本土化通过新写的 `SKILL.md`（注入层）覆盖。

**P0.2 五处本土化注入（2-3 天）**

只改这 5 处，**其余照搬 Anthropic 原版**：

| # | 注入点 | 上游原状 | 本土化注入 | 落地位置 |
|---|---|---|---|---|
| 1 | **MCP 名称** | CapIQ / FactSet / Daloopa | `cn-financial` 单源（其他写入 fallback 兜底注释，不接入）| 主 `SKILL.md` "Data Source" 段 |
| 2 | **行业分类** | GICS sector/industry | 申万一级 31 行业表（从 FinRobot `coordinator/skills/industry-analysis/SKILL.md:17` 拷）| `wiki/sectors/_taxonomy.md` cn 部分 |
| 3 | **估值字段** | P/E, EV/EBITDA | + `pe_ttm`（不做 3 年分位、不做 31 行业排名 → P2）| 主 `SKILL.md` Step 4 + Subagent `output_schema` |
| 4 | **输出格式** | Word / PPT | Obsidian Markdown + wikilink（`type: sector` / `market: cn` / `sources[]` 必填）| `Knowledge_Wiki/templates/sector.md` |
| 5 | **触发词** | "sector overview" 等 EN | + 中文："分析 X 行业" / "X 板块画像" / "半导体产业链" | 主 `SKILL.md` description |

**P0.3 单 Subagent + 单 MCP（2 天）**

- `.claude/agents/industry-collector-cn.md`（拷 [附录 A.6.6](anthropic-skills-appendix.md#a66-sector-readeryaml-subagent-s-级-最关键的设计模式) 的 `sector-reader.yaml` 模板 → 改为 .md 形态 + 改 `mcp_servers: [cn-financial]`）
- `output_schema` 字段只覆盖 Step 2/3/4 所需的最小集合：`market_size` / `top_companies[10]` / `valuation`，**不做 fund_flow / rotation / red_flags**（推 P2）
- 接 `cn-financial-mcp`（用户参与配 MCP server 端点）

**P0.4 防腐工具最小子集（半天）**

只拷 2 个工具到 `.claude/skills/industry-analysis/scripts/utils.py`（不建 `taxonomy_mapper.py`）：
- `safe_float` — 从 `OpenClaw_FinRobot/finrobot/agents/market-agent/skills/industry-analysis/scripts/industry_analysis.py:55-92` 拷
- `safe_call` — 从 `OpenClaw_FinRobot/finrobot/shared/data_fetcher.py:52-100` 拷

`safe_int` / `normalize_stock_code` / `_pick` / `CircuitBreaker` / `_kline_fallback_chain` **全部 P2**。

**P0.5 验收**

端到端跑通 `分析半导体行业`：
1. Skill 触发 → Subagent 调 `cn-financial-mcp` 取数 → 返回 JSON 摘要
2. 主 Skill 用 sector-overview 6 步生成 `wiki/sectors/sw-semiconductor.md`
3. 文件通过 `python3 scripts/build_index.py --validate`（frontmatter 合法）
4. 数值字段（PE / 龙头市值）能在 `cn-financial-mcp` 返回中找到出处（不允许 LLM 编造）
5. 至少 3 个龙头 `[[companies/...]]` wikilink 指向 `wiki/companies/`（缺页可建 stub）

**明确不在 P0 范围**：

- ❌ HK/US Subagent（→ P1）
- ❌ 跨市场 crosswalk / cross_market_peers（→ P1）
- ❌ ontology 5 类新边（→ P2）
- ❌ 4 分镜 CoT-1（policy / valuation / capital / sentiment）（→ P2）
- ❌ 骨架/结论分离 JSON Schema 复杂版（P0 用 Anthropic `output_schema` 简版即可）
- ❌ 8 红旗双轨 / Beneish / Altman / Piotroski（→ P2）
- ❌ rotation_phase.py（→ P2）
- ❌ 行业基准表 feiyuggg 模式（→ P2）
- ❌ pptx / xlsx 输出（→ P3）

### P1（1 周）——横向扩到 HK + US

| 范围 | 验收 |
|---|---|
| `industry-collector-hk` + `industry-collector-us`（套 sector-reader 模板 / 接 Longbridge + Finnhub MCP）| "分析半导体" 一次出 3 份 sector 页（cn / hk / us），单消息内并行 dispatch 3 Subagent |
| 跨市场 crosswalk（申万 31 ↔ GICS Industry Group 25 ↔ HSIII 12）落到 `wiki/sectors/_taxonomy.md` | NVDA 涨 → 通过 crosswalk 能查到沪电股份/中芯国际 |
| sector 页 frontmatter 加 `cross_market_peers[]` 字段 | 三市场 wikilink 互通 |

### P2（1-2 周）——差异化护城河

| 范围 | 验收 |
|---|---|
| ontology 5 类新边（supplies / packaged_by / uses_component / benefits_from / exposed_to）+ `Knowledge_Wiki/ontology/schema.yaml` | NVDA earnings → graph traversal 出 A/H 受益标的清单 |
| 8 维度全量（含估值历史分位 / 31 行业排名 / 主力净流入 / 北向 / 轮动阶段 / 8 红旗）| sector 页质量从"罗列"升级到"带判断" |
| 4 分镜 CoT-1（policy/valuation/capital/sentiment）+ 骨架先填数值-结论后补 pattern（[第六节](#六关键-trick骨架先填数值结论后补抄自-finrobot)）| 反幻觉强约束 |
| `rotation_phase.py` + `red_flags.py` 双轨（量化轨 Beneish/Altman/Piotroski + 定性轨 8 红旗 checklist）| 命令行可独立调用 |
| 行业基准表（feiyuggg 模式 / 每行业 PE/PB/ROE/毛利率正常区间）落 `_taxonomy.md` | "PE 22 算高还是低" 有锚 |
| FinRobot 完整防腐工具栈（`safe_int` / `normalize_stock_code` / `_pick` / `CircuitBreaker` / `_kline_fallback_chain`）| 跨市场字段抽取稳定 |

### P3（按需）

13F 跟踪 / 事件 → 受益股 YAML / 雪球 scraper / pptx-author（投资人路演 PPT 版）/ thesis-tracker 联动。
