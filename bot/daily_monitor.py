"""Idempotent periodic updater for saved fields."""

import asyncio
import logging
from dataclasses import replace
from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

try:
    from balance_report import format_balance_explanation, format_balance_report
    from db import get_user_language, save_report_explanation
    from field_service import calculate_saved_field, field_input_from_record
    from field_state import (claim_pending_alert, finish_pending_alert,
                             list_managed_fields, list_pending_alerts)
    from i18n import t
    from keyboards.inline import get_report_inline_keyboard
    from water_balance import BalanceInputError
except ImportError:
    from bot.balance_report import format_balance_explanation, format_balance_report
    from bot.db import get_user_language, save_report_explanation
    from bot.field_service import calculate_saved_field, field_input_from_record
    from bot.field_state import (claim_pending_alert, finish_pending_alert,
                                 list_managed_fields, list_pending_alerts)
    from bot.i18n import t
    from bot.keyboards.inline import get_report_inline_keyboard
    from bot.water_balance import BalanceInputError


logger = logging.getLogger(__name__)


async def _send_pending_alerts(bot: Bot, record: dict, counters: dict[str, int]) -> None:
    """Retry saved alerts without recalculating a past day's water balance."""
    field_id, user_id = int(record["id"]), int(record["user_id"])
    rows = await asyncio.to_thread(list_pending_alerts, field_id, user_id=user_id)
    for row in rows:
        claimed = await asyncio.to_thread(claim_pending_alert, int(row["id"]),
                                          field_id=field_id, user_id=user_id)
        if not claimed:
            continue
        sent = False
        try:
            field = await asyncio.to_thread(field_input_from_record, record,
                                            on_date=date.fromisoformat(row["balance_date"]))
            field = replace(field, yesterday=float(row["deficit_before"]))
            result = row["result"]
            weather = {"date": row["balance_date"], "timezone": row["timezone"],
                       "et0": row["et0"], "rain": row["rain"]}
            lang = get_user_language(user_id) or "ru"
            explanation = format_balance_explanation(lang, field, result, weather)
            report_id = save_report_explanation(user_id, explanation)
            report = format_balance_report(lang, field, result, weather)
            await bot.send_message(user_id, t(lang, "daily_field_alert", report=report),
                                   parse_mode="HTML",
                                   reply_markup=get_report_inline_keyboard(lang, report_id, field_id))
            sent = True
            counters["notified"] += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            counters["failed"] += 1
            logger.warning("Notification failed for user %s (field %s): %s",
                           user_id, field_id, exc, exc_info=True)
        finally:
            await asyncio.to_thread(finish_pending_alert, int(row["id"]), sent=sent)


async def update_all_fields_once(bot: Bot) -> dict[str, int]:
    """Update every saved field once; notify only newly critical/irrigate fields."""
    counters = {"seen": 0, "updated": 0, "notified": 0, "failed": 0}
    fields = await asyncio.to_thread(list_managed_fields)
    for record in fields:
        counters["seen"] += 1
        try:
            await _send_pending_alerts(bot, record, counters)
            _, _, _, created = await calculate_saved_field(
                int(record["id"]), int(record["user_id"])
            )
            if created:
                counters["updated"] += 1
                await _send_pending_alerts(bot, record, counters)
        except asyncio.CancelledError:
            raise
        except (TelegramAPIError, ConnectionError) as exc:
            counters["failed"] += 1
            logger.warning("Telegram notification failed for user %s (field %s): %s",
                           record.get("user_id"), record.get("id"), exc)
        except BalanceInputError as exc:
            if str(exc) == "season_ended":
                logger.info("Field %s reached end of season", record.get("id"))
            else:
                counters["failed"] += 1
                logger.warning("Field %s balance input error: %s", record.get("id"), exc)
        except Exception:
            counters["failed"] += 1
            logger.exception("Automatic field update failed for field_id=%s", record.get("id"))
    return counters


async def run_daily_monitor(bot: Bot, interval_seconds: int = 1800) -> None:
    """Run a lightweight loop; database uniqueness enforces once-per-local-date updates."""
    while True:
        stats = await update_all_fields_once(bot)
        logger.info("Daily field monitor: %s", stats)
        await asyncio.sleep(interval_seconds)
