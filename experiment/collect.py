"""Daily weighing session: one scale, every pot placed on it in turn.

    python experiment/collect.py --port COM7 --log data/log.csv --pots A1:sutech A2:sutech B1:control ...

For each pot the script records a stable pre-irrigation weight and, on watering
days, the post-irrigation weight and captured drainage. Without --port it uses
the virtual Arduino and writes to data/virtual-log.csv by default.

With --dose the flow meter controls the pump and provides a cross-check for the
scale measurement. Calibrate the meter first:

    python experiment/collect.py --port COM7 --calibrate-flow

Without --dose you pour a measured volume by hand.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.experiment_log import GROUPS, ExperimentLog
from bot.hardware_bridge import HardwareBridge


def stable_weight(bridge: HardwareBridge, tolerance_g: float = 0.5, needed: int = 3, timeout_s: float = 30.0) -> float:
    """Return a weight once `needed` consecutive readings agree within tolerance."""
    deadline = time.monotonic() + timeout_s
    recent: list[float] = []
    while time.monotonic() < deadline:
        w = bridge.get_weight()
        if w is not None and math.isfinite(w) and w >= 0:
            recent = (recent + [w])[-needed:]
            if len(recent) == needed and max(recent) - min(recent) <= tolerance_g:
                return sum(recent) / needed
        time.sleep(0.5)
    raise TimeoutError("weight did not stabilise: check the scale and that the pot is not touched")


def read_volume(prompt: str, *, allow_blank: bool = False) -> float | None:
    while True:
        raw = input(prompt).strip()
        if allow_blank and not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            value = math.nan
        if math.isfinite(value) and value >= 0:
            return value
        print("Enter a finite nonnegative number.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port, e.g. COM7 or /dev/ttyUSB0 (omit for a virtual dry run)")
    ap.add_argument("--log", help="output CSV (defaults to data/log.csv with --port)")
    ap.add_argument("--pots", nargs="+", help="pot_id:group, e.g. A1:sutech B1:control")
    ap.add_argument("--dose", action="store_true", help="pour with the pump + flow meter instead of by hand")
    ap.add_argument("--calibrate-flow", action="store_true", help="calibrate the flow meter and exit")
    a = ap.parse_args()

    if not (a.pots or a.calibrate_flow):
        ap.error("--pots is required for collection")
    pots = {}
    for spec in a.pots or ():
        pot, _, group = spec.partition(":")
        pot = pot.strip()
        if not pot or group not in GROUPS or pot in pots:
            ap.error(f"give each pot once as pot_id:sutech or pot_id:control, got {spec!r}")
        pots[pot] = group
    bridge = HardwareBridge(port=a.port, force_virtual=a.port is None)
    if a.port and bridge.is_virtual:
        ap.error(f"could not connect to an Arduino at {a.port}")
    print("Mode:", "VIRTUAL (dry run)" if bridge.is_virtual else "real Arduino")
    if a.calibrate_flow:
        calibrate_flow(bridge)
        return
    if a.dose and not bridge.get_flow()["calibrated"]:
        ap.error("the flow meter is not calibrated: run with --calibrate-flow first")
    try:
        log = ExperimentLog(a.log or ("data/virtual-log.csv" if bridge.is_virtual else "data/log.csv"))
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    if "drainage_ml" not in log.columns:
        ap.error("this legacy journal has no drainage column; use a new --log file for collection")
    for pot, group in pots.items():
        if log.assignments.get(pot, group) != group:
            ap.error(f"the log assigns pot {pot!r} to {log.assignments[pot]!r}")
    for pot, group in pots.items():
        prediction = read_volume("  Su-Tech ET rate for the interval just ended, mm/day (Enter to skip): ", allow_blank=True)
        if pot in log.assignments:
            delayed = read_volume(f"  Pot {pot} delayed drainage since the prior session, ml (0 if checked and none, Enter if unknown): ",
                                  allow_blank=True)
            log.append(pot_id=pot, group=group, event="drainage", drainage_ml=delayed)
        input(f"Put pot {pot} ({group}) on the scale and press Enter... ")
        weight = stable_weight(bridge)
        timestamp = datetime.now().astimezone().isoformat()
        t = bridge.get_telemetry()
        log.append(pot_id=pot, group=group, event="sample", timestamp=timestamp, weight_g=f"{weight:.1f}",
                   soil_pct=t["soil_moisture"], temp_c=t["temperature"], hum_pct=t["humidity"], model_et_mm=prediction,
                   note="VIRTUAL: dry run" if bridge.is_virtual else "")
        target = read_volume("  Planned water for this pot, ml (0 = none): ")
        if target == 0:
            continue
        reference = target
        note = f"hand-measured dose {target:.1f} ml"
        if a.dose:
            r = bridge.dose_water(target)
            reference = r["delivered_ml"]
            note = f"flow meter {reference} ml, target {target:.1f} ml, {r.get('reason', '')}"
            if not r["success"]:
                print("  ! dose not completed:", r["error"], "- check the tank and the hose")
        if bridge.is_virtual:
            if reference:
                log.record_irrigation(pot, group, reference, drainage_ml=0, note=f"VIRTUAL: {note}")
            continue
        if not a.dose:
            input(f"Pour {target:.1f} ml by hand into the pot and press Enter... ")
        input("Wait for immediate drainage to finish, then weigh the pot without its catch tray. Press Enter... ")
        try:
            after = stable_weight(bridge)
            drained = read_volume("  Measured immediate drainage, ml (0 if checked and none): ")
            if reference == 0 and drained == 0 and round(after, 1) == round(weight, 1):
                log.append(pot_id=pot, group=group, event="note", note=f"No water delivered. {note}")
                continue
            row = log.record_scale_irrigation(pot, group, weight, after, drained, note=note)
        except (TimeoutError, ValueError) as exc:
            log.append(pot_id=pot, group=group, event="note", note=f"MISSING_IRRIGATION_VOLUME: {note}; {exc}")
            ap.error(f"{pot}: {exc}. The unmeasured dose was logged; check the measurement before continuing.")
        gross = float(row["water_ml"])
        if reference is not None and abs(reference - gross) > 0.1 * gross:
            print("  ! scale and reference differ by more than 10%. Check the measurements and calibration.")
        print(f"  logged {pot}: {gross:.1f} ml applied, {drained:.1f} ml drained")


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
