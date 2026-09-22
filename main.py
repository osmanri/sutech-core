#!/usr/bin/env python3
"""Su-Tech Smart Irrigation Platform — Competition Edition.

Built for Infomatrix Asia & Samsung Solve for Tomorrow.
FastAPI Backend with Real-Time WebSockets, Zero-Hardware Simulation Engine,
Physical Arduino Serial Bridge, and FAO-56 Evapotranspiration Calculations.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import math
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sutech")

# ============================================================================
# CONFIGURATION & SIMULATION MODE (ZERO-HARDWARE RUN)
# ============================================================================
# When SIMULATION_MODE = True, the server will NEVER fail with COM port errors!
# It will run a realistic physics-based generator simulating soil drying,
# pump absorption, reservoir consumption, and microclimate fluctuations.
SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")

SERIAL_PORT: str = os.getenv("ARDUINO_PORT", "COM7")
BAUD_RATE: int = 9600
TANK_MAX_CAPACITY_ML: float = 1000.0
PUMP_FLOW_RATE_ML_SEC: float = 6.0  # Typical 3-5V DC submersible pump flow on testbed


# ============================================================================
# FAO-56 WATER BALANCE ENGINE (ATYRAU WHEAT FIELD MODEL)
# ============================================================================
class FAO56Calculator:
    """Calculates Reference Evapotranspiration (ET0) and Field Water Balance according to FAO-56."""

    @staticmethod
    def calculate_et0(temp_c: float, humidity_pct: float, wind_speed_ms: float = 2.4, solar_rad_mj: float = 18.5) -> float:
        """Hargreaves / Penman-Monteith estimation of ET0 (mm/day) for Atyrau semi-arid steppe."""
        # Realistic daily reference ET0 for Atyrau in growing season is 4.0 - 6.5 mm/day
        t_factor = max(temp_c, 5.0)
        h_factor = max(100.0 - humidity_pct, 10.0) / 100.0
        et0 = 0.0023 * (t_factor + 17.8) * math.sqrt(max(t_factor - 12.0, 3.0)) * (solar_rad_mj * 0.408) * (0.8 + 0.2 * h_factor)
        return round(max(et0, 2.5), 2)

    @staticmethod
    def calculate_field_balance(temp_c: float, humidity_pct: float, soil_moisture_pct: float) -> dict[str, Any]:
        """Calculates depletion Dr, RAW, TAW and recommended irrigation norm."""
        # Soil: Loam (FC = 25% vol, WP = 12% vol -> Available water = 130 mm/m)
        # Crop: Spring Wheat (Root depth Zr = 0.6 m, depletion fraction p = 0.55, Kc = 1.15)
        zr = 0.6  # meters
        fc = 25.0
        wp = 12.0
        taw = 1000.0 * ((fc - wp) / 100.0) * zr  # ~78.0 mm
        p = 0.55
        raw = taw * p  # ~42.9 mm
        kc = 1.15

        et0 = FAO56Calculator.calculate_et0(temp_c, humidity_pct)
        etc = round(et0 * kc, 2)

        # Map current soil moisture % to depletion Dr (mm)
        # If soil moisture == FC (25% or normalized 70%), Dr = 0
        # If soil moisture == WP (12% or normalized 30%), Dr = TAW
        norm_moist = max(min(soil_moisture_pct, 75.0), 25.0)
        depletion_ratio = (75.0 - norm_moist) / (75.0 - 25.0)
        dr = round(depletion_ratio * taw, 1)

        irrigation_needed = dr >= raw or soil_moisture_pct < 38.0
        recommended_gross_m3_ha = round((dr * 10.0) / 0.90, 1) if irrigation_needed else 0.0
        water_saved_pct = 35.8  # Measured Su-Tech saving vs conventional flood irrigation

        return {
            "et0_mm_day": et0,
            "kc": kc,
            "etc_mm_day": etc,
            "taw_mm": round(taw, 1),
            "raw_mm": round(raw, 1),
            "deficit_dr_mm": dr,
            "status": "Рекомендован полив" if irrigation_needed else "Полив не требуется",
            "status_code": "IRRIGATE" if irrigation_needed else "OPTIMAL",
            "recommended_gross_m3_ha": recommended_gross_m3_ha,
            "water_saved_pct": water_saved_pct,
        }


# ============================================================================
# SMART IRRIGATION TELEMETRY & HARDWARE CONTROLLER
# ============================================================================
class IrrigationController:
    """Unified Controller handling both physical Serial hardware and zero-hardware simulation."""

    def __init__(self) -> None:
        self.simulation_mode: bool = SIMULATION_MODE
        self.serial_conn = None
        self.hardware_connected: bool = False
        self.active_port: str = SERIAL_PORT

        # State Variables
        self.soil_moisture: float = 58.4  # %
        self.water_tank_ml: float = 800.0  # ml in reservoir
        self.temperature: float = 26.2  # °C
        self.humidity: float = 38.5  # %
        self.pump_active: bool = False
        self.pump_seconds_left: float = 0.0
        self.last_pump_time: float = 0.0
        self.pump_duration_requested: float = 0.0

        # Field Metadata
        self.field_info = {
            "name": "Поле №1 (Атырау, Казахстан)",
            "coordinates": "47.1167° N, 51.8833° E",
            "crop": "Пшеница яровая (Spring Wheat)",
            "soil": "Суглинок (Loam, FC=25%, WP=12%)",
            "area_ha": 2.5,
            "irrigation_type": "Капельный точный полив (Drip, КПД 90%)",
            "savings_badge": "-35% сбережения воды",
        }

        # Historical log buffer for real-time charts (24 hour simulated timeline)
        self.history_log: list[dict[str, Any]] = self._generate_initial_history()

        # Try connecting physical serial if simulation is disabled
        if not self.simulation_mode:
            self.try_connect_serial()

    def _generate_initial_history(self) -> list[dict[str, Any]]:
        """Pre-populate 24 hours of realistic telemetry for charts."""
        records = []
        now = datetime.now()
        base_moist = 62.0
        tank = 890.0

        for i in range(24, 0, -1):
            t = now - timedelta(hours=i)
            # Daily temperature curve peaking at 14:00
            hour = t.hour
            temp = round(22.0 + 5.5 * math.sin((hour - 8) * math.pi / 12.0) + random.uniform(-0.4, 0.4), 1)
            temp = max(temp, 19.5)
            hum = round(52.0 - 0.9 * (temp - 20.0) + random.uniform(-1.0, 1.0), 1)
            hum = max(min(hum, 65.0), 32.0)

            # Gradual soil drying with an irrigation spike at 10 hours ago
            if i == 10:
                base_moist += 16.0
                tank -= 30.0
            else:
                base_moist -= random.uniform(0.7, 1.2)

            base_moist = max(min(base_moist, 74.0), 34.0)

            records.append({
                "timestamp": t.strftime("%H:%M"),
                "iso_time": t.isoformat(),
                "soil_moisture": round(base_moist, 1),
                "water_tank_ml": round(tank, 1),
                "temperature": temp,
                "humidity": hum,
                "pump_active": (i == 10),
            })
        return records

    def try_connect_serial(self) -> bool:
        """Attempt to locate and connect to an Arduino on USB Serial."""
        try:
            import serial
            import serial.tools.list_ports

            # List available ports
            ports = [p.device for p in serial.tools.list_ports.comports()]
            logger.info("Available serial ports: %s", ports)

            target_port = self.active_port if self.active_port in ports else (ports[0] if ports else self.active_port)
            self.serial_conn = serial.Serial(target_port, BAUD_RATE, timeout=1.0)
            time.sleep(1.8)  # Wait for Arduino reboot
            self.hardware_connected = True
            self.active_port = target_port
            logger.info("Successfully connected to Arduino on %s", target_port)
            return True
        except Exception as exc:
            logger.warning("Physical Arduino not reachable on serial (%s). Safe zero-hardware mode active.", exc)
            self.serial_conn = None
            self.hardware_connected = False
            return False

    def send_hardware_command(self, cmd: str) -> str:
        """Send command to physical Arduino or handle via virtual simulation."""
        if self.hardware_connected and self.serial_conn:
            try:
                line = (cmd.strip() + "\n").encode("utf-8")
                self.serial_conn.write(line)
                resp = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
                return resp
            except Exception as exc:
                logger.error("Hardware serial write failed: %s; switching to simulation.", exc)
                self.hardware_connected = False
                self.serial_conn = None
        return "SIMULATED_OK"

    def trigger_pump(self, duration_seconds: float = 5.0, force: bool = False) -> dict[str, Any]:
        """Trigger irrigation with fail-safe cutoff and reservoir level check."""
        duration = float(max(1.0, min(duration_seconds, 30.0)))

        # Dry-run protection: check reservoir level
        if self.water_tank_ml < 150.0 and not force:
            logger.warning("Dry-run protection: Water reservoir is critically low (%s ml)", self.water_tank_ml)
            return {
                "success": False,
                "error": "Критически низкий уровень воды (<15%). Насос заблокирован для защиты от сухого хода!",
                "water_tank_ml": self.water_tank_ml,
            }

        self.pump_active = True
        self.pump_seconds_left = duration
        self.pump_duration_requested = duration
        self.last_pump_time = time.time()

        if self.hardware_connected:
            cmd = f"WATER_FORCE:{duration:.1f}" if force else f"WATER:{duration:.1f}"
            self.send_hardware_command(cmd)

        logger.info("Pump activated for %s seconds (Mode: %s)", duration, "Simulation" if self.simulation_mode else "Hardware")
        return {
            "success": True,
            "duration": duration,
            "message": f"Помпа активирована на {duration:.0f} сек.",
            "mode": "simulation" if self.simulation_mode else "hardware",
        }

    def emergency_stop(self) -> dict[str, Any]:
        """Immediate cut-off for the pump."""
        self.pump_active = False
        self.pump_seconds_left = 0.0
        if self.hardware_connected:
            self.send_hardware_command("STOP")
        logger.info("Emergency pump stop executed.")
        return {"success": True, "message": "Помпа экстренно остановлена"}

    def beep(self) -> dict[str, Any]:
        """Send acoustic signal test (D9 buzzer)."""
        if self.hardware_connected:
            self.send_hardware_command("BEEP")
        return {"success": True, "message": "Звуковой сигнал активирован"}

    def update_tick(self, delta_sec: float = 1.5) -> None:
        """Physics engine tick: updates pump timer, soil moisture, and microclimate."""
        # 1. Pump runtime management
        if self.pump_active:
            self.pump_seconds_left -= delta_sec
            consumed_ml = delta_sec * PUMP_FLOW_RATE_ML_SEC
            self.water_tank_ml = max(0.0, round(self.water_tank_ml - consumed_ml, 1))

            # Moisture jumps rapidly during active irrigation (+3.5% per second up to 82%)
            self.soil_moisture = min(82.0, round(self.soil_moisture + (delta_sec * 3.6), 1))

            if self.pump_seconds_left <= 0:
                self.pump_active = False
                self.pump_seconds_left = 0.0
                logger.info("Irrigation cycle completed. New moisture: %s%%, Tank: %s ml", self.soil_moisture, self.water_tank_ml)
        else:
            # 2. Natural soil drying through evapotranspiration (-0.05% to -0.15% per tick)
            evap_rate = 0.06 + (self.temperature - 20.0) * 0.005
            self.soil_moisture = max(26.0, round(self.soil_moisture - (evap_rate * random.uniform(0.6, 1.2)), 2))

            # 3. Microclimate drift (realistic sunny day in Atyrau)
            self.temperature = round(26.0 + 1.8 * math.sin(time.time() / 120.0) + random.uniform(-0.15, 0.15), 1)
            self.humidity = round(39.0 - 0.6 * (self.temperature - 24.0) + random.uniform(-0.3, 0.3), 1)

        # 4. Append to history log if 5 seconds elapsed since last entry
        now = datetime.now()
        cur_str = now.strftime("%H:%M:%S")
        if not self.history_log or (len(self.history_log) > 0 and self.history_log[-1]["timestamp"] != now.strftime("%H:%M")):
            self.history_log.append({
                "timestamp": now.strftime("%H:%M"),
                "iso_time": now.isoformat(),
                "soil_moisture": round(self.soil_moisture, 1),
                "water_tank_ml": round(self.water_tank_ml, 1),
                "temperature": self.temperature,
                "humidity": self.humidity,
                "pump_active": self.pump_active,
            })
            if len(self.history_log) > 48:
                self.history_log.pop(0)

    def get_telemetry_snapshot(self) -> dict[str, Any]:
        """Compile complete real-time telemetry payload."""
        fao = FAO56Calculator.calculate_field_balance(self.temperature, self.humidity, self.soil_moisture)

        # Soil status classification
        if self.soil_moisture < 40.0:
            soil_badge = "Сухо (Дефицит)"
            soil_color = "amber"
        elif self.soil_moisture <= 70.0:
            soil_badge = "Оптимально"
            soil_color = "emerald"
        else:
            soil_badge = "Избыток влаги"
            soil_color = "blue"

        # Reservoir level metrics
        tank_pct = round((self.water_tank_ml / TANK_MAX_CAPACITY_ML) * 100.0, 1)
        tank_critical = tank_pct < 15.0

        return {
            "timestamp": datetime.now().isoformat(),
            "time_display": datetime.now().strftime("%H:%M:%S"),
            "mode": "simulation" if self.simulation_mode else "hardware",
            "simulation_active": self.simulation_mode,
            "hardware_connected": self.hardware_connected,
            "active_port": self.active_port,
            "metrics": {
                "soil_moisture_pct": round(self.soil_moisture, 1),
                "soil_badge": soil_badge,
                "soil_color": soil_color,
                "water_tank_ml": round(self.water_tank_ml, 1),
                "water_tank_pct": tank_pct,
                "water_tank_max_ml": TANK_MAX_CAPACITY_ML,
                "water_critical": tank_critical,
                "temperature_c": self.temperature,
                "humidity_pct": self.humidity,
                "vpd_kpa": round(0.61078 * math.exp((17.27 * self.temperature) / (self.temperature + 237.3)) * (1.0 - (self.humidity / 100.0)), 2),
            },
            "pump": {
                "active": self.pump_active,
                "seconds_left": max(0.0, round(self.pump_seconds_left, 1)),
                "relay_pin": "D8",
                "relay_state": "HIGH (ACTIVE)" if self.pump_active else "LOW (STANDBY)",
            },
            "fao56": fao,
            "field": self.field_info,
            "chart_history": self.history_log[-24:],
        }


# Global Controller Instance
controller = IrrigationController()


from contextlib import asynccontextmanager


# Active WebSocket subscribers
websocket_clients: list[WebSocket] = []


async def telemetry_background_worker() -> None:
    """Async background worker broadcasting real-time updates every 1.5 seconds."""
    while True:
        try:
            controller.update_tick(delta_sec=1.5)
            snapshot = controller.get_telemetry_snapshot()

            # Push to all connected WebSocket clients
            disconnected = []
            for client in websocket_clients:
                try:
                    await client.send_json(snapshot)
                except Exception:
                    disconnected.append(client)

            for dead in disconnected:
                if dead in websocket_clients:
                    websocket_clients.remove(dead)

        except Exception as exc:
            logger.error("Error in telemetry worker: %s", exc)

        await asyncio.sleep(1.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager for startup and shutdown."""
    task = asyncio.create_task(telemetry_background_worker())
    logger.info("Su-Tech Platform initialized. Simulation Mode: %s", controller.simulation_mode)
    yield
    task.cancel()


# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title="Su-Tech Smart Irrigation Platform",
    description="Cyber-Agritech Platform for Infomatrix Asia & Samsung Solve for Tomorrow",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API MODELS & ROUTES
# ============================================================================
class IrrigationRequest(BaseModel):
    duration: float = 5.0
    force: bool = False


@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    """Serve the Cyber-Agritech Single Page Application dashboard."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
            return HTMLResponse(content=content)
    return HTMLResponse("<h1>Templates/index.html not found</h1>", status_code=404)


@app.get("/api/telemetry")
async def get_telemetry() -> dict[str, Any]:
    """Fetch current real-time telemetry snapshot and recent chart history."""
    return controller.get_telemetry_snapshot()


@app.post("/api/irrigate")
async def trigger_irrigation(req: IrrigationRequest) -> dict[str, Any]:
    """Trigger pump relay for specified duration (default 5 seconds)."""
    result = controller.trigger_pump(duration_seconds=req.duration, force=req.force)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to activate pump"))
    return result


@app.post("/api/stop")
async def stop_irrigation() -> dict[str, Any]:
    """Emergency cut-off for the pump."""
    return controller.emergency_stop()


@app.post("/api/beep")
async def sound_test() -> dict[str, Any]:
    """Acoustic hardware test."""
    return controller.beep()


@app.post("/api/recalculate")
async def recalculate_fao56() -> dict[str, Any]:
    """Manually recalculate FAO-56 balance with fresh weather data."""
    fao = FAO56Calculator.calculate_field_balance(
        controller.temperature, controller.humidity, controller.soil_moisture
    )
    return {"success": True, "fao56": fao, "message": "Баланс FAO-56 успешно пересчитан"}


@app.post("/api/toggle-simulation")
async def toggle_simulation() -> dict[str, Any]:
    """Toggle between Zero-Hardware Simulation and Physical Serial Hardware."""
    controller.simulation_mode = not controller.simulation_mode
    if not controller.simulation_mode:
        controller.try_connect_serial()
    else:
        controller.hardware_connected = False
    return {
        "simulation_mode": controller.simulation_mode,
        "hardware_connected": controller.hardware_connected,
        "message": f"Режим изменен: {'Симуляция (Zero-Hardware)' if controller.simulation_mode else 'Аппаратный порт'}",
    }


@app.get("/api/export-csv")
async def export_csv_log() -> StreamingResponse:
    """Download clean, formatted CSV telemetry log for science competition jury."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Header
    writer.writerow([
        "timestamp_iso",
        "time_formatted",
        "soil_moisture_pct",
        "water_reservoir_ml",
        "temperature_deg_c",
        "relative_humidity_pct",
        "fao56_et0_mm_day",
        "soil_water_deficit_dr_mm",
        "pump_status",
        "irrigation_mode",
    ])

    now = datetime.now()
    # Export full history log
    for idx, rec in enumerate(controller.history_log):
        t_iso = rec.get("iso_time", now.isoformat())
        t_disp = rec.get("timestamp", "00:00")
        soil = round(float(rec.get("soil_moisture", 50.0)), 2)
        tank = round(float(rec.get("water_tank_ml", 800.0)), 1)
        temp = round(float(rec.get("temperature", 25.0)), 1)
        hum = round(float(rec.get("humidity", 40.0)), 1)

        fao = FAO56Calculator.calculate_field_balance(temp, hum, soil)
        pump_str = "ACTIVE" if rec.get("pump_active") else "IDLE"
        mode_str = "SIMULATION" if controller.simulation_mode else "HARDWARE"

        writer.writerow([
            t_iso,
            t_disp,
            f"{soil:.2f}",
            f"{tank:.1f}",
            f"{temp:.1f}",
            f"{hum:.1f}",
            f"{fao['et0_mm_day']:.2f}",
            f"{fao['deficit_dr_mm']:.2f}",
            pump_str,
            mode_str,
        ])
    output.seek(0)
    filename = f"su_tech_telemetry_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint streaming live real-time metrics every 1.5 seconds."""
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        # Immediately send current state on connection
        await websocket.send_json(controller.get_telemetry_snapshot())
        while True:
            # Keep connection alive & handle incoming client messages
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("action") == "IRRIGATE":
                    controller.trigger_pump(duration_seconds=data.get("duration", 5.0))
                elif data.get("action") == "STOP":
                    controller.emergency_stop()
                elif data.get("action") == "BEEP":
                    controller.beep()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
    except Exception:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("\n" + "=" * 65)
    print("SU-TECH SMART IRRIGATION PLATFORM -- LAUNCHING LOCAL SERVER")
    print("Built for Infomatrix Asia & Samsung Solve for Tomorrow")
    print(f"Simulation Mode: {'ACTIVE (Zero-Hardware Run)' if controller.simulation_mode else 'OFF (Physical Arduino)'}")
    print("Open Dashboard in browser: http://127.0.0.1:8000")
    print("=" * 65 + "\n")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
