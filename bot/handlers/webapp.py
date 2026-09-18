from datetime import datetime
import json
import logging
import math

import aiohttp
from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

try:
    from i18n import t
    from keyboards.inline import get_report_inline_keyboard
    from user_state import add_history, get_lang
except ImportError:
    from bot.i18n import t
    from bot.keyboards.inline import get_report_inline_keyboard
    from bot.user_state import get_lang

webapp_router = Router()
logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

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
    async with aiohttp.ClientSession() as session:
        async with session.get(
            OPEN_METEO_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json()

    current = payload.get("current", {})
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


@webapp_router.message(F.web_app_data)
async def handle_webapp_data(message: Message, state: FSMContext) -> None:
    """
    Принимает JSON-данные из Telegram Mini App через Telegram.WebApp.sendData().
    Извлекает параметры: latitude, longitude, crop, area, area_unit, irrigation_type, field_type, is_saline.
    Производит полный агрономический, климатический и гидрологический расчет по модели FAO-56.
    """
    await state.clear()

    user_id = message.from_user.id
    lang = get_lang(user_id)

    try:
        raw = message.web_app_data.data
        logger.debug("RAW web_app_data от user_id=%s: %s", user_id, raw)

        data = json.loads(raw)
        if data.get("lang") in ("ru", "kz"):
            lang = data["lang"]

        # Координаты
        lat: float | None = data.get("latitude", data.get("lat"))
        lon: float | None = data.get("longitude", data.get("lon"))

        if lat is None or lon is None:
            logger.warning(
                "Координаты не найдены в payload. Ключи в data: %s | raw: %s",
                list(data.keys()), raw,
            )
            await message.answer(t(lang, "err_no_coords"))
            return

        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            await message.answer(t(lang, "err_no_coords"))
            return
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            await message.answer(t(lang, "err_no_coords"))
            return

        # Агрономические параметры
        crop: str = str(data.get("crop", "cotton")).lower()
        if crop not in CROP_KC:
            crop = "other"

        custom_kc = data.get("kc")
        if custom_kc is not None:
            try:
                CROP_KC[crop] = float(custom_kc)
            except (ValueError, TypeError):
                pass

        area_unit: str = str(data.get("area_unit", "hectare")).lower()
        if area_unit not in ("hectare", "sotka"):
            area_unit = "hectare"

        # ВАЛИДАЦИЯ ПЛОЩАДИ: строго больше 0 и менее 50 000
        try:
            area_val = data.get("area")
            if area_val is None:
                await message.answer(t(lang, "err_invalid_area", unit=t(lang, f"unit_{area_unit}")))
                return
            area: float = float(area_val)
        except (ValueError, TypeError):
            await message.answer(t(lang, "err_invalid_area", unit=t(lang, f"unit_{area_unit}")))
            return

        if not (0 < area < 50000):
            logger.warning("Валидация площади не пройдена: area=%.2f от user_id=%s", area, user_id)
            await message.answer(t(lang, "err_invalid_area", unit=t(lang, f"unit_{area_unit}")))
            return

        irrigation_type: str = str(data.get("irrigation_type", "drip")).lower()
        if irrigation_type not in IRRIGATION_EFFICIENCY:
            irrigation_type = "drip"

        field_type: str = str(data.get("field_type", "open") or "open").lower()
        if field_type not in ("open", "greenhouse"):
            field_type = "open"

        is_saline: str = str(data.get("is_saline", "no") or "no").lower()
        if is_saline not in ("no", "yes"):
            is_saline = "no"

        # Конвертация площади в м²
        if area_unit == "hectare":
            area_m2 = area * 10_000.0
        else:
            area_m2 = area * 100.0

        logger.info(
            "Данные получены | user_id=%s | lang=%s | lat=%.6f | lon=%.6f | "
            "crop=%s | area=%.2f %s (%.0f m²) | irrig=%s | field=%s | saline=%s",
            user_id, lang, lat, lon, crop, area, area_unit, area_m2, irrigation_type, field_type, is_saline,
        )

        # Запрашиваем метеоданные у Open-Meteo
        try:
            meteo = await fetch_meteo(lat, lon)
            raw_temp = meteo.get("temperature")
            temperature = float(raw_temp) if raw_temp is not None else 25.0
            raw_soil = meteo.get("soil_moisture")
            soil_moisture = float(raw_soil) if raw_soil is not None else 0.20
            raw_wind = meteo.get("wind_speed")
            wind_speed = float(raw_wind) if raw_wind is not None else 2.0
            raw_rad = meteo.get("radiation")
            radiation = float(raw_rad) if raw_rad is not None else 500.0
        except aiohttp.ClientError as exc:
            logger.error("Ошибка запроса к Open-Meteo: %s", exc)
            await message.answer(t(lang, "err_weather"))
            return

        logger.info(
            "Метеоданные | temp=%.1f°C | soil=%.3f m³/m³ | wind=%.1f м/с | rad=%.1f Вт/м²",
            temperature, soil_moisture, wind_speed, radiation,
        )

        # Полный расчет FAO-56 Penman-Monteith с учетом теплицы и солончака
        result = calculate_water_demand(
            temp=temperature,
            moisture=soil_moisture,
            wind=wind_speed,
            radiation=radiation,
            crop=crop,
            area_m2=area_m2,
            irrigation_type=irrigation_type,
            field_type=field_type,
            is_saline=is_saline,
        )

        logger.info(
            "FAO-56 | ET0=%.2f | ETc=%.2f | V=%s | saved_water=%s | saved_money=%s ₸ | полив=%s",
            result["et0_mm_day"],
            result["etc_mm_day"],
            result["volume_str"],
            result["saved_water_str"],
            result["savings_tenge"],
            result["needs_irrigation"],
        )

        # Локализованные названия параметров
        crop_name       = t(lang, f"crop_{crop}")
        unit_name       = t(lang, f"unit_{area_unit}")
        irrig_name      = t(lang, f"irrig_{irrigation_type}")
        field_type_name = t(lang, f"field_type_{field_type}")
        saline_name     = t(lang, f"saline_{is_saline}")
        final_message = format_compact_report(
            lang, crop, irrigation_type, area_m2,
            temperature, wind_speed, soil_moisture, result,
        )

        # Сохраняем расчет в историю пользователя навсегда (SQLite)
        try:
            from db import save_calculation
        except ImportError:
            from bot.db import save_calculation
        created_at = datetime.now().strftime("%d.%m.%Y %H:%M")
        crop_text = f"{crop_name} (Kc = {result['kc']})"
        area_text = f"{area} {unit_name} ({area_m2:,} м²)".replace(",", " ")
        irrigation_text = f"{field_type_name} | {saline_name} | {irrig_name}"
        volume_text = result["volume_str"]
        savings_text = f"{result['saved_water_str']} (~{result['savings_tenge']:,} ₸)".replace(",", " ")

        save_calculation(
            user_id=user_id,
            crop_name=crop_text,
            area_text=area_text,
            irrigation_text=irrigation_text,
            volume_text=volume_text,
            savings_text=savings_text,
            lang=lang,
            created_at=created_at
        )

        await message.answer(
            final_message,
            parse_mode="HTML",
            reply_markup=get_report_inline_keyboard(lang),
        )

    except json.JSONDecodeError:
        logger.error("Не удалось распарсить JSON от WebApp: %s", message.web_app_data.data)
        await message.answer(t(lang, "err_format"))
    except Exception:
        import traceback
        traceback.print_exc()
        logger.exception("Неожиданная ошибка в handle_webapp_data")
        await message.answer(t(lang, "err_internal"))
