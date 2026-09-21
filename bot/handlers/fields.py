"""
Модуль Telegram-хэндлеров управления полями (aiogram 3.x).
Реализует Clean Architecture:
- Тонкие хэндлеры (только прием событий и валидация).
- Бизнес-логика вынесена в FieldService и FieldExportService.
- Изолированный FSM (FieldForm) со строгой очисткой состояния (ликвидация нейролупов).
- Гарантированное округление всех чисел до 2 знаков и дефолт Атырау (Asia/Atyrau).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.fields_kb import (
    get_cancel_keyboard,
    get_crop_selection_keyboard,
    get_field_card_keyboard,
    get_fields_list_keyboard,
    get_irrigation_selection_keyboard,
    get_water_confirmation_keyboard,
)
from bot.schemas.field import (
    CropType,
    FieldCreate,
    FieldResponse,
    IrrigationMethod,
    IrrigationStatus,
    SoilType,
)
from bot.services.export_service import FieldExportService
from bot.services.field_manager import FieldService
from bot.services.geo_service import (
    DEFAULT_FALLBACK_LAT,
    DEFAULT_FALLBACK_LON,
    get_field_location_name,
    resolve_timezone_by_coords,
)
from bot.states.field_states import FieldCallback, FieldForm

logger = logging.getLogger(__name__)
fields_router = Router(name="fields_router")


# ─── Вспомогательные функции форматирования ──────────────────────────────────
def _render_field_card(field: FieldResponse, locality_name: Optional[str] = None) -> str:
    """Генерирует аккуратную карточку агрономического состояния поля."""
    status_text = {
        IrrigationStatus.NORMAL: "🟢 В норме (полив не требуется)",
        IrrigationStatus.IRRIGATE: "🟡 Требуется полив!",
        IrrigationStatus.CRITICAL: "🔴 КРИТИЧЕСКИЙ ДЕФИЦИТ (Стресс)",
        IrrigationStatus.RICE: "💧 Режим затопления рисового чека",
    }.get(field.current_status, "🟢 В норме")

    if locality_name:
        loc_str = f"{locality_name} ({field.latitude:.4f}° N, {field.longitude:.4f}° E)"
    else:
        loc_str = f"{field.latitude:.4f}° N, {field.longitude:.4f}° E"

    return (
        f"🌱 <b>Карточка поля: {field.name}</b>\n"
        f"───────────────────────────\n"
        f"🌾 <b>Культура:</b> {field.crop_type.value.capitalize()}\n"
        f"📐 <b>Площадь:</b> {field.area_ha:.2f} га\n"
        f"💧 <b>Метод полива:</b> {field.irrigation_method.value}\n"
        f"📍 <b>Локация:</b> {loc_str}\n"
        f"🕒 <b>Таймзона:</b> {field.timezone}\n"
        f"───────────────────────────\n"
        f"📊 <b>Водный баланс (FAO-56 Penman-Monteith):</b>\n"
        f"• Накопленный дефицит: <b>{field.accumulated_deficit_mm:.2f} мм</b>\n"
        f"• Статус полива: <b>{status_text}</b>\n"
        f"• Рекомендуемый объем: <b>{field.recommended_volume_m3:.2f} м³</b>\n"
    )


# ─── 1. Точка входа в меню «Мои поля» (Сброс FSM) ─────────────────────────────
@fields_router.message(Command("fields"))
@fields_router.message(F.text.in_({"🌱 Мои поля", "🌱 Менің алқаптарым"}))
async def show_fields_menu(message: Message, state: FSMContext) -> None:
    """
    Главное меню полей.
    Всегда сбрасывает активный FSM-контекст для исключения зацикливания состояний.
    """
    await state.clear()
    fields = await FieldService.get_user_fields(message.from_user.id)

    if not fields:
        await message.answer(
            "🌱 <b>У вас пока нет сохраненных полей.</b>\n\n"
            "Вы можете добавить свое первое поле прямо сейчас по GPS координатам:",
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard([]),
        )
        return

    await message.answer(
        "🌱 <b>Ваши поля (Мониторинг FAO-56):</b>\n\n"
        "Выберите поле для просмотра подробной карточки или добавьте новое:",
        parse_mode="HTML",
        reply_markup=get_fields_list_keyboard(fields),
    )


# ─── 2. Навигация по списку полей (Callback) ──────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "list"))
@fields_router.callback_query(F.data == "fields:list")
async def callback_show_list(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат к списку полей."""
    await state.clear()
    fields = await FieldService.get_user_fields(callback.from_user.id)
    text = (
        "🌱 <b>Ваши поля:</b>\n"
        "Выберите участок для просмотра детальной агрономической сводки:"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard(fields),
        )
    await callback.answer()


# ─── 3. Карточка поля (Просмотр) ──────────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "view"))
async def callback_view_field(callback: CallbackQuery, callback_data: FieldCallback, state: FSMContext) -> None:
    """Отображение карточки конкретного поля."""
    await state.clear()
    field = await FieldService.get_field_by_id(callback_data.field_id, callback.from_user.id)
    if not field:
        await callback.answer("Поле не найдено", show_alert=True)
        return

    locality = await get_field_location_name(float(field.latitude), float(field.longitude))
    card_text = _render_field_card(field, locality_name=locality)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(field.id),
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
        await callback.answer("Неверный ID поля", show_alert=True)
        return

    await callback.answer("Запрос свежих данных Open-Meteo...")
    try:
        updated_field, _ = await FieldService.update_balance_today(field_id, callback.from_user.id)
    except Exception as exc:
        logger.exception("Ошибка обновления поля %s: %s", field_id, exc)
        await callback.answer("Ошибка связи с метеосервисом", show_alert=True)
        return

    locality = await get_field_location_name(float(updated_field.latitude), float(updated_field.longitude))
    card_text = _render_field_card(updated_field, locality_name=locality)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(updated_field.id),
        )
    await callback.answer("Данные успешно обновлены ✅")


# ─── 5. Полив: запрос подтверждения и фиксация факта ──────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "water"))
@fields_router.callback_query(F.data.startswith("field:watered:"))
async def callback_ask_water(callback: CallbackQuery, state: FSMContext) -> None:
    """Запрос подтверждения полива."""
    await state.clear()
    try:
        field_id = int(str(callback.data).rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Неверный ID поля", show_alert=True)
        return

    field = await FieldService.get_field_by_id(field_id, callback.from_user.id)
    if not field:
        await callback.answer("Поле не найдено", show_alert=True)
        return

    text = (
        f"💧 <b>Подтверждение полива</b>\n\n"
        f"Поле: <b>{field.name}</b>\n"
        f"Текущий дефицит: <b>{field.accumulated_deficit_mm:.2f} мм</b>\n"
        f"Рекомендуемый объем: <b>{field.recommended_volume_m3:.2f} м³</b>\n\n"
        f"Отметить, что полив выполнен в полном объеме?"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_water_confirmation_keyboard(field.id),
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
        await callback.answer("Неверный ID поля", show_alert=True)
        return

    try:
        updated_field = await FieldService.record_irrigation_fact(field_id, callback.from_user.id)
    except Exception as exc:
        logger.exception("Не удалось зафиксировать полив для поля %s: %s", field_id, exc)
        await callback.answer("Ошибка при сохранении полива", show_alert=True)
        return

    card_text = _render_field_card(updated_field)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=get_field_card_keyboard(updated_field.id),
        )
    await callback.answer("Полив успешно зафиксирован! Дефицит обнулен ✅", show_alert=True)


# ─── 6. Чистый экспорт журнала в CSV ─────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "export"))
@fields_router.callback_query(F.data.startswith("field:export:"))
async def callback_export_csv(callback: CallbackQuery, state: FSMContext) -> None:
    """Генерация и отправка чистого CSV-журнала с округлением до 2 знаков."""
    await state.clear()
    try:
        field_id = int(str(callback.data).rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Неверный ID поля", show_alert=True)
        return

    field = await FieldService.get_field_by_id(field_id, callback.from_user.id)
    if not field:
        await callback.answer("Поле не найдено", show_alert=True)
        return

    await callback.answer("Генерация отчета...")
    records = await FieldService.get_journal_records(field.id, callback.from_user.id)
    if not records:
        await callback.answer("История поливов и расчетов пуста", show_alert=True)
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
        f"📄 <b>Агрономический журнал поля: {field.name}</b>\n"
        f"• Координаты (GPS): {field.latitude:.4f}° N, {field.longitude:.4f}° E\n"
        f"• Локация: {locality}\n"
        f"• Таймзона: {field.timezone}\n"
        f"• Округление: строго 2 знака (.round(2))\n"
        f"• Кодировка: UTF-8-BOM (для корректного открытия в Excel)"
    )
    if isinstance(callback.message, Message):
        await callback.message.answer_document(document, caption=caption, parse_mode="HTML")


# ─── 7. Удаление поля ────────────────────────────────────────────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "delete"))
async def callback_delete_field(callback: CallbackQuery, callback_data: FieldCallback, state: FSMContext) -> None:
    """Удаление поля."""
    await state.clear()
    success = await FieldService.delete_field(callback_data.field_id, callback.from_user.id)
    if success:
        await callback.answer("Поле удалено ✅", show_alert=True)
    else:
        await callback.answer("Поле не найдено", show_alert=True)

    fields = await FieldService.get_user_fields(callback.from_user.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text="🌱 <b>Ваши поля:</b>",
            parse_mode="HTML",
            reply_markup=get_fields_list_keyboard(fields),
        )


# ─── 8. FSM: Пошаговое добавление нового поля (Без нейролупов) ────────────────
@fields_router.callback_query(FieldCallback.filter(F.action == "add"))
async def callback_add_field_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 1: Ввод названия поля."""
    await state.set_state(FieldForm.name)
    text = (
        "📝 <b>Шаг 1 из 3: Введите название поля</b>\n\n"
        "Например: <i>Участок возле реки Урал</i> или <i>Поле №2</i>:"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(),
        )
    await callback.answer()


@fields_router.message(StateFilter(FieldForm.name), F.text)
async def process_form_name(message: Message, state: FSMContext) -> None:
    """Обработка названия и переход к шагу 2."""
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 60:
        await message.answer("⚠️ Название должно быть от 2 до 60 символов. Попробуйте еще раз:")
        return

    await state.update_data(name=name)
    await state.set_state(FieldForm.crop)
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "🌾 <b>Шаг 2 из 3: Выберите сельскохозяйственную культуру</b>:",
        parse_mode="HTML",
        reply_markup=get_crop_selection_keyboard(),
    )


@fields_router.callback_query(StateFilter(FieldForm.crop), F.data.startswith("f_crop:"))
async def process_form_crop(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка культуры и переход к шагу 3."""
    crop_val = callback.data.split(":", 1)[1]
    await state.update_data(crop=crop_val)
    await state.set_state(FieldForm.area)

    text = (
        f"🌾 Культура выбрана: <b>{crop_val.capitalize()}</b>\n\n"
        "📐 <b>Шаг 3 из 3: Введите площадь поля в гектарах (га)</b>\n"
        "Например: <code>12.5</code> или <code>25</code>:"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(),
        )
    await callback.answer()


@fields_router.message(StateFilter(FieldForm.area), F.text)
async def process_form_area(message: Message, state: FSMContext) -> None:
    """Валидация площади, сохранение поля и завершение FSM."""
    raw = (message.text or "").replace(",", ".").strip()
    try:
        area_num = Decimal(raw)
        if area_num <= 0 or area_num > 50000:
            raise ValueError
        area_num = area_num.quantize(Decimal("0.01"))
    except Exception:
        await message.answer("⚠️ Введите корректную площадь числом от 0.01 до 50 000 га:")
        return

    data = await state.get_data()
    # Строгий сброс FSM: исключает залипание состояния
    await state.clear()

    lat_def = DEFAULT_FALLBACK_LAT
    lon_def = DEFAULT_FALLBACK_LON
    tz_def = resolve_timezone_by_coords(lat_def, lon_def)

    field_create = FieldCreate(
        name=data.get("name") or "Новое поле",
        crop_type=CropType(data.get("crop") or "tomato"),
        area_ha=area_num,
        irrigation_method=IrrigationMethod.DRIP,
        soil_type=SoilType.LOAM,
        latitude=Decimal(str(lat_def)),
        longitude=Decimal(str(lon_def)),
        timezone=tz_def,
    )

    try:
        field_id = await FieldService.create_field(message.from_user.id, field_create)
    except Exception as exc:
        logger.exception("Ошибка создания поля: %s", exc)
        await message.answer("❌ Произошла ошибка при сохранении поля. Попробуйте позже.")
        return

    fields = await FieldService.get_user_fields(message.from_user.id)
    await message.answer(
        f"🎉 <b>Поле «{field_create.name}» успешно создано!</b>\n\n"
        f"• Культура: <b>{field_create.crop_type.value.capitalize()}</b>\n"
        f"• Площадь: <b>{field_create.area_ha:.2f} га</b>\n"
        f"• Метод полива: <b>{field_create.irrigation_method.value}</b>\n"
        f"• GPS координаты: <b>{field_create.latitude:.4f}° N, {field_create.longitude:.4f}° E</b>\n"
        f"• Таймзона: <b>{field_create.timezone}</b>\n\n"
        f"Мониторинг водного баланса активирован.",
        parse_mode="HTML",
        reply_markup=get_fields_list_keyboard(fields),
    )
