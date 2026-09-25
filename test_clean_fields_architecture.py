"""
Тесты для архитектуры Strict GPS-first:
1. Pydantic v2 схемы и квантование до 2 знаков.
2. Строгий расчет инсоляции FAO-56 через радианы широты (Ra, declination, sunset hour angle).
3. Динамическое определение IANA-таймзон через timezonefinder (без единого if-else).
4. Асинхронный обратный геокодинг и безопасный fallback Поле (lat, lon) без выдуманных городов.
5. Экспорт чистого CSV с честными координатами, локацией и динамической таймзоной в шапке.
6. Жизненный цикл CRUD сервисного слоя полей.
"""
from __future__ import annotations

import math
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

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
    DEFAULT_FALLBACK_LAT,
    DEFAULT_FALLBACK_LON,
    calculate_extraterrestrial_radiation_ra,
    calculate_solar_declination,
    calculate_sunset_hour_angle,
    get_field_location_name,
    resolve_field_coordinates,
    resolve_timezone_by_coords,
    reverse_geocode,
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
        self.assertEqual(field.area_ha, Decimal("15.556"))
        self.assertEqual(field.accumulated_deficit_mm, Decimal("18.40"))
        self.assertEqual(field.recommended_volume_m3, Decimal("316.89"))

    def test_strict_gps_solar_radiation_fao56_radians(self):
        """Проверка расчета формул солнечной инсоляции FAO-56 через радианы широты."""
        # 1. Солнечное склонение delta для летнего солнцестояния (J = 172)
        delta_summer = calculate_solar_declination(172)
        self.assertAlmostEqual(delta_summer, 0.409 * math.sin(2.0 * math.pi * 172 / 365.0 - 1.39), places=4)

        # 2. Часовой угол заката omega_s принимает строго радианы
        phi_atyrau = math.radians(47.1167)
        omega_s = calculate_sunset_hour_angle(phi_atyrau, delta_summer)
        self.assertGreater(omega_s, 1.57)  # Летом день длиннее ночи (omega_s > pi/2)

        # 3. Суточная внеземная радиация Ra для произвольной точки (Атырау)
        ra_summer = calculate_extraterrestrial_radiation_ra(47.1167, date(2026, 6, 21))
        self.assertGreater(ra_summer, 40.0)

        # Зимой радиация существенно ниже
        ra_winter = calculate_extraterrestrial_radiation_ra(47.1167, date(2026, 12, 21))
        self.assertLess(ra_winter, 15.0)

    def test_dynamic_timezonefinder_resolution_without_heuristics(self):
        """Проверка динамического разрешения IANA-таймзон по полигонам GPS без единого if."""
        # Атырау
        self.assertEqual(resolve_timezone_by_coords(47.1167, 51.8833), "Asia/Atyrau")
        # Алматы
        self.assertEqual(resolve_timezone_by_coords(43.24, 76.91), "Asia/Almaty")
        # Уральск
        self.assertEqual(resolve_timezone_by_coords(51.2, 51.3), "Asia/Oral")
        # Лондон
        self.assertEqual(resolve_timezone_by_coords(51.5074, -0.1278), "Europe/London")

        # Проверка резолвера координат поля
        lat, lon, tz = resolve_field_coordinates(43.24, 76.91)
        self.assertEqual(lat, 43.24)
        self.assertEqual(lon, 76.91)
        self.assertEqual(tz, "Asia/Almaty")

    async def test_reverse_geocoding_and_honest_fallback(self):
        """Проверка честного обратного геокодинга и безопасного fallback Поле (lat, lon)."""
        # 1. При сетевом сбое геокодинг обязан вернуть координаты, а не выдуманный город
        with patch("aiohttp.ClientSession.get", side_effect=Exception("Network unreachable")):
            location_offline = await reverse_geocode(47.50, 52.10)
            self.assertEqual(location_offline, "Поле (47.5000, 52.1000)")
            self.assertNotIn("Атырау", location_offline)

        # 2. Если точка в океане (нет населенного пункта) — честный fallback с координатами
        label_ocean = await get_field_location_name(0.0, 0.0)
        self.assertEqual(label_ocean, "Поле (0.0000, 0.0000)")

        # 3. При наличии населенного пункта возвращается реальное название (не хардкод)
        label_real = await get_field_location_name(47.1167, 51.8833)
        self.assertIn("Атырау", label_real)

    def test_export_service_generates_clean_csv_with_dynamic_gps_headers(self):
        """Проверка чистого CSV с точными GPS-координатами, локацией и динамической таймзоной."""
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
                applied_m3=Decimal("316.89"),
                source="Telegram Bot",
            ),
        ]

        doc = FieldExportService.get_telegram_document(
            field_id=1,
            field_name="Участок №1",
            records=records,
            latitude=47.1167,
            longitude=51.8833,
            timezone_str="Asia/Atyrau",
            locality="село Бейбарыс",
        )
        csv_text = doc.data.decode("utf-8-sig")

        # Проверка метаданных шапки
        self.assertIn("# ОТЧЕТ ПОЛЯ:;Участок №1", csv_text)
        self.assertIn("# КООРДИНАТЫ (GPS):;47.1167° N, 51.8833° E", csv_text)
        self.assertIn("# ЛОКАЦИЯ:;село Бейбарыс", csv_text)
        self.assertIn("# ТАЙМЗОНА:;Asia/Atyrau", csv_text)

        # Отсутствие дыр вида ',,,,,,,,'
        self.assertNotIn(",,,,,,,,", csv_text)
        self.assertNotIn(";;;;;;;;", csv_text)

    async def test_field_service_crud_lifecycle(self):
        """Полный цикл CRUD в сервисном слое со строгими GPS координатами."""
        form = FieldCreate(
            name="Участок возле реки",
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
        self.assertEqual(fields[0].name, "Участок возле реки")
        self.assertEqual(fields[0].area_ha, Decimal("20.00"))
        self.assertEqual(fields[0].latitude, Decimal("47.1167"))
        self.assertEqual(fields[0].longitude, Decimal("51.8833"))
        self.assertEqual(fields[0].timezone, "Asia/Atyrau")

        # 3. Record Irrigation
        updated = await FieldService.record_irrigation_fact(field_id, user_id=77, applied_m3=200.0)
        self.assertEqual(updated.accumulated_deficit_mm, Decimal("0.00"))

        # 4. Delete
        deleted = await FieldService.delete_field(field_id, user_id=77)
        self.assertTrue(deleted)
        empty_list = await FieldService.get_user_fields(user_id=77)
        self.assertEqual(len(empty_list), 0)

    async def test_weather_parser_strict_gps_no_hardcoded_overrides(self):
        """Проверка честного парсера погоды без искусственной подмены таймзон."""
        from bot.balance_weather import parse_daily_weather
        from datetime import timezone, timedelta

        # 1. Если API вернуло Asia/Oral (например, координаты Уральска) — парсер честно отдает Asia/Oral
        payload_oral = {
            "timezone": "Asia/Oral",
            "utc_offset_seconds": 18000,
            "daily_units": {"et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
            "daily": {
                "time": [datetime.now(timezone(timedelta(seconds=18000))).date().isoformat()],
                "et0_fao_evapotranspiration": [4.2],
                "precipitation_sum": [0.0],
            },
        }
        parsed_oral = parse_daily_weather(payload_oral)
        self.assertEqual(parsed_oral["timezone"], "Asia/Oral")
        self.assertEqual(parsed_oral["et0"], 4.2)

        # 2. Если API вернуло Asia/Atyrau (координаты Атырау) — парсер честно отдает Asia/Atyrau
        payload_atyrau = {
            "timezone": "Asia/Atyrau",
            "utc_offset_seconds": 18000,
            "daily_units": {"et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
            "daily": {
                "time": [datetime.now(timezone(timedelta(seconds=18000))).date().isoformat()],
                "et0_fao_evapotranspiration": [5.1],
                "precipitation_sum": [0.0],
            },
        }
        parsed_atyrau = parse_daily_weather(payload_atyrau)
        self.assertEqual(parsed_atyrau["timezone"], "Asia/Atyrau")
        self.assertEqual(parsed_atyrau["et0"], 5.1)


if __name__ == "__main__":
    unittest.main()
