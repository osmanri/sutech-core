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
    list_user_fields,
    reset_deficit,
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


if __name__ == "__main__":
    unittest.main()
