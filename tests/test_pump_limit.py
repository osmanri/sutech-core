"""Pump daily limit: a volume above one day of pumping is split over several days (plan step 1.1)."""
import math
import unittest

from bot.balance_report import pump_limit_note
from bot.water_balance import PUMP_MAX_HOURS_PER_DAY, calculate_balance, calculate_economics, parse_field


def payload(**changes):
    base = dict(balance_version=2, crop='cotton', soil_type='loam', irrigation_type='drip', area=10, area_unit='hectare',
                day_of_growth=90, moisture_condition='dry', pump_power_kw=22, pump_productivity_m3h=60, power_price=25)
    base.update(changes)
    return base


class PumpLimit(unittest.TestCase):
    def test_ten_hectares_needs_several_days(self):
        # Hand-checked in the agronomy review: 10 ha cotton on drip, dry soil, ET0 7 mm -> about 15 543 m3, 259 h of pumping.
        r = calculate_balance(parse_field(payload()), 7, 0)
        self.assertAlmostEqual(r['gross_m3'], 15543.0, delta=1)
        self.assertEqual(r['max_daily_m3'], 60 * PUMP_MAX_HOURS_PER_DAY)
        self.assertEqual(r['irrigation_days'], math.ceil(r['gross_m3'] / 1200))
        self.assertEqual(r['irrigation_days'], 13)
        self.assertLessEqual(r['gross_m3'] / r['irrigation_days'], r['max_daily_m3'])

    def test_exactly_one_day_of_pumping_is_one_day(self):
        eco = calculate_economics(1200, 100, 1, 25, 22, 60)
        self.assertEqual(eco['irrigation_days'], 1)
        self.assertEqual(calculate_economics(1200.5, 100, 1, 25, 22, 60)['irrigation_days'], 2)

    def test_nothing_to_irrigate_is_zero_days(self):
        self.assertEqual(calculate_economics(0, 0, 1, 25, 22, 60)['irrigation_days'], 0)

    def test_unknown_pump_gives_no_limit(self):
        eco = calculate_economics(5000, 100, 1, None, 22, 60)
        self.assertIsNone(eco['max_daily_m3'])
        self.assertIsNone(eco['irrigation_days'])

    def test_warning_text_only_when_split(self):
        field = parse_field(payload())
        big = calculate_balance(field, 7, 0)
        for lang in ('ru', 'kz', 'en'):
            note = pump_limit_note(lang, big)
            self.assertIn('13', note)
            self.assertIn('1200', note.replace(' ', '').replace(' ', ''))
        small = calculate_balance(parse_field(payload(area=0.1)), 7, 0)
        self.assertEqual(pump_limit_note('en', small), '')


if __name__ == '__main__':
    unittest.main()
