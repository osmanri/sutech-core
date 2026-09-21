"""
FSM-состояния и типизированные Callback-классы для aiogram 3.x.
Изолирует навигацию по полям, исключая перехват глобальных команд и зацикливание состояний.
"""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup


class FieldCallback(CallbackData, prefix="field"):
    """
    Типизированный callback для работы со списком и карточками полей.
    action:
      - 'list': список всех полей пользователя
      - 'view': карточка конкретного поля
      - 'water': запрос подтверждения полива
      - 'confirm_water': подтверждение факта полива
      - 'update': пересчет текущего суточного баланса
      - 'export': выгрузка чистого CSV-журнала
      - 'add': старт FSM создания нового поля
      - 'delete': удаление поля
    """
    action: str
    field_id: int = 0


class FieldForm(StatesGroup):
    """Строгие шаги FSM для добавления нового поля."""
    name = State()       # Ввод названия поля
    crop = State()       # Выбор культуры
    area = State()       # Ввод площади (га)
    irrigation = State() # Выбор способа полива
    confirm = State()    # Подтверждение параметров
