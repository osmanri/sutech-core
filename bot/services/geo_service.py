"""
Геодезический и астрономический сервис водного баланса FAO-56.
Строгая архитектура Strict GPS-first:
1. Координаты (latitude, longitude) — единственный источник правды.
2. Формулы инсоляции FAO-56 (Ra, declination, sunset hour angle) строго принимают широту в радианах.
3. Определение IANA-таймзоны динамически через библиотеку timezonefinder без эвристик.
4. Честный асинхронный обратный геокодинг через OpenStreetMap Nominatim с fallback Поле (lat, lon).
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import date
from typing import Dict, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

# Дефолтные координаты для обратной совместимости при отсутствии GPS
DEFAULT_FALLBACK_LAT = 47.1167
DEFAULT_FALLBACK_LON = 51.8833
ATYRAU_DEFAULT_LAT = 47.1167
ATYRAU_DEFAULT_LON = 51.8833
ATYRAU_TIMEZONE = "Asia/Atyrau"

# In-memory кэш для обратного геокодинга (lat_3dp, lon_3dp) -> location_name
_GEOCODE_CACHE: Dict[Tuple[float, float, str], str] = {}
_GEOCODE_LOCK = asyncio.Lock()


def calculate_solar_declination(day_of_year: int) -> float:
    """
    Солнечное склонение delta (уравнение 24 FAO-56) в радианах.
    
    :param day_of_year: Порядковый номер дня в году J (1 .. 365/366)
    :return: Склонение delta в радианах.
    """
    return 0.409 * math.sin((2.0 * math.pi * day_of_year / 365.0) - 1.39)


def calculate_sunset_hour_angle(latitude_rad: float, delta_rad: float) -> float:
    """
    Часовой угол захода солнца omega_s (уравнение 25 FAO-56) в радианах.
    Принимает широту ИСКЛЮЧИТЕЛЬНО в радианах.
    
    :param latitude_rad: Географическая широта phi в радианах (-pi/2 .. +pi/2)
    :param delta_rad: Солнечное склонение delta в радианах
    :return: Угол заката omega_s в радианах [0 .. pi]
    """
    tan_val = -math.tan(latitude_rad) * math.tan(delta_rad)
    if tan_val <= -1.0:
        return math.pi  # Полярный день
    elif tan_val >= 1.0:
        return 0.0      # Полярная ночь
    return math.acos(tan_val)


def calculate_extraterrestrial_radiation_ra(latitude: float, calc_date: date) -> float:
    """
    Вычисление суточной внеземной радиации Ra (МДж / (м² · день)) по стандарту FAO-56 (уравнения 21–28).
    
    :param latitude: Точная географическая широта поля в градусах (-90 .. +90)
    :param calc_date: Дата расчета
    :return: Значение Ra, округленное до 2 знаков после запятой.
    """
    # 1. Порядковый номер дня в году J (1 .. 365/366)
    j = calc_date.timetuple().tm_yday
    
    # 2. Географическая широта в радианах phi
    phi = math.radians(latitude)
    
    # 3. Обратное относительное расстояние Земля-Солнце dr (уравнение 23 FAO-56)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * j / 365.0)
    
    # 4. Солнечное склонение delta (уравнение 24 FAO-56)
    delta = calculate_solar_declination(j)
    
    # 5. Угол заката солнца omega_s (уравнение 25 FAO-56) строго через радианы широты phi
    omega_s = calculate_sunset_hour_angle(phi, delta)
    
    # 6. Внеземная радиация Ra (уравнение 21 FAO-56)
    # Солнечная постоянная G_sc = 0.0820 МДж / (м² · мин)
    g_sc = 0.0820
    ra = (24.0 * 60.0 / math.pi) * g_sc * dr * (
        omega_s * math.sin(phi) * math.sin(delta) +
        math.cos(phi) * math.cos(delta) * math.sin(omega_s)
    )
    return round(max(0.0, ra), 2)


def resolve_timezone_by_coords(lat: float, lon: float) -> str:
    """
    Честное определение IANA-таймзоны строго по GPS-координатам без if-else и эвристик.
    Использует геодезические полигоны библиотеки timezonefinder.
    
    :param lat: Географическая широта
    :param lon: Географическая долгота
    :return: Имя таймзоны IANA (например 'Asia/Atyrau', 'Asia/Almaty', 'Europe/London')
    """
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=float(lat), lng=float(lon))
        if tz:
            return tz
    except Exception as exc:
        logger.debug("TimezoneFinder resolution error for %s, %s: %s", lat, lon, exc)
    return "UTC"


def resolve_field_coordinates(lat: float | None, lon: float | None) -> Tuple[float, float, str]:
    """
    Валидирует координаты поля и возвращает (lat, lon, timezone).
    Честно определяет таймзону по переданным координатам без региональных подмен.
    """
    if lat is None or lon is None:
        lat_val, lon_val = DEFAULT_FALLBACK_LAT, DEFAULT_FALLBACK_LON
    else:
        lat_val, lon_val = float(lat), float(lon)

    lat_rounded = round(lat_val, 4)
    lon_rounded = round(lon_val, 4)
    timezone = resolve_timezone_by_coords(lat_rounded, lon_rounded)

    return lat_rounded, lon_rounded, timezone


async def reverse_geocode(lat: float, lon: float, lang: str = "ru") -> str:
    """
    Асинхронный сервис обратного геокодинга через OpenStreetMap Nominatim.
    Возвращает реальный населенный пункт или район.
    При недоступности сервиса или ошибке — строго возвращает fallback Поле (lat, lon),
    никогда не выдумывая дефолтный город.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return "Поле (неизвестные координаты)"

    fallback = f"Поле ({lat_f:.4f}, {lon_f:.4f})"
    cache_key = (round(lat_f, 3), round(lon_f, 3), lang)

    async with _GEOCODE_LOCK:
        if cache_key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[cache_key]

    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat_f}&lon={lon_f}&format=json&zoom=12"
    headers = {
        "User-Agent": "SuTechIrrigationBot/1.0 (agri@sutech.kz)",
        "Accept-Language": f"{lang}, ru, kz, en",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    addr = data.get("address", {})
                    # Приоритет от детального населенного пункта к району
                    locality = (
                        addr.get("village") or
                        addr.get("hamlet") or
                        addr.get("isolated_dwelling") or
                        addr.get("town") or
                        addr.get("city") or
                        addr.get("municipality") or
                        addr.get("county") or
                        addr.get("district") or
                        addr.get("state_district") or
                        addr.get("state")
                    )
                    if locality:
                        res = str(locality).strip()
                        async with _GEOCODE_LOCK:
                            _GEOCODE_CACHE[cache_key] = res
                        return res
    except Exception as exc:
        logger.debug("Reverse geocode request failed for (%s, %s): %s", lat, lon, exc)

    return fallback


async def get_field_location_name(lat: float, lon: float, lang: str = "ru") -> str:
    """Удобный хелпер для получения названия локации с гарантированным ответом."""
    return await reverse_geocode(lat, lon, lang)
