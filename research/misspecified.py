"""Su-Tech against the strongest calendar when the model is WRONG about the real crop and soil.

simulate.py lets the bot and the "real field" share the same equations, which flatters the bot. Here the
real crop and soil differ from what the bot believes:

  * crop coefficient of the real crop = model Kc x 0.85 or x 1.15;
  * plant-available water of the real soil = model TAW x 0.80 or x 1.20;
  * both at once in the two worst directions (crop uses more AND soil holds less, and the opposite).

Su-Tech decides with its (wrong) model; the strongest equal-yield calendar is searched with hindsight on
the REAL field, so the comparison stays as hard as possible for Su-Tech. Su-Tech is run twice:
without any correction, and with the bot's weekly three-level check (wet / normal / dry). The check
replaces the bot's estimate by the real depletion snapped to 0, RAW/2 or RAW, as simulate.sutech_decider does.

Result: how much water Su-Tech saves, and what it costs in stress and yield, when its parameters are off by
15-20 %. Run: python -m research.misspecified   ->  research/results/misspecified.{csv,md}
"""
from __future__ import annotations

import csv
import random
from statistics import mean

from research.simulate import (apply_study_engine, KY, LOCATIONS, ROOT, YEARS, best_safe_calendar, calendar_decider, fetch_power,
                               mean_daily_demand, run_season, season_weather, sutech_decider, truth_differs)

SCENARIOS = {
    "model_correct": (1.0, 1.0),
    "crop_uses_15pct_less": (0.85, 1.0),
    "crop_uses_15pct_more": (1.15, 1.0),
    "soil_holds_20pct_less": (1.0, 0.8),
    "soil_holds_20pct_more": (1.0, 1.2),
    "worst_dry_crop_more_soil_less": (1.15, 0.8),
    "worst_wet_crop_less_soil_more": (0.85, 1.2),
}
CHECK_EVERY = 7


def run(soil: str = "loam", crops=("cotton", "corn"), methods=("drip", "furrow")) -> list[dict]:
    rows = []
    for scenario, (kc_mult, taw_mult) in SCENARIOS.items():
        with truth_differs(kc_mult, taw_mult):
            for crop in crops:
                for method in methods:
                    for loc, (lat, lon) in LOCATIONS.items():
                        seasons = {y: season_weather(fetch_power(loc, lat, lon, y), crop, y) for y in YEARS}
                        demand = mean_daily_demand(crop, soil, method, list(seasons.values()))
                        n, m = best_safe_calendar(crop, soil, method, list(seasons.values()), demand)
                        for y, w in seasons.items():
                            cal = run_season(crop, soil, method, w, calendar_decider(n, demand * n * m))
                            for name, check in (("sutech_no_check", None), ("sutech_weekly_check", CHECK_EVERY)):
                                decide, _ = sutech_decider(crop, soil, method, check_every=check, categorical=bool(check),
                                                           rng=random.Random(0))
                                s = run_season(crop, soil, method, w, decide)
                                rows.append(dict(scenario=scenario, crop=crop, method=method, location=loc, year=y, strategy=name,
                                                 water_m3_ha=s.gross_mm * 10, calendar_m3_ha=cal.gross_mm * 10,
                                                 stress_days=s.stress_days, calendar_stress_days=cal.stress_days,
                                                 rel_yield=s.relative_yield(KY[crop]), calendar_rel_yield=cal.relative_yield(KY[crop])))
    return rows


def write(rows: list[dict]) -> list[str]:
    out = ROOT / "research" / "results"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "misspecified.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = ["# Su-Tech when the model is wrong about the real crop and soil (loam)", "",
             "Real crop Kc and soil plant-available water differ from the bot's parameters. Calendar = the strongest "
             "equal-yield calendar searched with hindsight on the REAL field. 5 regions x 5 seasons per row.", "",
             "| scenario | strategy | water vs calendar (mean / worst season) | seasons with less water | stress days (Su-Tech / calendar) | relative yield (Su-Tech mean / worst) |",
             "|---|---|---|---|---|---|"]
    for scenario in SCENARIOS:
        for strategy in ("sutech_no_check", "sutech_weekly_check"):
            rs = [r for r in rows if r["scenario"] == scenario and r["strategy"] == strategy]
            diff = [(r["water_m3_ha"] - r["calendar_m3_ha"]) / r["calendar_m3_ha"] * 100 for r in rs]
            less = sum(d < 0 for d in diff)
            lines.append(f"| {scenario} | {strategy} | {mean(diff):+.1f} % / {max(diff):+.1f} % | {less}/{len(rs)} | "
                         f"{mean(r['stress_days'] for r in rs):.1f} / {mean(r['calendar_stress_days'] for r in rs):.1f} | "
                         f"{mean(r['rel_yield'] for r in rs):.3f} / {min(r['rel_yield'] for r in rs):.3f} |")
    (out / "misspecified.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lines


if __name__ == "__main__":
    apply_study_engine()
    print("\n".join(write(run())))
