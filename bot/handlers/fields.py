"""
Модуль Telegram-хэндлеров управления полями (aiogram 3.x).
Реализует Clean Architecture:
- Тонкие хэндлеры (только прием событий и валидация).
- Бизнес-логика вынесена в FieldService и FieldExportService.
- Старые кнопки добавления направляют в полную настройку поля на карте.
- Числа отчёта округляются до 2 знаков; координаты указывает сам фермер.
"""
from __future__ import annotations

import logging
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.fields_kb import (
    get_field_card_keyboard,
    get_field_delete_confirmation_keyboard,
    get_fields_list_keyboard,
    get_water_confirmation_keyboard,
)
from bot.schemas.field import (
    FieldResponse,
    IrrigationStatus,
)
from bot.services.export_service import FieldExportService
from bot.services.field_manager import FieldService
from bot.services.geo_service import get_field_location_name
from bot.states.field_states import FieldCallback
from bot.keyboards.inline import get_launch_keyboard
from bot.user_state import get_lang
from bot.i18n import t

logger = logging.getLogger(__name__)
fields_router = Router(name="fields_router")


def _phrase(lang: str, ru: str, kz: str, en: str) -> str:
    return {"ru": ru, "kz": kz, "en": en}.get(lang, ru)


# ─── Вспомогательные функции форматирования ──────────────────────────────────
def _render_field_card(field: FieldResponse, locality_name: Optional[str] = None,
                       lang: str = "ru") -> str:
    """Генерирует аккуратную карточку агрономического состояния поля."""
    status_text = {
        IrrigationStatus.NORMAL: ("🟢 В норме (полив не требуется)", "🟢 Қалыпты (суару қажет емес)", "🟢 Normal (no irrigation needed)"),
        IrrigationStatus.IRRIGATE: ("🟡 Требуется полив", "🟡 Суару қажет", "🟡 Irrigation needed"),
        IrrigationStatus.CRITICAL: ("🔴 Дефицит выше RAW: возможен стресс", "🔴 Тапшылық RAW-дан асты: күйзеліс қаупі", "🔴 Deficit above RAW: crop stress risk"),
        IrrigationStatus.RICE: ("💧 Режим затопления рисового чека", "💧 Күріш атызын суға толтыру режимі", "💧 Flooded rice plot"),
    }.get(field.current_status, ("🟢 В норме", "🟢 Қалыпты", "🟢 Normal"))[{"ru": 0, "kz": 1, "en": 2}.get(lang, 0)]
    if locality_name:
        loc_str = f"{escape(locality_name)} ({field.latitude:.4f}° N, {field.longitude:.4f}° E)"
    else:
        loc_str = f"{field.latitude:.4f}° N, {field.longitude:.4f}° E"

    return (
        f"🌱 <b>{_phrase(lang, 'Поле', 'Алқап', 'Field')}: {escape(field.name)}</b>\n"
        f"───────────────────────────\n"
        f"🌾 <b>{_phrase(lang, 'Культура', 'Дақыл', 'Crop')}:</b> {t(lang, f'report_crop_{field.crop_type.value}')}\n"
        f"📐 <b>{_phrase(lang, 'Площадь', 'Аудан', 'Area')}:</b> {field.area_ha:.2f} {'ha' if lang == 'en' else 'га'}\n"
        f"💧 <b>{_phrase(lang, 'Метод полива', 'Суару әдісі', 'Irrigation method')}:</b> {t(lang, f'report_irrig_{field.irrigation_method.value}')}\n"
        f"📍 <b>{_phrase(lang, 'Локация', 'Орны', 'Location')}:</b> {loc_str}\n"
        f"🕒 <b>{_phrase(lang, 'Часовой пояс', 'Уақыт белдеуі', 'Time zone')}:</b> {field.timezone}\n"
        f"───────────────────────────\n"
        f"📊 <b>{_phrase(lang, 'Водный баланс', 'Су балансы', 'Water balance')} (FAO-56):</b>\n"
        f"• {_phrase(lang, 'Накопленный дефицит', 'Жиналған тапшылық', 'Accumulated deficit')}: <b>{field.accumulated_deficit_mm:.2f} {'mm' if lang == 'en' else 'мм'}</b>\n"
        f"• {_phrase(lang, 'Статус полива', 'Суару мәртебесі', 'Irrigation status')}: <b>{status_text}</b>\n"
        f"• {_phrase(lang, 'Рекомендуемый объем', 'Ұсынылған көлем', 'Recommended volume')}: <b>{field.recommended_volume_m3:.2f} м³</b>\n"
    )


# ─── 1. Точка входа в меню «Мои поля» (Сброс FSM) ─────────────────────────────
@fields_router.message(Command("fields"))
@fields_router.message(F.text.in_({"🌱 Мои поля", "🌱 Менің алқаптарым", "🌱 My fields"}))
async def show_fields_menu(message: Message, state: FSMContext) -> None:
    """
    Главное меню полей.
    Всегда сбрасывает активный FSM-контекст для исключения зацикливания состояний.
    """
    await state.clear()
    fields = await FieldService.get_user_fields(message.from_user.id)
    lang = get_lang(message.from_user.id)

    if not fields:
        await message.answer(
            _phrase(lang, "🌱 <b>У вас пока нет сохранённых полей.</b>\n\nВыберите своё поле на карте:",
                    "🌱 <b>Сақталған алқаптар әлі жоқ.</b>\n\nКартадан алқабыңызды таңдаңыз:",
                    "🌱 <b>No saved fields yet.</b>\n\nSelect your field on the map:"),
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard([], lang),
        )
        return

    await message.answer(
        _phrase(lang, "🌱 <b>Ваши поля (FAO-56):</b>\n\nВыберите поле или добавьте новое:",
                "🌱 <b>Алқаптарыңыз (FAO-56):</b>\n\nАлқапты таңдаңыз немесе жаңасын қосыңыз:",
                "🌱 <b>Your fields (FAO-56):</b>\n\nChoose a field or add a new one:"),
        parse_mode="HTML",
        reply_markup=get_fields_list_keyboard(fields, lang),
    )


# ─── 2. Навигация по списку полей (Callback) ──────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "list"))
@fields_router.callback_query(F.data == "fields:list")
async def callback_show_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к списку полей."""
    await state.clear()
    fields = await FieldService.get_user_fields(callback.from_user.id)
    lang = get_lang(callback.from_user.id)
    text = _phrase(lang, "🌱 <b>Ваши поля:</b>\nВыберите участок для подробной сводки:",
                   "🌱 <b>Алқаптарыңыз:</b>\nТолық есеп үшін алқапты таңдаңыз:",
                   "🌱 <b>Your fields:</b>\nChoose a field for details:")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard(fields, lang),
        )
    await callback.answer()


# ─── 3. Карточка поля (Просмотр) ──────────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "view"))
async def callback_view_field(callback: CallbackQuery, callback_data: FieldCallback, state: FSMContext) -> None:
    """Отображение карточки конкретного поля."""
    await state.clear()
    field = await FieldService.get_field_by_id(callback_data.field_id, callback.from_user.id)
    if not field:
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Поле не найдено", "Алқап табылмады", "Field not found"), show_alert=True)
        return

    locality = await get_field_location_name(float(field.latitude), float(field.longitude))
    lang = get_lang(callback.from_user.id)
    card_text = _render_field_card(field, locality_name=locality, lang=lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(field.id, lang),
        )
    await callback.answer()


# ─── 4. Обновление статуса и пересчет FAO-56 ─────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "update"))
@fields_router.callback_query(F.data.startswith("field:update:"))
async def callback_update_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Принудительный пересчет водного баланса поля по суточной метеомодели."""
    await state.clear()
    try:
        if ":" in str(callback.data):
            field_id = int(str(callback.data).rsplit(":", 1)[1])
        else:
            field_id = 0
    except (ValueError, IndexError):
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Неверный ID поля", "Алқап нөмірі қате", "Invalid field ID"), show_alert=True)
        return

    lang = get_lang(callback.from_user.id)
    await callback.answer(_phrase(lang, "Запрос свежих данных Open-Meteo...", "Open-Meteo деректері сұралуда...", "Getting current Open-Meteo data..."))
    try:
        updated_field, _ = await FieldService.update_balance_today(field_id, callback.from_user.id)
    except Exception as exc:
        logger.exception("Ошибка обновления поля %s: %s", field_id, exc)
        if isinstance(callback.message, Message):
            await callback.message.answer(_phrase(lang, "⚠️ Не удалось обновить поле. Проверьте соединение и попробуйте позже.",
                                                   "⚠️ Алқап жаңартылмады. Байланысты тексеріп, кейін қайталаңыз.",
                                                   "⚠️ Could not update the field. Check your connection and try later."))
        return

    locality = await get_field_location_name(float(updated_field.latitude), float(updated_field.longitude))
    card_text = _render_field_card(updated_field, locality_name=locality, lang=lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(updated_field.id, lang),
        )


# ─── 5. Полив: запрос подтверждения и фиксация факта ──────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "water"))
@fields_router.callback_query(F.data.startswith("field:watered:"))
async def callback_ask_water(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос подтверждения полива."""
    await state.clear()
    try:
        field_id = int(str(callback.data).rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Неверный ID поля", "Алқап нөмірі қате", "Invalid field ID"), show_alert=True)
        return

    field = await FieldService.get_field_by_id(field_id, callback.from_user.id)
    if not field:
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Поле не найдено", "Алқап табылмады", "Field not found"), show_alert=True)
        return

    lang = get_lang(callback.from_user.id)
    if lang == "kz":
        text = (f"💧 <b>Суаруды растау</b>\n\nАлқап: <b>{escape(field.name)}</b>\n"
                f"Ағымдағы тапшылық: <b>{field.accumulated_deficit_mm:.2f} мм</b>\n"
                f"Ұсынылған көлем: <b>{field.recommended_volume_m3:.2f} м³</b>\n\n"
                "Толық көлемде суардыңыз ба? Бұл тапшылықты нөлге түсіреді.")
    elif lang == "en":
        text = (f"💧 <b>Confirm irrigation</b>\n\nField: <b>{escape(field.name)}</b>\n"
                f"Current deficit: <b>{field.accumulated_deficit_mm:.2f} mm</b>\n"
                f"Recommended volume: <b>{field.recommended_volume_m3:.2f} m³</b>\n\n"
                "Did you irrigate the full volume? This resets the saved deficit to zero.")
    else:
        text = (f"💧 <b>Подтверждение полива</b>\n\nПоле: <b>{escape(field.name)}</b>\n"
                f"Текущий дефицит: <b>{field.accumulated_deficit_mm:.2f} мм</b>\n"
                f"Рекомендуемый объём: <b>{field.recommended_volume_m3:.2f} м³</b>\n\n"
                "Поливали в полном объёме? Это обнулит накопленный дефицит.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_water_confirmation_keyboard(field.id, lang),
        )
    await callback.answer()


@fields_router.callback_query(FieldCallback.filter(F.action == "confirm_water"))
@fields_router.callback_query(F.data.startswith("field:confirm-watered:"))
async def callback_confirm_water(callback: CallbackQuery, state: FSMContext) -> None:
    """Фиксация полива и обнуление дефицита."""
    await state.clear()
    try:
        field_id = int(str(callback.data).rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Неверный ID поля", "Алқап нөмірі қате", "Invalid field ID"), show_alert=True)
        return

    try:
        updated_field = await FieldService.record_irrigation_fact(field_id, callback.from_user.id)
    except Exception as exc:
        logger.exception("Не удалось зафиксировать полив для поля %s: %s", field_id, exc)
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Ошибка при сохранении полива", "Суару сақталмады", "Could not save irrigation"), show_alert=True)
        return

    lang = get_lang(callback.from_user.id)
    card_text = _render_field_card(updated_field, lang=lang)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(updated_field.id, lang),
        )
    await callback.answer(_phrase(lang, "Полив записан. Дефицит обнулён ✅",
                                  "Суару тіркелді. Тапшылық нөлге түсті ✅",
                                  "Irrigation saved. Deficit reset to zero ✅"), show_alert=True)


# ─── 6. Чистый экспорт журнала в CSV ─────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "export"))
@fields_router.callback_query(F.data.startswith("field:export:"))
async def callback_export_csv(callback: CallbackQuery, state: FSMContext) -> None:
    """Генерация и отправка чистого CSV-журнала с округлением до 2 знаков."""
    await state.clear()
    try:
        field_id = int(str(callback.data).rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Неверный ID поля", "Алқап нөмірі қате", "Invalid field ID"), show_alert=True)
        return

    field = await FieldService.get_field_by_id(field_id, callback.from_user.id)
    if not field:
        await callback.answer(_phrase(get_lang(callback.from_user.id), "Поле не найдено", "Алқап табылмады", "Field not found"), show_alert=True)
        return

    lang = get_lang(callback.from_user.id)
    await callback.answer(_phrase(lang, "Генерация отчёта...", "Журнал дайындалуда...", "Preparing your log..."))
    records = await FieldService.get_journal_records(field.id, callback.from_user.id)
    if not records:
        if isinstance(callback.message, Message):
            await callback.message.answer(_phrase(lang, "История поливов и расчётов пока пуста.",
                                                   "Суару және есеп тарихы әзірге бос.",
                                                   "No irrigation or calculation records yet."))
        return

    locality = await get_field_location_name(float(field.latitude), float(field.longitude))
    document = FieldExportService.get_telegram_document(
        field.id,
        field.name,
        records,
        latitude=float(field.latitude),
        longitude=float(field.longitude),
        timezone_str=field.timezone,
        locality=locality,
    )
    caption = (
        f"📄 <b>{_phrase(lang, 'Журнал поля', 'Алқап журналы', 'Field log')}: {escape(field.name)}</b>\n"
        f"• GPS: {field.latitude:.4f}° N, {field.longitude:.4f}° E\n"
        f"• {_phrase(lang, 'Место', 'Орны', 'Location')}: {escape(locality)}\n"
        f"• {_phrase(lang, 'Часовой пояс', 'Уақыт белдеуі', 'Time zone')}: {field.timezone}\n"
        "• CSV · UTF-8-BOM"
    )
    if isinstance(callback.message, Message):
        await callback.message.answer_document(document, caption=caption, parse_mode="HTML")


# ─── 7. Удаление поля ────────────────────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "delete"))
async def callback_delete_field(callback: CallbackQuery, callback_data: FieldCallback, state: FSMContext) -> None:
    """Show what will be lost before deleting a field."""
    await state.clear()
    lang = get_lang(callback.from_user.id)
    field = await FieldService.get_field_by_id(callback_data.field_id, callback.from_user.id)
    if not field:
        await callback.answer(_phrase(lang, "Поле не найдено", "Алқап табылмады", "Field not found"), show_alert=True)
        return
    if isinstance(callback.message, Message):
        text = _phrase(lang, f"Поле «{escape(field.name)}» и весь его журнал будут удалены. Продолжить?",
                       f"Алқап «{escape(field.name)}» және оның журналы жойылады. Жалғастыру керек пе?",
                       f"Field “{escape(field.name)}” and its entire log will be deleted. Continue?")
        await callback.message.edit_text(text, parse_mode="HTML",
                                         reply_markup=get_field_delete_confirmation_keyboard(field.id, lang))
    await callback.answer()


@fields_router.callback_query(FieldCallback.filter(F.action == "delete_confirm"))
async def callback_confirm_delete_field(callback: CallbackQuery, callback_data: FieldCallback,
                                        state: FSMContext) -> None:
    """Delete only after the farmer confirms the irreversible action."""
    await state.clear()
    lang = get_lang(callback.from_user.id)
    success = await FieldService.delete_field(callback_data.field_id, callback.from_user.id)
    if success:
        await callback.answer(_phrase(lang, "Поле удалено ✅", "Алқап жойылды ✅", "Field deleted ✅"), show_alert=True)
    else:
        await callback.answer(_phrase(lang, "Поле не найдено", "Алқап табылмады", "Field not found"), show_alert=True)

    fields = await FieldService.get_user_fields(callback.from_user.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=_phrase(lang, "🌱 <b>Ваши поля:</b>", "🌱 <b>Алқаптарыңыз:</b>", "🌱 <b>Your fields:</b>"),
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard(fields, lang),
        )


# ─── 8. Совместимость со старыми кнопками добавления ────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "add"))
async def callback_add_field_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Older add buttons also open the full, GPS-based field setup."""
    await state.clear()
    lang = get_lang(callback.from_user.id)
    text = _phrase(lang,
                   "Выберите поле на карте и укажите почву и способ полива. Без этих данных расчет будет неточным.",
                   "Алқапты картадан таңдап, топырақ пен суару түрін көрсетіңіз. Бұларсыз есеп дұрыс болмайды.",
                   "Select your field on the map, then enter soil and irrigation method. These inputs affect the result.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            reply_markup=get_launch_keyboard(lang),
        )
    await callback.answer()
