"""Export the headline results as JSON for the Mini App results page (sutech-frontend/data/results.json).

    python -m research.export_web --out ../sutech-frontend/data/results.json

Every figure on the website is read from this file, which is generated from research/results/*.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "research" / "results"
SCENARIOS = ["perfect", "et0_error_30pct", "rain_never_forecast", "soil_entered_sand",
             "et0_bias_+20pct", "et0_bias_-20pct", "et0_bias_-20pct_3level_check_7d"]


def build() -> dict:
    summ = list(csv.DictReader((R / "simulation_summary.csv").open(encoding="utf-8")))
    combos = []
    for crop in ("cotton", "corn"):
        for method in ("drip", "furrow"):
            sut = next(r for r in summ if (r["crop"], r["method"], r["strategy"]) == (crop, method, "sutech"))
            safe = next(r for r in summ if r["crop"] == crop and r["method"] == method and r["strategy"] == "calendar_best")
            plain = next(r for r in summ if r["crop"] == crop and r["method"] == method
                         and r["strategy"] == ("calendar_5d" if method == "drip" else "calendar_10d"))
            combos.append(dict(
                crop=crop, method=method, n=int(safe["n"]),
                sutech_m3_ha=round(float(sut["water_m3_ha"])), calendar_m3_ha=round(float(safe["water_m3_ha"])),
                saving_pct=round(-float(safe["sutech_vs_this_pct"]), 2),
                ci_low=round(-float(safe["ci95_high"]), 2), ci_high=round(-float(safe["ci95_low"]), 2),
                worst_pct=round(-float(safe["pair_max"]), 2), best_pct=round(-float(safe["pair_min"]), 2),
                seasons_less=int(safe["sutech_less_water_in"]),
                sutech_stress_days=round(float(sut["stress_days"]), 1),
                plain_calendar_stress_days=round(float(plain["stress_days"]), 1)))
    sens = {}
    for method in ("drip", "furrow"):
        rows = list(csv.DictReader((R / f"sensitivity_cotton_{method}.csv").open(encoding="utf-8")))
        sens[method] = [dict(scenario=k, stress_days=round(mean(float(r["stress_days"]) for r in rs), 1),
                             water_vs_calendar_pct=round(mean((float(r["water_m3_ha"]) - float(r["safe_calendar_m3_ha"]))
                                                              / float(r["safe_calendar_m3_ha"]) * 100 for r in rs), 1))
                        for k in SCENARIOS for rs in [[r for r in rows if r["scenario"] == k]]]
    return dict(source="sutech-core research/results (NASA POWER 2021-2025, 5 regions)", model_vs_model=True,
                combos=combos, sensitivity_cotton=sens)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(build(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", a.out)
