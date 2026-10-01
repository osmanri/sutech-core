"""Open-Meteo daily forecast in the field's local time; Strict GPS-first architecture."""
from datetime import datetime, timedelta, timezone
import logging
import aiohttp

logger = logging.getLogger(__name__)

try:
    from water_balance import number
except ImportError:
    from bot.water_balance import number

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
    return {
        'date': daily['time'][index],
        'timezone': tz,
        'et0': number(daily[keys[0]][index], 'et0', 0, 50),
        'rain': number(daily[keys[1]][index], 'rain', 0, 3000),
    }


async def fetch_daily_weather(lat, lon):
    """
    Запрашивает суточный прогноз Open-Meteo строго по GPS-координатам (lat, lon).
    Таймзона определяется внешним API (timezone=auto). При сетевом сбое
    расчет прекращается: нельзя подменять реальную погоду условными числами.
    """
    lat_f = number(lat, 'latitude', -90, 90)
    lon_f = number(lon, 'longitude', -180, 180)

    async with aiohttp.ClientSession() as session:
        params = {
            'latitude': lat_f,
            'longitude': lon_f,
            'timezone': 'auto',
            'forecast_days': 1,
            'daily': 'et0_fao_evapotranspiration,precipitation_sum',
            'precipitation_unit': 'mm',
        }
        try:
            async with session.get('https://api.open-meteo.com/v1/forecast', params=params,
                                   timeout=aiohttp.ClientTimeout(total=8)) as response:
                response.raise_for_status()
                return parse_daily_weather(await response.json())
        except (aiohttp.ClientError, TimeoutError):
            # Same daily forecast through our bounded Vercel cache. Shared
            # hosting IPs may exhaust the provider quota independently of us.
            # Date, units and values are validated again before calculation.
            async with session.get('https://frontend-2-mauve.vercel.app/api/weather',
                                   params={'latitude': lat_f, 'longitude': lon_f},
                                   timeout=aiohttp.ClientTimeout(total=8)) as response:
                response.raise_for_status()
                weather = parse_daily_weather(await response.json())
                logger.info('Daily weather recovered through application cache')
                return weather
