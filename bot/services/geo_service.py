"""
Геодезический и астрономический сервис водного баланса FAO-56.
Обеспечивает точный расчет солнечной радиации Ra для широты Атырау (47.1167° N)
и принудительно устанавливает региональную таймзону Asia/Atyrau (UTC+5).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Tuple

# Дефолтные координаты и IANA-таймзона для города Атырау, Казахстан
ATYRAU_DEFAULT_LAT = 47.1167
ATYRAU_DEFAULT_LON = 51.8833
ATYRAU_TIMEZONE = "Asia/Atyrau"


def resolve_field_coordinates(lat: float | None, lon: float | None) -> Tuple[float, float, str]:
    """
    Валидирует координаты поля и возвращает (lat, lon, timezone).
    Если координаты не переданы, использует эталонные координаты Атырау.
    """
    if lat is None or lon is None:
        return ATYRAU_DEFAULT_LAT, ATYRAU_DEFAULT_LON, ATYRAU_TIMEZONE

    lat_f = float(lat)
    lon_f = float(lon)

    # Западный Казахстан / Атырауская область (долгота западнее 56.0° E)
    if lon_f < 56.0:
        timezone = ATYRAU_TIMEZONE
    elif 43.0 <= lat_f <= 46.5 and 62.0 <= lon_f <= 67.5:
        timezone = "Asia/Qyzylorda"
    else:
        timezone = "Asia/Almaty"

    return round(lat_f, 4), round(lon_f, 4), timezone


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
    delta = 0.409 * math.sin((2.0 * math.pi * j / 365.0) - 1.39)
    
    # 5. Угол заката солнца omega_s (уравнение 25 FAO-56)
    # Исключение погрешностей арккосинуса при выходе за пределы [-1, 1]
    tan_val = -math.tan(phi) * math.tan(delta)
    if tan_val <= -1.0:
        omega_s = math.pi  # Полярный день
    elif tan_val >= 1.0:
        omega_s = 0.0      # Полярная ночь
    else:
        omega_s = math.acos(tan_val)
        
    # 6. Внеземная радиация Ra (уравнение 21 FAO-56)
    # Солнечная постоянная G_sc = 0.0820 МДж / (м² · мин)
    g_sc = 0.0820
    ra = (24.0 * 60.0 / math.pi) * g_sc * dr * (
        omega_s * math.sin(phi) * math.sin(delta) +
        math.cos(phi) * math.cos(delta) * math.sin(omega_s)
    )
    return round(max(0.0, ra), 2)
