"""Illustrative greenhouse cost scenarios. All prices are test assumptions."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Scenario:
    water_m3: float
    power_kw: float
    flow_m3h: float
    labour_hours: float
    water_per_m3: float
    energy_per_kwh: float
    labour_per_hour: float
    service: float = 0
    equipment_per_season: float = 0

    def totals(self):
        if not all(isfinite(v) and v >= 0 for v in vars(self).values()) or self.flow_m3h <= 0:
            raise ValueError("Inputs must be finite and nonnegative with a positive pump flow")
        hours = self.water_m3 / self.flow_m3h
        energy = hours * self.power_kw
        water_cost = self.water_m3 * self.water_per_m3
        energy_cost = energy * self.energy_per_kwh
        labour_cost = self.labour_hours * self.labour_per_hour
        return {
            "water_m3": self.water_m3, "pump_hours": hours, "energy_kwh": energy,
            "water_cost": water_cost, "energy_cost": energy_cost, "labour_cost": labour_cost,
            "service": self.service, "equipment": self.equipment_per_season,
            "total": water_cost + energy_cost + labour_cost + self.service + self.equipment_per_season,
        }


def examples():
    """Same-pump scheduling contrast, followed by a pump-only contrast."""
    return {
        "calendar": Scenario(120, .4, 2, 12, 50, 30, 1500),
        "scheduling": Scenario(102, .4, 2, 11, 50, 30, 1500, service=1200),
        "scheduling_new_pump": Scenario(102, .3, 2, 11, 50, 30, 1500, service=1200, equipment_per_season=500),
    }


if __name__ == "__main__":
    import json
    print(json.dumps({name: scenario.totals() for name, scenario in examples().items()}, indent=2))
