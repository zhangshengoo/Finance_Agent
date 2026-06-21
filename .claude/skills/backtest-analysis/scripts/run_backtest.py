#!/usr/bin/env python3
"""backtest-analysis Skill 的 bundled 运行器 —— 回测 / 交易模拟 + 记忆功能 A（写半边）。

两种模式：
- **M1 `--mode reflect`**（单决策反思）：对已有 snapshot 逐决策算 Tushare 真实前向收益，调原生
  `reflect_and_remember` 写 per-ticker 记忆桶（= 功能 B 读的同一批桶）。不重跑引擎。
- **M2 `--mode simulate`**（前向组合模拟）：按决策序列跑组合（现金/持仓/A 股 T+1），每交易日
  按真实收盘 mark-to-market 出净值曲线；每次平仓用**真实持有期收益**调 reflect 写教训（功能 A）。
  决策序列来源：snapshot glob（生产，向前累积）或 `--decisions <fixture.json>`（验证）。

必须用 TradingAgents-CN 自带 venv（Py3.10）：
  <ta-root>/.venv/bin/python run_backtest.py --ticker 600519 --mode reflect --horizons 5,20

设计/坑位见 docs/backtest-feature-design.md / docs/backtest-feature-framework.html。关键约束：
- **DashScope 仅做 Embedding**；reflect 的 quick-LLM 走 anthropic/claude-max-proxy:5678，计费独立。
- 记忆配置必须与功能 B 逐项一致（persist dir / namespace=ticker / text-embedding-v4），否则环断。
- reflect 前**探活 DashScope**：零向量=欠费/缺 key，写入永远召不回。
- **幂等**：ledger 记 (ticker,date,horizon|trade) 防重复写。
- 嵌入超长（>8192 token）走 memory.py 的分段归一化均值池化（不丢章节信息，写读一致）。
"""
import argparse
import asyncio
import glob
import json
import math
import os
import sys
import time
import traceback
from datetime import date as _date, datetime, timedelta

DEFAULT_TA_ROOT = "/Users/zhangsheng/code/OpenClaw-Task/Finance_Agent/TradingAgents-CN"
ACTION_EN = {"买入": "BUY", "卖出": "SELL", "持有": "HOLD"}
FALLBACK_FINGERPRINT = ("持有", 0.5, 0.5)  # signal 解析失败回退指纹
LOT = 100  # A 股一手 = 100 股


# ----------------------------------------------------------------------------- env
def _setup_env(ta_root, persist_dir):
    """无头 env：必须在 import tradingagents 之前。镜像 run_stock_analysis.py 的 preamble。"""
    os.environ["MONGODB_ENABLED"] = "false"
    os.environ["REDIS_ENABLED"] = "false"
    os.environ["USE_MONGODB_STORAGE"] = "false"
    os.makedirs(persist_dir, exist_ok=True)
    os.environ["TRADINGAGENTS_MEMORY_PERSIST_DIR"] = persist_dir
    os.chdir(ta_root)
    sys.path.insert(0, ta_root)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ta_root, ".env"), override=False)
    except Exception:
        pass


# ----------------------------------------------------------------------------- 价格层
def _fetch_prices(ticker, start_date, end_date):
    """同步包装引擎原生 Tushare provider；返回升序 [(YYYY-MM-DD, close)]（仅交易日，qfq）或 None。"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    prov = get_tushare_provider()
    if prov is None or not prov.is_available():
        return None
    df = asyncio.run(prov.get_historical_data(ticker, start_date, end_date, period="daily"))
    if df is None or len(df) == 0 or "close" not in getattr(df, "columns", []):
        return None
    dates = df["date"] if "date" in df.columns else df.index
    out = []
    for d, c in zip(list(dates), list(df["close"])):
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        try:
            out.append((ds, float(c)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0])
    return out or None


def _realized(prices, decision_date, horizon):
    """entry = 首个 >= decision_date 的交易日 close；exit = entry 后第 horizon 个交易日 close。"""
    idx = next((i for i, (d, _) in enumerate(prices) if d >= decision_date), None)
    if idx is None:
        return None
    j = idx + horizon
    if j >= len(prices):
        return None
    return prices[idx][0], prices[idx][1], prices[j][0], prices[j][1]


def _signed_return(action_cn, raw_ret):
    """按动作把价格涨跌转成"跟随该决策的收益"：买入→+涨幅；卖出→-涨幅。"""
    if action_cn == "买入":
        return raw_ret
    if action_cn == "卖出":
        return -raw_ret
    return 0.0


def _returns_str(action_cn, signed, raw_ret, h_label, ed, ec, xd, xc):
    en = ACTION_EN.get(action_cn, action_cn)
    return (
        f"{signed * 100:+.2f}% over {h_label} "
        f"(decision={en}, entry {ed} @{ec:.2f} -> exit {xd} @{xc:.2f}, "
        f"underlying price move {raw_ret * 100:+.2f}%). Positive return = correct decision."
    )


# ----------------------------------------------------------------------------- curr_state
def _coerce(v):
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def _build_curr_state(snap):
    """snapshot JSON → reflect 需要的 8 字段扁平 curr_state（key 改名 + None→''）。"""
    rep = snap.get("reports", {}) or {}
    deb = snap.get("debates", {}) or {}
    inv = deb.get("investment", {}) or {}
    rsk = deb.get("risk", {}) or {}
    return {
        "market_report": _coerce(rep.get("market")),
        "sentiment_report": _coerce(rep.get("sentiment")),
        "news_report": _coerce(rep.get("news")),
        "fundamentals_report": _coerce(rep.get("fundamentals")),
        "trader_investment_plan": _coerce(rep.get("trader_investment_plan")),
        "investment_debate_state": {
            "bull_history": _coerce(inv.get("bull_history")),
            "bear_history": _coerce(inv.get("bear_history")),
            "judge_decision": _coerce(inv.get("judge_decision")),
        },
        "risk_debate_state": {"judge_decision": _coerce(rsk.get("judge_decision"))},
    }


# ----------------------------------------------------------------------------- ledger
def _ledger_path(persist_dir):
    return os.path.join(persist_dir, "reflect-ledger.jsonl")


def _load_ledger(persist_dir):
    done = set()
    p = _ledger_path(persist_dir)
    if not os.path.exists(p):
        return done
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                done.add((r.get("ticker"), r.get("snapshot_date"), str(r.get("horizon"))))
            except Exception:
                continue
    return done


def _append_ledger(persist_dir, ticker, date, horizon, returns_str):
    with open(_ledger_path(persist_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ticker": ticker, "snapshot_date": date, "horizon": str(horizon),
            "returns_losses": returns_str, "reflected_at": datetime.now().isoformat(timespec="seconds"),
        }, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------- graph / reflect
def _build_graph_and_probe(args, persist_dir):
    """建图（memory_enabled=True，namespace=ticker，dashscope v4）+ 探活 DashScope。返回 ta 或退出。"""
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except Exception as e:
        print(f"FAILED import tradingagents: {e!r}", file=sys.stderr)
        sys.exit(1)
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = args.provider
    config["backend_url"] = args.backend_url
    config["deep_think_llm"] = args.deep_model
    config["quick_think_llm"] = args.quick_model
    config["memory_enabled"] = True
    config["online_tools"] = True
    config["memory_namespace"] = args.ticker            # 桶名 *_memory__<ticker>（= 功能 B 读的）
    config["memory_llm_provider"] = args.memory_embed_provider   # dashscope（仅嵌入）
    config["memory_embedding_model"] = args.memory_embed_model   # text-embedding-v4
    try:
        ta = TradingAgentsGraph(selected_analysts=["market", "fundamentals"], debug=False, config=config)
    except Exception as e:
        print(f"FAILED 建图: {e!r}\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)
    try:
        probe = ta.bull_memory.get_embedding("回测连通性探活：通胀上行宜配置防御板块")
        if not probe or not any(abs(x) > 1e-9 for x in probe):
            print("FAILED DashScope 嵌入探活=零向量（欠费/缺 key？）——拒绝写垃圾记忆。", file=sys.stderr)
            sys.exit(2)
        print(f"  DashScope 探活 OK（{len(probe)} 维非零）")
    except Exception as e:
        print(f"FAILED DashScope 探活异常: {e!r}", file=sys.stderr)
        sys.exit(2)
    return ta


def _probe_dashscope(args):
    """独立探活 DashScope 嵌入（不建图、不污染桶）：零向量=欠费/缺 key，直接退出。"""
    from tradingagents.agents.utils.memory import FinancialSituationMemory
    # namespace 须生成合法 ChromaDB 集合名（字母数字始末，故不能用前后下划线的 __probe__）。
    cfg = {"memory_namespace": "probe0", "memory_llm_provider": args.memory_embed_provider,
           "memory_embedding_model": args.memory_embed_model}
    try:
        v = FinancialSituationMemory("bull_memory", cfg).get_embedding("回测连通性探活：通胀上行宜配置防御板块")
        if not v or not any(abs(x) > 1e-9 for x in v):
            print("FAILED DashScope 嵌入探活=零向量（欠费/缺 key？）——拒绝写垃圾记忆。", file=sys.stderr)
            sys.exit(2)
        print(f"  DashScope 探活 OK（{len(v)} 维非零）")
    except Exception as e:
        print(f"FAILED DashScope 探活异常: {e!r}", file=sys.stderr)
        sys.exit(2)


def _reflect(ta, snap, returns_str):
    """重建 curr_state 并调原生 reflect_and_remember（5×quick-LLM）。"""
    ta.curr_state = _build_curr_state(snap)
    ta.ticker = snap.get("metadata", {}).get("ticker")
    ta.reflect_and_remember(returns_str)


# ----------------------------------------------------------------------------- M1 reflect 模式
def _reflect_mode(args, persist_dir, out_dir, runid, snap_files):
    horizons = sorted({int(h) for h in args.horizons.split(",") if h.strip()})
    if not horizons:
        print("FAILED horizons 为空", file=sys.stderr)
        sys.exit(1)

    decisions = []
    for sf in snap_files:
        try:
            snap = json.load(open(sf, encoding="utf-8"))
        except Exception as e:
            print(f"  skip 读取失败 {os.path.basename(sf)}: {e!r}")
            continue
        if snap.get("status") != "complete":
            print(f"  skip status!=complete {os.path.basename(sf)}")
            continue
        date = (snap.get("metadata") or {}).get("date")
        if not date:
            continue
        decisions.append((date, snap))
    decisions.sort(key=lambda x: x[0])
    if not decisions:
        print("FAILED 无可用 snapshot（complete + date）", file=sys.stderr)
        sys.exit(1)

    prices = None
    if not args.force_return and not args.dry_run:
        dmin = min(d for d, _ in decisions)
        start = (datetime.strptime(dmin, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
        end = _date.today().isoformat()
        t_p = time.time()
        prices = _fetch_prices(args.ticker, start, end)
        if prices is None:
            print(f"  ⚠️ 价格取数失败/为空——无法算真实收益。可用 --force-return 验证 A 闭环。")
        else:
            print(f"  价格 {args.ticker}: {len(prices)} 交易日 [{prices[0][0]}~{prices[-1][0]}] {time.time()-t_p:.1f}s")

    ta = None
    if not args.dry_run and not args.no_reflect:
        ta = _build_graph_and_probe(args, persist_dir)

    done = set() if args.force else _load_ledger(persist_dir)
    trades, n_reflected, n_skipped = [], 0, 0

    for date, snap in decisions:
        dec = snap.get("decision", {}) or {}
        action, conf, risk = dec.get("action"), dec.get("confidence"), dec.get("risk_score")
        if action == "持有" and not args.include_hold:
            print(f"  skip {date} action=持有（默认不反思）"); n_skipped += 1; continue
        if (action, conf, risk) == FALLBACK_FINGERPRINT:
            print(f"  skip {date} 解析回退指纹（持有/0.5/0.5）"); n_skipped += 1; continue
        if action not in ("买入", "卖出"):
            print(f"  skip {date} 未知 action={action!r}"); n_skipped += 1; continue

        for h in horizons:
            if (args.ticker, date, str(h)) in done:
                print(f"  skip {date} h={h} 已在台账"); n_skipped += 1; continue
            if args.force_return:
                ed = ec = xd = xc = raw_ret = signed = None
                rstr = args.force_return
            else:
                if prices is None:
                    trades.append({"ticker": args.ticker, "snapshot_date": date, "horizon": h, "action": action,
                                   "non_evaluable": True, "skip_reason": "no_prices", "reflected": False})
                    n_skipped += 1; continue
                got = _realized(prices, date, h)
                if got is None:
                    print(f"  non-eval {date} h={h}：前向交易日不足（评估日在未来）")
                    trades.append({"ticker": args.ticker, "snapshot_date": date, "horizon": h, "action": action,
                                   "non_evaluable": True, "skip_reason": "insufficient_forward", "reflected": False})
                    n_skipped += 1; continue
                ed, ec, xd, xc = got
                gap = (datetime.strptime(xd, "%Y-%m-%d") - datetime.strptime(ed, "%Y-%m-%d")).days
                if gap > h * 3 + 15:
                    print(f"  non-eval {date} h={h}：疑长停牌（{ed}->{xd} 跨 {gap} 日）")
                    trades.append({"ticker": args.ticker, "snapshot_date": date, "horizon": h, "action": action,
                                   "non_evaluable": True, "skip_reason": f"suspect_suspension_{gap}d", "reflected": False})
                    n_skipped += 1; continue
                raw_ret = (xc - ec) / ec
                signed = _signed_return(action, raw_ret)
                rstr = _returns_str(action, signed, raw_ret, f"{h} trading days", ed, ec, xd, xc)

            rec = {"trade_id": f"{args.ticker}-{date}-h{h}", "ticker": args.ticker, "snapshot_date": date,
                   "horizon": h, "action": action, "entry_date": ed, "entry_close": ec, "exit_date": xd,
                   "exit_close": xc, "price_return_pct": round(raw_ret * 100, 4) if raw_ret is not None else None,
                   "signed_return_pct": round(signed * 100, 4) if signed is not None else None,
                   "returns_losses": rstr, "confidence": conf, "risk_score": risk,
                   "target_price": dec.get("target_price"), "non_evaluable": False, "reflected": False}

            if args.dry_run:
                print(f"  DRY {date} h={h} {action} return={rec['signed_return_pct']}"); trades.append(rec); continue
            if args.no_reflect:
                print(f"  PRICE {date} h={h} {action} signed={rec['signed_return_pct']}% ({ed}@{ec}→{xd}@{xc})")
                trades.append(rec); continue
            try:
                t_r = time.time()
                _reflect(ta, snap, rstr)
                rec["reflected"] = True; n_reflected += 1
                _append_ledger(persist_dir, args.ticker, date, h, rstr)
                print(f"  ✅ reflect {date} h={h} {action} return={rec['signed_return_pct']}% ({time.time()-t_r:.1f}s)")
            except Exception as e:
                rec["reflect_error"] = repr(e); print(f"  ❌ reflect 失败 {date} h={h}: {e!r}")
            trades.append(rec)

    if not args.dry_run:
        _write_outputs(out_dir, trades, {
            "schema": "backtest-runner/v1", "mode": "reflect", "ticker": args.ticker, "runid": runid,
            "horizons": horizons, "snapshots": [os.path.basename(s) for s in snap_files],
            "persist_dir": persist_dir, "memory_namespace": args.ticker,
            "memory_embed_model": args.memory_embed_model, "force_return": args.force_return,
            "n_trades": len(trades), "n_reflected": n_reflected, "n_skipped": n_skipped,
            "generated_at": datetime.now().isoformat(timespec="seconds")})
    print(f"OK ticker={args.ticker} mode=reflect reflected={n_reflected} skipped={n_skipped} "
          f"trades={len(trades)} {'(dry-run)' if args.dry_run else 'out='+out_dir}")


# ----------------------------------------------------------------------------- M2 simulate 模式
def _load_decisions(args):
    """决策序列：fixture 文件（list[{ticker,date,action,confidence,snapshot?}]）或 snapshot glob。"""
    if args.decisions:
        raw = json.load(open(args.decisions, encoding="utf-8"))
        out = []
        for d in raw:
            out.append({"ticker": str(d["ticker"]), "date": d["date"], "action": d["action"],
                        "confidence": d.get("confidence"), "snapshot": d.get("snapshot")})
    else:
        # 生产：glob 全 universe 的 snapshot（向前累积的决策序列）
        base = os.path.join(args.ta_root, os.pardir, "Knowledge_Wiki", "raw", "data", "stock-snapshots", "cn")
        pat = f"{args.ticker}-*.json" if args.ticker else "*.json"
        out = []
        for sf in sorted(glob.glob(os.path.join(base, pat))):
            try:
                snap = json.load(open(sf, encoding="utf-8"))
            except Exception:
                continue
            if snap.get("status") != "complete":
                continue
            md, dec = snap.get("metadata", {}), snap.get("decision", {})
            out.append({"ticker": md.get("ticker"), "date": md.get("date"), "action": dec.get("action"),
                        "confidence": dec.get("confidence"), "snapshot": sf})
    out = [d for d in out if d["ticker"] and d["date"] and d["action"]]
    out.sort(key=lambda d: (d["date"], d["ticker"]))
    return out


def _price_map(series):
    """[(date,close)] → ({date:close}, sorted_dates) 便于按日查 + 停牌向前填充。"""
    return ({d: c for d, c in series}, [d for d, _ in series])


def _close_asof(pmap, sdates, day):
    """day 当日 close；停牌(无该日)用 <= day 的最近交易日 close 向前填充。"""
    if day in pmap:
        return pmap[day]
    prev = [d for d in sdates if d <= day]
    return pmap[prev[-1]] if prev else None


def _metrics(equity_curve, closed_trades, initial_cash):
    eqs = [p["equity"] for p in equity_curve]
    if len(eqs) < 2:
        return {"total_return": None, "cagr": None, "sharpe": None, "max_drawdown": None,
                "win_rate": None, "vs_benchmark": None, "n_closed_trades": len(closed_trades)}
    total_return = eqs[-1] / initial_cash - 1
    rets = [eqs[i] / eqs[i - 1] - 1 for i in range(1, len(eqs))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets) if len(rets) > 1 else 0.0
    vol = math.sqrt(var)
    sharpe = (mean / vol * math.sqrt(252)) if vol > 1e-12 else None
    peak, mdd = eqs[0], 0.0
    for e in eqs:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak > 0 else 0.0)
    d0 = datetime.strptime(equity_curve[0]["date"], "%Y-%m-%d")
    d1 = datetime.strptime(equity_curve[-1]["date"], "%Y-%m-%d")
    days = max((d1 - d0).days, 1)
    cagr = (eqs[-1] / initial_cash) ** (365.0 / days) - 1 if eqs[-1] > 0 else None
    wins = [t for t in closed_trades if (t.get("realized_pnl") or 0) > 0]
    win_rate = (len(wins) / len(closed_trades)) if closed_trades else None
    be0 = equity_curve[0].get("benchmark_equity")
    be1 = equity_curve[-1].get("benchmark_equity")
    vs_bench = (total_return - (be1 / be0 - 1)) if (be0 and be1) else None
    return {"total_return": round(total_return, 6), "cagr": round(cagr, 6) if cagr is not None else None,
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
            "max_drawdown": round(mdd, 6), "win_rate": round(win_rate, 4) if win_rate is not None else None,
            "vs_benchmark": round(vs_bench, 6) if vs_bench is not None else None,
            "n_closed_trades": len(closed_trades)}


def _simulate_mode(args, persist_dir, out_dir, runid):
    decisions = _load_decisions(args)
    if not decisions:
        print("FAILED 无决策序列（fixture 空 / 无 snapshot）", file=sys.stderr)
        sys.exit(1)
    tickers = sorted({d["ticker"] for d in decisions})
    dmin = min(d["date"] for d in decisions)
    dmax = max(d["date"] for d in decisions)
    end = args.end_date or _date.today().isoformat()
    start = (datetime.strptime(dmin, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    print(f"  决策 {len(decisions)} 条，标的 {tickers}，区间 [{dmin}~{dmax}]，模拟至 {end}")

    # 价格：每票拉一次
    pm = {}
    for t in tickers:
        s = _fetch_prices(t, start, end)
        if s is None:
            print(f"  ⚠️ {t} 价格为空——该票决策将无法成交/估值")
            continue
        pm[t] = _price_map(s)
        print(f"    {t}: {len(s)} 交易日 [{s[0][0]}~{s[-1][0]}]")
    # 基准（可选；指数/ETF 需 asset 类型支持，pro_bar 默认 equity 可能取不到 → 优雅降级为 null）
    bench_pm = None
    if args.benchmark:
        bs = _fetch_prices(args.benchmark, start, end)
        if bs:
            bench_pm = _price_map(bs)
            print(f"    benchmark {args.benchmark}: {len(bs)} 交易日")
        else:
            print(f"    ⚠️ benchmark {args.benchmark} 取数为空 → vs_benchmark 记 null（指数需 asset 支持，后续增强）")

    # 交易日轴 = 所有持仓票交易日并集，限定在 [dmin, end]
    all_days = sorted({d for t in pm for d in pm[t][1] if dmin <= d <= end})
    if not all_days:
        print("FAILED 模拟区间内无交易日价格", file=sys.stderr)
        sys.exit(1)

    reflect_enabled = not args.no_reflect and not args.dry_run
    if reflect_enabled:
        # 跨多票：reflect-on-close 按「平仓票」namespace 各进各自桶（见 _reflect_close）。
        # 这里只做一次 DashScope 探活，不建无 namespace 的主图（避免污染无后缀桶）。
        _probe_dashscope(args)

    dec_by_date = {}
    for d in decisions:
        dec_by_date.setdefault(d["date"], []).append(d)

    cash = float(args.initial_cash)
    positions = {}  # ticker -> {qty, avg_cost, available, entry_date, snapshot}
    equity_curve, all_trades, closed_trades = [], [], []
    n_reflected = 0
    fee = args.fee_bps / 10000.0
    bench_start_close = None

    for day in all_days:
        # T+1：昨日持仓今日可卖
        for p in positions.values():
            p["available"] = p["qty"]
        # 执行当日决策（按收盘价）
        for dec in dec_by_date.get(day, []):
            t, action, conf = dec["ticker"], dec["action"], (dec.get("confidence") or 0.5)
            if t not in pm:
                continue
            close = _close_asof(pm[t][0], pm[t][1], day)
            if close is None:
                continue
            if action == "买入":
                alloc = min(cash, float(args.initial_cash) * args.per_trade_weight * conf)
                qty = int(alloc / close // LOT) * LOT
                if qty <= 0:
                    all_trades.append({"date": day, "ticker": t, "side": "buy", "skipped": "alloc<1lot"}); continue
                cost = qty * close * (1 + fee)
                if cost > cash:
                    qty = int(cash / close // LOT) * LOT
                    cost = qty * close * (1 + fee)
                if qty <= 0:
                    continue
                pos = positions.get(t)
                if pos:
                    tot = pos["qty"] + qty
                    pos["avg_cost"] = (pos["avg_cost"] * pos["qty"] + close * qty) / tot
                    pos["qty"] = tot  # 新买入今日不可卖（available 不加）
                else:
                    positions[t] = {"qty": qty, "avg_cost": close, "available": 0,
                                    "entry_date": day, "snapshot": dec.get("snapshot")}
                cash -= cost
                all_trades.append({"date": day, "ticker": t, "side": "buy", "qty": qty, "price": round(close, 4),
                                   "confidence": conf})
            elif action == "卖出":
                pos = positions.get(t)
                if not pos or pos["available"] <= 0:
                    all_trades.append({"date": day, "ticker": t, "side": "sell", "skipped": "no_sellable_position"})
                    continue
                qty = pos["available"]
                proceeds = qty * close * (1 - fee)
                realized = (close - pos["avg_cost"]) * qty
                hold_ret = (close - pos["avg_cost"]) / pos["avg_cost"]
                hold_days = (datetime.strptime(day, "%Y-%m-%d") - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days
                cash += proceeds
                ct = {"date": day, "ticker": t, "side": "sell", "qty": qty, "price": round(close, 4),
                      "entry_date": pos["entry_date"], "avg_cost": round(pos["avg_cost"], 4),
                      "realized_pnl": round(realized, 2), "holding_return_pct": round(hold_ret * 100, 4),
                      "holding_days": hold_days, "reflected": False}
                # 平仓 → 功能 A：用真实持有期收益反思该买入决策
                if reflect_enabled and pos.get("snapshot"):
                    try:
                        snap = json.load(open(pos["snapshot"], encoding="utf-8"))
                        rstr = _returns_str("买入", hold_ret, hold_ret, f"{hold_days} calendar days held",
                                            pos["entry_date"], pos["avg_cost"], day, close)
                        _reflect_close(args, persist_dir, t, snap, rstr)
                        ct["reflected"] = True; n_reflected += 1
                        print(f"  ✅ reflect-on-close {t} {pos['entry_date']}→{day} 持有期收益 {hold_ret*100:+.2f}%")
                    except Exception as e:
                        ct["reflect_error"] = repr(e); print(f"  ❌ reflect-on-close 失败 {t}: {e!r}")
                closed_trades.append(ct); all_trades.append(ct)
                # 全平
                pos["qty"] -= qty
                if pos["qty"] <= 0:
                    positions.pop(t, None)
                else:
                    pos["available"] -= qty
            # 持有：no-op

        # mark-to-market（停牌向前填充）
        mkt = 0.0
        for t, p in positions.items():
            c = _close_asof(pm[t][0], pm[t][1], day) if t in pm else None
            if c is not None:
                mkt += p["qty"] * c
        equity = cash + mkt
        be = None
        if bench_pm:
            bc = _close_asof(bench_pm[0], bench_pm[1], day)
            if bc is not None:
                if bench_start_close is None:
                    bench_start_close = bc
                be = float(args.initial_cash) * bc / bench_start_close
        equity_curve.append({"date": day, "equity": round(equity, 2), "cash": round(cash, 2),
                             "market_value": round(mkt, 2), "benchmark_equity": round(be, 2) if be else None,
                             "n_positions": len(positions)})

    metrics = _metrics(equity_curve, closed_trades, float(args.initial_cash))

    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "equity_curve.json"), "w", encoding="utf-8") as f:
            json.dump(equity_curve, f, ensure_ascii=False, indent=2)
        _write_outputs(out_dir, all_trades, {
            "schema": "backtest-runner/v1", "mode": "simulate", "ticker": args.ticker, "runid": runid,
            "universe": tickers, "period": {"from": all_days[0], "to": all_days[-1]},
            "initial_cash": args.initial_cash, "per_trade_weight": args.per_trade_weight,
            "fee_bps": args.fee_bps, "benchmark": args.benchmark if bench_pm else None,
            "decisions_source": args.decisions or "snapshot-glob", "persist_dir": persist_dir,
            "memory_embed_model": args.memory_embed_model, "n_decisions": len(decisions),
            "n_trades": len(all_trades), "n_closed_trades": len(closed_trades), "n_reflected": n_reflected,
            "metrics": metrics, "generated_at": datetime.now().isoformat(timespec="seconds")})
        report_path = _write_simulate_report_md(args, runid, out_dir, tickers,
                                                 equity_curve, closed_trades, metrics)
        if report_path:
            print(f"   report : {report_path}")

    m = metrics
    print(f"OK mode=simulate universe={','.join(tickers)} days={len(equity_curve)} "
          f"total_return={m['total_return']} sharpe={m['sharpe']} maxDD={m['max_drawdown']} "
          f"win_rate={m['win_rate']} closed={m['n_closed_trades']} reflected={n_reflected} "
          f"{'(dry-run)' if args.dry_run else 'out='+out_dir}")


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


def _reflect_close(args, persist_dir, ticker, snap, returns_str):
    """simulate 平仓反思：按平仓票的 namespace 单独建 5 桶写入（跨票各进各自桶）。"""
    from tradingagents.graph.reflection import Reflector
    from tradingagents.agents.utils.memory import FinancialSituationMemory
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    # 复用一个 per-ticker graph（缓存避免重复建）
    cache = _reflect_close._cache
    if ticker not in cache:
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(llm_provider=args.provider, backend_url=args.backend_url, deep_think_llm=args.deep_model,
                   quick_think_llm=args.quick_model, memory_enabled=True, online_tools=True,
                   memory_namespace=ticker, memory_llm_provider=args.memory_embed_provider,
                   memory_embedding_model=args.memory_embed_model)
        cache[ticker] = TradingAgentsGraph(selected_analysts=["market", "fundamentals"], debug=False, config=cfg)
    ta = cache[ticker]
    ta.curr_state = _build_curr_state(snap)
    ta.ticker = ticker
    ta.reflect_and_remember(returns_str)


_reflect_close._cache = {}


# ----------------------------------------------------------------------------- 输出
def _write_outputs(out_dir, trades, cfg):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "trades.jsonl"), "w", encoding="utf-8") as f:
        for r in trades:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------- M1 教训回读 + 导出（export 模式）
# 说明：M1 内容全部由现有链路生成——前向收益用 _realized(价格层) 重算，教训由 reflect_and_remember 写入 5 桶。
# export 模式不重跑引擎、不重写桶（append-only 防污染），只「读出 + 落盘」：把已生成的教训 + 重算收益
# 组装成前端可读的 backtest-report.md。读桶用 chromadb exact-match（零 embedding、零 LLM）。
BUCKET_ROLES = [
    ("bull_memory", "多头研究员"), ("bear_memory", "空头研究员"),
    ("trader_memory", "交易员"), ("invest_judge_memory", "投资裁判"),
    ("risk_manager_memory", "风险经理"),
]


def _situation_from_snap(snap):
    """复刻引擎 Reflector._extract_current_situation：4 份报告拼接（= reflect 写入桶时的检索 KEY）。"""
    cs = _build_curr_state(snap)
    return f'{cs["market_report"]}\n\n{cs["sentiment_report"]}\n\n{cs["news_report"]}\n\n{cs["fundamentals_report"]}'


def _load_ledger_records(persist_dir, ticker=None):
    """返回台账全记录（dict）；reflect 时按 (ticker,date,horizon) 写入，含 returns_losses。"""
    recs, p = [], _ledger_path(persist_dir)
    if not os.path.exists(p):
        return recs
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if ticker is None or r.get("ticker") == ticker:
                recs.append(r)
    return recs


def _read_lessons(persist_dir, ticker, situation):
    """只读回读 5 桶里为该 situation 写入的教训（exact-match document；无 embedding、不改桶）。"""
    import chromadb
    client = chromadb.PersistentClient(path=persist_dir)
    out = []
    for bucket, role in BUCKET_ROLES:
        rec = {"bucket": bucket, "role": role, "lesson": "", "present": False, "matched_situation": False}
        try:
            col = client.get_collection(f"{bucket}__{ticker}")
        except Exception:
            out.append(rec); continue           # 桶不存在 = 未反思过
        rec["present"] = True
        try:
            got = col.get(include=["documents", "metadatas"])
        except Exception as e:
            rec["error"] = repr(e); out.append(rec); continue
        docs, metas = got.get("documents") or [], got.get("metadatas") or []
        idx = next((i for i in range(len(docs) - 1, -1, -1) if docs[i] == situation), None)
        rec["matched_situation"] = idx is not None
        if idx is None and docs:
            idx = len(docs) - 1                  # 兜底：取最新一条
        if idx is not None and idx < len(metas):
            rec["lesson"] = ((metas[idx] or {}).get("recommendation") or "")
        out.append(rec)
    return out


def _lesson_summary(text, n=240):
    """长教训报告 → 单行卡片摘要：去 markdown 记号、合并空白、截断。完整文本留在 lessons.json。"""
    import re
    t = (text or "").replace("```", " ")
    t = re.sub(r"[#*>`|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:n] + "…") if len(t) > n else t


def _snap_name(snap):
    md = snap.get("metadata") or {}
    return md.get("name") or md.get("company_name") or md.get("company") or ""


def _export_mode(args, persist_dir, out_dir, runid, snap_files):
    # 载入 snapshots（与 reflect 一致：complete + 有 date）
    decisions = []
    for sf in snap_files:
        try:
            snap = json.load(open(sf, encoding="utf-8"))
        except Exception as e:
            print(f"  skip 读取失败 {os.path.basename(sf)}: {e!r}"); continue
        if snap.get("status") != "complete":
            print(f"  skip status!=complete {os.path.basename(sf)}"); continue
        date = (snap.get("metadata") or {}).get("date")
        if date:
            decisions.append((date, snap))
    decisions.sort(key=lambda x: x[0])
    if not decisions:
        print("FAILED 无可用 snapshot（complete + date）", file=sys.stderr); sys.exit(1)

    led = _load_ledger_records(persist_dir, args.ticker)
    reflected = {(r.get("snapshot_date"), str(r.get("horizon"))) for r in led}
    led_h = {int(r["horizon"]) for r in led if str(r.get("horizon", "")).isdigit()}
    horizons = sorted(set(int(h) for h in args.horizons.split(",") if h.strip()) | led_h)

    # 价格层（重算真实收益，只读 Tushare）
    dmin = min(d for d, _ in decisions)
    start = (datetime.strptime(dmin, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    prices = _fetch_prices(args.ticker, start, _date.today().isoformat())
    if prices is None:
        print("FAILED 价格取数为空，无法重算收益", file=sys.stderr); sys.exit(1)
    print(f"  价格 {args.ticker}: {len(prices)} 交易日 [{prices[0][0]}~{prices[-1][0]}]；台账已反思 {len(reflected)} 条")

    trades, n_reflected, n_non_eval, reflected_dates = [], 0, 0, []
    for date, snap in decisions:
        dec = snap.get("decision", {}) or {}
        action = dec.get("action")
        for h in horizons:
            got = _realized(prices, date, h)
            if got is None:
                trades.append({"snapshot_date": date, "horizon": h, "action": action,
                               "non_evaluable": True, "skip_reason": "insufficient_forward", "reflected": False})
                n_non_eval += 1
                continue
            ed, ec, xd, xc = got
            raw = (xc - ec) / ec
            signed = _signed_return(action, raw)
            is_ref = (date, str(h)) in reflected
            trades.append({"snapshot_date": date, "horizon": h, "action": action,
                           "entry_date": ed, "entry_close": round(ec, 4), "exit_date": xd, "exit_close": round(xc, 4),
                           "price_return_pct": round(raw * 100, 4), "signed_return_pct": round(signed * 100, 4),
                           "confidence": dec.get("confidence"), "risk_score": dec.get("risk_score"),
                           "non_evaluable": False, "reflected": is_ref})
            if is_ref:
                n_reflected += 1
                if date not in reflected_dates:
                    reflected_dates.append(date)

    # 读回教训（按已反思 snapshot 的 situation 精确匹配）
    lessons, snap_by_date = [], {d: s for d, s in decisions}
    for date in reflected_dates:
        for L in _read_lessons(persist_dir, args.ticker, _situation_from_snap(snap_by_date[date])):
            L["snapshot_date"] = date
            lessons.append(L)
    if not reflected_dates:
        print("  ⚠️ 台账无该 ticker 的已反思记录 → lessons 为空（先 --mode reflect）")

    # 机器产物
    os.makedirs(out_dir, exist_ok=True)
    for fn, obj in (("trades.json", trades), ("lessons.json", lessons)):
        with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "backtest-runner/v1", "mode": "export", "ticker": args.ticker, "runid": runid,
                   "horizons": horizons, "snapshots": [os.path.basename(s) for s in snap_files],
                   "persist_dir": persist_dir, "n_trades": len(trades), "n_reflected": n_reflected,
                   "n_non_evaluable": n_non_eval, "generated_at": datetime.now().isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=2)

    report_path = _write_report_md(args, runid, out_dir, decisions, trades, lessons,
                                   n_reflected, n_non_eval, horizons)
    headline = next((t for t in trades if t.get("reflected")), None)
    hl = (f"{headline['signed_return_pct']:+.2f}% {headline['entry_date']}→{headline['exit_date']}"
          if headline else "无")
    n_with_lesson = len([L for L in lessons if L.get("lesson")])
    print(f"OK ticker={args.ticker} mode=export reflected={n_reflected} non_eval={n_non_eval} "
          f"lessons={n_with_lesson}/5 headline={hl}")
    print(f"   machine: {out_dir}")
    print(f"   report : {report_path}")


def _write_report_md(args, runid, out_dir, decisions, trades, lessons, n_reflected, n_non_eval, horizons):
    """落前端可读 backtest-report.md：flat frontmatter + 正文 <!-- backtest-json --> json 块。"""
    kb_root = os.path.abspath(os.path.join(args.ta_root, os.pardir, "Knowledge_Wiki"))
    report_dir = args.report_dir or os.path.join(kb_root, "raw", "analysis", "backtests", "cn")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{args.ticker}-{runid}.md")
    name = _snap_name(decisions[-1][1]) if decisions else ""
    ref_dates = sorted({t["snapshot_date"] for t in trades if t.get("reflected")})
    as_of = decisions[-1][0] if decisions else ""
    headline = next((t for t in trades if t.get("reflected")), None)
    rel_out = os.path.relpath(out_dir, kb_root).replace(os.sep, "/")

    # 前端展示用的精简教训（完整文本在 lessons.json）
    disp_lessons = [{"bucket": L["bucket"], "role": L["role"], "snapshot_date": L.get("snapshot_date"),
                     "matched": L.get("matched_situation", False), "lesson": _lesson_summary(L.get("lesson", ""))}
                    for L in lessons]
    payload = json.dumps({"trades": trades, "lessons": disp_lessons}, ensure_ascii=False)

    fm = ["---", "type: backtest-report", f'ticker: "{args.ticker}"']
    if name:
        fm.append(f"name: {name}")
    fm += ["mode: reflect", f"run_status: {'ok' if n_reflected else 'partial'}",
           f'snapshot_date: "{ref_dates[0] if ref_dates else (decisions[0][0] if decisions else "")}"',
           f'as_of: "{as_of}"', f'horizons: "{",".join(str(h) for h in horizons)}"',
           f"n_reflected: {n_reflected}", f"n_non_evaluable: {n_non_eval}"]
    if headline:
        fm.append(f"headline_return_pct: {headline['signed_return_pct']}")
    fm += ["sources:", f"  - {rel_out}/trades.json", f"  - {rel_out}/lessons.json", "---"]

    title_tk = f"{args.ticker} {name}".strip()
    body = []
    if headline:
        body.append(f"# {title_tk} · M1 单决策反思")
        body.append("")
        body.append(f"{headline['snapshot_date']} {headline['action']} @{headline['entry_close']} 持 "
                    f"{headline['horizon']} 交易日 → {headline['exit_date']} @{headline['exit_close']}，"
                    f"真实 {headline['signed_return_pct']:+.2f}%（Tushare qfq），已 reflect 写入 5 桶。")
    else:
        body.append(f"# {title_tk} · M1 单决策反思（暂无已反思决策）")
    body += ["", "⚠ 教训为引擎 reflect 模型生成（非事实），完整文本见 sources 的 lessons.json。", "",
             "<!-- backtest-json -->", "```json", payload, "```", ""]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n\n" + "\n".join(body) + "\n")
    return report_path


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="回测/交易模拟 + 记忆功能 A（M1 reflect / M2 simulate）。")
    ap.add_argument("--ticker", default=None, help="A 股代码 6 位；reflect 必填；simulate 可空（用 fixture 时）")
    ap.add_argument("--mode", default="reflect", choices=["reflect", "simulate", "export"])
    ap.add_argument("--snapshots", default=None, help="reflect：snapshot 目录或 glob（默认按 ticker）")
    ap.add_argument("--horizons", default="5,20", help="reflect：前向评估窗口（交易日）")
    # simulate
    ap.add_argument("--decisions", default=None, help="simulate：决策序列 fixture JSON（不给则 glob snapshot）")
    ap.add_argument("--initial-cash", type=float, default=1_000_000.0)
    ap.add_argument("--per-trade-weight", type=float, default=0.2, help="单笔买入预算 = initial_cash × 此 × confidence")
    ap.add_argument("--fee-bps", type=float, default=5.0, help="单边费率(基点)")
    ap.add_argument("--benchmark", default=None, help="基准代码（如 000300.SH；指数需 asset 支持，取不到则 null）")
    ap.add_argument("--end-date", default=None, help="simulate 模拟终点（默认今天）")
    # common
    ap.add_argument("--out", default=None)
    ap.add_argument("--report-dir", default=None,
                    help="export：前端可读报告(.md)目录，默认 Knowledge_Wiki/raw/analysis/backtests/cn")
    ap.add_argument("--ta-root", default=DEFAULT_TA_ROOT)
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--backend-url", default="http://localhost:5678")
    ap.add_argument("--quick-model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--deep-model", default="claude-opus-4-8")
    ap.add_argument("--memory-persist-dir", default=None)
    ap.add_argument("--memory-embed-provider", default="dashscope")
    ap.add_argument("--memory-embed-model", default="text-embedding-v4")
    ap.add_argument("--include-hold", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--force-return", default=None, help="reflect 验证用：跳过价格层用合成收益")
    ap.add_argument("--no-reflect", action="store_true", help="不写记忆（价格层/组合层干跑）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    args.ta_root = os.path.abspath(args.ta_root)
    if not os.path.isdir(args.ta_root):
        print(f"FAILED ta_root 不存在: {args.ta_root}", file=sys.stderr); sys.exit(1)
    if args.mode in ("reflect", "export") and not args.ticker:
        print(f"FAILED {args.mode} 模式需 --ticker", file=sys.stderr); sys.exit(1)

    persist_dir = os.path.abspath(args.memory_persist_dir or os.path.join(
        args.ta_root, os.pardir, "Knowledge_Wiki", ".kb-vectors", "ta-memory"))
    runid = datetime.now().strftime("%Y%m%dT%H%M%S")
    tag = args.ticker or "universe"
    out_dir = os.path.abspath(args.out) if args.out else os.path.abspath(os.path.join(
        args.ta_root, os.pardir, "Knowledge_Wiki", "raw", "data", "backtests", "cn", f"{tag}-{runid}"))

    _setup_env(args.ta_root, persist_dir)

    if args.mode in ("reflect", "export"):
        snap_arg = args.snapshots or os.path.join(
            args.ta_root, os.pardir, "Knowledge_Wiki", "raw", "data", "stock-snapshots", "cn",
            f"{args.ticker}-*.json")
        if os.path.isdir(snap_arg):
            snap_files = sorted(glob.glob(os.path.join(snap_arg, f"{args.ticker}-*.json")))
        else:
            snap_files = sorted(glob.glob(snap_arg))
        if not snap_files:
            print(f"FAILED 未找到 snapshot: {snap_arg}", file=sys.stderr); sys.exit(1)
        if args.mode == "reflect":
            _reflect_mode(args, persist_dir, out_dir, runid, snap_files)
        else:
            _export_mode(args, persist_dir, out_dir, runid, snap_files)
    else:
        _simulate_mode(args, persist_dir, out_dir, runid)


if __name__ == "__main__":
    main()
