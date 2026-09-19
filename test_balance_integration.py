import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import aiohttp

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
                             lang=lang,yesterday_deficit=20,power_price=25,energy_kwh_m3=.2)
                message=SimpleNamespace(from_user=SimpleNamespace(id=10),
                    web_app_data=SimpleNamespace(data=json.dumps(data)),answer=AsyncMock())
                weather=dict(et0=5,rain=0,date='2026-09-19',timezone='Asia/Almaty')
                with patch('bot.handlers.webapp.get_lang',return_value='ru'), \
                     patch('bot.handlers.webapp.fetch_daily_weather',AsyncMock(return_value=weather)) as fetch, \
                     patch('bot.handlers.webapp.save_report_explanation',return_value='a'*32) as snapshot, \
                     patch('bot.db.save_calculation') as history:
                    await handle_webapp_data(message,AsyncMock())
                fetch.assert_awaited_once_with(44,65)
                history.assert_called_once()
                self.assertEqual(history.call_args.kwargs['area_text'],'6.7 га')
                self.assertEqual(history.call_args.kwargs['lang'],lang)
                snapshot.assert_called_once()
                self.assertIn('20 + 5',snapshot.call_args.args[1])
                message.answer.assert_awaited_once()
                report=message.answer.call_args.args[0]
                self.assertIn(t(lang,'balance_status_irrigate'),report)
                self.assertIn('Open-Meteo',report)
                keyboard=message.answer.call_args.kwargs['reply_markup']
                self.assertEqual(keyboard.inline_keyboard[0][0].callback_data,'explain:'+'a'*32)

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
        for data in [[],payload(latitude='NaN',longitude=65),payload(latitude=44,longitude=65,yesterday_deficit='NaN')]:
            message=SimpleNamespace(from_user=SimpleNamespace(id=10),
                web_app_data=SimpleNamespace(data=json.dumps(data)),answer=AsyncMock())
            with patch('bot.handlers.webapp.get_lang',return_value='ru'), \
                 patch('bot.handlers.webapp.fetch_daily_weather',AsyncMock()) as fetch:
                await handle_webapp_data(message,AsyncMock())
            fetch.assert_not_awaited(); message.answer.assert_awaited_once()

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
