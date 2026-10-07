"""Exercise failure -> retry -> actual report, with no fake weather or history."""
import asyncio
import json
import time
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from bot import db
from bot.calculation_recovery import CalculationRecovery, active_calculations, phrase, previous_snapshot
from bot.field_state import get_field, list_daily_balances, record_irrigation
from bot.handlers import webapp, fields
from bot.chat_screens import ChatScreens, ChatScreenMiddleware
from aiogram.types import Update
from bot.main import analyze_webapp, BOT_APP_KEY, FSM_STORAGE_KEY
import test_bot_platform as platform_fixture
import test_field_refresh as refresh_fixture
from test_water_balance import payload


class CalculationRecoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = refresh_fixture.SavedFieldRefreshTests.asyncSetUp
    asyncTearDown = refresh_fixture.SavedFieldRefreshTests.asyncTearDown
    save_field = refresh_fixture.SavedFieldRefreshTests.save_field
    transport = refresh_fixture.SavedFieldRefreshTests.transport
    callback = refresh_fixture.SavedFieldRefreshTests.callback
    edits = refresh_fixture.SavedFieldRefreshTests.edits

    async def fail_initial(self, lang='ru'):
        data = payload(crop='corn', area=.2, day_of_growth=60,
                       latitude=44.85, longitude=65.5, lang=lang,
                       power_price=25, pump_power_kw=2, pump_productivity_m3h=10)
        msg = self.callback().message.model_copy(update={'from_user':self.user}).as_(self.bot)
        with patch.object(webapp, 'fetch_daily_weather', AsyncMock(side_effect=ConnectionError('offline'))), \
                patch.object(webapp, 'get_lang', return_value=lang):
            self.assertFalse(await webapp.handle_field_payload(msg, self.state, data))
        return data

    async def test_initial_failure_preserves_full_input_and_retry_delivers_in_same_card(self):
        for lang in ('ru','kz','en'):
            self.methods.clear()
            data = await self.fail_initial(lang)
            pending = await self.state.get_data()
            self.assertEqual(pending['recovery_payload'], data)
            self.assertEqual(await self.state.get_state(), CalculationRecovery.ready.state)
            self.assertNotIn(self.user.id, active_calculations)
            error = next(m for m in self.methods if type(m).__name__ == 'SendMessage')
            self.assertEqual(error.text, phrase(lang, 'error'))
            buttons = [b for row in error.reply_markup.inline_keyboard for b in row]
            retry = next(b.callback_data for b in buttons if b.callback_data.startswith('calc:retry:'))
            self.methods.clear()
            with patch.object(webapp, 'fetch_daily_weather', AsyncMock(return_value=self.weather)) as weather, \
                    patch.object(webapp, 'get_lang', return_value=lang):
                await webapp.retry_calculation(self.callback(retry), self.state)
            weather.assert_awaited_once_with(44.85, 65.5)
            self.assertIsNone(await self.state.get_state())
            self.assertEqual(len(self.edits()), 2)
            self.assertTrue(all(m.message_id == 50 for m in self.edits()))
            self.assertFalse(any(type(m).__name__ == 'SendMessage' for m in self.methods))
            self.assertIn({'ru':'Кукуруза','kz':'Жүгері','en':'Corn'}[lang], self.edits()[-1].text)
            self.assertTrue(any(b.callback_data.startswith('explain:')
                for row in self.edits()[-1].reply_markup.inline_keyboard for b in row))

    async def test_repeat_failure_is_retryable_without_history_or_deficit_changes(self):
        before = list_daily_balances(self.field_id, user_id=self.user.id)
        original = get_field(self.field_id)
        await self.fail_initial()
        pending = await self.state.get_data()
        self.methods.clear()
        with patch.object(webapp, 'fetch_daily_weather', AsyncMock(side_effect=TimeoutError())):
            await webapp.retry_calculation(self.callback('calc:retry:' + pending['recovery_token']), self.state)
        self.assertEqual((await self.state.get_data())['recovery_payload'], pending['recovery_payload'])
        self.assertEqual(await self.state.get_state(), CalculationRecovery.ready.state)
        self.assertEqual(get_field(self.field_id), original)
        self.assertEqual(list_daily_balances(self.field_id, user_id=self.user.id), before)
        self.assertEqual(self.edits()[-1].text, phrase('ru','error'))

    async def test_stale_foreign_and_expired_buttons_do_not_request_weather(self):
        await self.fail_initial()
        pending = await self.state.get_data()
        with patch.object(webapp, 'fetch_daily_weather', AsyncMock()) as weather:
            await webapp.retry_calculation(self.callback('calc:retry:wrong'), self.state)
            await self.state.update_data(recovery_created=time.time()-86401)
            await webapp.retry_calculation(self.callback('calc:retry:'+pending['recovery_token']), self.state)
            await self.state.clear()
            await webapp.retry_calculation(self.callback('calc:retry:'+pending['recovery_token']), self.state)
        weather.assert_not_awaited()
        self.assertFalse(self.edits())

    async def test_signed_api_weather_failure_is_not_mistaken_for_success_and_can_retry_in_bot(self):
        data = payload(crop='corn', area=.2, day_of_growth=60,
                       latitude=44.85, longitude=65.5, lang='ru')
        request = platform_fixture.BotPlatformTests.analysis_request(
            platform_fixture.BotPlatformTests.signed_init_data(user_id=self.user.id), data, self.bot)
        dispatcher = platform_fixture.shared_test_dispatcher()
        request.app[FSM_STORAGE_KEY] = dispatcher.storage
        state = dispatcher.fsm.get_context(bot=self.bot, chat_id=self.user.id, user_id=self.user.id)
        await state.clear()
        with patch.object(webapp, 'fetch_daily_weather', AsyncMock(side_effect=ConnectionError())):
            result = await analyze_webapp(request)
        self.assertEqual(json.loads(result.text), {'ok':False, 'bot_replied':True, 'recoverable':True})
        pending = await state.get_data()
        self.assertEqual(pending['recovery_payload'], data)
        with patch.object(webapp, 'fetch_daily_weather', AsyncMock(return_value=self.weather)):
            await dispatcher.feed_update(self.bot, Update(update_id=880,
                callback_query=self.callback('calc:retry:'+pending['recovery_token'])))
        self.assertIsNone(await state.get_state())
        self.assertIn('Кукуруза', self.edits()[-1].text)

    async def test_previous_result_is_dated_read_only_and_owner_scoped(self):
        old = (date.today()-timedelta(days=2)).isoformat()
        self.weather = {**self.weather, 'date':old}
        self.field_id = await self.save_field(crop='corn')
        record_irrigation(self.field_id, user_id=self.user.id)
        before = get_field(self.field_id)
        journal = list_daily_balances(self.field_id, user_id=self.user.id)
        for lang in ('ru','kz','en'):
            self.methods.clear()
            with patch.object(fields,'get_lang',return_value=lang), \
                    patch('bot.field_service.fetch_daily_weather', AsyncMock(side_effect=ConnectionError())):
                await fields.callback_update_field(self.callback(), self.state)
                buttons = {b.callback_data for row in self.edits()[-1].reply_markup.inline_keyboard for b in row}
                self.assertIn(f'field:last:{self.field_id}', buttons)
                await fields.callback_previous_result(self.callback(f'field:last:{self.field_id}'), self.state)
            last = self.edits()[-1]
            self.assertIn(date.fromisoformat(old).strftime('%d.%m.%Y'), last.text)
            self.assertIn(phrase(lang,'old'), last.text)
            self.assertFalse(any(b.callback_data.startswith(('field:water:','field:confirm_water:'))
                for row in last.reply_markup.inline_keyboard for b in row))
        self.assertEqual(get_field(self.field_id), before)
        self.assertEqual(list_daily_balances(self.field_id, user_id=self.user.id), journal)
        from bot.field_state import FieldNotFoundError
        with self.assertRaises(FieldNotFoundError):
            await previous_snapshot(self.field_id, self.user.id+1)

    async def test_deadline_keeps_retry_and_navigation_cancels_without_late_reply(self):
        msg = self.callback().message.model_copy(update={'from_user':self.user}).as_(self.bot)
        data = payload(latitude=44.85, longitude=65.5)
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def never(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
        with patch.object(webapp,'fetch_daily_weather',side_effect=never), \
                patch.object(webapp,'CALCULATION_TIMEOUT',.02):
            self.assertFalse(await asyncio.wait_for(webapp.handle_field_payload(msg,self.state,data),1))
        self.assertEqual(await self.state.get_state(),CalculationRecovery.ready.state)
        self.assertNotIn(self.user.id,active_calculations)
        self.methods.clear(); entered.clear(); cancelled.clear()
        with patch.object(webapp,'fetch_daily_weather',side_effect=never):
            first = asyncio.create_task(webapp.handle_field_payload(msg,self.state,data))
            await asyncio.wait_for(entered.wait(),1)
            async with ChatScreens().screen(self.user.id,True):
                await self.state.clear()
            await asyncio.wait_for(first,1)
        self.assertTrue(cancelled.is_set())
        self.assertFalse(any(type(m).__name__.startswith(('Send','EditMessage')) for m in self.methods))

    async def test_duplicate_retry_keeps_one_request_and_same_screen_generation(self):
        await self.fail_initial()
        pending = await self.state.get_data()
        callback = self.callback('calc:retry:'+pending['recovery_token'])
        entered, release = asyncio.Event(), asyncio.Event()
        async def weather(*args):
            entered.set(); await release.wait(); return self.weather
        ui = ChatScreens(); middleware = ChatScreenMiddleware(ui)
        async def dispatch(update, data):
            return await webapp.retry_calculation(update.callback_query,self.state)
        with patch.object(webapp,'fetch_daily_weather',side_effect=weather) as fetch:
            first=asyncio.create_task(middleware(dispatch,Update(update_id=1,callback_query=callback),{'bot':self.bot}))
            try:
                await asyncio.wait_for(entered.wait(),1)
                generation=ui.generations[self.user.id]; count=len(self.edits())
                await middleware(dispatch,Update(update_id=2,callback_query=callback),{'bot':self.bot})
                self.assertEqual(ui.generations[self.user.id],generation)
                self.assertEqual(len(self.edits()),count)
                self.assertEqual(fetch.call_count,1)
            finally:
                release.set(); await first
        self.assertIsNone(await self.state.get_state())


if __name__ == '__main__':
    unittest.main()
