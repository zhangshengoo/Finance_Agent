# media-archive raw 层目录重组 — 设计稿

- 日期：2026-06-03
- 范围：`.claude/skills/media-archive/` 的 B 站抓取脚本与 `Knowledge_Wiki/raw/transcripts/bilibili/` 物理布局
- 影响下游：`Knowledge_Wiki/.claude/skills/finance-ingest/` 的源路径识别需同步改造

## 1. 背景与目标

当前 `raw/transcripts/bilibili/` 平铺存储所有视频与动态文件（截至本次改造 25 个文件 = 5 视频 + 20 单条动态），存在两个问题：

1. **无层次**：UP 主增多、时间窗口拉长后，单目录文件数线性膨胀，无法直观浏览
2. **动态粒度过细**：每条动态一文件，对"当日 UP 主在干嘛"这类自然检索单位不友好

目标：为 raw 层引入按 **UP 主 / 类型 / 年 / 月** 四级分层，视频按单条存储、动态按日聚合存储。

## 2. 已决策项汇总

| # | 主题 | 选择 |
|---|---|---|
| Q1 | 三级目录顺序 | A：`up主 / 类型 / 时间` |
| Q2 | 时间层粒度 | A1：`YYYY / YYYY-MM` 两级 |
| Q3 | 动态聚合内层结构 | B2：按 `by_type` 分组 + 顶层 stats（精简版） |
| Q4 | 同日二次抓冲突处理 | C2b：新值覆盖（last-write-wins） |
| 时区 | 文件名日期基准 | 文件名 UTC+8；JSON 内 `published_at` 保留 UTC ISO |
| Q5 | 老数据处理 | D1：一次性迁移到新结构 |
| Q6 | 视频文件命名 | E1：`<date>_<bvid>.json` |
| Q7 | finance-ingest 改造 | F1：同步改路径识别（glob 模式） |
| Q8 | 动态摄入粒度 | G1：一文件 = 一摄入单元（finance-ingest 侧最小改动） |

## 3. 目录布局

```
Knowledge_Wiki/raw/
├── transcripts/bilibili/
│   └── <uploader-slug>/                    # 第 1 级：UP 主
│       ├── videos/                          # 第 2 级：类型
│       │   └── 2026/2026-03/                # 第 3-4 级：年/月（UTC+8）
│       │       └── 2026-03-15_BV1xx.json    # 单视频文件
│       └── dynamics/
│           └── 2026/2026-03/
│               └── 2026-03-15.json          # 按日聚合
│
├── news/weixin/<account-slug>/             # 公众号沿用现状不变
└── assets/
    ├── bilibili/<uid>/                     # 图片资源沿用现状
    └── weixin/<account-slug>/
```

**边界说明**：
- UTC+8 日期边界仅用于文件名/目录名，文件内 `published_at` 仍 UTC ISO
- `assets/` 与 `weixin/` 本次不动
- `uploader-slug` 用 `_bilibili_common.slugify(uploader)`，空 uploader 兜底为 `uid-<UID>`

## 4. 动态聚合 JSON Schema（精简版）

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
    "draw":    [ /* 单条动态对象 */ ],
    "word":    [ ],
    "forward": [ ]
  }
}
```

- 单条动态对象字段沿用现有格式（`dynamic_id` / `type` / `published_at` / `text` / `images` / `stats` / `is_ad` / `content_hints` / `image_hints` / `video_ref` / `article_ref` / `link`），不增减
- `by_type` 只包含当日实际出现过的类型 key，空类型省略
- `stats.by_type` 与对应数组长度一致（合并时重算）

## 5. 视频文件 Schema

沿用现有 schema（`source/kind/bvid/uid/uploader/title/published_at/duration_seconds/description/subtitle/subtitle_source/fetched_at/link`），**不变**。只改变落盘路径与文件名。

文件路径：`<up>/videos/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>_<BVID>.json`，其中 `<YYYY-MM-DD>` 来自 `published_at` 的 UTC+8 日期。

## 6. C2b 合并算法（动态聚合）

```
对每个日期桶 (date, new_bucket)：
  target_path = .../dynamics/<year>/<year-month>/<date>.json

  1. 文件不存在 → 直接构造 JSON 写入
  2. 文件已存在：
       a. 读老文件 → 把 by_type[*] 平铺成 dict { dyn_id → dyn }
       b. 遍历本次抓到的 new_bucket 的 dyn → 覆盖/插入 dict（C2b 新值覆盖）
       c. 按 type 重新分桶 → 新 by_type（只保留非空类型 key）
       d. 重算 stats.total 与 stats.by_type
       e. 更新 fetched_at = now
       f. 临时文件 + os.replace() 原子写回
```

**关键实现要点**：
- **原子写入**：`tempfile.NamedTemporaryFile(dir=同目录, delete=False)` → `os.replace(tmp, target)`，崩溃不留半文件
- **日期桶按 UTC+8 切分**：跨日动态各归各日，分别独立合并
- **异常路径**：JSON 损坏 / 磁盘满 → 不写入、stderr 报错、退出码非 0；不允许半合并状态
- **`--overwrite` 参数改名为 `--rebuild`**：避免与老语义肌肉记忆冲突。默认行为是 C2b 合并；`--rebuild` 用于忽略老文件、按本次抓取重建
- **视频不走合并算法**：单条一文件，目标已存在时报错跳过（与现有 `--overwrite` 语义一致）

## 7. 老数据迁移设计 (D1)

新增脚本：`.claude/skills/media-archive/scripts/migrate_bilibili_layout.py`

### 7.1 流程

```
扫描 raw/transcripts/bilibili/*.json （顶层平铺，不递归）
  │
  ├── 按 kind 分流：
  │     "video"   → 迁移到 <up>/videos/<year>/<year-month>/<date>_<bvid>.json
  │     "dynamic" → 按 published_at(UTC+8) 日期分桶 → 累积到日聚合文件
  │
  ├── 视频：内容不变，仅改路径
  └── 动态：日期分桶后，调用第 6 节合并算法落盘（与抓取脚本共享实现）
```

### 7.2 安全设计

- **默认 `--dry-run`**：只打印迁移计划（每文件→目标路径），不实际写
- **`--apply` 才真跑**
- **老文件不删，移到 `.archive/`**：迁移后 `raw/transcripts/bilibili/<原文件名>` → `raw/transcripts/bilibili/.archive/<原文件名>`，绝不 `rm`
- **目标已存在 = 报错**：迁移非合并语义，冲突时报错由用户决策
- **idempotent**：重复跑应是 no-op（`.archive/` 在扫描时跳过）
- **uploader 空兜底**：用 `uid-<UID>` 作为 slug
- **published_at 缺失**：记入 `errors[]`，跳过该文件

### 7.3 报告与验证

迁移完成后 stdout 输出 JSON：
```json
{
  "migrated": {"videos": 5, "dynamics_files": 18, "dynamics_entries": 20},
  "archived": [".archive/战国时代_姜汁汽水_BV1xx.json", ...],
  "errors": {}
}
```

人工验证清单：
1. `raw/transcripts/bilibili/` 顶层应只剩 `.archive/`
2. 新结构 `<up>/videos/2026/2026-XX/` 数量与原视频数一致
3. 新结构 `<up>/dynamics/2026/2026-XX/*.json` 每个文件 `stats.total == sum(len(by_type[k]) for k in by_type)`
4. 抽查任一视频文件与 `.archive/` 中原文件 `diff` 为空（除路径外内容不变）

## 8. finance-ingest 路径识别改造 (F1)

`finance-ingest` 通过 CLI `--props '{"path": "..."}'` 显式接收路径，本身不做自动 glob 扫描，因此 F1 改造的核心是：

1. **路径识别**：让 finance-ingest 接受多级深路径作为 B 站源（不需要改 glob，是 CLI 参数传入）
2. **`source_type` 枚举扩展**：
   - 新增 `bilibili-video`（适配单条视频）
   - 新增 `bilibili-dynamic-daily`（适配按日聚合，对应 G1 一文件一摄入单元）
3. **Step 1 prompt 模板适配 `bilibili-dynamic-daily`**：输入是一份含多条动态的 JSON，要求生成"当日 UP 主动态摘要"风格的 wiki 草稿
4. **`filings-summary` 命名约定补充**：
   - 视频：`<YYYY-MM-DD>-bilibili-<uploader-slug>-<bvid>.md`
   - 动态日聚合：`<YYYY-MM-DD>-bilibili-<uploader-slug>-dyn.md`

本次改造**不**重写 finance-ingest 的核心逻辑，只更新 SKILL.md 的下游契约文档 + 必要的 `source_type` 枚举值。具体 finance-ingest 内部 prompt 调整由该 skill 独立演进。

## 9. media-archive SKILL.md 更新点

- **写入目标矩阵**（第 52-60 行）：更新路径列
- **B 站动态 JSON 章节**（第 157-181 行）：替换为新的日聚合 schema
- **finance-ingest 衔接章节**（第 207-218 行）：补充 `bilibili-dynamic-daily` 枚举与命名约定
- **错误处理表**（第 220-230 行）：更新"目标文件已存在"行为——视频沿用拒绝覆盖；动态默认合并、`--rebuild` 重建
- **环境依赖章节**：无新依赖

## 10. 实施步骤（高层）

1. 改 `_bilibili_common.py`：新增 UTC+8 helper、路径构造 helper、原子写入 helper
2. 改 `fetch_bilibili.py`：用新路径写入视频（schema 不变）
3. 改 `fetch_bilibili_dynamic.py`：按日聚合 + C2b 合并写入
4. 新增 `migrate_bilibili_layout.py`：一次性迁移脚本（默认 dry-run）
5. 更新 SKILL.md：写入矩阵、动态 JSON 章节、错误处理表、finance-ingest 衔接
6. 执行迁移（dry-run → 人工对账 → apply）
7. 验证清单逐项核对

## 11. 不在本次范围

- 公众号路径布局改造（`weixin/` 沿用现状）
- `assets/` 目录改造
- finance-ingest 内部 prompt/逻辑改造（仅文档同步）
- 按类型分流的 G2 方案（演进留待未来）
- `merge_history` / `first_seen_at` 等审计字段（精简掉）
