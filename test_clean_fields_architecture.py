"""
Тесты для чистой архитектуры полей:
1. Pydantic v2 схемы и квантование до 2 знаков.
2. Геопривязка и солнечная радиация FAO-56 для Атырау.
3. Экспорт чистого CSV без мусорных колонок и IEEE-754.
4. CRUD сервисного слоя.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from bot import db
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
from bot.services.export_service import FieldExportService
from bot.services.field_manager import FieldService
from bot.services.geo_service import (
    ATYRAU_DEFAULT_LAT,
    ATYRAU_DEFAULT_LON,
    ATYRAU_TIMEZONE,
    calculate_extraterrestrial_radiation_ra,
    resolve_field_coordinates,
)


class CleanFieldsArchitectureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = db.DB_PATH
        db.DB_PATH = str(Path(self.temp_dir.name) / "test_clean.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_pydantic_rounding_quantize_2dp(self):
        """Проверка устранения артефактов IEEE-754: строго 2 знака."""
        val1 = 32.29687500000001
        val2 = 3763.5416666666674
        self.assertEqual(quantize_2dp(val1), Decimal("32.30"))
        self.assertEqual(quantize_2dp(val2), Decimal("3763.54"))

        field = FieldResponse(
            id=1,
            user_id=100,
            name="Тестовое поле",
            crop_type=CropType.TOMATO,
            area_ha=Decimal("15.556"),
            irrigation_method=IrrigationMethod.DRIP,
            soil_type=SoilType.LOAM,
            latitude=Decimal("47.1167"),
            longitude=Decimal("51.8833"),
            timezone="Asia/Atyrau",
            planting_date=date(2026, 5, 1),
            accumulated_deficit_mm=Decimal("18.4012"),
            current_status=IrrigationStatus.IRRIGATE,
            recommended_volume_m3=Decimal("316.888"),
        )
        self.assertEqual(field.area_ha, Decimal("15.56"))
        self.assertEqual(field.accumulated_deficit_mm, Decimal("18.40"))
        self.assertEqual(field.recommended_volume_m3, Decimal("316.89"))

    def test_atyrau_geo_and_solar_radiation(self):
        """Проверка дефолтов Атырау и расчета Ra по FAO-56."""
        lat, lon, tz = resolve_field_coordinates(None, None)
        self.assertEqual(lat, ATYRAU_DEFAULT_LAT)
        self.assertEqual(lon, ATYRAU_DEFAULT_LON)
        self.assertEqual(tz, ATYRAU_TIMEZONE)

        # Расчет Ra для Атырау (47.1167° N) в день летнего солнцестояния (21 июня)
        ra_summer = calculate_extraterrestrial_radiation_ra(47.1167, date(2026, 6, 21))
        self.assertGreater(ra_summer, 40.0)  # Летом в Атырау высокая инсоляция

        # Зимой (21 декабря) инсоляция значительно ниже
        ra_winter = calculate_extraterrestrial_radiation_ra(47.1167, date(2026, 12, 21))
        self.assertLess(ra_winter, 15.0)

    def test_export_service_generates_clean_csv_without_holes(self):
        """Проверка чистого CSV без пустых колонок и с UTF-8-BOM."""
        records = [
            UnifiedJournalRecord(
                timestamp=datetime(2026, 9, 21, 8, 0, 0),
                record_type="balance",
                date_str="2026-09-21",
                timezone="Asia/Atyrau",
                et0_mm=Decimal("4.50"),
                rain_mm=Decimal("0.00"),
                effective_rain_mm=Decimal("0.00"),
                etc_mm=Decimal("5.18"),
                deficit_before_mm=Decimal("13.22"),
                deficit_after_mm=Decimal("18.40"),
                status="irrigate",
                net_m3=Decimal("285.20"),
                gross_m3=Decimal("316.89"),
                applied_m3=None,
                source="Open-Meteo FAO-56",
            ),
            UnifiedJournalRecord(
                timestamp=datetime(2026, 9, 21, 10, 0, 0),
                record_type="irrigation",
                date_str="2026-09-21",
                timezone="Asia/Atyrau",
                et0_mm=None,
                rain_mm=None,
                effective_rain_mm=None,
                etc_mm=None,
                deficit_before_mm=Decimal("18.40"),
                deficit_after_mm=Decimal("0.00"),
                status="watered",
                net_m3=None,
                gross_m3=None,
                applied_m3=Decimal("320.00"),
                source="Telegram Bot",
            ),
        ]

        csv_stream = FieldExportService.generate_journal_csv("Поле 1", records)
        raw_bytes = csv_stream.getvalue()
        
        # Проверка сигнатуры UTF-8-BOM
        self.assertTrue(raw_bytes.startswith(b"\xef\xbb\xbf"))
        
        content = raw_bytes.decode("utf-8-sig")
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

        # Проверка отсутствия дыр и последовательных пустых запятых/точек с запятой (;;;;;)
        for line in lines[4:]:  # после метаданных
            self.assertNotIn(";;;;;;;;", line)

        doc = FieldExportService.get_telegram_document(1, "Северный сектор", records)
        self.assertTrue(doc.filename.startswith("su_tech_"))
        self.assertTrue(doc.filename.endswith(".csv"))

    async def test_field_service_crud_lifecycle(self):
        """Полный цикл CRUD в сервисном слое."""
        form = FieldCreate(
            name="Участок реки Урал",
            crop_type=CropType.TOMATO,
            area_ha=Decimal("20.00"),
            irrigation_method=IrrigationMethod.DRIP,
            soil_type=SoilType.LOAM,
            latitude=Decimal("47.1167"),
            longitude=Decimal("51.8833"),
            timezone="Asia/Atyrau",
        )
        
        # 1. Create
        field_id = await FieldService.create_field(user_id=77, form=form)
        self.assertIsInstance(field_id, int)

        # 2. Read / List
        fields = await FieldService.get_user_fields(user_id=77)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].name, "Участок реки Урал")
        self.assertEqual(fields[0].area_ha, Decimal("20.00"))
        self.assertEqual(fields[0].timezone, "Asia/Atyrau")

        # 3. Record Irrigation
        updated = await FieldService.record_irrigation_fact(field_id, user_id=77, applied_m3=200.0)
        self.assertEqual(updated.accumulated_deficit_mm, Decimal("0.00"))

        # 4. Delete
        deleted = await FieldService.delete_field(field_id, user_id=77)
        self.assertTrue(deleted)
        empty_list = await FieldService.get_user_fields(user_id=77)
        self.assertEqual(len(empty_list), 0)

    async def test_oral_timezone_is_strictly_intercepted_and_replaced_with_atyrau(self):
        """Проверка полного искоренения Asia/Oral на всех уровнях: парсер, сервис, БД и CSV."""
        from bot.balance_weather import parse_daily_weather
        from datetime import timezone, timedelta

        # 1. Проверка парсера погоды при получении Asia/Oral от внешнего API
        payload = {
            "timezone": "Asia/Oral",
            "utc_offset_seconds": 18000,
            "daily_units": {"et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
            "daily": {
                "time": [datetime.now(timezone(timedelta(seconds=18000))).date().isoformat()],
                "et0_fao_evapotranspiration": [4.5],
                "precipitation_sum": [0.0],
            },
        }
        parsed = parse_daily_weather(payload)
        self.assertEqual(parsed["timezone"], "Asia/Atyrau")

        # 2. Проверка миграции и чтения поля из БД с грязным 'Asia/Oral'
        with db.get_connection() as conn:
            cur = db.execute_query(
                conn,
                """
                INSERT INTO fields (user_id, crop_type, soil_type, irrigation_method, planting_date, latitude, longitude)
                VALUES (88, 'wheat', 'loam', 'drip', '2026-05-01', 51.23, 51.37)
                RETURNING id
                """
            )
            field_id = cur.fetchone()[0]
            # Вставляем суточный баланс со старым значением Asia/Oral
            db.execute_query(
                conn,
                """
                INSERT INTO field_daily_balances (
                    field_id, balance_date, timezone, et0, rain, effective_rain, etc,
                    deficit_before, deficit_after, status, net_m3, gross_m3, calculation_version, result_json
                ) VALUES (?, '2026-05-02', 'Asia/Oral', 4.5, 0, 0, 5.0, 10.0, 15.0, 'deferred', 150, 166.6, 'v4', '{}')
                """,
                (field_id,)
            )
            conn.commit()

        # 3. Вызываем автофикс миграции
        from bot.migrate_atyrau_fix import run_atyrau_migration
        run_atyrau_migration()

        # 4. Проверяем, что в БД координаты Уральска заменены на Атырау, а таймзона — на Asia/Atyrau
        field_dto = await FieldService.get_field_by_id(field_id, user_id=88)
        self.assertIsNotNone(field_dto)
        self.assertEqual(field_dto.timezone, "Asia/Atyrau")
        self.assertEqual(field_dto.latitude, Decimal("47.1167"))
        self.assertEqual(field_dto.longitude, Decimal("51.8833"))

        # 5. Проверяем журнал и итоговый CSV-документ
        journal = await FieldService.get_journal_records(field_id, user_id=88)
        self.assertEqual(journal[0].timezone, "Asia/Atyrau")
        
        doc = FieldExportService.get_telegram_document(field_id, field_dto.name, journal)
        csv_text = doc.data.decode("utf-8-sig")
        self.assertNotIn("Asia/Oral", csv_text)
        self.assertIn("Asia/Atyrau", csv_text)


if __name__ == "__main__":
    unittest.main()
