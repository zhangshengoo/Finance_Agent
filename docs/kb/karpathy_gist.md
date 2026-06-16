# LLM Wiki

A pattern for building personal knowledge bases using LLMs.

This is an idea file, it is designed to be copy pasted to your own LLM Agent (e.g. OpenAI Codex, Claude Code, OpenCode / Pi, or etc.). Its goal is to communicate the high level idea, but your agent will build out the specifics in collaboration with you.

## The core idea

Most people's experience with LLMs and documents looks like RAG: you upload a collection of files, the LLM retrieves relevant chunks at query time, and generates an answer. This works, but the LLM is rediscovering knowledge from scratch on every question. There's no accumulation. Ask a subtle question that requires synthesizing five documents, and the LLM has to find and piece together the relevant fragments every time. Nothing is built up. NotebookLM, ChatGPT file uploads, and most RAG systems work this way.

The idea here is different. Instead of just retrieving from raw documents at query time, the LLM **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files that sits between you and the raw sources. When you add a new source, the LLM doesn't just index it for later retrieval. It reads it, extracts the key information, and integrates it into the existing wiki — updating entity pages, revising topic summaries, noting where new data contradicts old claims, strengthening or challenging the evolving synthesis. The knowledge is compiled once and then *kept current*, not re-derived on every query.

This is the key difference: **the wiki is a persistent, compounding artifact.** The cross-references are already there. The contradictions have already been flagged. The synthesis already reflects everything you've read. The wiki keeps getting richer with every source you add and every question you ask.

You never (or rarely) write the wiki yourself — the LLM writes and maintains all of it. You're in charge of sourcing, exploration, and asking the right questions. The LLM does all the grunt work — the summarizing, cross-referencing, filing, and bookkeeping that makes a knowledge base actually useful over time. In practice, I have the LLM agent open on one side and Obsidian open on the other. The LLM makes edits based on our conversation, and I browse the results in real time — following links, checking the graph view, reading the updated pages. Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.

This can apply to a lot of different contexts. A few examples:

- **Personal**: tracking your own goals, health, psychology, self-improvement — filing journal entries, articles, podcast notes, and building up a structured picture of yourself over time.
- **Research**: going deep on a topic over weeks or months — reading papers, articles, reports, and incrementally building a comprehensive wiki with an evolving thesis.
- **Reading a book**: filing each chapter as you go, building out pages for characters, themes, plot threads, and how they connect. By the end you have a rich companion wiki. Think of fan wikis like [Tolkien Gateway](https://tolkiengateway.net/wiki/Main_Page) — thousands of interlinked pages covering characters, places, events, languages, built by a community of volunteers over years. You could build something like that personally as you read, with the LLM doing all the cross-referencing and maintenance.
- **Business/team**: an internal wiki maintained by LLMs, fed by Slack threads, meeting transcripts, project documents, customer calls. Possibly with humans in the loop reviewing updates. The wiki stays current because the LLM does the maintenance that no one on the team wants to do.
- **Competitive analysis, due diligence, trip planning, course notes, hobby deep-dives** — anything where you're accumulating knowledge over time and want it organized rather than scattered.

## Architecture

There are three layers:

**Raw sources** — your curated collection of source documents. Articles, papers, images, data files. These are immutable — the LLM reads from them but never modifies them. This is your source of truth.

**The wiki** — a directory of LLM-generated markdown files. Summaries, entity pages, concept pages, comparisons, an overview, a synthesis. The LLM owns this layer entirely. It creates pages, updates them when new sources arrive, maintains cross-references, and keeps everything consistent. You read it; the LLM writes it.

**The schema** — a document (e.g. CLAUDE.md for Claude Code or AGENTS.md for Codex) that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow when ingesting sources, answering questions, or maintaining the wiki. This is the key configuration file — it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot. You and the LLM co-evolve this over time as you figure out what works for your domain.

## Operations

**Ingest.** You drop a new source into the raw collection and tell the LLM to process it. An example flow: the LLM reads the source, discusses key takeaways with you, writes a summary page in the wiki, updates the index, updates relevant entity and concept pages across the wiki, and appends an entry to the log. A single source might touch 10-15 wiki pages. Personally I prefer to ingest sources one at a time and stay involved — I read the summaries, check the updates, and guide the LLM on what to emphasize. But you could also batch-ingest many sources at once with less supervision. It's up to you to develop the workflow that fits your style and document it in the schema for future sessions.

**Query.** You ask questions against the wiki. The LLM searches for relevant pages, reads them, and synthesizes an answer with citations. Answers can take different forms depending on the question — a markdown page, a comparison table, a slide deck (Marp), a chart (matplotlib), a canvas. The important insight: **good answers can be filed back into the wiki as new pages.** A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history. This way your explorations compound in the knowledge base just like ingested sources do.

**Lint.** Periodically, ask the LLM to health-check the wiki. Look for: contradictions between pages, stale claims that newer sources have superseded, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, data gaps that could be filled with a web search. The LLM is good at suggesting new questions to investigate and new sources to look for. This keeps the wiki healthy as it grows.

## Indexing and logging

Two special files help the LLM (and you) navigate the wiki as it grows. They serve different purposes:

**index.md** is content-oriented. It's a catalog of everything in the wiki — each page listed with a link, a one-line summary, and optionally metadata like date or source count. Organized by category (entities, concepts, sources, etc.). The LLM updates it on every ingest. When answering a query, the LLM reads the index first to find relevant pages, then drills into them. This works surprisingly well at moderate scale (~100 sources, ~hundreds of pages) and avoids the need for embedding-based RAG infrastructure.

**log.md** is chronological. It's an append-only record of what happened and when — ingests, queries, lint passes. A useful tip: if each entry starts with a consistent prefix (e.g. `## [2026-04-02] ingest | Article Title`), the log becomes parseable with simple unix tools — `grep "^## \[" log.md | tail -5` gives you the last 5 entries. The log gives you a timeline of the wiki's evolution and helps the LLM understand what's been done recently.

## Optional: CLI tools

At some point you may want to build small tools that help the LLM operate on the wiki more efficiently. A search engine over the wiki pages is the most obvious one — at small scale the index file is enough, but as the wiki grows you want proper search. [qmd](https://github.com/tobi/qmd) is a good option: it's a local search engine for markdown files with hybrid BM25/vector search and LLM re-ranking, all on-device. It has both a CLI (so the LLM can shell out to it) and an MCP server (so the LLM can use it as a native tool). You could also build something simpler yourself — the LLM can help you vibe-code a naive search script as the need arises.

## Tips and tricks

- **Obsidian Web Clipper** is a browser extension that converts web articles to markdown. Very useful for quickly getting sources into your raw collection.
- **Download images locally.** In Obsidian Settings → Files and links, set "Attachment folder path" to a fixed directory (e.g. `raw/assets/`). Then in Settings → Hotkeys, search for "Download" to find "Download attachments for current file" and bind it to a hotkey (e.g. Ctrl+Shift+D). After clipping an article, hit the hotkey and all images get downloaded to local disk. This is optional but useful — it lets the LLM view and reference images directly instead of relying on URLs that may break. Note that LLMs can't natively read markdown with inline images in one pass — the workaround is to have the LLM read the text first, then view some or all of the referenced images separately to gain additional context. It's a bit clunky but works well enough.
- **Obsidian's graph view** is the best way to see the shape of your wiki — what's connected to what, which pages are hubs, which are orphans.
- **Marp** is a markdown-based slide deck format. Obsidian has a plugin for it. Useful for generating presentations directly from wiki content.
- **Dataview** is an Obsidian plugin that runs queries over page frontmatter. If your LLM adds YAML frontmatter to wiki pages (tags, dates, source counts), Dataview can generate dynamic tables and lists.
- The wiki is just a git repo of markdown files. You get version history, branching, and collaboration for free.

## Why this works

The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. Updating cross-references, keeping summaries current, noting when new data contradicts old claims, maintaining consistency across dozens of pages. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. The wiki stays maintained because the cost of maintenance is near zero.

The human's job is to curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job is everything else.

The idea is related in spirit to Vannevar Bush's Memex (1945) — a personal, curated knowledge store with associative trails between documents. Bush's vision was closer to this than to what the web became: private, actively curated, with the connections between documents as valuable as the documents themselves. The part he couldn't solve was who does the maintenance. The LLM handles that.


## Note

This document is intentionally abstract. It describes the idea, not a specific implementation. The exact directory structure, the schema conventions, the page formats, the tooling — all of that will depend on your domain, your preferences, and your LLM of choice. Everything mentioned above is optional and modular — pick what's useful, ignore what isn't. For example: your sources might be text-only, so you don't need image handling at all. Your wiki might be small enough that the index file is all you need, no search engine required. You might not care about slide decks and just want markdown pages. You might want a completely different set of output formats. The right way to use this is to share it with your LLM agent and work together to instantiate a version that fits your needs. The document's only job is to communicate the pattern. Your LLM can figure out the rest.

---

## 附录：中文翻译

# LLM Wiki（大语言模型 维基）

一种用 LLM 构建个人知识库的范式。

这是一份"想法文档"，专门设计成可以被直接复制粘贴到你自己的 LLM Agent 中（例如 OpenAI Codex、Claude Code、OpenCode / Pi 等等）。它的目标是传达高层次的想法本身，而具体细节将由你的 Agent 与你协作落地完成。

## 核心想法

大多数人使用 LLM 处理文档的体验都长成 RAG 的样子：你上传一堆文件，LLM 在查询时检索相关片段，然后生成答案。这种方式能用，但 LLM 在每个问题上都要"从零重新发现知识"。**没有任何东西被积累下来。** 当你问一个需要综合五份文档才能回答的微妙问题时，LLM 每次都得重新找出相关片段并拼凑起来。什么都没有沉淀下来。NotebookLM、ChatGPT 文件上传、以及大多数 RAG 系统的工作方式都是如此。

这里提出的想法不同。与其在查询时仅仅从原始文档中检索，不如让 LLM **增量地构建并维护一个持续存在的 wiki** —— 一个结构化、相互链接的 markdown 文件集合，它坐落在你和原始资料之间。当你添加一个新的资料源时，LLM 不只是把它索引起来等待将来检索。它会读取、提取关键信息，并把它整合进现有 wiki —— 更新实体页面、修订主题摘要、标注新数据与旧主张的矛盾之处、强化或挑战正在演化的综合论述。**知识被编译一次，然后被持续保持最新**，而不是每次查询时重新推导一遍。

这就是关键区别：**wiki 是一个持续存在、不断累积的产物。** 交叉引用已经在那里。矛盾已经被标记出来。综合论述已经反映了你读过的全部内容。每加入一个资料源、每问一个问题，wiki 都变得更丰富。

你（几乎）从不亲自写 wiki —— 全部由 LLM 撰写和维护。你负责的是：寻找资料、探索方向、提出好问题。LLM 负责所有苦力活 —— 摘要、交叉引用、归档、簿记，这些正是真正让知识库长期有用的工作。实践中，我一边开着 LLM Agent，一边开着 Obsidian。LLM 根据我们的对话进行编辑，我实时浏览结果 —— 跟着链接走、看 graph view、读更新后的页面。**Obsidian 是 IDE；LLM 是程序员；wiki 是代码库。**

这个模式可以应用到很多不同的场景。一些例子：

- **个人**：追踪自己的目标、健康、心理、自我提升 —— 归档日记、文章、播客笔记，长期累积出一幅关于自己的结构化画像。
- **研究**：在某个主题上深入数周或数月 —— 阅读论文、文章、报告，增量地构建出一个全面的 wiki，并形成一个不断演化的论点。
- **读书**：每读一章就归档一章，逐渐为人物、主题、情节线及其连接构建页面。读完时你就拥有一份内容丰富的"伴读 wiki"。想想像 [Tolkien Gateway](https://tolkiengateway.net/wiki/Main_Page) 这样的粉丝 wiki —— 上千个相互链接的页面，覆盖人物、地点、事件、语言，由志愿者社区花费多年构建。你可以在自己读书的过程中，由 LLM 来负责所有交叉引用和维护，构建出类似规模的个人版本。
- **企业/团队**：由 LLM 维护的内部 wiki，吃进 Slack 线程、会议记录、项目文档、客户通话。可以由人工审核更新。wiki 之所以能保持最新，是因为 LLM 在做那些团队里没人愿意做的维护工作。
- **竞争分析、尽职调查、旅行规划、课程笔记、爱好深挖** —— 任何你随时间累积知识、并希望它有组织而非散落各处的场景。

## 架构

总共三层：

**原始资料（Raw sources）** —— 你精心挑选的源文档集合。文章、论文、图片、数据文件。这些是**不可变的** —— LLM 只读取，从不修改。这是你的真理之源。

**Wiki** —— 一个目录，里面全是 LLM 生成的 markdown 文件。摘要、实体页、概念页、对比页、概览页、综合页。这一层完全由 LLM 拥有。它创建页面，在新资料到来时更新页面，维护交叉引用，保持一切一致。**你读，LLM 写。**

**Schema（规范文档）** —— 一个文档（例如 Claude Code 用的 CLAUDE.md，或 Codex 用的 AGENTS.md），它告诉 LLM：wiki 是如何组织的、有哪些约定、在摄入资料 / 回答问题 / 维护 wiki 时要遵循什么工作流。这是关键的**配置文件** —— 它让 LLM 成为一个有纪律的 wiki 维护者，而不是一个通用聊天机器人。你和 LLM 会随着时间共同演化这份文档，逐渐摸索出适合你所在领域的做法。

## 操作

**摄入（Ingest）。** 你把一个新资料放进 raw 目录，让 LLM 处理它。一种典型流程：LLM 读取资料 → 跟你讨论关键要点 → 在 wiki 中写一个摘要页 → 更新索引 → 更新 wiki 中相关的实体页和概念页 → 向日志追加一条记录。一份资料可能触及 10–15 个 wiki 页面。我个人偏好**一次只摄入一个资料并全程参与** —— 我读摘要、看更新、引导 LLM 强调哪些重点。但你也可以一次批量摄入多个资料，少做监督。最适合你风格的工作流由你来开发，并在 schema 中文档化，供未来会话使用。

**查询（Query）。** 你针对 wiki 提问。LLM 搜索相关页面、阅读、综合出一个带引用的回答。回答形式可以因问题而异 —— markdown 页、对比表、幻灯片（Marp）、图表（matplotlib）、画布。一个关键洞见是：**好的回答可以被归档回 wiki，成为新页面。** 你要求的某次对比、某次分析、某个发现的连接 —— 这些都很有价值，不应该消失在聊天记录里。这样一来，你的**探索过程**也会像被摄入的资料一样，在知识库里复利累积。

**Lint（健康检查）。** 周期性地让 LLM 对 wiki 做"健康体检"。要找的东西包括：页面之间的矛盾、被新资料取代的过时主张、没有入链的"孤儿页"、被提及但还没有专属页面的重要概念、缺失的交叉引用、可以通过 web search 补足的数据缺口。LLM 很擅长建议**新的待研究问题**和**新的待查资料**。这能让 wiki 在不断生长的同时保持健康。

## 索引与日志

两个特殊文件帮助 LLM（和你）在 wiki 变大时仍能导航。它们的用途不同：

**index.md** 是**面向内容**的。它是 wiki 中一切内容的目录 —— 每个页面有一条记录，包含链接、一行简介，可选附带元数据（如日期、资料数量）。按类别组织（实体、概念、资料源等）。LLM 在每次摄入时更新它。回答查询时，LLM **先读 index** 来找相关页面，再深入具体页面。这种方式在中等规模（约 100 份资料、几百个页面）下表现出奇地好，并且避免了基于 embedding 的 RAG 基础设施。

**log.md** 是**按时间顺序**的。它是只追加的事件记录 —— 摄入了什么、查询了什么、做了什么 lint 检查。一个有用的小技巧：如果每条记录都以统一前缀开头（例如 `## [2026-04-02] ingest | 文章标题`），日志就能被普通 Unix 工具解析 —— `grep "^## \[" log.md | tail -5` 就能拿到最近 5 条记录。日志给你一个 wiki 演化的时间线，也帮助 LLM 理解最近都做了些什么。

## 可选：CLI 工具

到某个阶段，你可能想做一些小工具，让 LLM 更高效地操作 wiki。**对 wiki 页面的搜索引擎**是最显然的一个 —— 小规模下 index 文件就够了，但随着 wiki 变大，你会想要正经的搜索能力。[qmd](https://github.com/tobi/qmd) 是个不错的选择：它是针对 markdown 文件的本地搜索引擎，支持混合 BM25 / 向量搜索 + LLM 重排序，全部在本机运行。它同时提供 CLI（LLM 可以 shell out 调用）和 MCP server（LLM 可以把它当原生工具用）。你也可以自己做更简单的 —— LLM 可以帮你 vibe-code 一个 naive 的搜索脚本，等真有需要时再做。

## 小技巧

- **Obsidian Web Clipper** 是一个浏览器扩展，可以把网页文章转成 markdown。非常适合快速把资料抓进 raw 目录。
- **本地化下载图片。** 在 Obsidian 的「设置 → 文件与链接」中，把"附件文件夹路径"设为一个固定目录（如 `raw/assets/`）。然后在「设置 → 快捷键」里搜"Download"，找到 "Download attachments for current file"，绑定一个快捷键（例如 Ctrl+Shift+D）。每次剪藏完一篇文章后按一下快捷键，所有图片就都下载到本地了。这是可选项但很有用 —— 它让 LLM 可以直接查看和引用图片，而不必依赖可能失效的 URL。注意 LLM 还无法在一次读取中原生处理带内联图片的 markdown —— 变通办法是让 LLM 先读文本，再单独查看部分或全部被引用的图片以获取额外上下文。略显笨拙，但已经够用。
- **Obsidian 的 graph view** 是查看 wiki 形态的最佳方式 —— 谁连着谁、哪些页面是枢纽、哪些是孤儿。
- **Marp** 是一种基于 markdown 的幻灯片格式，Obsidian 有对应插件，适合直接从 wiki 内容生成演示稿。
- **Dataview** 是一个 Obsidian 插件，能基于页面 frontmatter 跑查询。如果你让 LLM 给 wiki 页面加 YAML frontmatter（tags、日期、资料数量等），Dataview 就能生成动态表格和列表。
- wiki 本质上就是一个由 markdown 文件组成的 git 仓库。版本历史、分支、协作 —— 全都白送。

## 为什么这种做法成立

维护知识库中真正繁琐的部分**不是阅读和思考，而是簿记**。更新交叉引用、保持摘要最新、记录新数据与旧主张的矛盾、维护数十个页面之间的一致性。人类放弃 wiki 是因为**维护成本增长得比价值更快**。而 LLM 不会感到无聊，不会忘记更新某个交叉引用，也能一次性触及 15 个文件。**wiki 之所以能保持维护，是因为维护成本接近零。**

人类的工作是：挑选资料、引导分析、提出好问题、思考这一切意味着什么。**LLM 的工作是其余的一切。**

这个想法在精神上与 Vannevar Bush 1945 年的 Memex 相关 —— 一个个人化、精心策展的知识库，文档之间通过联想路径相连。Bush 的愿景比后来的 web 更接近本文描述的形式：私人、主动策展、文档之间的连接与文档本身同样重要。他当年解决不了的部分是：**谁来做维护？** 答案是：LLM 来做。

## 备注

本文档**有意写得抽象**。它描述的是想法，不是具体实现。确切的目录结构、schema 约定、页面格式、工具链 —— 这一切都取决于你的领域、你的偏好和你选的 LLM。上面提到的所有东西**都是可选且模块化的** —— 用得上的拿走，用不上的忽略。例如：你的资料可能全是纯文本，那就完全不需要图片处理；你的 wiki 可能小到一个 index 文件就够用，不需要搜索引擎；你也许根本不在意幻灯片，只想要 markdown 页面；你可能想要一套完全不同的输出格式。**正确的用法是把这份文档分享给你的 LLM agent，与它协作实例化一个适合你需求的版本。** 这份文档的唯一任务是传达这个模式，剩下的让你的 LLM 来搞定。
