"""Raw-data journal for the pot-evaporation experiment.

One CSV row per measurement. The file is the single source of truth for the
paper: the analysis script (experiment/analyze.py) reads it unchanged, so
nothing is ever edited by hand between measurement and result.

Columns
-------
timestamp        ISO-8601 local time with UTC offset
pot_id           e.g. "A1"
group            "sutech" (irrigated by Su-Tech) or "control" (fixed schedule)
weight_g         pot weight from the HX711 scale (empty when unavailable)
soil_pct         soil moisture sensor, 0-100
temp_c, hum_pct  room microclimate (DHT11)
event            "sample" | "irrigation" | "note"
water_ml         water added in this event (irrigation rows only)
pump_seconds     pump run time (irrigation rows only)
model_et_mm      Su-Tech predicted crop water use for the day (optional)
note             free text
"""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

COLUMNS = [
    "timestamp", "pot_id", "group", "weight_g", "soil_pct", "temp_c", "hum_pct",
    "event", "water_ml", "pump_seconds", "model_et_mm", "note",
]
GROUPS = ("sutech", "control")
EVENTS = ("sample", "irrigation", "note")


class ExperimentLog:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(COLUMNS)

    def append(self, *, pot_id: str, group: str, event: str = "sample", **fields: Any) -> dict[str, Any]:
        if group not in GROUPS:
            raise ValueError(f"group must be one of {GROUPS}, got {group!r}")
        if event not in EVENTS:
            raise ValueError(f"event must be one of {EVENTS}, got {event!r}")
        unknown = set(fields) - set(COLUMNS)
        if unknown:
            raise ValueError(f"unknown columns: {sorted(unknown)}")
        row = {c: "" for c in COLUMNS}
        row.update(fields)
        row.update(
            timestamp=fields.get("timestamp") or datetime.now().astimezone().isoformat(timespec="seconds"),
            pot_id=pot_id, group=group, event=event,
        )
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=COLUMNS).writerow(row)
        return row

    def record_sample(self, bridge: Any, pot_id: str, group: str, **extra: Any) -> dict[str, Any]:
        """Read all sensors from the bridge and log one measurement row."""
        t = bridge.get_telemetry()
        weight = t.get("weight_g")
        return self.append(
            pot_id=pot_id, group=group, event="sample",
            weight_g="" if weight is None else f"{weight:.1f}",
            soil_pct=t.get("soil_moisture", ""),
            temp_c=t.get("temperature", ""), hum_pct=t.get("humidity", ""),
            **extra,
        )

    def record_irrigation(self, pot_id: str, group: str, water_ml: float, pump_seconds: float = 0.0,
                          **extra: Any) -> dict[str, Any]:
        if water_ml <= 0:
            raise ValueError("water_ml must be positive")
        return self.append(
            pot_id=pot_id, group=group, event="irrigation",
            water_ml=f"{water_ml:.1f}", pump_seconds=f"{pump_seconds:.2f}", **extra,
        )
