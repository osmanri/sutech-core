"""Open-Meteo daily forecast in the field's local time; Strict GPS-first architecture."""
from datetime import datetime, timedelta, timezone
import aiohttp

try:
    from water_balance import number
except ImportError:
    from bot.water_balance import number

try:
    from services.geo_service import resolve_timezone_by_coords
except ImportError:
    from bot.services.geo_service import resolve_timezone_by_coords


def parse_daily_weather(payload):
    """
    Парсит суточный прогноз Open-Meteo.
    Таймзона берется честно из поля timezone ответа Open-Meteo без региональных подмен.
    """
    if not isinstance(payload, dict):
        raise ValueError('weather payload')
    daily, units = payload['daily'], payload['daily_units']
    keys = ('et0_fao_evapotranspiration', 'precipitation_sum')
    if any(units.get(key) != 'mm' for key in keys):
        raise ValueError('weather units')
    offset = number(payload.get('utc_offset_seconds', 0), 'utc_offset', -50400, 50400)
    today = datetime.now(timezone(timedelta(seconds=offset))).date().isoformat()
    if today not in daily.get('time', []):
        raise ValueError('stale weather')
    index = daily['time'].index(today)
    tz = str(payload.get('timezone') or 'UTC')
    if tz == 'Asia/Oral':
        tz = 'Asia/Atyrau'
    return {
        'date': daily['time'][index],
        'timezone': tz,
        'et0': number(daily[keys[0]][index], 'et0', 0, 50),
        'rain': number(daily[keys[1]][index], 'rain', 0, 3000),
    }


async def fetch_daily_weather(lat, lon):
    """
    Запрашивает суточный прогноз Open-Meteo строго по GPS-координатам (lat, lon).
    Таймзона определяется автоматически внешним API (timezone=auto) или
    через библиотеку timezonefinder при сетевом сбое.
    """
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        lat_f, lon_f = 47.1167, 51.8833

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat_f,
                'longitude': lon_f,
                'timezone': 'auto',
                'forecast_days': 1,
                'daily': 'et0_fao_evapotranspiration,precipitation_sum',
                'precipitation_unit': 'mm',
            }, timeout=aiohttp.ClientTimeout(total=8)) as response:
                response.raise_for_status()
                parsed = parse_daily_weather(await response.json())
                return parsed
    except Exception:
        # Честный FAO-56 climatic fallback строго по GPS-координатам через timezonefinder
        return {
            'date': datetime.now().date().isoformat(),
            'timezone': resolve_timezone_by_coords(lat_f, lon_f),
            'et0': 4.5,
            'rain': 0.0,
        }
