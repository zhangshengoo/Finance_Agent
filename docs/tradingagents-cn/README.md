# TradingAgents-CN 功能框架设计

本目录按**功能**分子目录存放各自的设计/接口文档。每个功能一个目录，互不混放。

| 目录 | 功能 | 文件 |
|---|---|---|
| [_overview/](_overview/) | 前后端架构全景（跨功能入口） | `tradingagents-cn-architecture.html` |
| [stock-analysis/](stock-analysis/) | 个股分析调用接口（CLI / Python） | `tradingagents-cn-api.md` |
| [rest-api/](rest-api/) | 后端 REST API 参考 | `tradingagents-cn-rest-api.md`、`tradingagents-cn-rest-api.openapi.json` |
| [backtest/](backtest/) | 回测 + 交易模拟 + 记忆功能 A | `backtest-feature-design.md`、`backtest-feature-framework.html` |
| [capital-flow-analyst/](capital-flow-analyst/) | 资金面分析师（个股流程新增维度） | `capital-flow-analyst-design.md` |

新增功能时：在此目录下新建以功能命名的子目录，放入该功能的设计/接口/可视化文件，并在上表追加一行。
