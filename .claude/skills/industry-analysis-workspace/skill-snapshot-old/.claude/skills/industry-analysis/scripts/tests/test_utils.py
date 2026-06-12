"""Tests for safe_float and safe_call utilities."""
import math
import sys
import os
import time
import unittest

# allow importing utils.py from parent dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import safe_float, safe_call


class TestSafeFloat(unittest.TestCase):
    def test_normal_number(self):
        self.assertEqual(safe_float(22.3), 22.3)

    def test_none_returns_default(self):
        self.assertIsNone(safe_float(None))
        self.assertEqual(safe_float(None, default=0.0), 0.0)

    def test_nan_returns_default(self):
        self.assertIsNone(safe_float(float("nan")))

    def test_akshare_garbage_strings(self):
        for junk in ("", "-", "--", "nan", "  ", "\t"):
            self.assertIsNone(safe_float(junk), msg=f"junk={junk!r}")

    def test_numeric_string(self):
        self.assertEqual(safe_float("22.3"), 22.3)

    def test_rounding_to_4_decimals(self):
        self.assertEqual(safe_float(1.123456789), 1.1235)

    def test_invalid_string(self):
        self.assertIsNone(safe_float("abc"))

    def test_int_input(self):
        self.assertEqual(safe_float(42), 42.0)


class TestSafeCall(unittest.TestCase):
    def test_success_first_try(self):
        result = safe_call(lambda: 42, label="ok")
        self.assertEqual(result, 42)

    def test_retries_then_success(self):
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("transient")
            return "ok"

        result = safe_call(flaky, max_retries=2, base_wait=0.01, label="flaky")
        self.assertEqual(result, "ok")
        self.assertEqual(attempts["n"], 2)

    def test_exhausts_retries_returns_none(self):
        def always_fail():
            raise RuntimeError("nope")

        result = safe_call(always_fail, max_retries=2, base_wait=0.01, label="fail")
        self.assertIsNone(result)

    def test_kwargs_passed_to_fn(self):
        def fn(x, y=0):
            return x + y

        result = safe_call(fn, label="kwargs", _args=(2,), _kwargs={"y": 3})
        self.assertEqual(result, 5)


if __name__ == "__main__":
    unittest.main()
