# 前端 ↔ 知识库 绑定契约

> 目标：前端不写任何内容，所有文本/数据来自知识库；知识库页严格模版化，可被 Agent 与脚本确定性解析；同一份 `.md` 同时服务「Agent 阅读」与「人通过前端阅读」。
>
> 设计依据 [karpathy_gist.md](../karpathy_gist.md)：wiki 是人 + LLM 共读的单一事实源；frontmatter 是机器可查的 properties（karpathy 的 Dataview 用法）；前端是 wiki 的「编译视图」，等同 `index.md` 之于目录——**只读、可重建、不持有内容**。

## 1. 分层职责

| 层 | 内容 | 给谁读 |
|---|---|---|
| frontmatter（YAML） | 数值 / 可枚举字段（估值、龙头代码、产业链、牛熊…） | 机器（脚本 + Agent 查询）+ 人（Obsidian properties 可见） |
| 正文 prose / 表格 | 叙述、严格模版的 markdown 表格 | 人 + Agent（全文） |
| `[UNSOURCED]` / `null` | 缺失标记 | 两者；**前端显式渲染，绝不臆造** |

铁律：缺失就是缺失。脚本与前端都不得用模型猜测填充——与 [Knowledge_Wiki/CLAUDE.md](../Knowledge_Wiki/CLAUDE.md)「禁止杜撰」一致。

## 2. 行业页模版契约（type: sector）

### 2.1 frontmatter（前端结构化数据来源）

```yaml
type: "sector"
slug: "sw-semiconductor"
taxonomy_code: "SW:801080"      # 与 _taxonomy.md 31 行业对齐 → 索引页定位
market: "cn"
status: "full | partial | stub" # 前端状态徽章；partial 自动出 UNSOURCED 提示条
summary: "一句话摘要"            # 前端索引卡片描述
leaders: ["688981","002371",…]  # 龙头代码（图谱 LEADER 边来源）
# --- 以下为前端结构化数据；数值均引自正文，禁止臆造 ---
constituents: 484
pe_ttm: 72.79
pb: 7.57
div_yield: 0.43
val_rank: "30/31"
value_chain_up:   ["光刻机 (EUV·ASML)|bottleneck", "刻蚀/CVD/PVD", …]
value_chain_mid:  ["设计 (Fabless/IDM)", "制造 (Foundry)|bottleneck", "封测"]
value_chain_down: ["消费电子", "AI 算力 (GPU/HBM)", …]
bull: ["…", "…"]                # 牛方论据
bear: ["…", "…"]                # 熊方论据
sources: ["raw/…","finrobot:…"] # provenance，前端 sources 区
```

约定：
- 产业链单元格 `标签|bottleneck` → 前端标红为瓶颈环节。
- `value_chain_*` / `bull` / `bear` 用 YAML 块列表（每项一行 `- "…"`），避免逗号歧义；与现有 `build_index.py` 解析器兼容。

### 2.2 正文（人读叙述 + 严格表格）

固定 6 小节骨架（沿用 industry-analysis Skill）：`## 1. Scope` … `## 6. Catalysts`。其中**唯一被脚本解析的表格**是龙头画像：

```
### 3.1 龙头公司画像（TOP 10）
| 排名 | 公司 | 代码 | 市值（亿元） | PE-TTM | 近5日涨跌 | 差异化定位 | 关联页 |
| 1 | 中芯国际 | 688981 | [UNSOURCED] | [UNSOURCED] | … | A 股最大晶圆代工厂… | [[companies/688981]] |
```

解析规则（`parse_leaders_table`）：取 `### 3.1` 与 `### 3.2` 之间、首列为数字的 pipe 行；列序固定 `排名,公司,代码,市值,PE-TTM,_,定位`；`[UNSOURCED]` → `null`。其余小节是纯 prose，供人/Agent 阅读，前端不强解析。

## 2b. 个股页绑定契约（type: company / stock-analysis）

> **状态：前端「个股分析」模块已接入并可渲染（2026-06-09）。** 链路 `wiki/companies/<TICKER>.md`（flat frontmatter 原子 + §2b.3 注释栅栏模块）→ `build_frontend_data.py`（解析 atoms + modules）→ `data.json` `companies[].analysis/.modules` → `index.html` equity tab（`renderCompanyDetail()`）已打通，首个样例 `wiki/companies/601899.md`（紫金矿业）。**唯一剩余环节（Gap A）**：`finance-ingest` 新增 `kind=stock-analysis` 场景，把 `stock-analysis` Skill 经 raw-intake 落的 `raw/analysis/stocks/<ticker>-<as_of>.md`（`meta.frontend` 块 + 模块正文）**自动编译**成本节的 `wiki/companies/` 页——当前该页为手工依据引擎报告如实誊写（见 §6）。

### 2b.1 结构化字段（来自 stock-analysis envelope 的 `meta.frontend`）

```yaml
type: "company"
ticker: "600519"
exchange: "SSE"                 # SSE | SZSE | NASDAQ | NYSE | HKEX
market: "cn"                    # cn（P0）；hk/us → P1
# --- 以下为前端「个股分析」结构化数据；均引自正文/引擎快照，缺失→null/[]，禁止臆造 ---
# ta_* 前缀刻意标识"TradingAgents-CN 模型分析产出（非客观事实）"
ta_action: "持有"               # 买入 | 持有 | 卖出 | null
ta_target_price: 1720           # 数字，人民币 | null
ta_confidence: 0.72             # 0–1 | null
ta_risk_score: 0.45             # 0–1，越高越险 | null
ta_as_of: "2026-06-08"          # 决策时点
key_metrics: {pe_ttm: 22.3, pb: 8.1, roe: 0.31}   # 缺失项 null
technical: {trend: "up", support: 1600, resistance: 1820}  # trend ∈ up|down|side|null
bull: ["品牌护城河深", "预收款回暖"]               # 牛方论据（YAML 块列表）
bear: ["估值偏高", "政策不确定"]                   # 熊方论据
catalysts: ["Q2 提价预期", "中报 8 月"]            # 催化剂
risks: ["需求走弱", "三公消费限制"]                # 风险
sources: ["raw/analysis/stocks/600519-2026-06-08.md", "raw/data/stock-snapshots/cn/600519-2026-06-08.json", "tradingagents-cn:1:2026-06-08"]
```

约定：
- `ta_action` 三值药丸（买入红 / 持有灰 / 卖出绿），`ta_confidence` / `ta_risk_score` 渲染为仪表。
- `bull` / `bear` / `catalysts` / `risks` 用 YAML 块列表（每项一行 `- "…"`），与现有 `build_index.py` 解析器兼容（沿用 sector 页 `bull`/`bear` 写法）。
- `ta_*` 与 bull/bear 应在前端"模型分析（非客观事实）"卡片下渲染，与公司客观事实字段（exchange/sector/listed_since）视觉区分——遵循 KB 事实/观点分层。

### 2b.2 正文

`stock-analysis` 产出的 raw markdown 已把**事实段**（业务/关键财务/技术面）与**判断段**（`## TradingAgents-CN 分析判断（非客观事实）`，带 `> [!warning]` 阅读须知 + 牛/熊/催化剂/风险）物理分离。finance-ingest 编 `wiki/companies/<TICKER>.md` 时，事实进 `## 客观事实`，判断进 `## TradingAgents-CN 分析判断（非客观事实）`。

### 2b.3 注释栅栏模块（前端按模块解析的正文契约）

> 报告正文按「分析师模块」切片：每段用 HTML 注释栅栏包裹，渲染/Obsidian 下**不可见**，但 `build_frontend_data.py:parse_modules()` 一条正则即可确定性切片。这让同一份 `.md` 既人读连贯、又被前端「分析师档案」折叠面板逐模块渲染（含每模块健康度徽章）。

```markdown
<!-- module: id | status | layer | 中文标题 | 来源 -->
### 中文标题
（该模块正文 prose；栅栏内首行 ### 标题在解析时被剥离）
<!-- /module -->
```

- 字段顺序固定 `id | status | layer | 标题 | 来源`，以 `|` 分隔。
- `status ∈ ok | degraded | missing`：**降级/缺失如实标徽章**（黄 ⚠ / 灰 ✕），绝不隐藏缺口或臆造（对应「缺失即缺失」铁律）。引擎跑挂的模块（如 news 未取数、risk 辩论拒演降级）由此被前端忠实呈现。
- `layer ∈ fact | opinion`：事实层进「客观事实」区、判断层进「模型判断（非客观事实）」区，驱动前端事实/观点分层。
- 解析产物：`data.json` 的 `companies[].modules = [{id,status,layer,title,src,prose}]`；hero 的「数据完整性」状态条与「分析师档案」折叠面板均由它渲染。
- **重要实现约束**：wiki 页 frontmatter 必须 **flat（顶层扁平）**，不可用 `meta.frontend` 嵌套——`build_index.py` 的 stdlib 解析器会把嵌套 dict 降级为字符串。即 §2b.1 的 `key_metrics`/`technical` 在 wiki 页摊平为顶层 `pe_ttm`/`ta_trend`/`ta_support`… 决策链用块列表 `decision_chain: ["角色|文案|flag"]`。

### 2b.4 两视图：研究报告输出 ⇄ wiki 展示（2026-06-09）

前端「个股分析」详情页有**两个可切换视图，默认研究报告**，对应 KB 两层：

| 视图 | 数据源文件 | `data.json` 字段 | 角色 | 模块数 |
|---|---|---|---|---|
| **研究报告输出**（默认） | `raw/analysis/stocks/<ticker>-<date>.md`（`type: stock-report`） | `companies[].reports[]` | 某次引擎运行**全保真**（immutable，保留完整正文） | 全 8（含 missing/degraded） |
| **wiki 展示** | `wiki/companies/<TICKER>.md`（`type: company`） | `companies[].analysis` + `.modules` | finance-ingest 蒸馏的**编译视图** | distilled 子集 |

- 两视图共用同一渲染器 `renderAnalysisBody(vm)`（hero+facts+judgment+dossiers），仅 view-model 与子标题不同。研究报告视图额外渲染 run-header（engine/depth/run_config/price + `report_status` 徽章：样例/真跑/partial）与多 run 选择器。
- 研究报告固定模板 = `.claude/skills/stock-analysis/references/report-template.md`（`stock-analysis` Skill Step 4 产出）。同样的 flat frontmatter + §2b.3 注释栅栏契约，差别只是**研究报告保留完整正文、wiki 蒸馏**。
- `build_frontend_data.py` 扫 `raw/analysis/stocks/*.md`（`type: stock-report`）→ 按 ticker 挂到 `companies[].reports[]`（按 `as_of` 倒序）；报告原子与 wiki 共用 `build_analysis(fm)`。
- 样例：`688981`（中芯国际）= 研究报告 `report_status: sample`（8 模块，news/sentiment 因仅选 market+fundamentals 而 missing）+ wiki distilled（4 模块）；`601899`（紫金矿业）= 仅 wiki（7 模块，run2 风险/裁决 degraded）。

## 2d. 回测 / 记忆环绑定契约（type: backtest-report → wiki report）

> **状态：前端「回测 / 记忆环」单元已接入（M1 反思 2026-06-16；M2 净值曲线 2026-06-16）。** 链路 `raw/analysis/backtests/cn/<ticker>-<runid>.md` → `kb-parse.js`（backtest-report 分支）→ `companies[].backtests[]` → `index.html renderBacktest()`（同屏堆叠 M1 + M2，各取该模式最新 run）。浏览器一键经 serve.sh **仅绑 127.0.0.1** 的 SSE 桥 `GET /api/backtest/stream?ticker=&mode=`。

### 2d.1 raw 层（前端直接 live-parse 的源）

`type: backtest-report`，flat frontmatter + 正文 `<!-- backtest-json -->` ```json``` 块（**数组进不了 mini-YAML，故进 json 块**）：

| mode | frontmatter 原子 | json 块 |
|---|---|---|
| `reflect`（M1） | `headline_return_pct` / `n_reflected` / `n_non_evaluable` / `horizons` / `snapshot_date` | `{trades[], lessons[]}` |
| `simulate`（M2） | `total_return_pct` / `sharpe` / `max_drawdown_pct` / `win_rate_pct` / `vs_benchmark_pct` / `n_closed_trades` / `period_from` / `period_to` / `initial_cash` | `{mode, metrics{}, equity_curve[], trades[]}` |

公共：`type` / `ticker` / `mode` / `run_status`(ok|partial|sample) / `as_of` / `sources[]`。前端按 `mode==='simulate' || equity_curve.length` 分流：M2 渲染指标卡 + 手绘 SVG 净值曲线 + round-trip 成交表；M1 渲染决策反思表 + 5 桶教训卡。**收益 / 净值只用 Tushare 真实 qfq close，缺失 `non_evaluable` / `null`，禁止臆造。**

### 2d.2 wiki 层（finance-ingest 场景 F 编译产物）

`wiki/reports/<as_of>-<ticker>-backtest.md`（`type: report`）= raw 回测报告的蒸馏复盘页，供 Agent / Obsidian 阅读 + 喂 ontology。指标逐个溯源自机器产物，模型教训进「（非事实）」段。（当前前端无 `report` 类型渲染器 → 该页不在前端面板出现，其前端可见产出是**星图 Backtest 节点**。）

### 2d.3 ontology

1 run = 1 个 `Backtest` 节点（`graph_append.py create --type Backtest`）+ `COVERS → Company`（+ 可选 `EVALUATES → Thesis`）。**绝不给每笔成交 / 每个净值点建节点。** 星图节点标签显示「回测 ±x%」（`kb-parse.js` 节点标签规则；颜色落 company 金色）。

## 3. 其他类型（已接入）

| type | 前端取数 |
|---|---|
| `macro-topic` | `indicator_kind`（money/rate/growth）+ `summary`；驱动链由 summary 中「驱动因素/定价/传导链：a、b、c」确定性提取 |
| `filing-summary` | `summary` + join `ontology/graph.jsonl` 拿 `published_at` / `filing_type`（video/dynamic/trade-log）/ 作者(AUTHORED_BY) / 提及(MENTIONS) |
| `company` | `ticker` / `summary` / `sector` / `market`；含 `stub` → 待 company-page 填充 |
| 31 行业全集 | 解析 `wiki/sectors/_taxonomy.md` 映射表；已分析者按 `taxonomy_code` 匹配点亮 |

知识星图：`ontology/graph.jsonl` 的 create/relate 事件 → 节点 + 边；额外合成 sector→龙头公司 的 LEADER 边；孤立节点（如 NVDA）如实展示。

## 4. 解析器与前端

- 解析器 `Knowledge_Wiki/scripts/build_frontend_data.py`：纯 stdlib，复用 `build_index.py` 的 `extract_frontmatter`。输出 `frontend/data.json`。
- 前端 `frontend/index.html`：`fetch('data.json')` → 按 type 渲染器（`renderSectorDetail` / `renderMacro` / `renderMedia` …）。新增模块 = KB 出新 type + 加一个渲染器。
- 重建时机：手动跑脚本；或将其挂到 `industry-analysis` / `finance-ingest` 收尾；或 git pre-commit hook。

## 5. 校验

```bash
python3 Knowledge_Wiki/scripts/build_index.py --validate   # frontmatter 合规（新增字段不破坏必填校验）
python3 Knowledge_Wiki/scripts/build_frontend_data.py      # 编译 + 打印 docs/nodes/edges 计数
```

## 6. 待办（让所有类型达到完整富度）

- [x] industry-analysis Skill 输出对齐 §2.1（envelope `meta.frontend` 块）+ finance-ingest 摊平进 frontmatter
- [x] §2.1 sector 字段写入 `_schema.md`（金融扩展字段 · sector 专用）
- [x] §2b 个股 `meta.frontend` 绑定契约定稿（`stock-analysis` Skill 已按此产出 envelope）
- [ ] macro / filing-summary 的结构化原子（价格点、关键要点）同样上浮 frontmatter，减少正文依赖
- [x] **`build_frontend_data.py` 扩展 company 提取**：`num()` 强转 + `parse_chain()` + `parse_modules()`（§2b.3 栅栏），写进 `data.json` 的 `companies[].analysis/.modules`（2026-06-09）
- [x] **`frontend/index.html` 解锁 equity tab + `renderCompanyDetail()`**：决策药丸 + 置信/风险仪表 + 决策溯源链 + 数据完整性状态条 + 事实/判断分层 + 多空 + 催化/风险 + 分析师档案折叠面板（复用 shell 原语，新增 `eq-*`）（2026-06-09）
- [x] **研究报告视图（§2b.4）**：`stock-analysis` Skill Step 4 固定模板（`references/report-template.md`）→ `raw/analysis/stocks/*.md` → `build_frontend_data.py` 扫成 `companies[].reports[]` → 前端「研究报告 ⇄ wiki」双视图（默认研究报告）。样例 688981（2026-06-09）
- [ ] **Gap A：finance-ingest 新增 `kind=stock-analysis → wiki/companies/` 场景**：把研究报告（§2b.4）蒸馏 + `meta.frontend` 摊平进公司页 flat frontmatter + 写 §2b.3 栅栏模块，自动化当前手工誊写的 `wiki/companies/{601899,688981}.md`
- [ ] **真跑覆盖样例**：claude-max-proxy OAuth 重新授权后，对 688981 跑真引擎，用真快照 + 固定模板覆盖 `report_status: sample` 的占位报告
- [ ] macro / filing-summary 的结构化原子（价格点、关键要点）同样上浮 frontmatter，减少正文依赖
- [ ] §2b 字段写入 `_schema.md`（company 专用 · 模型分析扩展字段；当前校验通过因 validator 只查必填、放行额外字段）
- [ ] 把 §2.1 字段同步写入 `docs/industry-analysis-requirements.md`（与 SKILL.md 对齐）
