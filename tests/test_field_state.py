import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from bot import db
from bot.field_state import (
    FieldNotFoundError,
    InvalidFieldDataError,
    add_new_field,
    get_day_of_growth,
    get_field,
    get_daily_balance,
    list_user_fields,
    list_daily_balances,
    list_irrigation_events,
    make_field_key,
    record_irrigation,
    reset_deficit,
    save_daily_balance,
    upsert_managed_field,
    update_daily_deficit,
)


class FieldStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "state.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_create_and_growth_day(self):
        planted = date.today() - timedelta(days=12)
        field_id = add_new_field(42, "Potato", "LOAM", "drip", planted)
        field = get_field(field_id, user_id=42)
        self.assertEqual(field["crop_type"], "potato")
        self.assertEqual(field["accumulated_deficit"], 0.0)
        self.assertEqual(get_day_of_growth(field_id), 12)
        self.assertEqual(len(list_user_fields(42)), 1)

    def test_daily_balance_is_floored_at_zero_and_can_be_reset(self):
        field_id = add_new_field(7, "cotton", "sand", "sprinkler")
        self.assertAlmostEqual(update_daily_deficit(field_id, 6.25, 1.5), 4.75)
        self.assertEqual(update_daily_deficit(field_id, 1.0, 20.0), 0.0)
        update_daily_deficit(field_id, 3.0, 0.0)
        self.assertEqual(reset_deficit(field_id, user_id=7), 0.0)
        self.assertEqual(get_field(field_id)["accumulated_deficit"], 0.0)

    def test_missing_field_and_owner_are_reported(self):
        with self.assertRaises(FieldNotFoundError):
            get_day_of_growth(999)
        field_id = add_new_field(7, "corn", "loam", "drip")
        with self.assertRaises(FieldNotFoundError):
            reset_deficit(field_id, user_id=8)

    def test_bad_numeric_and_future_dates_are_rejected(self):
        field_id = add_new_field(7, "corn", "loam", "drip")
        for value in (-1, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises(InvalidFieldDataError):
                    update_daily_deficit(field_id, value, 0)
        with self.assertRaises(InvalidFieldDataError):
            add_new_field(7, "corn", "loam", "drip", date.today() + timedelta(days=1))

    def test_parallel_updates_do_not_lose_deficit(self):
        field_id = add_new_field(7, "corn", "loam", "drip")
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(lambda _: update_daily_deficit(field_id, 1.0, 0.0), range(20)))
        self.assertEqual(get_field(field_id)["accumulated_deficit"], 20.0)

    def test_managed_field_daily_balance_is_idempotent(self):
        key = make_field_key(44.8529, 65.4885, 1.5, "cotton")
        field_id, created = upsert_managed_field(
            user_id=7, field_key=key, crop="cotton", soil="loam", irrigation="drip",
            planting_date=date.today() - timedelta(days=30), initial_deficit=12,
            latitude=44.8529, longitude=65.4885, area_ha=1.5,
            stage_days=(30, 50, 60, 55), power_price=25,
            pump_power_kw=22, pump_productivity_m3h=60,
        )
        self.assertTrue(created)
        same_id, created = upsert_managed_field(
            user_id=7, field_key=key, crop="cotton", soil="sand", irrigation="drip",
            planting_date=date.today() - timedelta(days=30), initial_deficit=0,
            latitude=44.8529, longitude=65.4885, area_ha=1.5,
        )
        self.assertEqual(same_id, field_id)
        self.assertFalse(created)
        self.assertEqual(get_field(field_id)["accumulated_deficit"], 12)
        self.assertEqual(get_field(field_id)["soil_type"], "sand")

        result = dict(et0=5, rain=0, peff=0, etc=5.5, deficit=17.5,
                      status="irrigate", net_m3=262.5, gross_m3=291.666,
                      calculation_version="test")
        row, inserted = save_daily_balance(
            field_id, user_id=7, balance_date=date.today().isoformat(),
            timezone="Asia/Qyzylorda", result=result, deficit_before=12,
        )
        self.assertTrue(inserted)
        self.assertEqual(row["result"]["deficit"], 17.5)
        self.assertEqual(get_field(field_id)["accumulated_deficit"], 17.5)

        changed = dict(result, deficit=99)
        row, inserted = save_daily_balance(
            field_id, user_id=7, balance_date=date.today().isoformat(),
            timezone="Asia/Qyzylorda", result=changed, deficit_before=17.5,
        )
        self.assertFalse(inserted)
        self.assertEqual(row["result"]["deficit"], 17.5)
        self.assertEqual(len(list_daily_balances(field_id, user_id=7)), 1)

    def test_irrigation_event_checks_owner_and_supports_partial_volume(self):
        key = make_field_key(44.8, 65.4, 1, "wheat")
        field_id, _ = upsert_managed_field(
            user_id=7, field_key=key, crop="wheat", soil="loam", irrigation="drip",
            planting_date=date.today(), initial_deficit=10,
            latitude=44.8, longitude=65.4, area_ha=1,
        )
        event = record_irrigation(field_id, user_id=7, applied_m3=50)
        self.assertAlmostEqual(event["deficit_after"], 5.5)
        self.assertAlmostEqual(get_field(field_id)["accumulated_deficit"], 5.5)
        event = record_irrigation(field_id, user_id=7)
        self.assertEqual(event["deficit_after"], 0)
        events = list_irrigation_events(field_id, user_id=7)
        self.assertEqual(len(events), 2)
        self.assertIsNone(events[0]["applied_m3"])
        with self.assertRaises(FieldNotFoundError):
            record_irrigation(field_id, user_id=8)


if __name__ == "__main__":
    unittest.main()
