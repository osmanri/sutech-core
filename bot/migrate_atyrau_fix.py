"""
Скрипт миграции базы данных:
1. Заменяет все вхождения 'Asia/Oral' на 'Asia/Atyrau' в field_daily_balances.
2. Обновляет дефолтные координаты для полей без координат на координаты Атырау (47.1167, 51.8833).
3. Переназначает координаты Уральска (~51.2, ~51.3) на Атырау.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

try:
    import db as database
except ImportError:
    from bot import db as database

logger = logging.getLogger(__name__)


def run_atyrau_migration(conn=None) -> dict[str, int]:
    """
    Выполняет безопасное обновление существующих записей в SQLite / PostgreSQL.
    Возвращает статистику обновленных строк.
    """
    close_after = False
    if conn is None:
        conn = database.get_connection()
        close_after = True

    stats = {"balances_updated": 0, "fields_coords_updated": 0, "uralsk_coords_fixed": 0}

    try:
        # 1. Обновление таймзоны в суточных балансах
        sql_tz = """
            UPDATE field_daily_balances
            SET timezone = 'Asia/Atyrau'
            WHERE timezone = 'Asia/Oral' 
               OR timezone IS NULL 
               OR timezone = '' 
               OR timezone LIKE '%Oral%'
        """
        cur = database.execute_query(conn, sql_tz)
        stats["balances_updated"] = cur.rowcount if hasattr(cur, "rowcount") else 0

        # 2. Обновление полей с пустыми координатами на координаты Атырау
        sql_empty_coords = """
            UPDATE fields
            SET latitude = 47.1167, longitude = 51.8833
            WHERE latitude IS NULL OR longitude IS NULL
        """
        cur = database.execute_query(conn, sql_empty_coords)
        stats["fields_coords_updated"] = cur.rowcount if hasattr(cur, "rowcount") else 0

        # 3. Обновление полей с координатами Уральска (~51.2, ~51.3) на Атырау
        sql_uralsk = """
            UPDATE fields
            SET latitude = 47.1167, longitude = 51.8833
            WHERE (latitude BETWEEN 51.10 AND 51.40) 
              AND (longitude BETWEEN 51.10 AND 51.60)
        """
        cur = database.execute_query(conn, sql_uralsk)
        stats["uralsk_coords_fixed"] = cur.rowcount if hasattr(cur, "rowcount") else 0

        conn.commit()
        logger.info("Миграция Атырау завершена успешно: %s", stats)
        return stats
    except Exception as exc:
        logger.exception("Ошибка при выполнении миграции Атырау: %s", exc)
        raise
    finally:
        if close_after and conn is not None:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_atyrau_migration()
    print("Результат миграции:", result)
