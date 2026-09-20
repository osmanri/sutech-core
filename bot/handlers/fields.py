"""Telegram controls for persistent field balances and irrigation events."""

import asyncio
import csv
import io
import logging
from datetime import datetime

import aiohttp
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

try:
    from balance_report import economics, fmt, format_balance_explanation, format_balance_report
    from db import save_calculation, save_report_explanation
    from field_service import calculate_saved_field
    from field_state import (FieldNotFoundError, FieldStateError, list_daily_balances,
                             list_irrigation_events, list_user_fields, record_irrigation)
    from i18n import t
    from keyboards.inline import (
        get_fields_keyboard,
        get_irrigation_confirmation_keyboard,
        get_report_inline_keyboard,
    )
    from user_state import get_lang
    from water_balance import BalanceInputError
except ImportError:
    from bot.balance_report import economics, fmt, format_balance_explanation, format_balance_report
    from bot.db import save_calculation, save_report_explanation
    from bot.field_service import calculate_saved_field
    from bot.field_state import (FieldNotFoundError, FieldStateError, list_daily_balances,
                                 list_irrigation_events, list_user_fields, record_irrigation)
    from bot.i18n import t
    from bot.keyboards.inline import (
        get_fields_keyboard,
        get_irrigation_confirmation_keyboard,
        get_report_inline_keyboard,
    )
    from bot.user_state import get_lang
    from bot.water_balance import BalanceInputError


fields_router = Router()
logger = logging.getLogger(__name__)


async def _send_fields(target: Message, user_id: int, lang: str) -> None:
    fields = [field for field in await asyncio.to_thread(list_user_fields, user_id)
              if field.get("field_key") and field.get("latitude") is not None
              and field.get("longitude") is not None and field.get("area_ha")]
    if not fields:
        await target.answer(t(lang, "fields_empty"))
        return
    await target.answer(t(lang, "fields_title"), parse_mode="HTML",
                        reply_markup=get_fields_keyboard(lang, fields))


@fields_router.message(Command("fields"))
@fields_router.message(F.text.in_({"🌱 Мои поля", "🌱 Менің алқаптарым"}))
async def show_fields(message: Message) -> None:
    await _send_fields(message, message.from_user.id, get_lang(message.from_user.id))


@fields_router.callback_query(F.data == "fields:list")
async def show_fields_callback(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await _send_fields(callback.message, callback.from_user.id, lang)


def _callback_field_id(callback: CallbackQuery) -> int:
    return int(callback.data.rsplit(":", 1)[1])


@fields_router.callback_query(F.data.startswith("field:update:"))
async def update_field_today(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.id)
    if not isinstance(callback.message, Message):
        await callback.answer(t(lang, "field_update_error"), show_alert=True)
        return
    try:
        field_id = _callback_field_id(callback)
        field, result, weather, created = await calculate_saved_field(field_id, callback.from_user.id)
    except FieldNotFoundError:
        await callback.answer(t(lang, "field_not_found"), show_alert=True)
        return
    except (ValueError, FieldStateError, BalanceInputError, aiohttp.ClientError,
            asyncio.TimeoutError, OSError, KeyError, TypeError):
        logger.exception("Could not update saved field")
        await callback.answer(t(lang, "field_update_error"), show_alert=True)
        return

    explanation = format_balance_explanation(lang, field, result, weather)
    report_id = save_report_explanation(callback.from_user.id, explanation)
    save_calculation(
        user_id=callback.from_user.id,
        crop_name=t(lang, f"report_crop_{field.crop}"),
        area_text=f"{fmt(field.area_ha)} га",
        irrigation_text=t(lang, f"report_irrig_{field.method}"),
        volume_text=f"{fmt(result['gross_m3'])} м³ · {t(lang, 'balance_status_' + result['status'])}",
        savings_text=economics(lang, field, result), lang=lang,
        created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
    )
    await callback.answer(t(lang, "field_updated" if created else "field_already_updated"))
    await callback.message.answer(
        format_balance_report(lang, field, result, weather), parse_mode="HTML",
        reply_markup=get_report_inline_keyboard(lang, report_id, field_id),
    )


@fields_router.callback_query(F.data.startswith("field:watered:"))
async def ask_watered_confirmation(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.id)
    try:
        field_id = _callback_field_id(callback)
    except ValueError:
        await callback.answer(t(lang, "field_not_found"), show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t(lang, "field_watered_confirm"),
            reply_markup=get_irrigation_confirmation_keyboard(lang, field_id),
        )


@fields_router.callback_query(F.data == "field:cancel-watered")
async def cancel_watered(callback: CallbackQuery) -> None:
    await callback.answer(t(get_lang(callback.from_user.id), "btn_cancel"))
    if isinstance(callback.message, Message):
        try:
            await callback.message.delete()
        except Exception:
            pass


@fields_router.callback_query(F.data.startswith("field:confirm-watered:"))
async def confirm_watered(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.id)
    try:
        event = await asyncio.to_thread(
            record_irrigation, _callback_field_id(callback), user_id=callback.from_user.id
        )
    except (ValueError, FieldNotFoundError, FieldStateError):
        await callback.answer(t(lang, "field_not_found"), show_alert=True)
        return
    await callback.answer(t(lang, "field_watered", deficit=fmt(event["deficit_after"])),
                          show_alert=True)
    if isinstance(callback.message, Message):
        try:
            await callback.message.delete()
        except Exception:
            pass


@fields_router.callback_query(F.data.startswith("field:export:"))
async def export_field_journal(callback: CallbackQuery) -> None:
    lang = get_lang(callback.from_user.id)
    try:
        field_id = _callback_field_id(callback)
        rows = await asyncio.to_thread(
            list_daily_balances, field_id, user_id=callback.from_user.id, limit=366
        )
        irrigation_events = await asyncio.to_thread(
            list_irrigation_events, field_id, user_id=callback.from_user.id, limit=366
        )
    except (ValueError, FieldNotFoundError, FieldStateError):
        await callback.answer(t(lang, "field_not_found"), show_alert=True)
        return
    if not rows:
        await callback.answer(t(lang, "field_export_empty"), show_alert=True)
        return
    stream = io.StringIO(newline="")
    columns = ["record_type", "timestamp", "date", "timezone", "et0_mm", "rain_mm", "effective_rain_mm", "etc_mm",
               "deficit_before_mm", "deficit_after_mm", "status", "net_m3", "gross_m3",
               "applied_m3", "source", "calculation_version"]
    writer = csv.writer(stream)
    writer.writerow(columns)
    for row in reversed(rows):
        writer.writerow([
            "balance", row["created_at"], row["balance_date"], row["timezone"], row["et0"], row["rain"],
            row["effective_rain"], row["etc"], row["deficit_before"],
            row["deficit_after"], row["status"], row["net_m3"], row["gross_m3"],
            "", "", row["calculation_version"],
        ])
    for event in reversed(irrigation_events):
        writer.writerow([
            "irrigation", event["created_at"], "", "", "", "", "", "",
            event["deficit_before"], event["deficit_after"], "", "", "",
            "" if event["applied_m3"] is None else event["applied_m3"],
            event["source"], "",
        ])
    document = BufferedInputFile(stream.getvalue().encode("utf-8-sig"),
                                 filename=f"su-tech-field-{field_id}.csv")
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer_document(document, caption=t(lang, "field_export_caption"))
