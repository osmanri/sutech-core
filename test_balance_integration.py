import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import aiohttp
from itertools import product

from bot.balance_weather import parse_daily_weather, fetch_daily_weather
from bot.handlers.webapp import handle_webapp_data
from bot.i18n import t
from test_water_balance import payload


class WeatherTests(unittest.TestCase):
    def fixture(self, offset=18000):
        return dict(timezone='Asia/Almaty', utc_offset_seconds=offset,
            daily_units=dict(et0_fao_evapotranspiration='mm',precipitation_sum='mm'),
            daily=dict(time=[datetime.now(timezone(timedelta(seconds=offset))).date().isoformat()],
                       et0_fao_evapotranspiration=[5.2],precipitation_sum=[7.0]))

    def test_daily_values_units_and_field_date(self):
        for offset in [-43200,18000,50400]:
            result=parse_daily_weather(self.fixture(offset))
            self.assertEqual(result['et0'],5.2)
            self.assertEqual(result['rain'],7)
            self.assertEqual(result['date'],self.fixture(offset)['daily']['time'][0])

    def test_no_defaults_for_missing_stale_or_invalid_weather(self):
        for value in [None, 'NaN', -1, True]:
            data=self.fixture(); data['daily']['et0_fao_evapotranspiration']=[value]
            with self.assertRaises(ValueError): parse_daily_weather(data)
        data=self.fixture(); data['daily']['time']=['2000-01-01']
        with self.assertRaises(ValueError): parse_daily_weather(data)
        data=self.fixture(); data['daily_units']['precipitation_sum']='inch'
        with self.assertRaises(ValueError): parse_daily_weather(data)


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_history_and_explanation_match_both_units(self):
        for lang in ['ru','kz']:
            for unit,area in [('hectare',6.7),('sotka',670)]:
                data=payload(latitude=44,longitude=65,area=area,area_unit=unit,
                             lang=lang,moisture_condition='normal',power_price=25,
                             pump_power_kw=22,pump_productivity_m3h=60)
                message=SimpleNamespace(from_user=SimpleNamespace(id=10),
                    web_app_data=SimpleNamespace(data=json.dumps(data)),answer=AsyncMock())
                weather=dict(et0=5,rain=0,date='2026-09-19',timezone='Asia/Almaty')
                with patch('bot.handlers.webapp.get_lang',return_value='ru'), \
                     patch('bot.handlers.webapp.fetch_daily_weather',AsyncMock(return_value=weather)) as fetch, \
                     patch('bot.handlers.webapp.persist_webapp_field',AsyncMock(return_value=7)), \
                     patch('bot.handlers.webapp.save_report_explanation',return_value='a'*32) as snapshot, \
                     patch('bot.db.save_calculation') as history:
                    await handle_webapp_data(message,AsyncMock())
                fetch.assert_awaited_once_with(44,65)
                history.assert_called_once()
                self.assertEqual(history.call_args.kwargs['area_text'],'6.7 га')
                self.assertEqual(history.call_args.kwargs['lang'],lang)
                snapshot.assert_called_once()
                self.assertIn('51.56 + 5',snapshot.call_args.args[1])
                message.answer.assert_awaited_once()
                report=message.answer.call_args.args[0]
                self.assertIn(t(lang,'balance_status_irrigate'),report)
                self.assertIn('Open-Meteo',report)
                self.assertNotRegex(report, r'\d+[.,]\d{3,}')
                self.assertNotRegex(history.call_args.kwargs['savings_text'], r'\d+[.,]\d{3,}')
                keyboard=message.answer.call_args.kwargs['reply_markup']
                self.assertEqual(keyboard.inline_keyboard[0][0].callback_data,'explain:'+'a'*32)
                self.assertTrue(any(button.callback_data == 'field:watered:7'
                                    for row in keyboard.inline_keyboard for button in row))

    async def test_api_failure_has_no_recommendation_or_saved_calculation(self):
        message=SimpleNamespace(from_user=SimpleNamespace(id=10),
            web_app_data=SimpleNamespace(data=json.dumps(payload(latitude=44,longitude=65))),answer=AsyncMock())
        with patch('bot.handlers.webapp.get_lang',return_value='ru'), \
             patch('bot.handlers.webapp.fetch_daily_weather',AsyncMock(side_effect=aiohttp.ClientError('offline'))), \
             patch('bot.db.save_calculation') as history:
            await handle_webapp_data(message,AsyncMock())
        message.answer.assert_awaited_once_with(t('ru','err_weather'))
        history.assert_not_called()

    async def test_malformed_and_nonfinite_input_does_not_fetch_weather(self):
        for data in [[],payload(latitude='NaN',longitude=65),payload(latitude=44,longitude=65,moisture_condition='unknown'),
                     payload(latitude=44, longitude=65, moisture_condition=[])]:
            message=SimpleNamespace(from_user=SimpleNamespace(id=10),
                web_app_data=SimpleNamespace(data=json.dumps(data)),answer=AsyncMock())
            with patch('bot.handlers.webapp.get_lang',return_value='ru'), \
                 patch('bot.handlers.webapp.fetch_daily_weather',AsyncMock()) as fetch:
                await handle_webapp_data(message,AsyncMock())
            fetch.assert_not_awaited(); message.answer.assert_awaited_once()

    async def test_all_crop_methods_moisture_languages_units_money_reaches_telegram(self):
        from test_calculation_audit import PROFILES, APPLICATION, MOISTURE, inputs, reference_balance
        count = 0
        for crop, method, moisture, lang, unit in product(PROFILES, APPLICATION, MOISTURE,
                                                        ('ru', 'kz'), ('hectare', 'sotka')):
            data = inputs(crop=crop, irrigation_type=method, moisture_condition=moisture,
                          day_of_growth=0, latitude=44, longitude=65, lang=lang,
                          area_unit=unit, area='6,7' if unit == 'hectare' else 670)
            expected = reference_balance(data, 0, 0)
            message = SimpleNamespace(from_user=SimpleNamespace(id=10),
                web_app_data=SimpleNamespace(data=json.dumps(data)), answer=AsyncMock())
            weather = dict(et0=0, rain=0, date='2026-09-19', timezone='Asia/Almaty')
            with patch('bot.handlers.webapp.get_lang', return_value=lang), \
                 patch('bot.handlers.webapp.fetch_daily_weather', AsyncMock(return_value=weather)), \
                 patch('bot.handlers.webapp.persist_webapp_field', AsyncMock(return_value=7)), \
                 patch('bot.handlers.webapp.save_report_explanation', return_value='a'*32) as snapshot, \
                 patch('bot.db.save_calculation') as history:
                await handle_webapp_data(message, AsyncMock())
            report = message.answer.call_args.args[0]
            self.assertIn(t(lang, 'balance_status_' + expected['status']), report)
            shown_money = re.findall(r'(-?\d+\.\d{2}) ₸', report)
            self.assertEqual(len(shown_money), 3)
            for shown, key in zip(shown_money, ('traditional_cost', 'cost', 'savings')):
                # A rational value exactly halfway between cents may land on
                # either adjacent cent after binary floating-point arithmetic.
                # Require correct currency precision and <= half-cent error;
                # the independent core oracle checks unrounded math at 1e-10.
                self.assertGreaterEqual(float(shown), 0)
                self.assertLessEqual(abs(float(shown)-float(expected[key])), .005 + 1e-8)
            self.assertIn(history.call_args.kwargs['savings_text'], report)
            self.assertLess(len(snapshot.call_args.args[1]), 4096)
            self.assertNotIn('{', snapshot.call_args.args[1])
            message.answer.assert_awaited_once()
            count += 1
        print(f'AUDIT: {count} Telegram report/history/explanation cases (network mocked)')

    async def test_provider_request_uses_daily_fao_and_local_timezone(self):
        response=AsyncMock()
        response.raise_for_status=lambda: None
        response.json=AsyncMock(return_value=WeatherTests().fixture())
        from unittest.mock import MagicMock
        context=MagicMock(); context.__aenter__=AsyncMock(return_value=response)
        session=MagicMock(); session.get.return_value=context
        outer=MagicMock(); outer.__aenter__=AsyncMock(return_value=session)
        with patch('bot.balance_weather.aiohttp.ClientSession',return_value=outer):
            result=await fetch_daily_weather(44,65)
        self.assertEqual(result['et0'],5.2)
        params=session.get.call_args.kwargs['params']
        self.assertEqual(params['timezone'],'auto')
        self.assertEqual(params['forecast_days'],1)
        self.assertIn('et0_fao_evapotranspiration',params['daily'])


if __name__ == '__main__': unittest.main()
