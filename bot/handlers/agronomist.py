"""Private Telegram chat for plant-photo assessments and agronomy questions."""

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup,
                          WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup)

from bot.ai_i18n import AI_STRINGS, ai_text
from bot.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_DEEP_MODEL
from bot.bot_setup import webapp_url
from bot.i18n import t
from bot.keyboards.reply import get_main_reply_keyboard
from bot.services.agronomist import (AIError, AgronomistService, GeminiClient,
                                    LimitedImageBuffer, MAX_IMAGE_BYTES, MAX_TEXT_CHARS)
from bot.user_state import get_lang
from bot.services.ai_history import SQLAIHistory

agronomist_router = Router(name="agronomist")
agronomist_router.message.filter(F.chat.type == "private")
agronomist_router.callback_query.filter(F.message.chat.type == "private")
assistant = AgronomistService(GeminiClient(GEMINI_API_KEY, GEMINI_MODEL),
                             deep_client=GeminiClient(GEMINI_API_KEY, GEMINI_DEEP_MODEL, "MEDIUM"),
                             store=SQLAIHistory())
logger = logging.getLogger(__name__)
request_slots = asyncio.Semaphore(4)


class AgronomistChat(StatesGroup):
    active = State()


def chat_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=ai_text(lang, "photo_button"), style="success")],
        [KeyboardButton(text=ai_text(lang, "water_button")),
         KeyboardButton(text=ai_text(lang, "care_button"))],
        [KeyboardButton(text=ai_text(lang, "calculate_button"),
                        web_app=WebAppInfo(url=webapp_url(lang)))],
        [KeyboardButton(text=ai_text(lang, "deep_button")),
         KeyboardButton(text=ai_text(lang, "history_button"))],
        [KeyboardButton(text=ai_text(lang, "new_button")),
         KeyboardButton(text=ai_text(lang, "exit_button"))],
    ], resize_keyboard=True, input_field_placeholder=ai_text(lang, "placeholder"))


@agronomist_router.message(Command("ai", "disease"))
@agronomist_router.message(CommandStart(deep_link=True, magic=F.args == "ai"))
@agronomist_router.message(F.text.in_({copy["button"] for copy in AI_STRINGS.values()}))
async def start_ai(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.clear()
    assistant.clear(message.from_user.id)
    if not assistant.client.configured:
        await message.answer(ai_text(lang, "not_configured"),
                             reply_markup=get_main_reply_keyboard(lang))
        return
    try:
        await assistant.set_active(message.from_user.id, True)
    except AIError as exc:
        await message.answer(ai_text(lang, exc.code), parse_mode=None)
        return
    await state.set_state(AgronomistChat.active)
    await message.answer(ai_text(lang, "intro"), parse_mode=None,
                         reply_markup=chat_keyboard(lang))


@agronomist_router.message(Command("newchat"))
@agronomist_router.message(F.text.in_({copy["new_button"] for copy in AI_STRINGS.values()}))
async def new_chat(message: Message, state: FSMContext) -> None:
    if not assistant.client.configured:
        await start_ai(message, state)
        return
    lang = get_lang(message.from_user.id)
    try:
        await assistant.reset(message.from_user.id)
    except AIError as exc:
        await message.answer(ai_text(lang, exc.code), parse_mode=None)
        return
    await state.clear()
    await state.set_state(AgronomistChat.active)
    await message.answer(ai_text(lang, "cleared"), reply_markup=chat_keyboard(lang))


@agronomist_router.message(Command("exit"))
@agronomist_router.message(F.text.in_({copy["exit_button"] for copy in AI_STRINGS.values()}))
async def exit_ai(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    try:
        await assistant.set_active(message.from_user.id, False)
    except AIError:
        pass  # Menu access must remain available during a database outage.
    await state.clear()
    await message.answer(ai_text(lang, "closed"), reply_markup=get_main_reply_keyboard(lang))


ACTION_BUTTONS = {copy[key] for copy in AI_STRINGS.values()
                  for key in ("photo_button", "water_button", "care_button", "deep_button", "history_button")}


@agronomist_router.message(Command("deep"))
@agronomist_router.message(F.text.in_({copy["deep_button"] for copy in AI_STRINGS.values()}))
async def choose_deep(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    if not assistant.client.configured:
        await start_ai(message, state)
        return
    await state.set_state(AgronomistChat.active)
    await state.update_data(ai_deep=True, ai_topic=None)
    await message.answer(ai_text(lang, "deep_hint"), parse_mode=None,
                         reply_markup=chat_keyboard(lang))


async def send_history(message: Message, user_id: int, lang: str, offset=0) -> None:
    page = await assistant.history_page(user_id, offset)
    if not page["entry"]:
        await message.answer(ai_text(lang, "history_empty"), parse_mode=None)
        return
    entry, index, total = page["entry"], page["offset"], page["total"]
    date = datetime.fromtimestamp(entry["created_at"] / 1000, timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    await message.answer(
        ai_text(lang, "history_title").format(page=index + 1, total=total) + " · " + date
        + "\n\n" + ai_text(lang, "history_question") + ":\n" + entry["question"]
        + ("\n\n" + ai_text(lang, "history_photo") if entry["has_image"] else ""),
        parse_mode=None)
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton(text="←", callback_data=f"ai_history:{index - 1}"))
    if index + 1 < total:
        buttons.append(InlineKeyboardButton(text="→", callback_data=f"ai_history:{index + 1}"))
    rows = [buttons] if buttons else []
    rows.append([InlineKeyboardButton(text=ai_text(lang, "history_delete"), callback_data="ai_delete_prompt")])
    await message.answer(ai_text(lang, "history_answer") + ":\n" + entry["answer"],
                         parse_mode=None, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@agronomist_router.message(Command("aihistory"))
@agronomist_router.message(F.text.in_({copy["history_button"] for copy in AI_STRINGS.values()}))
async def show_ai_history(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    try:
        await send_history(message, message.from_user.id, lang)
    except AIError as exc:
        await message.answer(ai_text(lang, exc.code), parse_mode=None)


@agronomist_router.callback_query(F.data.startswith("ai_history:"))
async def ai_history_page(callback: CallbackQuery) -> None:
    await callback.answer()
    lang = get_lang(callback.from_user.id)
    try:
        offset = int(callback.data.split(":")[1])
        if callback.message:
            await send_history(callback.message, callback.from_user.id, lang, offset)
    except (ValueError, AIError) as exc:
        if callback.message:
            await callback.message.answer(ai_text(lang, getattr(exc, "code", "history_empty")), parse_mode=None)


@agronomist_router.callback_query(F.data.in_({"ai_delete_prompt", "ai_delete_yes", "ai_delete_no"}))
async def delete_ai_history(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return
    lang = get_lang(callback.from_user.id)
    if callback.data == "ai_delete_prompt":
        await callback.message.answer(ai_text(lang, "delete_confirm"), parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=ai_text(lang, "delete_yes"), callback_data="ai_delete_yes"),
                 InlineKeyboardButton(text=ai_text(lang, "delete_no"), callback_data="ai_delete_no")]]))
    elif callback.data == "ai_delete_yes":
        try:
            await assistant.reset(callback.from_user.id, delete=True)
            await state.clear()
            await state.set_state(AgronomistChat.active)
            await callback.message.edit_text(ai_text(lang, "deleted"), parse_mode=None, reply_markup=None)
            await callback.message.answer(ai_text(lang, "placeholder"), parse_mode=None,
                                          reply_markup=chat_keyboard(lang))
        except AIError as exc:
            await callback.message.answer(ai_text(lang, exc.code), parse_mode=None)
    else:
        await callback.message.edit_text(ai_text(lang, "delete_no"), parse_mode=None, reply_markup=None)


@agronomist_router.message(F.text.in_(ACTION_BUTTONS - {
    copy[key] for copy in AI_STRINGS.values() for key in ("deep_button", "history_button")}))
async def choose_topic(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    if not assistant.client.configured:
        await start_ai(message, state)
        return
    topic = next(key.removesuffix("_button") for key in ("photo_button", "water_button", "care_button")
                 if any(copy[key] == message.text for copy in AI_STRINGS.values()))
    # Choosing an action shows guidance; it must never spend an AI request.
    await state.set_state(AgronomistChat.active)
    await state.update_data(ai_topic=topic)
    await message.answer(ai_text(lang, topic + "_hint"), parse_mode=None,
                         reply_markup=chat_keyboard(lang))


# Exit the AI state before the usual menu handlers receive their commands.
MENU_TEXTS = {t(lang, key) for lang in ("ru", "kz", "en")
              for key in ("btn_fields", "btn_history", "btn_lang", "btn_about", "btn_help", "btn_webapp")}


@agronomist_router.message(AgronomistChat.active,
                           F.text.startswith("/") | F.text.in_(MENU_TEXTS))
async def leave_for_menu(message: Message, state: FSMContext) -> None:
    try:
        await assistant.set_active(message.from_user.id, False)
    except AIError:
        pass
    await state.clear()
    raise SkipHandler()


@agronomist_router.callback_query(AgronomistChat.active)
async def leave_for_callback(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await assistant.set_active(callback.from_user.id, False)
    except AIError:
        pass
    await state.clear()
    raise SkipHandler()


@agronomist_router.message(StateFilter(None, AgronomistChat.active), F.photo | F.document)
@agronomist_router.message(StateFilter(None, AgronomistChat.active), F.text,
                           ~F.text.startswith("/"), ~F.text.in_(MENU_TEXTS | ACTION_BUTTONS))
async def ask_ai(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    lang = get_lang(user_id)
    if not (message.photo or message.document) and await state.get_state() is None:
        if not assistant.client.configured:
            raise SkipHandler()
        # Resume the AI mode after a server restart; explicit menu exit stays off.
        try:
            if not await assistant.is_active(user_id):
                raise SkipHandler()
        except AIError as exc:
            await message.answer(ai_text(lang, exc.code), parse_mode=None)
            return
    if not assistant.client.configured:
        await start_ai(message, state)
        return
    has_image = bool(message.photo or message.document)
    text = (message.caption if has_image else message.text) or ai_text(lang, "photo_prompt")
    if len(text) > MAX_TEXT_CHARS:
        await message.answer(ai_text(lang, "long_text"))
        return
    file = message.photo[-1] if message.photo else message.document
    if file and (file.file_size or 0) > MAX_IMAGE_BYTES:
        await message.answer(ai_text(lang, "large_image"))
        return
    if message.document and message.document.mime_type not in {"image/jpeg", "image/png"}:
        await message.answer(ai_text(lang, "bad_image"))
        return
    chat_data = await state.get_data()
    topic = chat_data.get("ai_topic")
    deep = bool(chat_data.get("ai_deep"))
    if topic == "photo" and not has_image:
        await message.answer(ai_text(lang, "photo_pending"), reply_markup=chat_keyboard(lang))
        return
    if not has_image and topic in {"water", "care"}:
        text = ai_text(lang, topic + "_button") + ": " + text
    # One-time prompt context; follow-ups use the assistant's conversation.
    await state.update_data(ai_topic=None)
    if await state.get_state() is None:
        # Direct photos are supported, with the same privacy notice as /ai.
        await state.set_state(AgronomistChat.active)
        await message.answer(ai_text(lang, "intro"), parse_mode=None,
                             reply_markup=chat_keyboard(lang))
    status = await message.answer(ai_text(lang, "working" if has_image else "thinking"))
    try:
        async with request_slots:
            image = None
            if file:
                with LimitedImageBuffer() as buffer:
                    await message.bot.download(file, destination=buffer, timeout=20)
                    image = buffer.getvalue()
            result = await assistant.reply(user_id, text, lang, image, deep=deep)
        if await state.get_state() == AgronomistChat.active.state:
            await state.update_data(ai_deep=False)
            if getattr(result, "fallback", False):
                await message.answer(ai_text(lang, "deep_fallback"), parse_mode=None)
            await message.answer(result, parse_mode=None, reply_markup=chat_keyboard(lang))
    except AIError as exc:
        if exc.code != "cancelled":
            await message.answer(ai_text(lang, exc.code), parse_mode=None)
    except Exception as exc:
        # Do not log photos, questions, Telegram file URLs or provider secrets.
        logger.warning("Agronomist request failed (%s)", type(exc).__name__)
        await message.answer(ai_text(lang, "unavailable"))
    finally:
        try:
            await status.delete()
        except Exception:
            pass


@agronomist_router.message(AgronomistChat.active, ~F.web_app_data,
                           ~F.text, ~F.photo, ~F.document)
async def unsupported_ai_message(message: Message) -> None:
    await message.answer(ai_text(get_lang(message.from_user.id), "unsupported"))
