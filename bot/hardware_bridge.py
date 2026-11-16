"""Hardware communication bridge between Su-Tech Bot and Arduino/ESP32 testbed.

Supports both physical USB Serial connection and an embedded Virtual Bridge
for automatic testing, CI/CD, and offline demonstration.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

# Hard limits for desktop bench safety
MAX_PUMP_RUNTIME_SECONDS = 30.0
DEFAULT_BENCH_FLOW_ML_PER_SEC = 5.0  # Measured laboratory calibration (5 ml/s)
MAX_DOSE_ML = 1000.0  # firmware refuses larger single doses


def parse_fields(line: str) -> dict[str, str]:
    """'EVT:PUMP_OFF:REASON=X:ML=4.0:PULSES=9' -> {'REASON': 'X', 'ML': '4.0', 'PULSES': '9'}."""
    out: dict[str, str] = {}
    for part in line.split(":"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def _float_or_none(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "", "NA") else None
    except ValueError:
        return None


class VirtualArduinoBridge:
    """Deterministic in-memory emulator of the Arduino Relay Pump firmware."""

    def __init__(self) -> None:
        self.is_connected = True
        self.pump_active = False
        self.last_duration = 0.0
        self.water_level = 85
        self.soil_moisture = 65
        self.temperature = 23.5
        self.humidity = 48.0
        # Simulated pot scale (HX711): grams of pot + soil + water above the tare.
        self.weight_g = 1000.0
        self.scale_calibrated = True
        # Simulated flow meter: a calibrated bench sensor (pulses per ml) and its counters.
        self.true_ppml = 2.25          # what the "physical" sensor really gives
        self.flow_ppml = 2.25          # what the firmware has stored after FLOW_CAL
        self.flow_pulses = 0
        self.run_pulses = 0            # pulses of the current timed run
        self.last_run_pulses = 0
        # Lines the firmware would send on its own (EVT:...), read via pop_event().
        self.events: deque[str] = deque()

    def _ml(self, pulses: int) -> str:
        return f"{pulses / self.flow_ppml:.1f}" if self.flow_ppml > 0 else "NA"

    def pop_event(self) -> str | None:
        return self.events.popleft() if self.events else None

    def send_command(self, cmd: str) -> str:
        cmd = cmd.strip()
        if cmd == "PING":
            return "PONG"
        elif cmd == "STATUS":
            state = "1" if self.pump_active else "0"
            return (
                f"OK:STATUS:PUMP={state}:TIME_LEFT=0.00:"
                f"WATER_LVL={self.water_level}:SOIL={self.soil_moisture}:"
                f"TEMP={self.temperature:.1f}:HUM={self.humidity:.1f}"
            )
        elif cmd == "TELEMETRY":
            state = "1" if self.pump_active else "0"
            return (
                f"OK:TELEMETRY:PUMP={state}:WATER={self.water_level}:"
                f"SOIL={self.soil_moisture}:TEMP={self.temperature:.1f}:HUM={self.humidity:.1f}:"
                f"WEIGHT={self.weight_g:.1f}"
            )
        elif cmd == "SCALE":
            if not self.scale_calibrated:
                return "ERR:SCALE_NOT_READY"
            return f"OK:SCALE={self.weight_g:.1f}"
        elif cmd == "TARE":
            self.weight_g = 0.0
            self.scale_calibrated = True
            return "OK:TARE:OFFSET=0"
        elif cmd == "MOISTURE":
            return f"OK:MOISTURE={self.soil_moisture}"
        elif cmd == "WATER_LEVEL":
            return f"OK:WATER_LEVEL={self.water_level}"
        elif cmd == "BEEP":
            return "OK:BEEP"
        elif cmd.startswith("WATER:"):
            try:
                sec = float(cmd.split(":", 1)[1])
            except (ValueError, IndexError):
                return "ERR:INVALID_DURATION"
            if sec <= 0:
                return "ERR:INVALID_DURATION"
            if self.water_level < 8:
                return f"ERR:WATER_EMPTY:LEVEL={self.water_level}"
            effective_sec = min(sec, MAX_PUMP_RUNTIME_SECONDS)
            self.pump_active = True
            self.last_duration = effective_sec
            self.run_pulses = round(effective_sec * DEFAULT_BENCH_FLOW_ML_PER_SEC * self.true_ppml)
            return f"OK:PUMP_ON:DURATION={effective_sec:.2f}"
        elif cmd.startswith("WATER_ML:"):
            try:
                ml = float(cmd.split(":", 1)[1])
            except (ValueError, IndexError):
                return "ERR:INVALID_VOLUME"
            if ml <= 0 or ml > MAX_DOSE_ML:
                return "ERR:INVALID_VOLUME"
            if self.flow_ppml <= 0:
                return "ERR:FLOW_NOT_CALIBRATED"
            if self.water_level < 8:
                return f"ERR:WATER_EMPTY:LEVEL={self.water_level}"
            pulses = max(1, round(ml * self.flow_ppml))
            self.flow_pulses += pulses
            self.last_run_pulses = pulses
            self.weight_g += pulses / self.true_ppml  # the water ends up in the pot on the scale
            self.events.append(f"EVT:PUMP_OFF:REASON=VOLUME_REACHED:ML={self._ml(pulses)}:PULSES={pulses}")
            return f"OK:PUMP_ON:TARGET_ML={ml:.1f}"
        elif cmd == "FLOW":
            return f"OK:FLOW:PULSES={self.flow_pulses}:ML={self._ml(self.flow_pulses)}:PPML={self.flow_ppml:.4f}"
        elif cmd == "FLOW_RESET":
            self.flow_pulses = 0
            return "OK:FLOW_RESET"
        elif cmd.startswith("FLOW_CAL:"):
            try:
                ml = float(cmd.split(":", 1)[1])
            except (ValueError, IndexError):
                return "ERR:INVALID_VOLUME"
            if ml <= 0:
                return "ERR:INVALID_VOLUME"
            if self.pump_active:
                return "ERR:PUMP_RUNNING"
            if self.last_run_pulses == 0:
                return "ERR:NO_FLOW_PULSES"
            self.flow_ppml = self.last_run_pulses / ml
            return f"OK:FLOW_CAL:PPML={self.flow_ppml:.4f}"
        elif cmd.startswith("WATER_FORCE:"):
            try:
                sec = float(cmd.split(":", 1)[1])
            except (ValueError, IndexError):
                return "ERR:INVALID_DURATION"
            if sec <= 0:
                return "ERR:INVALID_DURATION"
            effective_sec = min(sec, MAX_PUMP_RUNTIME_SECONDS)
            self.pump_active = True
            self.last_duration = effective_sec
            self.run_pulses = round(effective_sec * DEFAULT_BENCH_FLOW_ML_PER_SEC * self.true_ppml)
            return f"OK:PUMP_ON:DURATION={effective_sec:.2f}"
        elif cmd == "STOP":
            pulses = self.run_pulses if self.pump_active else 0
            if self.pump_active:
                self.flow_pulses += pulses
                self.last_run_pulses = pulses
            self.pump_active = False
            self.run_pulses = 0
            return f"OK:PUMP_OFF:REASON=MANUAL_STOP:ML={self._ml(pulses)}:PULSES={pulses}"
        return "ERR:UNKNOWN_COMMAND"

    def close(self) -> None:
        self.pump_active = False


class HardwareBridge:
    """Manages physical Serial or virtual connection to the irrigation controller."""

    def __init__(self, port: str | None = None, baudrate: int = 9600, force_virtual: bool = False) -> None:
        self.port = port
        self.baudrate = baudrate
        self.force_virtual = force_virtual
        self._serial = None
        self._virtual = VirtualArduinoBridge()
        self._is_virtual = True
        # Unsolicited firmware lines (EVT:...) kept aside so they are never taken as a reply.
        self.events: deque[str] = deque()

        if not force_virtual and port:
            self._try_connect_serial(port)

    def _try_connect_serial(self, port: str) -> bool:
        try:
            import serial
            self._serial = serial.Serial(port, self.baudrate, timeout=2.0)
            time.sleep(1.8)  # Wait for Arduino bootloader reset
            try:
                self._serial.reset_input_buffer()
            except Exception:
                pass
            self._is_virtual = False
            logger.info("Connected to physical Arduino on port %s", port)
            return True
        except Exception as exc:
            logger.warning("Could not connect to physical serial %s (%s); falling back to virtual bridge", port, exc)
            self._serial = None
            self._is_virtual = True
            return False

    @property
    def is_virtual(self) -> bool:
        return self._is_virtual

    def send_raw_command(self, command: str) -> str:
        if self._is_virtual or self._serial is None:
            return self._virtual.send_command(command)
        try:
            self._drain_waiting_lines()
            line = (command.strip() + "\n").encode("utf-8")
            self._serial.write(line)
            # Skip unsolicited lines: an "EVT:PUMP_OFF" from a timer that just ran out, or the boot banner.
            for _ in range(20):
                response = self._serial.readline().decode("utf-8", errors="replace").strip()
                if response.startswith("EVT:"):
                    self.events.append(response)
                    continue
                if response.startswith("INIT:"):
                    continue
                return response
            return ""
        except Exception as exc:
            logger.error("Serial transmission error: %s; falling back to virtual bridge", exc)
            self._is_virtual = True
            return self._virtual.send_command(command)

    def _drain_waiting_lines(self) -> None:
        """Read whatever the Arduino sent since the last command; keep EVT lines, drop the rest."""
        while getattr(self._serial, "in_waiting", 0):
            response = self._serial.readline().decode("utf-8", errors="replace").strip()
            if not response:
                break
            if response.startswith("EVT:"):
                self.events.append(response)

    def wait_event(self, prefix: str, timeout_s: float) -> str | None:
        """Return the next unsolicited line starting with prefix, or None after timeout_s."""
        deadline = time.monotonic() + timeout_s
        while True:
            for i, ev in enumerate(self.events):
                if ev.startswith(prefix):
                    del self.events[i]
                    return ev
            if self._is_virtual or self._serial is None:
                ev = self._virtual.pop_event()
                if ev is None:
                    return None
                self.events.append(ev)
                continue
            if time.monotonic() >= deadline:
                return None
            try:
                response = self._serial.readline().decode("utf-8", errors="replace").strip()
            except Exception as exc:
                logger.error("Serial read error while waiting for %s: %s", prefix, exc)
                return None
            if response.startswith("EVT:"):
                self.events.append(response)

    def dose_water(self, ml: float) -> dict[str, Any]:
        """Pump exactly `ml` millilitres, measured by the flow meter, and wait until it is done.

        The firmware stops the pump itself when the counted pulses reach the dose, or after
        30 s if they do not (empty tank, air in the hose): then success is False and
        delivered_ml says how much really went through.
        """
        mode = "virtual" if self._is_virtual else "real"
        ml = float(ml)
        if not 0 < ml <= MAX_DOSE_ML:
            return {"success": False, "mode": mode, "target_ml": ml, "delivered_ml": None,
                    "error": f"dose must be between 0 and {MAX_DOSE_ML:.0f} ml"}
        resp = self.send_raw_command(f"WATER_ML:{ml:.1f}")
        if not resp.startswith("OK:PUMP_ON"):
            return {"success": False, "mode": mode, "target_ml": ml, "delivered_ml": None,
                    "response": resp, "error": resp}
        ev = self.wait_event("EVT:PUMP_OFF", MAX_PUMP_RUNTIME_SECONDS + 5.0)
        if ev is None:
            self.stop_pump()  # never leave the pump running when the answer is lost
            return {"success": False, "mode": mode, "target_ml": ml, "delivered_ml": None,
                    "response": resp, "error": "no pump-off message from the Arduino; pump stopped"}
        f = parse_fields(ev)
        reason = f.get("REASON", "")
        ok = reason == "VOLUME_REACHED"
        return {
            "success": ok, "mode": mode, "target_ml": ml,
            "delivered_ml": _float_or_none(f.get("ML")),
            "pulses": int(f.get("PULSES", "0") or 0),
            "reason": reason, "response": ev,
            "error": None if ok else f"dose not reached: {reason}",
        }

    def get_flow(self) -> dict[str, Any]:
        """Total flow-meter count since the last FLOW_RESET."""
        resp = self.send_raw_command("FLOW")
        f = parse_fields(resp) if resp.startswith("OK:FLOW:") else {}
        return {
            "pulses": int(f["PULSES"]) if f.get("PULSES", "").isdigit() else None,
            "ml": _float_or_none(f.get("ML")),
            "pulses_per_ml": _float_or_none(f.get("PPML")),
            "calibrated": (_float_or_none(f.get("PPML")) or 0) > 0,
            "response": resp,
        }

    def reset_flow(self) -> bool:
        return self.send_raw_command("FLOW_RESET") == "OK:FLOW_RESET"

    def calibrate_flow(self, measured_ml: float) -> dict[str, Any]:
        """After a timed run (trigger_irrigation) into a measuring cylinder, store pulses per ml."""
        resp = self.send_raw_command(f"FLOW_CAL:{float(measured_ml):.1f}")
        ok = resp.startswith("OK:FLOW_CAL")
        return {"success": ok, "pulses_per_ml": _float_or_none(parse_fields(resp).get("PPML")) if ok else None,
                "response": resp, "error": None if ok else resp}

    def trigger_irrigation(self, duration_seconds: float, force: bool = False) -> dict[str, Any]:
        """Activate the pump for duration_seconds (safe-capped at 30.0s)."""
        duration = float(duration_seconds)
        if duration <= 0:
            return {
                "success": False,
                "duration": 0.0,
                "mode": "virtual" if self._is_virtual else "real",
                "error": "Invalid duration: must be positive",
            }

        effective_duration = min(duration, MAX_PUMP_RUNTIME_SECONDS)
        prefix = "WATER_FORCE" if force else "WATER"
        cmd = f"{prefix}:{effective_duration:.2f}"
        resp = self.send_raw_command(cmd)
        success = resp.startswith("OK:PUMP_ON")

        return {
            "success": success,
            "duration": effective_duration,
            "mode": "virtual" if self._is_virtual else "real",
            "response": resp,
            "error": None if success else resp,
        }

    def stop_pump(self) -> dict[str, Any]:
        """Emergency cut-off for the pump relay."""
        resp = self.send_raw_command("STOP")
        return {
            "success": resp.startswith("OK:PUMP_OFF"),
            "mode": "virtual" if self._is_virtual else "real",
            "response": resp,
        }

    def ping(self) -> bool:
        resp = self.send_raw_command("PING")
        return resp == "PONG"

    def beep(self) -> bool:
        resp = self.send_raw_command("BEEP")
        return resp == "OK:BEEP"

    def get_moisture(self) -> int:
        resp = self.send_raw_command("MOISTURE")
        if resp.startswith("OK:MOISTURE="):
            try:
                val_part = resp.split("OK:MOISTURE=")[1].split(":")[0]
                return int(val_part)
            except (ValueError, IndexError):
                pass
        return 65

    def get_water_level(self) -> int:
        resp = self.send_raw_command("WATER_LEVEL")
        if "OK:WATER_LEVEL=" in resp:
            try:
                val_part = resp.split("OK:WATER_LEVEL=")[1].split(":")[0]
                return int(val_part)
            except (ValueError, IndexError):
                pass
        return 80

    def get_weight(self) -> float | None:
        """Pot weight in grams from the HX711 scale, or None when it is not ready."""
        resp = self.send_raw_command("SCALE")
        if resp.startswith("OK:SCALE="):
            try:
                return float(resp.split("OK:SCALE=")[1].split(":")[0])
            except (ValueError, IndexError):
                return None
        return None

    def tare_scale(self) -> bool:
        return self.send_raw_command("TARE").startswith("OK:TARE")

    def calibrate_scale(self, known_grams: float) -> dict[str, Any]:
        resp = self.send_raw_command(f"CALIBRATE:{float(known_grams):.1f}")
        ok = resp.startswith("OK:CALIBRATE")
        return {"success": ok, "response": resp, "error": None if ok else resp}

    def get_telemetry(self) -> dict[str, Any]:
        """Fetch real-time comprehensive telemetry from all hardware sensors."""
        resp = self.send_raw_command("TELEMETRY")
        telemetry: dict[str, Any] = {
            "pump_active": False,
            "water_level": 80,
            "soil_moisture": 65,
            "temperature": 23.5,
            "humidity": 48.0,
            "has_water": True,
            "weight_g": None,
            "raw": resp,
        }
        if resp.startswith("OK:TELEMETRY:"):
            parts = resp.split("OK:TELEMETRY:")[1].split(":")
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k == "PUMP":
                        telemetry["pump_active"] = (v == "1")
                    elif k == "WATER":
                        try:
                            telemetry["water_level"] = int(v)
                            telemetry["has_water"] = int(v) >= 8
                        except ValueError:
                            pass
                    elif k == "SOIL":
                        try:
                            telemetry["soil_moisture"] = int(v)
                        except ValueError:
                            pass
                    elif k == "TEMP":
                        try:
                            telemetry["temperature"] = float(v)
                        except ValueError:
                            pass
                    elif k == "HUM":
                        try:
                            telemetry["humidity"] = float(v)
                        except ValueError:
                            pass
                    elif k == "WEIGHT":
                        try:
                            telemetry["weight_g"] = float(v)
                        except ValueError:
                            telemetry["weight_g"] = None  # "NA": scale absent or uncalibrated
        return telemetry


_bridge_instance: HardwareBridge | None = None


def get_hardware_bridge() -> HardwareBridge:
    """Get or initialize the global hardware bridge singleton."""
    global _bridge_instance
    if _bridge_instance is None:
        import os
        port = os.getenv("ARDUINO_PORT", "COM7")
        force_virtual = os.getenv("FORCE_VIRTUAL_ARDUINO", "0") == "1"
        _bridge_instance = HardwareBridge(port=port, force_virtual=force_virtual)
    return _bridge_instance


def calculate_pump_runtime_seconds(
    volume_liters: float,
    pump_productivity_m3h: float | None = None,
    bench_flow_ml_sec: float = DEFAULT_BENCH_FLOW_ML_PER_SEC,
) -> float:
    """
    Calculate pump operation duration in seconds from water volume.

    If pump_productivity_m3h is provided (> 0):
        flow_liters_sec = (m3_h * 1000) / 3600
        seconds = volume_liters / flow_liters_sec
    Otherwise (desktop bench scale with 3-5V pump):
        volume_ml = volume_liters * 1000
        seconds = volume_ml / bench_flow_ml_sec
    """
    if volume_liters <= 0:
        return 0.0

    if pump_productivity_m3h and pump_productivity_m3h > 0:
        flow_liters_sec = (pump_productivity_m3h * 1000.0) / 3600.0
        sec = volume_liters / flow_liters_sec
    else:
        # Bench scale
        volume_ml = volume_liters * 1000.0 if volume_liters < 1.0 else volume_liters
        sec = volume_ml / max(bench_flow_ml_sec, 0.01)

    return round(min(sec, MAX_PUMP_RUNTIME_SECONDS), 2)
