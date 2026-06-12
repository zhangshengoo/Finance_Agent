# TradingAgents-CN API — REST API 参考

> **股票分析与批量队列系统 API** · 版本 `v1.0.1`
>
> 由运行中的后端 OpenAPI 规范（http://localhost:8000/openapi.json）导出，共 **274** 个接口，分 **54** 组。
> 原始规范见同目录 [`tradingagents-cn-rest-api.openapi.json`](tradingagents-cn-rest-api.openapi.json)；交互式文档：后端运行时访问 `http://localhost:8000/docs`。
>
> ⚠️ 本文件由脚本自动生成，请勿手改——重导出会覆盖。

## 目录

- [(未分类)](#(未分类)) （2）
- [analysis](#analysis) （18）
- [akshare-init](#akshare-init) （6）
- [AKShare初始化](#akshare初始化) （6）
- [baostock-init](#baostock-init) （7）
- [BaoStock初始化](#baostock初始化) （7）
- [tushare-init](#tushare-init) （5）
- [Tushare初始化](#tushare初始化) （5）
- [authentication](#authentication) （9）
- [cache](#cache) （10）
- [config](#config) （50）
- [配置管理](#配置管理) （50）
- [favorites](#favorites) （7）
- [自选股管理](#自选股管理) （7）
- [financial-data](#financial-data) （7）
- [财务数据](#财务数据) （7）
- [health](#health) （3）
- [historical-data](#historical-data) （6）
- [历史数据](#历史数据) （6）
- [internal-messages](#internal-messages) （20）
- [multi-market](#multi-market) （10）
- [model-capabilities](#model-capabilities) （8）
- [模型能力管理](#模型能力管理) （8）
- [multi-period-sync](#multi-period-sync) （10）
- [多周期同步](#多周期同步) （10）
- [news-data](#news-data) （9）
- [新闻数据](#新闻数据) （9）
- [notifications](#notifications) （5）
- [paper](#paper) （10）
- [queue](#queue) （1）
- [reports](#reports) （10）
- [scheduler](#scheduler) （32）
- [screening](#screening) （12）
- [social-media](#social-media) （16）
- [stock-data](#stock-data) （7）
- [股票数据](#股票数据) （7）
- [stock-sync](#stock-sync) （3）
- [股票数据同步](#股票数据同步) （3）
- [stocks](#stocks) （8）
- [streaming](#streaming) （2）
- [Multi-Source Sync](#multi-source-sync) （8）
- [sync](#sync) （2）
- [system](#system) （4）
- [database](#database) （11）
- [数据库管理](#数据库管理) （11）
- [operation_logs](#operation_logs) （6）
- [操作日志](#操作日志) （6）
- [logs](#logs) （5）
- [系统日志](#系统日志) （5）
- [tags](#tags) （4）
- [标签管理](#标签管理) （4）
- [usage-statistics](#usage-statistics) （6）
- [使用统计](#使用统计) （6）
- [websocket](#websocket) （1）

## (未分类)

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | Root |
| `GET` | `/api/test-log` | Test Log |

## analysis

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/analysis/admin/cleanup-zombie-tasks` | Cleanup Zombie Tasks |
| `GET` | `/api/analysis/admin/zombie-tasks` | Get Zombie Tasks |
| `POST` | `/api/analysis/analyze` | Analyze Single |
| `POST` | `/api/analysis/analyze/batch` | Analyze Batch |
| `POST` | `/api/analysis/batch` | Submit Batch Analysis |
| `GET` | `/api/analysis/batches/{batch_id}` | Get Batch |
| `POST` | `/api/analysis/single` | Submit Single Analysis |
| `GET` | `/api/analysis/tasks` | List User Tasks |
| `GET` | `/api/analysis/tasks/all` | List All Tasks |
| `DELETE` | `/api/analysis/tasks/{task_id}` | Delete Task |
| `POST` | `/api/analysis/tasks/{task_id}/cancel` | Cancel Task |
| `GET` | `/api/analysis/tasks/{task_id}/details` | Get Task Details |
| `POST` | `/api/analysis/tasks/{task_id}/mark-failed` | Mark Task As Failed |
| `GET` | `/api/analysis/tasks/{task_id}/result` | Get Task Result |
| `GET` | `/api/analysis/tasks/{task_id}/status` | Get Task Status New |
| `GET` | `/api/analysis/test-route` | Test Route |
| `GET` | `/api/analysis/user/history` | Get User Analysis History |
| `GET` | `/api/analysis/user/queue-status` | Get User Queue Status |

## akshare-init

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/akshare-init/connection-test` | Test Akshare Connection |
| `GET` | `/api/api/akshare-init/initialization-status` | Get Initialization Status |
| `POST` | `/api/api/akshare-init/start-basic-sync` | Start Basic Sync |
| `POST` | `/api/api/akshare-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/akshare-init/status` | Get Database Status |
| `POST` | `/api/api/akshare-init/stop` | Stop Initialization |

## AKShare初始化

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/akshare-init/connection-test` | Test Akshare Connection |
| `GET` | `/api/api/akshare-init/initialization-status` | Get Initialization Status |
| `POST` | `/api/api/akshare-init/start-basic-sync` | Start Basic Sync |
| `POST` | `/api/api/akshare-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/akshare-init/status` | Get Database Status |
| `POST` | `/api/api/akshare-init/stop` | Stop Initialization |

## baostock-init

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/baostock-init/connection-test` | Test Baostock Connection |
| `GET` | `/api/api/baostock-init/initialization-status` | Get Initialization Status |
| `GET` | `/api/api/baostock-init/service-status` | Get Service Status |
| `POST` | `/api/api/baostock-init/start-basic` | Start Basic Initialization |
| `POST` | `/api/api/baostock-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/baostock-init/status` | Get Database Status |
| `POST` | `/api/api/baostock-init/stop` | Stop Initialization |

## BaoStock初始化

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/baostock-init/connection-test` | Test Baostock Connection |
| `GET` | `/api/api/baostock-init/initialization-status` | Get Initialization Status |
| `GET` | `/api/api/baostock-init/service-status` | Get Service Status |
| `POST` | `/api/api/baostock-init/start-basic` | Start Basic Initialization |
| `POST` | `/api/api/baostock-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/baostock-init/status` | Get Database Status |
| `POST` | `/api/api/baostock-init/stop` | Stop Initialization |

## tushare-init

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/tushare-init/initialization-status` | Get Initialization Status |
| `POST` | `/api/api/tushare-init/start-basic` | Start Basic Initialization |
| `POST` | `/api/api/tushare-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/tushare-init/status` | Get Database Status |
| `POST` | `/api/api/tushare-init/stop` | Stop Initialization |

## Tushare初始化

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/api/tushare-init/initialization-status` | Get Initialization Status |
| `POST` | `/api/api/tushare-init/start-basic` | Start Basic Initialization |
| `POST` | `/api/api/tushare-init/start-full` | Start Full Initialization |
| `GET` | `/api/api/tushare-init/status` | Get Database Status |
| `POST` | `/api/api/tushare-init/stop` | Stop Initialization |

## authentication

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/change-password` | Change Password |
| `POST` | `/api/auth/create-user` | Create User |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Logout |
| `GET` | `/api/auth/me` | Me |
| `PUT` | `/api/auth/me` | Update Me |
| `POST` | `/api/auth/refresh` | Refresh Token |
| `POST` | `/api/auth/reset-password` | Reset Password |
| `GET` | `/api/auth/users` | List Users |

## cache

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/cache/backend-info` | Get Cache Backend Info |
| `GET` | `/api/cache/backend-info` | Get Cache Backend Info |
| `DELETE` | `/api/cache/cleanup` | Cleanup Old Cache |
| `DELETE` | `/api/cache/cleanup` | Cleanup Old Cache |
| `DELETE` | `/api/cache/clear` | Clear All Cache |
| `DELETE` | `/api/cache/clear` | Clear All Cache |
| `GET` | `/api/cache/details` | Get Cache Details |
| `GET` | `/api/cache/details` | Get Cache Details |
| `GET` | `/api/cache/stats` | Get Cache Stats |
| `GET` | `/api/cache/stats` | Get Cache Stats |

## config

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/config/database` | Add Database Config |
| `GET` | `/api/config/database` | Get Database Configs |
| `GET` | `/api/config/database/{db_name}` | Get Database Config |
| `PUT` | `/api/config/database/{db_name}` | Update Database Config |
| `DELETE` | `/api/config/database/{db_name}` | Delete Database Config |
| `POST` | `/api/config/database/{db_name}/test` | Test Saved Database Config |
| `POST` | `/api/config/datasource` | Add Data Source Config |
| `GET` | `/api/config/datasource` | Get Data Source Configs |
| `GET` | `/api/config/datasource-groupings` | Get Datasource Groupings |
| `POST` | `/api/config/datasource-groupings` | Add Datasource To Category |
| `DELETE` | `/api/config/datasource-groupings/{data_source_name}/{category_id}` | Remove Datasource From Category |
| `PUT` | `/api/config/datasource-groupings/{data_source_name}/{category_id}` | Update Datasource Grouping |
| `POST` | `/api/config/datasource/set-default` | Set Default Data Source |
| `PUT` | `/api/config/datasource/{name}` | Update Data Source Config |
| `DELETE` | `/api/config/datasource/{name}` | Delete Data Source Config |
| `POST` | `/api/config/default/datasource` | Set Default Data Source |
| `POST` | `/api/config/default/llm` | Set Default Llm |
| `POST` | `/api/config/export` | Export Config |
| `POST` | `/api/config/import` | Import Config |
| `POST` | `/api/config/llm` | Add Llm Config |
| `GET` | `/api/config/llm` | Get Llm Configs |
| `GET` | `/api/config/llm/providers` | Get Llm Providers |
| `POST` | `/api/config/llm/providers` | Add Llm Provider |
| `POST` | `/api/config/llm/providers/init-aggregators` | Init Aggregator Providers |
| `POST` | `/api/config/llm/providers/migrate-env` | Migrate Env To Providers |
| `PUT` | `/api/config/llm/providers/{provider_id}` | Update Llm Provider |
| `DELETE` | `/api/config/llm/providers/{provider_id}` | Delete Llm Provider |
| `POST` | `/api/config/llm/providers/{provider_id}/fetch-models` | Fetch Provider Models |
| `POST` | `/api/config/llm/providers/{provider_id}/test` | Test Provider Api |
| `PATCH` | `/api/config/llm/providers/{provider_id}/toggle` | Toggle Llm Provider |
| `POST` | `/api/config/llm/set-default` | Set Default Llm |
| `DELETE` | `/api/config/llm/{provider}/{model_name}` | Delete Llm Config |
| `GET` | `/api/config/market-categories` | Get Market Categories |
| `POST` | `/api/config/market-categories` | Add Market Category |
| `PUT` | `/api/config/market-categories/{category_id}` | Update Market Category |
| `DELETE` | `/api/config/market-categories/{category_id}` | Delete Market Category |
| `PUT` | `/api/config/market-categories/{category_id}/datasource-order` | Update Category Datasource Order |
| `POST` | `/api/config/migrate-legacy` | Migrate Legacy Config |
| `GET` | `/api/config/model-catalog` | Get Model Catalog |
| `POST` | `/api/config/model-catalog` | Save Model Catalog |
| `POST` | `/api/config/model-catalog/init` | Init Model Catalog |
| `GET` | `/api/config/model-catalog/{provider}` | Get Provider Model Catalog |
| `DELETE` | `/api/config/model-catalog/{provider}` | Delete Model Catalog |
| `GET` | `/api/config/models` | Get Available Models |
| `POST` | `/api/config/reload` | 重新加载配置 |
| `GET` | `/api/config/settings` | Get System Settings |
| `PUT` | `/api/config/settings` | Update System Settings |
| `GET` | `/api/config/settings/meta` | Get System Settings Meta |
| `GET` | `/api/config/system` | Get System Config |
| `POST` | `/api/config/test` | Test Config |

## 配置管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/config/database` | Add Database Config |
| `GET` | `/api/config/database` | Get Database Configs |
| `GET` | `/api/config/database/{db_name}` | Get Database Config |
| `PUT` | `/api/config/database/{db_name}` | Update Database Config |
| `DELETE` | `/api/config/database/{db_name}` | Delete Database Config |
| `POST` | `/api/config/database/{db_name}/test` | Test Saved Database Config |
| `POST` | `/api/config/datasource` | Add Data Source Config |
| `GET` | `/api/config/datasource` | Get Data Source Configs |
| `GET` | `/api/config/datasource-groupings` | Get Datasource Groupings |
| `POST` | `/api/config/datasource-groupings` | Add Datasource To Category |
| `DELETE` | `/api/config/datasource-groupings/{data_source_name}/{category_id}` | Remove Datasource From Category |
| `PUT` | `/api/config/datasource-groupings/{data_source_name}/{category_id}` | Update Datasource Grouping |
| `POST` | `/api/config/datasource/set-default` | Set Default Data Source |
| `PUT` | `/api/config/datasource/{name}` | Update Data Source Config |
| `DELETE` | `/api/config/datasource/{name}` | Delete Data Source Config |
| `POST` | `/api/config/default/datasource` | Set Default Data Source |
| `POST` | `/api/config/default/llm` | Set Default Llm |
| `POST` | `/api/config/export` | Export Config |
| `POST` | `/api/config/import` | Import Config |
| `POST` | `/api/config/llm` | Add Llm Config |
| `GET` | `/api/config/llm` | Get Llm Configs |
| `GET` | `/api/config/llm/providers` | Get Llm Providers |
| `POST` | `/api/config/llm/providers` | Add Llm Provider |
| `POST` | `/api/config/llm/providers/init-aggregators` | Init Aggregator Providers |
| `POST` | `/api/config/llm/providers/migrate-env` | Migrate Env To Providers |
| `PUT` | `/api/config/llm/providers/{provider_id}` | Update Llm Provider |
| `DELETE` | `/api/config/llm/providers/{provider_id}` | Delete Llm Provider |
| `POST` | `/api/config/llm/providers/{provider_id}/fetch-models` | Fetch Provider Models |
| `POST` | `/api/config/llm/providers/{provider_id}/test` | Test Provider Api |
| `PATCH` | `/api/config/llm/providers/{provider_id}/toggle` | Toggle Llm Provider |
| `POST` | `/api/config/llm/set-default` | Set Default Llm |
| `DELETE` | `/api/config/llm/{provider}/{model_name}` | Delete Llm Config |
| `GET` | `/api/config/market-categories` | Get Market Categories |
| `POST` | `/api/config/market-categories` | Add Market Category |
| `PUT` | `/api/config/market-categories/{category_id}` | Update Market Category |
| `DELETE` | `/api/config/market-categories/{category_id}` | Delete Market Category |
| `PUT` | `/api/config/market-categories/{category_id}/datasource-order` | Update Category Datasource Order |
| `POST` | `/api/config/migrate-legacy` | Migrate Legacy Config |
| `GET` | `/api/config/model-catalog` | Get Model Catalog |
| `POST` | `/api/config/model-catalog` | Save Model Catalog |
| `POST` | `/api/config/model-catalog/init` | Init Model Catalog |
| `GET` | `/api/config/model-catalog/{provider}` | Get Provider Model Catalog |
| `DELETE` | `/api/config/model-catalog/{provider}` | Delete Model Catalog |
| `GET` | `/api/config/models` | Get Available Models |
| `POST` | `/api/config/reload` | 重新加载配置 |
| `GET` | `/api/config/settings` | Get System Settings |
| `PUT` | `/api/config/settings` | Update System Settings |
| `GET` | `/api/config/settings/meta` | Get System Settings Meta |
| `GET` | `/api/config/system` | Get System Config |
| `POST` | `/api/config/test` | Test Config |

## favorites

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/favorites/` | Get Favorites |
| `POST` | `/api/favorites/` | Add Favorite |
| `GET` | `/api/favorites/check/{stock_code}` | Check Favorite |
| `POST` | `/api/favorites/sync-realtime` | Sync Favorites Realtime |
| `GET` | `/api/favorites/tags` | Get User Tags |
| `PUT` | `/api/favorites/{stock_code}` | Update Favorite |
| `DELETE` | `/api/favorites/{stock_code}` | Remove Favorite |

## 自选股管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/favorites/` | Get Favorites |
| `POST` | `/api/favorites/` | Add Favorite |
| `GET` | `/api/favorites/check/{stock_code}` | Check Favorite |
| `POST` | `/api/favorites/sync-realtime` | Sync Favorites Realtime |
| `GET` | `/api/favorites/tags` | Get User Tags |
| `PUT` | `/api/favorites/{stock_code}` | Update Favorite |
| `DELETE` | `/api/favorites/{stock_code}` | Remove Favorite |

## financial-data

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/financial-data/health` | 财务数据服务健康检查 |
| `GET` | `/api/financial-data/latest/{symbol}` | 获取最新财务数据 |
| `GET` | `/api/financial-data/query/{symbol}` | 查询股票财务数据 |
| `GET` | `/api/financial-data/statistics` | 获取财务数据统计 |
| `POST` | `/api/financial-data/sync/single` | 同步单只股票财务数据 |
| `POST` | `/api/financial-data/sync/start` | 启动财务数据同步 |
| `GET` | `/api/financial-data/sync/statistics` | 获取同步统计信息 |

## 财务数据

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/financial-data/health` | 财务数据服务健康检查 |
| `GET` | `/api/financial-data/latest/{symbol}` | 获取最新财务数据 |
| `GET` | `/api/financial-data/query/{symbol}` | 查询股票财务数据 |
| `GET` | `/api/financial-data/statistics` | 获取财务数据统计 |
| `POST` | `/api/financial-data/sync/single` | 同步单只股票财务数据 |
| `POST` | `/api/financial-data/sync/start` | 启动财务数据同步 |
| `GET` | `/api/financial-data/sync/statistics` | 获取同步统计信息 |

## health

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | Health |
| `GET` | `/api/healthz` | Healthz |
| `GET` | `/api/readyz` | Readyz |

## historical-data

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/historical-data/compare/{symbol}` | Compare Data Sources |
| `GET` | `/api/historical-data/health` | Health Check |
| `GET` | `/api/historical-data/latest-date/{symbol}` | Get Latest Date |
| `POST` | `/api/historical-data/query` | Query Historical Data |
| `GET` | `/api/historical-data/query/{symbol}` | Get Historical Data |
| `GET` | `/api/historical-data/statistics` | Get Data Statistics |

## 历史数据

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/historical-data/compare/{symbol}` | Compare Data Sources |
| `GET` | `/api/historical-data/health` | Health Check |
| `GET` | `/api/historical-data/latest-date/{symbol}` | Get Latest Date |
| `POST` | `/api/historical-data/query` | Query Historical Data |
| `GET` | `/api/historical-data/query/{symbol}` | Get Historical Data |
| `GET` | `/api/historical-data/statistics` | Get Data Statistics |

## internal-messages

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/internal-messages/analyst-notes/{symbol}` | Get Analyst Notes |
| `GET` | `/api/internal-messages/analyst-notes/{symbol}` | Get Analyst Notes |
| `GET` | `/api/internal-messages/categories` | Get Categories |
| `GET` | `/api/internal-messages/categories` | Get Categories |
| `GET` | `/api/internal-messages/health` | Health Check |
| `GET` | `/api/internal-messages/health` | Health Check |
| `GET` | `/api/internal-messages/latest/{symbol}` | Get Latest Messages |
| `GET` | `/api/internal-messages/latest/{symbol}` | Get Latest Messages |
| `GET` | `/api/internal-messages/message-types` | Get Message Types |
| `GET` | `/api/internal-messages/message-types` | Get Message Types |
| `POST` | `/api/internal-messages/query` | Query Internal Messages |
| `POST` | `/api/internal-messages/query` | Query Internal Messages |
| `GET` | `/api/internal-messages/research-reports/{symbol}` | Get Research Reports |
| `GET` | `/api/internal-messages/research-reports/{symbol}` | Get Research Reports |
| `POST` | `/api/internal-messages/save` | Save Internal Messages |
| `POST` | `/api/internal-messages/save` | Save Internal Messages |
| `GET` | `/api/internal-messages/search` | Search Messages |
| `GET` | `/api/internal-messages/search` | Search Messages |
| `GET` | `/api/internal-messages/statistics` | Get Statistics |
| `GET` | `/api/internal-messages/statistics` | Get Statistics |

## multi-market

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/markets` | Get Supported Markets |
| `GET` | `/api/markets` | Get Supported Markets |
| `GET` | `/api/markets/{market}/stocks/search` | Search Stocks |
| `GET` | `/api/markets/{market}/stocks/search` | Search Stocks |
| `GET` | `/api/markets/{market}/stocks/{code}/daily` | Get Stock Daily Quotes |
| `GET` | `/api/markets/{market}/stocks/{code}/daily` | Get Stock Daily Quotes |
| `GET` | `/api/markets/{market}/stocks/{code}/info` | Get Stock Info |
| `GET` | `/api/markets/{market}/stocks/{code}/info` | Get Stock Info |
| `GET` | `/api/markets/{market}/stocks/{code}/quote` | Get Stock Quote |
| `GET` | `/api/markets/{market}/stocks/{code}/quote` | Get Stock Quote |

## model-capabilities

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/model-capabilities/badges` | Get All Badges |
| `POST` | `/api/model-capabilities/batch-init` | Batch Init Capabilities |
| `GET` | `/api/model-capabilities/capability-descriptions` | Get Capability Descriptions |
| `GET` | `/api/model-capabilities/default-configs` | Get Default Model Configs |
| `GET` | `/api/model-capabilities/depth-requirements` | Get Depth Requirements |
| `GET` | `/api/model-capabilities/model/{model_name}` | Get Model Capability |
| `POST` | `/api/model-capabilities/recommend` | Recommend Models |
| `POST` | `/api/model-capabilities/validate` | Validate Models |

## 模型能力管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/model-capabilities/badges` | Get All Badges |
| `POST` | `/api/model-capabilities/batch-init` | Batch Init Capabilities |
| `GET` | `/api/model-capabilities/capability-descriptions` | Get Capability Descriptions |
| `GET` | `/api/model-capabilities/default-configs` | Get Default Model Configs |
| `GET` | `/api/model-capabilities/depth-requirements` | Get Depth Requirements |
| `GET` | `/api/model-capabilities/model/{model_name}` | Get Model Capability |
| `POST` | `/api/model-capabilities/recommend` | Recommend Models |
| `POST` | `/api/model-capabilities/validate` | Validate Models |

## multi-period-sync

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/multi-period-sync/health` | Health Check |
| `GET` | `/api/multi-period-sync/period-comparison/{symbol}` | Compare Period Data |
| `POST` | `/api/multi-period-sync/start` | Start Multi Period Sync |
| `POST` | `/api/multi-period-sync/start-all-history` | Start All History Sync |
| `POST` | `/api/multi-period-sync/start-daily` | Start Daily Sync |
| `POST` | `/api/multi-period-sync/start-incremental` | Start Incremental Sync |
| `POST` | `/api/multi-period-sync/start-monthly` | Start Monthly Sync |
| `POST` | `/api/multi-period-sync/start-weekly` | Start Weekly Sync |
| `GET` | `/api/multi-period-sync/statistics` | Get Sync Statistics |
| `GET` | `/api/multi-period-sync/supported-periods` | Get Supported Periods |

## 多周期同步

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/multi-period-sync/health` | Health Check |
| `GET` | `/api/multi-period-sync/period-comparison/{symbol}` | Compare Period Data |
| `POST` | `/api/multi-period-sync/start` | Start Multi Period Sync |
| `POST` | `/api/multi-period-sync/start-all-history` | Start All History Sync |
| `POST` | `/api/multi-period-sync/start-daily` | Start Daily Sync |
| `POST` | `/api/multi-period-sync/start-incremental` | Start Incremental Sync |
| `POST` | `/api/multi-period-sync/start-monthly` | Start Monthly Sync |
| `POST` | `/api/multi-period-sync/start-weekly` | Start Weekly Sync |
| `GET` | `/api/multi-period-sync/statistics` | Get Sync Statistics |
| `GET` | `/api/multi-period-sync/supported-periods` | Get Supported Periods |

## news-data

| 方法 | 路径 | 说明 |
|---|---|---|
| `DELETE` | `/api/news-data/cleanup` | Cleanup Old News |
| `GET` | `/api/news-data/health` | Health Check |
| `GET` | `/api/news-data/latest` | Get Latest News |
| `POST` | `/api/news-data/query` | Query News Advanced |
| `GET` | `/api/news-data/query/{symbol}` | Query Stock News |
| `GET` | `/api/news-data/search` | Search News |
| `GET` | `/api/news-data/statistics` | Get News Statistics |
| `POST` | `/api/news-data/sync/single` | Sync Single Stock News |
| `POST` | `/api/news-data/sync/start` | Start News Sync |

## 新闻数据

| 方法 | 路径 | 说明 |
|---|---|---|
| `DELETE` | `/api/news-data/cleanup` | Cleanup Old News |
| `GET` | `/api/news-data/health` | Health Check |
| `GET` | `/api/news-data/latest` | Get Latest News |
| `POST` | `/api/news-data/query` | Query News Advanced |
| `GET` | `/api/news-data/query/{symbol}` | Query Stock News |
| `GET` | `/api/news-data/search` | Search News |
| `GET` | `/api/news-data/statistics` | Get News Statistics |
| `POST` | `/api/news-data/sync/single` | Sync Single Stock News |
| `POST` | `/api/news-data/sync/start` | Start News Sync |

## notifications

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/notifications` | List Notifications |
| `GET` | `/api/notifications/debug/redis_pool` | Debug Redis Pool |
| `POST` | `/api/notifications/read_all` | Mark All Read |
| `GET` | `/api/notifications/unread_count` | Get Unread Count |
| `POST` | `/api/notifications/{notif_id}/read` | Mark Read |

## paper

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/paper/account` | Get Account |
| `GET` | `/api/paper/account` | Get Account |
| `POST` | `/api/paper/order` | Place Order |
| `POST` | `/api/paper/order` | Place Order |
| `GET` | `/api/paper/orders` | List Orders |
| `GET` | `/api/paper/orders` | List Orders |
| `GET` | `/api/paper/positions` | List Positions |
| `GET` | `/api/paper/positions` | List Positions |
| `POST` | `/api/paper/reset` | Reset Account |
| `POST` | `/api/paper/reset` | Reset Account |

## queue

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/queue/stats` | Queue Stats |

## reports

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/reports/list` | Get Reports List |
| `GET` | `/api/reports/list` | Get Reports List |
| `DELETE` | `/api/reports/{report_id}` | Delete Report |
| `DELETE` | `/api/reports/{report_id}` | Delete Report |
| `GET` | `/api/reports/{report_id}/content/{module}` | Get Report Module Content |
| `GET` | `/api/reports/{report_id}/content/{module}` | Get Report Module Content |
| `GET` | `/api/reports/{report_id}/detail` | Get Report Detail |
| `GET` | `/api/reports/{report_id}/detail` | Get Report Detail |
| `GET` | `/api/reports/{report_id}/download` | Download Report |
| `GET` | `/api/reports/{report_id}/download` | Download Report |

## scheduler

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/scheduler/executions` | Get Job Executions |
| `GET` | `/api/scheduler/executions` | Get Job Executions |
| `DELETE` | `/api/scheduler/executions/{execution_id}` | Delete Execution |
| `DELETE` | `/api/scheduler/executions/{execution_id}` | Delete Execution |
| `POST` | `/api/scheduler/executions/{execution_id}/cancel` | Cancel Execution |
| `POST` | `/api/scheduler/executions/{execution_id}/cancel` | Cancel Execution |
| `POST` | `/api/scheduler/executions/{execution_id}/mark-failed` | Mark Execution Failed |
| `POST` | `/api/scheduler/executions/{execution_id}/mark-failed` | Mark Execution Failed |
| `GET` | `/api/scheduler/health` | Scheduler Health Check |
| `GET` | `/api/scheduler/health` | Scheduler Health Check |
| `GET` | `/api/scheduler/history` | Get All History |
| `GET` | `/api/scheduler/history` | Get All History |
| `GET` | `/api/scheduler/jobs` | List Jobs |
| `GET` | `/api/scheduler/jobs` | List Jobs |
| `GET` | `/api/scheduler/jobs/{job_id}` | Get Job Detail |
| `GET` | `/api/scheduler/jobs/{job_id}` | Get Job Detail |
| `GET` | `/api/scheduler/jobs/{job_id}/execution-stats` | Get Job Execution Stats |
| `GET` | `/api/scheduler/jobs/{job_id}/execution-stats` | Get Job Execution Stats |
| `GET` | `/api/scheduler/jobs/{job_id}/executions` | Get Single Job Executions |
| `GET` | `/api/scheduler/jobs/{job_id}/executions` | Get Single Job Executions |
| `GET` | `/api/scheduler/jobs/{job_id}/history` | Get Job History |
| `GET` | `/api/scheduler/jobs/{job_id}/history` | Get Job History |
| `PUT` | `/api/scheduler/jobs/{job_id}/metadata` | Update Job Metadata Route |
| `PUT` | `/api/scheduler/jobs/{job_id}/metadata` | Update Job Metadata Route |
| `POST` | `/api/scheduler/jobs/{job_id}/pause` | Pause Job |
| `POST` | `/api/scheduler/jobs/{job_id}/pause` | Pause Job |
| `POST` | `/api/scheduler/jobs/{job_id}/resume` | Resume Job |
| `POST` | `/api/scheduler/jobs/{job_id}/resume` | Resume Job |
| `POST` | `/api/scheduler/jobs/{job_id}/trigger` | Trigger Job |
| `POST` | `/api/scheduler/jobs/{job_id}/trigger` | Trigger Job |
| `GET` | `/api/scheduler/stats` | Get Scheduler Stats |
| `GET` | `/api/scheduler/stats` | Get Scheduler Stats |

## screening

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/screening/enhanced` | Enhanced Screening |
| `POST` | `/api/screening/enhanced` | Enhanced Screening |
| `GET` | `/api/screening/fields` | Get Supported Fields |
| `GET` | `/api/screening/fields` | Get Supported Fields |
| `GET` | `/api/screening/fields/{field_name}` | Get Field Info |
| `GET` | `/api/screening/fields/{field_name}` | Get Field Info |
| `GET` | `/api/screening/industries` | Get Industries |
| `GET` | `/api/screening/industries` | Get Industries |
| `POST` | `/api/screening/run` | Run Screening |
| `POST` | `/api/screening/run` | Run Screening |
| `POST` | `/api/screening/validate` | Validate Conditions |
| `POST` | `/api/screening/validate` | Validate Conditions |

## social-media

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/social-media/health` | Health Check |
| `GET` | `/api/social-media/health` | Health Check |
| `GET` | `/api/social-media/latest/{symbol}` | Get Latest Messages |
| `GET` | `/api/social-media/latest/{symbol}` | Get Latest Messages |
| `GET` | `/api/social-media/platforms` | Get Supported Platforms |
| `GET` | `/api/social-media/platforms` | Get Supported Platforms |
| `POST` | `/api/social-media/query` | Query Social Media Messages |
| `POST` | `/api/social-media/query` | Query Social Media Messages |
| `POST` | `/api/social-media/save` | Save Social Media Messages |
| `POST` | `/api/social-media/save` | Save Social Media Messages |
| `GET` | `/api/social-media/search` | Search Messages |
| `GET` | `/api/social-media/search` | Search Messages |
| `GET` | `/api/social-media/sentiment-analysis/{symbol}` | Get Sentiment Analysis |
| `GET` | `/api/social-media/sentiment-analysis/{symbol}` | Get Sentiment Analysis |
| `GET` | `/api/social-media/statistics` | Get Statistics |
| `GET` | `/api/social-media/statistics` | Get Statistics |

## stock-data

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/stock-data/basic-info/{symbol}` | Get Stock Basic Info |
| `GET` | `/api/stock-data/combined/{symbol}` | Get Combined Stock Data |
| `GET` | `/api/stock-data/list` | Get Stock List |
| `GET` | `/api/stock-data/markets` | Get Market Summary |
| `GET` | `/api/stock-data/quotes/{symbol}` | Get Market Quotes |
| `GET` | `/api/stock-data/search` | Search Stocks |
| `GET` | `/api/stock-data/sync-status/quotes` | Get Quotes Sync Status |

## 股票数据

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/stock-data/basic-info/{symbol}` | Get Stock Basic Info |
| `GET` | `/api/stock-data/combined/{symbol}` | Get Combined Stock Data |
| `GET` | `/api/stock-data/list` | Get Stock List |
| `GET` | `/api/stock-data/markets` | Get Market Summary |
| `GET` | `/api/stock-data/quotes/{symbol}` | Get Market Quotes |
| `GET` | `/api/stock-data/search` | Search Stocks |
| `GET` | `/api/stock-data/sync-status/quotes` | Get Quotes Sync Status |

## stock-sync

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/stock-sync/batch` | Sync Batch Stocks |
| `POST` | `/api/stock-sync/single` | Sync Single Stock |
| `GET` | `/api/stock-sync/status/{symbol}` | Get Sync Status |

## 股票数据同步

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/stock-sync/batch` | Sync Batch Stocks |
| `POST` | `/api/stock-sync/single` | Sync Single Stock |
| `GET` | `/api/stock-sync/status/{symbol}` | Get Sync Status |

## stocks

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/stocks/{code}/fundamentals` | Get Fundamentals |
| `GET` | `/api/stocks/{code}/fundamentals` | Get Fundamentals |
| `GET` | `/api/stocks/{code}/kline` | Get Kline |
| `GET` | `/api/stocks/{code}/kline` | Get Kline |
| `GET` | `/api/stocks/{code}/news` | Get News |
| `GET` | `/api/stocks/{code}/news` | Get News |
| `GET` | `/api/stocks/{code}/quote` | Get Quote |
| `GET` | `/api/stocks/{code}/quote` | Get Quote |

## streaming

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/stream/batches/{batch_id}` | Stream Batch Progress |
| `GET` | `/api/stream/tasks/{task_id}` | Stream Task Progress |

## Multi-Source Sync

| 方法 | 路径 | 说明 |
|---|---|---|
| `DELETE` | `/api/sync/multi-source/cache` | Clear Sync Cache |
| `GET` | `/api/sync/multi-source/history` | Get Sync History |
| `GET` | `/api/sync/multi-source/recommendations` | Get Sync Recommendations |
| `GET` | `/api/sync/multi-source/sources/current` | Get Current Data Source |
| `GET` | `/api/sync/multi-source/sources/status` | Get Data Sources Status |
| `GET` | `/api/sync/multi-source/status` | Get Sync Status |
| `POST` | `/api/sync/multi-source/stock_basics/run` | Run Stock Basics Sync |
| `POST` | `/api/sync/multi-source/test-sources` | Test Data Sources |

## sync

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/sync/stock_basics/run` | Run Stock Basics Sync |
| `GET` | `/api/sync/stock_basics/status` | Get Stock Basics Status |

## system

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/system/config/summary` | 配置概要（已屏蔽敏感项，需管理员） |
| `GET` | `/api/system/config/summary` | 配置概要（已屏蔽敏感项，需管理员） |
| `GET` | `/api/system/config/validate` | 验证配置完整性 |
| `GET` | `/api/system/config/validate` | 验证配置完整性 |

## database

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/database/backup` | Create Backup |
| `GET` | `/api/system/database/backups` | List Backups |
| `DELETE` | `/api/system/database/backups/{backup_id}` | Delete Backup |
| `POST` | `/api/system/database/cleanup` | Cleanup Old Data |
| `POST` | `/api/system/database/cleanup/analysis` | Cleanup Analysis Results |
| `POST` | `/api/system/database/cleanup/logs` | Cleanup Operation Logs |
| `POST` | `/api/system/database/export` | Export Data |
| `POST` | `/api/system/database/import` | Import Data |
| `GET` | `/api/system/database/stats` | Get Database Stats |
| `GET` | `/api/system/database/status` | Get Database Status |
| `POST` | `/api/system/database/test` | Test Database Connections |

## 数据库管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/database/backup` | Create Backup |
| `GET` | `/api/system/database/backups` | List Backups |
| `DELETE` | `/api/system/database/backups/{backup_id}` | Delete Backup |
| `POST` | `/api/system/database/cleanup` | Cleanup Old Data |
| `POST` | `/api/system/database/cleanup/analysis` | Cleanup Analysis Results |
| `POST` | `/api/system/database/cleanup/logs` | Cleanup Operation Logs |
| `POST` | `/api/system/database/export` | Export Data |
| `POST` | `/api/system/database/import` | Import Data |
| `GET` | `/api/system/database/stats` | Get Database Stats |
| `GET` | `/api/system/database/status` | Get Database Status |
| `POST` | `/api/system/database/test` | Test Database Connections |

## operation_logs

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/logs/clear` | Clear Operation Logs |
| `POST` | `/api/system/logs/create` | Create Operation Log |
| `GET` | `/api/system/logs/export/csv` | Export Logs Csv |
| `GET` | `/api/system/logs/list` | Get Operation Logs |
| `GET` | `/api/system/logs/stats` | Get Operation Log Stats |
| `GET` | `/api/system/logs/{log_id}` | Get Operation Log Detail |

## 操作日志

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/logs/clear` | Clear Operation Logs |
| `POST` | `/api/system/logs/create` | Create Operation Log |
| `GET` | `/api/system/logs/export/csv` | Export Logs Csv |
| `GET` | `/api/system/logs/list` | Get Operation Logs |
| `GET` | `/api/system/logs/stats` | Get Operation Log Stats |
| `GET` | `/api/system/logs/{log_id}` | Get Operation Log Detail |

## logs

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/system-logs/export` | Export Logs |
| `GET` | `/api/system/system-logs/files` | List Log Files |
| `DELETE` | `/api/system/system-logs/files/{filename}` | Delete Log File |
| `POST` | `/api/system/system-logs/read` | Read Log File |
| `GET` | `/api/system/system-logs/statistics` | Get Log Statistics |

## 系统日志

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/system/system-logs/export` | Export Logs |
| `GET` | `/api/system/system-logs/files` | List Log Files |
| `DELETE` | `/api/system/system-logs/files/{filename}` | Delete Log File |
| `POST` | `/api/system/system-logs/read` | Read Log File |
| `GET` | `/api/system/system-logs/statistics` | Get Log Statistics |

## tags

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/tags/` | List Tags |
| `POST` | `/api/tags/` | Create Tag |
| `PUT` | `/api/tags/{tag_id}` | Update Tag |
| `DELETE` | `/api/tags/{tag_id}` | Delete Tag |

## 标签管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/tags/` | List Tags |
| `POST` | `/api/tags/` | Create Tag |
| `PUT` | `/api/tags/{tag_id}` | Update Tag |
| `DELETE` | `/api/tags/{tag_id}` | Delete Tag |

## usage-statistics

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/usage/cost/by-model` | 按模型统计成本 |
| `GET` | `/api/usage/cost/by-provider` | 按供应商统计成本 |
| `GET` | `/api/usage/cost/daily` | 每日成本统计 |
| `GET` | `/api/usage/records` | 获取使用记录 |
| `DELETE` | `/api/usage/records/old` | 删除旧记录 |
| `GET` | `/api/usage/statistics` | 获取使用统计 |

## 使用统计

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/usage/cost/by-model` | 按模型统计成本 |
| `GET` | `/api/usage/cost/by-provider` | 按供应商统计成本 |
| `GET` | `/api/usage/cost/daily` | 每日成本统计 |
| `GET` | `/api/usage/records` | 获取使用记录 |
| `DELETE` | `/api/usage/records/old` | 删除旧记录 |
| `GET` | `/api/usage/statistics` | 获取使用统计 |

## websocket

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/ws/stats` | Get Websocket Stats |
