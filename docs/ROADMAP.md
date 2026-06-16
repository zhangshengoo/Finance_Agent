# Finance_Agent 开发路线图（ROADMAP）

> 项目级开发计划与长期 ToDo。投研类主观笔记请走 `Knowledge_Wiki/thoughts/`，本文件只跟踪**能力 / 技能 / 集成**的开发任务。
> 约定：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 已完成。每条尽量链接对应的设计文档（`docs/*-requirements.md` / `docs/*-design.md`）。

## 个股分析（Planned next，对应 CLAUDE.md "Planned next: 个股分析"）

- [ ] **资金面分析师 Capital Flow Analyst** —— 在 TradingAgents-CN 个股分析流程中新增资金面维度
      - 方案文档：[capital-flow-analyst-design.md](tradingagents-cn/capital-flow-analyst/capital-flow-analyst-design.md)（v2，已对照真实源码评审修订）
      - 数据：筹码分布 `stock_cyq_em` / 主力资金流 `stock_individual_fund_flow` / 龙虎榜 `stock_lhb_stock_detail_em`（AKShare，免费无 token）
      - 接入点：插入分析师序列首位；涉及 12 类共 13+ 文件（provider / Toolkit / AgentState / 新 analyst / setup / trading_graph / conditional_logic / propagation / 下游消费者 / CLI / web）
      - 最小可运行集见方案文档 §6；验证方式见 §7

## 行业分析

- [x] **industry-analysis** 技能 + `industry-collector-cn` 子 agent（已落地，见 `.claude/skills/industry-analysis/`）

## 知识库 / 采集

- 见各技能 SKILL.md 与 `docs/*-requirements.md`

---

_新增长期计划时，在对应板块追加一条并链接设计文档；任务开发完成后将 `[ ]` 改为 `[x]` 并保留文档链接以备回溯。_
