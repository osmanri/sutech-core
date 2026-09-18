"""Telegram platform integration checks without network calls."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot import db
from bot.bot_setup import COMMANDS, configure_bot_profile, configure_user_menu
from bot.keyboards.inline import get_report_inline_keyboard


class BotPlatformTests(unittest.IsolatedAsyncioTestCase):
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

        self.assertIsNotNone(keyboard.inline_keyboard[0][0].web_app)
        self.assertIn("lang=ru", keyboard.inline_keyboard[0][0].web_app.url)


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
