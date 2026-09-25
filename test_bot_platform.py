"""Telegram platform integration checks without network calls."""

import tempfile
import asyncio
import hashlib
import hmac
import json
import os
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from bot import db
from bot.bot_setup import COMMANDS, configure_bot_profile, configure_user_menu
from bot.keyboards.inline import get_report_inline_keyboard


_test_dispatcher = None


def shared_test_dispatcher():
    """aiogram routers belong to one Dispatcher for the process lifetime."""
    global _test_dispatcher
    if _test_dispatcher is None:
        from bot.main import create_dispatcher
        _test_dispatcher = create_dispatcher()
    return _test_dispatcher


class BotPlatformTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def signed_init_data(user_id=10, age_seconds=0):
        from bot.main import BOT_TOKEN
        fields = {
            'auth_date': str(int(time.time()) - age_seconds),
            'user': json.dumps({'id': user_id, 'is_bot': False, 'first_name': 'Farmer'}, separators=(',', ':')),
        }
        check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
        secret = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(fields)

    @staticmethod
    def analysis_request(init_data, payload, bot):
        from bot.main import BOT_APP_KEY
        body = json.dumps({'init_data': init_data, 'payload': payload}).encode()
        return SimpleNamespace(
            content=SimpleNamespace(read=AsyncMock(return_value=body)),
            app={BOT_APP_KEY: bot},
        )

    async def test_signed_inline_app_delivers_selected_corn_to_bot(self):
        import sys
        from bot.main import analyze_webapp, handle_webapp_data
        from bot.i18n import t
        bot = SimpleNamespace(send_message=AsyncMock())
        payload = {
            'balance_version': 2, 'crop': 'corn', 'soil_type': 'loam',
            'area': 1, 'area_unit': 'hectare', 'irrigation_type': 'drip',
            'day_of_growth': 30, 'moisture_condition': 'normal',
            'latitude': 44.85, 'longitude': 65.5, 'lang': 'ru',
        }
        request = self.analysis_request(self.signed_init_data(), payload, bot)
        weather = {'date': '2026-09-25', 'timezone': 'Asia/Qyzylorda', 'et0': 4.5, 'rain': 0.0}
        snapshot = unittest.mock.Mock(return_value='a' * 32)
        actual_db = sys.modules.get('db', db)
        with patch.dict(handle_webapp_data.__globals__, {
                 'get_lang': lambda _user_id: 'ru',
                 'set_lang': lambda _user_id, _lang: None,
                 'fetch_daily_weather': AsyncMock(return_value=weather),
                 'persist_webapp_field': AsyncMock(return_value=7),
                 'save_report_explanation': snapshot,
             }), patch.object(actual_db, 'save_calculation') as history:
            response = await analyze_webapp(request)
        self.assertEqual(response.status, 200)
        self.assertTrue(json.loads(response.text)['ok'])
        self.assertTrue(json.loads(response.text)['bot_replied'])
        self.assertEqual(history.call_args.kwargs['crop_name'], t('ru', 'report_crop_corn'))
        self.assertIn(t('ru', 'report_crop_corn'), snapshot.call_args.args[1])
        self.assertNotIn(t('ru', 'report_crop_cotton'), snapshot.call_args.args[1])
        self.assertEqual(bot.send_message.await_args.kwargs['chat_id'], 10)
        self.assertIsNotNone(bot.send_message.await_args.kwargs['reply_markup'])
        report = bot.send_message.await_args.kwargs['text']
        self.assertIn('<b>Культура:</b> Кукуруза', report)
        self.assertNotIn('Хлопок', report)
        self.assertIn('1 га · Суглинок · день 30 · нормальная влажность · Капельный полив', report)
        self.assertEqual(history.call_args.kwargs['area_text'], '1 га')
        self.assertEqual(history.call_args.kwargs['irrigation_text'], t('ru', 'report_irrig_drip'))

    async def test_bot_report_matches_every_submitted_crop_and_detailed_field_inputs(self):
        import sys
        from bot.main import analyze_webapp, handle_webapp_data
        from bot.i18n import t
        from bot.water_balance import CROPS, parse_field, calculate_balance
        from bot.balance_report import fmt
        bot = SimpleNamespace(send_message=AsyncMock())
        base = {
            'balance_version': 2, 'soil_type': 'clay',
            'area': 6.7, 'area_unit': 'sotka', 'irrigation_type': 'sprinkler',
            'day_of_growth': 14, 'moisture_condition': 'dry',
            'field_type': 'greenhouse', 'is_saline': 'yes',
            'greenhouse_et0': 2.6, 'power_price': 25,
            'pump_power_kw': 22, 'pump_productivity_m3h': 60,
            'latitude': 44.85, 'longitude': 65.5, 'lang': 'ru',
        }
        weather = {'date': '2026-09-25', 'timezone': 'Asia/Qyzylorda', 'et0': 4.5, 'rain': 0.0}
        actual_db = sys.modules.get('db', db)
        with patch.dict(handle_webapp_data.__globals__, {
                 'get_lang': lambda _user_id: 'ru',
                 'set_lang': lambda _user_id, _lang: None,
                 'fetch_daily_weather': AsyncMock(return_value=weather),
                 'persist_webapp_field': AsyncMock(return_value=7),
                 'save_report_explanation': unittest.mock.Mock(return_value='a' * 32),
             }), patch.object(actual_db, 'save_calculation') as history:
            for lang in ('ru', 'kz', 'en'):
                for crop in (*CROPS, 'rice', 'other'):
                    with self.subTest(lang=lang, crop=crop):
                        payload = {**base, 'crop': crop, 'lang': lang}
                        if crop == 'other':
                            payload.update(custom_kc=1.1, custom_p=.4, custom_root_depth=.5)
                        bot.send_message.reset_mock()
                        response = await analyze_webapp(
                            self.analysis_request(self.signed_init_data(), payload, bot))
                        self.assertEqual(response.status, 200)
                        report = bot.send_message.await_args.kwargs['text']
                        expected = calculate_balance(parse_field(payload), weather['et0'], weather['rain'])
                        self.assertIn(t(lang, 'balance_crop_header',
                                        crop=t(lang, f'report_crop_{crop}')), report)
                        area_unit = 'ha' if lang == 'en' else 'га'
                        self.assertIn(f'0.067 {area_unit}', report)
                        self.assertIn(f"{fmt(expected['gross_m3'])} м³" if lang != 'en'
                                      else f"{fmt(expected['gross_m3'])} m³", report)
                        if crop != 'rice':
                            self.assertIn(t(lang, f'balance_soil_clay'), report)
                            self.assertIn(t(lang, 'balance_moisture_dry'), report)
                            self.assertIn(t(lang, 'report_irrig_sprinkler'), report)
                            self.assertEqual(expected['et0'], 2.6)
                            self.assertEqual(expected['rain'], 0.0)
                        self.assertEqual(history.call_args.kwargs['crop_name'],
                                         t(lang, f'report_crop_{crop}'))
                        self.assertEqual(history.call_args.kwargs['area_text'], f'0.067 {area_unit}')

    async def test_unsigned_or_expired_app_cannot_send_a_message(self):
        from bot.main import analyze_webapp
        bot = SimpleNamespace(send_message=AsyncMock())
        for init_data in ('auth_date=1&user=%7B%22id%22%3A10%7D&hash=bad',
                          self.signed_init_data(age_seconds=90000)):
            request = self.analysis_request(init_data, {'crop': 'corn'}, bot)
            with self.assertRaises(web.HTTPUnauthorized):
                await analyze_webapp(request)
        bot.send_message.assert_not_awaited()

    async def test_invalid_field_still_gets_clear_bot_reply(self):
        from bot.main import analyze_webapp, handle_webapp_data
        from bot.i18n import t
        bot = SimpleNamespace(send_message=AsyncMock())
        request = self.analysis_request(self.signed_init_data(), {
            'balance_version': 2, 'crop': 'corn', 'lang': 'ru',
        }, bot)
        with patch.dict(handle_webapp_data.__globals__, {
                 'get_lang': lambda _user_id: 'ru',
                 'set_lang': lambda _user_id, _lang: None,
             }):
            response = await analyze_webapp(request)
        body = json.loads(response.text)
        self.assertEqual(response.status, 200)
        self.assertEqual(body, {'ok': False, 'bot_replied': True})
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs['text'], t('ru', 'err_no_coords'))

    async def test_unexpected_analysis_error_gets_bot_fallback_message(self):
        from bot import main
        from bot.i18n import t
        bot = SimpleNamespace(send_message=AsyncMock())
        request = self.analysis_request(self.signed_init_data(), {'lang': 'ru'}, bot)
        with patch.object(main, 'handle_webapp_data', new_callable=AsyncMock,
                          side_effect=RuntimeError('test failure')):
            response = await main.analyze_webapp(request)
        self.assertEqual(json.loads(response.text), {'ok': False, 'bot_replied': True})
        bot.send_message.assert_awaited_once()
        self.assertEqual(bot.send_message.await_args.kwargs['text'], t('ru', 'err_internal'))

    async def test_unexpected_command_error_is_answered_by_dispatcher(self):
        from bot.main import handle_bot_error
        from bot.i18n import t
        message = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=AsyncMock())
        event = SimpleNamespace(update=SimpleNamespace(message=message, callback_query=None),
                                exception=RuntimeError('test failure'))
        with patch('bot.main.get_lang', return_value='ru'):
            self.assertTrue(await handle_bot_error(event))
        message.answer.assert_awaited_once_with(t('ru', 'err_internal'))
        self.assertTrue(shared_test_dispatcher().errors.handlers)

    async def test_browser_preflight_allows_only_the_site_origin(self):
        from bot.main import webapp_cors
        request = SimpleNamespace(
            path='/api/analyze', method='OPTIONS',
            headers={'Origin': 'https://frontend-2-mauve.vercel.app'},
        )
        response = await webapp_cors(request, AsyncMock())
        self.assertEqual(response.status, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], request.headers['Origin'])
        request.headers['Origin'] = 'https://unrelated.example'
        with self.assertRaises(web.HTTPForbidden):
            await webapp_cors(request, AsyncMock())

    async def test_http_post_from_mini_app_reaches_telegram_bot(self):
        import sys
        from bot.main import BOT_APP_KEY, analyze_webapp, handle_webapp_data, webapp_cors
        bot = SimpleNamespace(send_message=AsyncMock())
        app = web.Application(middlewares=[webapp_cors])
        app[BOT_APP_KEY] = bot
        app.router.add_post('/api/analyze', analyze_webapp)
        payload = {
            'balance_version': 2, 'crop': 'corn', 'soil_type': 'loam',
            'area': 1, 'area_unit': 'hectare', 'irrigation_type': 'drip',
            'day_of_growth': 30, 'moisture_condition': 'normal',
            'latitude': 44.85, 'longitude': 65.5, 'lang': 'ru',
        }
        weather = {'date': '2026-09-25', 'timezone': 'Asia/Qyzylorda', 'et0': 4.5, 'rain': 0.0}
        actual_db = sys.modules.get('db', db)
        with patch.dict(handle_webapp_data.__globals__, {
                 'get_lang': lambda _user_id: 'ru',
                 'set_lang': lambda _user_id, _lang: None,
                 'fetch_daily_weather': AsyncMock(return_value=weather),
                 'persist_webapp_field': AsyncMock(return_value=7),
                 'save_report_explanation': unittest.mock.Mock(return_value='a' * 32),
             }), patch.object(actual_db, 'save_calculation'):
            async with TestClient(TestServer(app)) as client:
                response = await client.post('/api/analyze', json={
                    'init_data': self.signed_init_data(), 'payload': payload,
                }, headers={'Origin': 'https://frontend-2-mauve.vercel.app'})
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'],
                                 'https://frontend-2-mauve.vercel.app')
                self.assertTrue((await response.json())['ok'])
        bot.send_message.assert_awaited_once()
        self.assertIn('Кукуруза', bot.send_message.await_args.kwargs['text'])

    async def test_health_identifies_calculation_revision_without_secrets(self):
        import json
        from bot.main import health_check
        from bot.water_balance import CALCULATION_VERSION
        with patch.dict('os.environ', {'RENDER_GIT_COMMIT': '0123456789abcdef'}):
            response = await health_check(None)
        data = json.loads(response.text)
        self.assertEqual(data['calculation_version'], CALCULATION_VERSION)
        self.assertEqual(data['revision'], '0123456789ab')
        self.assertEqual(set(data), {'status', 'service', 'updates', 'calculation_version', 'revision', 'database'})

    async def test_profile_commands_and_native_menu_are_configured(self):
        bot = SimpleNamespace(
            set_my_commands=AsyncMock(return_value=True),
            set_chat_menu_button=AsyncMock(return_value=True),
            set_my_name=AsyncMock(return_value=True),
            set_my_short_description=AsyncMock(return_value=True),
            set_my_description=AsyncMock(return_value=True),
        )

        await configure_bot_profile(bot)

        self.assertEqual(bot.set_my_commands.await_count, 4)
        self.assertEqual(bot.set_chat_menu_button.await_count, 1)
        self.assertEqual(bot.set_my_name.await_count, 3)
        self.assertEqual(bot.set_my_short_description.await_count, 3)
        self.assertEqual(bot.set_my_description.await_count, 3)
        self.assertEqual(
            [command.command for command in COMMANDS["ru"]],
            ["start", "app", "fields", "history", "language", "help", "about"],
        )

    async def test_language_selection_updates_personal_menu(self):
        bot = SimpleNamespace(set_chat_menu_button=AsyncMock(return_value=True))

        await configure_user_menu(bot, chat_id=42, lang="kz")

        call = bot.set_chat_menu_button.await_args
        self.assertEqual(call.kwargs["chat_id"], 42)
        self.assertIn("lang=kz", call.kwargs["menu_button"].web_app.url)

    async def test_english_language_button_sends_welcome_and_persists_choice(self):
        from bot.handlers import start
        from bot.user_state import clear_all
        old_path = db.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                db.DB_PATH = str(Path(directory) / 'history.db')
                db.init_db()
                callback = SimpleNamespace(
                    data='lang:en', from_user=SimpleNamespace(id=42, first_name='Farmer'),
                    bot=SimpleNamespace(send_message=AsyncMock()),
                    message=SimpleNamespace(delete=AsyncMock(), answer=AsyncMock(),
                                            edit_text=AsyncMock()),
                    answer=AsyncMock(),
                )
                with patch.object(start, 'configure_user_menu', new_callable=AsyncMock):
                    await start.lang_chosen(callback)
                callback.message.answer.assert_awaited_once()
                self.assertIn('Farmer', callback.message.answer.await_args.kwargs['text'])
                self.assertEqual(db.get_user_language(42), 'en')
                callback.answer.assert_awaited_once()
        finally:
            db.DB_PATH = old_path
            clear_all()

    async def test_language_welcome_has_direct_bot_fallback_if_message_edit_fails(self):
        from bot.handlers import start
        callback = SimpleNamespace(
            data='lang:en', from_user=SimpleNamespace(id=42, first_name='Farmer'),
            bot=SimpleNamespace(send_message=AsyncMock()),
            message=SimpleNamespace(delete=AsyncMock(side_effect=RuntimeError('delete failed')),
                                    answer=AsyncMock(),
                                    edit_text=AsyncMock(side_effect=RuntimeError('edit failed'))),
            answer=AsyncMock(),
        )
        with patch.object(start, 'set_lang'), \
             patch.object(start, 'configure_user_menu', new_callable=AsyncMock):
            await start.lang_chosen(callback)
        callback.bot.send_message.assert_awaited_once()
        callback.answer.assert_awaited_once()

    async def test_main_commands_always_send_a_bot_message(self):
        from bot.handlers import start, fields
        message = SimpleNamespace(from_user=SimpleNamespace(id=42), answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        with patch.object(start, 'get_lang', return_value='ru'), \
             patch.object(start, 'get_user_history', return_value=[]), \
             patch.object(fields, 'get_lang', return_value='ru'), \
             patch.object(fields.FieldService, 'get_user_fields', new_callable=AsyncMock,
                          return_value=[]):
            for handler in (start.cmd_start, start.open_app, start.show_about,
                            start.show_help, start.change_lang_menu, start.show_history,
                            start.unknown_text):
                with self.subTest(handler=handler.__name__):
                    message.answer.reset_mock()
                    await handler(message)
                    message.answer.assert_awaited_once()
            message.answer.reset_mock()
            await fields.show_fields_menu(message, state)
            message.answer.assert_awaited_once()

    async def test_dispatcher_routes_main_commands_to_telegram_messages(self):
        bot = Bot(token='123456:ABC')
        user = User(id=42, is_bot=False, first_name='Farmer')
        chat = Chat(id=42, type='private')
        dispatcher = shared_test_dispatcher()
        try:
            with patch.object(Bot, '__call__', new_callable=AsyncMock) as transport, \
                 patch('bot.handlers.start.get_user_history', return_value=[]), \
                 patch('bot.handlers.fields.FieldService.get_user_fields',
                       new_callable=AsyncMock, return_value=[]):
                for index, command in enumerate(('/start', '/app', '/help', '/about',
                                                 '/history', '/fields', 'hello'), 1):
                    with self.subTest(command=command):
                        transport.reset_mock()
                        message = Message(message_id=index, date=datetime.now(timezone.utc),
                                          chat=chat, from_user=user, text=command)
                        await dispatcher.feed_update(bot, Update(update_id=index, message=message))
                        sent = [call.args[0] for call in transport.await_args_list
                                if type(call.args[0]).__name__ == 'SendMessage']
                        self.assertTrue(sent, f'Bot stayed silent for {command}')
                        self.assertTrue(sent[-1].text)
        finally:
            await bot.session.close()

    async def test_dispatcher_answers_active_inline_buttons(self):
        bot = Bot(token='123456:ABC')
        user = User(id=42, is_bot=False, first_name='Farmer')
        chat = Chat(id=42, type='private')
        callbacks = ('lang:en', 'show_history_inline', 'hist_page:0',
                     'hist_menu', 'methodology:info', 'explain:unavailable',
                     'fields:list', 'field:list:0', 'field:view:999999',
                     'field:update:999999', 'field:water:999999',
                     'field:watered:999999', 'field:confirm_water:999999',
                     'field:confirm-watered:999999', 'field:export:999999',
                     'field:delete:999999', 'field:delete_confirm:999999',
                     'field:add:0')
        try:
            with patch.object(Bot, '__call__', new_callable=AsyncMock) as transport, \
                 patch('bot.handlers.start.set_lang'), \
                 patch('bot.handlers.start.configure_user_menu', new_callable=AsyncMock), \
                 patch('bot.handlers.start.get_user_history', return_value=[]), \
                 patch('bot.handlers.fields.FieldService.get_user_fields',
                       new_callable=AsyncMock, return_value=[]), \
                 patch('bot.handlers.fields.FieldService.get_field_by_id',
                       new_callable=AsyncMock, return_value=None), \
                 patch('bot.handlers.fields.FieldService.update_balance_today',
                       new_callable=AsyncMock, side_effect=RuntimeError('missing field')), \
                 patch('bot.handlers.fields.FieldService.record_irrigation_fact',
                       new_callable=AsyncMock, side_effect=RuntimeError('missing field')), \
                 patch('bot.handlers.fields.FieldService.delete_field',
                       new_callable=AsyncMock, return_value=False):
                for index, data in enumerate(callbacks, 1):
                    with self.subTest(callback=data):
                        transport.reset_mock()
                        message = Message(message_id=index, date=datetime.now(timezone.utc),
                                          chat=chat, from_user=user, text='Previous bot message')
                        callback = CallbackQuery(id=str(index), from_user=user,
                                                 chat_instance='test', message=message, data=data)
                        await shared_test_dispatcher().feed_update(
                            bot, Update(update_id=100 + index, callback_query=callback))
                        methods = [type(call.args[0]).__name__ for call in transport.await_args_list]
                        self.assertIn('AnswerCallbackQuery', methods,
                                      f'Button {data} left Telegram spinner unanswered')
                        if data in ('lang:en', 'hist_menu', 'methodology:info'):
                            self.assertIn('SendMessage', methods)
        finally:
            await bot.session.close()

    async def test_real_webhook_route_turns_start_update_into_bot_reply(self):
        from bot.main import start_http_server, WEBHOOK_PATH, WEBHOOK_SECRET
        bot = Bot(token='123456:ABC')
        user = User(id=42, is_bot=False, first_name='Farmer')
        message = Message(message_id=1, date=datetime.now(timezone.utc),
                          chat=Chat(id=42, type='private'), from_user=user, text='/start')
        update = Update(update_id=501, message=message)
        sent = asyncio.Event()

        async def observe(method, *args, **kwargs):
            if type(method).__name__ == 'SendMessage':
                sent.set()

        runner = None
        try:
            with patch.dict(os.environ, {'PORT': '0'}), \
                 patch.object(Bot, '__call__', new_callable=AsyncMock,
                              side_effect=observe):
                runner = await start_http_server(bot, shared_test_dispatcher())
                site = next(iter(runner.sites))
                port = site._server.sockets[0].getsockname()[1]
                async with ClientSession() as client:
                    response = await client.post(
                        f'http://127.0.0.1:{port}{WEBHOOK_PATH}',
                        json=update.model_dump(mode='json', exclude_none=True),
                        headers={'X-Telegram-Bot-Api-Secret-Token': WEBHOOK_SECRET},
                    )
                    self.assertEqual(response.status, 200)
                await asyncio.wait_for(sent.wait(), timeout=3)
        finally:
            if runner is not None:
                await runner.cleanup()
            await bot.session.close()

    async def test_report_has_new_calculation_webapp_button(self):
        keyboard = get_report_inline_keyboard("ru", field_id=17)

        buttons = [button for row in keyboard.inline_keyboard for button in row]
        launcher = next(button for button in buttons if button.web_app)
        self.assertIn("lang=ru", launcher.web_app.url)
        self.assertTrue(any((button.callback_data or '').startswith('explain:') for button in buttons))
        self.assertTrue(any(button.callback_data == 'field:watered:17' for button in buttons))
        self.assertTrue(any(button.callback_data == 'field:export:17' for button in buttons))


class UserLanguagePersistenceTests(unittest.TestCase):
    def test_language_survives_memory_reset(self):
        old_path = db.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                db.DB_PATH = str(Path(directory) / "history.db")
                db.init_db()
                for lang in ("ru", "kz", "en"):
                    db.set_user_language(42, lang)
                    self.assertEqual(db.get_user_language(42), lang)
                from bot.user_state import clear_all, get_lang
                clear_all()
                self.assertEqual(get_lang(42), "en")
        finally:
            db.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
