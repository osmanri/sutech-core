"""Farmer decision cards keep measured units, warnings and detailed snapshots."""
import unittest
from dataclasses import replace
from html import unescape

from bot.balance_report import format_balance_report, format_balance_explanation, display_volume
from bot.i18n import t
from bot.keyboards.inline import get_report_inline_keyboard
from bot.water_balance import calculate_balance, parse_field
from test_water_balance import payload


class DecisionCardTests(unittest.TestCase):
    weather = {'date': '2026-10-07', 'timezone': 'Asia/Qyzylorda'}

    def test_each_decision_is_first_and_details_are_available_separately(self):
        for lang in ('ru', 'kz', 'en'):
            for deficit, expected in ((0, 'deferred'), (20, 'irrigate'), (150, 'critical')):
                field = replace(parse_field(payload(area=.1, power_price=25,
                    pump_power_kw=22, pump_productivity_m3h=60)), yesterday=deficit)
                result = calculate_balance(field, 0, 0)
                self.assertEqual(result['status'], expected)
                card = format_balance_report(lang, field, result, self.weather)
                self.assertEqual(card.splitlines()[0], '<b>' + t(lang, 'decision_' + expected) + '</b>')
                self.assertIn(display_volume(lang, result['gross_m3']), card)
                self.assertIn('07.10.2026', card)
                self.assertIn('Asia/Qyzylorda', card)
                self.assertIn('Open-Meteo', card)
                self.assertIn(t(lang, 'report_crop_wheat'), card)
                self.assertIn(t(lang, 'report_irrig_drip'), card)
                self.assertNotIn('{', card)
                self.assertLess(len(card), 850)
                for technical in ('RAW', 'TAW', 'Kc', 'кВт', 'kWh', '₸'):
                    self.assertNotIn(technical, card)
                detail = format_balance_explanation(lang, field, result, self.weather)
                for technical in ('RAW', 'TAW', 'Kc'):
                    self.assertIn(technical, detail)
                self.assertIn('40' if expected == 'irrigate' else '0' if expected == 'deferred' else '300', detail)
                self.assertLess(len(detail), 4096)

    def test_zero_volume_hides_water_confirmation_but_keeps_explanation(self):
        for lang in ('ru', 'kz', 'en'):
            keyboard = get_report_inline_keyboard(lang, 'a' * 32, 17, needs_irrigation=False)
            actions = {b.callback_data for row in keyboard.inline_keyboard for b in row}
            self.assertNotIn('field:watered:17', actions)
            self.assertIn('explain:' + 'a' * 32, actions)
            self.assertIn('fields:list', actions)
            positive = get_report_inline_keyboard(lang, 'a' * 32, 17, needs_irrigation=True)
            self.assertIn('field:watered:17', {b.callback_data for row in positive.inline_keyboard for b in row})

    def test_rice_replenishment_is_not_mixed_with_root_zone_irrigation(self):
        field = parse_field(payload(crop='rice', area=.1))
        for rain, expected in ((0, 'rice'), (100, 'rice_deferred')):
            result = calculate_balance(field, 5, rain)
            for lang in ('ru', 'kz', 'en'):
                card = format_balance_report(lang, field, result, self.weather)
                self.assertEqual(card.splitlines()[0], '<b>' + t(lang, 'decision_' + expected) + '</b>')
                self.assertIn(display_volume(lang, result['gross_m3']), card)
                self.assertNotIn('RAW', card)
                detail = format_balance_explanation(lang, field, result, self.weather)
                self.assertIn('12', detail)

    def test_small_positive_volumes_never_appear_as_zero(self):
        for lang in ('ru', 'kz', 'en'):
            for quantity in (.0000001, .0001, .5):
                displayed = unescape(display_volume(lang, quantity))
                self.assertFalse(displayed.startswith('0 ') or displayed.startswith('0 м'))
                self.assertTrue(displayed.endswith('L' if lang == 'en' else 'л'))
            self.assertEqual(display_volume(lang, 0), '0 m³' if lang == 'en' else '0 м³')
        self.assertEqual(display_volume('ru', 22.2222), '22,22 м³')
        self.assertEqual(display_volume('en', 22.2222), '22.22 m³')

    def test_salinity_and_greenhouse_context_are_not_lost(self):
        field = parse_field(payload(field_type='greenhouse', is_saline='yes', moisture_condition='dry'))
        result = calculate_balance(field, 5, 100)
        for lang in ('ru', 'kz', 'en'):
            card = format_balance_report(lang, field, result, self.weather)
            detail = format_balance_explanation(lang, field, result, self.weather)
            self.assertIn(t(lang, 'decision_saline'), card)
            self.assertIn(t(lang, 'decision_greenhouse'), card)
            self.assertIn(t(lang, 'balance_salinity'), detail)
            self.assertIn(t(lang, 'balance_greenhouse'), detail)
            self.assertNotIn(t(lang, 'decision_reason_rain'), card)

    def test_rain_reason_only_appears_when_effective_rain_is_counted(self):
        field = parse_field(payload())
        result = calculate_balance(field, 1, 30)
        self.assertEqual(result['status'], 'deferred')
        for lang in ('ru', 'kz', 'en'):
            self.assertIn(t(lang, 'decision_reason_rain'), format_balance_report(lang, field, result, self.weather))

    def test_displayed_date_and_timezone_are_escaped_and_never_invented(self):
        field = parse_field(payload())
        result = calculate_balance(field, 0, 0)
        card = format_balance_report('ru', field, result, {'date': '<old>', 'timezone': '<zone>'})
        self.assertIn('&lt;old&gt;', card)
        self.assertIn('&lt;zone&gt;', card)


if __name__ == '__main__':
    unittest.main()
