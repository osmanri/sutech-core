"""Persistent state for a farmer's fields.

The functions in this module are synchronous and intentionally small. In an
async Telegram handler call them through ``asyncio.to_thread`` (see the module
doc example in FIELD_STATE.md) so a slow disk or network cannot block other updates.
"""

from __future__ import annotations

import math
import re
import hashlib
import json
from contextlib import closing
from datetime import date, datetime
from typing import Any

import sys

# Ensure 'field_state' and 'bot.field_state' refer to the exact same module in sys.modules
if "field_state" in sys.modules and __name__ == "bot.field_state":
    sys.modules["bot.field_state"] = sys.modules["field_state"]
elif "bot.field_state" in sys.modules and __name__ == "field_state":
    sys.modules["field_state"] = sys.modules["bot.field_state"]
elif __name__ == "bot.field_state":
    sys.modules["field_state"] = sys.modules[__name__]
elif __name__ == "field_state":
    sys.modules["bot.field_state"] = sys.modules[__name__]

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


def _connect():
    return database.get_connection()


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
            cursor = database.execute_query(
                conn,
                """
                INSERT INTO fields
                    (user_id, crop_type, soil_type, irrigation_method, planting_date)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                values,
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0])
    except database.DatabaseError as exc:
        raise FieldStateError("Could not create field") from exc


def get_field(field_id: int, *, user_id: int | None = None) -> dict[str, Any]:
    """Return one field; optional user_id prevents cross-user access."""
    field_key = _positive_int(field_id, "field_id")
    sql = "SELECT * FROM fields WHERE id = ?"
    params: tuple[Any, ...] = (field_key,)
    if user_id is not None:
        sql += " AND user_id = ?"
        params += (_positive_int(user_id, "user_id"),)
    try:
        with closing(_connect()) as conn:
            row = database.execute_query(conn, sql, params).fetchone()
    except database.DatabaseError as exc:
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
            database.begin_immediate(conn)
            cursor = database.execute_query(
                conn,
                """
                UPDATE fields
                SET accumulated_deficit = CASE
                    WHEN (accumulated_deficit + ? - ?) < 0.0 THEN 0.0
                    ELSE (accumulated_deficit + ? - ?)
                END
                WHERE id = ?
                """,
                (evaporation, rain, evaporation, rain, field_key),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise FieldNotFoundError(f"Field {field_key} was not found")
            value = database.execute_query(
                conn, "SELECT accumulated_deficit FROM fields WHERE id = ?", (field_key,)
            ).fetchone()[0]
            conn.commit()
            return float(value)
    except FieldNotFoundError:
        raise
    except database.DatabaseError as exc:
        raise FieldStateError("Could not update daily deficit") from exc


def reset_deficit(field_id: int, *, user_id: int | None = None) -> float:
    """Set deficit to zero after confirmed irrigation."""
    field_key = _positive_int(field_id, "field_id")
    params: tuple[Any, ...] = (field_key,)
    sql = "UPDATE fields SET accumulated_deficit = 0.0 WHERE id = ?"
    if user_id is not None:
        sql += " AND user_id = ?"
        params += (_positive_int(user_id, "user_id"),)
    try:
        with closing(_connect()) as conn:
            cursor = database.execute_query(conn, sql, params)
            if cursor.rowcount != 1:
                conn.rollback()
                raise FieldNotFoundError(f"Field {field_key} was not found")
            conn.commit()
            return 0.0
    except FieldNotFoundError:
        raise
    except database.DatabaseError as exc:
        raise FieldStateError("Could not reset deficit") from exc


def list_user_fields(user_id: int) -> list[dict[str, Any]]:
    """Return all fields owned by a Telegram user."""
    owner = _positive_int(user_id, "user_id")
    try:
        with closing(_connect()) as conn:
            rows = database.execute_query(
                conn, "SELECT * FROM fields WHERE user_id = ? ORDER BY id", (owner,)
            ).fetchall()
        return [dict(row) for row in rows]
    except database.DatabaseError as exc:
        raise FieldStateError("Could not list fields") from exc


def list_managed_fields() -> list[dict[str, Any]]:
    """Return fields that have enough location data for automatic weather updates."""
    try:
        with closing(_connect()) as conn:
            rows = database.execute_query(conn, """
                SELECT * FROM fields
                WHERE field_key IS NOT NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
                ORDER BY id
            """).fetchall()
        return [dict(row) for row in rows]
    except database.DatabaseError as exc:
        raise FieldStateError("Could not list managed fields") from exc


def make_field_key(latitude: Any, longitude: Any, area_ha: Any, crop: Any) -> str:
    """Build a stable, non-sensitive key for repeated submissions of one field."""
    lat = _non_negative_number(abs(float(latitude)), "latitude")
    lon = _non_negative_number(abs(float(longitude)), "longitude")
    if not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180:
        raise InvalidFieldDataError("invalid coordinates")
    area = _non_negative_number(area_ha, "area_ha")
    crop_code = _code(crop, "crop")
    source = f"{float(latitude):.5f}|{float(longitude):.5f}|{area:.6f}|{crop_code}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]


def upsert_managed_field(
    *, user_id: int, field_key: str, crop: str, soil: str, irrigation: str,
    planting_date: date | datetime | str, initial_deficit: float,
    latitude: float, longitude: float, area_ha: float, field_type: str = "open",
    is_saline: bool = False, stage_days: tuple | list | None = None,
    custom_kc: float | None = None, custom_p: float | None = None,
    custom_root_depth: float | None = None, power_price: float | None = None,
    pump_power_kw: float | None = None, pump_productivity_m3h: float | None = None,
    greenhouse_et0: float | None = None, name: str = "",
) -> tuple[int, bool]:
    """Create or refresh a tracked field while preserving its running deficit."""
    owner = _positive_int(user_id, "user_id")
    key = str(field_key).strip()
    if not re.fullmatch(r"[a-f0-9]{24}", key):
        raise InvalidFieldDataError("field_key is invalid")
    values = {
        "crop": _code(crop, "crop"), "soil": _code(soil, "soil"),
        "irrigation": _code(irrigation, "irrigation"),
        "planting": _date_value(planting_date).isoformat(),
        "deficit": _non_negative_number(initial_deficit, "initial_deficit"),
        "latitude": float(latitude), "longitude": float(longitude),
        "area": _non_negative_number(area_ha, "area_ha"),
    }
    if not -90 <= values["latitude"] <= 90 or not -180 <= values["longitude"] <= 180:
        raise InvalidFieldDataError("invalid coordinates")
    if field_type not in {"open", "greenhouse"}:
        raise InvalidFieldDataError("field_type is invalid")
    stages_json = json.dumps(list(stage_days), separators=(",", ":")) if stage_days else None
    optional = [custom_kc, custom_p, custom_root_depth, power_price,
                pump_power_kw, pump_productivity_m3h, greenhouse_et0]
    optional = [None if item is None else _non_negative_number(item, "field option") for item in optional]
    try:
        with closing(_connect()) as conn:
            database.begin_immediate(conn)
            existing = database.execute_query(
                conn,
                "SELECT id FROM fields WHERE user_id = ? AND field_key = ?", (owner, key)
            ).fetchone()
            if existing:
                field_id, created = int(existing[0]), False
                database.execute_query(conn, """
                    UPDATE fields SET crop_type=?, soil_type=?, irrigation_method=?, planting_date=?,
                        name=?, latitude=?, longitude=?, area_ha=?, field_type=?, is_saline=?,
                        stage_days=?, custom_kc=?, custom_p=?, custom_root_depth=?, power_price=?,
                        pump_power_kw=?, pump_productivity_m3h=?, greenhouse_et0=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=? AND user_id=?
                """, (values["crop"], values["soil"], values["irrigation"], values["planting"],
                      str(name).strip()[:80], values["latitude"], values["longitude"], values["area"],
                      field_type, int(bool(is_saline)), stages_json, *optional, field_id, owner))
            else:
                created = True
                cursor = database.execute_query(conn, """
                    INSERT INTO fields (
                        user_id, field_key, crop_type, soil_type, irrigation_method, planting_date,
                        accumulated_deficit, name, latitude, longitude, area_ha, field_type,
                        is_saline, stage_days, custom_kc, custom_p, custom_root_depth, power_price,
                        pump_power_kw, pump_productivity_m3h, greenhouse_et0, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                    RETURNING id
                """, (owner, key, values["crop"], values["soil"], values["irrigation"],
                      values["planting"], values["deficit"], str(name).strip()[:80],
                      values["latitude"], values["longitude"], values["area"], field_type,
                      int(bool(is_saline)), stages_json, *optional))
                field_id = int(cursor.fetchone()[0])
            conn.commit()
            return field_id, created
    except database.DatabaseError as exc:
        raise FieldStateError("Could not save managed field") from exc


def get_daily_balance(field_id: int, balance_date: str) -> dict[str, Any] | None:
    field_key = _positive_int(field_id, "field_id")
    try:
        date.fromisoformat(balance_date)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldDataError("balance_date must use YYYY-MM-DD") from exc
    try:
        with closing(_connect()) as conn:
            row = database.execute_query(
                conn,
                "SELECT * FROM field_daily_balances WHERE field_id=? AND balance_date=?",
                (field_key, balance_date),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["result"] = json.loads(result.pop("result_json"))
        return result
    except database.DatabaseError as exc:
        raise FieldStateError("Could not load daily balance") from exc


def save_daily_balance(field_id: int, *, user_id: int, balance_date: str,
                       timezone: str, result: dict[str, Any], deficit_before: float,
                       replace: bool = False) -> tuple[dict[str, Any], bool]:
    """Persist one calculation date and update the running deficit atomically."""
    field_key = _positive_int(field_id, "field_id")
    owner = _positive_int(user_id, "user_id")
    try:
        date.fromisoformat(balance_date)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldDataError("balance_date must use YYYY-MM-DD") from exc
    required = ("et0", "rain", "peff", "etc", "deficit", "status", "net_m3", "gross_m3")
    if not isinstance(result, dict) or any(key not in result for key in required):
        raise InvalidFieldDataError("daily result is incomplete")
    numeric = {key: _non_negative_number(result[key], key) for key in required if key != "status"}
    if result["status"] not in {"deferred", "irrigate", "critical"}:
        raise InvalidFieldDataError("daily status is invalid")
    before = _non_negative_number(deficit_before, "deficit_before")
    serialized = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    try:
        with closing(_connect()) as conn:
            database.begin_immediate(conn)
            owner_row = database.execute_query(
                conn,
                "SELECT id FROM fields WHERE id=? AND user_id=?", (field_key, owner)
            ).fetchone()
            if owner_row is None:
                raise FieldNotFoundError(f"Field {field_key} was not found")
            existing = database.execute_query(
                conn,
                "SELECT * FROM field_daily_balances WHERE field_id=? AND balance_date=?",
                (field_key, balance_date),
            ).fetchone()
            if existing is not None and not replace:
                conn.rollback()
                stored = dict(existing)
                stored["result"] = json.loads(stored.pop("result_json"))
                return stored, False
            params = (str(timezone), numeric["et0"], numeric["rain"], numeric["peff"],
                      numeric["etc"], before, numeric["deficit"], result["status"],
                      numeric["net_m3"], numeric["gross_m3"],
                      str(result.get("calculation_version", "fao56")), serialized)
            if existing is None:
                database.execute_query(conn, """
                    INSERT INTO field_daily_balances (
                        field_id,balance_date,timezone,et0,rain,effective_rain,etc,
                        deficit_before,deficit_after,status,net_m3,gross_m3,
                        calculation_version,result_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (field_key, balance_date, *params))
            else:
                database.execute_query(conn, """
                    UPDATE field_daily_balances SET timezone=?,et0=?,rain=?,effective_rain=?,etc=?,
                        deficit_before=?,deficit_after=?,status=?,net_m3=?,gross_m3=?,
                        calculation_version=?,result_json=?,created_at=CURRENT_TIMESTAMP
                    WHERE field_id=? AND balance_date=?
                """, (*params, field_key, balance_date))
            database.execute_query(
                conn,
                "UPDATE fields SET accumulated_deficit=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (numeric["deficit"], field_key),
            )
            conn.commit()
        stored = get_daily_balance(field_key, balance_date)
        return stored, True
    except FieldNotFoundError:
        raise
    except database.DatabaseError as exc:
        raise FieldStateError("Could not save daily balance") from exc


def list_daily_balances(field_id: int, *, user_id: int, limit: int = 31) -> list[dict[str, Any]]:
    field = get_field(field_id, user_id=user_id)
    safe_limit = min(_positive_int(limit, "limit"), 366)
    try:
        with closing(_connect()) as conn:
            rows = database.execute_query(conn, """
                SELECT * FROM field_daily_balances WHERE field_id=?
                ORDER BY balance_date DESC LIMIT ?
            """, (field["id"], safe_limit)).fetchall()
        return [dict(row) for row in rows]
    except database.DatabaseError as exc:
        raise FieldStateError("Could not list daily balances") from exc


def list_irrigation_events(field_id: int, *, user_id: int,
                           limit: int = 366) -> list[dict[str, Any]]:
    field = get_field(field_id, user_id=user_id)
    safe_limit = min(_positive_int(limit, "limit"), 1000)
    try:
        with closing(_connect()) as conn:
            rows = database.execute_query(conn, """
                SELECT * FROM irrigation_events WHERE field_id=?
                ORDER BY created_at DESC, id DESC LIMIT ?
            """, (field["id"], safe_limit)).fetchall()
        return [dict(row) for row in rows]
    except database.DatabaseError as exc:
        raise FieldStateError("Could not list irrigation events") from exc


def record_irrigation(field_id: int, *, user_id: int, applied_m3: float | None = None,
                      source: str = "telegram") -> dict[str, float]:
    """Record confirmed irrigation and reduce deficit by effective applied water."""
    field_key = _positive_int(field_id, "field_id")
    owner = _positive_int(user_id, "user_id")
    volume = None if applied_m3 is None else _non_negative_number(applied_m3, "applied_m3")
    try:
        from water_balance import METHODS
    except ImportError:
        from bot.water_balance import METHODS
    try:
        with closing(_connect()) as conn:
            database.begin_immediate(conn)
            row = database.execute_query(
                conn,
                "SELECT * FROM fields WHERE id=? AND user_id=?", (field_key, owner)
            ).fetchone()
            if row is None:
                raise FieldNotFoundError(f"Field {field_key} was not found")
            before = float(row["accumulated_deficit"])
            if volume is None:
                after = 0.0
            else:
                area = float(row["area_ha"] or 0)
                if area <= 0 or row["irrigation_method"] not in METHODS:
                    raise InvalidFieldDataError("field has no irrigation geometry")
                efficiency = METHODS[row["irrigation_method"]][1]
                effective_mm = volume * efficiency / (10 * area)
                after = max(0.0, before - effective_mm)
            database.execute_query(
                conn,
                "UPDATE fields SET accumulated_deficit=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (after, field_key),
            )
            database.execute_query(conn, """
                INSERT INTO irrigation_events
                    (field_id,user_id,applied_m3,deficit_before,deficit_after,source)
                VALUES (?,?,?,?,?,?)
            """, (field_key, owner, volume, before, after, str(source)[:32]))
            conn.commit()
            return {"deficit_before": before, "deficit_after": after,
                    "applied_m3": volume}
    except (FieldNotFoundError, InvalidFieldDataError):
        raise
    except database.DatabaseError as exc:
        raise FieldStateError("Could not record irrigation") from exc
