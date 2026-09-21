"""
Сервисный слой управления полями (Application Service).
Изолирует базу данных и расчеты FAO-56 от слоя представления (Telegram-хэндлеров).
Возвращает строго типизированные Pydantic v2 модели.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple
from contextlib import closing

try:
    import db as database
    from balance_weather import fetch_daily_weather
    from field_service import calculate_saved_field
    from field_state import (
        FieldNotFoundError,
        FieldStateError,
        get_field,
        list_daily_balances,
        list_irrigation_events,
        list_user_fields,
        make_field_key,
        record_irrigation,
        upsert_managed_field,
    )
except ImportError:
    from bot import db as database
    from bot.balance_weather import fetch_daily_weather
    from bot.field_service import calculate_saved_field
    from bot.field_state import (
        FieldNotFoundError,
        FieldStateError,
        get_field,
        list_daily_balances,
        list_irrigation_events,
        list_user_fields,
        make_field_key,
        record_irrigation,
        upsert_managed_field,
    )

from bot.schemas.field import (
    CropType,
    FieldCreate,
    FieldResponse,
    IrrigationMethod,
    IrrigationStatus,
    SoilType,
    UnifiedJournalRecord,
    quantize_2dp,
)
from bot.services.geo_service import (
    DEFAULT_FALLBACK_LAT,
    DEFAULT_FALLBACK_LON,
    resolve_timezone_by_coords,
)


class FieldService:
    """Сервис бизнес-логики для полей, расчетов и истории."""

    @classmethod
    def _map_record_to_dto(cls, record: dict[str, Any]) -> FieldResponse:
        """Преобразует словарь из БД в валидированную Pydantic-модель."""
        raw_deficit = float(record.get("accumulated_deficit") or 0.0)
        
        # Определение статуса полива
        if record.get("crop_type") == "rice":
            status = IrrigationStatus.RICE
        elif raw_deficit >= 30.0:
            status = IrrigationStatus.CRITICAL
        elif raw_deficit >= 15.0:
            status = IrrigationStatus.IRRIGATE
        else:
            status = IrrigationStatus.NORMAL

        area = float(record.get("area_ha") or 1.0)
        # Примерный рекомендуемый объем полива с учетом КПД:
        # V = Deficit(мм) * 10 * Area(га) / Efficiency
        eff_map = {"drip": 0.90, "subsurface": 0.90, "sprinkler": 0.75, "pivot": 0.75, "furrow": 0.50}
        eff = eff_map.get(record.get("irrigation_method") or "drip", 0.75)
        rec_m3 = (raw_deficit * 10.0 * area / eff) if status != IrrigationStatus.NORMAL else 0.0

        lat_raw = record.get("latitude")
        lon_raw = record.get("longitude")
        lat_f = float(lat_raw) if lat_raw is not None else DEFAULT_FALLBACK_LAT
        lon_f = float(lon_raw) if lon_raw is not None else DEFAULT_FALLBACK_LON

        stored_tz = str(record.get("timezone") or "").strip()
        field_tz = stored_tz if stored_tz and stored_tz != "None" else resolve_timezone_by_coords(lat_f, lon_f)

        return FieldResponse(
            id=int(record["id"]),
            user_id=int(record["user_id"]),
            name=record.get("name") or f"Поле #{record['id']}",
            crop_type=CropType(record.get("crop_type") or "tomato"),
            area_ha=Decimal(str(round(area, 2))),
            irrigation_method=IrrigationMethod(record.get("irrigation_method") or "drip"),
            soil_type=SoilType(record.get("soil_type") or "loam"),
            latitude=Decimal(str(round(lat_f, 4))),
            longitude=Decimal(str(round(lon_f, 4))),
            timezone=field_tz,
            planting_date=date.fromisoformat(record.get("planting_date") or date.today().isoformat()),
            accumulated_deficit_mm=Decimal(str(round(raw_deficit, 2))),
            current_status=status,
            recommended_volume_m3=Decimal(str(round(rec_m3, 2))),
        )

    @classmethod
    async def get_user_fields(cls, user_id: int) -> List[FieldResponse]:
        """Возвращает список всех полей пользователя в виде Pydantic-моделей."""
        records = await asyncio.to_thread(list_user_fields, user_id)
        valid = [r for r in records if r.get("id")]
        return [cls._map_record_to_dto(r) for r in valid]

    @classmethod
    async def get_field_by_id(cls, field_id: int, user_id: int) -> Optional[FieldResponse]:
        """Загружает поле по идентификатору с контролем прав доступа."""
        try:
            record = await asyncio.to_thread(get_field, field_id, user_id=user_id)
            return cls._map_record_to_dto(record)
        except (FieldNotFoundError, FieldStateError, ValueError):
            return None

    @classmethod
    async def create_field(cls, user_id: int, form: FieldCreate) -> int:
        """Создает новое поле со строгой привязкой к переданным GPS-координатам."""
        lat = float(form.latitude) if form.latitude else DEFAULT_FALLBACK_LAT
        lon = float(form.longitude) if form.longitude else DEFAULT_FALLBACK_LON
        area = float(form.area_ha)
        
        identity = make_field_key(lat, lon, area, form.crop_type.value)
        
        field_id, _ = await asyncio.to_thread(
            upsert_managed_field,
            user_id=user_id,
            field_key=identity,
            crop=form.crop_type.value,
            soil=form.soil_type.value,
            irrigation=form.irrigation_method.value,
            planting_date=form.planting_date,
            initial_deficit=0.0,
            latitude=lat,
            longitude=lon,
            area_ha=area,
            field_type="open",
            is_saline=False,
        )
        
        # Обновление пользовательского имени в базе данных
        if form.name:
            def _update_name():
                with closing(database.get_connection()) as conn:
                    database.execute_query(
                        conn, "UPDATE fields SET name = ? WHERE id = ?", (form.name, field_id)
                    )
                    conn.commit()
            await asyncio.to_thread(_update_name)

        return field_id

    @classmethod
    async def delete_field(cls, field_id: int, user_id: int) -> bool:
        """Удаляет поле пользователя и связанные с ним логи."""
        def _delete():
            with closing(database.get_connection()) as conn:
                cur = database.execute_query(
                    conn, "DELETE FROM fields WHERE id = ? AND user_id = ?", (field_id, user_id)
                )
                conn.commit()
                return cur.rowcount > 0
        return await asyncio.to_thread(_delete)

    @classmethod
    async def record_irrigation_fact(
        cls, field_id: int, user_id: int, applied_m3: Optional[float] = None
    ) -> FieldResponse:
        """Фиксирует факт проведения полива и сбрасывает дефицит влаги."""
        await asyncio.to_thread(
            record_irrigation,
            field_id=field_id,
            user_id=user_id,
            applied_m3=round(applied_m3, 2) if applied_m3 is not None else None,
            source="telegram_bot",
        )
        updated = await cls.get_field_by_id(field_id, user_id)
        if not updated:
            raise FieldNotFoundError(f"Field {field_id} not found")
        return updated

    @classmethod
    async def update_balance_today(
        cls, field_id: int, user_id: int
    ) -> Tuple[FieldResponse, dict[str, Any]]:
        """Запрашивает свежую погоду и производит суточный расчет по модели FAO-56."""
        field, result, weather, created = await calculate_saved_field(field_id, user_id)
        field_dto = await cls.get_field_by_id(field_id, user_id)
        if not field_dto:
            raise FieldNotFoundError(f"Field {field_id} not found")
        return field_dto, result

    @classmethod
    async def get_journal_records(cls, field_id: int, user_id: int) -> List[UnifiedJournalRecord]:
        """Формирует нормализованный список записей аудита без пустых колонок."""
        field = await cls.get_field_by_id(field_id, user_id)
        field_tz = field.timezone if field and field.timezone else "UTC"

        rows = await asyncio.to_thread(
            list_daily_balances, field_id, user_id=user_id, limit=366
        )
        events = await asyncio.to_thread(
            list_irrigation_events, field_id, user_id=user_id, limit=366
        )
        
        records: List[UnifiedJournalRecord] = []

        for row in rows:
            ts = datetime.fromisoformat(row["created_at"]) if "T" in str(row["created_at"]) else datetime.strptime(str(row["created_at"])[:19], "%Y-%m-%d %H:%M:%S")
            row_tz = str(row.get("timezone") or field_tz)

            records.append(
                UnifiedJournalRecord(
                    timestamp=ts,
                    record_type="balance",
                    date_str=str(row["balance_date"]),
                    timezone=row_tz,
                    et0_mm=quantize_2dp(row["et0"]),
                    rain_mm=quantize_2dp(row["rain"]),
                    effective_rain_mm=quantize_2dp(row["effective_rain"]),
                    etc_mm=quantize_2dp(row["etc"]),
                    deficit_before_mm=quantize_2dp(row["deficit_before"]) or Decimal("0.00"),
                    deficit_after_mm=quantize_2dp(row["deficit_after"]) or Decimal("0.00"),
                    status=str(row["status"]),
                    net_m3=quantize_2dp(row["net_m3"]),
                    gross_m3=quantize_2dp(row["gross_m3"]),
                    applied_m3=None,
                    source=f"Open-Meteo FAO-56 ({row.get('calculation_version', 'fao56')})",
                )
            )

        for ev in events:
            raw_ts = str(ev["created_at"])
            try:
                ts = datetime.strptime(raw_ts[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts = datetime.now()
            
            records.append(
                UnifiedJournalRecord(
                    timestamp=ts,
                    record_type="irrigation",
                    date_str=ts.strftime("%Y-%m-%d"),
                    timezone=field_tz,
                    et0_mm=None,
                    rain_mm=None,
                    effective_rain_mm=None,
                    etc_mm=None,
                    deficit_before_mm=quantize_2dp(ev["deficit_before"]) or Decimal("0.00"),
                    deficit_after_mm=quantize_2dp(ev["deficit_after"]) or Decimal("0.00"),
                    status="watered",
                    net_m3=None,
                    gross_m3=None,
                    applied_m3=quantize_2dp(ev["applied_m3"]),
                    source=str(ev.get("source") or "Telegram Bot"),
                )
            )

        # Сортировка по времени события
        records.sort(key=lambda r: r.timestamp)
        return records
