"""
Клавиатуры и кнопки для модуля управления полями на aiogram 3.x.
Использует типизированные FieldCallback и InlineKeyboardBuilder.
"""
from __future__ import annotations

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.schemas.field import CropType, FieldResponse, IrrigationMethod, IrrigationStatus
from bot.states.field_states import FieldCallback


def get_fields_list_keyboard(fields: List[FieldResponse]) -> InlineKeyboardMarkup:
    """Генерирует список полей со статусными маркерами и кнопкой добавления."""
    builder = InlineKeyboardBuilder()

    status_badges = {
        IrrigationStatus.NORMAL: "🟢",
        IrrigationStatus.IRRIGATE: "🟡",
        IrrigationStatus.CRITICAL: "🔴",
        IrrigationStatus.RICE: "💧",
    }

    for f in fields[:25]:
        badge = status_badges.get(f.current_status, "🟢")
        label = f"{badge} {f.name} ({f.crop_type.value}, {f.area_ha:.1f} га)"
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=FieldCallback(action="view", field_id=f.id).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить новое поле",
            callback_data=FieldCallback(action="add", field_id=0).pack(),
        )
    )
    return builder.as_markup()


def get_field_card_keyboard(field_id: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки выбранного поля: удобная сетка 2х2 + возврат."""
    builder = InlineKeyboardBuilder()
    # 1 ряд: оперативные действия
    builder.row(
        InlineKeyboardButton(
            text="💧 Отметить полив",
            callback_data=FieldCallback(action="water", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text="🔄 Обновить статус",
            callback_data=FieldCallback(action="update", field_id=field_id).pack(),
        ),
    )
    # 2 ряд: отчет и удаление
    builder.row(
        InlineKeyboardButton(
            text="📄 Экспорт CSV",
            callback_data=FieldCallback(action="export", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Удалить поле",
            callback_data=FieldCallback(action="delete", field_id=field_id).pack(),
        ),
    )
    # 3 ряд: навигация
    builder.row(
        InlineKeyboardButton(
            text="🔙 К списку полей",
            callback_data=FieldCallback(action="list", field_id=0).pack(),
        )
    )
    return builder.as_markup()


def get_crop_selection_keyboard() -> InlineKeyboardMarkup:
    """Выбор культуры для нового поля."""
    builder = InlineKeyboardBuilder()
    crops = [
        ("🌾 Пшеница", CropType.WHEAT),
        ("🌽 Кукуруза", CropType.CORN),
        ("🍅 Томаты", CropType.TOMATO),
        ("🥔 Картофель", CropType.POTATO),
        ("🍈 Бахчевые (Дыня)", CropType.MELON),
        ("🌿 Люцерна", CropType.ALFALFA),
        ("☁️ Хлопчатник", CropType.COTTON),
        ("🌱 Другая культура", CropType.OTHER),
    ]
    for label, crop in crops:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"f_crop:{crop.value}",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=FieldCallback(action="list", field_id=0).pack(),
        )
    )
    return builder.as_markup()


def get_irrigation_selection_keyboard() -> InlineKeyboardMarkup:
    """Выбор метода полива для нового поля."""
    builder = InlineKeyboardBuilder()
    methods = [
        ("💧 Капельный (КПД 90%)", IrrigationMethod.DRIP),
        ("🌱 Подземный капельный (КПД 90%)", IrrigationMethod.SUBSURFACE),
        ("🚿 Дождевание (КПД 75%)", IrrigationMethod.SPRINKLER),
        ("⭕ Круговой пивот (КПД 75%)", IrrigationMethod.PIVOT),
        ("🌊 Арычный / по бороздам (КПД 50%)", IrrigationMethod.FURROW),
    ]
    for label, method in methods:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"f_irrig:{method.value}",
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=FieldCallback(action="list", field_id=0).pack(),
        )
    )
    return builder.as_markup()


def get_water_confirmation_keyboard(field_id: int) -> InlineKeyboardMarkup:
    """Подтверждение полива поля."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, полив выполнен",
            callback_data=FieldCallback(action="confirm_water", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=FieldCallback(action="view", field_id=field_id).pack(),
        ),
    )
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены активного FSM-состояния."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=FieldCallback(action="list", field_id=0).pack(),
        )
    )
    return builder.as_markup()
