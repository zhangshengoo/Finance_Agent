"""Defensive utils for industry-analysis skill.

Adapted from OpenClaw_FinRobot industry_analysis.py:55-92 (safe_float)
and shared/data_fetcher.py:52-100 (safe_call, renamed from _retry_call).
Minimal P0 subset; safe_int / normalize_stock_code / CircuitBreaker deferred to P2.
"""
import math
import random
import time


def safe_float(val, default=None):
    """Safely coerce to float, handling None / NaN / AKShare garbage strings.

    Returns:
        float rounded to 4 decimals, or `default` on failure.

    Handles AKShare quirks: "", "-", "--", "nan" all map to default.
    """
    try:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.strip()
            if val in ("", "-", "--", "nan"):
                return default
        f = float(val)
        return default if math.isnan(f) else round(f, 4)
    except (ValueError, TypeError):
        return default


def safe_call(fn, max_retries=2, base_wait=2.0, label="", _args=None, _kwargs=None):
    """Call fn with exponential backoff + jitter.

    Args:
        fn: zero-arg callable, or arbitrary callable when _args/_kwargs provided.
        max_retries: number of retries after the first attempt (total = max_retries + 1).
        base_wait: base delay; effective wait = base_wait * 2**attempt + uniform(0,1).
        label: free-form tag for logging only.
        _args: optional positional args tuple passed to fn.
        _kwargs: optional kwargs dict passed to fn.

    Returns:
        fn's return value on success, or None when all retries exhausted.
    """
    args = _args or ()
    kwargs = _kwargs or {}
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            # treat empty DataFrame as failure-with-no-exception (mirrors AKShare behavior)
            if result is not None and hasattr(result, "empty") and result.empty:
                last_exc = RuntimeError(f"{label}: empty result")
            else:
                return result
        except Exception as exc:
            last_exc = exc
        if attempt < max_retries:
            wait = base_wait * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait)
    # All retries exhausted; swallow and return None (caller checks for None and sets _source=unavailable)
    return None
