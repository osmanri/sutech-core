"""Exercise saved-field refresh with real calculation/storage and mocked external services."""
import asyncio
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User

from bot import db
from bot.chat_screens import ChatScreens, ChatScreenMiddleware
from bot.field_service import persist_webapp_field
from bot.field_state import get_field, list_daily_balances, record_irrigation
from bot.handlers import fields as handler
from bot.i18n import t
from bot.keyboards.fields_kb import get_field_card_keyboard
from bot.keyboards.inline import get_report_inline_keyboard
from bot.services.field_manager import FieldService
from bot.water_balance import calculate_balance, parse_field
from test_water_balance import payload


class SavedFieldRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bot = Bot('123456:TEST_TOKEN')
        self.user = User(id=77451, is_bot=False, first_name='Farmer')
        self.chat = Chat(id=self.user.id, type='private')
        self.state = FSMContext(MemoryStorage(), StorageKey(
            bot_id=self.bot.id, chat_id=self.user.id, user_id=self.user.id))
        self.methods = []
        self.weather = {'date': date.today().isoformat(), 'timezone': 'Asia/Qyzylorda', 'et0': 5, 'rain': 0}
        self.patches = [patch.object(db, 'DB_PATH', str(Path(self.temp.name) / 'fields.db')),
                        patch.object(db, 'DATABASE_URL', ''),
                        patch.dict('os.environ', {'DATABASE_URL': ''}),
                        patch.object(handler, 'get_lang', return_value='ru'),
                        patch.object(Bot, '__call__', new=AsyncMock(side_effect=self.transport))]
        for p in self.patches:
            p.start()
        db.init_db()
        self.field_id = await self.save_field()

    async def save_field(self, **changes):
        data = payload(area=.1, day_of_growth=60, moisture_condition='normal', **changes)
        field = parse_field(data)
        return await persist_webapp_field(self.user.id, data, field, 44.85, 65.49,
            calculate_balance(field, self.weather['et0'], self.weather['rain']), self.weather)

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

    def callback(self, data=None, user=None):
        message = Message(message_id=50, date=datetime.now(timezone.utc), chat=self.chat,
            from_user=User(id=self.bot.id, is_bot=True, first_name='Su-Tech'), text='Saved field').as_(self.bot)
        return CallbackQuery(id=f'click-{len(self.methods)}', from_user=user or self.user,
            chat_instance='test', message=message,
            data=data or f'field:update:{self.field_id}').as_(self.bot)

    def edits(self):
        return [m for m in self.methods if type(m).__name__ == 'EditMessageText']

    async def asyncTearDown(self):
        handler.stop_field_refresh(self.user.id)
        await self.state.clear()
        await self.bot.session.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    async def test_refresh_uses_saved_settings_and_localized_compact_result_with_owned_explanation(self):
        for lang in ('ru', 'kz', 'en'):
            self.methods.clear()
            with patch.object(handler, 'get_lang', return_value=lang), \
                 patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=self.weather)) as fetch:
                await handler.callback_update_field(self.callback(), self.state)
            fetch.assert_awaited_once_with(44.85, 65.49)
            self.assertEqual(len(self.edits()), 2)
            result = self.edits()[-1]
            self.assertIn(t(lang, 'decision_irrigate'), result.text)
            self.assertIn(date.today().strftime('%d.%m.%Y'), result.text)
            self.assertNotIn('TAW', result.text)
            self.assertEqual(result.message_id, 50)
            buttons = [b for row in result.reply_markup.inline_keyboard for b in row]
            explanation_id = next(b.callback_data.split(':', 1)[1] for b in buttons if b.callback_data.startswith('explain:'))
            self.assertIn('TAW', db.get_report_explanation(explanation_id, self.user.id))
            self.assertIsNone(db.get_report_explanation(explanation_id, self.user.id + 1))
            self.assertIn(f'field:update:{self.field_id}', {b.callback_data for b in buttons})
            self.assertFalse(any(b.web_app for b in buttons), 'Refreshing must not reopen the setup form')
            self.assertFalse(any(type(m).__name__ == 'SendMessage' for m in self.methods))

    async def test_repeated_refresh_preserves_balance_and_history(self):
        before = list_daily_balances(self.field_id, user_id=self.user.id)
        deficit = get_field(self.field_id)['accumulated_deficit']
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=self.weather)):
            for _ in range(3):
                await handler.callback_update_field(self.callback(), self.state)
        self.assertEqual(list_daily_balances(self.field_id, user_id=self.user.id), before)
        self.assertEqual(get_field(self.field_id)['accumulated_deficit'], deficit)

    async def test_recorded_irrigation_is_not_overwritten_by_old_daily_recommendation(self):
        before = list_daily_balances(self.field_id, user_id=self.user.id)
        record_irrigation(self.field_id, user_id=self.user.id)
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=self.weather)):
            await handler.callback_update_field(self.callback(), self.state)
        result = self.edits()[-1]
        self.assertIn(t('ru', 'decision_deferred'), result.text)
        self.assertIn('0 м³', result.text)
        self.assertIn('Учтен отмеченный полив', result.text)
        buttons = {b.callback_data for row in result.reply_markup.inline_keyboard for b in row}
        self.assertNotIn(f'field:water:{self.field_id}', buttons)
        self.assertEqual(get_field(self.field_id)['accumulated_deficit'], 0)
        self.assertEqual(list_daily_balances(self.field_id, user_id=self.user.id), before)

    async def test_greenhouse_refresh_does_not_apply_configured_indoor_et0_after_irrigation(self):
        greenhouse_id = await self.save_field(field_type='greenhouse', greenhouse_et0=10)
        record_irrigation(greenhouse_id, user_id=self.user.id)
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=self.weather)):
            _, field, result, _ = await FieldService.recommendation_today(greenhouse_id, self.user.id)
        self.assertEqual(field.greenhouse_et0, 10)
        self.assertEqual(result['etc'], 0)
        self.assertEqual(result['gross_m3'], 0)
        self.assertEqual(result['deficit'], 0)

    async def test_next_local_day_advances_growth_and_adds_one_balance(self):
        tomorrow = {**self.weather, 'date': (date.today() + timedelta(days=1)).isoformat()}
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=tomorrow)):
            _, field, result, weather = await FieldService.recommendation_today(self.field_id, self.user.id)
            await FieldService.recommendation_today(self.field_id, self.user.id)
        self.assertEqual(field.day, 61)
        self.assertEqual(weather['date'], tomorrow['date'])
        self.assertEqual(len(list_daily_balances(self.field_id, user_id=self.user.id)), 2)

    async def test_foreign_field_is_rejected_before_weather_fetch(self):
        foreign = User(id=self.user.id + 1, is_bot=False, first_name='Other farmer')
        with patch('bot.field_service.fetch_daily_weather', AsyncMock()) as fetch:
            await handler.callback_update_field(self.callback(user=foreign), self.state)
        fetch.assert_not_awaited()
        self.assertIn('Поле не найдено', self.edits()[-1].text)

    async def test_weather_error_preserves_inputs_and_offers_retry_in_same_message(self):
        original = get_field(self.field_id)
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(side_effect=ConnectionError('offline'))):
            await handler.callback_update_field(self.callback(), self.state)
        self.assertEqual(get_field(self.field_id), original)
        result = self.edits()[-1]
        self.assertIn('Параметры поля сохранены', result.text)
        self.assertIn(f'field:update:{self.field_id}', {b.callback_data for row in result.reply_markup.inline_keyboard for b in row})
        self.assertFalse(any(type(m).__name__ == 'SendMessage' for m in self.methods))

    async def test_deadline_releases_refresh_and_keeps_navigation(self):
        async def never(*args, **kwargs):
            await asyncio.Event().wait()
        with patch('bot.field_service.fetch_daily_weather', side_effect=never), \
             patch.object(handler, 'FIELD_REFRESH_TIMEOUT', .03):
            await asyncio.wait_for(handler.callback_update_field(self.callback(), self.state), 1)
        self.assertNotIn(self.user.id, handler.active_field_refreshes)
        self.assertIn('Не удалось обновить', self.edits()[-1].text)
        with patch('bot.field_service.fetch_daily_weather', AsyncMock(return_value=self.weather)):
            await handler.callback_update_field(self.callback(), self.state)
        self.assertIn(t('ru', 'decision_irrigate'), self.edits()[-1].text)

    async def test_duplicate_click_does_not_supersede_the_inflight_screen(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def weather(*args):
            entered.set()
            await release.wait()
            return self.weather
        ui = ChatScreens()
        middleware = ChatScreenMiddleware(ui)
        async def dispatch(update, data):
            return await handler.callback_update_field(update.callback_query, self.state)
        with patch('bot.field_service.fetch_daily_weather', side_effect=weather) as fetch:
            first = asyncio.create_task(middleware(dispatch, Update(update_id=1, callback_query=self.callback()), {'bot': self.bot}))
            try:
                await asyncio.wait_for(entered.wait(), 1)
                before = len(self.edits())
                generation = ui.generations[self.user.id]
                await middleware(dispatch, Update(update_id=2, callback_query=self.callback()), {'bot': self.bot})
                self.assertEqual(len(self.edits()), before)
                self.assertEqual(ui.generations[self.user.id], generation)
                self.assertEqual(fetch.call_count, 1)
            finally:
                release.set()
                await first
        self.assertIn(t('ru', 'decision_irrigate'), self.edits()[-1].text)

    async def test_navigation_cancels_slow_refresh_without_late_result(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def never(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        with patch('bot.field_service.fetch_daily_weather', side_effect=never):
            first = asyncio.create_task(handler.callback_update_field(self.callback(), self.state))
            await asyncio.wait_for(entered.wait(), 1)
            ui = ChatScreens()
            async with ui.screen(self.user.id, True):
                pass
            await asyncio.wait_for(first, 1)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(len(self.edits()), 1, 'Navigation must not bring the old result back')
        self.assertNotIn(self.user.id, handler.active_field_refreshes)

    def test_refresh_is_primary_and_available_from_saved_report_in_each_language(self):
        for lang in ('ru', 'kz', 'en'):
            card = get_field_card_keyboard(self.field_id, lang)
            self.assertEqual(len(card.inline_keyboard[0]), 1)
            self.assertEqual(card.inline_keyboard[0][0].text, t(lang, 'btn_refresh_recommendation'))
            report = get_report_inline_keyboard(lang, 'report', self.field_id)
            buttons = [b for row in report.inline_keyboard for b in row]
            refresh = next(b for b in buttons if b.callback_data == f'field:update:{self.field_id}')
            self.assertEqual(refresh.text, t(lang, 'btn_refresh_recommendation'))


if __name__ == '__main__':
    unittest.main()
