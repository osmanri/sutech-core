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

    def send_command(self, cmd: str) -> str:
        cmd = cmd.strip()
        if cmd == "PING":
            return "PONG"
        elif cmd == "STATUS":
            state = "1" if self.pump_active else "0"
            return f"OK:STATUS:PUMP={state}:TIME_LEFT=0.00"
        elif cmd.startswith("WATER:"):
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
            time.sleep(1.5)  # Wait for Arduino bootloader reset
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

    def trigger_irrigation(self, duration_seconds: float) -> dict[str, Any]:
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
        cmd = f"WATER:{effective_duration:.2f}"
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


_bridge_instance: HardwareBridge | None = None


def get_hardware_bridge() -> HardwareBridge:
    """Get or initialize the global hardware bridge singleton."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = HardwareBridge(force_virtual=True)
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
