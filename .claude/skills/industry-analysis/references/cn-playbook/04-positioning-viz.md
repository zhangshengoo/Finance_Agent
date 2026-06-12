<!-- Distilled & localized from anthropics/financial-services @ 120a31d competitive-analysis "Step 5 — Positioning visualization" + frameworks.md (Apache 2.0). NOT a verbatim fork — 映射到本项目前端 value_chain_* 字段。上游原文见 ../upstream-competitive-analysis.md、../competitive-analysis-references/frameworks.md。 -->

# §4 产业链 / 定位可视化选型（→ 前端字段）

## 为什么

Step 2 要拆产业链、Step 3 要给竞争定位，但「怎么呈现」不是一种。选错形式会丢信息：垂直行业用 2×2 矩阵看不出上下游卡位，平台行业用价值链图画不出生态。先按行业结构选对形式，再去填前端字段。

## 选型表

| 形式 | 何时用 | 对应本项目产出 |
|---|---|---|
| **价值链图（上/中/下游）** | 垂直行业（半导体、锂电、医药）——价值沿链条分布 | 前端 `value_chain_up/mid/down`（**主力**） |
| 生态图 | 平台/网络市场（电商、支付、券商交易） | 正文叙述 + value_chain 近似 |
| 2×2 矩阵 | 两个决定性竞争因子（见下轴对） | 正文/可选图 |
| 分层(tier)图 | 自然聚成战略组（龙头/二线/新进入） | 正文叙述 |

## 价值链图（最常用）→ 前端字段约定

A 股行业多为垂直结构，默认用价值链。拆成上/中/下游，每段列关键环节，**瓶颈环节加 `|bottleneck` 后缀**（前端标红）：

```yaml
value_chain_up:   ["光刻机 (EUV·ASML)|bottleneck", "刻蚀/CVD/PVD 设备", "光刻胶|bottleneck", "硅片"]
value_chain_mid:  ["设计 (Fabless/IDM)", "制造 (Foundry)|bottleneck", "封测"]
value_chain_down: ["消费电子", "AI 算力 (GPU/HBM)", "汽车电子", "工业控制"]
```

规则（契约见 [frontend-kb-binding](../../../../docs/frontend-kb-binding.md) §2.1）：
- 每段 3–6 个环节，从最上游到最下游有序。
- `环节|bottleneck` 标「卡脖子/高壁垒/国产化低」的环节——这是产业链分析的信息核心。
- 写进 intake envelope `meta.frontend.value_chain_*`（YAML 块列表，每项一行），下游 finance-ingest 摊平进 sector 页 frontmatter。

## 2×2 矩阵轴对（按行业，可选）

需要画竞争定位 2×2 时，按行业选轴（distilled from 上游 frameworks.md，本土化）：

| 行业类型 | 常用轴对 |
|---|---|
| 科技/软件 | 产品广度 × 客户层级；集成深度 × 地域覆盖 |
| 消费/零售 | 价格带 × 品类宽度；线上 × 线下 |
| 金融 | 产品复杂度 × 客户成熟度；规模 × 专业化 |
| 医药/医疗 | 治疗场景 × 支付方结构；技术使能 × 服务广度 |
| 工业/制造 | 定制化 × 规模；地域范围 × 垂直聚焦 |

2×2 在 Markdown 里用文字描述四象限即可（本项目不出 pptx，去掉上游的画布/排版部分）。

## 落到输出

- 价值链 → 前端 `value_chain_*` 字段（主力路径，必填或 null）。
- 2×2 / tier / 生态 → sector 分析 markdown 的 Step 2「市场概览·产业链结构」段，纯 prose。
