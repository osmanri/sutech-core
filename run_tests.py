"""Run the whole Python test suite with a dummy Telegram token (the old bot refuses to import without one).

    python run_tests.py            # everything
    python run_tests.py -k geocod  # extra unittest arguments are passed through
"""
import os
import sys
import unittest

os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN_NOT_REAL")

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "discover", "-s", os.path.dirname(os.path.abspath(__file__)), "-p", "test_*.py"] + sys.argv[1:]
    unittest.main(module=None)
