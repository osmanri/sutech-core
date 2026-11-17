"""Salinity (plan step 1.3): leaching requirement FAO-29 eq. 9, yield loss FAO-56 Table 23. Nothing is invented without a measurement."""
import unittest

from bot.water_balance import SALT_TOLERANCE, BalanceInputError, calculate_balance, parse_field


def field(**changes):
    data = dict(balance_version=2, crop='corn', soil_type='loam', irrigation_type='drip', area=1, area_unit='hectare',
                day_of_growth=60, moisture_condition='dry')
    data.update(changes)
    return parse_field(data)


class Salinity(unittest.TestCase):
    def test_table_23_values_for_the_crops(self):
        self.assertEqual(SALT_TOLERANCE['cotton'], (7.7, 5.2))
        self.assertEqual(SALT_TOLERANCE['corn'], (1.7, 12.0))
        self.assertEqual(SALT_TOLERANCE['wheat'], (6.0, 7.1))
        self.assertNotIn('melon', SALT_TOLERANCE)   # the book gives no value for melons

    def test_fao29_example_3_maize_leaching_requirement(self):
        # FAO-29 Example 3: ECw 1.2 dS/m, ECe 1.7 dS/m (100 % yield) -> LR = 0.16
        r = calculate_balance(field(water_ec=1.2, irrigation_type='drip'), 6, 0)
        self.assertAlmostEqual(r['leaching_fraction'], 1.2 / (5 * 1.7 - 1.2), places=12)
        self.assertAlmostEqual(r['leaching_fraction'], 0.1644, places=4)

    def test_extra_water_only_when_losses_do_not_already_leach(self):
        plain = calculate_balance(field(), 6, 0)
        drip = calculate_balance(field(water_ec=1.2), 6, 0)       # drip loses 10 % < LR 16.4 %: extra water needed
        furrow_plain = calculate_balance(field(irrigation_type='furrow'), 6, 0)
        furrow = calculate_balance(field(irrigation_type='furrow', water_ec=1.2), 6, 0)  # furrow loses 50 % > LR: nothing extra
        self.assertAlmostEqual(drip['gross_m3'] / plain['gross_m3'], .9 / (1 - 1.2 / 7.3), places=9)
        self.assertEqual(furrow['gross_m3'], furrow_plain['gross_m3'])

    def test_tolerant_crop_with_good_water_needs_nothing_extra(self):
        base = field(crop='cotton')
        r = calculate_balance(field(crop='cotton', water_ec=3.0), 6, 0)   # LR 0.0845 < drip loss 0.10
        self.assertAlmostEqual(r['leaching_fraction'], 3.0 / (5 * 7.7 - 3.0))
        self.assertEqual(r['gross_m3'], calculate_balance(base, 6, 0)['gross_m3'])

    def test_water_too_salty_is_flagged_not_computed(self):
        for ec in (8.5, 9.0):
            r = calculate_balance(field(water_ec=ec), 6, 0)
            self.assertTrue(r['leaching_impossible'])
            self.assertIsNone(r['leaching_fraction'])

    def test_salt_yield_loss_from_measured_ece(self):
        self.assertAlmostEqual(calculate_balance(field(soil_ec=4.7), 6, 0)['salinity_yield_loss_pct'], 12.0 * (4.7 - 1.7))
        self.assertEqual(calculate_balance(field(crop='cotton', soil_ec=7.0), 6, 0)['salinity_yield_loss_pct'], 0.0)
        self.assertEqual(calculate_balance(field(soil_ec=50), 6, 0)['salinity_yield_loss_pct'], 100.0)

    def test_nothing_invented_without_measurement(self):
        r = calculate_balance(field(is_saline='yes'), 6, 0)
        self.assertIsNone(r['leaching_fraction'])
        self.assertIsNone(r['salinity_yield_loss_pct'])
        self.assertEqual(r['gross_m3'], calculate_balance(field(), 6, 0)['gross_m3'])
        melon = calculate_balance(field(crop='melon', water_ec=2.0, soil_ec=3.0), 6, 0)
        self.assertIsNone(melon['leaching_fraction'])
        self.assertIsNone(melon['salinity_yield_loss_pct'])

    def test_inputs_are_validated(self):
        for key, value in (('water_ec', -1), ('water_ec', 26), ('soil_ec', 51), ('water_ec', 'abc')):
            with self.assertRaises(BalanceInputError):
                field(**{key: value})


if __name__ == '__main__':
    unittest.main()


class SalinityReport(unittest.TestCase):
    def test_notes_only_from_measurements_in_all_languages(self):
        from bot.balance_report import salinity_notes
        f = field(water_ec=1.2, soil_ec=4.7)
        r = calculate_balance(f, 6, 0)
        for lang in ('ru', 'kz', 'en'):
            text = salinity_notes(lang, f, r)
            self.assertIn('16.44', text)
            self.assertIn('36', text)
        plain = field()
        self.assertEqual(salinity_notes('en', plain, calculate_balance(plain, 6, 0)), '')
        salty = field(water_ec=9)
        self.assertIn('9', salinity_notes('en', salty, calculate_balance(salty, 6, 0)))
