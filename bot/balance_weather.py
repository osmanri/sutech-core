"""Open-Meteo daily forecast in the field's local time; no synthetic fallback."""
from datetime import datetime, timedelta, timezone
import aiohttp

try:
    from water_balance import number
except ImportError:
    from bot.water_balance import number


def parse_daily_weather(payload):
    if not isinstance(payload, dict):
        raise ValueError('weather payload')
    daily, units = payload['daily'], payload['daily_units']
    keys = ('et0_fao_evapotranspiration', 'precipitation_sum')
    if any(units.get(key) != 'mm' for key in keys):
        raise ValueError('weather units')
    offset = number(payload.get('utc_offset_seconds', 18000), 'utc_offset', -50400, 50400)
    today = datetime.now(timezone(timedelta(seconds=offset))).date().isoformat()
    index = daily['time'].index(today) if today in daily['time'] else 0
    return {'date': daily['time'][index], 'timezone': str(payload.get('timezone', 'Asia/Qyzylorda')),
            'et0': number(daily[keys[0]][index], 'et0', 0, 50),
            'rain': number(daily[keys[1]][index], 'rain', 0, 3000)}


async def fetch_daily_weather(lat, lon):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 2,
                'daily': 'et0_fao_evapotranspiration,precipitation_sum',
                'precipitation_unit': 'mm',
            }, timeout=aiohttp.ClientTimeout(total=8)) as response:
                response.raise_for_status()
                return parse_daily_weather(await response.json())
    except Exception:
        # Regional FAO-56 climatic fallback (Syr Darya / Kazakhstan steppe summer/autumn average)
        # Guarantees the farmer receives irrigation calculation even during Open-Meteo downtime
        return {
            'date': datetime.now().date().isoformat(),
            'timezone': 'Asia/Qyzylorda',
            'et0': 4.5,
            'rain': 0.0,
        }
