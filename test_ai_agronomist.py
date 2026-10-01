"""AI integration checks; all Gemini and Telegram traffic is mocked."""

import asyncio
import base64
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.types import Chat, Message, PhotoSize, Update, User, WebAppData

from bot.ai_i18n import AI_STRINGS, ai_text
from bot.handlers import agronomist as handler
from bot.keyboards.reply import get_main_reply_keyboard
from bot.services.agronomist import (AIError, AgronomistService, GeminiClient,
                                    LimitedImageBuffer, MAX_HISTORY_MESSAGES,
                                    MAX_IMAGE_BYTES, MAX_SESSIONS, image_mime)
from test_bot_platform import shared_test_dispatcher

JPEG = b"\xff\xd8\xff\xe0test-photo"


class Response:
    def __init__(self, data, status=200):
        self.data, self.status = data, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.data


class Session(Response):
    def __init__(self, response):
        super().__init__(None)
        self.post = unittest.mock.Mock(return_value=response)


class GeminiTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_request_uses_key_header_and_inline_bytes(self):
        session = Session(Response({"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": "Возможный дефицит воды."}]}}]}))
        client = GeminiClient("private-test-key")
        with patch("bot.services.agronomist.aiohttp.ClientSession", return_value=session):
            result = await client.generate([], "Пшеница", "ru", JPEG)
        args, kwargs = session.post.call_args
        self.assertNotIn(client.api_key, args[0])
        self.assertIn('/models/gemini-3.5-flash-lite:generateContent', args[0])
        config = kwargs['json']['generationConfig']
        self.assertEqual(config['thinkingConfig']['thinkingLevel'], 'LOW')
        self.assertNotIn('temperature', config)
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], client.api_key)
        parts = kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(base64.b64decode(parts[0]["inlineData"]["data"]), JPEG)
        self.assertIn("Russian", kwargs["json"]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(result, "Возможный дефицит воды.")

    async def test_signed_followup_context_is_preserved_without_showing_thoughts(self):
        signed_parts = [{"text": "Internal reasoning", "thought": True,
                         "thoughtSignature": "opaque-signature"},
                        {"text": "Проверьте влажность почвы."}]
        session = Session(Response({"candidates": [{"finishReason": "STOP", "content": {
            "parts": signed_parts}}]}))
        service = AgronomistService(GeminiClient("private-test-key"), cooldown=0)
        with patch("bot.services.agronomist.aiohttp.ClientSession", return_value=session):
            answer = await service.reply(1, "Лист желтеет", "ru", JPEG)
            self.assertEqual(answer, "Проверьте влажность почвы.")
            await service.reply(1, "Как проверить?", "ru")
        contents = session.post.call_args.kwargs['json']['contents']
        self.assertEqual(contents[1]['parts'], signed_parts)
        self.assertNotIn('inlineData', str(contents))

    async def test_older_model_override_keeps_compatible_generation_parameters(self):
        session = Session(Response({"candidates": [{"content": {"parts": [{"text": "Ответ"}]}}]}))
        with patch("bot.services.agronomist.aiohttp.ClientSession", return_value=session):
            await GeminiClient("test", "gemini-2.5-flash-lite").generate([], "Вопрос", "ru")
        config = session.post.call_args.kwargs['json']['generationConfig']
        self.assertNotIn('thinkingConfig', config)
        self.assertEqual(config['maxOutputTokens'], 1200)

    async def test_quota_auth_empty_and_blocked_answers_are_safe_errors(self):
        for status, data, code in (
            (429, {"secret": "do-not-show"}, "quota"),
            (403, {"secret": "do-not-show"}, "configuration"),
            (503, {}, "unavailable"),
            (200, {"candidates": []}, "no_answer"),
            (200, {"candidates": [{"finishReason": "SAFETY"}]}, "no_answer"),
        ):
            with self.subTest(status=status, code=code):
                with patch("bot.services.agronomist.aiohttp.ClientSession",
                           return_value=Session(Response(data, status))):
                    with self.assertRaises(AIError) as error:
                        await GeminiClient("test").generate([], "Вопрос", "ru")
                self.assertEqual(error.exception.code, code)
                self.assertNotIn("do-not-show", str(error.exception))

    async def test_timeout_returns_retry_message_code(self):
        session = Session(None)
        session.post.side_effect = asyncio.TimeoutError()
        with patch("bot.services.agronomist.aiohttp.ClientSession", return_value=session):
            with self.assertRaises(AIError) as error:
                await GeminiClient("test").generate([], "Вопрос", "ru")
        self.assertEqual(error.exception.code, "unavailable")

    async def test_missing_key_does_not_call_provider(self):
        with patch("bot.services.agronomist.aiohttp.ClientSession") as factory:
            with self.assertRaises(AIError) as error:
                await GeminiClient("").generate([], "Вопрос", "ru")
        self.assertEqual(error.exception.code, "not_configured")
        factory.assert_not_called()

    def test_images_and_download_buffer_are_bounded(self):
        self.assertEqual(image_mime(JPEG), "image/jpeg")
        self.assertEqual(image_mime(b"\x89PNG\r\n\x1a\nrest"), "image/png")
        for bad in (b"%PDF", b"", b"x" * (MAX_IMAGE_BYTES + 1)):
            with self.assertRaises(AIError):
                image_mime(bad)
        with LimitedImageBuffer() as buffer:
            buffer.write(b"x" * MAX_IMAGE_BYTES)
            with self.assertRaises(AIError):
                buffer.write(b"x")


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def service(self, **kwargs):
        self.client = SimpleNamespace(configured=True, generate=AsyncMock(return_value="Ответ"))
        return AgronomistService(self.client, cooldown=0, **kwargs)

    async def test_followups_are_isolated_bounded_and_photos_not_retained(self):
        service = self.service(user_daily_limit=30)
        await service.reply(1, "Фото пшеницы", "ru", JPEG)
        await service.reply(1, "А что проверить?", "ru")
        self.assertIn("Ответ", str(self.client.generate.await_args.args[0]))
        self.assertNotIn("inlineData", str(service.sessions))
        self.assertNotIn(base64.b64encode(JPEG).decode(), str(service.sessions))
        await service.reply(2, "Другой фермер", "en")
        self.assertEqual(self.client.generate.await_args.args[0], [])
        for i in range(12):
            await service.reply(1, f"Вопрос {i}", "ru")
        self.assertEqual(len(service.sessions[1].history), MAX_HISTORY_MESSAGES)
        await service.reply(1, "Новое растение", "ru", JPEG)
        self.assertEqual(self.client.generate.await_args.args[0], [])

    async def test_daily_limit_survives_new_chat_and_is_global(self):
        service = self.service(user_daily_limit=1, daily_limit=2)
        await service.reply(1, "Вопрос", "ru")
        service.clear(1)
        with self.assertRaises(AIError) as error:
            await service.reply(1, "Обход лимита", "ru")
        self.assertEqual(error.exception.code, "daily_limit")
        await service.reply(2, "Вопрос", "ru")
        with self.assertRaises(AIError):
            await service.reply(3, "Третий фермер", "ru")

    async def test_parallel_requests_and_reset_cancel_old_result(self):
        service = self.service()
        ready, release = asyncio.Event(), asyncio.Event()

        async def generate(*args):
            ready.set()
            await release.wait()
            return "Старый ответ"

        self.client.generate.side_effect = generate
        task = asyncio.create_task(service.reply(1, "Фото", "ru", JPEG))
        await ready.wait()
        with self.assertRaises(AIError) as error:
            await service.reply(1, "Второй", "ru")
        self.assertEqual(error.exception.code, "busy")
        service.clear(1)
        release.set()
        with self.assertRaises(AIError) as error:
            await task
        self.assertEqual(error.exception.code, "cancelled")
        self.assertEqual(service.sessions[1].history, [])

    async def test_session_cache_has_ttl_and_capacity(self):
        service = self.service(user_daily_limit=1000, daily_limit=1000)
        for uid in range(MAX_SESSIONS + 2):
            await service.reply(uid, "Вопрос", "ru")
        self.assertEqual(len(service.sessions), MAX_SESSIONS)
        self.assertNotIn(0, service.sessions)
        for session in service.sessions.values():
            session.touched -= 1801
        await service.reply(999, "Вопрос", "ru")
        self.assertEqual(list(service.sessions), [999])


class TelegramAITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot(token="123456:ABC")
        self.dp = shared_test_dispatcher()
        self.user = User(id=812, is_bot=False, first_name="Farmer")
        self.chat = Chat(id=812, type="private")
        self.state = self.dp.fsm.get_context(bot=self.bot, chat_id=812, user_id=812)
        await self.state.clear()
        self.client = SimpleNamespace(configured=True, generate=AsyncMock(return_value="<b>Ответ</b>"))
        self.service = AgronomistService(self.client, cooldown=0)
        self.patcher = patch.object(handler, "assistant", self.service)
        self.patcher.start()
        self.lang_patch = patch.object(handler, "get_lang", return_value="ru")
        self.lang_patch.start()

    async def asyncTearDown(self):
        self.patcher.stop()
        self.lang_patch.stop()
        await self.state.clear()
        await self.bot.session.close()

    async def send(self, **kwargs):
        message = Message(message_id=1, date=datetime.now(timezone.utc),
                          chat=self.chat, from_user=self.user, **kwargs)
        await self.dp.feed_update(self.bot, Update(update_id=801, message=message))

    async def test_ai_command_text_photo_followup_and_exit_routing(self):
        with patch.object(Bot, "__call__", new_callable=AsyncMock) as transport, \
             patch.object(Bot, "download", new_callable=AsyncMock) as download:
            async def fill(*args, destination, **kwargs):
                destination.write(JPEG)
                return destination
            download.side_effect = fill
            await self.send(text="/ai")
            self.assertEqual(await self.state.get_state(), handler.AgronomistChat.active.state)
            await self.send(text="Как поливать?")
            self.assertEqual(self.client.generate.await_count, 1)
            answers = [call.args[0] for call in transport.await_args_list
                       if type(call.args[0]).__name__ == "SendMessage"]
            response = next(answer for answer in answers if answer.text == "<b>Ответ</b>")
            self.assertIsNone(response.parse_mode)
            await self.send(photo=[PhotoSize(file_id="photo", file_unique_id="p", width=500,
                                            height=500, file_size=len(JPEG))], caption="Пшеница")
            self.assertEqual(self.client.generate.await_args.args[3], JPEG)
            await self.send(text="/newchat")
            self.assertNotIn(812, self.service.sessions)
            await self.send(text="/help")
            self.assertIsNone(await self.state.get_state())
            self.assertEqual(self.client.generate.await_count, 2)

    async def test_direct_photo_starts_chat_and_missing_key_preserves_menu(self):
        self.client.configured = False
        with patch.object(Bot, "__call__", new_callable=AsyncMock) as transport:
            await self.send(photo=[PhotoSize(file_id="p", file_unique_id="p", width=200,
                                            height=200)])
        self.client.generate.assert_not_called()
        self.assertIsNone(await self.state.get_state())
        answer = transport.await_args.args[0]
        self.assertIn("GEMINI_API_KEY", answer.text)
        self.assertIsNotNone(answer.reply_markup)

    async def test_quick_actions_show_guidance_without_spending_quota(self):
        with patch.object(Bot, "__call__", new_callable=AsyncMock):
            for topic in ("photo", "water", "care"):
                await self.send(text=ai_text("ru", topic + "_button"))
                self.assertEqual((await self.state.get_data())["ai_topic"], topic)
        self.client.generate.assert_not_called()
        self.assertEqual(len(self.service.requests), 0)

    async def test_photo_action_waits_for_image_and_water_action_sets_context(self):
        with patch.object(Bot, "__call__", new_callable=AsyncMock):
            await self.send(text=ai_text("ru", "photo_button"))
            await self.send(text="Томат")
            self.client.generate.assert_not_called()
            await self.send(text=ai_text("ru", "water_button"))
            await self.send(text="Томат, суглинок, 30 дней")
        text = self.client.generate.await_args.args[1]
        self.assertIn("поливе", text)
        self.assertIn("Томат", text)
        self.assertIsNone((await self.state.get_data()).get("ai_topic"))

    async def test_app_deep_link_opens_ai_instead_of_language_picker(self):
        with patch.object(Bot, "__call__", new_callable=AsyncMock) as transport:
            await self.send(text="/start ai")
        self.assertEqual(await self.state.get_state(), handler.AgronomistChat.active.state)
        self.assertEqual(transport.await_args.args[0].text, ai_text("ru", "intro"))

    async def test_deep_button_is_one_request_mode_and_history_does_not_spend_quota(self):
        deep = SimpleNamespace(configured=True, model="gemini-3.8-flash",
                               generate=AsyncMock(return_value="Глубокий ответ"))
        self.service.deep_client = deep
        with patch.object(Bot, "__call__", new_callable=AsyncMock):
            await self.send(text=ai_text("ru", "deep_button"))
            self.assertTrue((await self.state.get_data())["ai_deep"])
            await self.send(text="Пятна на томате")
            deep.generate.assert_awaited_once()
            self.client.generate.assert_not_called()
            self.assertFalse((await self.state.get_data())["ai_deep"])
            await self.send(text=ai_text("ru", "history_button"))
            deep.generate.assert_awaited_once()
            await self.send(text="Что проверить?")
            self.client.generate.assert_awaited_once()

    async def test_history_card_keeps_full_text_without_telegram_html_parsing(self):
        self.service.history_page = AsyncMock(return_value={"total": 2, "offset": 0,
            "entry": {"created_at": 1790850000000, "question": "<crop>" * 300,
                      "answer": "<answer>" * 400, "has_image": 1}})
        with patch.object(Bot, "__call__", new_callable=AsyncMock) as transport:
            await self.send(text="/aihistory")
        answers = [call.args[0] for call in transport.await_args_list
                   if type(call.args[0]).__name__ == "SendMessage"]
        self.assertEqual(len(answers), 2)
        self.assertIn("<crop>" * 300, answers[0].text)
        self.assertIn("<answer>" * 400, answers[1].text)
        self.assertTrue(all(len(answer.text) <= 4096 and answer.parse_mode is None for answer in answers))
        self.service.history_page.assert_awaited_once_with(812, 0)

    def test_chat_keyboard_has_photo_topics_calculator_and_placeholder(self):
        for lang in ("ru", "kz", "en"):
            keyboard = handler.chat_keyboard(lang)
            self.assertEqual(keyboard.input_field_placeholder, ai_text(lang, "placeholder"))
            buttons = [button for row in keyboard.keyboard for button in row]
            self.assertIn(ai_text(lang, "photo_button"), [button.text for button in buttons])
            app = next(button for button in buttons if button.web_app)
            self.assertIn("lang=" + lang, app.web_app.url)

    async def test_webapp_submission_is_not_swallowed_by_ai_chat(self):
        await self.state.set_state(handler.AgronomistChat.active)
        with patch.object(Bot, "__call__", new_callable=AsyncMock) as transport:
            await self.send(web_app_data=WebAppData(data="{}", button_text="Su-Tech"))
        self.client.generate.assert_not_called()
        texts = [call.args[0].text for call in transport.await_args_list
                 if type(call.args[0]).__name__ == "SendMessage"]
        self.assertTrue(texts)
        self.assertNotIn(ai_text("ru", "unsupported"), texts)

    def test_all_languages_have_complete_copy_and_menu_entry(self):
        for lang in ("ru", "kz", "en"):
            self.assertEqual(set(AI_STRINGS[lang]), set(AI_STRINGS["ru"]))
            buttons = [button.text for row in get_main_reply_keyboard(lang).keyboard for button in row]
            self.assertIn(ai_text(lang, "button"), buttons)


if __name__ == "__main__":
    unittest.main()
