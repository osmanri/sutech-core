import sqlite3
import logging
import os
import uuid
from contextlib import closing
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).with_name("history.db")))

def init_db():
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
        conn.commit()
        conn.close()
        logger.info("SQLite DB (history) initialized.")
    except Exception as e:
        logger.error(f"Error initializing SQLite DB: {e}")

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
