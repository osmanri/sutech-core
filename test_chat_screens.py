"""Navigation replaces old chat screens without deleting saved farmer data."""
import asyncio
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import SendMessage, EditMessageText
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from bot import db, chat_screen_store as store
from bot.chat_screens import ChatScreens, ChatScreenMiddleware, ScreenSuperseded, is_navigation
from bot.i18n import t
from bot.ai_i18n import ai_text
from bot.services.agronomist import AgronomistService


def message(message_id, chat_id=10, text='Screen', bot=False, age=0):
    return Message(message_id=message_id,date=datetime.fromtimestamp(time.time()-age,timezone.utc),
        chat=Chat(id=chat_id,type='private'),text=text,
        from_user=User(id=99 if bot else chat_id,is_bot=bot,first_name='Farmer'))


class ChatScreenTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(db,'DB_PATH',str(Path(self.temp.name)/'screens.db')),
                        patch.object(db,'DATABASE_URL',''),patch.dict('os.environ',{'DATABASE_URL':''})]
        for p in self.patches:p.start()
        db.init_db()
        self.ui = ChatScreens()
        self.bot = SimpleNamespace(delete_messages=AsyncMock(return_value=True),
            delete_message=AsyncMock(return_value=True),edit_message_reply_markup=AsyncMock(return_value=True),
            send_message=AsyncMock(),session=SimpleNamespace(middleware=SimpleNamespace(register=lambda _:None)))

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    async def record(self,mid,kind='bot',chat=10,age=0):
        await self.ui.remember(chat,mid,kind,int(time.time()-age))

    def test_message_registry_survives_restart_and_never_touches_report_history(self):
        store.remember(10,1,'bot',int(time.time()))
        store.remember(11,1,'bot',int(time.time()))
        report=db.save_report_explanation(10,'Why this calculation')
        db.init_db()
        store.forget(10,[1])
        self.assertEqual(store.messages(10),{})
        self.assertIn(1,store.messages(11))
        self.assertEqual(db.get_report_explanation(report,10),'Why this calculation')

    def test_registry_is_bounded(self):
        for mid in range(1,store.MAX_MESSAGES+6):
            store.remember(10,mid,'bot',int(time.time()))
        self.assertEqual(len(store.messages(10)),store.MAX_MESSAGES)
        self.assertNotIn(1,store.messages(10))

    async def test_menu_replaces_all_old_bot_messages_and_user_button_text(self):
        await self.record(1);await self.record(2,'user');await self.record(3)
        await self.record(4,'user');await self.record(1,chat=11)
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(5,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='History'))
        self.bot.delete_messages.assert_awaited_once_with(chat_id=10,message_ids=[1,2,3,4])
        self.assertEqual(set(store.messages(10)),{5})
        self.assertEqual(set(store.messages(11)),{1})

    async def test_telegram_clock_ahead_does_not_leave_button_text(self):
        await self.record(1,'user',age=-3)
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(2,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='New screen'))
        self.bot.delete_messages.assert_awaited_once_with(chat_id=10,message_ids=[1])

    async def test_edit_keeps_the_current_card_and_removes_other_sections(self):
        await self.record(1);await self.record(2);await self.record(3,'user')
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(2,bot=True)),self.bot,
                                  EditMessageText(chat_id=10,message_id=2,text='My field'))
        self.bot.delete_messages.assert_awaited_once_with(chat_id=10,message_ids=[1,3])
        self.assertEqual(set(store.messages(10)),{2})

    async def test_plain_question_keeps_conversation_until_navigation(self):
        await self.record(1);await self.record(2,'user')
        async with self.ui.screen(10,False):
            await self.ui.request(AsyncMock(return_value=message(3,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='Agronomy answer'))
        self.bot.delete_messages.assert_not_awaited()
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(4,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='Main menu'))
        self.assertEqual(set(store.messages(10)),{4})

    async def test_failed_new_screen_does_not_erase_previous_screen(self):
        await self.record(1)
        send=SendMessage(chat_id=10,text='New screen')
        async with self.ui.screen(10,True):
            with self.assertRaises(TelegramNetworkError):
                await self.ui.request(AsyncMock(side_effect=TelegramNetworkError(send,'offline')),self.bot,send)
        self.bot.delete_messages.assert_not_awaited()
        self.assertEqual(set(store.messages(10)),{1})

    async def test_popup_without_render_does_not_clear_the_chat(self):
        await self.record(1)
        async with self.ui.screen(10,True):
            pass
        self.bot.delete_messages.assert_not_awaited()

    async def test_plain_navigation_screen_gets_a_localized_back_button(self):
        from bot.user_state import set_lang
        set_lang(10,'kz')
        render=AsyncMock(return_value=message(2,bot=True))
        async with self.ui.screen(10,True):
            await self.ui.request(render,self.bot,SendMessage(chat_id=10,text='Explanation'))
        markup=render.await_args.args[1].reply_markup
        self.assertEqual(markup.inline_keyboard[0][0].text,t('kz','btn_back'))
        self.assertEqual(markup.inline_keyboard[0][0].callback_data,'ui:home')

    async def test_expired_messages_lose_buttons_without_blocking_navigation(self):
        await self.record(1,age=49*3600);await self.record(2,'user',age=49*3600)
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(3,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='New screen'))
        self.bot.delete_messages.assert_not_awaited()
        self.bot.edit_message_reply_markup.assert_awaited_once()
        self.assertEqual(self.bot.edit_message_reply_markup.await_args.kwargs['message_id'],1)
        self.assertEqual(set(store.messages(10)),{3})

    async def test_delete_failure_retries_saved_ids_on_next_navigation(self):
        await self.record(1)
        self.bot.delete_messages.side_effect=TelegramNetworkError(SendMessage(chat_id=10,text='x'),'offline')
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(2,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='New screen'))
        self.assertEqual(set(store.messages(10)),{1,2})
        self.bot.delete_messages.side_effect=None
        async with self.ui.screen(10,True):
            await self.ui.request(AsyncMock(return_value=message(3,bot=True)),self.bot,
                                  SendMessage(chat_id=10,text='History'))
        self.assertEqual(set(store.messages(10)),{3})

    async def test_fast_navigation_cannot_deliver_an_older_response(self):
        old=SendMessage(chat_id=10,text='Old result');new=SendMessage(chat_id=10,text='History')
        async with self.ui.screen(10,True):
            async with self.ui.screen(10,True):
                await self.ui.request(AsyncMock(return_value=message(2,bot=True)),self.bot,new)
            request=AsyncMock()
            with self.assertRaises(ScreenSuperseded):
                await self.ui.request(request,self.bot,old)
            request.assert_not_awaited()

    async def test_slow_screen_restore_cannot_take_newer_navigation_generation(self):
        restoring=asyncio.Event();resume=asyncio.Event();reads=0
        async def read(function,*args):
            nonlocal reads
            reads+=1
            if reads==1:
                restoring.set()
                await resume.wait()
            return {}
        request=AsyncMock()
        async def old_navigation():
            async with self.ui.screen(10,True):
                with self.assertRaises(ScreenSuperseded):
                    await self.ui.request(request,self.bot,SendMessage(chat_id=10,text='Old'))
        with patch('bot.chat_screens.asyncio.to_thread',side_effect=read):
            task=asyncio.create_task(old_navigation())
            await restoring.wait()
            async with self.ui.screen(10,True):
                pass
            resume.set()
            await task
        request.assert_not_awaited()

    async def test_click_on_removed_card_renders_a_replacement(self):
        edit=EditMessageText(chat_id=10,message_id=1,text='Field details')
        self.bot.send_message.return_value=message(2,bot=True)
        async with self.ui.screen(10,True):
            result=await self.ui.request(AsyncMock(side_effect=TelegramBadRequest(edit,'message to edit not found')),self.bot,edit)
        self.assertEqual(result.message_id,2)
        self.bot.send_message.assert_awaited_once()

    async def test_repeated_button_still_cleans_other_old_messages(self):
        await self.record(1);await self.record(2)
        edit=EditMessageText(chat_id=10,message_id=1,text='Same screen')
        async with self.ui.screen(10,True):
            result=await self.ui.request(AsyncMock(side_effect=TelegramBadRequest(edit,'message is not modified')),self.bot,edit)
        self.assertEqual(result.message_id,1)
        self.bot.delete_messages.assert_awaited_once_with(chat_id=10,message_ids=[2])
        self.assertEqual(set(store.messages(10)),{1})

    async def test_real_session_middleware_tracks_message_results(self):
        bot=Bot('123456:TEST_TOKEN')
        self.ui.install(bot)
        try:
            with patch.object(bot.session,'make_request',new=AsyncMock(return_value=message(7,bot=True))):
                await bot.send_message(10,'Screen')
            self.assertIn(7,store.messages(10))
        finally:
            await bot.session.close()

    async def test_old_callback_is_tracked_and_group_chats_are_excluded(self):
        middleware=ChatScreenMiddleware(self.ui)
        private=message(4,bot=True)
        callback=CallbackQuery(id='a',from_user=User(id=10,is_bot=False,first_name='Farmer'),
                               chat_instance='x',message=private,data='fields:list')
        handler=AsyncMock(return_value='handled')
        self.assertEqual(await middleware(handler,Update(update_id=1,callback_query=callback),{'bot':self.bot}),'handled')
        self.assertIn(4,store.messages(10))
        group=private.model_copy(update={'chat':Chat(id=-10,type='group')})
        callback=callback.model_copy(update={'message':group})
        await middleware(handler,Update(update_id=2,callback_query=callback),{'bot':self.bot})
        self.assertEqual(store.messages(-10),{})

    def test_navigation_buttons_in_all_languages_and_regular_question(self):
        for lang in ('ru','kz','en'):
            for text in (t(lang,'btn_history'),t(lang,'btn_fields'),t(lang,'btn_back'),ai_text(lang,'button'),'/pilot'):
                self.assertTrue(is_navigation(message(1,text=text)))
        self.assertFalse(is_navigation(message(1,text='Why are tomato leaves yellow?')))

    async def test_production_menu_routes_leave_one_screen_in_each_language(self):
        from test_bot_platform import shared_test_dispatcher
        from bot.handlers import agronomist, start
        from bot.chat_screens import screens
        from bot import user_state
        dispatcher=shared_test_dispatcher()
        bot=Bot('123456:TEST_TOKEN')
        visible={};seq=100;received=1000;requests=[]
        client=SimpleNamespace(configured=True,generate=AsyncMock())
        service=AgronomistService(client)

        async def transport(bot,method,timeout=None):
            nonlocal seq
            name=type(method).__name__
            requests.append((name,getattr(method,'message_ids',None)))
            if name=='SendMessage':
                seq+=1
                result=message(seq,chat_id=method.chat_id,text=method.text,bot=True).as_(bot)
                visible[(method.chat_id,seq)]=result
                return result
            if name.startswith('EditMessage'):
                key=(method.chat_id,method.message_id)
                result=visible[key]
                if getattr(method,'text',None):result=result.model_copy(update={'text':method.text}).as_(bot)
                visible[key]=result
                return result
            if name=='DeleteMessages':
                for mid in method.message_ids:visible.pop((method.chat_id,mid),None)
            elif name=='DeleteMessage':visible.pop((method.chat_id,method.message_id),None)
            return True

        try:
            with patch.object(bot.session,'make_request',side_effect=transport), \
                 patch.object(agronomist,'assistant',service), \
                 patch.object(agronomist,'configure_user_menu',new_callable=AsyncMock), \
                 patch.object(start,'get_user_history',return_value=[]):
                for index,lang in enumerate(('ru','kz','en')):
                    uid=44001+index
                    user_state.set_lang(uid,lang)
                    screens.memory.pop(uid,None);screens.generations.pop(uid,None)
                    for text in ('/about',t(lang,'btn_fields'),t(lang,'btn_history'),
                                 ai_text(lang,'button'),t(lang,'btn_more'),t(lang,'btn_back'),'/pilot'):
                        received+=1
                        incoming=message(received,chat_id=uid,text=text)
                        visible[(uid,received)]=incoming
                        await dispatcher.feed_update(bot,Update(update_id=received,message=incoming))
                        owner_messages=[m for (chat,_),m in visible.items() if chat==uid]
                        self.assertEqual(len(owner_messages),1,(lang,text,[m.text for m in owner_messages],requests[-6:],store.messages(uid)))
                        self.assertTrue(owner_messages[0].from_user.is_bot)
            client.generate.assert_not_awaited()
        finally:
            await bot.session.close()


if __name__ == '__main__':unittest.main()
