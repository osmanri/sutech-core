"""Checks that migrating saved field state does not drop unsent alerts."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot import migrate_sqlite_to_pg


class MigrationIntegrityTests(unittest.TestCase):
    def test_pending_alert_survives_sqlite_to_postgres_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.db"
            with closing(sqlite3.connect(source)) as conn:
                conn.execute("""
                    CREATE TABLE field_daily_balances (
                        id INTEGER PRIMARY KEY, field_id INTEGER, balance_date TEXT,
                        alert_state TEXT, alert_claimed_at TEXT
                    )
                """)
                conn.execute("""
                    INSERT INTO field_daily_balances
                        (id, field_id, balance_date, alert_state, alert_claimed_at)
                    VALUES (1, 7, '2026-09-25', 'pending', NULL)
                """)
                conn.commit()

            cursor = SimpleNamespace(execute=Mock())
            target = SimpleNamespace(cursor=Mock(return_value=cursor), commit=Mock(),
                                     rollback=Mock(), close=Mock())
            driver = SimpleNamespace(connect=Mock(return_value=target))
            with patch.object(migrate_sqlite_to_pg, "psycopg2", driver):
                self.assertTrue(migrate_sqlite_to_pg.migrate(str(source), "postgresql://test"))

            inserts = [call for call in cursor.execute.call_args_list
                       if "INSERT INTO field_daily_balances" in call.args[0]]
            self.assertEqual(len(inserts), 1)
            sql, values = inserts[0].args
            columns = sql.split("(", 1)[1].split(")", 1)[0].replace(" ", "").split(",")
            saved = dict(zip(columns, values))
            self.assertEqual(saved["alert_state"], "pending")
            self.assertIsNone(saved["alert_claimed_at"])
            target.commit.assert_called_once()

    def test_sequence_failure_rolls_back_instead_of_claiming_success(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "history.db"
            with closing(sqlite3.connect(source)) as conn:
                conn.execute("CREATE TABLE history (id INTEGER PRIMARY KEY, user_id INTEGER)")
                conn.execute("INSERT INTO history (id, user_id) VALUES (5, 42)")
                conn.commit()

            def execute(sql, *_args):
                if "setval(" in sql:
                    raise RuntimeError("sequence reset failed")

            cursor = SimpleNamespace(execute=Mock(side_effect=execute))
            target = SimpleNamespace(cursor=Mock(return_value=cursor), commit=Mock(),
                                     rollback=Mock(), close=Mock())
            driver = SimpleNamespace(connect=Mock(return_value=target))
            with patch.object(migrate_sqlite_to_pg, "psycopg2", driver), \
                 patch.object(migrate_sqlite_to_pg.logger, "exception"):
                self.assertFalse(migrate_sqlite_to_pg.migrate(str(source), "postgresql://test"))
            target.rollback.assert_called_once()
            target.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
