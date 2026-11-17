import importlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.types import Message
from bot import db
from bot.handlers.webapp import calculate_water_demand, format_report_explanation, explain_report
from bot.keyboards.inline import get_report_inline_keyboard


class ExplanationTests(unittest.IsolatedAsyncioTestCase):
    def test_snapshot_persistence_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(db, 'DB_PATH', str(Path(directory) / 'test.db')):
                db.init_db()
                first = db.save_report_explanation(10, 'first result')
                second = db.save_report_explanation(10, 'second result')
                self.assertNotEqual(first, second)
                self.assertEqual(db.get_report_explanation(first, 10), 'first result')
                self.assertEqual(db.get_report_explanation(second, 10), 'second result')
                self.assertIsNone(db.get_report_explanation(first, 11))
                self.assertIsNone(db.get_report_explanation('missing', 10))
                db.init_db()  # Startup must preserve older reports.
                self.assertEqual(db.get_report_explanation(first, 10), 'first result')

    def test_localized_decisions_and_actual_volume(self):
        for lang in ('ru', 'kz'):
            for moisture in (.18, .25, .30):
                result = calculate_water_demand(28, moisture, 3.5, 550,
                    area_m2=67000, field_type='greenhouse', is_saline='yes')
                text = format_report_explanation(lang, 67000, moisture, result)
                self.assertNotIn('{', text)
                self.assertIn('67000', text)
                self.assertIn('Open-Meteo', text)
                self.assertIn('30%', text)
                self.assertLess(len(text), 4096)
                if moisture < .25:
                    self.assertIn('15%', text)
                    self.assertIn(str(result['total_liters'] / 1000), text)
                else:
                    self.assertIn('0 м³', text)
                    self.assertNotIn('15%', text)
                keyboard = get_report_inline_keyboard(lang, 'a' * 32)
                self.assertEqual(keyboard.inline_keyboard[0][0].callback_data, 'explain:' + 'a' * 32)
                self.assertLessEqual(len(keyboard.inline_keyboard[0][0].callback_data.encode()), 64)

    async def test_callback_answers_and_replies_to_original_report(self):
        message = Message(message_id=42, date=datetime.now(timezone.utc),
                          chat={'id': 10, 'type': 'private'})
        callback = SimpleNamespace(data='explain:abc', from_user=SimpleNamespace(id=10),
                                   message=message, answer=AsyncMock())
        with patch('bot.handlers.webapp.get_report_explanation', return_value='saved explanation') as get, \
             patch.object(Message, 'reply', new_callable=AsyncMock) as reply:
            await explain_report(callback)
        get.assert_called_once_with('abc', 10)
        callback.answer.assert_awaited_once_with()
        reply.assert_awaited_once_with('saved explanation', parse_mode='HTML')

    async def test_expired_or_foreign_report_shows_alert(self):
        callback = SimpleNamespace(data='explain:missing', from_user=SimpleNamespace(id=10),
                                   message=None, answer=AsyncMock())
        with patch('bot.handlers.webapp.get_report_explanation', return_value=None), \
             patch('bot.handlers.webapp.get_lang', return_value='ru'):
            await explain_report(callback)
        self.assertTrue(callback.answer.call_args.kwargs['show_alert'])


if __name__ == '__main__':
    unittest.main()
