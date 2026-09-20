import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from bot import db, field_state


class DatabaseAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.old_db_path = db.DB_PATH
        cls.test_db = os.path.join(cls.temp_dir.name, "test_adapter.db")
        db.DB_PATH = cls.test_db
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.old_db_path
        cls.temp_dir.cleanup()

    def test_01_sqlite_health(self):
        self.assertFalse(db.is_postgres())
        health = db.check_db_health()
        self.assertEqual(health["status"], "connected")
        self.assertEqual(health["engine"], "sqlite")

    def test_02_field_creation_and_retrieval(self):
        field_id = field_state.add_new_field(
            user_id=1001,
            crop="wheat",
            soil="loam",
            irrigation="drip",
            planting_date="2026-05-01",
        )
        self.assertIsInstance(field_id, int)
        self.assertGreater(field_id, 0)

        field = field_state.get_field(field_id, user_id=1001)
        self.assertEqual(field["crop_type"], "wheat")
        self.assertEqual(field["soil_type"], "loam")
        self.assertEqual(field["irrigation_method"], "drip")
        self.assertEqual(field["accumulated_deficit"], 0.0)

    def test_03_managed_field_upsert(self):
        key = "a1b2c3d4e5f60718293a4b5c"
        field_id, created = field_state.upsert_managed_field(
            user_id=1002,
            field_key=key,
            crop="cotton",
            soil="clay",
            irrigation="furrow",
            planting_date="2026-04-15",
            initial_deficit=5.5,
            latitude=42.3,
            longitude=69.6,
            area_ha=2.5,
            name="Хлопковое поле 1",
        )
        self.assertTrue(created)
        self.assertIsInstance(field_id, int)

        # Upsert again -> should update, not create new
        field_id2, created2 = field_state.upsert_managed_field(
            user_id=1002,
            field_key=key,
            crop="cotton",
            soil="clay",
            irrigation="furrow",
            planting_date="2026-04-15",
            initial_deficit=5.5,
            latitude=42.3,
            longitude=69.6,
            area_ha=3.0,
            name="Хлопковое поле 1 (обновлено)",
        )
        self.assertEqual(field_id, field_id2)
        self.assertFalse(created2)

        field = field_state.get_field(field_id, user_id=1002)
        self.assertEqual(field["area_ha"], 3.0)
        self.assertEqual(field["name"], "Хлопковое поле 1 (обновлено)")

    def test_04_daily_balance_and_irrigation(self):
        field_id = field_state.add_new_field(
            user_id=1003,
            crop="tomato",
            soil="sand",
            irrigation="drip",
            planting_date="2026-05-10",
        )
        # Update daily deficit
        new_deficit = field_state.update_daily_deficit(field_id, et_c=4.5, effective_rain=0.0)
        self.assertEqual(new_deficit, 4.5)

        # Save daily balance record
        result = {
            "et0": 5.0,
            "rain": 0.0,
            "peff": 0.0,
            "etc": 4.5,
            "deficit": 4.5,
            "status": "irrigate",
            "net_m3": 45.0,
            "gross_m3": 50.0,
        }
        balance, saved = field_state.save_daily_balance(
            field_id,
            user_id=1003,
            balance_date="2026-05-15",
            timezone="Asia/Almaty",
            result=result,
            deficit_before=0.0,
        )
        self.assertTrue(saved)
        self.assertEqual(balance["status"], "irrigate")

        # Second save for same date -> should return existing without re-saving
        balance2, saved2 = field_state.save_daily_balance(
            field_id,
            user_id=1003,
            balance_date="2026-05-15",
            timezone="Asia/Almaty",
            result=result,
            deficit_before=0.0,
        )
        self.assertFalse(saved2)

        # Record irrigation (full reset)
        irrig = field_state.record_irrigation(field_id, user_id=1003)
        self.assertEqual(irrig["deficit_after"], 0.0)
        self.assertEqual(irrig["deficit_before"], 4.5)

        # Verify field is reset
        field = field_state.get_field(field_id, user_id=1003)
        self.assertEqual(field["accumulated_deficit"], 0.0)

    def test_05_postgres_detection_and_query_translation(self):
        with patch.object(db, "DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb"):
            self.assertTrue(db.is_postgres())

        with patch.object(db, "DATABASE_URL", "postgres://user:pass@localhost:5432/testdb"):
            self.assertTrue(db.is_postgres())

        with patch.object(db, "DATABASE_URL", ""):
            self.assertFalse(db.is_postgres())

        # Test query translation logic
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(db, "is_postgres", return_value=True):
            db.execute_query(mock_conn, "SELECT * FROM t WHERE a = ? AND b = ?", (1, 2))
            mock_cursor.execute.assert_called_once_with(
                "SELECT * FROM t WHERE a = %s AND b = %s", (1, 2)
            )


if __name__ == "__main__":
    unittest.main()
