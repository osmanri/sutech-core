import sqlite3
import logging
import os
import sys
import uuid
from contextlib import closing
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Ensure 'db' and 'bot.db' refer to the exact same module in sys.modules
if "db" in sys.modules and __name__ == "bot.db":
    sys.modules["bot.db"] = sys.modules["db"]
elif "bot.db" in sys.modules and __name__ == "db":
    sys.modules["db"] = sys.modules["bot.db"]
elif __name__ == "bot.db":
    sys.modules["db"] = sys.modules[__name__]
elif __name__ == "db":
    sys.modules["bot.db"] = sys.modules[__name__]

try:
    from config import DATABASE_URL
except ImportError:
    try:
        from bot.config import DATABASE_URL
    except ImportError:
        DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    psycopg2 = None
    DictCursor = None

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).with_name("history.db")))

if HAS_PSYCOPG2:
    DatabaseError: Tuple[type, ...] = (sqlite3.Error, psycopg2.Error)
else:
    DatabaseError = (sqlite3.Error,)


def is_postgres() -> bool:
    """Check whether a PostgreSQL database is configured via DATABASE_URL."""
    url = (DATABASE_URL or os.getenv("DATABASE_URL", "")).strip()
    return url.startswith("postgres://") or url.startswith("postgresql://")


def get_connection():
    """Return an active connection configured for dict-like and index-like row access."""
    if is_postgres():
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2 is required when DATABASE_URL is configured for PostgreSQL")
        url = (DATABASE_URL or os.getenv("DATABASE_URL", "")).strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, cursor_factory=DictCursor)
        return conn
    else:
        parent = Path(DB_PATH).parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def begin_immediate(conn) -> None:
    """Acquire a write lock/transaction appropriately for the active database engine."""
    if is_postgres():
        # psycopg2 starts transactions automatically, ensure autocommit is False
        conn.autocommit = False
    else:
        conn.execute("BEGIN IMMEDIATE")


def execute_query(conn, sql: str, params: tuple | list = ()):
    """Execute a parameterized query, translating '?' to '%s' when on PostgreSQL."""
    if is_postgres():
        sql_pg = sql.replace("?", "%s")
        cursor = conn.cursor()
        cursor.execute(sql_pg, params)
        return cursor
    else:
        return conn.execute(sql, params)


def check_db_health() -> dict[str, Any]:
    """Test database connectivity and return status without leaking credentials."""
    engine = "postgresql" if is_postgres() else "sqlite"
    try:
        with closing(get_connection()) as conn:
            cursor = execute_query(conn, "SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                return {"status": "connected", "engine": engine}
            return {"status": "degraded", "engine": engine}
    except Exception as exc:
        logger.error("Database health check failed for %s: %s", engine, exc)
        return {"status": "error", "engine": engine, "detail": str(exc)}


def _ensure_columns_sqlite(cursor, table: str, columns: dict[str, str]) -> None:
    """Add new nullable/defaulted columns without breaking existing SQLite files."""
    existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _ensure_columns_postgres(cursor, table: str, columns: dict[str, str]) -> None:
    """Add new columns to a PostgreSQL table if they don't already exist."""
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    existing = {row[0] for row in cursor.fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db():
    """Initialize database tables and indexes for either SQLite or PostgreSQL."""
    conn = None
    try:
        conn = get_connection()
        if is_postgres():
            _init_postgres(conn)
        else:
            _init_sqlite(conn)
        logger.info("Database initialized successfully on %s.", "PostgreSQL" if is_postgres() else "SQLite")
    except Exception as e:
        logger.exception("Error initializing database: %s", e)
        raise
    finally:
        if conn is not None:
            conn.close()


def _init_sqlite(conn):
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
    _ensure_columns_sqlite(cursor, "fields", {
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
    _ensure_columns_sqlite(cursor, "field_daily_balances", {
        "alert_state": "TEXT NOT NULL DEFAULT 'done'",
        "alert_claimed_at": "TEXT",
    })
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
    # Keep the field's actual timezone and coordinates. Missing locations must
    # be completed by the farmer, never silently replaced with Atyrau.
    conn.commit()


def _init_postgres(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            created_at TEXT,
            crop_name TEXT,
            area_text TEXT,
            irrigation_text TEXT,
            volume_text TEXT,
            savings_text TEXT,
            lang TEXT
        );
        CREATE TABLE IF NOT EXISTS report_explanations (
            id TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            explanation TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            lang TEXT NOT NULL DEFAULT 'ru',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fields (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            crop_type TEXT NOT NULL,
            soil_type TEXT NOT NULL,
            irrigation_method TEXT NOT NULL,
            planting_date TEXT NOT NULL,
            accumulated_deficit REAL NOT NULL DEFAULT 0.0
                CHECK (accumulated_deficit >= 0.0),
            field_key TEXT,
            name TEXT NOT NULL DEFAULT '',
            latitude REAL,
            longitude REAL,
            area_ha REAL,
            field_type TEXT NOT NULL DEFAULT 'open',
            is_saline INTEGER NOT NULL DEFAULT 0,
            stage_days TEXT,
            custom_kc REAL,
            custom_p REAL,
            custom_root_depth REAL,
            power_price REAL,
            pump_power_kw REAL,
            pump_productivity_m3h REAL,
            greenhouse_et0 REAL,
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_fields_user_id ON fields (user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_fields_owner_key
            ON fields (user_id, field_key) WHERE field_key IS NOT NULL;
        CREATE TABLE IF NOT EXISTS field_daily_balances (
            id SERIAL PRIMARY KEY,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
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
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (field_id, balance_date)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_field_date
            ON field_daily_balances (field_id, balance_date DESC);
        CREATE TABLE IF NOT EXISTS irrigation_events (
            id SERIAL PRIMARY KEY,
            field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            applied_m3 REAL,
            deficit_before REAL NOT NULL,
            deficit_after REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'telegram',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    _ensure_columns_postgres(cursor, "fields", {
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
    _ensure_columns_postgres(cursor, "field_daily_balances", {
        "alert_state": "TEXT NOT NULL DEFAULT 'done'",
        "alert_claimed_at": "TIMESTAMP",
    })
    # Existing field coordinates and local dates are authoritative.
    conn.commit()


def save_calculation(user_id: int, crop_name: str, area_text: str, irrigation_text: str,
                     volume_text: str, savings_text: str, lang: str, created_at: str) -> None:
    try:
        with closing(get_connection()) as conn:
            execute_query(
                conn,
                """
                INSERT INTO history (user_id, created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving calculation: {e}")


def get_user_history(user_id: int) -> List[Dict]:
    try:
        with closing(get_connection()) as conn:
            cursor = execute_query(
                conn,
                """
                SELECT created_at, crop_name, area_text, irrigation_text, volume_text, savings_text, lang
                FROM history
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 10
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        history = []
        for row in rows:
            history.append({
                "date": row[0],
                "crop_name": row[1],
                "area_text": row[2],
                "irrigation_text": row[3],
                "volume_text": row[4],
                "savings_text": row[5],
                "lang": row[6],
            })
        return history
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []


def save_report_explanation(user_id: int, explanation: str) -> str | None:
    report_id = uuid.uuid4().hex
    try:
        with closing(get_connection()) as conn:
            execute_query(
                conn,
                "INSERT INTO report_explanations (id, user_id, explanation) VALUES (?, ?, ?)",
                (report_id, user_id, explanation),
            )
            conn.commit()
        return report_id
    except DatabaseError:
        logger.exception("Could not save report explanation")
        return None


def get_report_explanation(report_id: str, user_id: int) -> str | None:
    try:
        with closing(get_connection()) as conn:
            cursor = execute_query(
                conn,
                "SELECT explanation FROM report_explanations WHERE id = ? AND user_id = ?",
                (report_id, user_id),
            )
            row = cursor.fetchone()
        return row[0] if row else None
    except DatabaseError:
        logger.exception("Could not load report explanation")
        return None


def get_user_language(user_id: int) -> str | None:
    """Return a persisted language, or None for a first-time user."""
    try:
        with closing(get_connection()) as conn:
            cursor = execute_query(
                conn,
                "SELECT lang FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
        return row[0] if row and row[0] in {"ru", "kz", "en"} else None
    except Exception as exc:
        logger.error("Error fetching user language: %s", exc)
        return None


def set_user_language(user_id: int, lang: str) -> None:
    """Persist the selected language across bot and Render restarts."""
    if lang not in {"ru", "kz", "en"}:
        raise ValueError(f"Unsupported language: {lang}")
    try:
        with closing(get_connection()) as conn:
            execute_query(
                conn,
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
