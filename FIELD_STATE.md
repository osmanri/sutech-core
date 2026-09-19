# Состояние полей Su-Tech

`bot/field_state.py` хранит посевы и накопленный дефицит в той же SQLite-базе,
которую инициализирует `bot.main`. Open-Meteo остаётся источником погоды: после
получения ET₀ бот вычисляет `ETc = ET₀ × Kc`, эффективные осадки и один раз за
расчётный день обновляет запись поля.

```python
import asyncio
from datetime import date

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.field_state import (
    FieldNotFoundError,
    add_new_field,
    get_day_of_growth,
    reset_deficit,
    update_daily_deficit,
)

router = Router()

# Создание поля после заполнения WebApp/FSM.
field_id = await asyncio.to_thread(
    add_new_field,
    telegram_user_id,
    "potato",
    "loam",
    "drip",
    date(2026, 4, 15),       # аргумент можно опустить: будет сегодня
)

# Вечернее задание после получения погоды из уже подключённого Open-Meteo.
day = await asyncio.to_thread(get_day_of_growth, field_id)
kc = crop_kc_for_day("potato", day)
et_c = open_meteo_et0 * kc
effective_rain = 0.0 if open_meteo_rain < 5 else open_meteo_rain * 0.75
new_deficit = await asyncio.to_thread(
    update_daily_deficit, field_id, et_c, effective_rain
)

# Кнопка: callback_data="field-watered:<field_id>".
@router.callback_query(F.data.startswith("field-watered:"))
async def field_watered(callback: CallbackQuery) -> None:
    try:
        selected_id = int(callback.data.split(":", 1)[1])
        await asyncio.to_thread(
            reset_deficit,
            selected_id,
            user_id=callback.from_user.id,  # обязательная проверка владельца
        )
    except (ValueError, FieldNotFoundError):
        await callback.answer("Поле не найдено", show_alert=True)
        return
    await callback.answer("Дефицит обнулён после полива")
```

`update_daily_deficit` использует транзакцию `BEGIN IMMEDIATE`, поэтому два
параллельных обновления не потеряют данные. Планировщик всё равно должен хранить
дату последнего расчёта или использовать идемпотентное суточное задание, чтобы
одну и ту же погоду не начислить повторно.
