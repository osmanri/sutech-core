import sqlite3
import logging
import os
import uuid
from contextlib import closing
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).with_name("history.db")))


def _ensure_columns(cursor, table: str, columns: dict[str, str]) -> None:
    """Add new nullable/defaulted columns without breaking existing SQLite files."""
    existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                created_at TEXT,
                crop_name TEXT,
                area_text TEXT,
                irrigation_text TEXT,
                volume_text TEXT,
                savings_text TEXT,
                lang TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report_explanations (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                explanation TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL DEFAULT 'ru',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                crop_type TEXT NOT NULL,
                soil_type TEXT NOT NULL,
                irrigation_method TEXT NOT NULL,
                planting_date TEXT NOT NULL,
                accumulated_deficit REAL NOT NULL DEFAULT 0.0
                    CHECK (accumulated_deficit >= 0.0)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fields_user_id
            ON fields (user_id)
        """)
        _ensure_columns(cursor, "fields", {
            "field_key": "TEXT",
            "name": "TEXT NOT NULL DEFAULT ''",
            "latitude": "REAL",
            "longitude": "REAL",
            "area_ha": "REAL",
            "field_type": "TEXT NOT NULL DEFAULT 'open'",
            "is_saline": "INTEGER NOT NULL DEFAULT 0",
            "stage_days": "TEXT",
            "custom_kc": "REAL",
            "custom_p": "REAL",
            "custom_root_depth": "REAL",
            "power_price": "REAL",
            "pump_power_kw": "REAL",
            "pump_productivity_m3h": "REAL",
            "greenhouse_et0": "REAL",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        })
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_fields_owner_key
            ON fields (user_id, field_key)
            WHERE field_key IS NOT NULL
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS field_daily_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id INTEGER NOT NULL,
                balance_date TEXT NOT NULL,
                timezone TEXT NOT NULL,
                et0 REAL NOT NULL,
                rain REAL NOT NULL,
                effective_rain REAL NOT NULL,
                etc REAL NOT NULL,
                deficit_before REAL NOT NULL,
                deficit_after REAL NOT NULL,
                status TEXT NOT NULL,
                net_m3 REAL NOT NULL,
                gross_m3 REAL NOT NULL,
                calculation_version TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (field_id, balance_date),
                FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_field_date
            ON field_daily_balances (field_id, balance_date DESC)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS irrigation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                applied_m3 REAL,
                deficit_before REAL NOT NULL,
                deficit_after REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'telegram',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        logger.info("SQLite DB (history) initialized.")
    except Exception as e:
        logger.exception("Error initializing SQLite DB: %s", e)
        # Starting with a missing or partially migrated database would make the
        # health endpoint look healthy while field state silently disappears.
        # Let the process fail so Render can report the deployment as broken.
        raise
    finally:
        if conn is not None:
            conn.close()

def save_calculation(user_id: int, crop_name: str, area_text: str, irrigation_text: str, volume_text: str, savings_text: str, lang: str, created_at: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (user_id, created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving calculation to SQLite: {e}")

def get_user_history(user_id: int) -> List[Dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang
            FROM history
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 10
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "date": row[0],
                "crop_name": row[1],
                "area_text": row[2],
                "irrigation_text": row[3],
                "volume_text": row[4],
                "savings_text": row[5],
                "lang": row[6]
            })
        return history
    except Exception as e:
        logger.error(f"Error fetching history from SQLite: {e}")
        return []


def save_report_explanation(user_id: int, explanation: str) -> str | None:
    report_id = uuid.uuid4().hex
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.execute("INSERT INTO report_explanations VALUES (?, ?, ?)",
                         (report_id, user_id, explanation))
            conn.commit()
        return report_id
    except sqlite3.Error:
        logger.exception("Could not save report explanation")
        return None


def get_report_explanation(report_id: str, user_id: int) -> str | None:
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            row = conn.execute(
                "SELECT explanation FROM report_explanations WHERE id = ? AND user_id = ?",
                (report_id, user_id),
            ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.exception("Could not load report explanation")
        return None


def get_user_language(user_id: int) -> str | None:
    """Return a persisted language, or None for a first-time user."""
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            row = conn.execute(
                "SELECT lang FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row and row[0] in {"ru", "kz"} else None
    except Exception as exc:
        logger.error("Error fetching user language: %s", exc)
        return None


def set_user_language(user_id: int, lang: str) -> None:
    """Persist the selected language across bot and Render restarts."""
    if lang not in {"ru", "kz"}:
        raise ValueError(f"Unsupported language: {lang}")
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, lang, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    lang = excluded.lang,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, lang),
            )
            conn.commit()
    except Exception as exc:
        logger.error("Error saving user language: %s", exc)
