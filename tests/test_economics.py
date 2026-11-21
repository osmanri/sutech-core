import math
import unittest
from dataclasses import replace

from research.economics import examples


class GreenhouseScenarioTests(unittest.TestCase):
    def test_same_pump_then_pump_only_comparison(self):
        actual = {key: value.totals() for key, value in examples().items()}
        base, schedule, replaced = (actual[k] for k in examples())
        self.assertEqual(base["total"], 24720)
        self.assertAlmostEqual(schedule["total"], 23412)
        self.assertEqual(base["water_m3"] - schedule["water_m3"], 18)
        self.assertAlmostEqual(base["energy_kwh"] - schedule["energy_kwh"], 3.6)
        self.assertEqual(schedule["water_m3"], replaced["water_m3"])
        self.assertAlmostEqual(schedule["energy_kwh"] - replaced["energy_kwh"], 5.1)
        self.assertAlmostEqual(replaced["total"] - schedule["total"], 347)

    def test_rejects_invalid_inputs(self):
        example = examples()["calendar"]
        for updates in ({"flow_m3h": 0}, {"power_kw": -1}, {"water_m3": math.inf}, {"service": math.nan}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                replace(example, **updates).totals()
