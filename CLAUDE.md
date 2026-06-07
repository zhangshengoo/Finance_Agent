# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`Finance_Agent` is a **knowledge agent** for personal finance / investing research. It has no server, no UI, no backend — it is a directory of Markdown + a set of Claude Code skills that read and write that directory. All "intelligence" lives in:

1. **[Knowledge_Wiki/](Knowledge_Wiki/)** — the knowledge base the agent reads from and writes to. This is a separate git repo (`Knowledge_Wiki/.git`).
2. **Skills** — split by role across two `.claude/skills/` homes (plus globally-installed ones):
   - **`Knowledge_Wiki/.claude/skills/`** = **KB document-management** capabilities (operate on the KB's raw/wiki layers, anchored inside `Knowledge_Wiki/`): `finance-ingest` (两步 CoT 财报摄入), `company-page` (公司画像), `thesis-archive` (论点归档), `raw-preview` (raw 可读化预览), `asset-describe` (raw 图片 caption).
   - **`.claude/skills/`** (project root) = the **Agent's analysis / research & acquisition** capabilities (run from the project root, reach into the KB via `Knowledge_Wiki/` prefixes): `industry-analysis` (行业分析, + companion subagent `.claude/agents/industry-collector-cn.md`), `media-archive` (B 站/公众号采集落 raw). Planned next: 个股分析.

   **Rule of thumb:** if a skill's job is to *maintain knowledge documents* (deposit raw / compile wiki), it lives in `Knowledge_Wiki/.claude/skills/`. If its job is to *analyze / research / acquire* and then hand off to the KB skills for persistence, it lives at the project root.

There is **no application code** in the repo root. Work happens by editing the wiki, adding skills, and writing design docs.

## Repo layout (top-level)

| Path | Role |
|---|---|
| [Knowledge_Wiki/](Knowledge_Wiki/) | The actual KB. **Has its own [Knowledge_Wiki/CLAUDE.md](Knowledge_Wiki/CLAUDE.md) — read it before touching the wiki.** |
| [docs/](docs/) | Design specs for skills (e.g. `industry-analysis-requirements.md` — the now-built root skill `.claude/skills/industry-analysis/` was based on it) |
| [finance-kb-design.md](finance-kb-design.md) | Canonical design doc for the KB (Karpathy gist + llm_wiki synthesis) |
| [karpathy_gist.md](karpathy_gist.md) | Source: the "LLM wiki" pattern this project follows |
| `~/code/llm_wiki/` (out-of-tree) | **Reference implementation only.** A Tauri/React app that inspired the design. Moved out of this repo on 2026-06-04 to keep the working tree small; consult it only when you need to look up how the original project solved an ingest/UI problem. |
| `knowledge-wiki-*.html` | Generated visual explainers for the wiki structure/flow (not source) |

## Knowledge_Wiki architecture (the part Claude touches most)

Three layers, strictly separated:

```
raw/        ← immutable sources (PDFs, transcripts, 研报, 对账单)  — NEVER edit
wiki/       ← LLM-compiled typed entity pages (company / sector / thesis / filing-summary / …)
thoughts/   ← user-subjective notes (ideas / questions / decisions / reflections / todos), private-only
```

Plus three control files at `Knowledge_Wiki/` root: `purpose.md` (scope), `_schema.md` (frontmatter rules), `_areas-registry.md` (placement decision tree), and `_capabilities.yaml` (C-tier feature flags — default all off).

### Hard invariants (from [Knowledge_Wiki/CLAUDE.md](Knowledge_Wiki/CLAUDE.md))

These are non-negotiable when writing into the KB:

1. **`raw/` is immutable.** Ingest only flows raw → wiki via the `finance-ingest` skill (two-step CoT: analyze, then generate).
2. **Every `wiki/*` and `thoughts/*` page needs full YAML frontmatter.** `wiki/*` additionally needs `sources[]`. Schema is enforced by `build_index.py --strict`.
3. **Never fabricate** financial data, holdings, fees, market share. Missing fields → `null`, never an LLM guess.
4. **Ontology writes go through [Knowledge_Wiki/scripts/graph_append.py](Knowledge_Wiki/scripts/graph_append.py)**. Never edit `ontology/graph.jsonl` directly — it is append-only.
5. **`thoughts/` is `visibility: private` forced.** Do not paraphrase the user's theses / ideas; keep original wording.
6. **Placement decisions:** check `_areas-registry.md` decision tree first. If unsure, drop in `thoughts/_inbox/` and re-home within 48h.
7. **Don't touch** `.ingest-cache/`, `.ingest-queue/`, `.kb-vectors/` — these are skill internal state.

### Skill protocol

- New ingestion skills must follow the two-step CoT pattern (`templates/prompts/ingest-analyze.md` → `ingest-generate.md`) so the analysis step can be paused for human review.
- Skills declared in `Knowledge_Wiki/skills-lock.json` are pinned from external sources (anthropics, kepano, …) — update via the lock file, not by editing the installed skill in place.
- Trigger phrases live in each skill's `SKILL.md` description; design docs in `docs/*-requirements.md` define new skills before they're built (see `docs/industry-analysis-requirements.md` for the current template).

## Commands

All tooling lives under `Knowledge_Wiki/scripts/` and uses only the Python stdlib (no PyYAML, no deps).

```bash
# Run from inside Knowledge_Wiki/
python3 scripts/build_index.py             # regenerate _index.json
python3 scripts/build_index.py --validate  # check frontmatter on all wiki/thoughts pages
python3 scripts/build_index.py --strict    # strict mode (pre-commit gate)

# Ontology (append-only)
python3 scripts/graph_append.py stats
python3 scripts/graph_append.py validate
python3 scripts/graph_append.py history --id <node-id>
python3 scripts/graph_append.py create --type <Type> --id <id> --props '<json>'
python3 scripts/graph_append.py relate --from <id> --rel <REL> --to <id>
python3 scripts/graph_append.py supersede --old <id> --new <id> --reason "<text>"
```

There is no build, no test suite, no lint config at the repo level — `build_index.py --strict` is the validation gate.

## When working on a task

1. If the task touches the wiki, **read [Knowledge_Wiki/CLAUDE.md](Knowledge_Wiki/CLAUDE.md) first** — it has the operational contract and is more detailed than this file.
2. Before writing any `wiki/` or `thoughts/` page, consult `_areas-registry.md` for placement and `_schema.md` for required frontmatter.
3. For new skills, read the matching `docs/*-requirements.md` spec if one exists, and mirror the structure of an existing skill in `Knowledge_Wiki/.claude/skills/` (e.g. `finance-ingest`, `company-page`, `thesis-archive`).
4. After any wiki edit, run `python3 scripts/build_index.py --validate` to confirm frontmatter still passes.
