"""Daily farmer screens stay dated, localized and reversible."""
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch
from bot import db
from bot.handlers import fields, webapp
from bot.keyboards.inline import get_report_inline_keyboard
from bot.states.field_states import FieldCallback
from bot.field_state import get_field
import test_bot_platform as platform_fixture
import test_field_refresh as refresh_fixture


class FarmerUXTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = refresh_fixture.SavedFieldRefreshTests.asyncSetUp
    asyncTearDown = refresh_fixture.SavedFieldRefreshTests.asyncTearDown
    save_field = refresh_fixture.SavedFieldRefreshTests.save_field
    transport = refresh_fixture.SavedFieldRefreshTests.transport
    callback = refresh_fixture.SavedFieldRefreshTests.callback
    edits = refresh_fixture.SavedFieldRefreshTests.edits

    async def test_overview_is_dated_and_details_keep_export_and_delete_available(self):
        for lang in ('ru','kz','en'):
            self.methods.clear()
            with patch.object(fields,'get_lang',return_value=lang), \
                    patch.object(fields,'get_field_location_name',new=AsyncMock(return_value='Village')) as geocode:
                await fields.callback_view_field(self.callback(f'field:view:{self.field_id}'),
                    FieldCallback(action='view',field_id=self.field_id),self.state)
                geocode.assert_not_awaited()
                overview=self.edits()[-1]
                self.assertIn(date.today().strftime('%d.%m.%Y'),overview.text)
                self.assertNotIn('RAW',overview.text)
                self.assertNotIn('TAW',overview.text)
                buttons={b.callback_data for row in overview.reply_markup.inline_keyboard for b in row}
                self.assertIn(f'field:details:{self.field_id}',buttons)
                self.assertNotIn(f'field:delete:{self.field_id}',buttons)
                await fields.callback_view_field(self.callback(f'field:details:{self.field_id}'),
                    FieldCallback(action='details',field_id=self.field_id),self.state)
                details=self.edits()[-1]
                self.assertIn('FAO-56',details.text)
                buttons={b.callback_data for row in details.reply_markup.inline_keyboard for b in row}
                for action in ('export','delete','view'):
                    self.assertIn(f'field:{action}:{self.field_id}',buttons)
                await fields.callback_view_field(self.callback(f'field:view:{self.field_id}'),
                    FieldCallback(action='view',field_id=self.field_id),self.state)
            self.assertFalse(any(type(m).__name__=='SendMessage' for m in self.methods))

    async def test_explanation_and_back_preserve_result_and_actions_without_extra_messages(self):
        for lang in ('ru','kz','en'):
            self.methods.clear()
            report_id=db.save_report_explanation(self.user.id,'<b>FAO-56</b>\nTAW / RAW')
            markup=get_report_inline_keyboard(lang,report_id,self.field_id)
            callback=self.callback(f'explain:{report_id}')
            message=callback.message.model_copy(update={'text':'20 m³ · 07.10.2026','reply_markup':markup}).as_(self.bot)
            callback=callback.model_copy(update={'message':message}).as_(self.bot)
            before=get_field(self.field_id)
            with patch.object(webapp,'get_lang',return_value=lang):
                await webapp.explain_report(callback,self.state)
                details=self.edits()[-1]
                self.assertEqual(details.message_id,message.message_id)
                back=details.reply_markup.inline_keyboard[0][0].callback_data
                self.assertTrue(back.startswith('explain_back:'))
                await webapp.return_to_result(self.callback(back),self.state)
            restored=self.edits()[-1]
            self.assertEqual(restored.text,message.html_text)
            self.assertEqual(restored.reply_markup,markup)
            self.assertFalse(any(type(m).__name__=='SendMessage' for m in self.methods))
            self.assertEqual(get_field(self.field_id),before)
            self.assertEqual(await self.state.get_data(),{})
            self.methods.clear()
            await webapp.return_to_result(self.callback(back),self.state)
            self.assertFalse(self.edits())

    async def test_irrigation_confirmation_returns_to_overview_with_updated_balance(self):
        with patch.object(fields,'get_field_location_name',new=AsyncMock()) as geocode:
            await fields.callback_confirm_water(self.callback(f'field:confirm-watered:{self.field_id}'),self.state)
        geocode.assert_not_awaited()
        self.assertEqual(get_field(self.field_id)['accumulated_deficit'],0)
        self.assertIn('Полив записан',self.edits()[-1].text)
        self.assertNotIn('RAW',self.edits()[-1].text)

    async def test_real_dispatcher_routes_field_details(self):
        from aiogram.types import Update
        dp=platform_fixture.shared_test_dispatcher()
        with patch.object(fields,'get_field_location_name',new=AsyncMock(return_value='Village')):
            await dp.feed_update(self.bot,Update(update_id=988,callback_query=self.callback(f'field:details:{self.field_id}')))
        self.assertIn('FAO-56',self.edits()[-1].text)


if __name__=='__main__':
    unittest.main()
