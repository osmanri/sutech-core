"""Known-answer checks for the retrospective simulation (synthetic weather, no network)."""
import random
import unittest

from bot.water_balance import CROPS
from research.simulate import (KY, calendar_decider, mean_daily_demand, run_season, safe_multiplier,
                               summarise, sutech_decider)
from research.sensitivity import forecast_for

DAYS = sum(CROPS["cotton"][4])
DRY = [(6.0, 0.0)] * DAYS                                  # hot, rainless season
RAINY = [(5.0, 20.0 if d % 10 == 0 else 0.0) for d in range(DAYS)]


def sutech(weather, forecast=None, **kw):
    decide, _ = sutech_decider("cotton", "loam", "drip", **kw)
    return run_season("cotton", "loam", "drip", weather, decide, forecast)


class Simulation(unittest.TestCase):
    def test_water_balance_closes(self):
        for s in (sutech(DRY), sutech(RAINY), run_season("cotton", "loam", "furrow", RAINY, calendar_decider(10, 50.0))):
            self.assertAlmostEqual(s.closure_error(), 0.0, places=8)

    def test_perfect_information_sutech_never_stresses(self):
        for w in (DRY, RAINY):
            s = sutech(w)
            self.assertEqual(s.stress_days, 0)
            self.assertAlmostEqual(s.relative_yield(KY["cotton"]), 1.0)

    def test_no_irrigation_in_dry_season_causes_stress(self):
        s = run_season("cotton", "loam", "drip", DRY, calendar_decider(5, 0.0))
        self.assertGreater(s.stress_days, 100)
        self.assertLess(s.relative_yield(KY["cotton"]), 0.6)

    def test_sutech_applies_exactly_crop_demand_without_rain(self):
        s = sutech(DRY)
        self.assertAlmostEqual(s.net_mm, s.etm - s.dr_end, places=6)
        self.assertLess(s.deep_perc, 1e-9)

    def test_safe_calendar_reaches_target_yield(self):
        demand = mean_daily_demand("cotton", "loam", "drip", [RAINY])
        m = safe_multiplier("cotton", "loam", "drip", [RAINY], 5, demand)
        s = run_season("cotton", "loam", "drip", RAINY, calendar_decider(5, demand * 5 * m))
        self.assertGreaterEqual(s.relative_yield(KY["cotton"]), 0.98)
        if m > 1.0:  # one step less must miss the target, otherwise m is not minimal
            less = run_season("cotton", "loam", "drip", RAINY, calendar_decider(5, demand * 5 * (m - 0.05)))
            self.assertLess(less.relative_yield(KY["cotton"]), 0.98)

    def test_underestimating_forecast_drifts_into_stress_and_soil_check_fixes_it(self):
        biased = forecast_for(DRY, random.Random(1), bias=-0.2)
        self.assertGreater(sutech(DRY, biased).stress_days, 50)
        fixed = sutech(DRY, biased, check_every=7, sensor_sd_mm=0.0)
        self.assertEqual(fixed.stress_days, 0)

    def test_summary_pairs_runs_by_location_and_year(self):
        rows = [dict(crop="c", method="m", location="L", year=y, strategy=st, gross_m3_ha=g, stress_days=0,
                     rel_yield=1.0, deep_perc_mm=0.0, events=1)
                for y, st, g in ((1, "sutech", 80.0), (1, "cal", 100.0), (2, "sutech", 90.0), (2, "cal", 100.0))]
        cal = next(s for s in summarise(rows) if s["strategy"] == "cal")
        self.assertAlmostEqual(cal["sutech_vs_this_pct"], -15.0)
        self.assertEqual(cal["sutech_less_water_in"], 2)


if __name__ == "__main__":
    unittest.main()
