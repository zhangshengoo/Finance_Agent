/* kb-parse.js — 浏览器内把 Knowledge_Wiki 的 md / jsonl 源解析成 KB 对象。
 *
 * 单一解析真源：取代 build_frontend_data.py（及 data.json 中间产物）。同一份逻辑
 * 供 node 离线 diff 测试与浏览器 live 运行。语义严格移植自：
 *   - build_index.py  : parse_frontmatter_block / _parse_scalar（数值保持字符串，由 num() 强转）
 *   - build_frontend_data.py : read_md / parse_modules / build_analysis / 装配
 *
 * 输入：files = { "<KB相对路径>": "<文件原文>" }，键如
 *   "wiki/companies/601899.md" / "raw/analysis/stocks/601899-2026-06-10.md"
 *   "ontology/graph.jsonl" / "raw/transcripts/bilibili/<creator>/_previews/timeline.json"
 * 输出：与原 data.json 同构的对象 { generated, stats, sector_index, sectors, macro, media, companies, graph }
 */
(function (global) {
  'use strict';

  const TYPE_COLOR = { MediaSource: 'media', MediaItem: 'media', Macro: 'macro', Sector: 'sector', Company: 'company' };
  const METRIC_KEYS = ['pe_ttm', 'pb', 'roe', 'roa', 'net_margin', 'gross_margin', 'debt_ratio', 'current_ratio'];

  // ---------- frontmatter（移植 build_index 简易 YAML）----------
  function stripQuotes(s) {
    s = s.trim();
    if (s.length >= 2 && s[0] === s[s.length - 1] && (s[0] === "'" || s[0] === '"')) return s.slice(1, -1);
    return s;
  }
  function parseInlineList(v) {
    const inner = v.trim().slice(1, -1).trim();
    if (!inner) return [];
    return inner.split(',').map(x => stripQuotes(x.trim()));
  }
  function parseScalar(v) {
    v = v.trim();
    if (!v) return '';
    if (v.startsWith('[') && v.endsWith(']')) return parseInlineList(v);
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) return stripQuotes(v);
    if (v.toLowerCase() === 'null' || v === '~') return null;
    return v; // 数值在此保持字符串，交给 num() 强转——与 Python 一致
  }
  function parseFrontmatterBlock(block) {
    const data = {};
    const lines = block.split('\n');
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const stripped = line.trim();
      if (!stripped || stripped.startsWith('#')) { i++; continue; }
      const m = line.match(/^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.*)$/);
      if (!m) { i++; continue; }
      const key = m[1];
      const rawValue = m[2];
      if (rawValue.trim() === '') {
        // 空值 → 看下方是否为 '- item' 块列表；缩进 'k: v' 嵌套块整体降级为字符串
        const items = [];
        let j = i + 1;
        while (j < lines.length) {
          const nl = lines[j];
          if (!nl.trim()) { j++; continue; }
          const lm = nl.match(/^\s*-\s+(.*)$/);
          if (lm) { items.push(stripQuotes(lm[1].trim())); j++; continue; }
          if (/^\s+\S/.test(nl)) {
            const nested = [nl]; j++;
            while (j < lines.length && (!lines[j].trim() || /^\s+\S/.test(lines[j]))) { nested.push(lines[j]); j++; }
            if (items.length) break;            // 已有 list 项 → 以 list 为准
            data[key] = nested.join('\n').trim();
            break;
          }
          break; // 顶层新 key
        }
        if (!(key in data)) data[key] = items;
        i = j;
        continue;
      }
      data[key] = parseScalar(rawValue);
      i++;
    }
    return data;
  }
  function extractFrontmatter(text) {
    let m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);
    if (m) return parseFrontmatterBlock(m[1]);
    // 兜底：前 6 行内找
    const head = '\n' + text.split('\n').slice(0, 6).join('\n');
    m = head.match(/\n---\s*\n([\s\S]*?)\n---\s*\n/);
    if (m) return parseFrontmatterBlock(m[1]);
    return {};
  }
  function readMd(text) {
    const fm = extractFrontmatter(text) || {};
    const idx = text.indexOf('\n---\n');
    const body = idx >= 0 ? text.slice(idx + 5) : text; // = text.split("\n---\n",1)[-1]
    return { fm, body };
  }

  // ---------- 标量 / 文本工具 ----------
  function num(x) {
    if (x === null || x === undefined || x === '') return null;
    if (Array.isArray(x)) return null;
    const f = Number(x);
    return Number.isNaN(f) ? null : f; // 35.0→35、13.2→13.2（JSON 序列化与 Python int/float 一致）
  }
  function short(name) { return (name || '').split(/[（(]/)[0].trim(); }
  function splitCell(cell) {
    const parts = String(cell).split('|');
    return { label: parts[0].trim(), bottleneck: parts.length > 1 && parts[1].includes('bottle') };
  }
  function parseChain(items) {
    return (items || []).map(it => {
      const parts = String(it).split('|').map(p => p.trim());
      return { role: parts[0], text: parts.length > 1 ? parts[1] : '', flag: parts.length > 2 ? parts[2] : null };
    });
  }

  // ---------- 注释栅栏模块 ----------
  const MODULE_RE = /<!--\s*module:\s*([\w-]+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*([^>]+?)\s*-->([\s\S]*?)<!--\s*\/module\s*-->/g;
  function parseModules(body) {
    const out = [];
    MODULE_RE.lastIndex = 0;
    let m;
    while ((m = MODULE_RE.exec(body))) {
      let prose = m[6].trim().replace(/^\s*#{1,6}\s+.*\n+/, ''); // 去掉栅栏内首行标题
      out.push({
        id: m[1].trim(), status: m[2].trim().toLowerCase(), layer: m[3].trim().toLowerCase(),
        title: m[4].trim(), src: m[5].trim(), prose: prose.trim(),
      });
    }
    return out;
  }

  // 回测报告正文的 <!-- backtest-json --> ```json {trades,lessons,equity_curve,metrics}``` 块
  function parseBacktestJson(body) {
    const m = (body || '').match(/<!--\s*backtest-json\s*-->\s*```json\s*([\s\S]*?)```/);
    const empty = { trades: [], lessons: [], equity_curve: [], metrics: null };
    if (!m) return empty;
    try {
      const o = JSON.parse(m[1].trim());
      return { trades: o.trades || [], lessons: o.lessons || [],
               equity_curve: o.equity_curve || [], metrics: o.metrics || null };
    } catch (e) { return empty; }
  }

  function buildAnalysis(fm) {
    if (fm.ta_action === undefined || fm.ta_action === null) return null;
    return {
      action: fm.ta_action,
      target_price: num(fm.ta_target_price),
      confidence: num(fm.ta_confidence),
      risk_score: num(fm.ta_risk_score),
      as_of: String(fm.ta_as_of == null ? '' : fm.ta_as_of),
      reason: fm.ta_reason || '',
      chain: parseChain(fm.decision_chain),
      technical: { trend: fm.ta_trend == null ? null : fm.ta_trend, support: num(fm.ta_support), resistance: num(fm.ta_resistance) },
      key_metrics: Object.fromEntries(METRIC_KEYS.map(k => [k, num(fm[k])])),
      bull: fm.bull || [], bear: fm.bear || [], catalysts: fm.catalysts || [], risks: fm.risks || [],
    };
  }

  // ---------- 正文表格 / taxonomy / drivers ----------
  function parseLeadersTable(body) {
    const m = body.match(/###\s*3\.1[\s\S]*?\n([\s\S]*?)(?:\n###\s|$)/);
    if (!m) return [];
    const rows = [];
    for (let line of m[1].split('\n')) {
      line = line.trim();
      if (!line.startsWith('|')) continue;
      const cells = line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      if (cells.length < 7 || !/^\d+$/.test(cells[0])) continue;
      const clean = s => s.replace(/\[/g, '').replace(/\]/g, '').trim().toUpperCase() === 'UNSOURCED' ? null : s;
      rows.push({
        rank: parseInt(cells[0], 10), name: cells[1], code: cells[2],
        mcap: clean(cells[3]), pe: clean(cells[4]),
        position: cells.length > 6 ? cells[6] : cells[cells.length - 1],
      });
    }
    return rows;
  }
  function parseTaxonomy(files) {
    const txt = files['wiki/sectors/_taxonomy.md'];
    if (!txt) return [];
    const { body } = readMd(txt);
    const out = [];
    for (let line of body.split('\n')) {
      line = line.trim();
      if (!line.startsWith('|')) continue;
      const cells = line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      if (cells.length < 3 || !/^\d{6}$/.test(cells[0])) continue;
      out.push({ sw_code: cells[0], name: cells[1], slug: cells[2] });
    }
    return out;
  }
  function parseDrivers(summary) {
    const m = (summary || '').match(/(?:驱动因素|定价|传导链|驱动)[：:]\s*([^。\n]+)/);
    if (!m) return [];
    return m[1].split(/[、,，]/).map(x => x.trim()).filter(Boolean).slice(0, 5);
  }

  function parseGraph(files) {
    const nodes = {}, edges = [];
    const txt = files['ontology/graph.jsonl'];
    if (txt) {
      for (let line of txt.split('\n')) {
        line = line.trim();
        if (!line) continue;
        let ev; try { ev = JSON.parse(line); } catch (e) { continue; }
        if (ev.op === 'create') {
          const e = ev.entity;
          nodes[e.id] = { id: e.id, etype: e.type, props: e.props || {} };
        } else if (ev.op === 'relate') {
          edges.push({ from: ev.from, to: ev.to, rel: ev.rel });
        }
      }
    }
    return { nodes, edges };
  }

  function bvid(s) { const m = (s || '').match(/BV[0-9A-Za-z]+/); return m ? m[0] : null; }

  // ============================ 装配 ============================
  function kbParse(files) {
    // ---- wiki docs ----
    const docs = [];
    Object.keys(files).sort().forEach(rel => {
      if (!rel.startsWith('wiki/') || !rel.endsWith('.md')) return;
      const { fm, body } = readMd(files[rel]);
      const stem = rel.split('/').pop().replace(/\.md$/, '');
      docs.push({ rel, stem, fm, body });
    });
    const byType = t => docs.filter(d => d.fm.type === t);

    const macroName = {};
    byType('macro-topic').forEach(d => { macroName[d.stem] = short(d.fm.title || d.stem); });

    const { nodes: gnodes, edges: gedges } = parseGraph(files);

    // ---- sectors ----
    const sectors = [], sectorByCode = {};
    byType('sector').forEach(d => {
      if (d.stem === '_taxonomy') return;
      const fm = d.fm;
      const code = (fm.taxonomy_code || '').replace('SW:', '');
      const obj = {
        slug: fm.slug || d.stem, name: short(fm.title || ''), title: fm.title || '',
        code: fm.taxonomy_code == null ? null : fm.taxonomy_code, market: fm.market == null ? null : fm.market,
        status: fm.status || 'full', summary: fm.summary || '',
        constituents: fm.constituents === undefined ? null : fm.constituents,
        updated: String(fm.updated == null ? '' : fm.updated),
        valuation: { pe_ttm: fm.pe_ttm == null ? null : fm.pe_ttm, pb: fm.pb == null ? null : fm.pb,
                     div_yield: fm.div_yield == null ? null : fm.div_yield, rank: fm.val_rank == null ? null : fm.val_rank },
        value_chain: {
          up: (fm.value_chain_up || []).map(splitCell),
          mid: (fm.value_chain_mid || []).map(splitCell),
          down: (fm.value_chain_down || []).map(splitCell),
        },
        bull: fm.bull || [], bear: fm.bear || [],
        leaders: parseLeadersTable(d.body),
        sources: fm.sources || [],
      };
      sectors.push(obj);
      if (code) sectorByCode[code] = obj;
    });

    // ---- 行业索引（31 行业全集）----
    const sectorIndex = parseTaxonomy(files).map(t => {
      const an = sectorByCode[t.sw_code];
      return {
        name: an ? an.name : t.name, code: 'SW:' + t.sw_code, slug: an ? an.slug : t.slug,
        status: an ? an.status : 'stub', pe_ttm: an ? an.valuation.pe_ttm : null,
        desc: an ? an.summary : null,
      };
    });

    // ---- macro ----
    const macro = byType('macro-topic').map(d => ({
      slug: d.stem, name: short(d.fm.title || ''), kind: d.fm.indicator_kind == null ? null : d.fm.indicator_kind,
      region: d.fm.region == null ? null : d.fm.region, summary: d.fm.summary || '',
      drivers: parseDrivers(d.fm.summary || ''), sources: d.fm.sources || [],
    }));

    // ---- research reports（raw/analysis/stocks/*.md，type=stock-report）----
    const reportsByTicker = {};
    Object.keys(files).sort().forEach(rel => {
      if (!rel.startsWith('raw/analysis/stocks/') || !rel.endsWith('.md')) return;
      const { fm, body } = readMd(files[rel]);
      if (fm.type !== 'stock-report') return;
      const stem = rel.split('/').pop().replace(/\.md$/, '');
      const tk = String(fm.ticker || stem.split('-')[0]);
      (reportsByTicker[tk] = reportsByTicker[tk] || []).push({
        run_id: stem, ticker: tk, name: short(fm.name || fm.title || ''),
        as_of: String(fm.as_of == null ? '' : fm.as_of), depth: fm.depth === undefined ? null : fm.depth,
        engine: fm.engine == null ? null : fm.engine, run_config: fm.run_config || '',
        report_status: fm.report_status || 'complete',
        price: num(fm.price), change_pct: num(fm.change_pct),
        analysis: buildAnalysis(fm), modules: parseModules(body), sources: fm.sources || [],
      });
    });
    Object.values(reportsByTicker).forEach(reps => reps.sort((a, b) => (a.as_of < b.as_of ? 1 : a.as_of > b.as_of ? -1 : 0)));

    // ---- 回测 / 记忆环（raw/analysis/backtests/**/*.md，type=backtest-report）----
    const backtestsByTicker = {};
    Object.keys(files).sort().forEach(rel => {
      if (!rel.startsWith('raw/analysis/backtests/') || !rel.endsWith('.md')) return;
      const { fm, body } = readMd(files[rel]);
      if (fm.type !== 'backtest-report') return;
      const stem = rel.split('/').pop().replace(/\.md$/, '');
      const tk = String(fm.ticker || stem.split('-')[0]);
      const { trades, lessons, equity_curve, metrics } = parseBacktestJson(body);
      (backtestsByTicker[tk] = backtestsByTicker[tk] || []).push({
        run_id: stem, ticker: tk, mode: fm.mode || 'reflect',
        as_of: String(fm.as_of == null ? '' : fm.as_of),
        snapshot_date: String(fm.snapshot_date == null ? '' : fm.snapshot_date),
        report_status: fm.report_status || 'ok', horizons: String(fm.horizons == null ? '' : fm.horizons),
        n_reflected: num(fm.n_reflected), n_non_evaluable: num(fm.n_non_evaluable),
        headline_return_pct: num(fm.headline_return_pct),
        // M2 simulate 原子
        total_return_pct: num(fm.total_return_pct), sharpe: num(fm.sharpe),
        max_drawdown_pct: num(fm.max_drawdown_pct), win_rate_pct: num(fm.win_rate_pct),
        vs_benchmark_pct: num(fm.vs_benchmark_pct), n_closed_trades: num(fm.n_closed_trades),
        period_from: String(fm.period_from == null ? '' : fm.period_from),
        period_to: String(fm.period_to == null ? '' : fm.period_to),
        initial_cash: num(fm.initial_cash),
        trades, lessons, equity_curve, metrics, sources: fm.sources || [],
      });
    });
    Object.values(backtestsByTicker).forEach(bts => bts.sort((a, b) =>
      a.as_of < b.as_of ? 1 : a.as_of > b.as_of ? -1 : (a.run_id < b.run_id ? 1 : a.run_id > b.run_id ? -1 : 0)));

    // ---- companies（wiki distilled + 挂 research reports）----
    const companies = [];
    byType('company').forEach(d => {
      const fm = d.fm;
      const ticker = String(fm.ticker == null ? d.stem : fm.ticker);
      const analysis = buildAnalysis(fm);
      const reports = reportsByTicker[ticker] || []; delete reportsByTicker[ticker];
      const backtests = backtestsByTicker[ticker] || []; delete backtestsByTicker[ticker];
      const analyzed = analysis !== null || reports.length > 0;
      companies.push({
        ticker, name: short(fm.title || ''), summary: fm.summary || '',
        sector: fm.sector == null ? null : fm.sector, market: fm.market == null ? null : fm.market,
        status: analyzed ? 'analyzed' : ((fm.summary || '').includes('stub') ? 'stub' : 'full'),
        analysis, modules: parseModules(d.body), reports, backtests, sources: fm.sources || [],
      });
    });
    // 报告有票、无 wiki 公司页 → 合成 report-only 条目
    Object.keys(reportsByTicker).forEach(ticker => {
      const reps = reportsByTicker[ticker];
      const backtests = backtestsByTicker[ticker] || []; delete backtestsByTicker[ticker];
      companies.push({
        ticker, name: reps[0].name, summary: '', sector: null, market: 'cn',
        status: 'analyzed', analysis: null, modules: [], reports: reps, backtests, sources: [],
      });
    });
    // 只有回测、无 wiki 公司页且无研究报告 → 合成 backtest-only 条目
    Object.keys(backtestsByTicker).forEach(ticker => {
      const bts = backtestsByTicker[ticker];
      companies.push({
        ticker, name: ticker, summary: '', sector: null, market: 'cn',
        status: 'analyzed', analysis: null, modules: [], reports: [], backtests: bts, sources: [],
      });
    });

    // ---- media（各 UP 主 timeline.json + wiki filing-summary 叠加）----
    const wikiBySrc = {}, wikiByBv = {};
    byType('filing-summary').forEach(d => {
      const info = { rel: d.rel, title: d.fm.title || '', summary: d.fm.summary || '' };
      (d.fm.sources || []).forEach(s => { wikiBySrc[s] = info; const bv = bvid(s); if (bv) wikiByBv[bv] = info; });
    });
    const creators = [];
    let totV = 0, totD = 0, totDeep = 0;
    Object.keys(files).sort().forEach(rel => {
      if (!/^raw\/transcripts\/bilibili\/[^/]+\/_previews\/timeline\.json$/.test(rel)) return;
      let tl; try { tl = JSON.parse(files[rel]); } catch (e) { return; }
      let nDeep = 0;
      (tl.items || []).forEach(it => {
        let w = wikiBySrc[it.src];
        if (!w && it.kind === 'video') w = wikiByBv[bvid(it.src)];
        it.has_wiki = w != null; it.wiki = w || null;
        if (w) nDeep++;
      });
      tl.n_deep = nDeep;
      totV += tl.n_videos || 0; totD += tl.n_dynamics || 0; totDeep += nDeep;
      creators.push(tl);
    });
    const media = {
      creators,
      stats: { total: totV + totD, videos: totV, dynamics: totD, deep: totDeep, creators: creators.length },
    };

    // ---- 星图：图谱节点 + 合成 sector/leader/company ----
    const cnNodes = [], cnEdges = [], seen = new Set();
    Object.keys(gnodes).forEach(nid => {
      const n = gnodes[nid];
      let label = n.props.name || n.props.slug || nid;
      if (n.etype === 'Macro') label = macroName[n.props.slug] || label;
      else if (n.etype === 'MediaItem') label = (String(n.props.published_at || '').slice(5) + ' ' + (String(n.props.filing_type || '').includes('video') ? '视频' : '动态'));
      else if (n.etype === 'MediaSource') label = short(n.props.name || label);
      else if (n.etype === 'Backtest') label = '回测 ' + (n.props.headline_return_pct != null ? (n.props.headline_return_pct >= 0 ? '+' : '') + n.props.headline_return_pct + '%' : (n.props.ticker || nid));
      cnNodes.push({ id: nid, type: TYPE_COLOR[n.etype] || 'company', label });
      seen.add(nid);
    });
    gedges.forEach(e => cnEdges.push({ from: e.from, to: e.to, rel: e.rel }));
    const compName = {}; companies.forEach(c => { compName[c.ticker] = c.name; });
    sectors.forEach(s => {
      const sid = 'sector_' + s.slug;
      cnNodes.push({ id: sid, type: 'sector', label: s.name });
      const sdoc = byType('sector').find(d => d.fm.slug === s.slug);
      const leaders = (sdoc && sdoc.fm.leaders) || [];
      leaders.forEach(code => {
        const cid = 'company_' + code;
        if (!seen.has(cid)) { cnNodes.push({ id: cid, type: 'company', label: compName[code] || code }); seen.add(cid); }
        cnEdges.push({ from: sid, to: cid, rel: 'LEADER' });
      });
    });
    const linked = new Set(); cnEdges.forEach(e => { linked.add(e.from); linked.add(e.to); });
    companies.forEach(c => {
      const cid = 'company_' + c.ticker;
      if (!seen.has(cid) && !linked.has(cid)) { cnNodes.push({ id: cid, type: 'company', label: c.name }); seen.add(cid); }
    });

    return {
      generated: null,
      stats: {
        documents: docs.length,
        sectors_analyzed: sectors.length, sectors_total: sectorIndex.length,
        media: media.stats.total, macro: macro.length, companies: companies.length,
        nodes: cnNodes.length, edges: cnEdges.length,
      },
      sector_index: sectorIndex, sectors, macro, media, companies,
      graph: { nodes: cnNodes, edges: cnEdges },
    };
  }

  const api = { kbParse, readMd, parseModules, buildAnalysis, num, parseFrontmatterBlock };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.kbParse = kbParse;
  global.KBParse = api;
})(typeof window !== 'undefined' ? window : globalThis);
