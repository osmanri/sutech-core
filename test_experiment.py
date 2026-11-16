"""Tests for the experiment journal and analysis (known-answer checks)."""

import math
import tempfile
import unittest
from pathlib import Path

from bot.experiment_log import ExperimentLog
from bot.hardware_bridge import HardwareBridge
from experiment.analyze import analyse, daily_evaporation, error_metrics, load_rows, welch_t_test


class StatsTests(unittest.TestCase):
    def test_welch_known_value(self):
        # scipy.stats.ttest_ind([1,2,3,4,5],[3,4,5,6,7], equal_var=False) -> t=-2.0, p=0.0805
        r = welch_t_test([1, 2, 3, 4, 5], [3, 4, 5, 6, 7])
        self.assertAlmostEqual(r["t"], -2.0, places=6)
        self.assertAlmostEqual(r["df"], 8.0, places=6)
        self.assertAlmostEqual(r["p"], 0.0805, places=3)

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
        log.append(pot_id="A1", group="sutech", event="irrigation", timestamp="2027-01-10T12:00:00+05:00", water_ml="50")
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-11T08:00:00+05:00", weight_g="1030")
        (day,) = daily_evaporation(load_rows(self.path), pot_area_cm2=100.0)
        self.assertAlmostEqual(day["loss_g"], 20.0)         # 1000 + 50 - 1030
        self.assertAlmostEqual(day["observed_mm"], 2.0)     # 20 g / 100 cm2 = 0.2 cm

    def test_long_gap_is_skipped_not_interpolated(self):
        log = ExperimentLog(self.path)
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-10T08:00:00+05:00", weight_g="1000")
        log.append(pot_id="A1", group="sutech", timestamp="2027-01-14T08:00:00+05:00", weight_g="900")
        self.assertEqual(daily_evaporation(load_rows(self.path), 100.0), [])

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


if __name__ == "__main__":
    unittest.main()
