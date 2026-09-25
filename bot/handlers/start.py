import html
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

try:
    from bot_setup import configure_user_menu
    from i18n import t
    from keyboards.inline import get_history_carousel_keyboard, get_lang_keyboard, get_launch_keyboard
    from keyboards.reply import get_main_reply_keyboard
    from user_state import get_lang, set_lang
    from db import get_user_history
except ImportError:
    from bot.bot_setup import configure_user_menu
    from bot.i18n import t
    from bot.keyboards.inline import get_history_carousel_keyboard, get_lang_keyboard, get_launch_keyboard
    from bot.keyboards.reply import get_main_reply_keyboard
    from bot.user_state import get_lang, set_lang
    from bot.db import get_user_history

start_router = Router()
logger = logging.getLogger(__name__)


# ─── /start ──────────────────────────────────────────────────────────────────
@start_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Обработчик /start — отправляет инлайн-клавиатуру выбора языка.
    Приветствие и постоянное Reply-меню придут после выбора языка.
    """
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "choose_lang"),
        reply_markup=get_lang_keyboard(),
    )


# ─── Смена и выбор языка (Callback) ──────────────────────────────────────────
@start_router.callback_query(F.data.startswith("lang:"))
async def lang_chosen(callback: CallbackQuery) -> None:
    """
    Обработчик выбора языка.
    Сохраняет язык, обновляет приветствие и отправляет постоянное Reply-меню
    на выбранном языке.
    """
    lang = callback.data.split(":")[1]  # "lang:kz" → "kz"
    if lang not in {"ru", "kz", "en"}:
        await callback.answer("Unsupported language", show_alert=True)
        return
    user_id = callback.from_user.id
    name = html.escape(callback.from_user.first_name or "Фермер")

    set_lang(user_id, lang)
    logger.info("Язык выбран | user_id=%s | lang=%s", user_id, lang)
    try:
        await configure_user_menu(callback.bot, user_id, lang)
    except Exception as exc:
        logger.warning("Не удалось обновить кнопку меню для user_id=%s: %s", user_id, exc)

    # Обновляем сообщение и Reply-клавиатуру без отправки отдельного спам-сообщения
    try:
        await callback.message.delete()
        await callback.message.answer(
            text=t(lang, "welcome", name=name),
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard(lang),
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=t(lang, "welcome", name=name),
                parse_mode="HTML",
            )
        except Exception:
            try:
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=t(lang, "welcome", name=name),
                    parse_mode="HTML",
                    reply_markup=get_main_reply_keyboard(lang),
                )
            except Exception:
                logger.exception("Could not deliver language welcome to user_id=%s", user_id)

    toast = {"kz": "Қазақ тілі таңдалды ✅", "en": "English selected ✅"}.get(lang, "Выбран русский язык ✅")
    await callback.answer(toast)


# ─── 📊 История расчетов (Карусель с инлайн-пагинацией) ───────────────────────
def format_history_card(rec: dict, lang: str, page: int, total: int) -> str:
    """Форматирует одну карточку замера для карусели истории."""
    return t(
        lang,
        "history_carousel_card",
        page=page,
        total=total,
        date=rec.get("date", "—"),
        crop_name=rec.get("crop_name", "—"),
        area_text=rec.get("area_text", "—"),
        irrigation_text=rec.get("irrigation_text", "—"),
        volume_text=rec.get("volume_text", "—"),
        savings_text=rec.get("savings_text", "—"),
    )


@start_router.message(F.text.in_({"📊 История", "📊 Тарих", "📊 History", "/history"}))
@start_router.message(Command("history"))
async def show_history(message: Message) -> None:
    """
    Выводит 1 карточку замера из истории с инлайн-кнопками пагинации:
    [ ⬅️ ] [ Бет X из Y ] [ ➡️ ]
    [ 🔙 Басты мәзірге / В главное меню ]
    """
    user_id = message.from_user.id
    lang = get_lang(user_id)
    history = get_user_history(user_id)

    if not history:
        await message.answer(
            text=t(lang, "history_empty"),
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard(lang),
        )
        return

    total = len(history)
    card_text = format_history_card(history[0], lang, page=1, total=total)
    keyboard = get_history_carousel_keyboard(lang, current_page=0, total_pages=total)

    await message.answer(
        text=card_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@start_router.callback_query(F.data == "show_history_inline")
async def show_history_inline(callback: CallbackQuery) -> None:
    """Обработчик инлайн-кнопки истории (когда обычная кнопка WebApp заблокирована)."""
    user_id = callback.from_user.id
    lang = get_lang(user_id)
    history = get_user_history(user_id)

    if not history:
        await callback.answer(t(lang, "history_empty"), show_alert=True)
        return

    total = len(history)
    card_text = format_history_card(history[0], lang, page=1, total=total)
    keyboard = get_history_carousel_keyboard(lang, current_page=0, total_pages=total)

    await callback.answer()
    await callback.message.answer(
        text=card_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@start_router.callback_query(F.data.startswith("hist_page:"))
async def handle_history_page(callback: CallbackQuery) -> None:
    """Плавное переключение страниц карусели истории через edit_text."""
    user_id = callback.from_user.id
    lang = get_lang(user_id)
    history = get_user_history(user_id)

    if not history:
        await callback.answer(t(lang, "history_empty"), show_alert=True)
        return

    try:
        page_idx = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        page_idx = 0

    total = len(history)
    page_idx = page_idx % total

    card_text = format_history_card(history[page_idx], lang, page=page_idx + 1, total=total)
    keyboard = get_history_carousel_keyboard(lang, current_page=page_idx, total_pages=total)

    try:
        await callback.message.edit_text(
            text=card_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        pass

    await callback.answer()


@start_router.callback_query(F.data == "hist_menu")
async def handle_history_menu(callback: CallbackQuery) -> None:
    """Возврат в главное меню из карусели истории."""
    user_id = callback.from_user.id
    lang = get_lang(user_id)
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        text=t(lang, "history_menu_returned"),
        reply_markup=get_main_reply_keyboard(lang),
    )



# ─── ⚙️ Выбор языка ──────────────────────────────────────────────────────────
@start_router.message(F.text.in_({"⚙️ Язык", "⚙️ Тіл", "⚙️ Language", "/lang", "/language"}))
@start_router.message(Command("lang", "language"))
async def change_lang_menu(message: Message) -> None:
    """Отправляет инлайн-кнопки для переключения языка."""
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "choose_lang"),
        reply_markup=get_lang_keyboard(),
    )


# ─── 🌿 Открытие Mini App ───────────────────────────────────────────────────
@start_router.message(Command("app"))
async def open_app(message: Message) -> None:
    """Show a native Web App button from the command menu."""
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "app_prompt"),
        parse_mode="HTML",
        reply_markup=get_launch_keyboard(lang),
    )


# ─── 📜 О системе ────────────────────────────────────────────────────────────
@start_router.message(F.text.in_({"📜 О системе", "📜 Жүйе туралы", "📜 About", "/about"}))
@start_router.message(Command("about"))
async def show_about(message: Message) -> None:
    """Академический паспорт системы Su-Tech v1.0."""
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "about_text"),
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard(lang),
    )


# ─── ❓ Помощь ───────────────────────────────────────────────────────────────
@start_router.message(F.text.in_({"❓ Помощь", "❓ Көмек", "❓ Help", "/help"}))
@start_router.message(Command("help"))
async def show_help(message: Message) -> None:
    """Руководство пользователя по работе с системой Su-Tech."""
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "help_text"),
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard(lang),
    )


# ─── 📜 О методике (Callback Popup) ──────────────────────────────────────────
@start_router.callback_query(F.data == "methodology:info")
async def show_methodology(callback: CallbackQuery) -> None:
    """Выводит детальное описание методики FAO-56 Penman-Monteith."""
    lang = get_lang(callback.from_user.id)
    await callback.answer(
        text="Su-Tech · FAO-56 · TAW / RAW",
        show_alert=False,
    )
    await callback.message.answer(
        text=t(lang, "methodology_text"),
        parse_mode="HTML",
    )


# Keep this text-only fallback last so commands, WebApp data and callbacks keep
# their dedicated handlers.
@start_router.message(F.text)
async def unknown_text(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(
        text=t(lang, "unknown_message"),
        reply_markup=get_launch_keyboard(lang),
    )
