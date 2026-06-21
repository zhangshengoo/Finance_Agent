---
name: media-archive
description: 把 B 站视频/动态 与 微信公众号文章 抓取后落到 Knowledge_Wiki 的 raw/ 层（不可变源），然后提示用户调用 finance-ingest 完成 raw→wiki 的两步 CoT 摄入。触发词：「采集 B 站」「抓 UP 主」「存这条公众号」「归档这个 BV」「ingest media」。
---

# media-archive — B 站 / 公众号 抓取入库

## Purpose

把对话中提到的 **B 站视频/动态** 与 **微信公众号文章** 抓为不可变源文件，按 Knowledge_Wiki 三层架构落到 `raw/` 层，并提示用户用 `finance-ingest` 继续把 raw → wiki。

本 skill 的责任**严格限定在 raw/ 层**：
- 抓取（B 站 API / 公众号 HTML）
- 规整为可被 `finance-ingest` 消费的结构化文件
- 落到 `raw/transcripts/bilibili/`、`raw/weixin/`、`raw/assets/{bilibili,weixin}/`
- 提示用户下一步触发 `finance-ingest`

**永远不写 `wiki/`、不写 `ontology/`、不动 `.ingest-cache/`**。那是 `finance-ingest` 的事。

## 何时使用

触发条件（任一）：
- 用户说「采集 UP 主 X」「抓这个 BV 号」「存这条公众号文章」「归档这个 mp.weixin.qq.com 链接」
- 用户给了 B 站 UID / BV 号 / `mp.weixin.qq.com` URL，意图是入库
- 用户在 `finance-research` 流水线中需要把网络音视频/图文沉淀到 KB

**不**使用本 skill 的场景：
- 用户已经手动把 PDF/HTML 放到 `raw/` 下了 → 直接走 `finance-ingest`
- 用户只想要一次性总结、不入库 → 直接读取/总结，别落盘
- 抓的内容是 PDF 财报 → 走对应抓取（本 skill 仅覆盖 B 站 + 公众号）

## CRITICAL 红线

1. **禁止越界写 wiki/**：本 skill 只产出 `raw/` 下的文件。如需 wiki 页，必须由用户/Agent 显式触发 `finance-ingest`。这是为了保留 2-step CoT 的人工 review 点（见 finance-ingest 红线 1）。
2. **禁止覆盖 raw/ 已存在文件**：raw/ 是 append-only。同名文件存在时报错退出，让用户决定是新增（改 slug）还是手动删除老的。
3. **禁止伪造发布时间 / UP 主名 / 作者**：所有 `published_at` / `uploader` / `account` 字段必须来自 API 真实返回，缺失则留空字符串，**不**从 LLM 猜测。
4. **禁止跳过 `is_ad` 标记**：B 站动态脚本会标 `is_ad`，本 skill 不主动过滤（保留 Agent 决策权），但也**不**抹掉这个字段。
5. **图片必须本地化**：B 站/公众号图片 URL 有反盗链，必须下载到 `raw/assets/` 并改写引用为相对路径；不允许 raw 文件里留外链。
6. **路径必须用 KB_ROOT**：所有写入路径通过 `KB_ROOT` 解析，默认 `${PROJECT_ROOT}/Knowledge_Wiki`。脚本必须接 `--kb-root` 参数，SKILL.md 必须读环境变量。
7. **采集走直连、住宅 CN IP**：B 站/公众号一律直连走本机住宅 CN IP，境外/机房 IP → B 站风控（412/-352/-799）、公众号封；采集前先自检出口 IP 为 CN 住宅再抓，仅境外流量走代理。

## KB_ROOT 解析约定

- 环境变量：`KB_ROOT`
- 默认值：与本 skill 所在 `.claude/skills/` 同级的 `Knowledge_Wiki/`（即 `Finance_Agent/Knowledge_Wiki/`）
- 解析顺序：
  1. 命令行 `--kb-root <path>`（脚本层）
  2. 环境变量 `KB_ROOT`
  3. 默认值（脚本根据自身路径反推）

预检：每次 skill 触发先 `ls "${KB_ROOT}/raw/"`，若不存在或缺少 `transcripts/`、`news/`、`assets/` 子目录，提示用户：「KB_ROOT 未指向有效 Knowledge_Wiki，请检查路径」。

## 写入目标矩阵

| 内容形态 | raw/ 目标路径（四级布局） | 文件格式 | 命名 |
|---|---|---|---|
| B 站视频（含字幕） | `raw/transcripts/bilibili/<up>/videos/<YYYY>/<YYYY-MM>/` | JSON | `<YYYY-MM-DD>_<bvid>.json` |
| B 站动态（按日聚合） | `raw/transcripts/bilibili/<up>/dynamics/<YYYY>/<YYYY-MM>/` | JSON | `<YYYY-MM-DD>.json` |
| B 站图片 | `raw/assets/bilibili/<uid>/` | png/jpg | 原文件名（hash 兜底） |
| 微信公众号文章 | `raw/weixin/<account-slug>/` | Markdown + frontmatter | `<date>-<title-slug>.md` |
| 公众号正文图片 | `raw/assets/weixin/<account-slug>/` | png/jpg | `<date>-<title-slug>-<idx>.<ext>` |

**slug / 日期规则**：
- `<up>`：UP 主名 `slugify` 后的目录名（中文保留，文件系统非法字符剔除）
- `account-slug`：公众号名同规则
- `title-slug`：标题前 30 字符
- 路径中所有 `<YYYY-MM-DD>`、`<YYYY-MM>`、`<YYYY>` **按 UTC+8 时区**从 `published_at` 推算；文件内 `published_at` 字段仍保留 UTC ISO 标准时间。
- 同一天的多条动态**聚合到一份日文件**，重复抓取走 C2b 合并（默认覆盖更新；`--rebuild` 用于忽略老文件重建）。

## 工作流（Phase A → Phase C）

### Phase A — 解析意图 + 路径预检

1. 从用户消息提取标识符：
   - **B 站 UID**：用户给「UID 1039025435」或「UP 主名 + 让我查」
   - **B 站 BV 号**：`BV1xxxxxx`
   - **公众号 URL**：以 `https://mp.weixin.qq.com/s/` 开头
2. 解析 `KB_ROOT`（见上节）。
3. `ls "${KB_ROOT}/raw/{transcripts,news,assets}"` 预检。
4. 必要时 `mkdir -p` 子目录（`raw/transcripts/bilibili/`、`raw/weixin/<account-slug>/`、`raw/assets/bilibili/<uid>/`、`raw/assets/weixin/<account-slug>/`）。

### Phase B — 抓取并落 raw/

按内容形态选脚本：

#### B 站视频 + 字幕
```bash
uv run --with 'curl_cffi==0.9.0' \
  "${SKILL_DIR}/scripts/fetch_bilibili.py" \
  --kb-root "${KB_ROOT}" \
  --bvid <BV号> --with-subtitle
# 或: --uid <UID> --count 3 --with-subtitle
```
- **必须后台执行**（脚本含 412 重试 90s）
- 含字幕时 `--count` ≤ 5
- 输出：每个视频一份 `raw/transcripts/bilibili/<uploader-slug>_<bvid>.json`
- `subtitle_source` 优先级：`cc-zh > ai-zh > none`（`none` 代表无字幕轨道，需走 ASR）

#### B 站视频 ASR 转写（当 subtitle_source=none 时的备选方案）

当视频无字幕（`subtitle_source: none`）时，用 **DashScope Qwen3-ASR** 从音频转写：

```bash
# 方式 A：BV号直接下载+转写（需 yt-dlp 能访问B站，可能遇412风控）
uv run --project "${PROJECT_ROOT}/Third_Party/bili2text" \
  python3 "${SKILL_DIR}/scripts/transcribe_bilibili.py" \
  --bvid <BV号> --kb-root "${KB_ROOT}" \
  [--prompt "金融/半导体行业术语提示"] \
  [--model qwen3-asr-flash]

# 方式 B：已有音频文件（BBDown 下载或其他工具）
uv run --project "${PROJECT_ROOT}/Third_Party/bili2text" \
  python3 "${SKILL_DIR}/scripts/transcribe_bilibili.py" \
  --audio-file /path/to/audio.m4a \
  --bvid <BV号> --kb-root "${KB_ROOT}"
```

**当 yt-dlp 遇到 412 时**，脚本会打印 BBDown 备用命令：
```bash
BBDown -ia -c ~/.bilibili_sessdata.json <BV号>
# 下载完后再用方式 B
```

- 需要环境变量 `DASHSCOPE_API_KEY`（必须）
- 可选 `BILIBILI_SESSDATA`（提升 yt-dlp 成功率）
- 输出：更新已有 raw JSON 的 `subtitle` / `subtitle_source: asr-qwen3-asr-flash` 字段
- 若 raw JSON 不存在：创建 skeleton JSON 到 `raw/transcripts/bilibili/_asr_only/<bvid>.json`
- bili2text 安装路径：`Third_Party/bili2text/`（含 DashScope 插件 + pydub/soundfile）

#### B 站动态 + 图片
```bash
uv run --with 'curl_cffi==0.9.0' \
  "${SKILL_DIR}/scripts/fetch_bilibili_dynamic.py" \
  --kb-root "${KB_ROOT}" \
  --uid <UID> --count 10 --download-images
```
- **必须后台执行**
- 视频抓取与动态抓取之间**等待 ≥30 秒**（防 IP 级 412）
- 抓回来的动态按 `published_at` UTC+8 日期**分桶聚合**：一天的多条动态写入同一份 `raw/transcripts/bilibili/<up>/dynamics/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>.json`
- 默认行为是 C2b 合并：目标文件已存在时，**新值覆盖**同 `dynamic_id` 的旧条目、新条目追加。`--rebuild` 用于忽略老文件重建
- 图片落 `raw/assets/bilibili/<uid>/`，路径不变

#### 公众号文章
```bash
uv run --with 'curl_cffi==0.9.0,readability-lxml==0.8.1,lxml-html-clean,html2text==2024.2.26,beautifulsoup4==4.12.3' \
  "${SKILL_DIR}/scripts/fetch_weixin.py" \
  --kb-root "${KB_ROOT}" \
  --url 'https://mp.weixin.qq.com/s/...'
```
- 同步执行即可（无 WBI 风控，但有 referer 限制）
- 输出：一份 `raw/weixin/<account-slug>/<date>-<title-slug>.md`；正文图片落 `raw/assets/weixin/<account-slug>/`，文中改写为相对路径

### Phase B+ — 重建创作者时间线（B 站，自动收尾）

抓完 B 站源后**自动**重建该 UP 主的「创作者时间线清单」`timeline.json`。这是**廉价、纯 raw 派生**的收尾，让前端「媒体转录」视图随每次抓取保持最新、全覆盖——**不**经过 `finance-ingest`，**不**写 wiki。

```bash
python3 "${SKILL_DIR}/scripts/build_timeline.py" \
  --kb-root "${KB_ROOT}" \
  --up "<uploader-slug>"        # 省略 --up 则重建所有 UP 主
```

- 输出：`raw/transcripts/bilibili/<up>/_previews/timeline.json`（每个 UP 主一份）
- 每条 item 一行高度概括：`{date, kind, id, title, summary, tldr, topics, stances, mentions, up_actions, is_trade, stats, src, preview, link}`（`summary/topics/stances` 来自 preview 的 knowledge-tree v0.3）
- 数据来源：raw JSON（权威字段）+ `_previews/*.md`（TL;DR / mentions / 操作表 / knowledge-tree）。**没有 `_preview` 的源也照样进时间线**（降级：tldr 为空，仅 raw 字段）——这正是「全覆盖」的价值。
- `has_wiki` / 深度链接**不在此处算**——那是前端构建期 `build_frontend_data.py` 读 wiki/filings-summary 叠加的事。
- 无内容动态（`n_items=0` 纯转发 / 无 preview，即无 tldr·树·摘要·立场）仍写入 timeline.json，但**前端「媒体转录」默认隐藏**，仅在计数处标注"已隐藏 N 条空动态"，避免刷屏。

**定位**：`timeline.json` 与 `_previews/` 同等地位——派生、可重建、随时可删，**不进** `wiki/` / `ontology/` / `_index.json`。它既不破坏 `raw/` 不可变铁律，也不绕过 `finance-ingest` 的两步 CoT 人工 review 边界。设计见 [`frontend/media-timeline-architecture.html`](../../../frontend/media-timeline-architecture.html)：**「wiki 装结论，raw + 轻量 digest 装流水」**。

> 公众号文章（`raw/weixin/`）暂不纳入 `timeline.json`（当前仅覆盖 B 站 UP 主时间线）。

### Phase C — 报告结果 + 提示下游 skill（不自动调用）

抓完后向用户报告 ≤ 20 行，按"是否含图"选择性提示 asset-describe，明确给出下游 skill 的可执行命令：

```
✅ media-archive 抓取完成

落地文件：
- raw/transcripts/bilibili/<up>/dynamics/2026/2026-05/2026-05-28.json
- raw/assets/bilibili/<uid>/xxx_0.png  （18 张图）

✓ 已重建 raw/transcripts/bilibili/<up>/_previews/timeline.json（前端时间线已含本条，全覆盖）

下一步（按需选择，本 skill 不自动调用）：

🖼️  **给图打 caption**（仅当源含图，OCR + 视觉描述）→ asset-describe
   uv run .claude/skills/asset-describe/scripts/describe_assets.py \
     --from-dynamic raw/transcripts/bilibili/<up>/dynamics/2026/2026-05/2026-05-28.json
   → 产出 batch + prompt 包，Claude 会话内逐张看图后跑 --apply 落 caption JSON
   → 跑完后 raw-preview 会自动读 caption 渲染图文增强版预览

🔍 **生成人类可读预览**（推荐，先扫一眼判断价值）→ raw-preview
   uv run .claude/skills/raw-preview/scripts/render_preview.py \
     --source raw/transcripts/bilibili/<up>/dynamics/2026/2026-05/2026-05-28.json
   → 产出启发式 draft + LLM prompt 包，Claude 读 prompt 后跑 --apply 完成预览
   → 若图缺 caption，预览顶部会有 warning 提示先跑 asset-describe

📥 **摄入到 wiki/**（沉淀知识，含两步 CoT review）→ finance-ingest
   「摄入 raw/transcripts/bilibili/<up>/dynamics/2026/2026-05/2026-05-28.json」
```

**所有下游都不自动触发**。用户/Agent 显式说出"打 caption" / "出预览" / "摄入" 才进入对应阶段。
这是有意保留的 review 边界——保持 raw → caption / preview / wiki 的人工节点不被绕过。

**Phase C 报告何时提示 asset-describe**：
- 视频源（无图）→ 不提示
- 含图动态 / 公众号文章 → 提示，并把 asset-describe 命令排在 raw-preview 之前（因为 raw-preview 会消费 caption）
- 用户已熟悉的、纯字幕视频转录 → 不提示

#### 下游 skill 选择指引

| 场景 | 推荐流程 |
|---|---|
| 视频（无图） | raw-preview → 看完决定 → finance-ingest |
| 含图动态 / 公众号文章 | **asset-describe → raw-preview → finance-ingest**（caption 是预览与摄入的共同输入）|
| 不确定源价值、想先扫一眼 | **只走 raw-preview**，不入 wiki |
| 已熟悉 UP 主、跳过预览 | **直接 finance-ingest** |
| 批量回填历史源 | `asset-describe --dir`（如适用）+ `raw-preview --backfill` + 选择性 `finance-ingest` |

raw-preview 与 asset-describe 的产物**都不进 wiki / ontology / _index.json**：
- raw-preview → `raw/.../_previews/` 下派生镜像
- asset-describe → `raw/assets/.captions/<sha256>.json` 按图内容指纹缓存

两者都可被随时重建或删除。详见 [`.claude/skills/raw-preview/SKILL.md`](../../raw-preview/SKILL.md) 与 [`.claude/skills/asset-describe/SKILL.md`](../../asset-describe/SKILL.md)。

## 输出文件 schema

### B 站视频 JSON（`raw/transcripts/bilibili/<slug>_<bvid>.json`）

```json
{
  "source": "bilibili",
  "kind": "video",
  "bvid": "BV1xxxxxx",
  "uid": "1039025435",
  "uploader": "战国时代_姜汁汽水",
  "title": "...",
  "published_at": "2026-05-15T12:00:00Z",
  "duration_seconds": 1215,
  "description": "视频简介",
  "subtitle": "字幕全文，空格分隔（向后兼容快速读取）",
  "subtitle_source": "cc-zh | ai-zh | asr-qwen3-asr-flash | none",
  "subtitle_data": {
    "source": "ai-zh",
    "lan": "ai-zh",
    "lan_doc": "中文（自动生成）",
    "type": 1,
    "body": [
      {"from": 0.5, "to": 3.2, "content": "大家好"},
      {"from": 3.5, "to": 7.1, "content": "今天讲..."}
    ]
  },
  "fetched_at": "2026-06-03T08:42:11Z",
  "link": "https://www.bilibili.com/video/BV1xxxxxx"
}
```

**`subtitle_source` 枚举值：**
| 值 | 含义 |
|---|---|
| `cc-zh` | UP 主手动上传的人工字幕 |
| `ai-zh` | B 站 AI 自动生成字幕 |
| `asr-qwen3-asr-flash` | DashScope Qwen3-ASR 兜底转写 |
| `none` | 无任何字幕 |

**`subtitle_data` 字段含义：**
- 官方字幕（`cc-zh` / `ai-zh`）：`type`=0 为人工 CC，`type`=1 为 AI；`body` 含完整时间轴 `[{from, to, content}]`
- ASR 转写（`asr-*`）：`body=null`（无逐句时间轴），额外含 `model`、`language`、`duration_s`、`asr_at`
- 无字幕：`subtitle_data=null`

### B 站动态日聚合 JSON（`raw/transcripts/bilibili/<up>/dynamics/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>.json`）

按日聚合：UTC+8 同一天内的所有动态进同一文件，按 type 分桶；顶层带轻量统计便于浏览。

```json
{
  "source": "bilibili",
  "kind": "dynamic-daily",
  "uid": "1039025435",
  "uploader": "战国时代_姜汁汽水",
  "date": "2026-03-15",
  "fetched_at": "2026-06-03T08:42:11Z",
  "stats": {
    "total": 7,
    "by_type": {"draw": 4, "word": 2, "forward": 1}
  },
  "by_type": {
    "draw": [
      {
        "dynamic_id": "718384798557536290",
        "type": "draw",
        "published_at": "2026-03-15T02:23:00Z",
        "text": "动态正文",
        "images": [
          {"local_path": "raw/assets/bilibili/1039025435/abc.jpg",
           "width": 1920, "height": 1080,
           "original_url": "https://i0.hdslb.com/..."}
        ],
        "video_ref": null,
        "article_ref": null,
        "stats": {"like": 231, "comment": 42, "forward": 5},
        "is_ad": false,
        "content_hints": ["chart_likely"],
        "image_hints": ["wide", "normal"],
        "link": "https://t.bilibili.com/718384798557536290"
      }
    ],
    "word": [],
    "forward": []
  }
}
```

**说明**：
- `by_type` 只包含当日实际出现的类型 key（空类型省略）
- `stats.by_type` 计数与对应数组长度一致（合并时重算）
- 同日二次抓取走 **C2b 新值覆盖合并**：相同 `dynamic_id` 的旧条目被新条目整体替换；新增条目追加；顶层 `fetched_at` 更新为最新时间

### 公众号 Markdown（`raw/weixin/<account-slug>/<date>-<title-slug>.md`）

```markdown
---
source: weixin
account: "<公众号名>"
account_biz: "<__biz 参数>"
author: "<作者，若 API 给>"
title: "<文章标题>"
published_at: 2026-05-15
url: https://mp.weixin.qq.com/s/...
fetched_at: 2026-06-03T08:42:11Z
images:
  - raw/assets/weixin/<account-slug>/2026-05-15-xxx-0.png
---

# <文章标题>

<readability 提取的正文，图片用相对路径 ![](../../../assets/weixin/<account-slug>/...) 引用>
```

**说明**：这个 frontmatter 是 raw 层的元数据，不需要符合 `_schema.md` 的 wiki 强校验。`finance-ingest` Step 1 会读这份 raw，生成符合 `filing-summary` schema 的 wiki 草稿。

## finance-ingest 衔接（下游契约）

为让 `finance-ingest` 顺利消费本 skill 的产出，已与其约定：

- `_schema.md` 的 `filing_type` / `source_type` 枚举扩展三个值：
  - `bilibili-video` —— B 站视频（单条一文件）
  - `bilibili-dynamic-daily` —— B 站动态按日聚合（一文件 = 一摄入单元，G1）
  - `weixin-article` —— 公众号文章
- 路径识别采用 glob 模式（F1）：
  - 视频：`raw/transcripts/bilibili/**/videos/**/*.json`
  - 动态：`raw/transcripts/bilibili/**/dynamics/**/*.json`
- B 站视频 `issuer` = UP 主名；公众号文章 `issuer` = 公众号名。
- 默认入 `wiki/filings-summary/`，命名约定：
  - 视频：`<YYYY-MM-DD>-bilibili-<uploader-slug>-<bvid>.md`
  - 动态日聚合：`<YYYY-MM-DD>-bilibili-<uploader-slug>-dyn.md`
- 一份 `dynamic-daily` JSON = 一个摄入单元，finance-ingest 把当日 N 条动态作为整体生成 wiki 草稿（G1，不按 by_type 拆分）。

如果该 UP 主 / 公众号是首次出现，`finance-ingest` 会顺便建一个 `wiki/companies/` 风格的"信息源画像页"—— 细则由 `finance-ingest` 决定，本 skill 不干预。

## 错误处理

| 失败情况 | 行为 |
|---|---|
| `KB_ROOT` 不存在 / 不是有效 KW | 抛错退出，提示用户设置 `KB_ROOT` |
| B 站 412 风控（脚本两次重试都败） | 脚本退出码非 0，本 skill 报错并建议用户：检查 `BILIBILI_SESSDATA` / 等 5 分钟重试 |
| B 站 BV 不存在 / UP 已注销 | API 返回 code≠0，脚本在 `errors` 字段标记，本 skill 报告用户并跳过 |
| 公众号链接已删除 / 403 | `fetch_weixin.py` 退出码非 0，报告用户 |
| 图片下载失败 | 单张图片失败不阻断主流程，JSON/Markdown 里 `local_path` 留空 + 在 `errors` 字段标记 |
| 视频目标文件已存在（同 bvid） | **拒绝覆盖**：报错，提示用户手动删除或加 `--overwrite` |
| 动态日聚合文件已存在（同日） | **默认 C2b 合并**：相同 `dynamic_id` 新值覆盖；新条目追加。`--rebuild` 用于忽略老文件重建 |
| 动态 `published_at` 缺失 | 跳过该条，记入 `errors`，不影响其他条目 |

## 与其它 skill 的边界

| 任务 | 用哪个 skill |
|---|---|
| 抓 B 站 / 公众号到 raw/ | **media-archive**（本 skill） |
| raw/ 源 → 人类可读预览（不入 wiki）| `raw-preview`（位于 KB 的 `.claude/skills/`）|
| raw/ → wiki/ 摄入 | `finance-ingest` |
| 维护公司画像 | `company-page` |
| 存论点 | `thesis-archive` |
| 网络搜索 / 一次性问答 | 直接 WebSearch / WebFetch |

## 历史数据迁移（一次性工具）

`scripts/migrate_bilibili_layout.py` 用于把 2026-06-03 之前老的平铺 raw 文件迁到四级布局：

```bash
# dry-run（默认）：只打印计划
uv run scripts/migrate_bilibili_layout.py --kb-root "${KB_ROOT}"

# 真跑：移老文件到 raw/transcripts/bilibili/.archive/、按新布局写新文件
uv run scripts/migrate_bilibili_layout.py --kb-root "${KB_ROOT}" --apply
```

- 视频按原 schema 落 `<up>/videos/<YYYY>/<YYYY-MM>/<date>_<bvid>.json`
- 老的单条动态按 `published_at`(UTC+8) 日期分桶聚合，写成新的 `dynamic-daily` 格式
- 老文件移到 `.archive/`，**不删除**；用户对账后可手动清理
- 已迁移完成的项目不需要再跑

## 环境依赖

- `uv`（PEP 723 内联依赖管理）
- B 站抓取：`curl_cffi==0.9.0`（自动安装）
- 公众号抓取：`readability-lxml`、`lxml-html-clean`、`html2text`、`beautifulsoup4`（自动安装）
- B 站 ASR 转写（`transcribe_bilibili.py`）：
  - `Third_Party/bili2text/`：主体工具，含 `DashScopeQwenTranscriber`（已安装于项目中）
  - `Third_Party/Qwen3-ASR-Toolkit/`：QwenASR 封装（重试/幻觉过滤），已克隆
  - `pydub`、`soundfile`（已纳入 bili2text 依赖，`uv sync` 后自动就绪）
  - `ffmpeg`：系统依赖，用于音频解码（`brew install ffmpeg`）
- 环境变量：
  - `BILIBILI_SESSDATA`：登录态 Cookie，显著提升字幕获取成功率
  - `BILIBILI_PROXY`：HTTP 代理（如频繁触发 412）
  - `KB_ROOT`：Knowledge_Wiki 根路径，默认 `<project_root>/Knowledge_Wiki`
  - `DASHSCOPE_API_KEY`：必须，ASR 转写时使用（Qwen3-ASR-Flash）
