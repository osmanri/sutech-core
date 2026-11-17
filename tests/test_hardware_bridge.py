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
        # 5 s at the 5 ml/s bench flow = 25 ml; 2.25 pulses per ml -> 56 pulses
        self.assertEqual(stop_resp, "OK:PUMP_OFF:REASON=MANUAL_STOP:ML=24.9:PULSES=56")
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


class FlowMeterTests(unittest.TestCase):
    def setUp(self):
        self.bridge = HardwareBridge(force_virtual=True)
        self.virtual = self.bridge._virtual

    def test_dose_water_reaches_target(self):
        before = self.bridge.get_weight()
        r = self.bridge.dose_water(40)
        self.assertTrue(r["success"], r)
        self.assertEqual(r["reason"], "VOLUME_REACHED")
        self.assertEqual(r["pulses"], 90)
        self.assertAlmostEqual(r["delivered_ml"], 40.0)
        self.assertAlmostEqual(self.bridge.get_weight() - before, 40.0, places=1)

    def test_dose_water_rejects_bad_volume(self):
        for bad in (0, -5, 5000):
            r = self.bridge.dose_water(bad)
            self.assertFalse(r["success"])
        self.assertFalse(self.virtual.events)

    def test_dose_refused_without_calibration_or_water(self):
        self.virtual.flow_ppml = 0.0
        r = self.bridge.dose_water(40)
        self.assertFalse(r["success"])
        self.assertEqual(r["error"], "ERR:FLOW_NOT_CALIBRATED")
        self.virtual.flow_ppml = 2.25
        self.virtual.water_level = 3
        self.assertIn("ERR:WATER_EMPTY", self.bridge.dose_water(40)["error"])

    def test_calibration_from_timed_run(self):
        self.virtual.flow_ppml = 0.0
        self.assertEqual(self.bridge.calibrate_flow(100)["error"], "ERR:NO_FLOW_PULSES")
        self.bridge.trigger_irrigation(10)      # 50 ml at 5 ml/s -> 112 pulses
        self.bridge.stop_pump()
        cal = self.bridge.calibrate_flow(50.0)  # the measuring cylinder shows 50 ml
        self.assertTrue(cal["success"])
        self.assertAlmostEqual(cal["pulses_per_ml"], 2.24, places=2)
        self.assertTrue(self.bridge.get_flow()["calibrated"])

    def test_flow_counter_and_reset(self):
        self.bridge.dose_water(40)
        self.assertEqual(self.bridge.get_flow()["pulses"], 90)
        self.assertTrue(self.bridge.reset_flow())
        self.assertEqual(self.bridge.get_flow()["pulses"], 0)


class FakeSerial:
    """Scripted serial port: replies to each written command with the queued lines."""

    def __init__(self, script):
        self.script = list(script)   # list of (expected_command, [lines to send back])
        self.pending: list[bytes] = []
        self.written: list[str] = []

    @property
    def in_waiting(self):
        return len(self.pending)

    def write(self, data):
        cmd = data.decode().strip()
        self.written.append(cmd)
        expected, lines = self.script.pop(0)
        assert cmd == expected, (cmd, expected)
        self.pending.extend(l.encode() + b"\n" for l in lines)

    def readline(self):
        return self.pending.pop(0) if self.pending else b""

    def reset_input_buffer(self):
        self.pending.clear()


class SerialProtocolTests(unittest.TestCase):
    def make(self, script):
        b = HardwareBridge(force_virtual=True)
        b._serial = FakeSerial(script)
        b._is_virtual = False
        return b

    def test_unsolicited_pump_off_is_not_taken_as_reply(self):
        # The timer ran out right before SCALE was sent: the EVT line arrives first.
        b = self.make([("SCALE", ["EVT:PUMP_OFF:REASON=TIMER_COMPLETED:ML=NA:PULSES=0", "OK:SCALE=812.4"])])
        self.assertEqual(b.get_weight(), 812.4)
        self.assertEqual(list(b.events), ["EVT:PUMP_OFF:REASON=TIMER_COMPLETED:ML=NA:PULSES=0"])

    def test_stale_lines_are_drained_before_a_command(self):
        b = self.make([("PING", ["PONG"])])
        b._serial.pending = [b"EVT:PUMP_OFF:REASON=TIMER_COMPLETED:ML=NA:PULSES=0\n", b"INIT:SU-TECH:v2.1\n"]
        self.assertTrue(b.ping())
        self.assertEqual(len(b.events), 1)

    def test_real_dose_reads_pump_off_event(self):
        b = self.make([("WATER_ML:40.0", ["OK:PUMP_ON:TARGET_ML=40.0",
                                          "EVT:PUMP_OFF:REASON=VOLUME_REACHED:ML=40.0:PULSES=90"])])
        r = b.dose_water(40)
        self.assertTrue(r["success"], r)
        self.assertEqual(r["mode"], "real")
        self.assertEqual(r["delivered_ml"], 40.0)

    def test_real_dose_timeout_reports_partial_volume(self):
        b = self.make([("WATER_ML:40.0", ["OK:PUMP_ON:TARGET_ML=40.0",
                                          "EVT:PUMP_OFF:REASON=TIMEOUT_BEFORE_VOLUME:ML=4.4:PULSES=10"])])
        r = b.dose_water(40)
        self.assertFalse(r["success"])
        self.assertEqual(r["delivered_ml"], 4.4)
        self.assertIn("TIMEOUT_BEFORE_VOLUME", r["error"])


if __name__ == "__main__":
    unittest.main()

