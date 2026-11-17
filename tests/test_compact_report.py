"""Focused report and WebApp integration checks; no Telegram/weather/DB writes."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp

from bot.handlers.webapp import (
    calculate_water_demand,
    fetch_meteo,
    format_compact_report,
    handle_webapp_data,
)
from bot.i18n import STRINGS, t


class CompactReportTests(unittest.TestCase):
    def test_reports_are_six_lines_in_both_languages_and_decisions(self):
        for lang in ("ru", "kz"):
            for moisture in (0.18, 0.30):
                with self.subTest(lang=lang, moisture=moisture):
                    result = calculate_water_demand(28, moisture, 3.5, 550, area_m2=100)
                    report = format_compact_report(lang, "cotton", "drip", 100, 28, 3.5, moisture, result)
                    self.assertEqual(len(report.splitlines()), 6)
                    self.assertIn("0.01 га", report)
                    self.assertIn("3.5 м/с", report)
                    self.assertIn(f"{moisture:.3f} m³/m³", report)
                    self.assertIn("м³", report.splitlines()[3])
                    decision = "decision_irrigate" if moisture < .25 else "decision_normal"
                    self.assertTrue(report.endswith(t(lang, decision)))
                    self.assertNotIn("{", report)
                    if moisture >= .25:
                        self.assertIn("0 м³", report)

    def test_large_area_and_small_water_volume_keep_correct_units(self):
        result = {"total_liters": 1.5, "savings_tenge": 1200, "needs_irrigation": True}
        report = format_compact_report("kz", "wheat", "pivot", 100000, 20, 2, .2, result)
        self.assertIn("Бидай | 10 га | Айналмалы пивот", report)
        self.assertIn("0.0015 м³", report)
        self.assertIn("~1 200 ₸", report)

    def test_translation_key_parity(self):
        for key in STRINGS["ru"]:
            if key.startswith(("report_", "compact_", "decision_")):
                self.assertIn(key, STRINGS["kz"])


class WebAppReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_weather_provider_outage_does_not_invent_meteorology(self):
        with patch(
            "bot.handlers.webapp.aiohttp.ClientSession",
            side_effect=aiohttp.ClientError("provider unavailable"),
        ):
            with self.assertRaises(aiohttp.ClientError):
                await fetch_meteo(44.852290, 65.488472)

    async def test_legacy_payload_requests_new_balance_inputs(self):
        for unit, area in (("hectare", .01), ("sotka", 1)):
            with self.subTest(unit=unit):
                payload = {"latitude": 0, "longitude": 0, "area": area, "area_unit": unit,
                           "crop": "cotton", "irrigation_type": "drip", "lang": "kz"}
                message = SimpleNamespace(from_user=SimpleNamespace(id=123),
                    web_app_data=SimpleNamespace(data=json.dumps(payload)), answer=AsyncMock())
                weather = {"temperature": 28, "soil_moisture": .18, "wind_speed": 3.5, "radiation": 550}
                with patch("bot.handlers.webapp.fetch_meteo", AsyncMock(return_value=weather)) as fetch, \
                     patch("bot.handlers.webapp.get_lang", return_value="ru"), \
                     patch("bot.handlers.webapp.save_report_explanation", return_value="test-report"), \
                     patch("bot.db.save_calculation") as save:
                    await handle_webapp_data(message, AsyncMock())
                fetch.assert_not_awaited()
                save.assert_not_called()
                message.answer.assert_awaited_once()
                report = message.answer.call_args.args[0]
                self.assertEqual(report, t('kz', 'balance_old_app'))


if __name__ == "__main__":
    unittest.main()
