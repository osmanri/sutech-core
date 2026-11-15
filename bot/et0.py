"""FAO-56 reference evapotranspiration (ET0), daily time step.

Implements Allen et al. (1998), FAO Irrigation and Drainage Paper 56:
  * Penman-Monteith, eq. 6 (with Rs from sunshine hours, or measured Rs);
  * Hargreaves-Samani (temperature only; screening estimate, see warning).

Why this module exists: the production bot takes ET0 from Open-Meteo. The pot
experiment is indoors, so outdoor weather does not apply and ET0 has to come from
the room sensors. Equation numbers refer to FAO-56 so every line can be checked
against the paper. Validated in test_et0.py against FAO-56 Example 18.
"""

from __future__ import annotations

import math

SOLAR_CONSTANT = 0.0820          # MJ m-2 min-1
STEFAN_BOLTZMANN = 4.903e-9      # MJ K-4 m-2 day-1


def sat_vapour_pressure(t_c: float) -> float:
    """e0(T), kPa (eq. 11)."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def slope_vapour_pressure(t_c: float) -> float:
    """Delta, kPa/degC (eq. 13)."""
    return 4098.0 * sat_vapour_pressure(t_c) / (t_c + 237.3) ** 2


def atmospheric_pressure(elevation_m: float) -> float:
    """kPa (eq. 7)."""
    return 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26


def psychrometric_constant(elevation_m: float) -> float:
    """kPa/degC (eq. 8)."""
    return 0.000665 * atmospheric_pressure(elevation_m)


def extraterrestrial_radiation(lat_deg: float, day_of_year: int) -> tuple[float, float]:
    """Return (Ra in MJ m-2 day-1, daylight hours N) (eqs. 21-25, 34)."""
    phi = math.radians(lat_deg)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi * day_of_year / 365.0)
    delta = 0.409 * math.sin(2.0 * math.pi * day_of_year / 365.0 - 1.39)
    x = -math.tan(phi) * math.tan(delta)
    ws = math.acos(max(-1.0, min(1.0, x)))  # clamp: polar day / night
    ra = (24.0 * 60.0 / math.pi) * SOLAR_CONSTANT * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))
    return ra, 24.0 / math.pi * ws


def wind_at_2m(u_z: float, height_m: float) -> float:
    """Convert wind speed measured at height_m to 2 m (eq. 47)."""
    return u_z * 4.87 / math.log(67.8 * height_m - 5.42)


def net_radiation(rs: float, ra: float, elevation_m: float, t_max: float, t_min: float, ea: float,
                  albedo: float = 0.23) -> float:
    """Rn, MJ m-2 day-1 (eqs. 37-40); daily soil heat flux G is taken as 0."""
    rns = (1.0 - albedo) * rs
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rs_rso = min(rs / rso, 1.0) if rso > 0 else 0.0
    rnl = (STEFAN_BOLTZMANN * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2.0
           * (0.34 - 0.14 * math.sqrt(ea)) * (1.35 * rs_rso - 0.35))
    return rns - rnl


def et0_penman_monteith(
    *, t_max: float, t_min: float, u2: float, elevation_m: float,
    rs: float | None = None, sunshine_h: float | None = None,
    lat_deg: float | None = None, day_of_year: int | None = None,
    rh_max: float | None = None, rh_min: float | None = None, rh_mean: float | None = None,
    t_dew: float | None = None,
) -> float:
    """Daily ET0, mm/day (eq. 6).

    Radiation: give `rs` (measured, MJ m-2 day-1) or `sunshine_h` with lat/day.
    Humidity (FAO-56 order of preference): t_dew (eq. 14), rh_max and rh_min (eq. 17), rh_mean (eq. 19).
    For an indoor stand pass measured Rs under the lamp and u2 = the real air speed.
    """
    if t_max < t_min:
        raise ValueError("t_max must be >= t_min")
    if u2 < 0:
        raise ValueError("wind speed cannot be negative")
    t_mean = (t_max + t_min) / 2.0
    es = (sat_vapour_pressure(t_max) + sat_vapour_pressure(t_min)) / 2.0
    if t_dew is not None:
        ea = sat_vapour_pressure(t_dew)
    elif rh_max is not None and rh_min is not None:
        ea = (sat_vapour_pressure(t_min) * rh_max / 100.0 + sat_vapour_pressure(t_max) * rh_min / 100.0) / 2.0
    elif rh_mean is not None:
        ea = rh_mean / 100.0 * es
    else:
        raise ValueError("humidity: give t_dew, rh_max and rh_min, or rh_mean")

    ra, n_day = (None, None)
    if lat_deg is not None and day_of_year is not None:
        ra, n_day = extraterrestrial_radiation(lat_deg, day_of_year)
    if rs is None:
        if sunshine_h is None or ra is None:
            raise ValueError("radiation: give rs, or sunshine_h together with lat_deg and day_of_year")
        if n_day is None:
            raise ValueError("lat_deg and day_of_year are needed to convert sunshine hours")
        rs = (0.25 + 0.50 * sunshine_h / n_day) * ra  # eq. 35 with default as, bs
    if ra is None:
        raise ValueError("lat_deg and day_of_year are needed for the clear-sky radiation limit")

    rn = net_radiation(rs, ra, elevation_m, t_max, t_min, ea)
    delta = slope_vapour_pressure(t_mean)
    gamma = psychrometric_constant(elevation_m)
    num = 0.408 * delta * rn + gamma * 900.0 / (t_mean + 273.0) * u2 * (es - ea)
    return max(0.0, num / (delta + gamma * (1.0 + 0.34 * u2)))


def et0_hargreaves(*, t_max: float, t_min: float, lat_deg: float, day_of_year: int) -> float:
    """Hargreaves-Samani daily ET0, mm/day (FAO-56 eq. 52).

    Temperature-only screening estimate: use outdoors when radiation, humidity
    or wind are missing. NOT suitable for an indoor stand with artificial light.
    """
    if t_max < t_min:
        raise ValueError("t_max must be >= t_min")
    ra, _ = extraterrestrial_radiation(lat_deg, day_of_year)
    return max(0.0, 0.0023 * ((t_max + t_min) / 2.0 + 17.8) * math.sqrt(t_max - t_min) * 0.408 * ra)
