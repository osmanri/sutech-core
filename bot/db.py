import sqlite3
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

DB_PATH = "history.db"

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
