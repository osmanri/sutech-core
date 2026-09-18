"""Focused report and WebApp integration checks; no Telegram/weather/DB writes."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.handlers.webapp import calculate_water_demand, format_compact_report, handle_webapp_data
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
    async def test_payload_units_language_and_history(self):
        for unit, area in (("hectare", .01), ("sotka", 1)):
            with self.subTest(unit=unit):
                payload = {"latitude": 0, "longitude": 0, "area": area, "area_unit": unit,
                           "crop": "cotton", "irrigation_type": "drip", "lang": "kz"}
                message = SimpleNamespace(from_user=SimpleNamespace(id=123),
                    web_app_data=SimpleNamespace(data=json.dumps(payload)), answer=AsyncMock())
                weather = {"temperature": 28, "soil_moisture": .18, "wind_speed": 3.5, "radiation": 550}
                with patch("bot.handlers.webapp.fetch_meteo", AsyncMock(return_value=weather)) as fetch, \
                     patch("bot.handlers.webapp.get_lang", return_value="ru"), \
                     patch("bot.db.save_calculation") as save:
                    await handle_webapp_data(message, AsyncMock())
                fetch.assert_awaited_once_with(0, 0)
                save.assert_called_once()
                message.answer.assert_awaited_once()
                report = message.answer.call_args.args[0]
                self.assertEqual(len(report.splitlines()), 6)
                self.assertIn("Агро-есеп", report)
                self.assertIn("0.01 га", report)
                self.assertEqual(save.call_args.kwargs["lang"], "kz")


if __name__ == "__main__":
    unittest.main()
