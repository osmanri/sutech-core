"""Farmer-facing request races; Telegram and the AI provider stay mocked."""
import asyncio
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, User

from bot.handlers import agronomist as handler
from bot.handlers import start
from bot.services.agronomist import AgronomistService


class BotResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = Bot('123456:TEST_TOKEN')
        self.user = User(id=99341, is_bot=False, first_name='Farmer')
        self.chat = Chat(id=self.user.id, type='private')
        self.state = FSMContext(MemoryStorage(), StorageKey(
            bot_id=self.bot.id, chat_id=self.user.id, user_id=self.user.id))
        await self.state.set_state(handler.AgronomistChat.active)
        self.client = SimpleNamespace(configured=True, generate=AsyncMock(return_value='Проверьте почву.'))
        self.service = AgronomistService(self.client, cooldown=0)
        self.methods = []
        self.patches = [patch.object(handler, 'assistant', self.service),
                        patch.object(handler, 'get_lang', return_value='ru'),
                        patch.object(Bot, '__call__', new=AsyncMock(side_effect=self.transport))]
        for p in self.patches:
            p.start()

    async def transport(self, method, **kwargs):
        self.methods.append(method)
        if type(method).__name__.startswith(('Send', 'EditMessage')):
            return Message(message_id=getattr(method, 'message_id', None) or 50,
                date=datetime.now(timezone.utc), chat=self.chat,
                from_user=User(id=self.bot.id, is_bot=True, first_name='Su-Tech'),
                text=getattr(method, 'text', None),
                reply_markup=(method.reply_markup if isinstance(getattr(method, 'reply_markup', None),
                                                               InlineKeyboardMarkup) else None)).as_(self.bot)
        return True

    def message(self, text='Как поливать томат?'):
        return Message(message_id=12, date=datetime.now(timezone.utc),
            chat=self.chat, from_user=self.user, text=text).as_(self.bot)

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        handler.active_status_events.pop(self.user.id, None)
        await self.state.clear()
        await self.bot.session.close()

    async def test_answer_keeps_visible_back_navigation(self):
        await handler.ask_ai(self.message(), self.state)
        result = next(m for m in self.methods if getattr(m, 'text', None) == 'Проверьте почву.')
        self.assertIsNotNone(result.reply_markup, 'The answer must not leave the farmer without Back')
        actions = {b.callback_data for row in result.reply_markup.inline_keyboard for b in row}
        self.assertIn('ai_nav:menu', actions)
        self.assertIn('ai_nav:exit', actions)

    async def test_loading_keeps_visible_exit(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return 'Проверьте почву.'
        self.client.generate.side_effect = delayed
        pending = asyncio.create_task(handler.ask_ai(self.message(), self.state))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            status = next(m for m in self.methods if getattr(m, 'text', None) == handler.ai_text('ru', 'thinking'))
            self.assertIsNotNone(status.reply_markup, 'A slow answer must have a visible way to leave')
        finally:
            release.set()
            await pending

    async def test_total_deadline_returns_actionable_error_and_releases_next_question(self):
        async def delayed(*args, **kwargs):
            await asyncio.Event().wait()
        self.client.generate.side_effect = delayed
        with patch.object(handler, 'AI_REQUEST_TIMEOUT', .03):
            await asyncio.wait_for(handler.ask_ai(self.message(), self.state), 1)
        error = next(m for m in self.methods if getattr(m, 'text', None) == handler.ai_text('ru', 'timeout'))
        self.assertIsNotNone(error.reply_markup)
        self.assertFalse(self.service.sessions[self.user.id].busy)
        self.client.generate.side_effect = None
        await handler.ask_ai(self.message(), self.state)
        self.assertEqual(self.client.generate.await_count, 2)

    async def test_second_question_cannot_overwrite_inflight_card(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return 'Проверьте почву.'
        self.client.generate.side_effect = delayed
        first = asyncio.create_task(handler.ask_ai(self.message(), self.state))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            before = len(self.methods)
            await handler.ask_ai(self.message('А когда поливать?'), self.state)
            self.assertEqual(len(self.methods), before, 'A duplicate must not overwrite the first loading card')
            self.assertEqual(self.client.generate.await_count, 1)
        finally:
            release.set()
            await first

    async def test_navigation_releases_provider_and_suppresses_late_answer(self):
        entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def delayed(*args, **kwargs):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return 'OLD ANSWER'
        self.client.generate.side_effect = delayed
        pending = asyncio.create_task(handler.ask_ai(self.message(), self.state))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            card = Message(message_id=50, date=datetime.now(timezone.utc), chat=self.chat,
                from_user=User(id=self.bot.id, is_bot=True, first_name='Su-Tech')).as_(self.bot)
            callback = CallbackQuery(id='back', from_user=self.user, chat_instance='test',
                message=card, data='ai_nav:menu').as_(self.bot)
            await handler.ai_navigation(callback, self.state)
            await asyncio.sleep(.03)
            self.assertTrue(cancelled.is_set(), 'Navigation must release a slow provider request immediately')
            self.assertTrue(pending.done(), 'Old requests must not block a new question')
            self.assertFalse(any(getattr(m, 'text', None) == 'OLD ANSWER' for m in self.methods))
            self.assertFalse(self.service.sessions[self.user.id].busy)
            self.client.generate.side_effect = None
            await handler.ask_ai(self.message(), self.state)
            self.assertEqual(self.client.generate.await_count, 2)
        finally:
            release.set()
            await pending

    def test_farmer_menu_has_no_advanced_mode_and_loading_copy_is_localized(self):
        for lang in ('ru', 'kz', 'en'):
            actions = {b.callback_data for row in handler.chat_keyboard(lang).inline_keyboard for b in row}
            self.assertNotIn('ai_nav:deep', actions)
            self.assertNotIn('ai_nav:plan', actions)
            for key in ('still_working', 'cancel_button', 'timeout'):
                self.assertTrue(handler.ai_text(lang, key))
                if lang != 'ru':
                    self.assertNotEqual(handler.ai_text(lang, key), handler.ai_text('ru', key))

    async def test_slow_history_read_does_not_freeze_other_chat_updates(self):
        release = threading.Event()
        read_finished_without_blocking = []
        def read_history(user_id):
            read_finished_without_blocking.append(release.wait(.2))
            return []
        async def another_chat():
            await asyncio.sleep(.01)
            release.set()
        with patch.object(start, 'get_user_history', side_effect=read_history), \
             patch.object(start, 'get_lang', return_value='ru'):
            await asyncio.gather(start.show_history(self.message()), another_chat())
        self.assertEqual(read_finished_without_blocking, [True],
                         'Database latency for history must not freeze the bot event loop')


if __name__ == '__main__':
    unittest.main()
