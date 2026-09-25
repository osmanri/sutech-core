"""Regression checks for the bot's farmer-facing actions and math."""

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.balance_weather import fetch_daily_weather
from bot.balance_report import format_balance_explanation, format_balance_report
from bot.handlers.fields import (_render_field_card, callback_add_field_start,
                                 callback_delete_field, callback_export_csv, callback_update_field)
from bot.keyboards.fields_kb import get_field_delete_confirmation_keyboard, get_fields_list_keyboard
from bot.keyboards.inline import get_report_inline_keyboard
from bot.schemas.field import CropType, FieldResponse, IrrigationMethod, IrrigationStatus, SoilType
from bot.services.field_manager import FieldService
from bot.states.field_states import FieldCallback
from bot.water_balance import calculate_balance, parse_field
from test_water_balance import payload


class BotAuditTests(unittest.IsolatedAsyncioTestCase):
    def _record(self, deficit):
        return {
            "id": 7, "user_id": 42, "name": "Песчаное поле", "crop_type": "cotton",
            "soil_type": "sand", "irrigation_method": "furrow", "area_ha": 1,
            "planting_date": date.today().isoformat(), "accumulated_deficit": deficit,
            "latitude": 44.85, "longitude": 65.49, "timezone": "Asia/Qyzylorda",
        }

    def test_saved_field_card_uses_raw_and_technology_threshold(self):
        field = parse_field(payload(crop="cotton", soil_type="sand",
                                    irrigation_type="furrow", day_of_growth=0))
        with patch("bot.services.field_manager.field_input_from_record", return_value=field):
            below = FieldService._map_record_to_dto(self._record(10))
            at_raw = FieldService._map_record_to_dto(self._record(11.375))
            stressed = FieldService._map_record_to_dto(self._record(12))
        self.assertEqual(below.current_status, IrrigationStatus.NORMAL)
        self.assertEqual(at_raw.current_status, IrrigationStatus.IRRIGATE)
        self.assertEqual(stressed.current_status, IrrigationStatus.CRITICAL)
        self.assertEqual(stressed.recommended_volume_m3, Decimal("240.00"))

    def test_field_name_is_escaped_in_html_card(self):
        field = FieldResponse(
            id=7, user_id=42, name="Поле <b>&", crop_type=CropType.COTTON,
            soil_type=SoilType.SAND, irrigation_method=IrrigationMethod.FURROW,
            area_ha=1, latitude=44.85, longitude=65.49,
            planting_date=date.today(), current_status=IrrigationStatus.NORMAL,
        )
        card = _render_field_card(field, "Район <опасный>")
        self.assertIn("Поле &lt;b&gt;&amp;", card)
        self.assertIn("Район &lt;опасный&gt;", card)

    def test_add_field_button_opens_full_webapp_form(self):
        button = get_fields_list_keyboard([], "kz").inline_keyboard[0][0]
        self.assertIsNotNone(button.web_app)
        self.assertIn("lang=kz", button.web_app.url)
        self.assertIsNone(button.callback_data)

    def test_english_webapp_result_and_bot_buttons_stay_in_english(self):
        field = parse_field(payload(crop="wheat", soil_type="loam"))
        result = calculate_balance(field, 5, 0)
        weather = {"date": date.today().isoformat(), "timezone": "Asia/Qyzylorda"}
        report = format_balance_report("en", field, result, weather)
        explanation = format_balance_explanation("en", field, result, weather)
        self.assertIn("<b>STATUS:</b>", report)
        self.assertIn("How was this calculated?", explanation)
        buttons = get_report_inline_keyboard("en", "abc", 7).inline_keyboard
        self.assertIn("Why this result?", buttons[0][0].text)
        self.assertIn("lang=en", buttons[1][-1].web_app.url)
        self.assertEqual(get_fields_list_keyboard([], "en").inline_keyboard[0][0].text,
                         "➕ Add field")

    async def test_weather_outage_never_invents_et0_or_rain(self):
        with patch("bot.balance_weather.aiohttp.ClientSession", side_effect=ConnectionError("offline")):
            with self.assertRaises(ConnectionError):
                await fetch_daily_weather(44.85, 65.49)

    async def test_update_callback_acknowledges_once_on_success_and_failure(self):
        callback = SimpleNamespace(data="field:update:7", from_user=SimpleNamespace(id=42),
                                   message=None, answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        field = SimpleNamespace(latitude=44.85, longitude=65.49)
        with patch("bot.handlers.fields.FieldService.update_balance_today",
                   AsyncMock(return_value=(field, {}))), patch(
                   "bot.handlers.fields.get_field_location_name", AsyncMock(return_value="Поле")), patch(
                   "bot.handlers.fields._render_field_card", return_value="Card"):
            await callback_update_field(callback, state)
        self.assertEqual(callback.answer.await_count, 1)

        callback.answer.reset_mock()
        with patch("bot.handlers.fields.FieldService.update_balance_today",
                   AsyncMock(side_effect=ConnectionError("offline"))):
            await callback_update_field(callback, state)
        self.assertEqual(callback.answer.await_count, 1)

    async def test_empty_export_acknowledges_callback_once(self):
        callback = SimpleNamespace(data="field:export:7", from_user=SimpleNamespace(id=42),
                                   message=None, answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        with patch("bot.handlers.fields.FieldService.get_field_by_id",
                   AsyncMock(return_value=SimpleNamespace(id=7))), patch(
                   "bot.handlers.fields.FieldService.get_journal_records", AsyncMock(return_value=[])):
            await callback_export_csv(callback, state)
        self.assertEqual(callback.answer.await_count, 1)

    async def test_legacy_add_callback_does_not_start_guessing_field_data(self):
        callback = SimpleNamespace(from_user=SimpleNamespace(id=42), message=None,
                                   answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock(), set_state=AsyncMock())
        with patch("bot.handlers.fields.get_lang", return_value="ru"):
            await callback_add_field_start(callback, state)
        state.clear.assert_awaited_once()
        state.set_state.assert_not_awaited()
        callback.answer.assert_awaited_once()

    async def test_delete_requires_separate_confirmation_tap(self):
        callback = SimpleNamespace(from_user=SimpleNamespace(id=42), message=None,
                                   answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        field = SimpleNamespace(id=7, name="Поле")
        with patch("bot.handlers.fields.get_lang", return_value="ru"), patch(
             "bot.handlers.fields.FieldService.get_field_by_id", AsyncMock(return_value=field)), patch(
             "bot.handlers.fields.FieldService.delete_field", AsyncMock()) as delete:
            await callback_delete_field(callback, FieldCallback(action="delete", field_id=7), state)
        delete.assert_not_awaited()
        callback.answer.assert_awaited_once()
        buttons = get_field_delete_confirmation_keyboard(7).inline_keyboard[0]
        self.assertIn("delete_confirm", buttons[0].callback_data)
        self.assertIn("view", buttons[1].callback_data)


if __name__ == "__main__":
    unittest.main()
