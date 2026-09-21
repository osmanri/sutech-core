"""Unit tests for HardwareBridge, VirtualArduinoBridge and fail-safe pump controls."""

import unittest
from bot.hardware_bridge import (
    HardwareBridge,
    VirtualArduinoBridge,
    calculate_pump_runtime_seconds,
    MAX_PUMP_RUNTIME_SECONDS,
    DEFAULT_BENCH_FLOW_ML_PER_SEC,
)


class HardwareBridgeTests(unittest.TestCase):
    def setUp(self):
        self.virtual = VirtualArduinoBridge()
        self.bridge = HardwareBridge(force_virtual=True)

    def test_01_virtual_ping_pong(self):
        response = self.virtual.send_command("PING")
        self.assertEqual(response, "PONG")
        self.assertTrue(self.bridge.ping())

    def test_02_virtual_status(self):
        status = self.virtual.send_command("STATUS")
        self.assertTrue(status.startswith("OK:STATUS:PUMP=0"))

    def test_03_virtual_water_valid_duration(self):
        resp = self.virtual.send_command("WATER:5.5")
        self.assertEqual(resp, "OK:PUMP_ON:DURATION=5.50")
        self.assertTrue(self.virtual.pump_active)
        self.assertEqual(self.virtual.last_duration, 5.5)

    def test_04_virtual_water_hard_cap_fail_safe(self):
        # Durations above 30 seconds must be safely capped
        resp = self.virtual.send_command("WATER:120.0")
        self.assertEqual(resp, f"OK:PUMP_ON:DURATION={MAX_PUMP_RUNTIME_SECONDS:.2f}")
        self.assertEqual(self.virtual.last_duration, MAX_PUMP_RUNTIME_SECONDS)

    def test_05_virtual_water_invalid_duration(self):
        self.assertEqual(self.virtual.send_command("WATER:0"), "ERR:INVALID_DURATION")
        self.assertEqual(self.virtual.send_command("WATER:-10"), "ERR:INVALID_DURATION")
        self.assertEqual(self.virtual.send_command("WATER:abc"), "ERR:INVALID_DURATION")

    def test_06_virtual_stop(self):
        self.virtual.send_command("WATER:5.0")
        self.assertTrue(self.virtual.pump_active)
        stop_resp = self.virtual.send_command("STOP")
        self.assertEqual(stop_resp, "OK:PUMP_OFF:REASON=MANUAL_STOP")
        self.assertFalse(self.virtual.pump_active)

    def test_07_hardware_bridge_trigger(self):
        self.assertTrue(self.bridge.is_virtual)
        result = self.bridge.trigger_irrigation(7.5)
        self.assertTrue(result["success"])
        self.assertEqual(result["duration"], 7.5)
        self.assertEqual(result["mode"], "virtual")

    def test_08_hardware_bridge_stop(self):
        result = self.bridge.stop_pump()
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "virtual")

    def test_09_calculate_runtime_bench_scale(self):
        # 25 ml at 5 ml/s bench flow rate = 5.0 seconds
        sec = calculate_pump_runtime_seconds(volume_liters=0.025, pump_productivity_m3h=None)
        self.assertEqual(sec, 5.0)

        # Zero or negative volume
        self.assertEqual(calculate_pump_runtime_seconds(0.0), 0.0)
        self.assertEqual(calculate_pump_runtime_seconds(-5.0), 0.0)

        # Capped at 30.0s maximum
        capped = calculate_pump_runtime_seconds(volume_liters=1000.0)
        self.assertEqual(capped, MAX_PUMP_RUNTIME_SECONDS)

    def test_10_calculate_runtime_field_scale(self):
        # 60 m3/h = (60 * 1000) / 3600 = 16.6667 liters/s
        # 50 liters / 16.6667 = 3.0 seconds
        sec = calculate_pump_runtime_seconds(volume_liters=50.0, pump_productivity_m3h=60.0)
        self.assertAlmostEqual(sec, 3.0, places=2)

    def test_11_virtual_moisture(self):
        resp = self.virtual.send_command("MOISTURE")
        self.assertEqual(resp, "OK:MOISTURE=65")
        moisture = self.bridge.get_moisture()
        self.assertEqual(moisture, 65)

    def test_12_virtual_water_level(self):
        level = self.bridge.get_water_level()
        self.assertEqual(level, 85)

    def test_13_virtual_telemetry(self):
        telemetry = self.bridge.get_telemetry()
        self.assertFalse(telemetry["pump_active"])
        self.assertEqual(telemetry["water_level"], 85)
        self.assertEqual(telemetry["soil_moisture"], 65)
        self.assertEqual(telemetry["temperature"], 23.5)
        self.assertEqual(telemetry["humidity"], 48.0)
        self.assertTrue(telemetry["has_water"])

    def test_14_water_safety_empty_reservoir_blocks_pump(self):
        # When reservoir water level is critically low (< 8%), normal irrigation must be blocked
        self.virtual.water_level = 3
        resp = self.virtual.send_command("WATER:5.0")
        self.assertEqual(resp, "ERR:WATER_EMPTY:LEVEL=3")
        self.assertFalse(self.virtual.pump_active)

        # Force mode can still be used for diagnostic override
        resp_force = self.virtual.send_command("WATER_FORCE:2.0")
        self.assertEqual(resp_force, "OK:PUMP_ON:DURATION=2.00")
        self.assertTrue(self.virtual.pump_active)
        self.virtual.stop_pump = self.virtual.send_command("STOP")

    def test_15_beep_signal(self):
        self.assertTrue(self.bridge.beep())


if __name__ == "__main__":
    unittest.main()

