"""Private Telegram chat for plant-photo assessments and agronomy questions."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from bot.ai_i18n import AI_STRINGS, ai_text
from bot.config import GEMINI_API_KEY, GEMINI_MODEL
from bot.bot_setup import webapp_url
from bot.i18n import t
from bot.keyboards.reply import get_main_reply_keyboard
from bot.services.agronomist import (AIError, AgronomistService, GeminiClient,
                                    LimitedImageBuffer, MAX_IMAGE_BYTES, MAX_TEXT_CHARS)
from bot.user_state import get_lang

agronomist_router = Router(name="agronomist")
agronomist_router.message.filter(F.chat.type == "private")
assistant = AgronomistService(GeminiClient(GEMINI_API_KEY, GEMINI_MODEL))
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
    assistant.clear(message.from_user.id)
    await state.clear()
    await state.set_state(AgronomistChat.active)
    await message.answer(ai_text(lang, "cleared"), reply_markup=chat_keyboard(lang))


@agronomist_router.message(Command("exit"))
@agronomist_router.message(F.text.in_({copy["exit_button"] for copy in AI_STRINGS.values()}))
async def exit_ai(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    assistant.clear(message.from_user.id)
    await state.clear()
    await message.answer(ai_text(lang, "closed"), reply_markup=get_main_reply_keyboard(lang))


ACTION_BUTTONS = {copy[key] for copy in AI_STRINGS.values()
                  for key in ("photo_button", "water_button", "care_button")}


@agronomist_router.message(F.text.in_(ACTION_BUTTONS))
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
              for key in ("btn_fields", "btn_history", "btn_lang", "btn_about", "btn_help")}


@agronomist_router.message(AgronomistChat.active,
                           F.text.startswith("/") | F.text.in_(MENU_TEXTS))
async def leave_for_menu(message: Message, state: FSMContext) -> None:
    assistant.clear(message.from_user.id)
    await state.clear()
    raise SkipHandler()


@agronomist_router.callback_query(AgronomistChat.active)
async def leave_for_callback(callback: CallbackQuery, state: FSMContext) -> None:
    assistant.clear(callback.from_user.id)
    await state.clear()
    raise SkipHandler()


@agronomist_router.message(StateFilter(None, AgronomistChat.active), F.photo | F.document)
@agronomist_router.message(AgronomistChat.active, F.text,
                           ~F.text.startswith("/"), ~F.text.in_(MENU_TEXTS | ACTION_BUTTONS))
async def ask_ai(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    lang = get_lang(user_id)
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
    topic = (await state.get_data()).get("ai_topic")
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
            result = await assistant.reply(user_id, text, lang, image)
        if await state.get_state() == AgronomistChat.active.state:
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
