---
title: TradingAgents-CN 可用 LLM API 费用 / 订阅 / 购买渠道深度对比
date: 2026-06-08
scope: 基于 TradingAgents-CN v1.0.1 model_catalog.py 与 .env.example 实际支持的 provider
currency: 国产模型 = 人民币 ¥/百万 tokens；海外模型 = 美元 $/百万 tokens
note: 价格随厂商调整频繁变动，落库/计费前请以各厂商官方定价页实时数字为准
---

# TradingAgents-CN 可用 LLM API：费用 · 订阅 · 购买渠道

> 研究日期 **2026-06-08**。本报告只覆盖 TradingAgents-CN 代码里**真实支持**的 provider（见
> [model_catalog.py](../../TradingAgents-CN/tradingagents/llm_clients/model_catalog.py) 与
> [.env.example](../../TradingAgents-CN/.env.example)）：DeepSeek、通义千问 Qwen、智谱 GLM、OpenAI、
> Anthropic Claude、Google Gemini，外加聚合/购买渠道 硅基流动、AIHubMix、302.AI、OpenRouter、百度千帆、OneAPI。

---

## 0. 结论速览（TL;DR）

- **最省钱的可用组合**：智谱 `GLM-4-Flash`（**免费**）→ DeepSeek `deepseek-chat`（¥1/¥2 每百万 token）→ 通义 `qwen-turbo`（¥0.3/¥0.6）。跑 TradingAgents-CN 多智能体分析，国产模型性价比碾压海外。
- **国内用户首选渠道**：要用 Claude/GPT 又只有人民币 → **AIHubMix**（项目官方推荐/赞助，OpenAI 兼容、支付宝充值）；只用国产模型 → **硅基流动**（直连免费额度）或 **百度千帆**（合规发票）。
- **三家海外厂商（OpenAI / Anthropic / Google）API 都是纯按量付费，没有"API 订阅"**。ChatGPT Plus / Claude Pro / Google AI Pro 这些 $20/月订阅 **≠ API**，不能用来跑程序。
- **三家国产厂商订阅情况**：DeepSeek 纯按量无订阅；通义有"节省计划 + Token 资源包"；智谱有"GLM Coding Plan 包月/季/年 + 资源包"。
- ⚠️ **重要工程提醒**：TradingAgents-CN model_catalog 里好几个模型 ID 到 2026 年中已**改名/弃用/下线**（DeepSeek 旧 ID 2026-07-24 停用、Claude 3.x 多个已退役、gemini-2.0-flash 已于 2026-06-01 弃用）。见 [§1](#1-️-模型-id-失效提醒先看这个)。

---

## 1. ⚠️ 模型 ID 失效提醒（先看这个）

研究中发现一个**比价格更紧迫**的问题：项目 catalog 固定的模型 ID 很多已被厂商改名或下线。直接照搬会在近期报错。

| 项目中的模型 ID | 状态（2026-06） | 现行替代 / 说明 |
|---|---|---|
| `deepseek-chat` / `deepseek-reasoner` | **别名，2026-07-24 23:59 后停用** | 迁移到 `deepseek-v4-flash`（或 `-pro`） |
| `qwen-max-longcontext` | **未确认为在售独立 SKU** | 由 `qwen-long` 取代（¥0.5/¥2） |
| `glm-4-long` | **官方价目表未确认** | 长上下文转由 GLM-4.5/4.6 长文模型承接 |
| `claude-3-5-haiku` | **一方 API 已退役**（Bedrock/Vertex 仍在） | Haiku 4.5（$1/$5） |
| `claude-3-5-sonnet` / `claude-3-7-sonnet` | **已下价目表** | Sonnet 4.6（$3/$15） |
| `claude-sonnet-4` / `claude-opus-4` | **已弃用**（仍可调用） | Sonnet 4.6 / Opus 4.5+（注意新 Opus 仅 $5/$25，比 Opus 4 便宜约 3 倍） |
| `gpt-4o` / `gpt-4o-mini` | **遗留 grandfathered**（老集成仍可用） | GPT-4.1 系列 / GPT-5.x（新用户默认） |
| `gpt-4.1-mini` / `gpt-4.1-nano` | 仍在售 | 可继续用 |
| `gemini-2.0-flash` | **2026-06-01 已弃用** | `gemini-2.5-flash-lite` |
| `gemini-2.5-flash` / `flash-lite` / `2.5-pro` | 仍在售 | 可继续用 |

> 建议：把这些 ID 当作"出厂默认值"，在 Web 配置页用"Custom model ID"覆盖为现行 ID，或升级项目的 model_catalog。

---

## 2. 国产模型 API 价格表（¥/百万 tokens）

> 单位人民币元，每百万 tokens；输入 / 输出分列。"缓存命中"指上下文缓存命中价。

### 2.1 DeepSeek（api.deepseek.com）

| 模型 | 输入(缓存命中) | 输入(未命中) | 输出 | 备注 | 来源 |
|---|---|---|---|---|---|
| `deepseek-chat`（→v4-flash, 非思考） | ¥0.02 | ¥1 | ¥2 | 别名，2026-07-24 弃用 | [官方定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
| `deepseek-reasoner`（→v4-flash, 思考） | ¥0.02 | ¥1 | ¥2 | 别名，同价 | [官方定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
| `deepseek-v4-flash`（现行经济款） | ¥0.02 | ¥1 | ¥2 | — | [官方定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
| `deepseek-v4-pro`（旗舰推理/代码） | ¥0.025 | ¥3 | ¥6 | — | [USD页](https://api-docs.deepseek.com/quick_start/pricing-details-usd) |

- **订阅**：❌ 无。纯按量付费，无包月、无资源包。
- **购买渠道**：开放平台控制台**充值**；个人/企业均可，国内支付需**实名认证**；新用户注册送 **500 万 token**（约 5M）免费额度。[3]
- **折扣**：主要靠**上下文缓存命中**（命中价比未命中便宜约 98%）；官方页已无"错峰时段 5 折"。

### 2.2 通义千问 Qwen / 阿里云百炼（DashScope）

| 模型 | 输入 | 输出 | 备注 | 来源 |
|---|---|---|---|---|
| `qwen-turbo` | ¥0.3 | ¥0.6 | 扁平价 | [百炼定价](https://help.aliyun.com/zh/model-studio/model-pricing) |
| `qwen-plus` | ¥0.8 | ¥4.8 | 按上下文分档；思考模式输出更高 | [百炼定价](https://help.aliyun.com/zh/model-studio/model-pricing) |
| `qwen-max`（≈qwen3-max 档） | ¥2.5 (≤32K) | ¥10 (≤32K) | 分档计价 | [百炼定价](https://help.aliyun.com/zh/model-studio/model-pricing) |
| `qwen3-max` | ¥2.5 / ¥4 (32–128K) | ¥10 / ¥16 (32–128K) | 按上下文长度分档 | [阿里云社区](https://developer.aliyun.com/article/1714977) |
| `qwen-long`（替代 longcontext） | ¥0.5 | ¥2 | 长上下文经济款 | [百炼定价](https://help.aliyun.com/zh/model-studio/model-pricing) |

- **订阅**：✅ 有两种。① **节省计划**（承诺月消费换阶梯折扣，最高约 53% off）；② **Token 资源包**（预付费 token 包）。两者与默认按量付费并存；**Batch API 另享输入+输出 5 折**。[6][8]
- **免费额度**：新开百炼总计 **>7000 万 token** 赠送，**每个主力模型 100 万 token、90 天有效**。[4][6]
- **购买渠道**：阿里云账户充值（支付宝/微信/对公），个人/企业均可，需阿里云**实名认证**。[4][6]

### 2.3 智谱 GLM / BigModel（bigmodel.cn）

| 模型 | 输入 | 输出 | 备注 | 来源 |
|---|---|---|---|---|
| `glm-4-flash` | **¥0 免费** | **¥0 免费** | 智谱首个免费 API；现行免费旗舰为 GLM-4.5/4.7-Flash | [免费模型文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash) |
| `glm-4-flashx` | ¥0.1 | ¥0.1 | 每亿 token 10 元 | [智源社区](https://hub.baai.ac.cn/view/37676) |
| `glm-4-air` | ¥1 | ¥1 | 输入=输出单一费率 | [OSChina](https://www.oschina.net/news/346496) |
| `glm-4-plus` | ¥5 | ¥5 | 从 ¥50 降 90% 至 ¥5（2025-04-24 起） | [OSChina](https://www.oschina.net/news/346496) |
| `glm-4-long` | 未确认 | — | 官方表未确认现价，按弃用处理 | [智谱定价](https://open.bigmodel.cn/pricing) |

> 注：GLM-4 系多数模型输入价=输出价（单一费率），与 DeepSeek/Qwen 分列不同。

- **订阅**：✅ 有 **GLM Coding Plan**（包月/季/年）：Lite ¥49/月、Pro ¥149/月、Max ¥469/月（连续包季约 9 折、包年约 7 折）。另有按量付费 + 资源包。[14][15]
- **免费/新户**：`glm-4-flash`、`GLM-4.5/4.7-Flash` 完全免费；新用户/实名推荐可领 **2000 万～2 亿** token 资源包。[10][11]
- **购买渠道**：控制台充值/买资源包/Coding Plan，支持**微信支付、支付宝**，需**实名认证**。[14][15]

---

## 3. 海外模型 API 价格表（$/百万 tokens）

> 单位美元，每百万 tokens；输入 / 输出分列，含缓存输入价（如有）。

### 3.1 OpenAI

| 模型 | 输入 | 输出 | 缓存输入 | 备注 | 来源 |
|---|---|---|---|---|---|
| `gpt-4o` | $2.50 | $10.00 | $1.25 | 遗留 grandfathered，缓存 5 折 | [OpenAI 定价](https://openai.com/api/pricing/) |
| `gpt-4o-mini` | $0.15 | $0.60 | $0.075 | 遗留 | [OpenAI 定价](https://openai.com/api/pricing/) |
| `gpt-4.1-mini` | $0.40 | $1.60 | $0.10 | 现行在售 | [OpenAI 定价](https://openai.com/api/pricing/) |
| `gpt-4.1-nano` | $0.10 | $0.40 | $0.025 | OpenAI 最便宜文本模型 | [OpenAI 定价](https://openai.com/api/pricing/) |

- **订阅**：❌ API 无订阅，纯预付费 credits 按量。**ChatGPT Plus $20/月、Pro $200/月 ≠ API**（消费级聊天，独立计费）。
- **国内购买**：需**海外信用卡 + 受支持地区**，大陆**不能直接付费**，普遍走聚合中转（见 §5）。

### 3.2 Anthropic Claude（官方文档实测）

| 模型 | 输入 | 输出 | 缓存读取 | 备注 | 来源 |
|---|---|---|---|---|---|
| `claude-3-5-haiku` | $0.80 | $4.00 | $0.08 | 一方 API 已退役；batch $0.40/$2.00 | [Claude 官方定价](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-3-5-sonnet` | — | — | — | 已下表（原 $3/$15），改用 Sonnet 4.6 | [Claude 官方定价](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-3-7-sonnet` | — | — | — | 已下表（原 $3/$15） | [Claude 官方定价](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-sonnet-4` | $3.00 | $15.00 | $0.30 | 已弃用仍可调；batch $1.50/$7.50 | [Claude 官方定价](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-opus-4` | $15.00 | $75.00 | $1.50 | 已弃用；新 Opus 4.5+ 仅 $5/$25 | [Claude 官方定价](https://platform.claude.com/docs/en/about-claude/pricing) |

- **缓存/批量**：5 分钟缓存写 1.25×、1 小时写 2×、缓存命中读 0.1×（省 90%）；**Batch API 输入+输出 5 折**，可叠加缓存。
- **订阅**：❌ API 无订阅，按量 credits。**Claude.ai Pro $20/月、Max $100+/月 ≠ API**。
- **国内购买**：不官方服务大陆，需海外卡 + 受支持地区；走聚合中转。

### 3.3 Google Gemini API

| 模型 | 输入 | 输出 | 缓存输入 | 备注 | 来源 |
|---|---|---|---|---|---|
| `gemini-2.5-flash` | $0.30 | $2.50 | ~$0.03 | ⚠️ 官方一处快照显示 $0.50/$2.00，存冲突，落库前核对 | [Gemini 定价](https://ai.google.dev/gemini-api/docs/pricing) · [校验](https://costgoat.com/pricing/gemini-api) |
| `gemini-2.5-flash-lite` | $0.10 | $0.40 | ~$0.01 | GA，已确认 | [Gemini 定价](https://ai.google.dev/gemini-api/docs/pricing) |
| `gemini-2.0-flash` | $0.10 | $0.40 | ~$0.01 | **2026-06-01 已弃用**，迁 2.5 Flash-Lite | [Gemini 定价](https://ai.google.dev/gemini-api/docs/pricing) |
| `gemini-2.5-pro` | $1.25 / $2.50(>200K) | $10 / $15(>200K) | $0.125 / $0.25 | 按上下文分档 | [Gemini 定价](https://ai.google.dev/gemini-api/docs/pricing) |

- **免费层**：Google AI Studio 对 **Flash / Flash-Lite** 提供免费层（约 30 RPM / 1500 次每天），免信用卡。**2026-04-01 起 Pro 退出免费层**，2.5 Pro 需付费 key 或 AI Pro/Ultra 订阅。
- **订阅**：API 按量付费；有免费层但非"订阅"。
- **国内购买**：大陆非受支持地区，需海外卡，走聚合中转。

---

## 4. 订阅方式一览（"是否有订阅"专项）

| Provider | API 是否有订阅 | 订阅/资源包形态 | 消费级订阅（≠API） | 来源 |
|---|---|---|---|---|
| DeepSeek | ❌ 无 | 纯按量付费 | — | [定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) |
| 通义千问 | ✅ 有 | 节省计划（最高~53% off）+ Token 资源包 + Batch 5 折 | — | [节省计划](https://help.aliyun.com/zh/model-studio/savings-plan-and-resource-package) |
| 智谱 GLM | ✅ 有 | GLM Coding Plan 包月/季/年（¥49/¥149/¥469 月）+ 资源包 | — | [Coding Plan](https://docs.bigmodel.cn/cn/coding-plan/overview) |
| OpenAI | ❌ 无 | 预付费 credits 按量 | ChatGPT Plus $20 / Pro $200 | [API 定价](https://openai.com/api/pricing/) |
| Anthropic | ❌ 无 | 按量 credits（+缓存/批量折扣） | Claude Pro $20 / Max $100+ | [API vs 订阅](https://www.cloudzero.com/blog/claude-api-pricing/) |
| Google Gemini | ❌ 无（有免费层） | 按量付费 | Google AI Pro / Ultra | [定价](https://ai.google.dev/gemini-api/docs/pricing) |

**一句话**：海外三家"想要订阅省钱"是误区——订阅买的是网页聊天，跑 TradingAgents-CN 必须走 API 按量付费。国产里只有通义、智谱提供 API 侧的预付费/折扣计划。

---

## 5. 购买渠道 / 聚合平台对比

| 渠道 | 海外闭源(GPT/Claude/Gemini) | 国产/开源 | 计费 | 折扣 vs 官方 | 大陆支付 | 订阅 | 来源/官网 |
|---|---|---|---|---|---|---|---|
| **硅基流动 SiliconFlow** | ❌ | ✅(源站托管) | 按量+送¥14 | 源站价 | ✅ 直连 | 无 | [计费规则](https://docs.siliconflow.com/cn/faqs/billing-rules) · [官网](https://cloud.siliconflow.cn) |
| **AIHubMix**（项目推荐） | ✅ | ✅ | 按量 | 充值约 86 折 / 新人首充 ¥3.5*¹ | ✅ 支付宝/Stripe | 无 | [文档](https://docs.aihubmix.com/cn) · [官网](https://aihubmix.com) |
| **302.AI** | ✅ | ✅ | PTC 积分 $1=1PTC，最低 $5 | 无明显折扣 | ✅ 充值(人民币)*² | 无 | [定价](https://302ai.cn/pricing/) · [官网](https://302.ai) |
| **OpenRouter** | ✅ | ✅ | credits，推理不加价 + 5.5% 手续费 | 推理=官方价 | ⚠️ 国际卡/crypto，支付宝不稳*² | 无 | [定价](https://openrouter.ai/pricing) · [FAQ](https://openrouter.ai/docs/faq) |
| **百度千帆 Qianfan** | ❌ | ✅(ERNIE+第三方开源) | 后付费/量包/TPM | 量包多 85 折 | ✅ 完全友好 | ✅ 资源包/TPM/算力 | [计费](https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya) · [免费额度](https://cloud.baidu.com/doc/qianfan/s/Imi2rpirg) |
| **OneAPI / New-API** | 取决上游 | 取决上游 | 开源自部署，只付上游 | n/a | n/a | n/a | [one-api](https://github.com/songquanpeng/one-api) · [new-api](https://github.com/QuantumNous/new-api) |

\*¹ AIHubMix 充值折扣（约 86 折、新人首充 ¥3.5/美元）来自第三方教程而非官方原文，汇率优惠常变，**以充值页实时为准**。
\*² 302.AI / OpenRouter 的支付宝可用性来自第三方资料，官方未明确承诺，视为不稳定。

**渠道要点：**
- **硅基流动**：国内自营开源模型推理云，OpenAI 兼容，注册送 ¥14（约 2000 万 token），有约 8 个免费小模型；**拿不到 GPT/Claude**。只用 DeepSeek/Qwen 最省事。
- **AIHubMix**（TradingAgents-CN 官方推荐/赞助）：合规聚合，一个 key 覆盖 GPT+Claude+Gemini+国产，OpenAI 兼容、零改代码，支付宝充值——**国内跑 Claude/GPT 最省心**。
- **302.AI**：企业级聚合，PTC 积分制（$1=1PTC，余额永久），含图像/视频模型；适合 LLM+多模态。
- **OpenRouter**：海外统一网关，模型最全、推理**不加价**（充值收 5.5% 手续费）；门槛是国际卡+科学上网。
- **百度千帆**：百度智能云一站式，文心 ERNIE + DeepSeek/Qwen/Kimi 等第三方开源，ERNIE-3.5-8K 永久免费，发票合规；**无海外闭源**。
- **OneAPI/New-API**：开源**自部署**网关，把多家上游统一成 OpenAI 兼容格式，软件免费、只付上游用量；适合已有多家 key 想本地统一管理。

---

## 6. 给 TradingAgents-CN 用户的配置建议

1. **零成本起步**：智谱 `GLM-4-Flash`（免费）或硅基流动免费模型先跑通多智能体流水线，验证再升级。
2. **低成本主力（国内直连）**：DeepSeek `deepseek-v4-flash`（注意别再写 `deepseek-chat`，7-24 后失效）¥1/¥2，或 `qwen-plus`。深度推理环节用 `deepseek-v4-pro` / `qwen3-max`。
3. **要用 Claude/GPT 做复盘**：走 **AIHubMix**（项目 .env 里填 `AIHUBMIX_API_KEY` + `AIHUBMIX_BASE_URL=https://aihubmix.com/v1`，OpenAI 兼容），支付宝充值即可，免海外卡。
4. **成本控制**：能开缓存就开（DeepSeek/Claude 缓存命中省 90%+）；大批量分析用通义/Claude 的 **Batch 5 折**；订阅只对重度高频的智谱 Coding Plan 才划算。
5. **别买消费级订阅当 API**：ChatGPT Plus / Claude Pro 不能驱动本项目。

---

## 7. 局限与数据来源

**局限**：(1) LLM 价格调整极频繁，本表为 2026-06-08 快照；(2) 部分官方定价页为 JS 渲染或对自动抓取返回 403（bigmodel.cn、aliyun model-pricing、openai.com、ai.google.dev、302ai.cn），相关数字以官方帮助中心文本 + 2 个以上二手源交叉验证，已逐项标注"未确认"；(3) 聚合平台充值折扣/支付宝可用性多来自第三方教程，充值前以平台实时页为准；(4) Gemini 2.5 Flash 价格存在 $0.30/$2.50 与 $0.50/$2.00 冲突，需核对。

**来源（国产）**：[1] DeepSeek 官方定价 https://api-docs.deepseek.com/zh-cn/quick_start/pricing ・ [2] EN https://api-docs.deepseek.com/quick_start/pricing ・ [3] USD/额度 https://api-docs.deepseek.com/quick_start/pricing-details-usd ・ [4] 阿里云社区 https://developer.aliyun.com/article/1714977 ・ [5] 百炼官方定价 https://help.aliyun.com/zh/model-studio/model-pricing ・ [6] 计费规则 https://help.aliyun.com/zh/model-studio/product-billing ・ [7] Qwen 价格表解读 https://www.dayuyun.com/news/10446.html ・ [8] 节省计划 https://help.aliyun.com/zh/model-studio/savings-plan-and-resource-package ・ [9] 智谱定价 https://open.bigmodel.cn/pricing ・ [10] GLM-4.7-Flash 免费 https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash ・ [11] https://zhuanlan.zhihu.com/p/2000274493264905320 ・ [12] https://hub.baai.ac.cn/view/37676 ・ [13] https://www.oschina.net/news/346496 ・ [14] GLM Coding Plan https://docs.bigmodel.cn/cn/coding-plan/overview ・ [15] https://codingplan.org/plans/zhipu

**来源（海外）**：OpenAI https://openai.com/api/pricing/ ・ Claude 官方文档 https://platform.claude.com/docs/en/about-claude/pricing ・ Claude 消费/API 区分 https://www.cloudzero.com/blog/claude-api-pricing/ ・ Gemini https://ai.google.dev/gemini-api/docs/pricing ・ 校验 https://costgoat.com/pricing/gemini-api ・ https://findskill.ai/blog/gemini-api-pricing-guide/

**来源（渠道）**：硅基流动 https://docs.siliconflow.com/cn/faqs/billing-rules ・ AIHubMix https://docs.aihubmix.com/cn ・ 302.AI https://302ai.cn/pricing/ ・ OpenRouter https://openrouter.ai/pricing , https://openrouter.ai/docs/faq ・ 百度千帆 https://cloud.baidu.com/doc/qianfan/s/wmh4sv6ya , https://cloud.baidu.com/doc/qianfan/s/Imi2rpirg ・ One-API https://github.com/songquanpeng/one-api ・ New-API https://github.com/QuantumNous/new-api
