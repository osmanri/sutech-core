"""Greenhouse honesty (plan step 1.4): no advice for substrate or a heated greenhouse without a measured ET0."""
import unittest

from bot.balance_report import format_balance_report
from bot.water_balance import BalanceInputError, calculate_balance, parse_field


def field(**changes):
    data = dict(balance_version=2, crop='tomato', soil_type='loam', irrigation_type='drip', area=0.1, area_unit='hectare',
                day_of_growth=60, moisture_condition='dry', field_type='greenhouse')
    data.update(changes)
    return parse_field(data)


class GreenhouseHonesty(unittest.TestCase):
    def test_unheated_soil_greenhouse_gets_the_estimate(self):
        r = calculate_balance(field(), 6, 0)
        self.assertNotEqual(r['status'], 'unsupported')
        self.assertIsNone(r['unsupported_reason'])
        self.assertGreater(r['gross_m3'], 0)

    def test_substrate_gets_no_advice(self):
        r = calculate_balance(field(greenhouse_medium='substrate'), 6, 0)
        self.assertEqual((r['status'], r['unsupported_reason'], r['gross_m3'], r['net_m3']), ('unsupported', 'substrate', 0.0, 0.0))

    def test_heated_needs_a_measured_et0(self):
        r = calculate_balance(field(greenhouse_heated='yes'), 0.6, 0)
        self.assertEqual((r['status'], r['unsupported_reason'], r['gross_m3']), ('unsupported', 'heated_needs_measurement', 0.0))
        measured = calculate_balance(field(greenhouse_heated='yes', greenhouse_et0=2.5), 0.6, 0)
        self.assertNotEqual(measured['status'], 'unsupported')
        self.assertGreater(measured['gross_m3'], 0)

    def test_open_field_ignores_greenhouse_settings(self):
        r = calculate_balance(field(field_type='open', greenhouse_medium='substrate', greenhouse_heated='yes'), 6, 0)
        self.assertNotEqual(r['status'], 'unsupported')

    def test_invalid_values_are_refused(self):
        for key, value in (('greenhouse_medium', 'peat'), ('greenhouse_heated', 'maybe'), ('greenhouse_heated', True)):
            with self.assertRaises(BalanceInputError):
                field(**{key: value})

    def test_decision_card_explains_why_in_all_languages(self):
        for kwargs, word in ((dict(greenhouse_medium='substrate'), 'rockwool'), (dict(greenhouse_heated='yes'), 'Heated')):
            f = field(**kwargs)
            r = calculate_balance(f, 6, 0)
            en = format_balance_report('en', f, r, {'date': '2026-01-15', 'timezone': 'Asia/Almaty'})
            self.assertIn(word, en)
            self.assertIn('No irrigation advice', en)
            for lang in ('ru', 'kz'):
                self.assertTrue(format_balance_report(lang, f, r, {'date': '2026-01-15', 'timezone': 'Asia/Almaty'}))


if __name__ == '__main__':
    unittest.main()
