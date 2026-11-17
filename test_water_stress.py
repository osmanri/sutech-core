"""FAO-56 water-stress coefficient Ks (eq. 84) in the production balance."""
import unittest
from dataclasses import replace

from bot.water_balance import CALCULATION_VERSION, calculate_balance, parse_field, stress_coefficient

# Wheat day 60 on loam: Zr = 1.25 m, p = 0.55 -> TAW = 187.5 mm, RAW = 103.125 mm.
PAYLOAD = dict(balance_version=2, crop='wheat', soil_type='loam', irrigation_type='drip', area=1,
               area_unit='hectare', day_of_growth=60, moisture_condition='dry')


class StressCoefficient(unittest.TestCase):
    def test_no_stress_up_to_raw(self):
        self.assertEqual(stress_coefficient(103.125, 187.5, 103.125, .55), 1.)
        self.assertEqual(stress_coefficient(0., 187.5, 103.125, .55), 1.)

    def test_hand_computed_value(self):
        # Ks = (187.5 - 150) / ((1 - 0.55) * 187.5) = 37.5 / 84.375 = 0.4444...
        self.assertAlmostEqual(stress_coefficient(150., 187.5, 103.125, .55), 37.5 / 84.375)

    def test_wilting_point_stops_water_use(self):
        self.assertEqual(stress_coefficient(187.5, 187.5, 103.125, .55), 0.)

    def test_balance_uses_ks(self):
        field = replace(parse_field(PAYLOAD), yesterday=150.)
        r = calculate_balance(field, 5., 0.)
        self.assertAlmostEqual(r['ks'], 37.5 / 84.375)
        self.assertAlmostEqual(r['etc'], 5. * 1.15 * 37.5 / 84.375)
        self.assertAlmostEqual(r['deficit'], 150. + r['etc'])

    def test_unstressed_reference_case_unchanged(self):
        r = calculate_balance(parse_field(PAYLOAD), 5., 0.)
        self.assertEqual(r['ks'], 1.)
        self.assertAlmostEqual(r['deficit'], 108.875)
        self.assertEqual(CALCULATION_VERSION, 'fao56.7')


if __name__ == '__main__':
    unittest.main()
