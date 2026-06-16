# 中文金融 Agent 本地化 Embedding 选型报告

> 场景：TradingAgents-CN 个股分析「A/B 记忆环」（ChromaDB `FinancialSituationMemory`）的向量嵌入选型。
> 目标：在「优先本地离线、零外部 API 依赖」约束下，给出可落地的中文金融 embedding 方案。
> 日期：2026-06-12 ｜ 模式：deep research（20+ 来源 + 本机实测）

---

## 摘要（Executive Summary）

本项目记忆环嵌入的不是辩论文字，而是 `market + sentiment + news + fundamentals` 四份报告拼接成的**长篇中文金融文本**（常达数 KB），写入量极小（每次分析约 5 个 collection 各写 1 条 + 少量读），跨日复用。因此选型的决定性维度不是吞吐，而是**①中文金融语义质量 ②长文本容纳能力 ③完全离线/零账户依赖**。

当前 fallback 是 ChromaDB 默认的 `all-MiniLM-L6-v2`（384 维，英文为主，**最大仅 256 token**）。本会话实测发现两个真实问题：(1) 在本机（Intel x86_64 Mac）上，ChromaDB 默认会选 **CoreML 执行器，批量推理直接崩溃**（CoreML error -1）、冷启动单条耗时 13.3s——**必须强制 `CPUExecutionProvider`** 才能用；(2) 强制 CPU 后可用（384 维、warm ~100ms/条、4 文档粗粒度中文检索 3/3 命中），但 256-token 上限会**严重截断**本项目的长 situation 文本，且中文细粒度判别力偏弱。

结论：**主推 `bge-m3` 本地部署**（中文原生 + 8192 长上下文 + 1024 维，正好匹配长 situation 文本，完全离线）；以「强制 CPU 的 MiniLM」作为零依赖兜底；`DashScope text-embedding-v4` 仅作为「愿意接受云依赖时」的可选高质量替换。

---

## 一、本项目需求分析

记忆环的工作方式（已对照 `tradingagents/agents/utils/memory.py` 源码核实）：

- **嵌入键（situation）** = 四份客观报告拼接：`market_report + sentiment_report + news_report + fundamentals_report`。这是**纯中文金融长文本**（个股分析一次产出常 2–6 KB），不是简短句子。
- **写**：`add_situations([(situation, recommendation)])`，每次分析在 bull/bear/trader/judge/risk 共 5 个 collection 各写约 1 条。
- **读**：`get_memories(current_situation, n_matches=2)`，只做嵌入 + 向量近邻，**不调用 LLM**。
- **量级**：单次分析总嵌入调用约 10 次以内；跨日累积也只到百/千条级。**吞吐与延迟几乎不构成约束**。
- **硬约束**（来自项目记忆与既定决策）：知识库/记忆只走本地，优先**完全离线、零外部 API 依赖**（此前 DashScope 账户欠费导致嵌入静默返回零向量、记忆 no-op，正是要规避的失败模式）；持久化目录落 `Knowledge_Wiki/.kb-vectors/ta-memory`。

由此推出选型权重：**中文金融质量 > 长文本容纳 > 离线/零依赖 ≫ 吞吐/延迟**。其中「长文本容纳」尤为关键——本项目 situation 文本远超 256 token，**MiniLM 会截断到前 256 个 word-piece**，丢掉绝大部分基本面/新闻信息，这是默认方案对本场景最致命的短板。

---

## 二、本地机器性能实测（本会话）

机器：`macOS-14.7.6-x86_64`（Intel），12 逻辑核，无 NVIDIA GPU；`onnxruntime 1.22.0`，可用执行器 `['CoreMLExecutionProvider','AzureExecutionProvider','CPUExecutionProvider']`。

实测 ChromaDB 默认 `DefaultEmbeddingFunction`（= `all-MiniLM-L6-v2` ONNX）：

| 配置 | 结果 |
|---|---|
| 默认（自动选 CoreML） | ❌ 单条嵌入 **冷启动 13.3s**；批量 20 条 **直接崩溃**（`CoreMLExecutionProvider … error code: -1`，神经网络模型无法在该 Intel CoreML 上执行） |
| 强制 `preferred_providers=["CPUExecutionProvider"]` | ✅ 384 维；冷启动 1097ms；**warm 单条 ~101ms（10 条/秒）**；批量 20 条 2104ms（105ms/条均摊，批量无加速） |
| 中文检索 sanity（4 文档语料 + 3 同义改写 query） | ✅ **3/3 命中**，top 相似度 0.78–0.85 vs 次优 0.65（粗粒度区分良好） |

**两条可执行结论**：
1. 本机用任何 ChromaDB ONNX 嵌入，**必须显式传 `preferred_providers=["CPUExecutionProvider"]`**，否则 CoreML 会崩或极慢——这同样适用于我们 `memory.py` 的本地分支（当前用 `DefaultEmbeddingFunction()`，需改为 `ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])`）。
2. 纯 CPU 跑小模型对本项目「每次 ≤10 条」的量级**完全够用**（总耗时 < 1s）；即便换更大的 `bge-m3`（~570M，CPU 约 1–2s/条），单次分析也只增加几秒，可接受。本机没有 CUDA，但本场景**不需要 GPU**。

---

## 三、Embedding 能力总览：本地 vs API（2025–2026）

**Leaderboard 现状**：`Qwen3-Embedding-8B` 截至 2025-06 居 MTEB 多语榜首（70.58）[1][2]；中文 C-MTEB 上 `Conan-embedding-v2`、Qwen3、Seed 系列、`zpoint_large_embedding_zh`、`piccolo-large-zh-v2` 为第一梯队[1][11]。基于 LLM 的 embedding（Qwen3、e5-Mistral）整体优于传统双塔，但参数量从 0.6B 到 8B 不等，本地成本差异大[1]。

**中文/金融专项**：`FinMTEB`（金融大规模文本嵌入基准，64 个中英金融数据集，覆盖财报/研报/ESG/监管文件/电话会纪要）证实——**领域自适应显著提升金融检索效果**，通用模型直接用并非最优；其金融适配版 `Fin-E5`（e5-Mistral-7B 微调）领先[3]。网易有道 `BCEmbedding`（双语，279M）训练数据**显式含金融域**，是 QAnything 的 RAG 基座[5]。

**长文本能力**：`bge-m3` 支持 **8192 token** 上下文，并同时输出 dense/sparse/ColBERT 三种表示，被广泛认为是**中文 RAG + 混合检索 + 边缘部署**的首选[8][12]；`Qwen3-Embedding` 支持 32K 上下文 + MRL 可变维度（32–1024）[7]。相比之下 BGE-zh v1.5 系列上限 512 token、MiniLM 仅 256 token。

**API 现状**：阿里云 DashScope `text-embedding-v3/v4` 按 token 计费，1024 维为性价比平衡点，支持 100+ 语种、8192 输入、含免费额度[4]；OpenAI `text-embedding-3` 默认大维度（small 1536 / large 3072），中文支持中上但跨境合规与离线性是硬伤[14]。

---

## 四、核心对比表

> 「中文/金融效果」为相对档位（基于 C-MTEB/FinMTEB 公开评测与社区实践，非本项目实测）；「延迟」为本机（Intel CPU，无 GPU）量级估计，本会话仅实测 MiniLM。成本按约 1 元≈$0.14 折算，均为近似。

| 方案 | 部署 | 维度 | 最大输入(token) | 中文/金融效果 | 成本 | 本机延迟(CPU) | 离线/隐私 | 对本项目适配 |
|---|---|---|---|---|---|---|---|---|
| **all-MiniLM-L6-v2**（现 fallback）[16] | 本地 ONNX | 384 | **256** | 弱（英文为主，粗粒度中文可用）[16] | 免费 | ~100ms/条(需强制CPU) | ✅完全离线 | ⚠️ 可跑但**长文严重截断**+中文偏弱；CoreML 须禁用 |
| **bge-small-zh-v1.5**[6] | 本地 ONNX/ST | 512 | 512 | 良（中文原生，远胜 MiniLM）[6][9] | 免费 | ~20–40ms/条 | ✅完全离线 | 轻量首选，但 512 ctx 对长 situation 仍偏短 |
| **bge-large-zh-v1.5**[9] | 本地 ST | 1024 | 512 | 优（中文 SOTA 级）[9][10] | 免费 | ~150–300ms/条 | ✅完全离线 | 质量高但 512 ctx 限制 + 326M 偏重 |
| **bge-m3** ★[8][12] | 本地 ST/ONNX | 1024(+sparse+ColBERT) | **8192** | 优（中文+多语+长文+混合检索）[8][12] | 免费 | ~1–2s/条(CPU) | ✅完全离线 | **最契合**：长文不截断+中文强+1024 维 |
| **Qwen3-Embedding-0.6B**[7] | 本地 ST/Ollama | 32–1024(MRL) | **32K** | 优（C-MTEB 66.3）[7] | 免费 | ~0.5–1.5s/条(CPU) | ✅完全离线 | 强，但需正确 last-token pooling + 归一化，集成成本略高 |
| **BCE-embedding-base_v1**（有道）[5] | 本地 ST | 768 | 512 | 优（中英 RAG，**训练含金融域**）[5] | 免费 | ~150–300ms/条 | ✅完全离线 | 金融域友好，但 512 ctx 限制 |
| **DashScope text-embedding-v4**[4] | API | 64–2048 | 8192 | 优（中文原生云服务）[4] | ¥0.0005/1K（batch ¥0.00025）+1M 免费 | 网络 ~50–200ms | ❌依赖云；**欠费即静默失败** | 高质量低工程量，但违背「零外部依赖」 |
| **OpenAI text-embedding-3-large**[14] | API | 256–3072 | 8191 | 中上（中文非强项） | ~$0.13/1M token | 跨境网络 | ❌离线不可/合规风险 | 不推荐（跨境 + 中文非最优 + 在线依赖） |

---

## 五、中文金融场景的三点关键考量

**① 长文本容纳是本项目的硬门槛，不是加分项。** situation 文本拼接四份报告常 2–6KB（约 1–3K token），远超 MiniLM 的 256 与 BGE-zh v1.5 的 512。只有 `bge-m3`（8192）与 `Qwen3-Embedding`（32K）能**无截断**地把基本面 + 新闻 + 情绪全部纳入向量，这直接决定「次日同 ticker 能否按当时完整态势召回历史教训」。这是为什么即便 MiniLM 在小语料 sanity 上 3/3 命中，仍不足以胜任真实 situation 的原因——sanity 文本短，没触发截断。

**② 中文原生 > 通用多语 > 英文为主。** C-MTEB/社区实践一致显示 BGE-zh、Conan、Qwen3 等中文原生模型在中文检索上显著优于 `all-MiniLM-L6-v2` 这类英文中心模型[1][9][10]。MiniLM 能过粗粒度 sanity，但面对「同一只票不同交易日、措辞高度相似的 situation」这种细粒度判别，区分度会塌缩。

**③ 金融域自适应有真实增益，但对本项目非必需。** FinMTEB 证明领域微调（Fin-E5）和含金融语料训练（BCE）能提升金融检索[3][5]。但本项目记忆环是「同一标的、相似结构文本」的自我比对，通用强中文模型（bge-m3）已足够；金融专用模型属于「锦上添花」，不值得为它牺牲长上下文或离线性。

---

## 六、选型建议（分档落地）

**主推（默认上线）— `bge-m3` 本地部署。** 理由：唯一同时满足「中文强 + 8192 长上下文（不截断 situation）+ 1024 维 + 完全离线」的方案，正好命中本项目三大权重。以 `sentence-transformers` 或导出 ONNX（强制 CPU 执行器）在本机 CPU 跑，单次分析增加几秒，量级可忽略。落盘仍走 `Knowledge_Wiki/.kb-vectors/ta-memory`。集成方式：在 `memory.py` 增加 `bge-m3` 本地分支（与现有 `local`/`dashscope` 分支并列），`memory_llm_provider="bge-m3"`。

**兜底（零工程依赖）— 强制 CPU 的 `all-MiniLM-L6-v2`。** 已实测可用、零下载（模型已缓存）、完全离线。**必做修复**：把 `memory.py` 本地分支从 `DefaultEmbeddingFunction()` 改为 `ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])`，规避本机 CoreML 崩溃。接受其 256-ctx 截断与中文偏弱，仅作为「bge-m3 未就绪时也能不阻塞跑通 B 环」的保底。

**可选（愿接受云依赖时）— `DashScope text-embedding-v4`。** 质量高、工程量最小（1024 维、8192 ctx、含免费额度）[4]。但它把记忆环重新绑回外部账户，**欠费/断网即静默返回零向量、记忆 no-op**——与「零外部依赖」原则冲突，故仅列为可选开关，不设为默认。

**轻量备选 — `bge-small-zh-v1.5`。** 若关注启动体积/速度且能接受 512 ctx 截断，它是比 MiniLM 更好的中文兜底（中文原生、~24M、ONNX/CPU 友好）[6]。

**不推荐 — OpenAI text-embedding-3**：跨境合规 + 在线依赖 + 中文非最优，三重不匹配。

### 落地动作清单
1. `memory.py`：本地分支强制 `CPUExecutionProvider`（修复本机 CoreML 崩溃）——**无论选哪个方案都应先做**。
2. 新增 `bge-m3` 本地嵌入分支，置为 `--memory-embed-provider` 默认值；MiniLM-CPU 作 fallback。
3. 维度变更需注意：ChromaDB collection 的向量维度随模型固定（MiniLM 384 / bge-m3 1024），**切换模型需用新的持久化目录或重建 collection**，不可混用。
4. 先用临时 KB 跑 `validate_mem_b.py`（provider 改为 bge-m3）验证「写→读命中」全链路，再接回 runner。

---

## 七、局限与说明

本报告的「中文/金融效果」档位综合自 C-MTEB/FinMTEB 公开评测与社区实践[1][3][9][10]，**未在本项目真实 situation 语料上做端到端检索评测**；除 MiniLM（本机实测）外，其余模型的本机延迟为按参数量推算的量级估计。FinMTEB 等基准证明「金融域自适应有增益」，但本项目「同标的自比对」场景下该增益边际递减，故未将金融专用模型列为主推。各 API 价格随厂商调整，以官方页为准[4]。MiniLM 的 3/3 中文 sanity 命中基于仅 4 文档、主题高度可分的小语料，**不能外推到真实长文细粒度场景**。

---

## 引用

[1] Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models. arXiv:2506.05176 / Hugging Face `Qwen/Qwen3-Embedding-8B`. https://huggingface.co/Qwen/Qwen3-Embedding-8B （Qwen3-Embedding-8B MTEB 多语 70.58，居首；C-MTEB 第一梯队）
[2] Top embedding models on the MTEB leaderboard. Modal Blog. https://modal.com/blog/mteb-leaderboard-article
[3] FinMTEB: Finance Massive Text Embedding Benchmark. arXiv:2502.10990. https://arxiv.org/abs/2502.10990 （64 个中英金融数据集；领域自适应提升金融检索；Fin-E5）
[4] 通用文本向量 Text Embedding 计量计费 / 向量化. 阿里云百炼 Model Studio. https://help.aliyun.com/zh/model-studio/developer-reference/billing-for-text-embedding （v3 ¥0.0005/1K，64–1024 维，8192 ctx，500K 免费；v4 至 2048 维，1M 免费；batch 半价）
[5] BCEmbedding: Netease Youdao bilingual embedding & reranker. GitHub. https://github.com/netease-youdao/BCEmbedding （bce-embedding-base_v1，279M，含金融域，QAnything RAG 基座）
[6] onnx-community/bge-small-zh-v1.5-ONNX + qdrant/fastembed. https://huggingface.co/onnx-community/bge-small-zh-v1.5-ONNX ; https://github.com/qdrant/fastembed （bge-small-zh ONNX/CPU 部署）
[7] Qwen/Qwen3-Embedding-0.6B 模型卡. https://huggingface.co/Qwen/Qwen3-Embedding-0.6B （0.6B；维度 32–1024 MRL；32K 上下文；C-MTEB 66.33；MTEB 多语 64.33）
[8] 大模型 RAG 基础：BGE-M3 embedding 实践. https://arthurchiao.art/blog/rag-basis-bge-zh/ ；RAG: BGE-M3 从论文到生产. https://zhuanlan.zhihu.com/p/697592190 （dense+sparse+ColBERT，8192，中文 RAG 首选）
[9] Embedding Models Comparison: BGE vs E5 vs Instructor. https://dasroot.net/posts/2026/01/embedding-models-comparison-bge-e5-instructor/
[10] Best Embedding Models 2025: MTEB Scores & Leaderboard. Ailog RAG. https://app.ailog.fr/en/blog/guides/choosing-embedding-models
[11] Conan-Embedding-v2: Training an LLM from Scratch for Text Embeddings. arXiv:2509.12892. https://arxiv.org/pdf/2509.12892 （C-MTEB 平均超越基线）
[12] BAAI/bge-m3 模型卡. https://huggingface.co/BAAI/bge-m3
[13] 各大厂商 Embedding 价格对比. https://blog.chs.pub/p/24-05-embeddingprice/
[14] OpenAI text-embedding-3 定价与维度（small 1536 / large 3072；small ~$0.02/1M、large ~$0.13/1M）；社区对比. https://www.buzhou.io/en/articles/embedding-model-selection-guide-openai-text-embedding-3-vs-open-source-alternatives
[15] Embedding 模型完全指南（2026）. https://blog.aihubplus.com/post/embedding-model-guide-2026/
[16] 本会话本机实测（Intel x86_64 Mac，onnxruntime 1.22）：ChromaDB `all-MiniLM-L6-v2` 默认 CoreML 批量崩溃 / 冷启动 13.3s；强制 `CPUExecutionProvider` 后 384 维、warm ~100ms/条、4 文档中文 sanity 3/3 命中。`/tmp/bench_onnx.py`、`/tmp/bench_cpu.py`。
