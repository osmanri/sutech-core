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
event            "sample" | "irrigation" | "drainage" | "note"
water_ml         gross water applied (irrigation rows only)
pump_seconds     pump run time (irrigation rows only)
model_et_mm      Su-Tech daily-rate prediction for the interval ending at this sample
note             free text
drainage_ml      measured immediate or delayed drainage (zero = checked and none, blank = unknown)
post_weight_g    weight after irrigation and immediate drainage (irrigation rows only)
"""

from __future__ import annotations

import csv
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any

LEGACY_COLUMNS = [
    "timestamp", "pot_id", "group", "weight_g", "soil_pct", "temp_c", "hum_pct",
    "event", "water_ml", "pump_seconds", "model_et_mm", "note",
]
COLUMNS = [*LEGACY_COLUMNS, "drainage_ml", "post_weight_g"]
GROUPS = ("sutech", "control")
EVENTS = ("sample", "irrigation", "drainage", "note")


class ExperimentLog:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.columns = COLUMNS
        self.assignments: dict[str, str] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(COLUMNS)
        else:
            with self.path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames not in (COLUMNS, LEGACY_COLUMNS):
                    raise ValueError(f"{self.path}: unsupported experiment log header")
                self.columns = reader.fieldnames
                for row in reader:
                    if self.assignments.setdefault(row["pot_id"], row["group"]) != row["group"]:
                        raise ValueError(f"{self.path}: conflicting group assignment for pot {row['pot_id']!r}")

    def append(self, *, pot_id: str, group: str, event: str = "sample", **fields: Any) -> dict[str, Any]:
        pot_id = pot_id.strip()
        if not pot_id:
            raise ValueError("pot_id must be nonempty")
        if group not in GROUPS:
            raise ValueError(f"group must be one of {GROUPS}, got {group!r}")
        if event not in EVENTS:
            raise ValueError(f"event must be one of {EVENTS}, got {event!r}")
        if self.assignments.get(pot_id, group) != group:
            raise ValueError(f"group assignment changed for pot {pot_id!r}")
        unknown = set(fields) - set(self.columns)
        if unknown:
            raise ValueError(f"columns unavailable in this log: {sorted(unknown)}")
        if event == "drainage" and "drainage_ml" not in self.columns:
            raise ValueError("this legacy journal has no drainage column")
        row = dict.fromkeys(self.columns, "")
        row.update(fields)
        row.update(
            timestamp=fields.get("timestamp") or datetime.now().astimezone().isoformat(timespec="microseconds"),
            pot_id=pot_id, group=group, event=event,
        )
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=self.columns).writerow(row)
        self.assignments[pot_id] = group
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
                          *, drainage_ml: float | None = None, **extra: Any) -> dict[str, Any]:
        if not math.isfinite(water_ml) or water_ml <= 0:
            raise ValueError("water_ml must be finite and positive")
        if not math.isfinite(pump_seconds) or pump_seconds < 0:
            raise ValueError("pump_seconds must be finite and nonnegative")
        if drainage_ml is not None:
            if not math.isfinite(drainage_ml) or drainage_ml < 0:
                raise ValueError("drainage_ml must be finite and nonnegative")
            extra["drainage_ml"] = f"{drainage_ml:.1f}"
        return self.append(
            pot_id=pot_id, group=group, event="irrigation",
            water_ml=f"{water_ml:.1f}", pump_seconds=f"{pump_seconds:.2f}", **extra,
        )

    def record_scale_irrigation(self, pot_id: str, group: str, weight_before_g: float, weight_after_g: float,
                                drainage_ml: float, **extra: Any) -> dict[str, Any]:
        values = (weight_before_g, weight_after_g, drainage_ml)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("scale weights and drainage must be finite and nonnegative")
        before, after, drainage = (round(value, 1) for value in values)
        gross_ml = round(after - before + drainage, 1)
        return self.record_irrigation(pot_id, group, gross_ml, drainage_ml=drainage,
                                      post_weight_g=f"{after:.1f}", **extra)
