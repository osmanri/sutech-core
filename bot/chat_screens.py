"""One navigation screen per private chat, shared by all bot sections."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, User
from bot import chat_screen_store as store

logger = logging.getLogger(__name__)


class ScreenSuperseded(Exception):
    """A newer navigation has replaced this request's visible screen."""


@dataclass
class Screen:
    chat_id: int
    generation: int
    navigation: bool
    previous: dict
    cleaned: bool = False
    rendered: set = field(default_factory=set)


current_screen = ContextVar('sutech_chat_screen', default=None)


class ChatScreens:
    def __init__(self):
        self.memory = {}
        self.generations = {}

    async def remember(self, chat_id, message_id, kind, created_at):
        if chat_id <= 0 or message_id <= 0:
            return
        known = self.memory.setdefault(chat_id, {})
        if message_id in known:
            return  # Loading-animation edits must not repeatedly hit PostgreSQL.
        known[message_id] = {'kind':kind, 'created_at':created_at}
        for old in sorted(known)[:-store.MAX_MESSAGES]:
            known.pop(old, None)
        try:
            await asyncio.to_thread(store.remember,chat_id,message_id,kind,created_at)
        except Exception as exc:
            logger.warning('UI message tracking unavailable: %s',type(exc).__name__)

    @asynccontextmanager
    async def screen(self, chat_id, navigation):
        if navigation:
            self.generations[chat_id] = self.generations.get(chat_id,0) + 1
            from bot.handlers.agronomist import stop_visible_request
            stop_visible_request(chat_id)
        generation = self.generations.get(chat_id,0)
        previous = dict(self.memory.get(chat_id,{}))
        if navigation:
            try:
                previous.update(await asyncio.to_thread(store.messages,chat_id))
            except Exception as exc:
                logger.warning('UI screen restore unavailable: %s',type(exc).__name__)
        screen = Screen(chat_id,generation,navigation,previous)
        token = current_screen.set(screen)
        try:
            yield screen
        finally:
            current_screen.reset(token)

    def is_current(self, screen):
        return self.generations.get(screen.chat_id,0) == screen.generation

    async def forget(self, chat_id, ids):
        for message_id in ids:
            self.memory.get(chat_id,{}).pop(message_id,None)
        try:
            await asyncio.to_thread(store.forget,chat_id,ids)
        except Exception as exc:
            logger.warning('UI cleanup tracking unavailable: %s',type(exc).__name__)

    async def cleanup(self, bot, screen):
        if screen.cleaned or not screen.navigation or not self.is_current(screen):
            return
        screen.cleaned = True
        previous = {i:r for i,r in screen.previous.items() if i not in screen.rendered}
        now = time.time()
        # Telegram dates may be a few seconds ahead of this server's clock.
        recent = [i for i,r in previous.items() if now-r['created_at'] < 48*3600]
        removed = []
        for offset in range(0,len(recent),100):
            batch = recent[offset:offset+100]
            if not self.is_current(screen):
                break
            try:
                await bot.delete_messages(chat_id=screen.chat_id,message_ids=batch)
                removed.extend(batch)
            except TelegramBadRequest:
                # A dice/service message or already-deleted message must not
                # prevent cleaning the other ordinary messages in this screen.
                for message_id in batch:
                    if not self.is_current(screen):
                        break
                    try:
                        await bot.delete_message(chat_id=screen.chat_id,message_id=message_id)
                        removed.append(message_id)
                    except TelegramBadRequest:
                        await self.disable_buttons(bot,screen.chat_id,message_id,previous[message_id])
                        removed.append(message_id)
                    except TelegramAPIError:
                        break  # Retry retained IDs on the next navigation.
            except TelegramAPIError:
                break
        for message_id,record in previous.items():
            if now-record['created_at'] >= 48*3600 and self.is_current(screen):
                await self.disable_buttons(bot,screen.chat_id,message_id,record)
                removed.append(message_id)
        await self.forget(screen.chat_id,removed)

    @staticmethod
    async def disable_buttons(bot,chat_id,message_id,record):
        if record['kind'] != 'bot':
            return
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id,message_id=message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        except TelegramAPIError:
            pass

    async def request(self, make_request, bot, method):
        screen = current_screen.get()
        chat_id = getattr(method,'chat_id',None)
        mutates_ui = type(method).__name__.startswith(('Send','EditMessage'))
        if screen and chat_id == screen.chat_id and mutates_ui and not self.is_current(screen):
            raise ScreenSuperseded()
        if (screen and screen.navigation and chat_id == screen.chat_id
                and type(method).__name__ in ('SendMessage','SendPhoto','SendDocument')
                and method.reply_markup is None):
            from bot.i18n import t
            from bot.user_state import get_lang
            method=method.model_copy(update={'reply_markup':InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=t(get_lang(chat_id),'btn_back'),callback_data='ui:home')]])})
        try:
            result = await make_request(bot,method)
        except TelegramBadRequest as exc:
            # A fast second click can arrive after its old card was removed.
            # Render its content as a new screen rather than silently dropping it.
            recoverable = ('message to edit not found','message can\'t be edited')
            if (screen and self.is_current(screen) and mutates_ui
                    and getattr(method,'message_id',None) and 'message is not modified' in str(exc).lower()):
                # Telegram reports an already-rendered card as an error. It is
                # still the current screen, so remove the other old messages.
                record=screen.previous.get(method.message_id,{})
                result=Message(message_id=method.message_id,
                    date=datetime.fromtimestamp(record.get('created_at',time.time()),timezone.utc),
                    chat=Chat(id=chat_id,type='private'),
                    from_user=User(id=getattr(bot,'id',0),is_bot=True,first_name='Su-Tech'),
                    text=getattr(method,'text',None),reply_markup=getattr(method,'reply_markup',None)).as_(bot)
            elif (screen and self.is_current(screen) and type(method).__name__ == 'EditMessageText'
                    and any(term in str(exc).lower() for term in recoverable)):
                return await bot.send_message(chat_id=chat_id,text=method.text,
                    parse_mode=method.parse_mode,entities=method.entities,
                    reply_markup=method.reply_markup,link_preview_options=method.link_preview_options)
            else:
                raise
        results = result if isinstance(result,list) else [result]
        for message in results:
            if not isinstance(message,Message) or message.chat.type != 'private' or message.chat.id <= 0:
                continue
            await self.remember(message.chat.id,message.message_id,'bot',int(message.date.timestamp()))
            if screen and message.chat.id == screen.chat_id and mutates_ui:
                screen.rendered.add(message.message_id)
                await self.cleanup(bot,screen)
        # Successful explicit deletions in existing handlers also retire IDs.
        if result is True and type(method).__name__ in ('DeleteMessage','DeleteMessages') and isinstance(chat_id,int) and chat_id > 0:
            ids = ([method.message_id] if type(method).__name__=='DeleteMessage' else method.message_ids)
            await self.forget(chat_id,ids)
        return result

    def install(self, bot):
        if getattr(bot.session,'_sutech_chat_screens',None) is not self:
            bot.session.middleware.register(self.request)
            bot.session._sutech_chat_screens = self


screens = ChatScreens()


def is_navigation(message, raw_state=None):
    from bot.ai_i18n import AI_STRINGS
    from bot.i18n import t
    from bot.handlers.chat_planner import PLAN_BUTTON
    labels = {t(lang,key) for lang in ('ru','kz','en') for key in
              ('btn_fields','btn_history','btn_lang','btn_about','btn_help','btn_webapp','btn_more','btn_back')}
    labels.update(value for copy in AI_STRINGS.values() for key,value in copy.items()
                  if key.endswith('_button') and isinstance(value,str))
    labels.update(copy['button'] for copy in AI_STRINGS.values())
    labels.update(PLAN_BUTTON.values())
    return (bool(message.web_app_data) or (message.text or '').startswith('/')
            or message.text in labels or raw_state == 'ChatPlan:collecting')


class ChatScreenMiddleware(BaseMiddleware):
    def __init__(self, controller=screens):
        self.controller = controller

    async def __call__(self, handler, update, data):
        message = update.message
        callback = update.callback_query
        target = message or (callback.message if callback else None)
        user = message.from_user if message else callback.from_user if callback else None
        if not isinstance(target,Message) or not user or target.chat.type != 'private' or target.chat.id != user.id:
            return await handler(update,data)
        bot = data['bot']
        self.controller.install(bot)
        await self.controller.remember(user.id,target.message_id,
            'user' if message else 'bot',int(target.date.timestamp()))
        navigation = bool(callback) or is_navigation(target,data.get('raw_state'))
        async with self.controller.screen(user.id,navigation):
            try:
                return await handler(update,data)
            except ScreenSuperseded:
                return None
