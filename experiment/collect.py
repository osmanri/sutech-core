"""Daily weighing session: one scale, every pot placed on it in turn.

    python experiment/collect.py --port COM7 --log data/log.csv --pots A1:sutech A2:sutech B1:control ...

For each pot the script waits for a stable weight, logs it with the room
microclimate, then asks how much water you added (0 = none) and logs that too.
Add water AFTER the weighing, the next weighing then includes it (the analysis
accounts for it). Without --port it uses the built-in virtual Arduino (a dry run).
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
    ap.add_argument("--pots", nargs="+", required=True, help="pot_id:group, e.g. A1:sutech B1:control")
    a = ap.parse_args()

    bridge = HardwareBridge(port=a.port, force_virtual=a.port is None)
    log = ExperimentLog(a.log)
    print("Mode:", "VIRTUAL (dry run)" if bridge.is_virtual else "real Arduino")
    for spec in a.pots:
        pot, group = spec.split(":", 1)
        input(f"Put pot {pot} ({group}) on the scale and press Enter... ")
        weight = stable_weight(bridge)
        t = bridge.get_telemetry()
        log.append(pot_id=pot, group=group, event="sample", weight_g=f"{weight:.1f}",
                   soil_pct=t["soil_moisture"], temp_c=t["temperature"], hum_pct=t["humidity"],
                   model_et_mm=input("  Su-Tech predicted ET for today, mm (Enter to skip): ").strip())
        ml = input("  Water added to this pot, ml (0 = none): ").strip() or "0"
        if float(ml) > 0:
            log.record_irrigation(pot, group, float(ml))
        print(f"  logged {pot}: {weight:.1f} g, +{ml} ml")


if __name__ == "__main__":
    main()
