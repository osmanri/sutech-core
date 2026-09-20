# Состояние полей Su-Tech

`bot/field_state.py` хранит поля, накопленный дефицит, дневной журнал и события
фактического полива в той же SQLite-базе, которую инициализирует `bot.main`.
После первого расчёта WebApp поле сохраняется автоматически. Раздел «Мои поля»
позволяет обновить баланс, подтвердить полив и выгрузить журнал CSV.

`bot/daily_monitor.py` проверяет сохранённые поля каждые 30 минут. Уникальная
пара `(field_id, balance_date)` гарантирует, что ETc и осадки одной даты не будут
начислены повторно после рестарта или повторного нажатия. Уведомление отправляется
только для нового решения `irrigate` или `critical`.

Open-Meteo остаётся источником погоды. Это объяснимая алгоритмическая система,
а не модель машинного обучения.

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

# Низкоуровневое создание поля после заполнения WebApp/FSM.
field_id = await asyncio.to_thread(
    add_new_field,
    telegram_user_id,
    "potato",
    "loam",
    "drip",
    date(2026, 4, 15),       # аргумент можно опустить: будет сегодня
)

# Обновление после получения погоды из уже подключённого Open-Meteo.
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

`update_daily_deficit` оставлен как низкоуровневая атомарная операция. Рабочий
маршрут использует `save_daily_balance`, где дата, входы погоды, результат и
новый дефицит сохраняются одной транзакцией.

В production `DB_PATH` должен указывать на постоянный том. Файловая система
обычного контейнера Render может очищаться при новом деплое; без постоянного
тома журнал и поля нельзя считать долговременным хранилищем.
