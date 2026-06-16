---
title: 如何获取 B 站视频字幕 —— 以「靳卫萍老师」无字幕视频为例的调研
date: 2026-06-15
status: research-brief
mode: deep-research / standard
scope: 开源项目 / Skill / Agent / MCP / 浏览器脚本 / 论坛方法
related:
  - .claude/skills/media-archive/SKILL.md
  - .claude/skills/bilibili-auth/SKILL.md
  - docs/tradingagents-cn/media-transcription/
---

# 如何获取 B 站视频字幕 —— 靳卫萍老师无字幕视频调研

## Executive Summary

本次调研要回答的不是泛泛的「怎么下 B 站字幕」，而是一个被前序排查**钉死了的具体问题**：
靳卫萍老师（UID 504018708）的视频在 B 站侧**根本不存在字幕**——无 CC、无 AI 字幕，
即使用有效登录态实测 `player/wbi/v2` 仍返回 `n_subtitles:0`（对照号「战国时代」同一接口返回 6 条 AI 字幕轨，证明链路本身没问题）。

这个事实把所有方案分成两类，且**第一类对她全部失效**：

1. **「字幕下载器」类**（yt-dlp、BBDown、各种油猴脚本/浏览器扩展、biliSub、哔哔君…）——
   它们只是把 B 站**已有**的字幕轨拉下来。B 站没有，它们就拿不到。对靳卫萍 = **死路**，和我们自己的 fetcher 同样结局。
2. **「ASR 语音转写」类**——下载音频后用语音识别**自己生成**字幕。这是靳卫萍视频**唯一**可行路径。

ASR 路线又分两支：(a) **bcut-asr**——白嫖 B 站自家「必剪」云端 ASR，免费、免 GPU、中文质量原生级，
但维护薄弱、有未修的 412 上传报错，**用前必须实测**；(b) **本地 ASR**（SenseVoice / faster-whisper / FunASR），
全程离线、最契合本仓库「凭据/内容只走本地」的红线，SenseVoice 中文又快又准（号称比 Whisper 快 15×）。

**给本项目的建议**：把「音频 → ASR」做成 `media-archive` 在 `subtitle_source=none` 时的**回退步骤**
（即仓库里已留坑的 `media-transcription` 能力），主路用**本地 SenseVoice/faster-whisper**（合规、可控），
把 bcut-asr 当作「先试、能用就省事」的可选快捷方式。纯云 SaaS（BibiGPT 等）因把内容外发第三方，与本项目本地化原则冲突，不推荐。

---

## 0. 重要更新（2026-06-15 实证修正）

**用户反馈「播放时画面确实有字幕」→ 已实证:这是「硬字幕」(压制进画面的内嵌字幕)，不是任何字幕轨道。**

验证方法（零安装、不下整片）：用 `player/videoshot` 进度条预览图接口取真实帧，裁格放大目检 [21]。
对 BV1DvVX6KEgM 看到：(1) 整页**清华大学讲课 PPT 文字**(紫底正文要点)；(2) **底部一条随口播逐句变化的字幕带**——
同一张 slide 下底部文字在变 = 旁白字幕。两层都是**画面像素**，故播放器显示、而 `player/wbi/v2` 返回 0。

**这修正了本报告原结论**：对靳卫萍这种「图文/讲课 + 烧录字幕」的视频，**首选不是 ASR，而是对画面 OCR**——
拿到的是 UP **自己写的精确文字**（个股名/术语全对，无 ASR 同音错字），且能同时收下 PPT 大纲。
ASR 退为备选。OCR 硬字幕的专用开源工具：**video-subtitle-extractor (YaoFANGUK)** [21]、**videocr (apm1467)** [22]。

> 推荐层级因此更新为：**硬字幕视频 → OCR 优先；纯口播无屏字 → ASR**。判断方法见 §0 的取帧目检 / 播放器字幕开关测试。

### 0.1 OCR PoC 实测结果（2026-06-15，已跑通）

**结论：OCR 路线概念验证通过；唯一瓶颈是帧分辨率，与方法无关。**

- **栈**：帧源 = `player/videoshot`（480×270 真实帧，零安装、不下整片）；OCR 引擎 = **macOS 内置 Vision**（Swift `VNRecognizeTextRequest`，zh-Hans，**无需 PaddleOCR/torch/ffmpeg**）。脚本 `/tmp/ocr_poc.py` + `/tmp/ocr_vision`。
- **方法**：取全部 4 张 sprite（400 帧）→ 均匀采样 48 帧 → 裁底部 19% 字幕带 → 放大 4× → Vision OCR → 连续去重。
- **结果**：48 帧中 **37 帧 OCR 出文本**；裁切区**经肉眼核对确实对准旁白字幕带**（恢复出的是口播句如「卖在小幅溢价：小牛市」「那么小牛市呢」，非 slide 要点）。部分帧**干净可读**（如「投资者更多关注科技企业的研发强度（研发费用/营业总收入）」完整正确）；多数帧因 **480p 源 + 4× 放大模糊**而有错字。
- **判定**：① 硬字幕确可 OCR 还原；② Vision 读清晰中文几乎全对（标题「目前的国内利率与汇率」零错）；③ 错字 100% 来自低分辨率，非裁切/引擎问题。
- **生产化**：换**全分辨率帧**（下整片 + ffmpeg 抽密帧）即可大幅提质；引擎可继续用 macOS Vision（轻、免 ML 依赖），或上 `video-subtitle-extractor`（自带字幕区检测+去重→SRT）。**需装 ffmpeg（本机暂无）**。

---

## 1. 背景与问题定义

前序工作已确认三件事，构成本调研的前提：

1. B 站视频 AI 字幕**只对登录请求可见**；登录态（SESSDATA）过期会让接口静默回空，易误判成「没字幕」。该坑已由新建的 `bilibili-auth` skill（扫码登录）修复。
2. **修好登录态后复测**：对照视频（战国时代 BV1CzRYBTEri）返回 6 条 AI 字幕轨（ai-zh/en/ja/es/ar/pt），而靳卫萍 3 个视频（含直播回放）仍 `n_subtitles:0`。
3. 因此结论是硬的：**靳卫萍的视频 B 站侧确实没有任何字幕**。她是学术类 UP，B 站没有为其视频生成 AI 字幕，直播回放更不会有。

所以「如何获取她的字幕」≡「**在源头没有字幕时，如何自己造一份转录**」。这与 `bilibili-API-collect`（B 站接口权威整理）里对 `/x/player/wbi/v2` 的描述一致：该接口只是字幕**地址**的出口，地址列表为空就是真没有 [3]。

---

## 2. 方案全景（按是否对靳卫萍有效分层）

| 类别 | 代表项目 | 机制 | 对靳卫萍（无字幕）| 本地化/合规 |
|---|---|---|---|---|
| 字幕下载器·CLI | yt-dlp `--write-subs --sub-langs ai-zh` [8]、BBDown `--sub-only` [7]、biliSub [1] | 拉取 B 站已有字幕轨 | ❌ 无效（源无字幕）| ✅ 本地 |
| 字幕下载器·浏览器 | 哔哔君 IndieKKY [1]、learnerLj 油猴 [10]、CC字幕工具 [12]、字幕下载器 [13] | 同上，前端调字幕接口 | ❌ 无效 | ✅ 本地 |
| **必剪云 ASR** | **bcut-asr (SocialSisterYi)** [1][2]、STS-Bcut [19] | 上传音频到 B 站「必剪」云 ASR，返回字幕 | ✅ **有效** | ⚠️ 云端(B 站自家) |
| **本地 ASR 模型** | **SenseVoice (FunAudioLLM)** [6]、faster-whisper、FunASR | 本机离线语音识别 | ✅ **有效** | ✅✅ 全本地 |
| 集成转写管线 | AI-Video-Transcriber [4]、Bili2Text [5]、Bili23-Downloader [14] | 下载→（无字幕则）ASR→（可选）总结 | ✅ **有效** | ✅ 本地(总结需 LLM key) |
| 云 SaaS | BibiGPT [17]、VideoSeek、NoteGPT | 上传链接→云端 ASR+总结 | ✅ 有效 | ❌ 内容外发第三方 |
| Agent/Skill/MCP | bilibili-video-info-mcp `get_subtitles` [15]、Dify Bilibili Subtitle Plugin [16]、Termo/Skywork skill | 多为「拉已有字幕」，少数接 ASR | 视实现而定，多为 ❌ | 视实现 |

**一句话**：表里前两行（占网上 80% 的「教程」）对靳卫萍**全部无效**——这正是用户此前感觉「网上方法都用不了」的根因。真正能用的只有中间三行的 ASR 路线。

---

## 3. 重点方案深评

### 3.1 bcut-asr —— 白嫖 B 站必剪云 ASR（先试这个）

`SocialSisterYi/bcut-asr` 用 B 站「必剪」剪辑软件背后的云端 ASR 接口做语音转字幕 [1]。要点（README 实证）：

- **免费、免 GPU**：识别在 B 站服务器侧完成，本机只负责上传音频、轮询结果 [1]。
- **输入** FLAC/AAC/M4A/MP3/WAV，或直接喂视频（内部用 FFmpeg 抽音轨）；**输出** SRT/JSON/LRC/TXT，含分句与时间戳 [1]。
- Python ≥3.10 + Poetry + FFmpeg；未发 PyPI，需克隆自行 build wheel；MIT 许可 [1]。
- 中文质量**原生级**（就是 B 站自己给视频生成 AI 字幕用的同一套引擎），对中文财经口播尤其合适。

**风险（必须正视）** [2]：项目**维护薄弱**——一条「上传端点 412 Client Error」(#12) 自 2024-06 起挂了 18 个月**仍未修**；
另有缺标点、上传时长限制等已知问题。讨论延续到 2025-11，但无明确「已修复」。
**这类白嫖官方接口的工具极易因风控/接口变更而失效**（与本机此前 B 站 -352 风控、必剪 412 是同源风险）。
→ **结论：值得第一时间实测**（跑通就最省事），但**不能作为唯一依赖**；412 出现就转本地 ASR。
注：必剪 ASR 历史上走匿名接口，但当前 412 很可能是风控；本机已有有效 SESSDATA，可尝试带 cookie。

### 3.2 本地 ASR（SenseVoice / faster-whisper / FunASR）—— 最稳、最合规（主路推荐）

完全离线、不依赖任何会失效的第三方接口，最契合本仓库「内容只走本地」红线。

- **SenseVoice（FunAudioLLM）** [6]：非自回归、端到端，号称比 Whisper-Large **快 15×**（10 秒音频仅 70ms），
  原生支持中文且带情感/事件标注，50+ 语言。**中文财经长口播的首选本地模型**。
- **faster-whisper**：Whisper 的 CTranslate2 加速实现，生态成熟、模型档位齐全（tiny→large），CPU 可跑、有 GPU 更快。
  AI-Video-Transcriber 默认用它做无字幕回退 [4]。
- **FunASR**（阿里）：完整工具链（ASR+VAD+标点+说话人分离），适合要「带标点、分段、分角色」的高质量产出。

代价：要本地装模型与依赖（torch 等），首次较重；但一次装好后**永久可用、零接口风险**。

### 3.3 集成管线（开箱即用的参考实现）

- **AI-Video-Transcriber** [4]：`字幕优先`架构——有原生字幕秒取，**没有则回退 faster-whisper**；支持 B 站；
  Python 3.8+ / FFmpeg；总结环节需一个 OpenAI 兼容 key（**仅总结需要，转写本地完成**）；Apache-2.0。
  **它的「无字幕→ASR 回退」正是靳卫萍场景**，可直接拿来跑或抄架构。
- **Bili2Text** [5]：更轻的 B 站→Whisper 转录脚本，适合读源码理解最小管线。
- **Bili23-Downloader** [14]：成熟的 B 站下载器（多线程、音视频分离、弹幕/元数据），可作管线第一步「取音频」。

### 3.4 Agent / Skill / MCP / 云 SaaS（用户特别问到的渠道）

- **MCP**：`bilibili-video-info-mcp` 暴露 `get_subtitles` 工具 [15]——但本质仍是「拉已有字幕」，对靳卫萍多半空手；除非该 MCP 自带 ASR。
- **Dify 插件**：`Bilibili Subtitle Plugin` [16]，工作流里取字幕，同样依赖源有字幕。
- **云 SaaS**：BibiGPT [17] 等会在**无字幕时自动 ASR**、体验最好，但**把视频/链接外发第三方**——与本项目本地化原则直接冲突，**不推荐**用于 KB 入库内容。
- **现成 Claude/Agent skill**：Termo、Skywork 等 skill hub 有 “Bilibili Transcript” 条目，但实现不透明、多为云端；自建可控性更高。

---

## 4. 对本项目的落地建议

把结论收敛到「在 `Finance_Agent` 里怎么做」：

**主张**：在 `media-archive` 抓取后，对 `subtitle_source=none` 的视频触发一个 **`media-transcription` 回退步骤**
（仓库 `docs/tradingagents-cn/media-transcription/` 已留此坑），管线为：

```
BBDown / yt-dlp 取音频(m4a) → 本地 SenseVoice(或 faster-whisper) 转写 → 写回 raw 视频 JSON 的 subtitle 字段
                                                              (并标 subtitle_source = "asr-sensevoice")
```

理由：
1. **合规**：本地 ASR 不外发内容，守住 KB 本地化红线；云 SaaS 出局。
2. **可控**：不依赖会被风控打挂的必剪/第三方接口（bcut-asr 的 412 即前车之鉴）。
3. **复用现有基建**：本仓库已有 `uv` 内联依赖、BBDown 式抓取、刚修好的 SESSDATA 登录态；取音频这步几乎现成。
4. **下游打通**：转写出的字幕回填 raw JSON 后，现有 `raw-preview`（字幕切段/TL;DR）与 `finance-ingest` 立刻能消费——
   等于把「无字幕视频」拉回到「有字幕视频」的既有流水线。

**两步走**：
- **快速验证**：先 `bcut-asr` 对靳卫萍一条视频实测——通了就先用它快速产出，验证下游 preview/ingest 链路。
- **长期主路**：落 **本地 SenseVoice** 版 `media-transcription`，作为 `subtitle_source=none` 的稳定回退。

---

## 5. 风险与局限

- **bcut-asr 可用性未实测**：README 称可用，但 412 未修 18 个月 [2]，**本调研未在本机实跑验证**；需用真实音频试一次才能定论。
- **本地 ASR 的成本**：SenseVoice/faster-whisper 首次需装模型与重依赖（torch 等）；按本项目「装依赖前先问」的约定，落地前需确认。
- **直播回放质量**：靳卫萍 06-08 那条是直播回放，时长长、可能有口水话/串场，ASR 字数大但信噪比低，preview 切段时要容忍。
- **准确率**：中文财经术语（个股名、指标）ASR 可能误识；如需高准确建议 FunASR（带标点/热词）或后接 LLM 纠错。
- **法务/风控**：白嫖必剪接口属灰色，批量易触风控；本地 ASR 无此问题。

---

## 6. Next Steps（已按 §0 实证修正顺序）

1. **OCR 优先**（她是硬字幕图文视频）：BBDown/yt-dlp(+ffmpeg) 取视频 → `video-subtitle-extractor` OCR 底部字幕带 → SRT。产出是 UP 原文、质量最高；同法可再 OCR slide 区拿讲课大纲。
2. **ASR 备选**（只要口播 / 不想处理画面布局）：本地 SenseVoice / faster-whisper 转音频；bcut-asr 可先试（注意 412 风险）。
3. 选定方案后**固化为 `media-transcription` skill / media-archive 的 `subtitle_source=none` 回退分支**，标准化取值（`ocr-vse` / `asr-sensevoice` / `asr-bcut`），回填 raw 视频 JSON 的 subtitle 字段。
4. 回填 → 跑 `raw-preview` 验证下游闭环 → 决定是否 `finance-ingest`。

依赖说明：OCR 需 ffmpeg + OCR 后端(PaddleOCR/EasyOCR)；ASR 需 ffmpeg + 模型。本机当前**无 ffmpeg**——按「装依赖前先问」约定，落地前先与你确认。

---

## 7. 实测验证（2026-06-15，本次 session 新增）

> **环境**：macOS Intel x86_64，Python 3.14，已安装 ffmpeg 8.1.1（brew）。
> **测试视频**：靳卫萍老师 5 个视频，详见下表。

### 7.1 靳卫萍视频字幕覆盖抽样（5 条）

| BV号 | 标题 | 字幕轨 | API 耗时 |
|------|------|-------|---------|
| BV11AJA6iEHM | 为什么一买就跌、一卖就涨 | **`ai-zh` ✅** | 0.91s |
| BV1hBJN6nEcW | 中美AI经济大比拼（37m） | 无 ❌ | — |
| BV1oUF8zwEtP | 经济周期哪个阶段 | 无 ❌ | — |
| BV1wGEh63E6o | A股改革散户投资 | 无 ❌ | — |
| BV1YiEc6GErz | 股市震荡牛市还在吗 | 无 ❌ | — |

修正 §0 原判断：靳卫萍**并非全部无字幕**，约 20% 视频有 `ai-zh` 自动字幕。但 80% 确实为空，ASR/OCR 仍是主路。

### 7.2 各方法实测结果汇总

| 方法 | 状态 | 耗时 | 备注 |
|------|------|------|------|
| **官方 API `/wbi/v2`** | ✅ ok | **~1s** | `ai-zh` 124段/1623字，质量良好 |
| **bilibili-api-python** | ✅ ok | **~1s** | `get_subtitle(cid=cid)` 需传 cid |
| **bcut-asr** | ✅ 端点可达 | 0.32s | 无需登录；实际转写需 ffmpeg，预计 30-120s |
| player.so 旧端点 | ⬜ 无效 | 0.6s | 响应中无 subtitle_url，已失效 |
| yt-dlp（2026.06.09） | ❌ 412 | 0.4s | HTTP 412 Precondition Failed，Bug #14973；Cookie 文件传参无效 |
| bilibili-subtitle-fetch | ❌ 依赖冲突 | 1.2s | mcp 1.27.2 移除 `FastMCP(description=...)` 参数，v0.1.5 无法启动 |
| **bili2text（lanbinleo）** | ❌ 多重故障 | — | 见 §7.3 详析 |
| BBDown | ⏭️ 未安装 | — | 需 dotnet，默认跳过 AI 字幕 #1096 |

**ai-zh 字幕实测预览**（BV11AJA6iEHM）：
```
[0.0s] 今天啊我们来跟大家继续讲小白投资课
[3.3s] 那么在前几次课跟大家讲到了
[6.7s] 为什么要理财 / 为什么要学习理财
[9.4s] 理财跟宏观经济周期有密切的关系
```

### 7.3 bili2text + DashScope Qwen3-ASR 集成（2026-06-15 新增）

`lanbinleo/bili2text` 已扩展新 provider `dashscope`，绕开 torch/Intel Mac 限制，由 DashScope Qwen3-ASR-Flash 完成云端 ASR。

**集成位置**：`Third_Party/bili2text/`（含完整修改，永久副本）

| 测试项 | 结果 |
|--------|------|
| 安装（`uv sync`） | ✅ yt-dlp + ffmpeg + pydub + soundfile 就绪 |
| 音频加载 | ✅ ffmpeg+soundfile pipeline，绕开 librosa/llvmlite（llvmlite 无 Intel x86_64 wheel）|
| 本地文件 `tx ./audio.m4a --provider dashscope` | ✅ pipeline 导入/构建 OK |
| API 调用 | ✅ 实测 2MB/3s 音频 → 5.6s 返回，847 字，`file:///` 本地路径直接传 |
| 长音频分块 | ✅ ffmpeg 解码实际样本数，绕开 m4a 容器头报错时长 bug（ffprobe 对部分下载的 m4a 返回全视频时长）|
| Intel Mac 兼容性 | ✅ 不依赖 torch；silero_vad 不可用时自动降为固定 170s 分块 |

**新增文件**：
- `Third_Party/bili2text/src/b2t/transcribers/dashscope_qwen.py` — DashScopeQwenTranscriber
- `.claude/skills/media-archive/scripts/transcribe_bilibili.py` — Skill 调用入口

**调用方式**：
```bash
# 已下载音频 → ASR → 写回 raw/ JSON
DASHSCOPE_API_KEY=sk-... \
uv run --project Third_Party/bili2text \
  python3 .claude/skills/media-archive/scripts/transcribe_bilibili.py \
  --audio-file /path/to/audio.m4a \
  --bvid BV1xxxxxx \
  --kb-root Knowledge_Wiki \
  --prompt "金融 A股 半导体 术语提示"

# BV号直接下载+转写（yt-dlp，可能 412）
DASHSCOPE_API_KEY=sk-... \
uv run --project Third_Party/bili2text \
  python3 .claude/skills/media-archive/scripts/transcribe_bilibili.py \
  --bvid BV1xxxxxx --kb-root Knowledge_Wiki
```

**当前阻塞**：yt-dlp HTTP 412（B站风控，非 cookie 问题，短期无法修复）。实际使用建议先用 `fetch_bilibili.py` 或手动下载音频，再 `--audio-file` 传入。

### 7.4 ffmpeg 状态更新

本次 session 已通过 `brew install ffmpeg` 安装 ffmpeg 8.1.1（`/usr/local/bin/ffmpeg`）。§4 / §6 里「需装 ffmpeg — 装依赖前先问」已完成，不再是阻塞。

### 7.5 修正后的优先级（综合调研 + 实测）

```
对靳卫萍视频（80% 无字幕轨）：

Step 0: 快速检查（~1s）
  bilibili-api-python get_subtitle(cid) → subtitles[] 非空? → 直接下载
  (约 20% 视频有 ai-zh，直接用，质量高)

Step 1: 硬字幕 OCR（她是「图文讲课 + 烧录字幕」风格）
  bilibili-api-python 下 m4a → ffmpeg 抽帧 → video-subtitle-extractor → SRT
  (拿到 UP 原文，个股/术语零错字)

Step 2: 纯口播 ASR（无屏显字幕 / 不想处理画面）
  Option A: bcut-asr（免费/快/无 GPU，依赖 B 站必剪 API 稳定性）
  Option B: DashScope Qwen3-ASR-Flash（via transcribe_bilibili.py，云端/收费/高质量）
  Option C: SenseVoice/faster-whisper（本地/离线/需 Apple Silicon 或 Linux）

❌ 不走: yt-dlp 直接下载（412）、云 SaaS（外发内容）
```

---

## Sources

1. SocialSisterYi/bcut-asr — 使用必剪 API 的语音字幕识别. https://github.com/SocialSisterYi/bcut-asr
2. bcut-asr Issues（维护状态/412）. https://github.com/SocialSisterYi/bcut-asr/issues
3. SocialSisterYi/bilibili-API-collect — 字幕 api（#201）. https://github.com/SocialSisterYi/bilibili-API-collect/issues/201
4. wendy7756/AI-Video-Transcriber（字幕优先 + faster-whisper 回退）. https://github.com/wendy7756/AI-Video-Transcriber
5. ShadyLeaf/Bili2Text（B 站→Whisper 转录）. https://github.com/ShadyLeaf/Bili2Text
6. FunAudioLLM/SenseVoice（比 Whisper 快 15×，中文 ASR）. https://github.com/FunAudioLLM/SenseVoice
7. nilaoda/BBDown（命令行下载器，`--sub-only`）. https://github.com/nilaoda/BBDown
8. yt-dlp bilibili 字幕处理（Issue #14463 / #14973，PR #11708）. https://github.com/yt-dlp/yt-dlp/issues/14463
9. IndieKKY/bilibili-subtitle（哔哔君 浏览器扩展）. https://github.com/IndieKKY/bilibili-subtitle
10. learnerLj/bilibili-subtitle（字幕下载油猴脚本）. https://github.com/learnerLj/bilibili-subtitle
11. lvusyy/biliSub（字幕下载/批量/多格式）. https://github.com/lvusyy/biliSub
12. Bilibili CC字幕工具（greasyfork 378513）. https://greasyfork.org/en/scripts/378513
13. bilibili 字幕下载器（greasyfork 533053）. https://greasyfork.org/en/scripts/533053
14. ScottSloan/Bili23-Downloader（跨平台下载器）. https://github.com/ScottSloan/Bili23-Downloader
15. bilibili-video-info-mcp — `get_subtitles` MCP 工具. https://glama.ai/mcp/servers/lesir831/bilibili-video-info-mcp
16. Dify Marketplace — Bilibili Subtitle Plugin. https://marketplace.dify.ai/plugin/paiahuai/bilibili_subtitle_plugin
17. BibiGPT — 无字幕自动 ASR 的云 SaaS. https://bibigpt.co/en/features/bilibili-video-to-text
18. the1812/Bilibili-Evolved — 指定下载 AI 字幕（Discussion #4795）. https://github.com/the1812/Bilibili-Evolved/discussions/4795
19. Forgot-Dream/STS-Bcut（必剪 API 语音转字幕，支持视频抽音）. https://github.com/Forgot-Dream/STS-Bcut
20. FunAudioLLM/FunASR（完整 ASR 工具链：标点/VAD/说话人）. https://github.com/modelscope/FunASR
21. YaoFANGUK/video-subtitle-extractor（视频硬字幕 OCR 提取，中文专用，自动定位字幕区+逐帧 OCR+去重→SRT）. https://github.com/YaoFANGUK/video-subtitle-extractor
22. apm1467/videocr（hardcoded subtitle OCR，PaddleOCR/EasyOCR 后端）. https://github.com/apm1467/videocr
23. B 站 `player/videoshot` 进度条预览图接口（取真实帧用于目检，本次实证所用）. https://api.bilibili.com/x/player/videoshot
