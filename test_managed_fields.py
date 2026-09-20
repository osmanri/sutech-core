import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bot import db
from bot.field_service import calculate_saved_field, persist_webapp_field
from bot.field_state import get_field, list_daily_balances
from bot.water_balance import calculate_balance, parse_field
from bot.daily_monitor import update_all_fields_once
from test_water_balance import payload


class ManagedFieldServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "managed.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_webapp_snapshot_and_same_day_update_are_idempotent(self):
        data = payload(crop="cotton", day_of_growth=30, moisture_condition="normal",
                       area="6,7", power_price=25, pump_power_kw=22,
                       pump_productivity_m3h=60)
        field = parse_field(data)
        weather = {"et0": 5.2, "rain": 0, "date": date.today().isoformat(),
                   "timezone": "Asia/Qyzylorda"}
        result = calculate_balance(field, weather["et0"], weather["rain"])
        field_id = await persist_webapp_field(42, data, field, 44.85, 65.49, result, weather)

        self.assertIsNotNone(field_id)
        self.assertAlmostEqual(get_field(field_id)["accumulated_deficit"], result["deficit"])
        self.assertEqual(len(list_daily_balances(field_id, user_id=42)), 1)

        with patch("bot.field_service.fetch_daily_weather", AsyncMock(return_value=weather)) as fetch:
            saved_field, saved_result, saved_weather, created = await calculate_saved_field(field_id, 42)
        fetch.assert_awaited_once_with(44.85, 65.49)
        self.assertFalse(created)
        self.assertAlmostEqual(saved_field.yesterday, field.yesterday)
        self.assertEqual(saved_result["deficit"], result["deficit"])
        self.assertEqual(saved_weather["date"], weather["date"])
        self.assertEqual(len(list_daily_balances(field_id, user_id=42)), 1)

    async def test_rice_is_not_saved_as_root_zone_balance(self):
        data = payload(crop="rice")
        field = parse_field(data)
        result = calculate_balance(field, 0, 0)
        field_id = await persist_webapp_field(
            42, data, field, 44.85, 65.49, result,
            {"date": date.today().isoformat(), "timezone": "Asia/Qyzylorda"},
        )
        self.assertIsNone(field_id)

    async def test_monitor_updates_next_day_once_and_notifies_when_irrigation_is_due(self):
        data = payload(crop="wheat", day_of_growth=60, moisture_condition="dry",
                       area=1, power_price=25, pump_power_kw=22,
                       pump_productivity_m3h=60)
        field = parse_field(data)
        today = date.today()
        initial_weather = {"et0": 0, "rain": 0, "date": today.isoformat(),
                           "timezone": "Asia/Qyzylorda"}
        result = calculate_balance(field, 0, 0)
        await persist_webapp_field(42, data, field, 44.85, 65.49, result, initial_weather)

        tomorrow_weather = {"et0": 5, "rain": 0,
                            "date": (today + timedelta(days=1)).isoformat(),
                            "timezone": "Asia/Qyzylorda"}
        bot = AsyncMock()
        with patch("bot.field_service.fetch_daily_weather", AsyncMock(return_value=tomorrow_weather)):
            first = await update_all_fields_once(bot)
            second = await update_all_fields_once(bot)
        self.assertEqual(first, {"seen": 1, "updated": 1, "notified": 1, "failed": 0})
        self.assertEqual(second, {"seen": 1, "updated": 0, "notified": 0, "failed": 0})
        bot.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
