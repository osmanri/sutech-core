"""ET0 validation against FAO-56 Example 18 (Uccle/Brussels, 6 July) and basic invariants.

Reference values es = 1.997 kPa and Ra = 41.088 MJ m-2 day-1 were confirmed against the
R package ETo vignette, which uses the same data. The final ET0 = 3.9 mm/day and
Rn = 13.28 MJ m-2 day-1 are the values recalled from FAO-56 Example 18 and have NOT yet
been checked against the printed book: verify them in the FAO-56 PDF (Chapter 4).
"""

import unittest

from bot.et0 import (
    et0_hargreaves, et0_penman_monteith, extraterrestrial_radiation, net_radiation,
    psychrometric_constant, sat_vapour_pressure, slope_vapour_pressure, wind_at_2m,
)
from bot.water_balance import root_zone_capacity

BRUSSELS = dict(t_max=21.5, t_min=12.3, u2=2.078, elevation_m=100, sunshine_h=9.25,
                lat_deg=50.80, day_of_year=187, rh_max=84, rh_min=63)


class Fao56Example18(unittest.TestCase):
    def test_intermediate_values(self):
        self.assertAlmostEqual((sat_vapour_pressure(21.5) + sat_vapour_pressure(12.3)) / 2, 1.997, places=3)
        ra, n_day = extraterrestrial_radiation(50.80, 187)
        self.assertAlmostEqual(ra, 41.09, places=2)
        self.assertAlmostEqual(n_day, 16.1, places=1)
        self.assertAlmostEqual(slope_vapour_pressure(16.9), 0.122, places=3)
        self.assertAlmostEqual(psychrometric_constant(100), 0.0666, places=4)
        self.assertAlmostEqual(wind_at_2m(2.78, 10), 2.078, places=2)

    def test_net_radiation(self):
        ra, n_day = extraterrestrial_radiation(50.80, 187)
        rs = (0.25 + 0.5 * 9.25 / n_day) * ra
        self.assertAlmostEqual(rs, 22.07, places=1)
        ea = (sat_vapour_pressure(12.3) * 0.84 + sat_vapour_pressure(21.5) * 0.63) / 2
        self.assertAlmostEqual(ea, 1.409, places=3)
        self.assertAlmostEqual(net_radiation(rs, ra, 100, 21.5, 12.3, ea), 13.28, delta=0.05)

    def test_final_et0(self):
        self.assertAlmostEqual(et0_penman_monteith(**BRUSSELS), 3.9, delta=0.05)


class Invariants(unittest.TestCase):
    def test_more_wind_or_dryness_raises_et0(self):
        base = et0_penman_monteith(**BRUSSELS)
        self.assertGreater(et0_penman_monteith(**{**BRUSSELS, "u2": 4.0}), base)
        self.assertGreater(et0_penman_monteith(**{**BRUSSELS, "rh_max": 60, "rh_min": 30}), base)

    def test_overcast_saturated_calm_air_lowers_et0(self):
        # Overcast still leaves Rs = 0.25 Ra in July at 51N, so ET0 stays near 2 mm/day (not ~0).
        cloudy = {**BRUSSELS, "sunshine_h": 0.0, "u2": 0.0, "rh_max": 100, "rh_min": 100}
        et = et0_penman_monteith(**cloudy)
        self.assertLess(et, 0.6 * et0_penman_monteith(**BRUSSELS))
        self.assertGreater(et, 1.0)

    def test_measured_rs_equals_sunshine_path(self):
        ra, n_day = extraterrestrial_radiation(50.80, 187)
        rs = (0.25 + 0.5 * 9.25 / n_day) * ra
        args = {k: v for k, v in BRUSSELS.items() if k != "sunshine_h"}
        self.assertAlmostEqual(et0_penman_monteith(**args, rs=rs), et0_penman_monteith(**BRUSSELS), places=9)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            et0_penman_monteith(**{**BRUSSELS, "t_max": 5.0})
        with self.assertRaises(ValueError):
            et0_penman_monteith(**{k: v for k, v in BRUSSELS.items() if k not in ("rh_max", "rh_min")})

    def test_hargreaves_is_in_plausible_range(self):
        # Temperature-only estimate stays within ~20% of Penman-Monteith for this temperate day.
        self.assertAlmostEqual(et0_hargreaves(t_max=21.5, t_min=12.3, lat_deg=50.8, day_of_year=187), 3.9, delta=0.5)


class RootZoneCapacity(unittest.TestCase):
    def test_taw_raw_follow_fao56_eq_82_83(self):
        # TAW = 1000 (theta_FC - theta_WP) Zr ; RAW = p TAW   -> loam: 1000*(0.33-0.18)*1.0 = 150 mm
        taw, raw = root_zone_capacity("loam", 1.0, 0.55)
        self.assertAlmostEqual(taw, 150.0)
        self.assertAlmostEqual(raw, 82.5)


if __name__ == "__main__":
    unittest.main()
