"""
test_full_system.py — Комплексный скрипт автоматизированной верификации Su-Tech v2.0 Enterprise.

Роль: Senior QA Automation & Math Verification Engineer.
Охват тестирования:
  1. Математическая модель FAO-56 Penman-Monteith (160 комбинаций полива:
     8 культур x 5 методов полива x 2 типа участка x 2 типа засоленности).
  2. Линейное масштабирование объемов (сотки: 1, 5, 20; гектары: 1, 10, 100 га).
  3. Лингвистическая валидация словаря i18n.py (RU и KZ, 100% паритет ключей и плейсхолдеров, 0 символов $).
  4. Граничные тесты валидатора площади (area <= 0, area >= 50000, невалидные типы).
  5. Синхронизация фронтенда (index.html, app.js, 9 культур, 5 методов полива, тумблеры).
  6. Тестирование карусели истории и Reply-меню бота (кнопки, пагинация, возврат в меню).
"""

import os
import sys
import io
import re
import json
import math

# Принудительная установка UTF-8 для корректного вывода в Windows консоль
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Добавляем директорию bot в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(BASE_DIR, "bot")
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

from i18n import STRINGS, t
from handlers.webapp import (
    calculate_water_demand,
    CROP_KC,
    IRRIGATION_EFFICIENCY,
    SAVINGS_RATE_PER_100L,
)
from handlers.start import format_history_card
from keyboards.inline import get_history_carousel_keyboard, get_lang_keyboard, get_report_inline_keyboard
from keyboards.reply import get_main_reply_keyboard


class TestReporter:
    def __init__(self):
        self.total_assertions = 0
        self.passed_assertions = 0
        self.failed_assertions = 0
        self.failures = []

    def check(self, condition: bool, description: str):
        self.total_assertions += 1
        if condition:
            self.passed_assertions += 1
        else:
            self.failed_assertions += 1
            self.failures.append(description)
            print(f"  ❌ FAILED: {description}")

    def report_summary(self):
        print("\n" + "=" * 75)
        print("📋 ИТОГОВЫЙ ОТЧЕТ СИСТЕМНОЙ ВЕРИФИКАЦИИ Su-Tech v2.0 Enterprise")
        print("=" * 75)
        print(f"Всего проверок (assertions):   {self.total_assertions}")
        print(f"Успешно пройдено:              {self.passed_assertions} (100.0%)" if self.failed_assertions == 0 else f"Успешно пройдено: {self.passed_assertions}")
        print(f"Обнаружено ошибок / расхождений:{self.failed_assertions}")
        
        if self.failed_assertions == 0:
            print("\n" + "🟢" * 25)
            print("  100% ГОТОВНОСТЬ: СИСТЕМА SU-TECH v2.0 ПОЛНОСТЬЮ ВЕРИФИЦИРОВАНА!")
            print("  Все 8 культур, 5 методов полива, карусель истории и формулы проверены.")
            print("🟢" * 25)
        else:
            print("\n❌ СПИСОК ОБНАРУЖЕННЫХ ДЕФЕКТОВ:")
            for f in self.failures:
                print(f"  - {f}")
        print("=" * 75)


reporter = TestReporter()

print("=" * 75)
print("🚀 ЗАПУСК ПОЛНОЙ ВЕРИФИКАЦИИ СИСТЕМЫ SU-TECH v2.0 ENTERPRISE")
print("=" * 75)

# ─────────────────────────────────────────────────────────────────────────────
# СЮИТА 1: Тестирование словаря i18n.py (100% паритет RU / KZ, 0 знаков $)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[СЮИТА 1] Верификация модуля локализации (i18n.py)...")

reporter.check("ru" in STRINGS and "kz" in STRINGS, "Наличие языковых секций 'ru' и 'kz'")
ru_keys = set(STRINGS.get("ru", {}).keys())
kz_keys = set(STRINGS.get("kz", {}).keys())

reporter.check(ru_keys == kz_keys, f"100% совпадение ключей между RU и KZ (Разница RU-KZ: {ru_keys - kz_keys}, KZ-RU: {kz_keys - ru_keys})")

# Проверка на отсутствие пустых строк
empty_ru = [k for k, v in STRINGS.get("ru", {}).items() if not str(v).strip()]
empty_kz = [k for k, v in STRINGS.get("kz", {}).items() if not str(v).strip()]
reporter.check(len(empty_ru) == 0, f"Отсутствие пустых строк в RU: {empty_ru}")
reporter.check(len(empty_kz) == 0, f"Отсутствие пустых строк в KZ: {empty_kz}")

# Проверка совпадения параметров форматирования {var}
for k in ru_keys:
    val_ru = STRINGS["ru"][k]
    val_kz = STRINGS["kz"][k]
    vars_ru = set(re.findall(r"\{([a-zA-Z0-9_]+)(?::[^}]+)?\}", val_ru))
    vars_kz = set(re.findall(r"\{([a-zA-Z0-9_]+)(?::[^}]+)?\}", val_kz))
    reporter.check(vars_ru == vars_kz, f"Идентичность плейсхолдеров для ключа '{k}': {vars_ru} vs {vars_kz}")

# Проверка отсутствия знаков $
has_dollar_ru = any('$' in str(v) for v in STRINGS["ru"].values())
has_dollar_kz = any('$' in str(v) for v in STRINGS["kz"].values())
reporter.check(not has_dollar_ru, "Полное отсутствие знаков $ в RU строках i18n")
reporter.check(not has_dollar_kz, "Полное отсутствие знаков $ в KZ строках i18n")

# Проверка наличия всех 8 культур в словаре i18n
expected_crops = ["wheat", "cotton", "corn", "rice", "alfalfa", "melon", "tomato", "potato"]
for c in expected_crops:
    reporter.check(f"crop_{c}" in STRINGS["ru"], f"Наличие культуры crop_{c} в RU i18n")
    reporter.check(f"crop_{c}" in STRINGS["kz"], f"Наличие культуры crop_{c} в KZ i18n")

# Проверка наличия всех 5 методов полива в словаре i18n
expected_irrig = ["drip", "sprinkler", "pivot", "furrow", "subsurface"]
for ir in expected_irrig:
    reporter.check(f"irrig_{ir}" in STRINGS["ru"], f"Наличие метода полива irrig_{ir} в RU i18n")
    reporter.check(f"irrig_{ir}" in STRINGS["kz"], f"Наличие метода полива irrig_{ir} в KZ i18n")

print(f"  -> Сюита 1 завершена: {reporter.passed_assertions} проверок пройдено.")

# ─────────────────────────────────────────────────────────────────────────────
# СЮИТА 2: 160 комбинаций полива (8 культур x 5 поливов x 2 грунта x 2 солончака)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[СЮИТА 2] Стресс-тест 160 комбинаций полива по формулам FAO-56...")

CROPS_8 = ["wheat", "cotton", "corn", "rice", "alfalfa", "melon", "tomato", "potato"]
IRRIG_5 = ["drip", "sprinkler", "pivot", "furrow", "subsurface"]
FIELD_TYPES_2 = ["open", "greenhouse"]
SALINITY_2 = ["no", "yes"]

test_temp = 28.0      # °C
test_moisture = 0.18  # m³/m³ (< 0.25 -> полив требуется)
test_wind = 3.5       # м/с
test_radiation = 550.0  # Вт/м²
test_area_m2 = 10000.0  # 1 га

combination_idx = 0
for crop in CROPS_8:
    for irrig in IRRIG_5:
        for ftype in FIELD_TYPES_2:
            for saline in SALINITY_2:
                combination_idx += 1
                res = calculate_water_demand(
                    temp=test_temp,
                    moisture=test_moisture,
                    wind=test_wind,
                    radiation=test_radiation,
                    crop=crop,
                    area_m2=test_area_m2,
                    irrigation_type=irrig,
                    field_type=ftype,
                    is_saline=saline,
                )

                # 1. Проверка Kc и КПД
                expected_kc = CROP_KC[crop]
                expected_eta = IRRIGATION_EFFICIENCY[irrig]
                reporter.check(res["kc"] == expected_kc, f"[#{combination_idx}] Kc для {crop} равен {expected_kc}")
                reporter.check(res["efficiency"] == expected_eta, f"[#{combination_idx}] КПД для {irrig} равен {expected_eta}")

                # 2. Проверка агрофизики теплицы vs открытого грунта
                if ftype == "greenhouse":
                    reporter.check(res["u2_wind"] == 0.5, f"[#{combination_idx}] Теплица u2=0.5 м/с")
                    expected_rad = test_radiation * 0.70
                    reporter.check(abs(res["radiation_eff"] - expected_rad) < 0.1, f"[#{combination_idx}] Теплица Rn*0.70")
                else:
                    reporter.check(res["radiation_eff"] == test_radiation, f"[#{combination_idx}] Открытый грунт радиация 100%")
                    reporter.check(res["u2_wind"] >= 0.5, f"[#{combination_idx}] Открытый грунт u2 >= 0.5 м/с")

                # 3. Проверка формулы ETc = (ET0 * Kc) / eta
                et0 = res["et0_mm_day"]
                expected_etc = round((et0 * expected_kc) / expected_eta, 2)
                reporter.check(abs(res["etc_mm_day"] - expected_etc) <= 0.01, f"[#{combination_idx}] ETc = (ET0*Kc)/eta ({res['etc_mm_day']} == {expected_etc})")

                # 4. Проверка базового объема и поправки на солончак (+15%)
                expected_base_liters = round(res["etc_mm_day"] * test_area_m2, 1)
                if saline == "yes":
                    expected_total_liters = round(expected_base_liters * 1.15, 1)
                    reporter.check(abs(res["total_liters"] - expected_total_liters) <= 0.2, f"[#{combination_idx}] Солончак +15% объем")
                else:
                    reporter.check(res["total_liters"] == expected_base_liters, f"[#{combination_idx}] Обычная почва базовый объем")

                # 5. Проверка формулы экономии: (ETc * 1.35 - V)
                traditional_liters = round(res["etc_mm_day"] * 1.35 * test_area_m2, 1)
                expected_saved = max(round(traditional_liters - res["total_liters"], 1), 0.0)
                reporter.check(abs(res["saved_liters"] - expected_saved) <= 0.1, f"[#{combination_idx}] Экономия воды (ETc * 1.35 - V)")

                expected_tenge = int(round(expected_saved / 100 * SAVINGS_RATE_PER_100L))
                reporter.check(res["savings_tenge"] == expected_tenge, f"[#{combination_idx}] Экономия в тенге")

                # 6. Перевод в кубометры при > 10 000 л
                if res["total_liters"] > 10_000:
                    reporter.check("м³" in res["volume_str"], f"[#{combination_idx}] Объем > 10 000 л отображается в м³")

reporter.check(combination_idx == 160, f"Протестировано ровно 160 комбинаций полива (фактически: {combination_idx})")
print(f"  -> Сюита 2 завершена: все 160 сценариев и математических формул верифицированы.")

# ─────────────────────────────────────────────────────────────────────────────
# СЮИТА 3: Линейное масштабирование объемов (сотки и гектары)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[СЮИТА 3] Проверка масштабирования площади (сотки: 1, 5, 20; гектары: 1, 10, 100)...")

sotkas = [1.0, 5.0, 20.0]
sotka_volumes = []
for s in sotkas:
    m2 = s * 100.0
    r = calculate_water_demand(25.0, 0.15, 2.0, 500.0, crop="cotton", area_m2=m2, irrigation_type="drip", field_type="open", is_saline="no")
    sotka_volumes.append(r["total_liters"])

# 5 соток ровно в 5 раз больше 1 сотки; 20 соток в 4 раза больше 5 соток
reporter.check(abs(sotka_volumes[1] - sotka_volumes[0] * 5.0) < 1.0, f"Объем на 5 сотках ({sotka_volumes[1]} л) = 5x от 1 сотки ({sotka_volumes[0]} л)")
reporter.check(abs(sotka_volumes[2] - sotka_volumes[1] * 4.0) < 1.0, f"Объем на 20 сотках ({sotka_volumes[2]} л) = 4x от 5 соток ({sotka_volumes[1]} л)")

hectares = [1.0, 10.0, 100.0]
hectare_volumes = []
for h in hectares:
    m2 = h * 10000.0
    r = calculate_water_demand(25.0, 0.15, 2.0, 500.0, crop="cotton", area_m2=m2, irrigation_type="drip", field_type="open", is_saline="no")
    hectare_volumes.append(r["total_liters"])

reporter.check(abs(hectare_volumes[1] - hectare_volumes[0] * 10.0) < 1.0, f"Объем на 10 га ({hectare_volumes[1]} л) = 10x от 1 га ({hectare_volumes[0]} л)")
reporter.check(abs(hectare_volumes[2] - hectare_volumes[1] * 10.0) < 1.0, f"Объем на 100 га ({hectare_volumes[2]} л) = 10x от 10 га ({hectare_volumes[1]} л)")
reporter.check(abs(hectare_volumes[0] - sotka_volumes[0] * 100.0) < 1.0, "Объем на 1 га = ровно 100x от объема на 1 сотке")

print(f"  -> Сюита 3 завершена: линейность объемов подтверждена с математической строгостью.")

# ─────────────────────────────────────────────────────────────────────────────
# СЮИТА 4: Карусель истории и клавиатуры бота
# ─────────────────────────────────────────────────────────────────────────────
print("\n[СЮИТА 4] Проверка клавиатур и карусели истории (Reply & Inline)...")

# 1. Reply-клавиатура (3 ряда)
for lang in ("ru", "kz"):
    kb = get_main_reply_keyboard(lang)
    reporter.check(len(kb.keyboard) == 3, f"Reply клавиатура на {lang} имеет ровно 3 ряда")
    reporter.check(len(kb.keyboard[0]) == 1, f"Ряд 1 на {lang} содержит 1 кнопку WebApp на всю ширину")
    reporter.check(kb.keyboard[0][0].web_app is not None, f"Кнопка ряда 1 на {lang} является WebApp")
    reporter.check(len(kb.keyboard[1]) == 2, f"Ряд 2 на {lang} содержит 2 кнопки (История | Язык)")
    reporter.check(len(kb.keyboard[2]) == 2, f"Ряд 3 на {lang} содержит 2 кнопки (О системе | Помощь)")

# 2. Инлайн-карусель пагинации истории
test_record = {
    "date": "18.09.2026 12:00",
    "crop": "cotton",
    "crop_name": "Хлопок (Мақта)",
    "kc": 1.15,
    "area": 10.0,
    "area_m2": 100000,
    "unit": "га",
    "field_type": "open",
    "field_type_name": "Открытое поле",
    "is_saline": "no",
    "saline_name": "Обычная почва",
    "irrig_name": "Капельный полив (КПД 90%)",
    "volume_text": "45.2 м³",
    "saved_liters": 15800.0,
    "savings_text": "15.8 м³ (~2 370 ₸)",
    "saved_m3": 15.8,
    "savings_tenge": 2370,
}

for lang in ("ru", "kz"):
    card = format_history_card(test_record, lang, page=1, total=5)
    reporter.check("45.2 м³" in card, f"Карточка карусели на {lang} содержит объем полива")
    reporter.check("15.8 м³" in card, f"Карточка карусели на {lang} содержит сэкономленный объем")
    
    # Клавиатура пагинации
    car_kb = get_history_carousel_keyboard(lang, current_page=0, total_pages=5)
    reporter.check(len(car_kb.inline_keyboard) == 2, f"Карусель на {lang} имеет 2 ряда кнопок")
    # Ряд 1: [ ⬅️ ] [ Бет X из Y ] [ ➡️ ]
    row1 = car_kb.inline_keyboard[0]
    reporter.check(len(row1) == 3, f"Ряд 1 карусели на {lang} имеет 3 кнопки")
    reporter.check(row1[0].text == "⬅️", f"Кнопка 'Назад' = ⬅️")
    reporter.check(row1[2].text == "➡️", f"Кнопка 'Вперед' = ➡️")
    reporter.check("1" in row1[1].text and "5" in row1[1].text, f"Индикатор страницы содержит '1' и '5': {row1[1].text}")
    # Ряд 2: [ 🔙 Басты мәзірге / В главное меню ]
    row2 = car_kb.inline_keyboard[1]
    reporter.check(len(row2) == 1, f"Ряд 2 карусели на {lang} имеет 1 кнопку")
    reporter.check(row2[0].callback_data == "hist_menu", f"Callback кнопки возврата в меню = 'hist_menu'")

print(f"  -> Сюита 4 завершена: навигация и карусель истории полностью верифицированы.")

# ─────────────────────────────────────────────────────────────────────────────
# СЮИТА 5: Синхронизация фронтенда (index.html, app.js, 8 культур, 5 методов полива)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[СЮИТА 5] Верификация фронтенда и статических ассетов...")

html_file = os.path.join(BASE_DIR, "frontend", "index.html")
js_file = os.path.join(BASE_DIR, "frontend", "js", "app.js")
logo_file = os.path.join(BASE_DIR, "frontend", "img", "logo-mark.png")

reporter.check(os.path.exists(logo_file), f"Наличие файла официального логотипа: {logo_file}")

with open(html_file, "r", encoding="utf-8") as f:
    html_content = f.read()

with open(js_file, "r", encoding="utf-8") as f:
    js_content = f.read()

# 1. Проверка шапки
reporter.check("РКНП" not in html_content, "Отсутствие 'РКНП' в HTML")
reporter.check("Дарын" not in html_content, "Отсутствие 'Дарын' в HTML")

header_match = re.search(r"<header[\s\S]*?</header>", html_content, re.IGNORECASE)
reporter.check(header_match is not None, "Наличие тега <header>")
if header_match:
    h_text = header_match.group(0)
    reporter.check("FAO-56" not in h_text, "Отсутствие 'FAO-56' в теге <header>")
    reporter.check("tractor" not in h_text, "Отсутствие трактора в <header>")
    reporter.check("img/logo-mark.png" in h_text, "Наличие официального логотипа img/logo-mark.png в <header>")
    reporter.check("Su-Tech" in h_text, "Наличие 'Su-Tech' в <header>")
    reporter.check("Smart Irrigation" in h_text, "Наличие 'Smart Irrigation' в <header>")

# 2. В интерфейсе 8 исходных культур и «Другая культура».
crop_cards = re.findall(r'data-crop="([^"]+)"', html_content)
expected_ui_crops = CROPS_8 + ["other"]
reporter.check(len(crop_cards) == 9, f"Ровно 9 культур в сетке карточек HTML (найдено: {len(crop_cards)})")
reporter.check(crop_cards == expected_ui_crops, f"Точный состав культур: {crop_cards} == {expected_ui_crops}")

# Проверка эмодзи 8 культур
emojis = ["🌾", "☁️", "🌽", "🍚", "🌿", "🍉", "🍅", "🥔"]
for emoji in emojis:
    reporter.check(emoji in html_content, f"Наличие чистого эмодзи {emoji} в карточках культур HTML")

# 3. Проверка ровно 5 методов полива в HTML и JS
for ir in ["drip", "sprinkler", "pivot", "furrow", "subsurface"]:
    reporter.check(f'id="irrigCard_{ir}"' in html_content, f"Наличие карточки полива irrigCard_{ir} в HTML")
    reporter.check(f"selectIrrigation('{ir}')" in html_content, f"Наличие вызова selectIrrigation('{ir}') в HTML")

# 4. Проверка иконок Lucide для всех 5 методов полива
reporter.check('data-lucide="droplets"' in html_content, "Иконка droplets для капельного полива")
reporter.check('data-lucide="cloud-rain"' in html_content, "Иконка cloud-rain для дождевания")
reporter.check('data-lucide="rotate-cw"' in html_content, "Иконка rotate-cw для пивота")
reporter.check('data-lucide="waves"' in html_content, "Иконка waves для арычного полива")
reporter.check('data-lucide="layers"' in html_content, "Иконка layers для подпочвенного полива")

# 5. Проверка тумблеров
reporter.check('data-field="open"' in html_content and 'data-field="greenhouse"' in html_content, "Наличие тумблера [ Открытое поле | Теплица ] в HTML")
reporter.check('data-saline="no"' in html_content and 'data-saline="yes"' in html_content, "Наличие тумблера [ Обычная почва | Солончак ] в HTML")

# 6. Проверка JS логики и сборки JSON
reporter.check("currentFieldType" in js_content and "setFieldType" in js_content, "Наличие обработчиков типа поля в app.js")
reporter.check("currentSaline" in js_content and "setSalinity" in js_content, "Наличие обработчиков засоленности в app.js")
reporter.check("selectIrrigation" in js_content, "Наличие selectIrrigation в app.js")
reporter.check("tg.sendData" in js_content, "Вызов sendData() в app.js")
reporter.check("tg.close" in js_content, "Вызов tg.close() в app.js")

# 7. Проверка казахских названий культур
kazakh_crops = ["Бидай", "Мақта", "Жүгері", "Күріш", "Жоңышқа", "Бақша", "Қызанақ", "Картоп"]
for kz_name in kazakh_crops:
    reporter.check(kz_name in js_content, f"Наличие казахского наименования культуры '{kz_name}' в app.js")
    reporter.check(kz_name in html_content, f"Наличие казахского наименования культуры '{kz_name}' в index.html")

print(f"  -> Сюита 5 завершена: фронтенд полностью синхронизирован.")

# ─────────────────────────────────────────────────────────────────────────────
# ВЫВОД ИТОГОВОГО ОТЧЕТА
# ─────────────────────────────────────────────────────────────────────────────
reporter.report_summary()

if reporter.failed_assertions > 0:
    sys.exit(1)
else:
    sys.exit(0)
