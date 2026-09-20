"""Application service for persistent, explainable daily field balances."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

# Ensure 'field_service' and 'bot.field_service' refer to the exact same module in sys.modules
if "field_service" in sys.modules and __name__ == "bot.field_service":
    sys.modules["bot.field_service"] = sys.modules["field_service"]
elif "bot.field_service" in sys.modules and __name__ == "field_service":
    sys.modules["field_service"] = sys.modules["bot.field_service"]
elif __name__ == "bot.field_service":
    sys.modules["field_service"] = sys.modules[__name__]
elif __name__ == "field_service":
    sys.modules["bot.field_service"] = sys.modules[__name__]

try:
    from balance_weather import fetch_daily_weather
    from field_state import (
        get_daily_balance,
        get_day_of_growth,
        get_field,
        make_field_key,
        save_daily_balance,
        upsert_managed_field,
    )
    from water_balance import CALCULATION_VERSION, calculate_balance, parse_field
except ImportError:
    from bot.balance_weather import fetch_daily_weather
    from bot.field_state import (
        get_daily_balance,
        get_day_of_growth,
        get_field,
        make_field_key,
        save_daily_balance,
        upsert_managed_field,
    )
    from bot.water_balance import CALCULATION_VERSION, calculate_balance, parse_field


def _result_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(result)
    snapshot["calculation_version"] = CALCULATION_VERSION
    return snapshot


async def persist_webapp_field(user_id: int, data: dict[str, Any], field, latitude: float,
                               longitude: float, result: dict[str, Any],
                               weather: dict[str, Any]) -> int | None:
    """Save a WebApp calculation as the initial/configuration snapshot of a field."""
    if field.crop == "rice":
        return None
    planting = date.fromisoformat(weather["date"]) - timedelta(days=field.day)
    identity = make_field_key(latitude, longitude, field.area_ha, field.crop)
    field_id, _ = await asyncio.to_thread(
        upsert_managed_field,
        user_id=user_id, field_key=identity, crop=field.crop, soil=field.soil,
        irrigation=field.method, planting_date=planting,
        initial_deficit=field.yesterday, latitude=latitude, longitude=longitude,
        area_ha=field.area_ha, field_type=field.field_type, is_saline=field.saline,
        stage_days=field.stages, custom_kc=field.kc if field.crop == "other" else None,
        custom_p=field.p if field.crop == "other" else None,
        custom_root_depth=field.zr if field.crop == "other" else None,
        power_price=field.power_price, pump_power_kw=field.pump_power_kw,
        pump_productivity_m3h=field.pump_productivity_m3h,
        greenhouse_et0=field.greenhouse_et0,
    )
    await asyncio.to_thread(
        save_daily_balance, field_id, user_id=user_id, balance_date=weather["date"],
        timezone=weather["timezone"], result=_result_snapshot(result),
        deficit_before=field.yesterday, replace=True,
    )
    return field_id


def field_input_from_record(record: dict[str, Any], *, on_date: date | None = None):
    """Rebuild validated calculation input from a stored field configuration."""
    current_date = on_date or date.today()
    day = get_day_of_growth(int(record["id"]), today=current_date)
    payload: dict[str, Any] = {
        "balance_version": 2,
        "crop": record["crop_type"],
        "soil_type": record["soil_type"],
        "area": record["area_ha"],
        "area_unit": "hectare",
        "irrigation_type": record["irrigation_method"],
        "day_of_growth": day,
        "moisture_condition": "recent",
        "field_type": record.get("field_type") or "open",
        "is_saline": "yes" if record.get("is_saline") else "no",
        "power_price": record.get("power_price"),
        "pump_power_kw": record.get("pump_power_kw"),
        "pump_productivity_m3h": record.get("pump_productivity_m3h"),
        "greenhouse_et0": record.get("greenhouse_et0"),
    }
    if record.get("stage_days"):
        payload["stage_days"] = json.loads(record["stage_days"])
    if record["crop_type"] == "other":
        payload.update(custom_kc=record.get("custom_kc"), custom_p=record.get("custom_p"),
                       custom_root_depth=record.get("custom_root_depth"))
    parsed = parse_field(payload)
    return replace(parsed, yesterday=float(record["accumulated_deficit"]),
                   moisture_condition="stored")


async def calculate_saved_field(field_id: int, user_id: int):
    """Calculate a saved field at most once for the provider's local date."""
    record = await asyncio.to_thread(get_field, field_id, user_id=user_id)
    weather = await fetch_daily_weather(record["latitude"], record["longitude"])
    balance_date = date.fromisoformat(weather["date"])
    stored = await asyncio.to_thread(get_daily_balance, field_id, weather["date"])
    if stored is not None:
        field = await asyncio.to_thread(field_input_from_record, record, on_date=balance_date)
        field = replace(field, yesterday=float(stored["deficit_before"]))
        return field, stored["result"], {
            "date": stored["balance_date"], "timezone": stored["timezone"],
            "et0": stored["et0"], "rain": stored["rain"],
        }, False

    field = await asyncio.to_thread(field_input_from_record, record, on_date=balance_date)
    result = calculate_balance(field, weather["et0"], weather["rain"])
    saved, created = await asyncio.to_thread(
        save_daily_balance, field_id, user_id=user_id, balance_date=weather["date"],
        timezone=weather["timezone"], result=_result_snapshot(result),
        deficit_before=field.yesterday,
    )
    return field, saved["result"], weather, created
