"""Every crop must obey greenhouse applicability, including the separate rice routine."""
import unittest

from bot.water_balance import CROPS, calculate_balance, parse_field
from bot.balance_report import format_balance_explanation, format_balance_report


class GreenhouseApplicability(unittest.TestCase):
    def test_unsupported_reports_have_no_volume_or_economic_claims(self):
        for crop in ('rice', 'tomato'):
            field = parse_field(dict(balance_version=2, crop=crop, soil_type='loam',
                                     irrigation_type='drip', area=.1, area_unit='hectare',
                                     day_of_growth=20, moisture_condition='dry',
                                     field_type='greenhouse', greenhouse_medium='substrate',
                                     power_price=25, pump_power_kw=2, pump_productivity_m3h=20))
            result = calculate_balance(field, 6, 0)
            for lang in ('ru', 'kz', 'en'):
                for formatter in (format_balance_report, format_balance_explanation):
                    with self.subTest(crop=crop, lang=lang, formatter=formatter.__name__):
                        text = formatter(lang, field, result, {'date': '2026-11-17'})
                        self.assertNotIn('m³', text)
                        self.assertNotIn('м³', text)
                        self.assertNotIn('100%', text)
                        self.assertNotIn('100 %', text)
                        self.assertIn('минвата' if lang in ('ru', 'kz') else 'rockwool', text)

    def test_all_crops_obey_the_same_greenhouse_limits(self):
        greenhouse_cases = [
            ('soil', 'no', None, None), ('soil', 'no', 0, None), ('soil', 'no', 2.5, None),
            ('soil', 'yes', None, 'heated_needs_measurement'),
            ('soil', 'yes', 0, None), ('soil', 'yes', 2.5, None),
            ('substrate', 'no', None, 'substrate'), ('substrate', 'no', 0, 'substrate'),
            ('substrate', 'no', 2.5, 'substrate'), ('substrate', 'yes', None, 'substrate'),
            ('substrate', 'yes', 0, 'substrate'), ('substrate', 'yes', 2.5, 'substrate'),
        ]
        cases = [('greenhouse', *case) for case in greenhouse_cases]
        cases += [('open', medium, heated, measured, None)
                  for medium, heated, measured, _ in greenhouse_cases]
        for crop in [*CROPS, 'rice', 'other']:
            for field_type, medium, heated, measured, reason in cases:
                with self.subTest(crop=crop, field_type=field_type, medium=medium,
                                  heated=heated, measured=measured):
                    p = dict(balance_version=2, crop=crop, soil_type='loam',
                             irrigation_type='drip', area=.1, area_unit='hectare',
                             day_of_growth=20, moisture_condition='dry', field_type=field_type,
                             greenhouse_medium=medium, greenhouse_heated=heated,
                             greenhouse_et0=measured, custom_kc=.9,
                             custom_root_depth=.5, custom_p=.4)
                    result = calculate_balance(parse_field(p), 6, 10)
                    if reason:
                        self.assertEqual(result['status'], 'unsupported')
                        self.assertEqual(result['unsupported_reason'], reason)
                        self.assertEqual(result['net_m3'], 0)
                        self.assertEqual(result['gross_m3'], 0)
                    else:
                        self.assertNotEqual(result['status'], 'unsupported')
