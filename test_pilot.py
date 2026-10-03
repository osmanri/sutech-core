import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from aiogram import Bot
from aiogram.types import Message, Chat, User, Update
from bot import db
from bot import pilot_store as store
from bot.handlers import pilot
from bot.keyboards.inline import get_report_inline_keyboard
from test_bot_platform import shared_test_dispatcher


class PilotTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.patches=[patch.object(db,'DB_PATH',str(Path(self.directory.name)/'pilot.db')),
                      patch.object(db,'DATABASE_URL',''),patch.dict('os.environ',{'DATABASE_URL':''})]
        for p in self.patches:p.start()
        db.init_db()
        self.report=db.save_report_explanation(10,'Calculation explanation')

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.directory.cleanup()

    def callback(self,data,user=10):
        return SimpleNamespace(data=data,from_user=SimpleNamespace(id=user),answer=AsyncMock(),
            message=SimpleNamespace(chat=SimpleNamespace(id=user,type='private'),
                reply_markup=get_report_inline_keyboard('ru',self.report),
                edit_text=AsyncMock(),edit_reply_markup=AsyncMock(),answer=AsyncMock()))

    def test_restart_keeps_participation_and_one_vote_per_report(self):
        store.join_pilot(10,'ru');store.join_pilot(10,'kz')
        self.assertTrue(store.save_feedback(10,self.report,True))
        self.assertTrue(store.save_feedback(10,self.report,False))
        db.init_db()
        self.assertEqual(store.pilot_status(10),{'joined':True,'reviews':1,'useful':0})
        self.assertEqual(store.pilot_summary(),{'applications':1,'participants_with_feedback':1,'rated_reports':1,'helpful_reports':0})

    def test_foreign_and_missing_reports_cannot_be_rated(self):
        self.assertFalse(store.save_feedback(11,self.report,True))
        self.assertFalse(store.save_feedback(10,'f'*32,True))
        self.assertEqual(store.pilot_status(11)['reviews'],0)

    def test_non_participants_do_not_inflate_pilot_summary(self):
        store.save_feedback(10,self.report,True)
        self.assertEqual(store.pilot_summary()['participants_with_feedback'],0)
        self.assertEqual(store.pilot_summary()['rated_reports'],0)

    def test_leaving_only_deletes_own_participation_and_feedback(self):
        other=db.save_report_explanation(11,'Other calculation')
        for uid,rid in [(10,self.report),(11,other)]:
            store.join_pilot(uid,'ru');store.save_feedback(uid,rid,True)
        store.leave_pilot(10)
        self.assertEqual(store.pilot_status(10),{'joined':False,'reviews':0,'useful':0})
        self.assertTrue(store.pilot_status(11)['joined'])
        self.assertEqual(db.get_report_explanation(self.report,10),'Calculation explanation')

    async def test_votes_update_keyboard_without_sending_new_messages(self):
        callback=self.callback('pilot:vote:y:'+self.report)
        with patch.object(pilot,'get_lang',return_value='kz'):
            await pilot.rate_report(callback)
        self.assertEqual(store.pilot_status(10)['useful'],1)
        callback.message.answer.assert_not_awaited()
        callback.message.edit_text.assert_not_awaited()
        changed=callback.message.edit_reply_markup.call_args.kwargs['reply_markup']
        self.assertEqual(changed.inline_keyboard[-1][0].text,'✓ Пайдалы')
        self.assertEqual(changed.inline_keyboard[0][0].callback_data,'explain:'+self.report)

    async def test_foreign_vote_does_not_change_markup(self):
        callback=self.callback('pilot:vote:y:'+self.report,user=11)
        with patch.object(pilot,'get_lang',return_value='en'):
            await pilot.rate_report(callback)
        callback.message.edit_reply_markup.assert_not_awaited()
        self.assertTrue(callback.answer.call_args.kwargs['show_alert'])

    async def test_group_votes_are_rejected_before_persistence(self):
        callback=self.callback('pilot:vote:y:'+self.report)
        callback.message.chat.type='group'
        with patch.object(pilot,'save_feedback') as save,patch.object(pilot,'get_lang',return_value='ru'):
            await pilot.rate_report(callback)
        save.assert_not_called()

    async def test_deletion_requires_confirmation_screen(self):
        store.join_pilot(10,'ru')
        callback=self.callback('pilot:leave')
        with patch.object(pilot,'get_lang',return_value='ru'):
            await pilot.pilot_action(callback)
        self.assertTrue(store.pilot_status(10)['joined'])
        self.assertIn('pilot:delete',str(callback.message.edit_text.call_args.kwargs['reply_markup']))

    async def test_failed_storage_never_claims_success(self):
        callback=self.callback('pilot:vote:y:'+self.report)
        with patch.object(pilot,'save_feedback',side_effect=RuntimeError('unavailable')),patch.object(pilot,'get_lang',return_value='en'):
            await pilot.rate_report(callback)
        self.assertIn('Could not save',callback.answer.call_args.args[0])
        callback.message.edit_reply_markup.assert_not_awaited()

    async def test_deep_link_reaches_localized_invitation_and_does_not_enroll(self):
        bot=Bot(token='123456:TEST')
        dispatcher=shared_test_dispatcher()
        try:
            for language in ['ru','kz','en']:
                message=Message(message_id=1,date=datetime.now(timezone.utc),chat=Chat(id=10,type='private'),
                    from_user=User(id=10,is_bot=False,first_name='Pilot'),text='/start pilot_'+language)
                with patch.object(Bot,'__call__',new_callable=AsyncMock) as transport:
                    await dispatcher.feed_update(bot,Update(update_id=1,message=message))
                sent=[call.args[0] for call in transport.await_args_list if type(call.args[0]).__name__=='SendMessage']
                self.assertEqual(len(sent),1)
                self.assertIn(pilot.pilot_text(language,'invite'),sent[0].text)
                self.assertEqual(sent[0].reply_markup.inline_keyboard[0][0].callback_data,'pilot:join')
                self.assertFalse(store.pilot_status(10)['joined'])
        finally:await bot.session.close()

    def test_markup_is_localized_and_within_telegram_limits(self):
        for language in ['ru','kz','en']:
            keyboard=get_report_inline_keyboard(language,self.report)
            for row in keyboard.inline_keyboard:
                for button in row:
                    if button.callback_data:self.assertLessEqual(len(button.callback_data.encode()),64)
            self.assertIn(pilot.pilot_text(language,'useful'),keyboard.inline_keyboard[-1][0].text)


if __name__=='__main__':unittest.main()
