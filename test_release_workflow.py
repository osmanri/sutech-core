"""Release-level checks for the persistent Su-Tech field workflow."""

import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bot import db
from bot.daily_monitor import update_all_fields_once
from bot.field_service import calculate_saved_field, persist_webapp_field
from bot.field_state import (
    get_field,
    list_daily_balances,
    list_irrigation_events,
    record_irrigation,
)
from bot.water_balance import calculate_balance, parse_field
from test_water_balance import payload


class LegacyDatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "legacy.db")

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_legacy_field_survives_schema_upgrade_and_restart(self):
        with closing(sqlite3.connect(db.DB_PATH)) as conn:
            conn.execute(
                """
                CREATE TABLE fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    crop_type TEXT NOT NULL,
                    soil_type TEXT NOT NULL,
                    irrigation_method TEXT NOT NULL,
                    planting_date TEXT NOT NULL,
                    accumulated_deficit REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            conn.execute(
                """
                INSERT INTO fields
                    (user_id, crop_type, soil_type, irrigation_method,
                     planting_date, accumulated_deficit)
                VALUES (42, 'wheat', 'loam', 'drip', ?, 7.5)
                """,
                ((date.today() - timedelta(days=10)).isoformat(),),
            )
            conn.commit()

        db.init_db()
        migrated = get_field(1, user_id=42)
        self.assertEqual(migrated["crop_type"], "wheat")
        self.assertEqual(migrated["accumulated_deficit"], 7.5)
        self.assertIn("field_key", migrated)

        # A second startup must be harmless and data must remain available.
        db.init_db()
        self.assertEqual(get_field(1, user_id=42)["accumulated_deficit"], 7.5)
        with closing(sqlite3.connect(db.DB_PATH)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("field_daily_balances", tables)
        self.assertIn("irrigation_events", tables)

    def test_database_initialization_fails_loudly_for_invalid_path(self):
        db.DB_PATH = self.temp_dir.name
        with self.assertRaises(sqlite3.Error):
            db.init_db()


class ReleaseWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "release.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def _create_due_field(self) -> tuple[int, dict, date]:
        data = payload(
            crop="wheat",
            day_of_growth=60,
            moisture_condition="dry",
            area="6,7",
            power_price=25,
            pump_power_kw=22,
            pump_productivity_m3h=60,
        )
        field = parse_field(data)
        today = date.today()
        weather = {
            "et0": 0,
            "rain": 0,
            "date": today.isoformat(),
            "timezone": "Asia/Qyzylorda",
        }
        result = calculate_balance(field, weather["et0"], weather["rain"])
        field_id = await persist_webapp_field(
            42, data, field, 44.8529, 65.4885, result, weather
        )
        return field_id, data, today

    async def test_two_monitor_runs_create_one_row_and_one_alert(self):
        field_id, _, today = await self._create_due_field()
        tomorrow = {
            "et0": 5,
            "rain": 0,
            "date": (today + timedelta(days=1)).isoformat(),
            "timezone": "Asia/Qyzylorda",
        }
        bot = AsyncMock()
        with patch(
            "bot.field_service.fetch_daily_weather",
            AsyncMock(return_value=tomorrow),
        ):
            stats = await asyncio.gather(
                update_all_fields_once(bot), update_all_fields_once(bot)
            )

        self.assertEqual(sum(item["updated"] for item in stats), 1)
        self.assertEqual(sum(item["notified"] for item in stats), 1)
        self.assertEqual(sum(item["failed"] for item in stats), 0)
        bot.send_message.assert_awaited_once()
        self.assertEqual(len(list_daily_balances(field_id, user_id=42)), 2)

    async def test_confirmed_irrigation_is_the_next_days_starting_state(self):
        field_id, _, today = await self._create_due_field()
        before = get_field(field_id, user_id=42)["accumulated_deficit"]
        self.assertGreater(before, 0)

        event = record_irrigation(field_id, user_id=42)
        self.assertEqual(event["deficit_after"], 0)
        self.assertEqual(get_field(field_id, user_id=42)["accumulated_deficit"], 0)
        self.assertEqual(len(list_irrigation_events(field_id, user_id=42)), 1)

        tomorrow = {
            "et0": 3,
            "rain": 0,
            "date": (today + timedelta(days=1)).isoformat(),
            "timezone": "Asia/Qyzylorda",
        }
        with patch(
            "bot.field_service.fetch_daily_weather",
            AsyncMock(return_value=tomorrow),
        ):
            _, result, _, created = await calculate_saved_field(field_id, 42)

        self.assertTrue(created)
        self.assertAlmostEqual(result["deficit"], result["etc"])
        rows = list_daily_balances(field_id, user_id=42)
        self.assertEqual(rows[0]["deficit_before"], 0)


if __name__ == "__main__":
    unittest.main()
