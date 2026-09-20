from datetime import datetime
import asyncio
import json
import logging
import math

import aiohttp
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

try:
    from i18n import t
    from keyboards.inline import get_report_inline_keyboard
    from user_state import add_history, get_lang
    from db import save_report_explanation, get_report_explanation
    from water_balance import parse_field, calculate_balance, number, BalanceInputError
    from balance_weather import fetch_daily_weather
    from balance_report import format_balance_report, format_balance_explanation, economics, fmt
    from field_service import persist_webapp_field
    from field_state import FieldStateError
except ImportError:
    from bot.i18n import t
    from bot.keyboards.inline import get_report_inline_keyboard
    from bot.user_state import get_lang
    from bot.db import save_report_explanation, get_report_explanation
    from bot.water_balance import parse_field, calculate_balance, number, BalanceInputError
    from bot.balance_weather import fetch_daily_weather
    from bot.balance_report import format_balance_report, format_balance_explanation, economics, fmt
    from bot.field_service import persist_webapp_field
    from bot.field_state import FieldStateError

webapp_router = Router()
logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_METEO = {
    "temperature": 25.0,
    "soil_moisture": 0.20,
    "wind_speed": 2.0,
    "radiation": 500.0,
}

# ── Агрономические коэффициенты культур (Kc по FAO-56, строго 8 культур) ─────
CROP_KC: dict[str, float] = {
    "wheat":     1.10,  # 🌾 Пшеница (Бидай)
    "cotton":    1.15,  # ☁️ Хлопок (Мақта)
    "corn":      1.20,  # 🌽 Кукуруза (Жүгері)
    "alfalfa":   1.05,  # 🌿 Люцерна (Жоңышқа)
    "melon":     1.05,  # 🍉 Бахча (Қарбыз/Қауын)
    "tomato":    1.15,  # 🍅 Томаты (Қызанақ)
    "potato":    1.10,  # 🥔 Картофель (Картоп)
    "other":     1.00,  # ⭐ Другая культура (Басқа дақыл)
    # Обратная совместимость
    "rice":      1.25,  # Рис (Күріш)
    "sunflower": 1.00,  # Подсолнечник (Күнбағыс)
}

# ── Технологический КПД систем орошения (η) ──────────────────────────────────
IRRIGATION_EFFICIENCY: dict[str, float] = {
    "drip":       0.90,  # Капельный полив (КПД 90%)
    "sprinkler":  0.75,  # Дождевание (КПД 75%)
    "pivot":      0.80,  # Круговой пивот (КПД 80%)
    "furrow":     0.50,  # Арычный полив (КПД 50%)
    "subsurface": 0.95,  # Подпочвенное (КПД 95%)
}

# ── Экономические коэффициенты ───────────────────────────────────────────────
# Тариф и затраты на подачу воды/электроэнергию (~15 тенге за каждые 100 л перерасхода)
SAVINGS_RATE_PER_100L = 15


async def fetch_meteo(lat: float, lon: float) -> dict:
    """
    Делает асинхронный GET-запрос к Open-Meteo API и возвращает:
      - temperature_2m         (°C)
      - soil_moisture_3_to_9cm (m³/m³)
      - wind_speed_10m         (м/с)
      - shortwave_radiation    (Вт/м²)
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "wind_speed_unit": "ms",
        "current": (
            "temperature_2m,"
            "soil_moisture_3_to_9cm,"
            "wind_speed_10m,"
            "shortwave_radiation"
        ),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OPEN_METEO_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        OSError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        # Telegram WebApps can run on networks that block or interrupt external
        # weather requests. Keep the calculation available with conservative
        # defaults instead of turning a recoverable API outage into err_internal.
        logger.warning(
            "Open-Meteo unavailable for %.6f,%.6f (%s); using defaults",
            lat,
            lon,
            exc,
        )
        return DEFAULT_METEO.copy()

    if not isinstance(payload, dict):
        logger.warning("Open-Meteo returned an unexpected payload; using defaults")
        return DEFAULT_METEO.copy()

    current = payload.get("current")
    if not isinstance(current, dict):
        logger.warning("Open-Meteo response has no current weather block; using defaults")
        return DEFAULT_METEO.copy()

    return {
        "temperature":   current.get("temperature_2m"),
        "soil_moisture": current.get("soil_moisture_3_to_9cm"),
        "wind_speed":    current.get("wind_speed_10m"),
        "radiation":     current.get("shortwave_radiation"),
    }


def calculate_water_demand(
    temp: float,
    moisture: float,
    wind: float,
    radiation: float,
    crop: str = "cotton",
    area_m2: float = 100.0,
    irrigation_type: str = "drip",
    field_type: str = "open",
    is_saline: str = "no",
) -> dict:
    """
    Рассчитывает потребность в воде по модели FAO-56 Penman-Monteith
    с учетом микроклимата участка, биологии культуры, КПД полива,
    засоленности почвы и предотвращенного перерасхода.

    Параметры
    ---------
    temp            : температура воздуха (°C)
    moisture        : влажность почвы (m³/m³)
    wind            : скорость ветра на высоте 10 м (м/с)
    radiation       : коротковолновая радиация (Вт/м²)
    crop            : идентификатор культуры ('wheat', 'cotton', 'corn', 'alfalfa', 'melon', 'tomato', 'potato', 'other')
    area_m2         : площадь участка в квадратных метрах (м²)
    irrigation_type : тип поливной системы ('drip', 'sprinkler', 'pivot', 'furrow', 'subsurface')
    field_type      : тип участка ('open' или 'greenhouse')
    is_saline       : засоленность почвы ('no' или 'yes')

    Возвращает
    ----------
    dict с полным набором агрофизических и гидрологических метрик
    """
    # 1. Корректировка метеоусловий под микроклимат участка:
    # Если теплица: ослабление радиации пленкой на 30% (коэф. 0.7) и обнуление внешнего ветра (u2 = 0.5 м/с)
    if field_type == "greenhouse":
        effective_radiation = radiation * 0.7
        rn = effective_radiation * 0.0864  # Вт/м² -> МДж/м²/день
        u2 = 0.5  # минимальная конвективная циркуляция воздуха в закрытом грунте
    else:
        effective_radiation = radiation
        rn = effective_radiation * 0.0864
        # Скорость ветра на высоте 2 м (логарифмическое приведение с 10 м по FAO-56)
        u2 = max(wind * (4.87 / math.log(67.8 * 10 - 5.42)), 0.5)

    # Наклон кривой давления насыщенного пара (Delta), кПа/°C
    delta = (
        4098 * (0.6108 * math.exp((17.27 * temp) / (temp + 237.3)))
        / (temp + 237.3) ** 2
    )

    # Психрометрическая константа gamma ~ 0.0665 кПа/°C
    gamma = 0.0665

    # Давление насыщенного пара (es) и фактического пара (ea)
    es = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
    # RH оценка через влажность почвы
    rh_approx = min(moisture * 400, 95)
    ea = es * (rh_approx / 100)
    vpd = max(es - ea, 0.01)  # дефицит давления пара, кПа

    # ET₀ = [0.408*Delta*Rn + gamma*(900/(T+273))*u2*VPD] / [Delta + gamma*(1+0.34*u2)]
    numerator   = 0.408 * delta * rn + gamma * (900 / (temp + 273)) * u2 * vpd
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0 = round(max(numerator / denominator, 0.0), 2)  # мм/день, не менее 0

    # 2. Учет биологии культуры (Kc) и КПД поливной системы (η)
    # Формула: ET_c = (ET_0 * Kc) / η
    kc = CROP_KC.get(crop, 1.00)
    eta = IRRIGATION_EFFICIENCY.get(irrigation_type, 0.90)
    etc = round((et0 * kc) / eta, 2)

    # 3. Агрофизическое решение о необходимости полива (порог влажности: 0.25 m³/m³)
    needs_irrigation = moisture < 0.25

    # 4. Базовый суточный объем: V = ET_c * Площадь в м² (1 мм = 1 л/м²)
    base_liters = round(etc * area_m2, 1) if needs_irrigation else 0.0

    # 5. Учет промывочной фракции при засолении: V = V * 1.15
    if is_saline == "yes" and needs_irrigation:
        total_liters = round(base_liters * 1.15, 1)
    else:
        total_liters = round(base_liters, 1)

    volume_m3 = round(total_liters / 1000, 2)

    # Строковое представление объема (в л или м³)
    if total_liters > 10_000:
        volume_str = f"{total_liters / 1000:,.1f} м³".replace(",", " ")
    else:
        volume_str = f"{total_liters:,.0f} л".replace(",", " ")

    # 6. Расчет экономии относительно традиционного полива: (ETc * 1.35 - V)
    # Традиционный полив без моделей расходует 1.35 * ETc на всей площади
    traditional_liters = round(etc * 1.35 * area_m2, 1)
    saved_liters = max(round(traditional_liters - total_liters, 1), 0.0)
    saved_m3 = round(saved_liters / 1000, 2)

    if saved_liters > 10_000:
        saved_water_str = f"{saved_liters / 1000:,.1f} м³".replace(",", " ")
    else:
        saved_water_str = f"{saved_liters:,.0f} л".replace(",", " ")

    savings_tenge = int(round(saved_liters / 100 * SAVINGS_RATE_PER_100L))

    return {
        "et0_mm_day":         round(et0, 2),
        "etc_mm_day":         round(etc, 2),
        "kc":                 kc,
        "efficiency":         eta,
        "u2_wind":            round(u2, 1),
        "radiation_eff":      round(effective_radiation, 1),
        "total_liters":       total_liters,
        "volume_str":         volume_str,
        "volume_m3":          volume_m3,
        "saved_liters":       round(saved_liters, 1),
        "saved_m3":           saved_m3,
        "saved_water_str":    saved_water_str,
        "savings_tenge":      savings_tenge,
        "needs_irrigation":   needs_irrigation,
        "field_type":         field_type,
        "is_saline":          is_saline,
    }


def format_compact_report(lang, crop, irrigation_type, area_m2, temperature, wind_speed, soil_moisture, result):
    """Six-line localized report; always hectares and cubic metres, including small fields."""
    def number(value, precision):
        return f"{value:,.{precision}f}".rstrip("0").rstrip(".").replace(",", " ")

    return t(
        lang, "compact_report",
        crop=t(lang, f"report_crop_{crop}"),
        irrigation=t(lang, f"report_irrig_{irrigation_type}"),
        area_ha=number(area_m2 / 10000, 6),
        temp=f"{temperature:.1f}",
        wind=f"{wind_speed:.1f}",
        moisture=f"{soil_moisture:.3f}",
        volume_m3=number(result["total_liters"] / 1000, 4),
        savings=f"{result['savings_tenge']:,}".replace(",", " "),
        decision=t(lang, "decision_irrigate" if result["needs_irrigation"] else "decision_normal"),
    )


def format_report_explanation(lang, area_m2, moisture, result):
    return t(
        lang, "explanation_body",
        decision=t(lang, "explanation_dry" if result["needs_irrigation"] else "explanation_wet"),
        moisture=f"{moisture:.3f}", et0=result["et0_mm_day"], kc=result["kc"],
        efficiency=round(result["efficiency"] * 100), area=f"{area_m2:g}",
        volume=f"{result['total_liters'] / 1000:.4f}".rstrip('0').rstrip('.'),
        field=t(lang, "explanation_greenhouse" if result["field_type"] == "greenhouse" else "explanation_open"),
        salinity=t(lang, "explanation_saline" if result["is_saline"] == "yes" and result["needs_irrigation"] else "explanation_no_extra"),
    )


@webapp_router.callback_query(F.data.startswith("explain:"))
async def explain_report(callback: CallbackQuery) -> None:
    explanation = get_report_explanation(callback.data.split(":", 1)[1], callback.from_user.id)
    if not explanation or not isinstance(callback.message, Message):
        await callback.answer(t(get_lang(callback.from_user.id), "explanation_unavailable"), show_alert=True)
        return
    await callback.answer()
    await callback.message.reply(explanation, parse_mode="HTML")


@webapp_router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext) -> None:
    """The active WebApp route uses only the versioned daily water balance."""
    await state.clear()
    user_id = message.from_user.id
    lang = get_lang(user_id)
    try:
        data = json.loads(message.web_app_data.data)
        if not isinstance(data, dict):
            raise ValueError('payload')
    except (ValueError, TypeError):
        await message.answer(t(lang, 'err_format'))
        return
    if data.get('lang') in ('ru', 'kz'):
        lang = data['lang']
    try:
        lat = number(data.get('latitude', data.get('lat')), 'latitude', -90, 90)
        lon = number(data.get('longitude', data.get('lon')), 'longitude', -180, 180)
    except BalanceInputError:
        await message.answer(t(lang, 'err_no_coords'))
        return
    try:
        field = parse_field(data)
    except BalanceInputError as exc:
        key = {'version': 'balance_old_app', 'season_ended': 'balance_season_ended'}.get(str(exc), 'balance_error')
        await message.answer(t(lang, key))
        return
    try:
        if field.crop == 'rice':
            weather = {}  # No false numeric recommendation for flooded paddy.
            result = calculate_balance(field, 0, 0)
        else:
            weather = await fetch_daily_weather(lat, lon)
            result = calculate_balance(field, weather['et0'], weather['rain'])
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError, KeyError, TypeError, IndexError):
        logger.exception('Daily Open-Meteo balance unavailable')
        await message.answer(t(lang, 'err_weather'))
        return
    field_id = None
    if field.crop != 'rice':
        try:
            field_id = await persist_webapp_field(user_id, data, field, lat, lon, result, weather)
        except (FieldStateError, ValueError, KeyError, TypeError):
            # A storage failure must not hide a valid, already-computed water recommendation.
            logger.exception('Could not persist daily field state')
    final_message = format_balance_report(lang, field, result, weather)
    if field_id is not None:
        final_message += '\n' + t(lang, 'field_saved_note')
    explanation = format_balance_explanation(lang, field, result, weather)
    try:
        from db import save_calculation
    except ImportError:
        from bot.db import save_calculation
    save_calculation(
        user_id=user_id, crop_name=t(lang, f'report_crop_{field.crop}'),
        area_text=f'{fmt(field.area_ha)} га',
        irrigation_text=t(lang, f'report_irrig_{field.method}'),
        volume_text=(t(lang, 'balance_rice') if field.crop == 'rice' else
                     f"{fmt(result['gross_m3'])} м³ · {t(lang, 'balance_status_' + result['status'])}"),
        savings_text='—' if field.crop == 'rice' else economics(lang, field, result),
        lang=lang, created_at=datetime.now().strftime('%d.%m.%Y %H:%M'),
    )
    report_id = save_report_explanation(user_id, explanation)
    await message.answer(final_message, parse_mode='HTML',
                         reply_markup=get_report_inline_keyboard(lang, report_id, field_id))
