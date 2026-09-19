"""Telegram platform integration checks without network calls."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import db
from bot.bot_setup import COMMANDS, configure_bot_profile, configure_user_menu
from bot.keyboards.inline import get_report_inline_keyboard


class BotPlatformTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_identifies_calculation_revision_without_secrets(self):
        import json
        from bot.main import health_check
        from bot.water_balance import CALCULATION_VERSION
        with patch.dict('os.environ', {'RENDER_GIT_COMMIT': '0123456789abcdef'}):
            response = await health_check(None)
        data = json.loads(response.text)
        self.assertEqual(data['calculation_version'], CALCULATION_VERSION)
        self.assertEqual(data['revision'], '0123456789ab')
        self.assertEqual(set(data), {'status', 'service', 'updates', 'calculation_version', 'revision'})

    async def test_profile_commands_and_native_menu_are_configured(self):
        bot = SimpleNamespace(
            set_my_commands=AsyncMock(return_value=True),
            set_chat_menu_button=AsyncMock(return_value=True),
            set_my_name=AsyncMock(return_value=True),
            set_my_short_description=AsyncMock(return_value=True),
            set_my_description=AsyncMock(return_value=True),
        )

        await configure_bot_profile(bot)

        self.assertEqual(bot.set_my_commands.await_count, 3)
        self.assertEqual(bot.set_chat_menu_button.await_count, 1)
        self.assertEqual(bot.set_my_name.await_count, 2)
        self.assertEqual(bot.set_my_short_description.await_count, 2)
        self.assertEqual(bot.set_my_description.await_count, 2)
        self.assertEqual(
            [command.command for command in COMMANDS["ru"]],
            ["start", "app", "history", "language", "help", "about"],
        )

    async def test_language_selection_updates_personal_menu(self):
        bot = SimpleNamespace(set_chat_menu_button=AsyncMock(return_value=True))

        await configure_user_menu(bot, chat_id=42, lang="kz")

        call = bot.set_chat_menu_button.await_args
        self.assertEqual(call.kwargs["chat_id"], 42)
        self.assertIn("lang=kz", call.kwargs["menu_button"].web_app.url)

    async def test_report_has_new_calculation_webapp_button(self):
        keyboard = get_report_inline_keyboard("ru")

        buttons = [button for row in keyboard.inline_keyboard for button in row]
        launcher = next(button for button in buttons if button.web_app)
        self.assertIn("lang=ru", launcher.web_app.url)
        self.assertTrue(any((button.callback_data or '').startswith('explain:') for button in buttons))


class UserLanguagePersistenceTests(unittest.TestCase):
    def test_language_survives_memory_reset(self):
        old_path = db.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                db.DB_PATH = str(Path(directory) / "history.db")
                db.init_db()
                db.set_user_language(42, "kz")
                self.assertEqual(db.get_user_language(42), "kz")
        finally:
            db.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
