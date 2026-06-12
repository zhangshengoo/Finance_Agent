#!/usr/bin/env python3
"""stock-analysis Skill 的 bundled 运行器：无头调用 TradingAgents-CN 做单股分析，
把 final_state 报告 + decision 序列化成结构化 JSON。

必须用 **TradingAgents-CN 自带的 venv**（Python 3.10，依赖已装）运行，而不是 uv --python 3.12：

  MONGODB_ENABLED=false REDIS_ENABLED=false \
  <ta-root>/.venv/bin/python run_stock_analysis.py \
    --ticker 600519 --date 2026-06-08 --depth 1 \
    --analysts market,fundamentals --out /tmp/600519.json --ta-root <ta-root>

设计要点（已对照 TradingAgents-CN 源码核实）：
- 在 import tradingagents 之前 **强制** 设 MONGODB_ENABLED/REDIS_ENABLED/USE_MONGODB_STORAGE=false。
  连接是惰性的，由这些开关短路（tradingagents/config/database_manager.py:88/128），
  且 load_dotenv 用 override=False，不会覆盖我们提前设好的禁用开关。
- chdir 到 ta_root：results_dir / data_cache 等用相对路径。
- ChromaDB（记忆）只在 config["memory_enabled"] 为真时初始化（trading_graph.py:546）；
  档位 1 关闭记忆即可完全避开。
- 只序列化「安全字段」，跳过 final_state["messages"]（内含 LangChain message 对象，无法直接 JSON 化）。
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import date as _date

# 档位 → (max_debate_rounds, max_risk_discuss_rounds, memory_enabled)
# 对齐 cli/utils.py 与 web/utils/analysis_runner.py 的 1–5 档预设。
DEPTH_MAP = {
    1: (1, 1, False),  # 快速
    2: (1, 1, True),   # 基础
    3: (1, 2, True),   # 标准（Web 默认）
    4: (2, 2, True),   # 深入
    5: (3, 3, True),   # 全面
}

# 默认 TradingAgents-CN 根目录（项目内固定位置）；子 agent 仍会显式传 --ta-root。
DEFAULT_TA_ROOT = "/Users/zhangsheng/code/OpenClaw-Task/Finance_Agent/TradingAgents-CN"


def _fail(out_path, args, msg, elapsed=None):
    """写一份 status=failed 的 JSON 并以非零码退出，方便调用方稳定解析失败。"""
    tb = traceback.format_exc()
    has_tb = tb and "NoneType: None" not in tb
    err = {
        "schema": "stock-analysis-runner/v1",
        "status": "failed",
        "error": str(msg),
        "traceback": tb if has_tb else None,
        "metadata": {
            "ticker": getattr(args, "ticker", None),
            "date": getattr(args, "date", None),
            "depth": getattr(args, "depth", None),
            "elapsed_seconds": round(elapsed, 1) if elapsed is not None else None,
        },
    }
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(err, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass
    print(f"FAILED {msg}", file=sys.stderr)
    if has_tb:
        print(tb, file=sys.stderr)
    sys.exit(1)


def _g(state, key):
    """取报告字符串字段；空串/缺失统一归一为 None。"""
    v = state.get(key)
    if isinstance(v, str):
        v = v.strip()
    return v or None


def _serialize(args, analysts, config, final_state, decision, elapsed):
    ids = final_state.get("investment_debate_state") or {}
    rds = final_state.get("risk_debate_state") or {}
    return {
        "schema": "stock-analysis-runner/v1",
        "status": "complete",
        "metadata": {
            "ticker": args.ticker,
            "company_of_interest": final_state.get("company_of_interest"),
            "date": args.date,
            "market": "cn",
            "depth": args.depth,
            "analysts": analysts,
            "provider": config["llm_provider"],
            "deep_model": config["deep_think_llm"],
            "quick_model": config["quick_think_llm"],
            "model_info": decision.get("model_info"),
            "elapsed_seconds": round(elapsed, 1),
        },
        "reports": {
            "market": _g(final_state, "market_report"),
            "fundamentals": _g(final_state, "fundamentals_report"),
            "news": _g(final_state, "news_report"),
            "sentiment": _g(final_state, "sentiment_report"),
            "investment_plan": _g(final_state, "investment_plan"),
            "trader_investment_plan": _g(final_state, "trader_investment_plan"),
            "final_trade_decision": _g(final_state, "final_trade_decision"),
        },
        "debates": {
            "investment": {
                "bull_history": (ids.get("bull_history") or None),
                "bear_history": (ids.get("bear_history") or None),
                "judge_decision": (ids.get("judge_decision") or None),
                "count": ids.get("count"),
            },
            "risk": {
                "risky_history": (rds.get("risky_history") or None),
                "safe_history": (rds.get("safe_history") or None),
                "neutral_history": (rds.get("neutral_history") or None),
                "judge_decision": (rds.get("judge_decision") or None),
                "count": rds.get("count"),
            },
        },
        "decision": {
            "action": decision.get("action"),
            "target_price": decision.get("target_price"),
            "confidence": decision.get("confidence"),
            "risk_score": decision.get("risk_score"),
            "reasoning": decision.get("reasoning"),
            "model_info": decision.get("model_info"),
        },
        "performance_metrics": final_state.get("performance_metrics") or {},
    }


def main():
    ap = argparse.ArgumentParser(description="Headless single-stock analysis via TradingAgents-CN.")
    ap.add_argument("--ticker", required=True, help="A 股代码，6 位数字，如 600519")
    ap.add_argument("--date", default=_date.today().isoformat(), help="交易日期 YYYY-MM-DD（不可未来）")
    ap.add_argument("--depth", type=int, default=1, choices=[1, 2, 3, 4, 5], help="分析档位 1–5")
    ap.add_argument("--analysts", default="market,social,news,fundamentals", help="逗号分隔；A 股 social 走 sentiment_em，全 4 类可用")
    ap.add_argument("--out", required=True, help="结果 JSON 的绝对路径")
    ap.add_argument("--ta-root", default=DEFAULT_TA_ROOT, help="TradingAgents-CN 根目录")
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--backend-url", default="http://localhost:5678")
    ap.add_argument("--deep-model", default="claude-opus-4-8")
    ap.add_argument("--quick-model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    ta_root = os.path.abspath(args.ta_root)
    out_path = os.path.abspath(args.out)

    # 1) 强制无头：禁用 Mongo/Redis（必须在 import tradingagents 之前）。
    os.environ["MONGODB_ENABLED"] = "false"
    os.environ["REDIS_ENABLED"] = "false"
    os.environ["USE_MONGODB_STORAGE"] = "false"

    # 2) 切到 TA 根（相对路径的 results/data 缓存等），并把 TA 根放到 sys.path。
    #    tradingagents 不是 pip 安装的包，而是 TA 根下的源码目录——analyze_stock.py 能 import
    #    是因为它就跑在 TA 根（sys.path[0]=CWD）。我们的 runner 在别处，chdir 不改 sys.path，
    #    所以必须显式把 ta_root 插到 sys.path 最前。
    if not os.path.isdir(ta_root):
        _fail(out_path, args, f"ta_root 不存在: {ta_root}")
    os.chdir(ta_root)
    sys.path.insert(0, ta_root)

    # 3) 读 .env 拿 TUSHARE_TOKEN / ANTHROPIC_*（override=False，不覆盖上面禁用开关）。
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ta_root, ".env"), override=False)
    except Exception:
        pass  # 没有 dotenv 也没关系，shell env 仍可用

    # 4) chdir + env 就绪后再 import。
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except Exception as e:
        _fail(out_path, args, f"import tradingagents 失败: {e!r}")

    debate, risk, mem = DEPTH_MAP[args.depth]
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = args.provider
    config["backend_url"] = args.backend_url
    config["deep_think_llm"] = args.deep_model
    config["quick_think_llm"] = args.quick_model
    config["max_debate_rounds"] = debate
    config["max_risk_discuss_rounds"] = risk
    config["memory_enabled"] = mem
    config["online_tools"] = True

    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    # A 股 social 情绪已接入 sentiment_em（东财人气排名 + 微博情绪分，social_media_analyst 走 is_china），
    # 不再剔除 social——这是本会话新接的 A 股真数据能力（见 analyze_stock_deep.py）。
    if not analysts:
        _fail(out_path, args, "analysts 为空")

    # debug=True 是已验证路径（analyze_stock.py 同款）：propagate 在无 progress_callback 时，
    # debug=True 走 "values" 流模式（final_state = chunk，正确）；debug=False 会落进引擎自身的
    # invoke 模式分支，在 trading_graph.py:797 误把状态字段当 update dict → ValueError。
    # verbose stdout 由子 agent 吸收，对结构化产出无影响。
    t0 = time.time()
    try:
        ta = TradingAgentsGraph(selected_analysts=analysts, debug=True, config=config)
        final_state, decision = ta.propagate(args.ticker, args.date)
    except Exception as e:
        _fail(out_path, args, f"propagate 失败: {e!r}", elapsed=time.time() - t0)
    elapsed = time.time() - t0

    result = _serialize(args, analysts, config, final_state, decision, elapsed)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    d = result.get("decision", {})
    print(
        f"OK ticker={args.ticker} depth={args.depth} analysts={','.join(analysts)} "
        f"action={d.get('action')} target_price={d.get('target_price')} "
        f"confidence={d.get('confidence')} risk={d.get('risk_score')} "
        f"elapsed={elapsed:.1f}s out={out_path}"
    )


if __name__ == "__main__":
    main()
