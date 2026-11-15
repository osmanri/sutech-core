"""Daily weighing session: one scale, every pot placed on it in turn.

    python experiment/collect.py --port COM7 --log data/log.csv --pots A1:sutech A2:sutech B1:control ...

For each pot the script waits for a stable weight, logs it with the room
microclimate, then asks how much water you added (0 = none) and logs that too.
Add water AFTER the weighing, the next weighing then includes it (the analysis
accounts for it). Without --port it uses the built-in virtual Arduino (a dry run).

With --dose the pump pours the water through the flow meter (WATER_ML) and the log
gets the volume the meter counted. Calibrate the meter first:

    python experiment/collect.py --port COM7 --calibrate-flow

Without --dose you pour by hand and type the volume.
"""

from __future__ import annotations

import argparse
import time

from bot.experiment_log import ExperimentLog
from bot.hardware_bridge import HardwareBridge


def stable_weight(bridge: HardwareBridge, tolerance_g: float = 0.5, needed: int = 3, timeout_s: float = 30.0) -> float:
    """Return a weight once `needed` consecutive readings agree within tolerance."""
    deadline = time.monotonic() + timeout_s
    recent: list[float] = []
    while time.monotonic() < deadline:
        w = bridge.get_weight()
        if w is not None:
            recent = (recent + [w])[-needed:]
            if len(recent) == needed and max(recent) - min(recent) <= tolerance_g:
                return sum(recent) / needed
        time.sleep(0.5)
    raise TimeoutError("weight did not stabilise: check the scale and that the pot is not touched")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port, e.g. COM7 or /dev/ttyUSB0 (omit for a virtual dry run)")
    ap.add_argument("--log", default="data/log.csv")
    ap.add_argument("--pots", nargs="+", help="pot_id:group, e.g. A1:sutech B1:control")
    ap.add_argument("--dose", action="store_true", help="pour with the pump + flow meter instead of by hand")
    ap.add_argument("--calibrate-flow", action="store_true", help="calibrate the flow meter and exit")
    a = ap.parse_args()

    bridge = HardwareBridge(port=a.port, force_virtual=a.port is None)
    print("Mode:", "VIRTUAL (dry run)" if bridge.is_virtual else "real Arduino")
    if a.calibrate_flow:
        calibrate_flow(bridge)
        return
    if not a.pots:
        ap.error("--pots is required")
    if a.dose and not bridge.get_flow()["calibrated"]:
        ap.error("the flow meter is not calibrated: run with --calibrate-flow first")
    log = ExperimentLog(a.log)
    for spec in a.pots:
        pot, group = spec.split(":", 1)
        input(f"Put pot {pot} ({group}) on the scale and press Enter... ")
        weight = stable_weight(bridge)
        t = bridge.get_telemetry()
        log.append(pot_id=pot, group=group, event="sample", weight_g=f"{weight:.1f}",
                   soil_pct=t["soil_moisture"], temp_c=t["temperature"], hum_pct=t["humidity"],
                   model_et_mm=input("  Su-Tech predicted ET for today, mm (Enter to skip): ").strip())
        ml = float(input("  Water for this pot, ml (0 = none): ").strip() or "0")
        if ml > 0 and a.dose:
            r = bridge.dose_water(ml)
            if r["delivered_ml"]:
                log.record_irrigation(pot, group, r["delivered_ml"],
                                      note=f"flow meter dose, target {ml:.1f} ml, {r.get('reason', '')}")
            if not r["success"]:
                print("  ! dose not completed:", r["error"], "- check the tank and the hose")
            ml = r["delivered_ml"] or 0.0
        elif ml > 0:
            log.record_irrigation(pot, group, ml, note="poured by hand")
        print(f"  logged {pot}: {weight:.1f} g, +{ml:.1f} ml")


def calibrate_flow(bridge: HardwareBridge, seconds: float = 10.0) -> None:
    """Timed run into a measuring cylinder, then store pulses per ml in the Arduino's EEPROM."""
    input(f"Put the hose into an empty measuring cylinder and press Enter (pump runs {seconds:.0f} s)... ")
    r = bridge.trigger_irrigation(seconds)
    if not r["success"]:
        print("Pump did not start:", r["error"])
        return
    if bridge.is_virtual:
        bridge.stop_pump()
    else:
        bridge.wait_event("EVT:PUMP_OFF", seconds + 5.0)
    ml = float(input("How many ml are in the cylinder? ").strip())
    cal = bridge.calibrate_flow(ml)
    if cal["success"]:
        print(f"Saved: {cal['pulses_per_ml']:.3f} pulses per ml. Repeat 3 times; the values should agree within 5%.")
    else:
        print("Calibration failed:", cal["error"])


if __name__ == "__main__":
    main()
