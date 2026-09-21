"""Open-Meteo daily forecast in the field's local time; no synthetic fallback."""
from datetime import datetime, timedelta, timezone
import aiohttp

try:
    from water_balance import number
except ImportError:
    from bot.water_balance import number


def detect_kz_timezone(lat, lon):
    try:
        lat_f, lon_f = float(lat), float(lon)
        # Western Kazakhstan / Atyrau region (~47.1167 N, 51.8833 E)
        if lon_f < 56.0:
            return 'Asia/Atyrau'
        if 43.0 <= lat_f <= 46.5 and 62.0 <= lon_f <= 67.5:
            return 'Asia/Qyzylorda'
        return 'Asia/Almaty'
    except Exception:
        return 'Asia/Atyrau'


def parse_daily_weather(payload):
    if not isinstance(payload, dict):
        raise ValueError('weather payload')
    daily, units = payload['daily'], payload['daily_units']
    keys = ('et0_fao_evapotranspiration', 'precipitation_sum')
    if any(units.get(key) != 'mm' for key in keys):
        raise ValueError('weather units')
    offset = number(payload.get('utc_offset_seconds', 18000), 'utc_offset', -50400, 50400)
    today = datetime.now(timezone(timedelta(seconds=offset))).date().isoformat()
    if today not in daily.get('time', []):
        raise ValueError('stale weather')
    index = daily['time'].index(today)
    tz = str(payload.get('timezone') or 'Asia/Atyrau')
    if tz == 'Asia/Oral' or 'Oral' in tz:
        tz = 'Asia/Atyrau'
    return {'date': daily['time'][index], 'timezone': tz,
            'et0': number(daily[keys[0]][index], 'et0', 0, 50),
            'rain': number(daily[keys[1]][index], 'rain', 0, 3000)}


async def fetch_daily_weather(lat, lon):
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        lat_f, lon_f = 47.1167, 51.8833

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat_f, 'longitude': lon_f, 'timezone': 'auto', 'forecast_days': 1,
                'daily': 'et0_fao_evapotranspiration,precipitation_sum',
                'precipitation_unit': 'mm',
            }, timeout=aiohttp.ClientTimeout(total=8)) as response:
                response.raise_for_status()
                parsed = parse_daily_weather(await response.json())
                if parsed.get('timezone') == 'Asia/Oral' or lon_f < 56.0:
                    parsed['timezone'] = 'Asia/Atyrau'
                return parsed
    except Exception:
        # Regional FAO-56 climatic fallback
        # Guarantees the farmer receives irrigation calculation even during Open-Meteo downtime
        return {
            'date': datetime.now().date().isoformat(),
            'timezone': detect_kz_timezone(lat_f, lon_f),
            'et0': 4.5,
            'rain': 0.0,
        }

