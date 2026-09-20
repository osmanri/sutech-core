"""Idempotent periodic updater for saved fields."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

try:
    from balance_report import format_balance_explanation, format_balance_report
    from db import get_user_language, save_report_explanation
    from field_service import calculate_saved_field
    from field_state import list_managed_fields
    from i18n import t
    from keyboards.inline import get_report_inline_keyboard
    from water_balance import BalanceInputError
except ImportError:
    from bot.balance_report import format_balance_explanation, format_balance_report
    from bot.db import get_user_language, save_report_explanation
    from bot.field_service import calculate_saved_field
    from bot.field_state import list_managed_fields
    from bot.i18n import t
    from bot.keyboards.inline import get_report_inline_keyboard
    from bot.water_balance import BalanceInputError


logger = logging.getLogger(__name__)


async def update_all_fields_once(bot: Bot) -> dict[str, int]:
    """Update every saved field once; notify only newly critical/irrigate fields."""
    counters = {"seen": 0, "updated": 0, "notified": 0, "failed": 0}
    fields = await asyncio.to_thread(list_managed_fields)
    for record in fields:
        counters["seen"] += 1
        try:
            field, result, weather, created = await calculate_saved_field(
                int(record["id"]), int(record["user_id"])
            )
            if not created:
                continue
            counters["updated"] += 1
            if result["status"] not in {"irrigate", "critical"}:
                continue
            lang = get_user_language(int(record["user_id"])) or "ru"
            explanation = format_balance_explanation(lang, field, result, weather)
            report_id = save_report_explanation(int(record["user_id"]), explanation)
            report = format_balance_report(lang, field, result, weather)
            await bot.send_message(
                int(record["user_id"]), t(lang, "daily_field_alert", report=report),
                parse_mode="HTML",
                reply_markup=get_report_inline_keyboard(lang, report_id, int(record["id"])),
            )
            counters["notified"] += 1
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
