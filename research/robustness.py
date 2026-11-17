"""Does the headline result survive other soils and planting dates?

Repeats the equal-yield comparison of simulate.py for every combination of
soil (sand, loam, clay) and planting date (15 April, 1 May, 15 May), cotton and maize,
drip and furrow, 5 locations x 5 seasons. Output: research/results/robustness.{csv,md}.
"""

from __future__ import annotations

import csv
from statistics import mean

import research.simulate as sim

SOILS = ("sand", "loam", "clay")
PLANTINGS = {"15 Apr": (4, 15), "1 May": (5, 1), "15 May": (5, 15)}


def run() -> list[dict]:
    rows = []
    original = dict(sim.PLANTING)
    try:
        for label, md in PLANTINGS.items():
            for crop in ("cotton", "corn"):
                sim.PLANTING[crop] = md
            for soil in SOILS:
                runs = sim.simulate(soil=soil)
                for s in sim.summarise(runs):
                    if s["strategy"] != "calendar_best":
                        continue
                    sut = next(x for x in sim.summarise(runs) if (x["crop"], x["method"], x["strategy"]) == (s["crop"], s["method"], "sutech"))
                    rows.append(dict(planting=label, soil=soil, crop=s["crop"], method=s["method"],
                                     saving_pct=-s["sutech_vs_this_pct"], worst_pct=-s["pair_max"], best_pct=-s["pair_min"],
                                     seasons_less=s["sutech_less_water_in"], n=s["n"],
                                     sutech_stress_days=sut["stress_days"], calendar_rel_yield=s["rel_yield"]))
    finally:
        sim.PLANTING.clear()
        sim.PLANTING.update(original)
    return rows


def write(rows: list[dict]) -> list[str]:
    out = sim.ROOT / "research" / "results"
    with (out / "robustness.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = ["# Robustness: soils x planting dates (equal-yield comparison)", "",
             f"{len(rows)} combinations; each is 5 locations x 5 seasons.", "",
             "| planting | soil | crop | method | Su-Tech saving | worst / best season | seasons with less water | Su-Tech stress days |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['planting']} | {r['soil']} | {r['crop']} | {r['method']} | {r['saving_pct']:.1f} % | "
                     f"{r['worst_pct']:.1f} / {r['best_pct']:.1f} % | {r['seasons_less']}/{r['n']} | {r['sutech_stress_days']:.1f} |")
    sav = [r["saving_pct"] for r in rows]
    lines += ["", f"Saving range over all {len(rows)} combinations: {min(sav):.1f}–{max(sav):.1f} % (mean {mean(sav):.1f} %); "
              f"worst single season anywhere: {min(r['worst_pct'] for r in rows):.1f} %; "
              f"combinations where Su-Tech used less water in every season: {sum(r['seasons_less'] == r['n'] for r in rows)}/{len(rows)}; "
              f"max Su-Tech stress days: {max(r['sutech_stress_days'] for r in rows):.1f}.", ""]
    (out / "robustness.md").write_text("\n".join(lines), encoding="utf-8")
    return lines


if __name__ == "__main__":
    sim.apply_study_engine()
    print("\n".join(write(run())))
