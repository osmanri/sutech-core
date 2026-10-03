"""Voluntary pilot onboarding and feedback without extra chat messages."""
import asyncio
import logging
import re
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from bot.pilot_i18n import pilot_text
from bot.pilot_store import join_pilot, leave_pilot, pilot_status, save_feedback
from bot.keyboards.inline import get_launch_keyboard
from bot.user_state import get_lang, set_lang

pilot_router = Router(name='pilot')
logger = logging.getLogger(__name__)


def pilot_keyboard(lang, joined=False):
    rows = list(get_launch_keyboard(lang).inline_keyboard)
    rows.insert(0, [InlineKeyboardButton(text=pilot_text(lang,'leave' if joined else 'join'),
                                       callback_data='pilot:leave' if joined else 'pilot:join')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _private(message, user_id):
    return message is not None and message.chat.type == 'private' and message.chat.id == user_id


async def _screen(user_id, lang):
    status = await asyncio.to_thread(pilot_status, user_id)
    text = pilot_text(lang,'joined',**status) if status['joined'] else pilot_text(lang,'invite')
    return text,pilot_keyboard(lang,status['joined'])


@pilot_router.message(Command('pilot'))
@pilot_router.message(CommandStart(), F.text.regexp(r'^/start(?:@\w+)?\s+pilot_(?:ru|kz|en)$'))
async def open_pilot(message: Message):
    lang = get_lang(message.from_user.id)
    payload = (message.text or '').split(maxsplit=1)
    if len(payload)==2 and payload[1] in {'pilot_ru','pilot_kz','pilot_en'}:
        lang=payload[1].removeprefix('pilot_');set_lang(message.from_user.id,lang)
    if not _private(message,message.from_user.id):
        await message.answer(pilot_text(lang,'private'));return
    try:
        text,keyboard=await _screen(message.from_user.id,lang)
    except Exception as exc:
        logger.warning('Pilot screen unavailable: %s',type(exc).__name__)
        await message.answer(pilot_text(lang,'failed'));return
    await message.answer(text,parse_mode='HTML',reply_markup=keyboard)


@pilot_router.callback_query(F.data.in_({'pilot:join','pilot:leave','pilot:delete','pilot:back'}))
async def pilot_action(callback: CallbackQuery):
    user_id=callback.from_user.id;lang=get_lang(user_id)
    if not _private(callback.message,user_id):
        await callback.answer(pilot_text(lang,'private'),show_alert=True);return
    try:
        if callback.data=='pilot:leave':
            keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=pilot_text(lang,'confirmDelete'),callback_data='pilot:delete')],
                [InlineKeyboardButton(text=pilot_text(lang,'cancel'),callback_data='pilot:back')],
            ])
            await callback.message.edit_text(pilot_text(lang,'deletePrompt'),reply_markup=keyboard)
        elif callback.data=='pilot:delete':
            await asyncio.to_thread(leave_pilot,user_id)
            await callback.message.edit_text(pilot_text(lang,'deleted'),reply_markup=get_launch_keyboard(lang))
        else:
            if callback.data=='pilot:join':await asyncio.to_thread(join_pilot,user_id,lang)
            text,keyboard=await _screen(user_id,lang)
            await callback.message.edit_text(text,parse_mode='HTML',reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if 'message is not modified' not in str(exc):
            logger.warning('Could not update pilot screen')
            await callback.answer(pilot_text(lang,'failed'),show_alert=True);return
    except Exception as exc:
        logger.warning('Pilot action unavailable: %s',type(exc).__name__)
        await callback.answer(pilot_text(lang,'failed'),show_alert=True);return
    await callback.answer()


@pilot_router.callback_query(F.data.startswith('pilot:vote:'))
async def rate_report(callback: CallbackQuery):
    user_id=callback.from_user.id;lang=get_lang(user_id)
    match=re.fullmatch(r'pilot:vote:([yn]):([0-9a-f]{32})',callback.data or '')
    if not match or not _private(callback.message,user_id):
        await callback.answer(pilot_text(lang,'not_found'),show_alert=True);return
    vote,report_id=match.groups()
    try:
        saved=await asyncio.to_thread(save_feedback,user_id,report_id,vote=='y')
    except Exception as exc:
        logger.warning('Feedback unavailable: %s',type(exc).__name__)
        await callback.answer(pilot_text(lang,'failed'),show_alert=True);return
    if not saved:
        await callback.answer(pilot_text(lang,'not_found'),show_alert=True);return
    # Preserve the original report and navigation. Only show which vote was saved.
    if callback.message.reply_markup:
        markup=callback.message.reply_markup.model_copy(deep=True)
        for row in markup.inline_keyboard:
            for button in row:
                if button.callback_data in {f'pilot:vote:y:{report_id}',f'pilot:vote:n:{report_id}'}:
                    label=pilot_text(lang,'useful' if ':y:' in button.callback_data else 'unhelpful')
                    button.text=('✓ ' if button.callback_data==callback.data else '')+label
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except TelegramAPIError:
            logger.warning('Rating saved; Telegram could not refresh its buttons')
    await callback.answer(pilot_text(lang,'thanks'))
