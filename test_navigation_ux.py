"""Small farmer-facing keyboard contract: essential actions stay visible."""

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Chat, Message, Update, User

from bot.ai_i18n import ai_text
from bot.keyboards.reply import get_main_reply_keyboard, get_more_reply_keyboard
from bot.handlers.agronomist import chat_keyboard
from bot.i18n import t
from bot.handlers import agronomist, start
from bot.services.agronomist import AgronomistService
from test_bot_platform import shared_test_dispatcher


class NavigationUXTests(unittest.TestCase):
    @staticmethod
    def texts(markup):
        return [button.text for row in markup.keyboard for button in row]

    def test_main_menu_has_only_daily_actions(self):
        for lang in ("ru", "kz", "en"):
            markup = get_main_reply_keyboard(lang)
            texts = self.texts(markup)
            self.assertEqual(len(markup.keyboard), 4)
            self.assertIn(t(lang, "btn_webapp"), texts)
            self.assertIn(ai_text(lang, "button"), texts)
            self.assertIn(t(lang, "btn_fields"), texts)
            self.assertIn(t(lang, "btn_history"), texts)
            self.assertIn(t(lang, "btn_more"), texts)
            self.assertNotIn(t(lang, "btn_help"), texts)
            self.assertNotIn(t(lang, "btn_about"), texts)

    def test_more_menu_has_back_and_infrequent_actions(self):
        for lang in ("ru", "kz", "en"):
            texts = self.texts(get_more_reply_keyboard(lang))
            self.assertIn(t(lang, "btn_back"), texts)
            self.assertIn(t(lang, "btn_lang"), texts)
            self.assertIn(t(lang, "btn_help"), texts)
            self.assertIn(t(lang, "btn_about"), texts)

    def test_ai_chat_has_one_back_button_and_no_deep_mode_clutter(self):
        for lang in ("ru", "kz", "en"):
            texts = self.texts(chat_keyboard(lang))
            self.assertIn(ai_text(lang, "photo_button"), texts)
            self.assertIn(ai_text(lang, "water_button"), texts)
            self.assertIn(ai_text(lang, "care_button"), texts)
            self.assertIn(ai_text(lang, "calculate_button"), texts)
            self.assertIn(ai_text(lang, "history_button"), texts)
            self.assertIn(ai_text(lang, "new_button"), texts)
            self.assertIn(ai_text(lang, "exit_button"), texts)
            self.assertNotIn(ai_text(lang, "deep_button"), texts)
            self.assertEqual(texts.count(ai_text(lang, "new_button")), 1)


class NavigationRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot(token="123456:ABC")
        self.dispatcher = shared_test_dispatcher()
        self.user_id = 981234
        self.state = self.dispatcher.fsm.get_context(
            bot=self.bot, chat_id=self.user_id, user_id=self.user_id)
        await self.state.clear()
        self.lang = "ru"
        self.client = SimpleNamespace(configured=True,
            generate=AsyncMock(return_value="Assessment"))
        self.service = AgronomistService(self.client, cooldown=0)
        self.patches = [
            patch.object(agronomist, "assistant", self.service),
            patch.object(agronomist, "get_lang", side_effect=lambda _: self.lang),
            patch.object(start, "get_lang", side_effect=lambda _: self.lang),
            patch.object(agronomist, "set_lang", side_effect=self.select_language),
            patch.object(start, "set_lang", side_effect=self.select_language),
            patch.object(start, "configure_user_menu", new_callable=AsyncMock),
            patch.object(agronomist, "configure_user_menu", new_callable=AsyncMock),
            patch.object(Bot, "__call__", new_callable=AsyncMock),
        ]
        self.mocks = [p.start() for p in self.patches]
        self.transport = self.mocks[-1]

    def select_language(self, user_id, lang):
        self.assertEqual(user_id, self.user_id)
        self.lang = lang

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        await self.state.clear()
        await self.bot.session.close()

    async def send(self, text):
        self.transport.reset_mock()
        message = Message(message_id=1, date=datetime.now(timezone.utc),
            chat=Chat(id=self.user_id, type="private"),
            from_user=User(id=self.user_id, is_bot=False, first_name="Farmer"), text=text)
        await self.dispatcher.feed_update(self.bot, Update(update_id=9001, message=message))
        return [call.args[0] for call in self.transport.await_args_list
                if type(call.args[0]).__name__ == "SendMessage"]

    async def test_site_language_reaches_ai_intro_keyboard_and_model(self):
        for lang in ("kz", "en", "ru"):
            with self.subTest(lang=lang):
                messages = await self.send(f"/start ai_{lang}")
                self.assertEqual(self.lang, lang)
                self.assertEqual(messages[-1].text, ai_text(lang, "intro"))
                self.assertIn(ai_text(lang, "exit_button"),
                              NavigationUXTests.texts(messages[-1].reply_markup))
                await self.send("Томаттағы дақтар / tomato leaf spots / пятна на томате")
                self.assertEqual(self.client.generate.await_args.args[2], lang)
                messages = await self.send(ai_text(lang, "exit_button"))
                self.assertIsNone(await self.state.get_state())
                self.assertIn(t(lang, "btn_more"),
                              NavigationUXTests.texts(messages[-1].reply_markup))

    async def test_more_back_and_ai_exit_never_spend_provider_quota(self):
        for lang in ("ru", "kz", "en"):
            self.lang = lang
            await self.send("/ai")
            messages = await self.send(t(lang, "btn_more"))
            self.assertIsNone(await self.state.get_state())
            self.assertIn(t(lang, "btn_back"),
                          NavigationUXTests.texts(messages[-1].reply_markup))
            messages = await self.send(t(lang, "btn_back"))
            self.assertIn(t(lang, "btn_more"),
                          NavigationUXTests.texts(messages[-1].reply_markup))
            self.assertFalse(await self.service.is_active(self.user_id))
        self.client.generate.assert_not_awaited()

    async def test_localized_ai_button_overrides_old_bot_language(self):
        for lang in ("kz", "en", "ru"):
            self.lang = "ru"
            messages = await self.send(ai_text(lang, "button"))
            self.assertEqual(self.lang, lang)
            self.assertEqual(messages[-1].text, ai_text(lang, "intro"))
        self.client.generate.assert_not_awaited()

    async def test_browser_calculator_entry_keeps_selected_language(self):
        for lang in ("ru", "kz", "en"):
            messages = await self.send(f"/start app_{lang}")
            self.assertEqual(self.lang, lang)
            self.assertEqual(messages[-1].text, t(lang, "app_prompt"))
            app = next(button.web_app for row in messages[-1].reply_markup.keyboard
                       for button in row if button.web_app)
            self.assertIn(f"lang={lang}", app.url)


if __name__ == "__main__":
    unittest.main()
