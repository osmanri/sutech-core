"""Private Telegram chat for plant-photo assessments and agronomy questions."""

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup,
                          WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup)

from bot.ai_i18n import AI_STRINGS, ai_text
from bot.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_DEEP_MODEL
from bot.bot_setup import webapp_url, configure_user_menu
from bot.i18n import t
from bot.keyboards.reply import get_main_reply_keyboard
from bot.services.agronomist import (AIError, AgronomistService, GeminiClient,
                                    LimitedImageBuffer, MAX_IMAGE_BYTES, MAX_TEXT_CHARS)
from bot.user_state import get_lang, set_lang
from bot.services.ai_history import SQLAIHistory
from bot.handlers.chat_planner import PLAN_BUTTON, register_chat_planner

agronomist_router = Router(name="agronomist")
agronomist_router.message.filter(F.chat.type == "private")
agronomist_router.callback_query.filter(F.message.chat.type == "private")
assistant = AgronomistService(GeminiClient(GEMINI_API_KEY, GEMINI_MODEL),
                             deep_client=GeminiClient(GEMINI_API_KEY, GEMINI_DEEP_MODEL, "MEDIUM"),
                             store=SQLAIHistory())
logger = logging.getLogger(__name__)
request_slots = asyncio.Semaphore(4)
register_chat_planner(agronomist_router)


class AgronomistChat(StatesGroup):
    active = State()


async def replace_ui_message(message: Message, state: FSMContext, text: str,
                             reply_markup=None) -> Message:
    """Reuse the assistant's current guidance/status card instead of stacking one."""
    data = await state.get_data()
    previous_id = data.get("ai_ui_message_id")
    if previous_id:
        try:
            edited = await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=previous_id, text=text,
                parse_mode=None,
                reply_markup=reply_markup if isinstance(reply_markup, InlineKeyboardMarkup) else None)
            await state.update_data(ai_ui_message_id=edited.message_id)
            return edited
        except TelegramBadRequest:
            # The prompt may have been deleted or aged out; send one replacement.
            pass
    sent = await message.answer(text, parse_mode=None, reply_markup=reply_markup)
    await state.update_data(ai_ui_message_id=sent.message_id)
    return sent


async def animate_status(bot, chat_id: int, message_id: int, lang: str,
                         stop: asyncio.Event) -> None:
    """Animate one Telegram status bubble; no extra messages are created."""
    frames = AI_STRINGS.get(lang, AI_STRINGS["ru"]).get("loading_frames", ())
    if not frames:
        return
    index = 0
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.1)
            break
        except asyncio.TimeoutError:
            pass
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                        text=frames[index % len(frames)], parse_mode=None)
            index += 1
        except TelegramBadRequest:
            # Keep the request running even if Telegram rejects a redundant edit.
            continue


def history_keyboard(lang: str, index: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    if index > 0:
        buttons.append(InlineKeyboardButton(text="←", callback_data=f"ai_history:{index - 1}"))
    if index + 1 < total:
        buttons.append(InlineKeyboardButton(text="→", callback_data=f"ai_history:{index + 1}"))
    rows = [buttons] if buttons else []
    rows.append([InlineKeyboardButton(text=ai_text(lang, "history_delete"), callback_data="ai_delete_prompt")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def chat_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=ai_text(lang, "photo_button"), style="success")],
        [KeyboardButton(text=ai_text(lang, "water_button")),
         KeyboardButton(text=ai_text(lang, "care_button"))],
        [KeyboardButton(text=ai_text(lang, "calculate_button"),
                        web_app=WebAppInfo(url=webapp_url(lang))),
         KeyboardButton(text=PLAN_BUTTON.get(lang, PLAN_BUTTON['ru']))],
        [KeyboardButton(text=ai_text(lang, "history_button")),
         KeyboardButton(text=ai_text(lang, "new_button"))],
        [KeyboardButton(text=ai_text(lang, "exit_button"))],
    ], resize_keyboard=True, input_field_placeholder=ai_text(lang, "placeholder"))


@agronomist_router.message(Command("ai", "disease"))
@agronomist_router.message(CommandStart(deep_link=True, magic=F.args.in_({"ai", "ai_ru", "ai_kz", "ai_en"})))
@agronomist_router.message(F.text.in_({copy["button"] for copy in AI_STRINGS.values()}))
async def start_ai(message: Message, state: FSMContext) -> None:
    payload = (message.text or "").split(maxsplit=1)
    requested_lang = None
    if len(payload) == 2 and payload[1] in {"ai_ru", "ai_kz", "ai_en"}:
        requested_lang = payload[1].removeprefix("ai_")
    elif message.text:
        requested_lang = next((language for language, copy in AI_STRINGS.items()
                               if copy["button"] == message.text), None)
    if requested_lang:
        set_lang(message.from_user.id, requested_lang)
        try:
            await configure_user_menu(message.bot, message.from_user.id, requested_lang)
        except Exception as exc:
            logger.warning("Could not update localized AI menu (%s)", type(exc).__name__)
    lang = get_lang(message.from_user.id)
    previous_ui_id = (await state.get_data()).get("ai_ui_message_id")
    await state.clear()
    if previous_ui_id:
        await state.update_data(ai_ui_message_id=previous_ui_id)
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
    await replace_ui_message(message, state, ai_text(lang, "intro"),
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
    previous_ui_id = (await state.get_data()).get("ai_ui_message_id")
    await state.clear()
    await state.set_state(AgronomistChat.active)
    if previous_ui_id:
        await state.update_data(ai_ui_message_id=previous_ui_id)
    await replace_ui_message(message, state, ai_text(lang, "cleared"),
                             reply_markup=chat_keyboard(lang))


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
    await replace_ui_message(message, state, ai_text(lang, "deep_hint"),
                             reply_markup=chat_keyboard(lang))


async def send_history(message: Message, user_id: int, lang: str, offset=0,
                       edit: bool = False, state: FSMContext | None = None) -> None:
    page = await assistant.history_page(user_id, offset)
    if not page["entry"]:
        if state is not None and not edit:
            await replace_ui_message(message, state, ai_text(lang, "history_empty"))
        elif edit:
            await message.edit_text(ai_text(lang, "history_empty"), parse_mode=None,
                                    reply_markup=None)
        else:
            await message.answer(ai_text(lang, "history_empty"), parse_mode=None)
        return
    entry, index, total = page["entry"], page["offset"], page["total"]
    date = datetime.fromtimestamp(entry["created_at"] / 1000, timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    card = (ai_text(lang, "history_title").format(page=index + 1, total=total) + " · " + date
            + "\n\n" + ai_text(lang, "history_question") + ":\n" + entry["question"]
            + ("\n" + ai_text(lang, "history_photo") if entry["has_image"] else "")
            + "\n\n" + ai_text(lang, "history_answer") + ":\n" + entry["answer"])
    markup = history_keyboard(lang, index, total)
    if edit:
        await message.edit_text(card, parse_mode=None, reply_markup=markup)
    elif state is not None:
        await replace_ui_message(message, state, card, reply_markup=markup)
    else:
        await message.answer(card, parse_mode=None, reply_markup=markup)


@agronomist_router.message(Command("aihistory"))
@agronomist_router.message(F.text.in_({copy["history_button"] for copy in AI_STRINGS.values()}))
async def show_ai_history(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    try:
        await send_history(message, message.from_user.id, lang, state=state)
    except AIError as exc:
        await replace_ui_message(message, state, ai_text(lang, exc.code))


@agronomist_router.callback_query(F.data.startswith("ai_history:"))
async def ai_history_page(callback: CallbackQuery) -> None:
    await callback.answer()
    lang = get_lang(callback.from_user.id)
    try:
        offset = int(callback.data.split(":")[1])
        if callback.message:
            await send_history(callback.message, callback.from_user.id, lang, offset, edit=True)
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
        await callback.message.edit_text(ai_text(lang, "delete_confirm"), parse_mode=None,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=ai_text(lang, "delete_yes"), callback_data="ai_delete_yes"),
                 InlineKeyboardButton(text=ai_text(lang, "delete_no"), callback_data="ai_delete_no")]]))
    elif callback.data == "ai_delete_yes":
        try:
            await assistant.reset(callback.from_user.id, delete=True)
            await state.clear()
            await state.set_state(AgronomistChat.active)
            await state.update_data(ai_ui_message_id=callback.message.message_id)
            await callback.message.edit_text(ai_text(lang, "deleted"), parse_mode=None, reply_markup=None)
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
    await replace_ui_message(message, state, ai_text(lang, topic + "_hint"),
                             reply_markup=chat_keyboard(lang))


# Exit the AI state before the usual menu handlers receive their commands.
MENU_TEXTS = {t(lang, key) for lang in ("ru", "kz", "en")
              for key in ("btn_fields", "btn_history", "btn_lang", "btn_about", "btn_help", "btn_webapp", "btn_more", "btn_back")}


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
    # Do not prepend a crop-care topic to arbitrary text: it could make an
    # unrelated question appear relevant to the local quota-saving filter.
    # One-time prompt context; follow-ups use the assistant's conversation.
    await state.update_data(ai_topic=None)
    if await state.get_state() is None:
        # Direct photos are supported, with the same privacy notice as /ai.
        await state.set_state(AgronomistChat.active)
        await replace_ui_message(message, state, ai_text(lang, "intro"),
                                 reply_markup=chat_keyboard(lang))
    status = await replace_ui_message(
        message, state, ai_text(lang, "working" if has_image else "thinking"))
    stop_animation = asyncio.Event()
    animation = asyncio.create_task(animate_status(
        message.bot, message.chat.id, status.message_id, lang, stop_animation))

    async def stop_loading_animation() -> None:
        stop_animation.set()
        animation.cancel()
        await asyncio.gather(animation, return_exceptions=True)

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
                result = f"{result}\n\n{ai_text(lang, 'deep_fallback')}"
            await stop_loading_animation()
            await status.edit_text(result, parse_mode=None)
            await state.update_data(ai_ui_message_id=None)
    except AIError as exc:
        if exc.code != "cancelled":
            await stop_loading_animation()
            await status.edit_text(ai_text(lang, exc.code), parse_mode=None)
            await state.update_data(ai_ui_message_id=None)
    except Exception as exc:
        # Do not log photos, questions, Telegram file URLs or provider secrets.
        logger.warning("Agronomist request failed (%s)", type(exc).__name__)
        await stop_loading_animation()
        await status.edit_text(ai_text(lang, "unavailable"), parse_mode=None)
        await state.update_data(ai_ui_message_id=None)
    finally:
        await stop_loading_animation()


@agronomist_router.message(AgronomistChat.active, ~F.web_app_data,
                           ~F.text, ~F.photo, ~F.document)
async def unsupported_ai_message(message: Message) -> None:
    await message.answer(ai_text(get_lang(message.from_user.id), "unsupported"))
