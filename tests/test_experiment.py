"""Tests for the experiment journal and analysis (known-answer checks)."""

import math
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.experiment_log import ExperimentLog
from bot.hardware_bridge import HardwareBridge
from experiment import collect
from experiment.analyze import analyse, compare_groups, daily_evaporation, error_metrics, load_rows, welch_t_test


class StatsTests(unittest.TestCase):
    def test_welch_known_value(self):
        # scipy.stats.ttest_ind([1,2,3,4,5],[3,4,5,6,7], equal_var=False) -> t=-2.0, p=0.0805
        r = welch_t_test([1, 2, 3, 4, 5], [3, 4, 5, 6, 7])
        self.assertAlmostEqual(r["t"], -2.0, places=6)
        self.assertAlmostEqual(r["df"], 8.0, places=6)
        self.assertAlmostEqual(r["p"], 0.0805, places=3)
        self.assertAlmostEqual(r["difference_ci_95"][0], -4.306004, places=5)
        self.assertAlmostEqual(r["difference_ci_95"][1], 0.306004, places=5)

    def test_standardized_effect_interval_known_value(self):
        r = compare_groups({"sutech": [1, 2, 3, 4, 5], "control": [3, 4, 5, 6, 7]})
        self.assertAlmostEqual(r["cohens_d"], -2 / math.sqrt(2.5))
        radius = 1.95996398454 * math.sqrt(0.5)
        self.assertAlmostEqual(r["cohens_d_ci_95"][0], r["cohens_d"] - radius)
        self.assertAlmostEqual(r["cohens_d_ci_95"][1], r["cohens_d"] + radius)

    def test_welch_identical_groups(self):
        self.assertAlmostEqual(welch_t_test([1, 2, 3], [1, 2, 3])["p"], 1.0, places=6)

    def test_welch_needs_two_pots(self):
        with self.assertRaises(ValueError):
            welch_t_test([1.0], [1.0, 2.0])

    def test_error_metrics(self):
        m = error_metrics([1.0, 2.0, 3.0], [2.0, 2.0, 5.0])
        self.assertAlmostEqual(m["rmse_mm"], math.sqrt((1 + 0 + 4) / 3))
        self.assertAlmostEqual(m["mae_mm"], 1.0)
        self.assertAlmostEqual(m["bias_mm"], 1.0)
        self.assertAlmostEqual(m["pearson_r"], math.sqrt(3) / 2)

    def test_pearson_r_is_undefined_for_constant_or_single_series(self):
        self.assertIsNone(error_metrics([1, 2], [3, 3])["pearson_r"])
        self.assertIsNone(error_metrics([1], [2])["pearson_r"])


class LogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "log.csv"

    def test_rejects_bad_group(self):
        with self.assertRaises(ValueError):
            ExperimentLog(self.path).append(pot_id="A1", group="oops")

    def test_record_sample_from_virtual_bridge(self):
        log = ExperimentLog(self.path)
        row = log.record_sample(HardwareBridge(force_virtual=True), "A1", "sutech")
        self.assertEqual(row["weight_g"], "1000.0")
        self.assertEqual(len(load_rows(self.path)), 1)

    def test_irrigation_requires_positive_volume(self):
        with self.assertRaises(ValueError):
            ExperimentLog(self.path).record_irrigation("A1", "sutech", 0)

    def test_scale_irrigation_records_gross_water_and_drainage(self):
        log = ExperimentLog(self.path)
        log.record_scale_irrigation("A1", "sutech", 1000.0, 1038.0, 12.0)
        (row,) = load_rows(self.path)
        self.assertEqual(float(row["water_ml"]), 50.0)
        self.assertEqual(float(row["drainage_ml"]), 12.0)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "log.csv"

    def _build(self):
        log = ExperimentLog(self.path)
        # Two days, 100 cm2 pots. sutech pots lose 20 g/day, control 30 g/day.
        for pot, group, loss, water in (("A1", "sutech", 20, 40), ("A2", "sutech", 22, 44),
                                        ("A3", "sutech", 18, 36), ("B1", "control", 30, 80),
                                        ("B2", "control", 33, 90), ("B3", "control", 27, 70)):
            for day, ts in ((1, "2027-01-10T08:00:00+05:00"), (2, "2027-01-11T08:00:00+05:00")):
                w = 1000 - loss * (day - 1)
                log.append(pot_id=pot, group=group, timestamp=ts, weight_g=f"{w}", model_et_mm=f"{loss / 10 + 0.5}")
            log.append(pot_id=pot, group=group, event="irrigation", timestamp="2027-01-11T09:00:00+05:00",
                       water_ml=f"{water}")
        return log

    def test_evaporation_accounts_for_added_water(self):
        log = ExperimentLog(self.path)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T08:00:00+05:00", weight_g="1000")
        log.append(pot_id="A1", group="sutech", event="irrigation", timestamp="2027-01-10T12:00:00+05:00", water_ml="50", drainage_ml=0)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-11T08:00:00+05:00", weight_g="1030")
        (day,) = daily_evaporation(load_rows(self.path), pot_area_cm2=100.0)
        self.assertAlmostEqual(day["loss_g"], 20.0)         # 1000 + 50 - 1030
        self.assertAlmostEqual(day["observed_mm"], 2.0)     # 20 g / 100 cm2 = 0.2 cm

    def test_drainage_is_subtracted_and_elapsed_time_is_normalized(self):
        log = ExperimentLog(self.path)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T08:00:00+05:00", weight_g=1000)
        log.record_irrigation("A1", "sutech", 50, drainage_ml=12, timestamp="2027-01-10T09:00:00+05:00")
        log.append(pot_id="A1", group="sutech", event="drainage", drainage_ml=1,
                   timestamp="2027-01-11T06:00:00+05:00")
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-11T14:00:00+05:00", weight_g=1012, model_et_mm=2)
        (day,) = daily_evaporation(load_rows(self.path), 100.0)
        self.assertAlmostEqual(day["observed_mm"], 2.0)  # (1000 + 50 - 12 - 1 - 1012) / 10 * 24 / 30

    def test_unknown_legacy_drainage_is_distinct_from_zero(self):
        self.path.write_text(
            "timestamp,pot_id,group,event,weight_g,water_ml,model_et_mm\n"
            "2027-01-10T08:00:00+05:00,A1,sutech,sample,1000,,\n"
            "2027-01-10T09:00:00+05:00,A1,sutech,irrigation,,50,\n"
            "2027-01-11T08:00:00+05:00,A1,sutech,sample,1030,,2\n",
            encoding="utf-8",
        )
        s = analyse(self.path, 100.0, None, self.dir / "results")
        self.assertEqual(s["water_ml_per_pot"]["sutech"]["mean"], 50)
        self.assertEqual(s["intervals"]["excluded"]["unknown_drainage"], 1)
        self.assertNotIn("model_accuracy", s)

    def test_long_gap_is_skipped_not_interpolated(self):
        log = ExperimentLog(self.path)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T08:00:00+05:00", weight_g="1000")
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-14T08:00:00+05:00", weight_g="900")
        self.assertEqual(daily_evaporation(load_rows(self.path), 100.0), [])
        s = analyse(self.path, 100.0, None, self.dir / "results")
        self.assertEqual(s["intervals"]["excluded"]["long_gap"], 1)
        self.assertEqual(s["intervals"]["missing_scheduled_days"], 3)

    def test_short_gap_and_missing_prediction_are_reported(self):
        log = ExperimentLog(self.path)
        for ts in ("2027-01-10T23:00:00+05:00", "2027-01-11T04:00:00+05:00", "2027-01-12T04:00:00+05:00"):
            log.append(pot_id="A1", group="sutech", timestamp=ts, weight_g=1000)
        s = analyse(self.path, 100.0, None, self.dir / "results")
        self.assertEqual(s["intervals"]["excluded"]["short_gap"], 1)
        self.assertEqual(s["intervals"]["missing_prediction"], 1)

    def test_missing_irrigation_measurement_excludes_interval_and_total(self):
        log = ExperimentLog(self.path)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T08:00:00+05:00", weight_g=1000)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T09:00:00+05:00", event="note",
                   note="MISSING_IRRIGATION_VOLUME: scale timed out")
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-11T08:00:00+05:00", weight_g=990, model_et_mm=1)
        summary = analyse(self.path, 100, None, self.dir / "results")
        self.assertEqual(summary["intervals"]["excluded"]["unknown_irrigation"], 1)
        self.assertEqual(summary["pots_with_unmeasured_irrigation"], ["A1"])
        self.assertEqual(summary["water_ml_per_pot"]["sutech"]["n"], 0)

    def test_rejects_invalid_log_rows(self):
        header = "timestamp,pot_id,group,event,weight_g,water_ml,model_et_mm\n"
        first = "2027-01-10T08:00:00+05:00,A1,sutech,sample,1000,,\n"
        for row, error in (
            ("2027-01-11T08:00:00,A1,sutech,sample,1000,,\n", "UTC offset"),
            ("2027-01-11T08:00:00+05:00,A1,control,sample,1000,,\n", "group assignment"),
            ("2027-01-10T03:00:00+00:00,A1,sutech,sample,1000,,\n", "duplicate"),
            ("2027-01-11T08:00:00+05:00,A1,sutech,sample,nan,,\n", "weight_g"),
            ("2027-01-11T08:00:00+05:00,A1,sutech,irrigation,,,\n", "water_ml"),
            ("2027-01-11T08:00:00+05:00,A1,sutech,sample,1000,,,extra\n", "column count"),
        ):
            with self.subTest(row=row):
                self.path.write_text(header + first + row, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    load_rows(self.path)

    def test_outcomes_must_match_recorded_assignments(self):
        self._build()
        outcomes = self.dir / "outcomes.csv"
        for rows, error in (
            ("A1,control,10\n", "group assignment"),
            ("C1,control,10\n", "unknown pot"),
            ("A1,sutech,10\nA1,sutech,11\n", "duplicate"),
        ):
            with self.subTest(rows=rows):
                outcomes.write_text("pot_id,group,dry_mass_g\n" + rows, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    analyse(self.path, 100.0, outcomes, self.dir / "results")

    def test_mass_noninferiority_includes_uncertainty_in_control_mean(self):
        self._build()
        outcomes = self.dir / "outcomes.csv"
        outcomes.write_text("pot_id,group,dry_mass_g\nA1,sutech,10\nA2,sutech,10.1\nA3,sutech,9.9\n"
                            "B1,control,9.9\nB2,control,10\nB3,control,10.1\n", encoding="utf-8")
        result = analyse(self.path, 100.0, outcomes, self.dir / "results")["mass_noninferiority"]
        self.assertAlmostEqual(result["estimate_g"], 1.0)
        self.assertAlmostEqual(result["lower_bound_g"], 0.834, places=3)
        self.assertTrue(result["demonstrated"])

        outcomes.write_text("pot_id,group,dry_mass_g\nA1,sutech,9.5\nA2,sutech,9.6\nA3,sutech,9.4\n"
                            "B1,control,8\nB2,control,10\nB3,control,12\n", encoding="utf-8")
        result = analyse(self.path, 100.0, outcomes, self.dir / "results")["mass_noninferiority"]
        self.assertAlmostEqual(result["estimate_g"], 0.5)
        self.assertLess(result["lower_bound_g"], 0)
        self.assertFalse(result["demonstrated"])

    def test_no_inference_without_variance_and_json_is_finite(self):
        log = ExperimentLog(self.path)
        for pot, group, water in (("A1", "sutech", 40), ("A2", "sutech", 40),
                                  ("B1", "control", 80), ("B2", "control", 80)):
            log.record_irrigation(pot, group, water, drainage_ml=0)
        out = self.dir / "results"
        report = analyse(self.path, 100, None, out)
        self.assertIsNone(report["water_ml_per_pot"]["welch"]["p"])
        self.assertIsNone(report["water_ml_per_pot"]["cohens_d"])
        self.assertEqual(json.loads((out / "summary.json").read_text(encoding="utf-8")), report)

    def test_full_analysis(self):
        self._build()
        out = self.dir / "results"
        s = analyse(self.path, 100.0, None, out)
        self.assertEqual(s["water_ml_per_pot"]["sutech"]["mean"], 40.0)
        self.assertEqual(s["water_ml_per_pot"]["control"]["mean"], 80.0)
        self.assertAlmostEqual(s["water_ml_per_pot"]["difference_pct"], -50.0)
        self.assertLess(s["water_ml_per_pot"]["welch"]["p"], 0.05)
        self.assertAlmostEqual(s["model_accuracy"]["bias_mm"], 0.5, places=6)
        for name in ("summary.json", "report.md", "cumulative_water.svg"):
            self.assertTrue((out / name).exists())


class CollectionTests(unittest.TestCase):
    def test_missing_immediate_drainage_is_saved_as_an_unmeasured_dose(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.csv"
            command = ["collect.py", "--port", "FAKE", "--log", str(log), "--pots", "A1:sutech"]
            inputs = ["", "", "50", "", "", ""]
            with (
                patch.object(sys, "argv", command),
                patch.object(collect, "HardwareBridge") as hardware,
                patch.object(collect, "stable_weight", side_effect=[1000, 1038]),
                patch("builtins.input", side_effect=inputs),
                patch("builtins.print"),
            ):
                hardware.return_value.is_virtual = False
                hardware.return_value.get_telemetry.return_value = {"soil_moisture": 60, "temperature": 22, "humidity": 55}
                collect.main()
            _, note = load_rows(log)
            self.assertEqual(note["event"], "note")
            self.assertIn("MISSING_IRRIGATION_VOLUME: immediate drainage was not measured", note["note"])

if __name__ == "__main__":
    unittest.main()
