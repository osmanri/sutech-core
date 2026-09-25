"""Migration utility: Transfer data from local SQLite (history.db) to PostgreSQL.

Usage:
    python -m bot.migrate_sqlite_to_pg [--sqlite-path path/to/history.db] [--pg-url postgresql://...]

Requires DATABASE_URL environment variable or --pg-url argument.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    psycopg2 = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sqlite_to_pg")


def migrate(sqlite_path: str, pg_url: str) -> bool:
    if not psycopg2:
        logger.error("psycopg2 is required for PostgreSQL migration. Run: pip install psycopg2-binary")
        return False

    if not os.path.exists(sqlite_path):
        logger.error("SQLite database not found at: %s", sqlite_path)
        return False

    logger.info("Opening SQLite database: %s", sqlite_path)
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    logger.info("Connecting to PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(pg_url)
    except Exception as exc:
        logger.error("Failed to connect to PostgreSQL: %s", exc)
        sqlite_conn.close()
        return False

    try:
        # 1. Migrate users
        _migrate_table(
            sqlite_conn, pg_conn,
            table="users",
            columns=["user_id", "lang", "updated_at"],
            conflict_target="user_id",
            conflict_action="DO UPDATE SET lang = EXCLUDED.lang, updated_at = EXCLUDED.updated_at",
        )

        # 2. Migrate report_explanations
        _migrate_table(
            sqlite_conn, pg_conn,
            table="report_explanations",
            columns=["id", "user_id", "explanation"],
            conflict_target="id",
            conflict_action="DO NOTHING",
        )

        # 3. Migrate history
        _migrate_table(
            sqlite_conn, pg_conn,
            table="history",
            columns=["id", "user_id", "created_at", "crop_name", "area_text", "irrigation_text", "volume_text", "savings_text", "lang"],
            conflict_target="id",
            conflict_action="DO NOTHING",
            has_serial_id=True,
        )

        # 4. Migrate fields
        _migrate_table(
            sqlite_conn, pg_conn,
            table="fields",
            columns=[
                "id", "user_id", "crop_type", "soil_type", "irrigation_method", "planting_date",
                "accumulated_deficit", "field_key", "name", "latitude", "longitude", "area_ha",
                "field_type", "is_saline", "stage_days", "custom_kc", "custom_p", "custom_root_depth",
                "power_price", "pump_power_kw", "pump_productivity_m3h", "greenhouse_et0", "updated_at"
            ],
            conflict_target="id",
            conflict_action="DO NOTHING",
            has_serial_id=True,
        )

        # 5. Migrate field_daily_balances
        _migrate_table(
            sqlite_conn, pg_conn,
            table="field_daily_balances",
            columns=[
                "id", "field_id", "balance_date", "timezone", "et0", "rain", "effective_rain",
                "etc", "deficit_before", "deficit_after", "status", "net_m3", "gross_m3",
                "calculation_version", "result_json", "created_at", "alert_state",
                "alert_claimed_at"
            ],
            conflict_target="id",
            conflict_action="DO NOTHING",
            has_serial_id=True,
        )

        # 6. Migrate irrigation_events
        _migrate_table(
            sqlite_conn, pg_conn,
            table="irrigation_events",
            columns=["id", "field_id", "user_id", "applied_m3", "deficit_before", "deficit_after", "source", "created_at"],
            conflict_target="id",
            conflict_action="DO NOTHING",
            has_serial_id=True,
        )

        pg_conn.commit()
        logger.info("All tables migrated successfully!")
        return True
    except Exception as exc:
        pg_conn.rollback()
        logger.exception("Migration failed: %s", exc)
        return False
    finally:
        sqlite_conn.close()
        pg_conn.close()


def _migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    table: str,
    columns: list[str],
    conflict_target: str,
    conflict_action: str,
    has_serial_id: bool = False,
) -> None:
    # Check if table exists in SQLite
    cur = sqlite_conn.cursor()
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    if not cur.fetchone():
        logger.info("Table '%s' does not exist in SQLite source, skipping.", table)
        return

    # Check available columns in SQLite
    existing_cols = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
    valid_cols = [col for col in columns if col in existing_cols]

    if not valid_cols:
        logger.warning("No matching columns for table '%s', skipping.", table)
        return

    col_names = ", ".join(valid_cols)
    placeholders = ", ".join(["%s"] * len(valid_cols))
    select_sql = f"SELECT {col_names} FROM {table}"
    cur.execute(select_sql)
    rows = cur.fetchall()

    if not rows:
        logger.info("Table '%s' is empty, 0 rows to migrate.", table)
        return

    logger.info("Migrating %d rows from table '%s'...", len(rows), table)

    insert_sql = f"""
        INSERT INTO {table} ({col_names})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_target}) {conflict_action}
    """

    pg_cur = pg_conn.cursor()
    for row in rows:
        pg_cur.execute(insert_sql, tuple(row))

    if has_serial_id and "id" in valid_cols:
        # Reset PostgreSQL serial sequence to max(id) + 1
        seq_sql = f"""
            SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id), 1))
            FROM {table};
        """
        # A failed statement aborts the PostgreSQL transaction. Let migrate()
        # roll the whole copy back instead of reporting a false success.
        pg_cur.execute(seq_sql)

    logger.info("Table '%s': %d rows processed.", table, len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Su-Tech data from SQLite to PostgreSQL")
    default_sqlite = os.getenv("DB_PATH", str(Path(__file__).with_name("history.db")))
    parser.add_argument("--sqlite-path", default=default_sqlite, help="Path to SQLite database")
    default_pg = os.getenv("DATABASE_URL", "")
    parser.add_argument("--pg-url", default=default_pg, help="PostgreSQL connection string")
    args = parser.parse_args()

    if not args.pg_url:
        logger.error("No PostgreSQL URL provided. Set DATABASE_URL or pass --pg-url.")
        sys.exit(1)

    success = migrate(args.sqlite_path, args.pg_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
