#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["akshare==1.18.38", "pandas", "curl_cffi==0.13.0"]
# ///

# Vendored from OpenClaw_FinRobot:
#   finrobot/agents/market-agent/skills/industry-analysis/scripts/industry_analysis.py
# Copied on 2026-06-05 for industry-analysis Skill P0 (direct AKShare path; Tushare merge in P2).
# OpenClaw_FinRobot is an internal sister project under the same user-owned umbrella; no
# external license obligation. To re-sync upstream changes, re-copy the source file and
# re-apply this comment block.

"""
行业分析数据采集脚本

四种模式：
  overview  — 31 个申万一级行业估值横向对比
  detail    — 单行业深度数据（估值 + K线 + 成份股 + 资金流）
  history   — 行业估值历史趋势（从 DB 读取，含分位数）
  snapshot  — 保存当日估值快照到 DB

数据源：
  申万行业估值 — AKShare sw_index_first_info (legulegu)
  行业K线     — AKShare stock_board_industry_hist_em (eastmoney)
  成份股      — AKShare stock_board_industry_cons_em (eastmoney)
  资金流      — AKShare stock_fund_flow_industry (eastmoney)

用法：
  # 31 个行业估值一览
  uv run --python 3.12 industry_analysis.py --mode overview

  # 单行业深度（估值+K线+成份股+资金流）
  uv run --python 3.12 industry_analysis.py --mode detail --industry "有色金属"

  # 行业估值历史（从 DB 读取）
  uv run --python 3.12 industry_analysis.py --mode history --industry "有色金属" --days 756

  # 保存今日 31 个行业估值快照到 DB
  uv run --python 3.12 industry_analysis.py --mode snapshot

  # 保存快照并同时保存成份股（周度）
  uv run --python 3.12 industry_analysis.py --mode snapshot --with-constituents
"""
import argparse
import json
import os
import sys
import time
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

# 引入持久化层
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../shared"))

# ============================================================
# 工具函数
# ============================================================

def safe_float(val, default=None):
    """安全转 float，处理 None/NaN/空字符串。"""
    try:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.strip()
            if val in ("", "-", "--", "nan"):
                return default
        import math
        f = float(val)
        return default if math.isnan(f) else round(f, 4)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    """安全转 int。"""
    f = safe_float(val)
    return int(f) if f is not None else default


def _retry_call(fn, max_retries=2, base_wait=2.0):
    """指数退避重试。"""
    for attempt in range(max_retries + 1):
        try:
            result = fn()
            if result is not None and hasattr(result, 'empty') and not result.empty:
                return result
            if result is not None and not hasattr(result, 'empty'):
                return result
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = base_wait * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    return None


# ============================================================
# 申万行业估值数据
# ============================================================

def fetch_sw_industries():
    """获取申万一级行业估值一览（31 个行业）。
    数据源：AKShare sw_index_first_info (legulegu)。
    返回 DataFrame 或 None。
    """
    import akshare as ak
    try:
        df = _retry_call(lambda: ak.sw_index_first_info())
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(json.dumps({"error": f"sw_index_first_info 失败: {e}"}, ensure_ascii=False), file=sys.stderr)
        return None


def parse_sw_industries(df):
    """解析申万一级行业 DataFrame → 标准化 dict 列表。"""
    results = []
    # 列名可能因 AKShare 版本不同
    col_map = {
        "行业代码": "sw_code",
        "行业名称": "name",
        "成份个数": "constituents",
        "静态市盈率": "pe_static",
        "TTM(市盈率)": "pe_ttm",
        "TTM(滚动)市盈率": "pe_ttm",
        "市净率": "pb",
        "静态股息率": "dividend_yield",
    }
    # 备用列名
    alt_col_map = {
        "指数代码": "sw_code",
        "指数名称": "name",
        "成分股个数": "constituents",
    }

    for _, row in df.iterrows():
        item = {}
        for src, dst in col_map.items():
            if src in df.columns:
                item[dst] = row[src]
        # 备用列名
        for src, dst in alt_col_map.items():
            if src in df.columns and dst not in item:
                item[dst] = row[src]

        # 标准化
        if "name" in item:
            # 去掉可能的 "(申万)" 后缀
            name = str(item["name"]).replace("(申万)", "").strip()
            item["name"] = name
        item["sw_code"] = str(item.get("sw_code", ""))
        item["constituents"] = safe_int(item.get("constituents"))
        item["pe_static"] = safe_float(item.get("pe_static"))
        item["pe_ttm"] = safe_float(item.get("pe_ttm"))
        item["pb"] = safe_float(item.get("pb"))
        item["dividend_yield"] = safe_float(item.get("dividend_yield"))

        if item.get("name"):
            results.append(item)

    return results


# ============================================================
# 东财行业数据
# ============================================================

def fetch_industry_kline(industry_name, period="daily", days=60):
    """获取东财行业板块历史K线。
    period: daily / weekly / monthly
    返回 dict 列表或 None。
    """
    import akshare as ak
    try:
        df = _retry_call(lambda: ak.stock_board_industry_hist_em(
            symbol=industry_name, period=period, adjust=""
        ))
        if df is None or df.empty:
            return None

        # 取最近 N 条
        df = df.tail(days)

        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "amount", "振幅": "amplitude", "涨跌幅": "pct_chg",
            "涨跌额": "change", "换手率": "turnover",
        }
        records = []
        for _, row in df.iterrows():
            item = {}
            for src, dst in col_map.items():
                if src in df.columns:
                    val = row[src]
                    if dst == "date":
                        item[dst] = str(val)[:10]
                    elif dst == "amount":
                        item["amount_yi"] = safe_float(val / 1e8 if val else None)
                    else:
                        item[dst] = safe_float(val)
            records.append(item)
        return records
    except Exception as e:
        print(json.dumps({"error": f"行业K线获取失败({industry_name}): {e}"}, ensure_ascii=False), file=sys.stderr)
        return None


def fetch_industry_constituents(industry_name, top_n=20):
    """获取东财行业成份股。返回 dict 列表或 None。"""
    import akshare as ak
    try:
        df = _retry_call(lambda: ak.stock_board_industry_cons_em(symbol=industry_name))
        if df is None or df.empty:
            return None

        col_map = {
            "代码": "symbol", "名称": "name", "最新价": "price",
            "涨跌幅": "pct_chg", "成交额": "amount",
            "总市值": "market_cap", "市盈率-动态": "pe",
            "市净率": "pb",
        }
        records = []
        for _, row in df.iterrows():
            item = {}
            for src, dst in col_map.items():
                if src in df.columns:
                    item[dst] = row[src]
            # 标准化
            item["symbol"] = str(item.get("symbol", ""))
            item["name"] = str(item.get("name", ""))
            item["price"] = safe_float(item.get("price"))
            item["pct_chg"] = safe_float(item.get("pct_chg"))
            item["pe"] = safe_float(item.get("pe"))
            item["pb"] = safe_float(item.get("pb"))
            mc = safe_float(item.get("market_cap"))
            item["market_cap_yi"] = round(mc / 1e8, 2) if mc else None
            item.pop("market_cap", None)
            item.pop("amount", None)
            records.append(item)

        # 按市值排序取 TOP N
        records.sort(key=lambda x: x.get("market_cap_yi") or 0, reverse=True)
        return records[:top_n]
    except Exception as e:
        print(json.dumps({"error": f"成份股获取失败({industry_name}): {e}"}, ensure_ascii=False), file=sys.stderr)
        return None


def fetch_industry_fund_flow(industry_name):
    """获取行业资金流向。返回 dict 或 None。"""
    import akshare as ak
    try:
        df = _retry_call(lambda: ak.stock_fund_flow_industry(symbol="即时"))
        if df is None or df.empty:
            return None

        # 查找目标行业
        name_col = None
        for c in ["行业", "名称", "板块名称"]:
            if c in df.columns:
                name_col = c
                break
        if not name_col:
            return None

        matched = df[df[name_col].str.contains(industry_name, na=False)]
        if matched.empty:
            return None

        row = matched.iloc[0]
        result = {}
        flow_cols = {
            "主力净流入-净额": "main_net_inflow",
            "超大单净流入-净额": "super_large_net",
            "大单净流入-净额": "large_net",
            "中单净流入-净额": "medium_net",
            "小单净流入-净额": "small_net",
        }
        for src, dst in flow_cols.items():
            if src in df.columns:
                val = safe_float(row[src])
                result[dst + "_yi"] = round(val / 1e8, 2) if val else None

        result["industry"] = industry_name
        return result
    except Exception as e:
        print(json.dumps({"error": f"资金流向获取失败({industry_name}): {e}"}, ensure_ascii=False), file=sys.stderr)
        return None


# ============================================================
# 四种模式实现
# ============================================================

def mode_overview():
    """模式 1: 31 个行业估值一览。"""
    df = fetch_sw_industries()
    if df is None:
        return {"results": {}, "errors": {"overview": "sw_index_first_info 返回空数据"}}

    industries = parse_sw_industries(df)

    # 按 PE(TTM) 排序，加排名
    valid = [i for i in industries if i.get("pe_ttm") is not None and i["pe_ttm"] > 0]
    valid.sort(key=lambda x: x["pe_ttm"])
    for idx, item in enumerate(valid, 1):
        item["pe_rank"] = idx

    # 按 PB 排序
    valid_pb = sorted([i for i in industries if i.get("pb") is not None and i["pb"] > 0],
                      key=lambda x: x["pb"])
    pb_rank_map = {item["name"]: idx + 1 for idx, item in enumerate(valid_pb)}
    for item in industries:
        item["pb_rank"] = pb_rank_map.get(item["name"])

    # 按股息率排序（降序，高股息排前面）
    valid_div = sorted([i for i in industries if i.get("dividend_yield") is not None],
                       key=lambda x: x["dividend_yield"], reverse=True)
    div_rank_map = {item["name"]: idx + 1 for idx, item in enumerate(valid_div)}
    for item in industries:
        item["dividend_rank"] = div_rank_map.get(item["name"])

    return {
        "results": {
            "industries": industries,
            "count": len(industries),
            "pe_lowest_5": [i["name"] for i in valid[:5]] if len(valid) >= 5 else [],
            "pe_highest_5": [i["name"] for i in valid[-5:]] if len(valid) >= 5 else [],
            "dividend_top_5": [i["name"] for i in valid_div[:5]] if len(valid_div) >= 5 else [],
        },
        "errors": {},
    }


def mode_detail(industry_name, kline_days=60, top_n=20):
    """模式 2: 单行业深度数据。"""
    results = {}
    errors = {}

    # 1. 申万行业估值
    df = fetch_sw_industries()
    if df is not None:
        all_industries = parse_sw_industries(df)
        # 找到目标行业
        target = None
        for item in all_industries:
            if industry_name in item.get("name", ""):
                target = item
                break
        if target:
            results["valuation"] = target
            # 计算排名
            valid_pe = sorted([i for i in all_industries if i.get("pe_ttm") and i["pe_ttm"] > 0],
                              key=lambda x: x["pe_ttm"])
            for idx, i in enumerate(valid_pe, 1):
                if i["name"] == target["name"]:
                    results["valuation"]["pe_rank_in_31"] = idx
                    break
            results["valuation"]["total_industries"] = len(all_industries)
            results["valuation"]["_source"] = "legulegu"

            # 尝试从 DB 计算分位数
            try:
                from industry_store import get_industry_id, calc_percentile
                ind_id = get_industry_id(target["name"])
                if ind_id and target.get("pe_ttm"):
                    pctile = calc_percentile(ind_id, "pe_ttm", target["pe_ttm"])
                    if pctile is not None:
                        results["valuation"]["pe_ttm_percentile_3y"] = pctile
                if ind_id and target.get("pb"):
                    pctile = calc_percentile(ind_id, "pb", target["pb"])
                    if pctile is not None:
                        results["valuation"]["pb_percentile_3y"] = pctile
            except ImportError:
                pass  # 持久化层不可用时跳过
        else:
            errors["valuation"] = f"未找到行业: {industry_name}"
    else:
        errors["valuation"] = "sw_index_first_info 返回空数据"

    # 2. 行业K线（东财）
    time.sleep(0.5)
    kline = fetch_industry_kline(industry_name, period="daily", days=kline_days)
    if kline:
        # 计算涨幅统计
        closes = [k["close"] for k in kline if k.get("close")]
        trend_stats = {}
        if len(closes) >= 5:
            trend_stats["pct_chg_5d"] = round((closes[-1] / closes[-5] - 1) * 100, 2) if closes[-5] else None
        if len(closes) >= 20:
            trend_stats["pct_chg_20d"] = round((closes[-1] / closes[-20] - 1) * 100, 2) if closes[-20] else None
        if len(closes) >= 60:
            trend_stats["pct_chg_60d"] = round((closes[-1] / closes[0] - 1) * 100, 2) if closes[0] else None

        # 均线
        if len(closes) >= 5:
            trend_stats["ma5"] = round(sum(closes[-5:]) / 5, 2)
        if len(closes) >= 20:
            trend_stats["ma20"] = round(sum(closes[-20:]) / 20, 2)
        if len(closes) >= 60:
            trend_stats["ma60"] = round(sum(closes[-60:]) / 60, 2)

        # 均线排列判断
        ma5 = trend_stats.get("ma5", 0)
        ma20 = trend_stats.get("ma20", 0)
        ma60 = trend_stats.get("ma60", 0)
        if ma5 and ma20 and ma60:
            if ma5 > ma20 > ma60:
                trend_stats["ma_alignment"] = "多头排列"
            elif ma5 < ma20 < ma60:
                trend_stats["ma_alignment"] = "空头排列"
            else:
                trend_stats["ma_alignment"] = "交叉整理"

        results["price_trend"] = {
            "period": "daily",
            "days": len(kline),
            "latest_close": closes[-1] if closes else None,
            "stats": trend_stats,
            "kline": kline[-20:],  # 只返回最近 20 条 K 线，减少 JSON 体积
            "_source": "eastmoney",
        }
    else:
        errors["price_trend"] = f"行业K线获取失败: {industry_name}"

    # 3. 成份股 TOP N（东财）
    time.sleep(0.5)
    stocks = fetch_industry_constituents(industry_name, top_n=top_n)
    if stocks:
        results["top_stocks"] = {
            "by_market_cap": stocks,
            "count": len(stocks),
            "_source": "eastmoney",
        }
    else:
        errors["top_stocks"] = f"成份股获取失败: {industry_name}"

    # 4. 资金流向（东财）
    time.sleep(0.5)
    fund = fetch_industry_fund_flow(industry_name)
    if fund:
        results["fund_flow"] = fund
        results["fund_flow"]["_source"] = "eastmoney"
    else:
        errors["fund_flow"] = f"资金流向获取失败: {industry_name}"

    # 5. 自动保存估值快照到 DB（首次查询时自动保存）
    if "valuation" in results:
        try:
            _auto_save_snapshot(results["valuation"])
        except Exception as e:
            print(json.dumps({"warning": f"自动保存快照失败: {e}"}, ensure_ascii=False), file=sys.stderr)

    return {"results": results, "errors": errors}


def _auto_save_snapshot(valuation_data):
    """首次查询时自动保存估值快照到 DB。"""
    from industry_store import upsert_industry, save_valuation_snapshot
    today = datetime.now().strftime("%Y-%m-%d")
    name = valuation_data.get("name", "")
    sw_code = valuation_data.get("sw_code", "")
    if not name or not sw_code:
        return
    ind_id = upsert_industry(name, sw_code, sw_level=1)
    save_valuation_snapshot(
        industry_id=ind_id,
        snapshot_date=today,
        pe_static=valuation_data.get("pe_static"),
        pe_ttm=valuation_data.get("pe_ttm"),
        pb=valuation_data.get("pb"),
        dividend_yield=valuation_data.get("dividend_yield"),
        constituents=valuation_data.get("constituents"),
        source="legulegu",
    )


def mode_history(industry_name, days=756):
    """模式 3: 行业估值历史趋势（从 DB 读取）。"""
    try:
        from industry_store import get_industry_id, get_valuation_history, calc_percentile, get_latest_valuation
    except ImportError:
        return {"results": {}, "errors": {"history": "industry_store 模块不可用"}}

    ind_id = get_industry_id(industry_name)
    if not ind_id:
        return {"results": {}, "errors": {"history": f"行业 '{industry_name}' 不在 DB 中，请先运行 --mode snapshot"}}

    history = get_valuation_history(ind_id, days=days)
    latest = get_latest_valuation(ind_id)

    percentiles = {}
    if latest:
        for metric in ("pe_ttm", "pb", "dividend_yield"):
            val = latest.get(metric)
            if val is not None:
                pctile = calc_percentile(ind_id, metric, val, lookback_days=days)
                if pctile is not None:
                    percentiles[f"{metric}_percentile"] = pctile

    return {
        "results": {
            "industry": industry_name,
            "lookback_days": days,
            "data_points": len(history),
            "latest": latest,
            "percentiles": percentiles,
            "history": history,
        },
        "errors": {},
    }


def mode_snapshot(with_constituents=False):
    """模式 4: 保存当日 31 个行业估值快照到 DB。"""
    try:
        from industry_store import upsert_industry, save_valuation_batch, save_constituents_batch
    except ImportError:
        return {"results": {}, "errors": {"snapshot": "industry_store 模块不可用"}}

    df = fetch_sw_industries()
    if df is None:
        return {"results": {}, "errors": {"snapshot": "sw_index_first_info 返回空数据"}}

    industries = parse_sw_industries(df)
    today = datetime.now().strftime("%Y-%m-%d")

    # 保存行业基础信息 + 估值
    batch_rows = []
    for item in industries:
        ind_id = upsert_industry(item["name"], item["sw_code"], sw_level=1)
        batch_rows.append({
            "industry_id": ind_id,
            "pe_static": item.get("pe_static"),
            "pe_ttm": item.get("pe_ttm"),
            "pb": item.get("pb"),
            "dividend_yield": item.get("dividend_yield"),
            "constituents": item.get("constituents"),
            "source": "legulegu",
        })

    saved = save_valuation_batch(batch_rows, today)

    result = {
        "snapshot_date": today,
        "industries_saved": saved,
    }

    # 可选：保存成份股
    if with_constituents:
        from industry_store import get_industry_id
        cons_saved = 0
        cons_errors = []
        for item in industries:
            ind_id = get_industry_id(item["name"])
            if not ind_id:
                continue
            time.sleep(0.6)  # 东财反爬间隔
            stocks = fetch_industry_constituents(item["name"], top_n=20)
            if stocks:
                n = save_constituents_batch(ind_id, today, stocks, rank_by="market_cap")
                cons_saved += n
            else:
                cons_errors.append(item["name"])

        result["constituents_saved"] = cons_saved
        if cons_errors:
            result["constituents_errors"] = cons_errors

    return {"results": result, "errors": {}}


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="行业分析数据采集")
    parser.add_argument("--mode", required=True,
                        choices=["overview", "detail", "history", "snapshot"],
                        help="运行模式")
    parser.add_argument("--industry", type=str, default="",
                        help="行业名称（detail/history 模式必填）")
    parser.add_argument("--days", type=int, default=60,
                        help="K线天数(detail) 或历史天数(history)")
    parser.add_argument("--top", type=int, default=20,
                        help="成份股 TOP N")
    parser.add_argument("--with-constituents", action="store_true",
                        help="snapshot 模式下同时保存成份股")
    args = parser.parse_args()

    if args.mode in ("detail", "history") and not args.industry:
        print(json.dumps({
            "results": {},
            "errors": {"params": f"--industry 参数在 {args.mode} 模式下必填"},
        }, ensure_ascii=False))
        sys.exit(1)

    if args.mode == "overview":
        output = mode_overview()
    elif args.mode == "detail":
        output = mode_detail(args.industry, kline_days=args.days, top_n=args.top)
    elif args.mode == "history":
        output = mode_history(args.industry, days=args.days)
    elif args.mode == "snapshot":
        output = mode_snapshot(with_constituents=args.with_constituents)
    else:
        output = {"results": {}, "errors": {"mode": f"未知模式: {args.mode}"}}

    output["meta"] = {
        "mode": args.mode,
        "industry": args.industry or None,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    print(json.dumps(output, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
