# M2 净值曲线前端 + wiki/ontology 编译 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本仓库不走 pytest-TDD**（用户明确偏好；repo 根无测试套件）。每个任务的"验证步骤"用本项目真实的校验闸：`run_backtest.py` 的 `OK` stdout、`node` 解析 harness、`build_index.py --validate`、`graph_append.py validate/stats`、`curl` 本地服务。**提交（git commit）仅在用户要求时做**——计划把建议提交点放在每个 Part 末尾并标注「可选」。

**Goal:** 把已实现但未接前端的 M2 前向组合模拟（净值曲线 + 指标）接进前端「回测 / 记忆环」单元；并把回测产物经 finance-ingest 编译成 `wiki/reports` 页 + ontology `Backtest` 节点，让回测进入知识图谱。

**Architecture:** 复用现有「Agent 写 KB 文件 → 前端 live-parse 渲染」单向数据流。Part A：`run_backtest.py --mode simulate` 末尾**新增**落一份 `backtest-report.md`（`mode: simulate`，正文 json 块带 `equity_curve` + `metrics`）→ `kb-parse.js` 扩展解析 → `index.html renderBacktest()` 增 M2 分支（指标卡 + 手绘 SVG 净值曲线 + round-trip 成交表）。Part B：注册 ontology `Backtest` 节点/边 schema → finance-ingest 新增 `kind=backtest` 编译场景 → 对 601899 实跑编译出 `wiki/reports/...-backtest.md` + `graph_append` 写 Backtest 节点 → 前端星图标签。

**Tech Stack:** Python 3.10（TradingAgents-CN 自带 venv，仅 stdlib + 已装 chromadb/tushare）；vanilla JS（无框架/无构建，`kb-parse.js` 同时供 node 离线测与浏览器 live）；Knowledge_Wiki stdlib 工具链（`build_index.py` / `graph_append.py`）。

---

## Scope Check（两个独立子系统）

本计划覆盖**两个可独立交付的子系统**：

- **Part A — M2 净值曲线前端**：自成闭环（runner 落报告 → 解析 → 渲染），确定性、可验证、前端可见。**不依赖 Part B。**
- **Part B — wiki/ontology 编译**：KB 编译管线（schema 注册 + finance-ingest 场景 + 实跑编译 + 图谱写入）。前端可见的产出是**星图里多一个 Backtest 节点**（不是新面板）。**不依赖 Part A。**

二者可分批执行、分别 ship。推荐先做 Part A（高价值、纯确定性），Part B 含一步 LLM 编译（finance-ingest 两步 CoT），非确定性、靠 `--validate` 把关。

**明确不在本计划内（沿用设计文档「仍待实现」）**：raw-intake 溯源 ledger handoff（runner 当前直写 raw/，已有 sources[] 可溯，本次不改）；M2 **多票组合**视图（本次仅单票净值挂公司页）；M3 历史重跑；M2 reflect-on-close 教训回读进前端（教训仍是 M1 域）。

---

## File Structure（改动文件与职责）

### Part A
| 文件 | 动作 | 职责 |
|---|---|---|
| `.claude/skills/backtest-analysis/scripts/run_backtest.py` | 改 | `_simulate_mode` 末尾调新增 `_write_simulate_report_md()`：单票时落 `backtest-report.md`（`mode: simulate`，正文 json 块 `{mode,metrics,equity_curve,trades}` + flat 指标原子）|
| `frontend/kb-parse.js` | 改 | `parseBacktestJson` 多返回 `equity_curve`/`metrics`；backtest 推送增 M2 字段 |
| `frontend/index.html` | 改 | 新增 `btEquitySVG()`；`renderBacktest()` 增 M2 分支（指标卡 + 曲线 + 成交表）；`.bt-eqchart` CSS；`kb-parse.js?v=bt1`→`bt2` |
| `frontend/serve.sh` | 改（**可选任务 A5**）| `POST /api/backtest` 支持 `{ticker,mode}`，`mode:simulate` 跑 `--mode simulate --no-reflect` |

### Part B
| 文件 | 动作 | 职责 |
|---|---|---|
| `Knowledge_Wiki/ontology/schema.yaml` | 改 | 登记 `Backtest` 节点 + `COVERS`/`EVALUATES` 边 |
| `Knowledge_Wiki/.claude/skills/finance-ingest/SKILL.md` | 改 | 新增 `kind=backtest` 编译场景（raw 回测报告 → `wiki/reports/<date>-<ticker>-backtest.md`）|
| `docs/kb/frontend-kb-binding.md` | 改 | 新增 §2d 回测绑定契约（raw 层 / wiki 层 / ontology 三段）|
| `Knowledge_Wiki/wiki/reports/2026-06-15-601899-backtest.md` | 建 | 601899 首个回测复盘 wiki 页（type: report），经 finance-ingest 编译 |
| `Knowledge_Wiki/ontology/graph.jsonl` | 追加（经 graph_append）| `Backtest` 节点 + `COVERS` 边 |
| `frontend/kb-parse.js` | 改 | 星图 `Backtest` 节点标签规则 |

### 跨 Part 收尾
| 文件 | 动作 |
|---|---|
| `.claude/skills/backtest-analysis/SKILL.md` | 改「不做清单」「Scope」反映 M2 前端 + wiki/ontology 已落 |
| `docs/tradingagents-cn/backtest/backtest-feature-design.md` | 改抬头状态块 |

---

# Part A — M2 净值曲线前端

## Task A1: runner 落 M2 前端可读报告

**Files:**
- Modify: `.claude/skills/backtest-analysis/scripts/run_backtest.py`（在 `_simulate_mode` 之后、`_reflect_close` 之前加新函数；并在 `_simulate_mode` 收尾调用）

- [ ] **Step 1: 新增 `_write_simulate_report_md()`**

紧跟在 `_simulate_mode(...)` 函数定义之后插入（即第 577 行 `print(...)` 收尾之后、`def _reflect_close` 之前）：

```python
def _write_simulate_report_md(args, runid, out_dir, tickers, equity_curve, closed_trades, metrics):
    """M2 单票前向模拟 → 前端可读 backtest-report.md（mode: simulate）。
    仅单票挂公司页（多票组合视图后续）；equity_curve + metrics 放正文 json 块（数组进不了 mini-YAML）。"""
    if len(tickers) != 1:
        print("  （多票组合：跳过前端报告，仅机器产物；组合视图后续）")
        return None
    ticker = tickers[0]
    kb_root = os.path.abspath(os.path.join(args.ta_root, os.pardir, "Knowledge_Wiki"))
    report_dir = args.report_dir or os.path.join(kb_root, "raw", "analysis", "backtests", "cn")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{ticker}-{runid}.md")
    rel_out = os.path.relpath(out_dir, kb_root).replace(os.sep, "/")
    m = metrics or {}

    def _pct(x):
        return round(x * 100, 2) if isinstance(x, (int, float)) else None

    def _atom(v):
        return v if v is not None else "null"

    p_from = equity_curve[0]["date"] if equity_curve else ""
    p_to = equity_curve[-1]["date"] if equity_curve else ""
    tr, mdd = _pct(m.get("total_return")), _pct(m.get("max_drawdown"))
    wr, vb = _pct(m.get("win_rate")), _pct(m.get("vs_benchmark"))
    n_closed = m.get("n_closed_trades", 0) or 0
    has_bench = any(p.get("benchmark_equity") for p in equity_curve)
    run_status = "ok" if (equity_curve and n_closed) else "partial"

    payload = json.dumps({"mode": "simulate", "metrics": m,
                          "equity_curve": equity_curve, "trades": closed_trades}, ensure_ascii=False)

    fm = ["---", "type: backtest-report", f'ticker: "{ticker}"', "mode: simulate",
          f"run_status: {run_status}", f'as_of: "{p_to}"',
          f'period_from: "{p_from}"', f'period_to: "{p_to}"',
          f"initial_cash: {int(args.initial_cash)}",
          f"total_return_pct: {_atom(tr)}", f"sharpe: {_atom(m.get('sharpe'))}",
          f"max_drawdown_pct: {_atom(mdd)}", f"win_rate_pct: {_atom(wr)}",
          f"vs_benchmark_pct: {_atom(vb)}", f"n_closed_trades: {n_closed}",
          "sources:", f"  - {rel_out}/equity_curve.json", f"  - {rel_out}/trades.jsonl",
          f"  - {rel_out}/config.json", "---"]

    body = [f"# {ticker} · M2 前向纸面交易", "",
            (f"{p_from} → {p_to} 单票前向模拟（A 股 T+1，初始资金 ¥{int(args.initial_cash):,}）。"
             f"总收益 {tr if tr is not None else '—'}%，最大回撤 {mdd if mdd is not None else '—'}%，"
             f"平仓 {n_closed} 笔。" + ("（含基准对比）" if has_bench else "")),
            "", "⚠ 净值/收益用 Tushare 真实 qfq close 逐日 mark-to-market；非投资建议。", "",
            "<!-- backtest-json -->", "```json", payload, "```", ""]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n\n" + "\n".join(body) + "\n")
    return report_path
```

- [ ] **Step 2: 在 `_simulate_mode` 收尾调用它**

在 `_simulate_mode` 里，把现有结尾（第 558-576 行附近，`if not args.dry_run:` 写完机器产物之后、最后那段 `m = metrics` + `print("OK mode=simulate ...")` 之前）插入报告落盘。具体：找到 `_write_outputs(out_dir, all_trades, {... "generated_at": ...})` 这一调用所在的 `if not args.dry_run:` 块，在该块**内部、`_write_outputs(...)` 之后**追加：

```python
        report_path = _write_simulate_report_md(args, runid, out_dir, tickers,
                                                 equity_curve, closed_trades, metrics)
        if report_path:
            print(f"   report : {report_path}")
```

- [ ] **Step 3: 跑真数据生成 601899 的 M2 报告（纯算价，无 LLM）**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
TradingAgents-CN/.venv/bin/python .claude/skills/backtest-analysis/scripts/run_backtest.py \
  --ticker 601899 --mode simulate --no-reflect --ta-root TradingAgents-CN
```
Expected: stdout 末两行形如
```
OK mode=simulate universe=601899 days=N total_return=0.0xxx sharpe=... maxDD=... win_rate=1.0 closed=1 reflected=0 out=...
   report : /Users/.../Knowledge_Wiki/raw/analysis/backtests/cn/601899-<runid>.md
```
（`--no-reflect` → 不建图、不调 DashScope/Claude，纯 Tushare 价格模拟，数秒。）

- [ ] **Step 4: 校验报告结构**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
ls -t Knowledge_Wiki/raw/analysis/backtests/cn/601899-*.md | head -1 | xargs sed -n '1,20p'
```
Expected: frontmatter 有 `type: backtest-report` / `mode: simulate` / `total_return_pct:` / `sharpe:` / `n_closed_trades: 1`；正文有 `<!-- backtest-json -->` + ```json` 块。再确认 json 块可解析：
```bash
ls -t Knowledge_Wiki/raw/analysis/backtests/cn/601899-*.md | head -1 | xargs python3 - <<'PY'
import sys, re, json
md = open(sys.argv[1]).read()
m = re.search(r"<!--\s*backtest-json\s*-->\s*```json\s*([\s\S]*?)```", md)
o = json.loads(m.group(1))
print("mode=", o["mode"], "curve_pts=", len(o["equity_curve"]),
      "trades=", len(o["trades"]), "metrics_keys=", sorted(o["metrics"]))
assert o["mode"] == "simulate" and len(o["equity_curve"]) >= 2
print("OK A1 报告结构正确")
PY
```
Expected: `OK A1 报告结构正确`。

## Task A2: kb-parse.js 解析 M2 字段

**Files:**
- Modify: `frontend/kb-parse.js`（`parseBacktestJson` 约 L129-136；backtest 推送约 L294-314）

- [ ] **Step 1: `parseBacktestJson` 多返回 equity_curve + metrics**

把现有函数体替换为：

```javascript
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
```

- [ ] **Step 2: backtest 推送对象增 M2 字段**

在 `backtestsByTicker` 的 `Object.keys(files).sort().forEach(...)` 分支里，把解构与 push 改为：

```javascript
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
```

- [ ] **Step 3: node 离线 harness 验证解析**

Run（用 A1 生成的真报告 + 一个 wiki 公司页骨架，确认 `companies[].backtests[]` 带上 equity_curve/metrics）：
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
node - <<'PY'
const fs = require('fs');
const { kbParse } = require('./frontend/kb-parse.js');
const g = require('child_process').execSync(
  "ls -t Knowledge_Wiki/raw/analysis/backtests/cn/601899-*.md | head -1").toString().trim();
const rel = g.replace(/^Knowledge_Wiki\//, '');
const files = { [rel]: fs.readFileSync(g, 'utf8') };
const kb = kbParse(files);
const c = kb.companies.find(x => x.ticker === '601899');
const sim = (c.backtests || []).find(b => b.mode === 'simulate');
if (!sim) throw new Error('未解析到 simulate 回测');
console.log('mode=', sim.mode, 'total_return_pct=', sim.total_return_pct,
  'sharpe=', sim.sharpe, 'curve_pts=', (sim.equity_curve||[]).length,
  'metrics?', !!sim.metrics, 'closed=', sim.n_closed_trades);
if (!(sim.equity_curve.length >= 2)) throw new Error('equity_curve 缺失');
console.log('OK A2 解析通过');
PY
```
Expected: 打印字段 + `OK A2 解析通过`。

## Task A3: index.html 渲染 M2（指标卡 + SVG 净值曲线 + 成交表）

**Files:**
- Modify: `frontend/index.html`（新增 `btEquitySVG()`；改 `renderBacktest()`；加 `.bt-eqchart` CSS；改 script 版本号）

- [ ] **Step 1: 加 `.bt-eqchart` CSS**

在 `.bt-genstatus{...}`（第 597 行）之后追加一行：
```css
.bt-eqchart{margin:10px 0 4px} .bt-eqchart svg{width:100%;height:auto;display:block}
```

- [ ] **Step 2: 新增 `btEquitySVG()`，紧接 `renderBacktest` 之前插入**

在 `/* 回测 / 记忆环视图 ... */`（第 1472 行注释）之前插入：

```javascript
/* M2 净值曲线 手绘 SVG（仿 mtChartSVG）：组合净值实线 + 基准虚线 */
function btEquitySVG(curve){
  const pts=(curve||[]).filter(p=>p&&p.equity!=null);
  if(pts.length<2)return '<div class="bt-dim" style="padding:10px 0">净值点不足，无法绘制曲线</div>';
  const W=980,H=300,L=58,R=18,T=18,B=30;
  const eqs=pts.map(p=>p.equity);
  const bvals=pts.map(p=>p.benchmark_equity).filter(v=>v!=null);
  const hasB=bvals.length>=2;
  let lo=Math.min(...eqs,...(hasB?bvals:[])),hi=Math.max(...eqs,...(hasB?bvals:[]));
  if(lo===hi){lo-=Math.max(1,lo*0.01);hi+=Math.max(1,hi*0.01);}
  const pad=(hi-lo)*0.12;lo-=pad;hi+=pad;
  const x=k=>L+(W-L-R)*(k/(pts.length-1));
  const y=v=>+(T+(H-T-B)*(1-(v-lo)/(hi-lo))).toFixed(1);
  const GRID='rgba(20,50,44,.14)',FAINT='#8c968f',EQC='#cd5638',BMC='#bd7a0e';
  const ticks=[hi-pad,(hi+lo)/2,lo+pad];
  const axis=`<line x1="${L}" y1="${T}" x2="${L}" y2="${H-B}" stroke="${GRID}"/>`+
    `<line x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}" stroke="${GRID}"/>`+
    ticks.map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="${GRID}" opacity=".6"/>`+
      `<text x="${L-8}" y="${y(v)+3}" text-anchor="end" font-size="9" fill="${FAINT}" font-family="monospace">${(v/10000).toFixed(1)}w</text>`).join('');
  const eqPoly=`<polyline points="${pts.map((p,k)=>`${x(k).toFixed(1)},${y(p.equity)}`).join(' ')}" fill="none" stroke="${EQC}" stroke-width="2.5"/>`;
  const bmPoly=hasB?`<polyline points="${pts.map((p,k)=>p.benchmark_equity!=null?`${x(k).toFixed(1)},${y(p.benchmark_equity)}`:'').filter(Boolean).join(' ')}" fill="none" stroke="${BMC}" stroke-width="1.6" stroke-dasharray="5 3"/>`:'';
  const n=pts.length;
  const dateL=[0,Math.floor(n/2),n-1].map(k=>`<text x="${x(k).toFixed(1)}" y="${H-B+16}" text-anchor="middle" font-size="9" fill="${FAINT}" font-family="monospace">${esc(pts[k].date.slice(5))}</text>`).join('');
  const leg=`<text x="${L+4}" y="${T+9}" font-size="10" fill="${EQC}" font-family="monospace">— 组合净值</text>`+
    (hasB?`<text x="${L+98}" y="${T+9}" font-size="10" fill="${BMC}" font-family="monospace">- - 基准</text>`:'');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="M2 净值曲线">${axis}${bmPoly}${eqPoly}${dateL}${leg}</svg>`;
}
```

- [ ] **Step 3: `renderBacktest()` 顶部加 M2 分支**

在 `renderBacktest(bts,idx,ticker)` 里，`const runsel=...` 这一行**之后**、`const hr=b.headline_return_pct;` 这一行**之前**，插入 M2 分支（命中即提前 return，不影响下方 M1 逻辑）：

```javascript
  const isSim = b.mode==='simulate' || (b.equity_curve && b.equity_curve.length);
  if(isSim){
    const m=b.metrics||{};
    const pc=v=>v==null?'—':((v>=0?'+':'')+v+'%');
    const tr=b.total_return_pct, mdd=b.max_drawdown_pct, wr=b.win_rate_pct, vb=b.vs_benchmark_pct;
    const subS=`<div class="eq-subhead report"><div class="eq-shrow"><span class="eq-kind">M2 前向纸面交易 · 净值曲线</span>${badge}</div>
       <div class="eq-rmeta">${esc(b.period_from)} → ${esc(b.period_to)} · 初始 ¥${b.initial_cash==null?'—':b.initial_cash.toLocaleString()} · 平仓 ${b.n_closed_trades==null?0:b.n_closed_trades} 笔 ${runsel}</div></div>`;
    const cards=`<div class="instruments" style="margin:12px 0">`+
      inst('总收益', pc(tr), '相对初始资金', tr!=null&&tr>=0)+
      inst('Sharpe', m.sharpe==null?'—':m.sharpe, '年化', false)+
      inst('最大回撤', mdd==null?'—':('-'+Math.abs(mdd)+'%'), '峰值到谷', false)+
      inst('胜率', wr==null?'—':wr+'%', `${b.n_closed_trades||0} 笔平仓`, false)+
      inst('超额', pc(vb), 'vs 基准', vb!=null&&vb>=0)+
      `</div>`;
    const chart=`<div class="bt-sech">净值曲线 · Tushare 真实 qfq 逐日 mark-to-market</div>
       <div class="bt-eqchart">${btEquitySVG(b.equity_curve)}</div>`;
    const rows=(b.trades||[]).map(t=>{
      const ret=t.holding_return_pct;
      const rc=ret==null?'':`color:${ret<0?'#c2362f':'#2f8f5b'}`;
      return `<tr><td>${esc(t.entry_date||'')}</td><td>${esc(t.date||'')}</td><td class="bt-num">${t.qty==null?'—':t.qty}</td><td class="bt-num">${t.avg_cost==null?'—':t.avg_cost}</td><td class="bt-num">${t.price==null?'—':t.price}</td><td class="bt-num"><b style="${rc}">${ret==null?'—':(ret>=0?'+':'')+ret+'%'}</b></td><td class="bt-num">${t.realized_pnl==null?'—':t.realized_pnl}</td><td>${t.holding_days==null?'—':t.holding_days+'d'}</td></tr>`;
    }).join('');
    const tableS=`<div class="bt-sech">round-trip 成交</div>
       <table class="bt-table"><thead><tr><th>买入</th><th>卖出</th><th>股数</th><th>成本</th><th>卖价</th><th>持有收益</th><th>实现盈亏</th><th>持有</th></tr></thead><tbody>${rows}</tbody></table>`;
    return subS+genbar+cards+chart+tableS;
  }
```

> 注：M2 分支用到的 `badge` / `runsel` / `genbar` 都在该函数前面已定义；`inst()` / `esc()` / `EQ_VCLS` 为全局工具。M1（reflect）报告的 `mode` 非 simulate 且无 equity_curve → 不进此分支，保持原渲染。

- [ ] **Step 4: bump 缓存版本号**

把第 741 行 `<script src="kb-parse.js?v=bt1"></script>` 改为 `?v=bt2`（A2 改了 kb-parse.js，必须破缓存）。

- [ ] **Step 5: 起服务，curl 确认报告被动态 manifest 收录 + 页面可达**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
./frontend/serve.sh 8000 >/tmp/serve-bt.log 2>&1 &
sleep 2
curl -s "http://127.0.0.1:8000/manifest.json" | python3 -c "import sys,json; f=json.load(sys.stdin)['files']; print('simulate report in manifest:', any('raw/analysis/backtests' in x for x in f))"
curl -s -o /dev/null -w "kb-parse.js?v=bt2 -> %{http_code}\n" "http://127.0.0.1:8000/frontend/kb-parse.js?v=bt2"
curl -s -o /dev/null -w "loopback-only check (hostname) -> %{http_code}\n" "http://$(hostname):8000/frontend/" || echo "  (非 127.0.0.1 不可达 = 预期，本地 only)"
```
Expected: `simulate report in manifest: True`；`kb-parse.js?v=bt2 -> 200`；hostname 形式连接失败/拒绝（本地 only 不变量）。

- [ ] **Step 6: 浏览器人工确认（用户视觉验收）**

在已打开的 `http://127.0.0.1:8000/frontend/` → 个股分析 → 601899 → 点「回测 / 记忆环」→ 运行选择器选 `mode: simulate` 那条 → 确认：5 张指标卡、净值曲线 SVG、round-trip 成交表都渲染。**这一步只能人工看（无浏览器截图能力）**；A1-A5 的数据/解析/服务链路已被前述步骤逐层验证。完成后停掉测试服务：`kill %1 2>/dev/null || true`。

## Task A4: 收尾 Part A（停服务 + 可选提交）

- [ ] **Step 1: 确认无残留测试服务**

Run: `lsof -ti:8000 | xargs kill -9 2>/dev/null || true`

- [ ] **Step 2:（可选，仅在用户要求 checkpoint 提交时）提交 Part A**

```bash
git add .claude/skills/backtest-analysis/scripts/run_backtest.py frontend/kb-parse.js frontend/index.html
git commit -m "feat(backtest): wire M2 forward-sim equity curve into frontend backtest unit

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Task A5（可选）: 浏览器一键生成 M2

> 仅在用户想要「浏览器一键跑 M2」时做。核心 Part A（A1-A3）已让 M2 报告可被前端渲染，生成可由 CLI（A1 Step 3 的命令）完成。本任务把生成也搬进浏览器。

**Files:**
- Modify: `frontend/serve.sh`（`run_export` + `do_POST`）
- Modify: `frontend/index.html`（`genBacktest` 传 mode + 加一个「净值模拟」按钮）

- [ ] **Step 1: serve.sh 的 `run_export` 支持 mode**

把 `run_export(ticker)` 改为 `run_export(ticker, mode)`，命令按 mode 分支：
```python
def run_export(ticker, mode):
    if mode == "simulate":
        cmd = [str(VENV), str(SCRIPT), "--ticker", ticker, "--mode", "simulate",
               "--no-reflect", "--ta-root", str(TA_ROOT)]
    else:
        cmd = [str(VENV), str(SCRIPT), "--ticker", ticker, "--mode", "export", "--ta-root", str(TA_ROOT)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=240, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": f"{mode} 超时（>240s）"}
    lines = (p.stdout or "").splitlines()
    okline = next((l for l in lines if l.startswith("OK ")), "")
    report = next((l.split("report :", 1)[1].strip() for l in lines if "report :" in l), "")
    tail = "\n".join(lines[-6:])
    ok = p.returncode == 0 and bool(okline)
    return {"ok": ok, "message": okline or (tail or f"{mode} 失败"), "report": report,
            "tail": tail, "code": p.returncode}
```

- [ ] **Step 2: do_POST 解析 + 校验 mode**

在 `do_POST` 里 `ticker` 校验通过后，替换 `return self._json(run_export(ticker))` 为：
```python
            mode = str(data.get("mode", "export")).strip()
            if mode not in ("export", "simulate"):
                return self._json({"ok": False, "message": "mode 非法（export|simulate）"}, 400)
            return self._json(run_export(ticker, mode))
```

- [ ] **Step 3: 前端 genBacktest 传 mode + 加按钮**

`genBacktest(ticker,btn)` 签名改 `genBacktest(ticker,btn,mode)`，fetch body 改 `JSON.stringify({ticker, mode: mode||'export'})`。在 `renderBacktest` 的 `genbar` 里，M1 按钮后加一个 M2 按钮：
```javascript
  const genbar=`<div class="bt-genbar"><button class="bt-gen" data-ticker="${esc(ticker)}" data-mode="export">⟳ ${bts&&bts.length?'刷新 M1 反思':'生成 M1 反思'}</button><button class="bt-gen" data-ticker="${esc(ticker)}" data-mode="simulate" style="background:var(--c-sector)">📈 跑 M2 净值模拟</button><span class="bt-genstatus"></span></div>`;
```
并在 `paintEqBody()` 的 backtest 分支里，把 `.bt-gen` 绑定改为遍历两个按钮、读 `data-mode`：
```javascript
    document.querySelectorAll('#eq-body .bt-gen').forEach(gb=>
      gb.addEventListener('click',()=>genBacktest(c.ticker,gb,gb.dataset.mode)));
```

- [ ] **Step 4: 验证一键 M2（curl 直打端点）**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
./frontend/serve.sh 8000 >/tmp/serve-bt.log 2>&1 & sleep 2
curl -s -X POST "http://127.0.0.1:8000/api/backtest" -H 'Content-Type: application/json' -d '{"ticker":"601899","mode":"simulate"}' | python3 -m json.tool
curl -s -X POST "http://127.0.0.1:8000/api/backtest" -H 'Content-Type: application/json' -d '{"ticker":"601899","mode":"evil"}' -w "\n-> %{http_code}\n" -o /dev/null
kill %1 2>/dev/null || true
```
Expected: 第一发 `{"ok": true, ... "message": "OK mode=simulate ...", "report": ".../601899-<runid>.md"}`；第二发 mode=evil → HTTP 400。

---

# Part B — wiki/ontology 编译

## Task B1: 注册 ontology `Backtest` 节点 + 边

**Files:**
- Modify: `Knowledge_Wiki/ontology/schema.yaml`

- [ ] **Step 1: nodes 段加 Backtest**

在 `Macro: { keys: [slug] }` 之后（媒体源注释之前）加：
```yaml
  Backtest:   { keys: [id] }                # 回测/记忆环运行（1 run = 1 节点；绝不给每笔成交建节点）
```

- [ ] **Step 2: edges 段加 COVERS / EVALUATES**

在金融层 edges 末尾（`EXPOSED_TO` 之后）加：
```yaml
  COVERS:        { from: Backtest,   to: [Company] }       # 回测覆盖的标的
  EVALUATES:     { from: Backtest,   to: [Thesis] }        # 回测验证的论点（可选）
```

- [ ] **Step 3: 确认 graph_append 仍 validate 通过（schema 改动不破坏回放）**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
python3 Knowledge_Wiki/scripts/graph_append.py validate
```
Expected: `OK: 全部引用完整性校验通过`（graph_append 不强校 schema.yaml，此步确认现有图谱未受影响）。

## Task B2: finance-ingest 新增 `kind=backtest` 编译场景

**Files:**
- Modify: `Knowledge_Wiki/.claude/skills/finance-ingest/SKILL.md`

- [ ] **Step 1: 读现有 SKILL.md 找场景列表锚点**

Run: `sed -n '1,80p' Knowledge_Wiki/.claude/skills/finance-ingest/SKILL.md` —— 定位"场景"枚举（现有如 sector-analysis 场景 E、stock-analysis Gap A 等）的插入点。

- [ ] **Step 2: 追加 `kind=backtest` 场景小节**

在场景列表后追加（措辞与现有场景对齐；这是**编译契约说明**，实际编译由两步 CoT 执行）：

```markdown
### 场景 F：kind=backtest（回测复盘 → wiki/reports）

**输入**：`raw/analysis/backtests/cn/<ticker>-<runid>.md`（`type: backtest-report`，frontmatter 指标原子 + 正文 `<!-- backtest-json -->` json 块）+ 同 run 机器产物 `raw/data/backtests/cn/<ticker>-<runid>/{trades.json|jsonl, lessons.json?, equity_curve.json?, config.json}`。

**输出**：`wiki/reports/<as_of>-<ticker>-backtest.md`（`type: report`，6 必填字段 + `sources[]`）。

**两步 CoT**：
- Step 1（analyze）：核对 raw 报告里的指标/收益**全部能在机器产物里溯源**（headline_return_pct、total_return、sharpe…），列出哪些是事实（Tushare 算价）、哪些是模型判断（reflect 教训）。**禁止引入任何机器产物里没有的数字。**
- Step 2（generate）：写 wiki/reports 页。frontmatter 指标原子**逐个 copy 自机器产物**；正文：① 一句话结论（决策→真实收益）；② 决策×horizon 收益表（事实层）；③ 5 桶教训摘要置于 `## 来自模型的复盘教训（非事实）` 段、每条带 `> 来源 [[...]]` 链接（仅 reflect 模式有）；④ `[[companies/<ticker>]]` 反链。

**收尾**：
1. `python3 scripts/build_index.py --validate` 必须过。
2. 写 ontology：`graph_append.py create --type Backtest ...` + `relate --rel COVERS --to <Company 节点 id>`（见 backtest-analysis SKILL References）。

**不做**：不给每笔成交/每个净值点建 ontology 节点；不改 raw/；不臆造任何未在机器产物出现的数值。
```

- [ ] **Step 3: 确认 SKILL.md 仍是合法 markdown（无校验脚本，目视）**

Run: `sed -n '/场景 F/,/不做/p' Knowledge_Wiki/.claude/skills/finance-ingest/SKILL.md`
Expected: 完整打印新场景小节。

## Task B3: frontend-kb-binding §2d 回测绑定契约

**Files:**
- Modify: `docs/kb/frontend-kb-binding.md`（在 §2b 个股契约之后、§3 之前插入 §2d）

- [ ] **Step 1: 插入 §2d**

```markdown
## 2d. 回测 / 记忆环绑定契约（type: backtest-report → wiki report）

> **状态：前端「回测 / 记忆环」单元已接入（M1 反思 2026-06-16；M2 净值曲线 2026-06-16）。** 链路 `raw/analysis/backtests/cn/<ticker>-<runid>.md` → `kb-parse.js`（backtest-report 分支）→ `companies[].backtests[]` → `index.html renderBacktest()`。

### 2d.1 raw 层（前端直接 live-parse 的源）

`type: backtest-report`，flat frontmatter + 正文 `<!-- backtest-json -->` ```json``` 块（**数组进不了 mini-YAML，故进 json 块**）：

| mode | frontmatter 原子 | json 块 |
|---|---|---|
| `reflect`（M1） | `headline_return_pct` / `n_reflected` / `n_non_evaluable` / `horizons` / `snapshot_date` | `{trades[], lessons[]}` |
| `simulate`（M2） | `total_return_pct` / `sharpe` / `max_drawdown_pct` / `win_rate_pct` / `vs_benchmark_pct` / `n_closed_trades` / `period_from` / `period_to` / `initial_cash` | `{mode, metrics{}, equity_curve[], trades[]}` |

公共：`type` / `ticker` / `mode` / `run_status`(ok|partial|sample) / `as_of` / `sources[]`。前端按 `mode==='simulate' || equity_curve.length` 分流到 M2 渲染（指标卡 + SVG 净值曲线 + round-trip 成交表），否则 M1（反思表 + 5 桶教训卡）。**收益/净值只用 Tushare 真实 qfq close，缺失 `non_evaluable`/`null`，禁止臆造。**

### 2d.2 wiki 层（finance-ingest 编译产物）

`wiki/reports/<as_of>-<ticker>-backtest.md`（`type: report`）= raw 回测报告的蒸馏复盘页，供 Agent/Obsidian 阅读 + 喂 ontology。指标逐个溯源自机器产物，模型教训进「（非事实）」段。（当前前端无 `report` 类型渲染器 → 该页不在前端面板出现，其前端可见产出是**星图 Backtest 节点**。）

### 2d.3 ontology

1 run = 1 个 `Backtest` 节点（`graph_append.py create --type Backtest`）+ `COVERS → Company`（+ 可选 `EVALUATES → Thesis`）。**绝不给每笔成交/每个净值点建节点。** 星图节点标签显示「回测 ±x%」。
```

- [ ] **Step 2: 目视确认**

Run: `sed -n '/## 2d\./,/## 3\./p' docs/kb/frontend-kb-binding.md`
Expected: 完整打印 §2d。

## Task B4: 实跑编译 601899 回测复盘 wiki 页（finance-ingest 两步 CoT）

> 这是**唯一一步 LLM 编译**（执行者即 agent，按 B2 场景 F 跑 finance-ingest）。验收靠 `--validate` + 人工核对「指标==机器产物、无臆造」。

**Files:**
- Create: `Knowledge_Wiki/wiki/reports/2026-06-15-601899-backtest.md`

- [ ] **Step 1: 读 601899 M1 机器产物核对真实指标**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
cat Knowledge_Wiki/raw/data/backtests/cn/601899-20260616T060708/config.json
python3 -c "import json;print([(t.get('snapshot_date'),t.get('horizon'),t.get('signed_return_pct'),t.get('reflected')) for t in json.load(open('Knowledge_Wiki/raw/data/backtests/cn/601899-20260616T060708/trades.json'))])"
```
确认 headline = +13.0325%、horizon=3、1 笔 reflected。

- [ ] **Step 2: 写 wiki/reports 页（严格按下方模板；数字逐个来自 Step 1）**

```markdown
---
title: "601899 紫金矿业 · M1 回测复盘（+13.03%）"
type: report
domain: finance
created: 2026-06-16
updated: 2026-06-16
summary: "601899 于 2026-06-10 BUY，持 3 交易日至 06-15 实现 +13.03%（Tushare qfq）；reflect 写入 5 桶记忆，功能 B 次日召回。"
ticker: "601899"
backtest_mode: reflect
headline_return_pct: 13.03
horizons: "3"
n_reflected: 1
sources:
  - raw/analysis/backtests/cn/601899-20260616T060708.md
  - raw/data/backtests/cn/601899-20260616T060708/trades.json
  - raw/data/backtests/cn/601899-20260616T060708/lessons.json
---

# 601899 紫金矿业 · M1 回测复盘

2026-06-10 的 **BUY** 决策，持有 3 个交易日至 2026-06-15，入场 ¥27.70 → 出场 ¥31.31，真实收益 **+13.03%**（Tushare 前复权 close）。该笔已经引擎原生 `reflect_and_remember` 写入 5 个 per-ticker 记忆桶，[[companies/601899]] 次日同票分析（功能 B，depth≥2）自动召回。

## 决策 × 收益（事实层）

| snapshot | 决策 | horizon | 入场 | 评估 | 真实收益 | 状态 |
|---|---|---|---|---|---|---|
| 2026-06-10 | 买入 | 3 交易日 | ¥27.70 | ¥31.31 | +13.03% | 已反思 |

> 收益仅用 Tushare 真实 qfq close；其余 horizon（5/20）因评估日在未来标 non_evaluable，未杜撰。

## 来自模型的复盘教训（非事实）

5 桶（多头/空头/交易员/投资裁判/风险经理）各写入一条 reflect 教训，核心均为「极度超卖（RSI6≈24.9）下精准把握技术反弹」。完整文本见 sources 的 `lessons.json`。

> ⚠ 教训为引擎 quick-LLM 生成的事后复盘，非客观事实。
> 来源 [[companies/601899]] · raw/analysis/backtests/cn/601899-20260616T060708.md
```

- [ ] **Step 3: 校验 frontmatter 合规**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
python3 Knowledge_Wiki/scripts/build_index.py --validate
```
Expected: 校验通过（新页 6 必填字段 + sources[] 齐全；sources 非媒体源 → 不触发「来自媒体源」段要求）。若报缺字段，按报错补齐后重跑。

## Task B5: ontology 写入 + 星图标签

**Files:**
- Append（经脚本）: `Knowledge_Wiki/ontology/graph.jsonl`
- Modify: `frontend/kb-parse.js`（星图节点标签）

- [ ] **Step 1: 写 Backtest 节点 + COVERS 边**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
python3 Knowledge_Wiki/scripts/graph_append.py create --type Backtest \
  --id bt_601899_20260616 \
  --props '{"ticker":"601899","mode":"reflect","headline_return_pct":13.03,"horizons":"3","as_of":"2026-06-15","report":"wiki/reports/2026-06-15-601899-backtest.md"}'
python3 Knowledge_Wiki/scripts/graph_append.py relate \
  --from bt_601899_20260616 --rel COVERS --to comp_601899
```
Expected: 两行 `[append] create Backtest:...` / `[append] relate ... -COVERS->`。（`comp_601899` 已存在于图谱。）

- [ ] **Step 2: validate + stats**

Run:
```bash
python3 Knowledge_Wiki/scripts/graph_append.py validate
python3 Knowledge_Wiki/scripts/graph_append.py stats
```
Expected: validate `OK`；stats 出现 `Backtest: 1` 与 `COVERS: 1`。

- [ ] **Step 3: 星图标签规则（让 Backtest 节点显示「回测 ±x%」而非裸 id）**

在 `frontend/kb-parse.js` 的星图节点循环里（`Object.keys(gnodes).forEach`），在 `else if (n.etype === 'MediaSource') ...` 之后加：
```javascript
      else if (n.etype === 'Backtest') label = '回测 ' + (n.props.headline_return_pct != null ? (n.props.headline_return_pct >= 0 ? '+' : '') + n.props.headline_return_pct + '%' : (n.props.ticker || nid));
```
（颜色：`TYPE_COLOR` 无 Backtest → 自动落 `company` 金色，无需改色。）

- [ ] **Step 4: node harness 确认星图含 Backtest 节点 + COVERS 边**

Run:
```bash
cd /Users/zhangsheng/code/OpenClaw-Task/Finance_Agent
node - <<'PY'
const fs=require('fs');
const {kbParse}=require('./frontend/kb-parse.js');
const files={'ontology/graph.jsonl':fs.readFileSync('Knowledge_Wiki/ontology/graph.jsonl','utf8')};
const kb=kbParse(files);
const bt=kb.graph.nodes.find(n=>/回测/.test(n.label));
const cov=kb.graph.edges.find(e=>e.rel==='COVERS');
console.log('backtest node label=', bt&&bt.label, '| COVERS edge=', cov&&(cov.from+'->'+cov.to));
if(!bt||!cov)throw new Error('星图缺 Backtest 节点或 COVERS 边');
console.log('OK B5 星图接入');
PY
```
Expected: 打印 `回测 +13.03%` 标签 + `bt_601899_20260616->comp_601899` + `OK B5 星图接入`。

> 若前面没做 A3 的 `?v=bt2` bump（即只跑 Part B），此处仍需把 `index.html` 的 `kb-parse.js?v=bt1` bump 一位（如 `?v=bt3`）以破缓存——B5 改了 kb-parse.js。

## Task B6: 收尾 Part B（可选提交）

- [ ] **Step 1:（可选，仅在用户要求 checkpoint 提交时）提交 Part B**

注意 `Knowledge_Wiki/` 是独立 git repo（`Knowledge_Wiki/.git`）；ontology/graph.jsonl + wiki/reports 在该子库内提交，schema/binding/skill 在外层库。分别：
```bash
# 外层库
git add Knowledge_Wiki/.claude/skills/finance-ingest/SKILL.md docs/kb/frontend-kb-binding.md frontend/kb-parse.js frontend/index.html
git commit -m "feat(backtest): finance-ingest kind=backtest scenario + binding §2d + ontology Backtest node label

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
# 子库（Knowledge_Wiki）：schema + wiki/reports + graph.jsonl
git -C Knowledge_Wiki add ontology/schema.yaml ontology/graph.jsonl wiki/reports/2026-06-15-601899-backtest.md
git -C Knowledge_Wiki commit -m "feat(ontology): register Backtest node/edges; compile 601899 backtest report + graph node"
```

---

# 跨 Part 收尾（文档同步）

## Task C1: 同步 SKILL.md 与设计文档状态

**Files:**
- Modify: `.claude/skills/backtest-analysis/SKILL.md`
- Modify: `docs/tradingagents-cn/backtest/backtest-feature-design.md`

- [ ] **Step 1: SKILL.md「不做清单」改 M2 前端 / wiki·ontology 为已落**

把第 115 行 `❌ M2 前向组合模拟前端...前端面板待接` 改为：
```markdown
- ✅ M2 前向组合模拟前端（单票净值曲线 + 指标卡 + round-trip 成交表已接；多票组合视图后续）
```
把第 117 行 `❌ wiki/reports 编译 + ontology Backtest 节点...` 改为：
```markdown
- ✅ wiki/reports 编译（finance-ingest 场景 F）+ ontology Backtest 节点（COVERS 边）已落；首例 601899
```

- [ ] **Step 2: SKILL.md Scope 段补 M2 + export·simulate 两模式落报告**

第 28 行末「**仍后续**：wiki/reports 编译 + ontology...」改为反映已落，并提一句 M2：simulate 单票也落 `backtest-report.md`（`mode: simulate`）渲染净值曲线。

- [ ] **Step 3: 设计文档抬头状态块更新**

在 `backtest-feature-design.md` 抬头（第 3-14 行状态块）把 M2「前端面板待接」改为「✅ M2 单票净值曲线前端已接（2026-06-16）」，并把「仍待实现」收敛为：M2 多票组合视图、raw-intake 溯源 handoff、M3 历史重跑。

- [ ] **Step 4: 校验文档无破坏**

Run: `python3 Knowledge_Wiki/scripts/build_index.py --validate`
Expected: 通过（文档改动不涉及 wiki 校验项，但确认无回归）。

---

## Self-Review（计划自检 — 实现前已执行）

**1. Spec coverage（用户诉求逐项对照）**
- 「M2 净值曲线前端」→ Task A1（runner 落报告）+ A2（解析）+ A3（指标卡/SVG 曲线/成交表）+ A5（可选一键）。✅ 覆盖。
- 「wiki/ontology 编译」→ B1（schema）+ B2（finance-ingest 场景）+ B3（绑定契约）+ B4（实跑编译 wiki 页）+ B5（ontology 节点 + 星图）。✅ 覆盖。
- 「实现前先自我评审」→ 本节即评审；且每个 Part 末尾有独立验证闸。✅。

**2. Placeholder scan**：无 "TODO/待填"；每个改代码的步骤都给了完整代码块（`_write_simulate_report_md` 全量、`btEquitySVG` 全量、kb-parse 解构、renderBacktest M2 分支、schema/绑定/wiki 页全文、graph_append 具体命令）。✅。

**3. Type/命名一致性核对**：
- runner json 块键 `{mode, metrics, equity_curve, trades}` ↔ `parseBacktestJson` 取的键 ↔ `renderBacktest` 用的 `b.equity_curve`/`b.metrics`/`b.trades`/`b.mode`。✅ 一致。
- frontmatter 原子名 `total_return_pct`/`sharpe`/`max_drawdown_pct`/`win_rate_pct`/`vs_benchmark_pct`/`n_closed_trades`/`period_from`/`period_to`/`initial_cash` ↔ kb-parse `num(fm.xxx)` ↔ renderBacktest `b.xxx`。✅ 三处逐字对齐。
- 成交表字段用 `closed_trades` 的真实键（`entry_date`/`date`/`qty`/`avg_cost`/`price`/`holding_return_pct`/`realized_pnl`/`holding_days`，见 run_backtest.py:514-517）。✅。
- ontology：`comp_601899` 用图谱**已存在**的 id（已核对 graph.jsonl 末行）；`Backtest`/`COVERS` 与 B1 schema 注册一致。✅。
- 缓存版本：A2 改 kb-parse.js → A3 Step4 bump `?v=bt2`；若只跑 Part B 改 kb-parse.js → B5 Step3 提示 bump。✅ 不会漏破缓存。

**4. 不变量合规**：收益只用 Tushare qfq、缺失 null（A1/B4 均强调）；wiki 经 finance-ingest 两步 CoT（B2/B4）不直写；ontology 只经 graph_append、1 run 1 节点不给成交建节点（B1/B5）；本地 only（A3 Step5 验证 hostname 不可达）；DashScope 不碰（M2 走 `--no-reflect` 纯算价，零 LLM）；raw/ 不改。✅。

**5. 已知边界（非缺陷，已在计划标注）**：M2 仅单票挂公司页（多票组合视图后续）；equity_curve 当前日级短曲线，未下采样（超长后续）；wiki/reports 无前端渲染器（前端可见产出是星图节点）；B4 是唯一 LLM 步、靠 `--validate` + 人工核对把关。

自检发现并已在正文修正：A3 M2 分支提前 return，确保 M1（reflect）路径零回归；B5 补了「只跑 Part B 时也要 bump 版本号」提示。
