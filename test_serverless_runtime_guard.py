import ast
import unittest
from pathlib import Path

from bot.runtime_guard import assert_legacy_runtime_allowed


class ServerlessRuntimeGuardTests(unittest.TestCase):
    def test_default_start_cannot_modify_production_delivery(self):
        with self.assertRaisesRegex(RuntimeError, 'Telegram Serverless'):
            assert_legacy_runtime_allowed({})

    def test_only_explicit_operator_override_enables_recovery(self):
        for value in ('', 'true', 'yes', '0'):
            with self.assertRaises(RuntimeError):
                assert_legacy_runtime_allowed({'SU_TECH_ENABLE_LEGACY_BOT': value})
        assert_legacy_runtime_allowed({'SU_TECH_ENABLE_LEGACY_BOT': '1'})

    def test_guard_runs_before_database_bot_or_webhook_initialization(self):
        tree = ast.parse(Path(__file__).with_name('bot').joinpath('main.py').read_text(encoding='utf8'))
        entry = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'main')
        call = entry.body[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(call.func.id, 'assert_legacy_runtime_allowed')
