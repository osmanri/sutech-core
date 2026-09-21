"""Hardware communication bridge between Su-Tech Bot and Arduino/ESP32 testbed.

Supports both physical USB Serial connection and an embedded Virtual Bridge
for automatic testing, CI/CD, and offline demonstration.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Hard limits for desktop bench safety
MAX_PUMP_RUNTIME_SECONDS = 30.0
DEFAULT_BENCH_FLOW_ML_PER_SEC = 5.0  # Measured laboratory calibration (5 ml/s)


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
                f"SOIL={self.soil_moisture}:TEMP={self.temperature:.1f}:HUM={self.humidity:.1f}"
            )
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
            return f"OK:PUMP_ON:DURATION={effective_sec:.2f}"
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
            return f"OK:PUMP_ON:DURATION={effective_sec:.2f}"
        elif cmd == "STOP":
            self.pump_active = False
            return "OK:PUMP_OFF:REASON=MANUAL_STOP"
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
            line = (command.strip() + "\n").encode("utf-8")
            self._serial.write(line)
            response = self._serial.readline().decode("utf-8", errors="replace").strip()
            return response
        except Exception as exc:
            logger.error("Serial transmission error: %s; falling back to virtual bridge", exc)
            self._is_virtual = True
            return self._virtual.send_command(command)

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
