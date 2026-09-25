"""
Клавиатуры и кнопки для модуля управления полями на aiogram 3.x.
Использует типизированные FieldCallback и InlineKeyboardBuilder.
"""
from __future__ import annotations

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.schemas.field import CropType, FieldResponse, IrrigationMethod, IrrigationStatus
from bot.states.field_states import FieldCallback
from bot.config import WEBAPP_URL
from bot.i18n import t


def _label(lang: str, ru: str, kz: str, en: str) -> str:
    return {"ru": ru, "kz": kz, "en": en}.get(lang, ru)


def get_fields_list_keyboard(fields: List[FieldResponse], lang: str = "ru") -> InlineKeyboardMarkup:
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
        label = f"{badge} {f.name} ({t(lang, f'report_crop_{f.crop_type.value}')}, {f.area_ha.normalize():f} {'ha' if lang == 'en' else 'га'})"
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=FieldCallback(action="view", field_id=f.id).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "➕ Добавить новое поле", "➕ Жаңа алқап қосу", "➕ Add field"),
            web_app=WebAppInfo(url=f"{WEBAPP_URL}{'&' if '?' in WEBAPP_URL else '?'}lang={lang}"),
        )
    )
    return builder.as_markup()


def get_field_card_keyboard(field_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Клавиатура карточки выбранного поля: удобная сетка 2х2 + возврат."""
    builder = InlineKeyboardBuilder()
    # 1 ряд: оперативные действия
    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "💧 Отметить полив", "💧 Суаруды белгілеу", "💧 Record irrigation"),
            callback_data=FieldCallback(action="water", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text=_label(lang, "🔄 Обновить статус", "🔄 Мәртебені жаңарту", "🔄 Refresh status"),
            callback_data=FieldCallback(action="update", field_id=field_id).pack(),
        ),
    )
    # 2 ряд: отчет и удаление
    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "📄 Экспорт CSV", "📄 CSV жүктеу", "📄 Export CSV"),
            callback_data=FieldCallback(action="export", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text=_label(lang, "❌ Удалить поле", "❌ Алқапты жою", "❌ Delete field"),
            callback_data=FieldCallback(action="delete", field_id=field_id).pack(),
        ),
    )
    # 3 ряд: навигация
    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "🔙 К списку полей", "🔙 Алқаптар тізімі", "🔙 Field list"),
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


def get_water_confirmation_keyboard(field_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Подтверждение полива поля."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "✅ Да, полив выполнен", "✅ Иә, толық суарылды", "✅ Yes, fully irrigated"),
            callback_data=FieldCallback(action="confirm_water", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text=_label(lang, "❌ Отмена", "❌ Бас тарту", "❌ Cancel"),
            callback_data=FieldCallback(action="view", field_id=field_id).pack(),
        ),
    )
    return builder.as_markup()


def get_field_delete_confirmation_keyboard(field_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Require an explicit second tap before deleting a field and its journal."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_label(lang, "Да, удалить поле и журнал", "Иә, алқап пен журналды жою", "Delete field and log"),
            callback_data=FieldCallback(action="delete_confirm", field_id=field_id).pack(),
        ),
        InlineKeyboardButton(
            text=_label(lang, "Отмена", "Бас тарту", "Cancel"),
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
