"""Persistent state for a farmer's fields.

The functions in this module are synchronous and intentionally small.  In an
async Telegram handler call them through ``asyncio.to_thread`` (see the module
doc example in FIELD_STATE.md) so a slow disk cannot block other updates.
"""

from __future__ import annotations

import math
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime
from typing import Any

try:
    import db as database
except ImportError:  # package import, e.g. ``python -m bot.main``
    from bot import db as database


_CODE_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


class FieldStateError(RuntimeError):
    """Base error for field state operations."""


class FieldNotFoundError(FieldStateError):
    """Raised when the requested field does not exist or belongs to another user."""


class InvalidFieldDataError(ValueError, FieldStateError):
    """Raised when input cannot safely be stored or used in a calculation."""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database.DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise InvalidFieldDataError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldDataError(f"{label} must be a positive integer") from exc
    if number <= 0:
        raise InvalidFieldDataError(f"{label} must be a positive integer")
    return number


def _code(value: Any, label: str) -> str:
    normalized = str(value).strip().lower() if value is not None else ""
    if not _CODE_RE.fullmatch(normalized):
        raise InvalidFieldDataError(
            f"{label} must contain 1-64 lowercase Latin letters, digits, '_' or '-'"
        )
    return normalized


def _non_negative_number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise InvalidFieldDataError(f"{label} must be a finite non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldDataError(f"{label} must be a finite non-negative number") from exc
    if not math.isfinite(number) or number < 0:
        raise InvalidFieldDataError(f"{label} must be a finite non-negative number")
    return number


def _date_value(value: date | datetime | str | None) -> date:
    if value is None:
        result = date.today()
    elif isinstance(value, datetime):
        result = value.date()
    elif isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError as exc:
            raise InvalidFieldDataError("planting_date must use YYYY-MM-DD") from exc
    else:
        raise InvalidFieldDataError("planting_date must be a date, datetime or YYYY-MM-DD")
    if result > date.today():
        raise InvalidFieldDataError("planting_date cannot be in the future")
    return result


def add_new_field(
    user_id: int,
    crop: str,
    soil: str,
    irrigation: str,
    planting_date: date | datetime | str | None = None,
) -> int:
    """Create a field and return its database id."""
    values = (
        _positive_int(user_id, "user_id"),
        _code(crop, "crop"),
        _code(soil, "soil"),
        _code(irrigation, "irrigation"),
        _date_value(planting_date).isoformat(),
    )
    try:
        with closing(_connect()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO fields
                    (user_id, crop_type, soil_type, irrigation_method, planting_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                values,
            )
            conn.commit()
            return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        raise FieldStateError("Could not create field") from exc


def get_field(field_id: int, *, user_id: int | None = None) -> dict[str, Any]:
    """Return one field; optional user_id prevents cross-user access."""
    field_key = _positive_int(field_id, "field_id")
    params: tuple[int, ...]
    sql = "SELECT * FROM fields WHERE id = ?"
    params = (field_key,)
    if user_id is not None:
        sql += " AND user_id = ?"
        params += (_positive_int(user_id, "user_id"),)
    try:
        with closing(_connect()) as conn:
            row = conn.execute(sql, params).fetchone()
    except sqlite3.Error as exc:
        raise FieldStateError("Could not load field") from exc
    if row is None:
        raise FieldNotFoundError(f"Field {field_key} was not found")
    return dict(row)


def get_day_of_growth(field_id: int, *, today: date | None = None) -> int:
    """Return elapsed full calendar days; planting day is day 0."""
    row = get_field(field_id)
    current_day = today or date.today()
    if not isinstance(current_day, date):
        raise InvalidFieldDataError("today must be a date")
    days = (current_day - date.fromisoformat(row["planting_date"])).days
    if days < 0:
        raise InvalidFieldDataError("today cannot be before planting_date")
    return days


def update_daily_deficit(field_id: int, et_c: float, effective_rain: float) -> float:
    """Atomically apply max(0, old deficit + ETc - effective rain)."""
    field_key = _positive_int(field_id, "field_id")
    evaporation = _non_negative_number(et_c, "et_c")
    rain = _non_negative_number(effective_rain, "effective_rain")
    try:
        with closing(_connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE fields
                SET accumulated_deficit = MAX(0.0, accumulated_deficit + ? - ?)
                WHERE id = ?
                """,
                (evaporation, rain, field_key),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise FieldNotFoundError(f"Field {field_key} was not found")
            value = conn.execute(
                "SELECT accumulated_deficit FROM fields WHERE id = ?", (field_key,)
            ).fetchone()[0]
            conn.commit()
            return float(value)
    except FieldNotFoundError:
        raise
    except sqlite3.Error as exc:
        raise FieldStateError("Could not update daily deficit") from exc


def reset_deficit(field_id: int, *, user_id: int | None = None) -> float:
    """Set deficit to zero after confirmed irrigation.

    Telegram callbacks should pass ``user_id=callback.from_user.id`` so one
    farmer cannot reset another farmer's field using a forged callback value.
    """
    field_key = _positive_int(field_id, "field_id")
    params: tuple[int, ...] = (field_key,)
    sql = "UPDATE fields SET accumulated_deficit = 0.0 WHERE id = ?"
    if user_id is not None:
        sql += " AND user_id = ?"
        params += (_positive_int(user_id, "user_id"),)
    try:
        with closing(_connect()) as conn:
            cursor = conn.execute(sql, params)
            if cursor.rowcount != 1:
                conn.rollback()
                raise FieldNotFoundError(f"Field {field_key} was not found")
            conn.commit()
            return 0.0
    except FieldNotFoundError:
        raise
    except sqlite3.Error as exc:
        raise FieldStateError("Could not reset deficit") from exc


def list_user_fields(user_id: int) -> list[dict[str, Any]]:
    """Return all fields owned by a Telegram user."""
    owner = _positive_int(user_id, "user_id")
    try:
        with closing(_connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM fields WHERE user_id = ? ORDER BY id", (owner,)
            ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise FieldStateError("Could not list fields") from exc
