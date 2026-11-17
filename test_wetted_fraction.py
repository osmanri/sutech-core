"""FAO-56 equation 60: with partial wetting Kc ini = fw * Kc ini(Table 12); trickle fw = 0.3-0.4 (Table 20), midpoint 0.35."""
import unittest

from bot.water_balance import CROPS, WETTED_FRACTION, parse_field


def field(method, crop='cotton', day=0):
    return parse_field(dict(balance_version=2, crop=crop, soil_type='loam', irrigation_type=method, area=1, area_unit='hectare',
                            day_of_growth=day, moisture_condition='normal'))


class WettedFraction(unittest.TestCase):
    def test_table_20_values(self):
        self.assertEqual(WETTED_FRACTION['drip'], .35)
        self.assertEqual(WETTED_FRACTION['subsurface'], .35)
        for method in ('sprinkler', 'pivot', 'furrow'):
            self.assertEqual(WETTED_FRACTION[method], 1.)
        self.assertTrue(.3 <= WETTED_FRACTION['drip'] <= .4)

    def test_cotton_initial_kc_hand_computed(self):
        # Table 12: Kc ini 0.35 -> drip 0.35 * 0.35 = 0.1225; furrow keeps 0.35
        self.assertAlmostEqual(field('drip').kc, .1225)
        self.assertAlmostEqual(field('furrow').kc, .35)

    def test_mid_and_late_season_are_not_reduced(self):
        for method in ('drip', 'furrow'):
            mid = field(method, day=30 + 50 + 10)  # inside the mid stage (cotton: 30, 50, 60, 55)
            self.assertAlmostEqual(mid.kc, CROPS['cotton'][3][1])

    def test_development_starts_from_the_reduced_value(self):
        drip, furrow = field('drip', day=55), field('furrow', day=55)  # halfway through development (30 + 25)
        self.assertAlmostEqual(drip.kc, (.1225 + 1.18) / 2)
        self.assertAlmostEqual(furrow.kc, (.35 + 1.18) / 2)


if __name__ == '__main__':
    unittest.main()
