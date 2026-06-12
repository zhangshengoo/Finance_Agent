# 输出 Schema & 前端绑定契约

> 按需加载。两份契约的单一事实源：① `stock-analyst-cn` subagent 回传的 JSON 摘要；② intake envelope 里 `meta.frontend` 的前端绑定字段。

## 1. subagent 回传摘要（≤200 行）

完整定义见 `.claude/agents/stock-analyst-cn.md` 的 Output Schema。主 Skill 收到后用于 **Step 3 审核**；**Step 4 合成时再 `Read` 完整快照**（`raw/data/stock-snapshots/cn/<ticker>-<date>.json`）拿全文报告。

关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `decision.action` | `"买入"\|"持有"\|"卖出"` | 引擎强制中文 |
| `decision.target_price` | number\|null | 目标价（人民币） |
| `decision.confidence` | number 0–1\|null | 置信度 |
| `decision.risk_score` | number 0–1\|null | 风险分（越高越险） |
| `decision.reasoning` | string | 决策理由（原文，≤300 字摘录） |
| `report_excerpts.{market,fundamentals,investment_judge,risk_judge}` | string\|null | 各 ≤600 字摘录 |
| `snapshot_path` | string | KB 相对 `raw/data/...` |
| `status` | `complete\|partial\|failed` | |
| `missing[]` | string[] | 缺失字段路径；`decision.parse_fallback` 表示引擎信号解析回退到兜底默认值 |

## 2. `meta.frontend` 前端绑定契约（本次数据交付物）

`stock-analysis` Skill 在 Step 5 把这块写进 intake envelope 的 `meta.frontend`。raw-intake 会把整个 `meta` 注入 raw 文件 frontmatter（不可变 + 可溯源）。**未来**由 finance-ingest 个股场景摊平进 `wiki/companies/<TICKER>.md` frontmatter，再由 `build_frontend_data.py` 取数、前端「个股分析」模块渲染（均为后续工作）。

铁律：**数值一律引自 Step 4 正文 / 引擎快照；缺失就是缺失 → `null` / `[]`，禁止臆造**（与 `docs/frontend-kb-binding.md` 第 1 节、Knowledge_Wiki「禁止杜撰」一致）。

| 字段 | 类型 | 来源 | 前端语义（未来） |
|---|---|---|---|
| `ta_action` | `"买入"\|"持有"\|"卖出"`\|null | `decision.action` | 决策药丸（红/灰/绿配色） |
| `ta_target_price` | number\|null | `decision.target_price` | 目标价 |
| `ta_confidence` | number 0–1\|null | `decision.confidence` | 置信度仪表 |
| `ta_risk_score` | number 0–1\|null | `decision.risk_score` | 风险仪表 |
| `ta_as_of` | string `YYYY-MM-DD` | 分析日期 | 决策时点标注 |
| `key_metrics.pe_ttm` | number\|null | fundamentals 报告 | 关键财务卡 |
| `key_metrics.pb` | number\|null | fundamentals 报告 | 关键财务卡 |
| `key_metrics.roe` | number\|null | fundamentals 报告 | 关键财务卡 |
| `technical.trend` | `"up"\|"down"\|"side"`\|null | market 报告 | 趋势徽章 |
| `technical.support` | number\|null | market 报告 | 支撑位 |
| `technical.resistance` | number\|null | market 报告 | 压力位 |
| `bull[]` | string[] | 多空辩论 bull | 牛方列 |
| `bear[]` | string[] | 多空辩论 bear | 熊方列 |
| `catalysts[]` | string[] | investment/risk 裁决 | 催化剂时间线 |
| `risks[]` | string[] | risk 裁决 | 风险列表 |

### 字段约定
- `bull` / `bear` / `catalysts` / `risks` 用 YAML 块列表（每项一行 `- "…"`），与现有 `build_index.py` 解析器兼容（参照 sector 页 `bull`/`bear` 写法）。
- `ta_*` 前缀刻意标识"这是 TradingAgents-CN 模型分析产出"，与公司页上未来可能并存的客观事实字段（exchange/sector/listed_since 等）区分开——前端应在"模型分析（非客观事实）"卡片下渲染 `ta_*` 与 bull/bear。
- 数值字段必须是 JSON `number`，不要写成字符串。

## 3. 下游 TODO（不在本次任务，仅记录契约去向）
- finance-ingest 新增 `kind=stock-analysis → wiki/companies/` 场景：把 `meta.frontend` 摊平进公司页 frontmatter，决策/牛熊落「## 来自媒体源的观察与观点（非事实）」。
- `build_frontend_data.py` 扩展 company 提取：读上述 frontmatter 字段，写进 `frontend/data.json` 的 `companies[]`。
- `frontend/index.html` 解锁 equity tab + `renderCompanyDetail()`。
