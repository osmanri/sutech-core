import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from bot.balance_weather import fetch_daily_weather


def fixture():
    return dict(timezone='Asia/Qyzylorda', utc_offset_seconds=18000,
                daily_units=dict(et0_fao_evapotranspiration='mm', precipitation_sum='mm'),
                daily=dict(time=[datetime.now(timezone(timedelta(hours=5))).date().isoformat()],
                           et0_fao_evapotranspiration=[5.2], precipitation_sum=[7.0]))


def context(response):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    return cm


def response(data=None, error=None):
    obj = MagicMock()
    obj.raise_for_status.side_effect = error
    obj.json = AsyncMock(return_value=data)
    return obj


class WeatherRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, responses, lat=44.85, lon=65.5):
        session = MagicMock()
        session.get.side_effect = [context(item) for item in responses]
        with patch('bot.balance_weather.aiohttp.ClientSession', return_value=context(session)):
            result = await fetch_daily_weather(lat, lon)
        return result, session

    async def test_render_rate_limit_recovers_using_validated_weather(self):
        data = fixture()
        result, session = await self.invoke([
            response(error=aiohttp.ClientError('429 Too Many Requests')),
            response(data),
        ])
        self.assertEqual(result['et0'], 5.2)
        self.assertEqual(session.get.call_args_list[1].args[0],
                         'https://frontend-2-mauve.vercel.app/api/weather')
        self.assertEqual(session.get.call_args_list[1].kwargs['params'],
                         {'latitude': 44.85, 'longitude': 65.5})

    async def test_direct_success_does_not_call_fallback(self):
        _, session = await self.invoke([response(fixture())])
        self.assertEqual(session.get.call_count, 1)

    async def test_timeout_recovers(self):
        result, _ = await self.invoke([response(error=TimeoutError()),
                                      response(fixture())])
        self.assertEqual(result['rain'], 7)

    async def test_stale_fallback_never_returns_recommendation(self):
        stale = fixture()
        stale['daily']['time'] = ['2000-01-01']
        with self.assertRaises(ValueError):
            await self.invoke([response(error=aiohttp.ClientError('429')),
                               response(stale)])

    async def test_both_unavailable_raise_error(self):
        with self.assertRaises(aiohttp.ClientError):
            await self.invoke([response(error=aiohttp.ClientError('429')),
                               response(error=aiohttp.ClientError('503'))])

    async def test_invalid_coordinates_do_not_request_weather(self):
        with patch('bot.balance_weather.aiohttp.ClientSession') as factory:
            with self.assertRaises(ValueError):
                await fetch_daily_weather('NaN', 65)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
