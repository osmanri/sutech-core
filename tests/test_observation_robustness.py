"""Known-answer cases for the observation and irrigation-delay simulation."""

import csv
import unittest

from research import observation_robustness as study
from research.simulate import WEATHER_DIR, fetch_power, field_for, run_season, season_weather, sutech_decider


class ObservationRobustness(unittest.TestCase):
    def test_engine_selection_clears_cached_fields_and_restores_previous_variant(self):
        kc_before = field_for("cotton", "loam", "drip", 0).kc
        with study.engine_variant("historical"):
            self.assertAlmostEqual(field_for("cotton", "loam", "drip", 0).kc, .35)
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with study.engine_variant("current"):
                    self.assertAlmostEqual(field_for("cotton", "loam", "drip", 0).kc, .1225)
                    self.assertAlmostEqual(field_for("cotton", "loam", "furrow", 0).kc, .35)
                    raise RuntimeError("stop")
            self.assertAlmostEqual(field_for("cotton", "loam", "drip", 0).kc, .35)
        self.assertEqual(field_for("cotton", "loam", "drip", 0).kc, kc_before)

    def test_weekly_observation_shifts_the_category_and_clamps_at_wet(self):
        field = field_for("cotton", "loam", "drip", 7)
        for actual_dr, shift, want in (
            (15.0, 0, 16.8796875),
            (15.0, -1, 0.0),
            (15.0, 1, 33.759375),
            (1.0, -1, 0.0),
            (40.0, 1, 33.759375),
        ):
            with self.subTest(actual_dr=actual_dr, shift=shift):
                decide = study.observation_decider(study.Scenario(category_shift=shift))
                self.assertAlmostEqual(decide(7, actual_dr, 0, 0, field), want)

    def test_missing_checks_leave_the_forecast_state_intact(self):
        scenario = study.Scenario(missing_checks="alternate")
        with study.engine_variant("historical"):
            decide = study.observation_decider(scenario)
            for day in range(7):
                field = field_for("cotton", "loam", "drip", day)
                self.assertEqual(decide(day, 0, 0, 0, field), 0)
            self.assertEqual(decide(7, 0, 10, 0, field_for("cotton", "loam", "drip", 7)), 0)
            # Day 7's check is skipped. Its 3.5 mm and today's 1.75 mm trigger irrigation.
            self.assertAlmostEqual(decide(8, 0, 5, 0, field_for("cotton", "loam", "drip", 8)), 5.25)
            self.assertAlmostEqual(decide(14, 40, 0, 0, field_for("cotton", "loam", "drip", 14)), 43.14375)

    def test_four_week_outage_preserves_checks_on_both_sides(self):
        scenario = study.Scenario(missing_checks="four-week")
        decide = study.observation_decider(scenario)
        for day, expected_irrigation in ((63, True), (70, False), (77, False), (84, False), (91, False), (98, True)):
            with self.subTest(day=day):
                field = field_for("cotton", "loam", "drip", day)
                self.assertEqual(decide(day, 100, 0, 0, field) > 0, expected_irrigation)

    def test_delayed_order_delivers_original_dose_and_leaves_residual_deficit(self):
        with study.engine_variant("current"):
            decide = study.observation_decider(study.Scenario(delay_days=2, missing_checks="all"))
            actual = [decide(day, 0, et0, 0, field_for("cotton", "loam", "drip", day))
                      for day, et0 in enumerate([50, 10, 10, 25, 0, 0])]
        for result, want in zip(actual, [0.0, 0.0, 6.125, 0.0, 0.0, 5.5125], strict=True):
            self.assertAlmostEqual(result, want)

    def test_pending_order_does_not_count_as_water_at_harvest(self):
        with study.engine_variant("current"):
            result = run_season("cotton", "loam", "drip", [(50.0, 0.0)],
                                study.observation_decider(study.Scenario(delay_days=2)))
        self.assertEqual(result.events, 0)
        self.assertEqual(result.gross_mm, 0)
        self.assertAlmostEqual(result.dr_end, 6.125)
        self.assertAlmostEqual(result.closure_error(), 0)

    def test_historical_no_check_baseline_matches_archived_weather_result(self):
        with (WEATHER_DIR.parent.parent / "results" / "simulation_runs.csv").open(newline="", encoding="utf-8") as f:
            expected = next(r for r in csv.DictReader(f) if r["strategy"] == "sutech" and r["crop"] == "cotton"
                            and r["method"] == "drip" and r["location"] == "Turkestan" and r["year"] == "2021")
        weather = season_weather(fetch_power("Turkestan", 43.30, 68.25, 2021), "cotton", 2021)
        with study.engine_variant("historical"):
            actual = run_season("cotton", "loam", "drip", weather,
                                study.observation_decider(study.Scenario(missing_checks="all")))
        self.assertAlmostEqual(actual.gross_mm * 10, float(expected["gross_m3_ha"]))
        self.assertEqual(actual.events, int(expected["events"]))

    def test_error_free_weekly_check_reproduces_the_existing_decider(self):
        weather = [(6.0, 0.0)] * 50
        forecast = [(4.8, 0.0)] * 50
        original, _ = sutech_decider("corn", "loam", "furrow", check_every=7, categorical=True)
        actual = run_season("corn", "loam", "furrow", weather, study.observation_decider(study.Scenario()), forecast)
        self.assertEqual(actual, run_season("corn", "loam", "furrow", weather, original, forecast))

    def test_failure_counts_exclude_under_yield_cases_from_water_comparison(self):
        def row(relative_yield, water):
            return study.Result(location="Taraz", year=2022, crop="corn", method="drip",
                                scenario=study.Scenario(), water_m3_ha=water, stress_days=0,
                                relative_yield=relative_yield, calendar_m3_ha=10, calendar_yield=0.995)

        results = [row(.9799, 12), row(.98, 10), row(1, 9)]
        self.assertEqual(study.failure_counts(results), (1, 1))
