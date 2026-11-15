"""How robust are Su-Tech's decisions to wrong inputs? (Monte Carlo, seeded, reproducible.)

Truth = real weather on loam (as in simulate.py). The app decides with:
  * ET0 forecast error: forecast = truth x exp(N(0, sigma)), sigma = 10 / 20 / 30 %;
  * missed rain: the app never sees rain (worst case of a bad precipitation forecast);
  * systematic ET0 bias of -20 % / +20 % (a forecast that is always too low / too high);
  * the -20 % bias corrected by a soil-moisture check every 7 or 3 days
    (sensor error N(0, 10 mm) on the root-zone depletion);
  * wrong soil entered by the farmer: sand or clay instead of loam.
Outputs water use, stress days and relative yield next to the perfect-information run and
the equal-yield safe calendar, so every scenario can be judged against the same baseline.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from statistics import mean

from research.simulate import (KY, LOCATIONS, ROOT, SAFE_INTERVAL, YEARS, calendar_decider, fetch_power,
                               mean_daily_demand, run_season, safe_multiplier, season_weather, sutech_decider)

REPLICATES = 20
SEED = 20261115


def scenarios():
    yield "perfect", dict()
    for sigma in (0.10, 0.20, 0.30):
        yield f"et0_error_{int(sigma * 100)}pct", dict(sigma=sigma)
    for bias in (-0.20, +0.20):
        yield f"et0_bias_{int(bias * 100):+d}pct", dict(bias=bias)
    for every in (7, 3):
        yield f"et0_bias_-20pct_soil_check_{every}d", dict(bias=-0.20, check_every=every, sensor_sd_mm=10.0)
    yield "rain_never_forecast", dict(no_rain=True)
    for app_soil in ("sand", "clay"):
        yield f"soil_entered_{app_soil}", dict(app_soil=app_soil)


def forecast_for(weather, rng, sigma=0.0, no_rain=False, bias=0.0):
    return [(et0 * (1.0 + bias) * (math.exp(rng.gauss(0.0, sigma)) if sigma else 1.0), 0.0 if no_rain else rain)
            for et0, rain in weather]


def run(crop="cotton", method="drip", soil="loam", out=None):
    out = out or ROOT / "research" / "results" / f"sensitivity_{crop}_{method}.csv"
    rng = random.Random(SEED)
    rows = []
    for loc, (lat, lon) in LOCATIONS.items():
        seasons = {y: season_weather(fetch_power(loc, lat, lon, y), crop, y) for y in YEARS}
        demand = mean_daily_demand(crop, soil, method, list(seasons.values()))
        n = SAFE_INTERVAL[method]
        m = safe_multiplier(crop, soil, method, list(seasons.values()), n, demand)
        for y, w in seasons.items():
            safe = run_season(crop, soil, method, w, calendar_decider(n, demand * n * m))
            for name, cfg in scenarios():
                reps = REPLICATES if (cfg.get("sigma") or cfg.get("sensor_sd_mm")) else 1
                for _ in range(reps):
                    decide, _ = sutech_decider(crop, soil, method, app_soil=cfg.get("app_soil"),
                                               check_every=cfg.get("check_every"),
                                               sensor_sd_mm=cfg.get("sensor_sd_mm", 0.0), rng=rng)
                    s = run_season(crop, soil, method, w, decide, forecast_for(w, rng, cfg.get("sigma", 0.0), cfg.get("no_rain", False), cfg.get("bias", 0.0)))
                    rows.append(dict(scenario=name, location=loc, year=y, water_m3_ha=s.gross_mm * 10,
                                     stress_days=s.stress_days, rel_yield=s.relative_yield(KY[crop]),
                                     safe_calendar_m3_ha=safe.gross_mm * 10))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"# Sensitivity of Su-Tech decisions ({crop}, {method}, true soil {soil})", "",
             f"{len(LOCATIONS)} locations x {len(YEARS)} seasons; ET0-error scenarios repeated {REPLICATES}x (seed {SEED}).", "",
             "| scenario | water m³/ha | vs safe calendar | stress days | rel. yield (mean / worst) |", "|---|---|---|---|---|"]
    for name, _ in scenarios():
        rs = [r for r in rows if r["scenario"] == name]
        vs = mean((r["water_m3_ha"] - r["safe_calendar_m3_ha"]) / r["safe_calendar_m3_ha"] * 100 for r in rs)
        lines.append(f"| {name} | {mean(r['water_m3_ha'] for r in rs):.0f} | {vs:+.1f} % | "
                     f"{mean(r['stress_days'] for r in rs):.1f} | {mean(r['rel_yield'] for r in rs):.3f} / {min(r['rel_yield'] for r in rs):.3f} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


if __name__ == "__main__":
    for method in ("drip", "furrow"):
        print("\n".join(run(method=method)), end="\n\n")
