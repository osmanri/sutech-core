"""Assemble paper/Su-Tech_paper_draft.md; every number in the results tables is read from research/results/*.csv."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "research" / "results"
summ = list(csv.DictReader((R / "simulation_summary.csv").open(encoding="utf-8")))
N = {"cotton": "cotton", "corn": "maize", "drip": "drip", "furrow": "furrow"}


def row(crop, method, strat):
    return next(r for r in summ if (r["crop"], r["method"], r["strategy"]) == (crop, method, strat))


def f(x, nd=0):
    return f"{float(x):,.{nd}f}".replace(",", " ")


t1 = ["| Crop, method | Su-Tech water, m³/ha | Best equal-yield calendar, m³/ha | Su-Tech saving (95% CI) | Worst–best season | Seasons with less water | Plain calendar (same mean dose): Su-Tech vs calendar | Stress days: Su-Tech / plain calendar | Relative yield: Su-Tech / plain calendar |",
      "|---|---|---|---|---|---|---|---|---|"]
for crop in ("cotton", "corn"):
    for method in ("drip", "furrow"):
        s = row(crop, method, "sutech")
        safe = next(r for r in summ if r["crop"] == crop and r["method"] == method and r["strategy"] == "calendar_best")
        plain = next(r for r in summ if r["crop"] == crop and r["method"] == method and r["strategy"].endswith("_5d" if method == "drip" else "_10d"))
        t1.append(f"| {N[crop]}, {N[method]} | {f(s['water_m3_ha'])} | {f(safe['water_m3_ha'])} | **{abs(float(safe['sutech_vs_this_pct'])):.0f}%** ({abs(float(safe['ci95_high'])):.0f}–{abs(float(safe['ci95_low'])):.0f}%) | {abs(float(safe['pair_max'])):.0f}–{abs(float(safe['pair_min'])):.0f}% | {safe['sutech_less_water_in']}/{safe['n']} | "
                  f"{float(plain['sutech_vs_this_pct']):+.1f}% | {float(s['stress_days']):.0f} / {float(plain['stress_days']):.0f} | {float(s['rel_yield']):.2f} / {float(plain['rel_yield']):.2f} |")

sens = {}
for method in ("drip", "furrow"):
    rows = list(csv.DictReader((R / f"sensitivity_cotton_{method}.csv").open(encoding="utf-8")))
    by = {}
    for r in rows:
        by.setdefault(r["scenario"], []).append(r)
    sens[method] = by
labels = [("perfect", "Perfect forecast"), ("et0_error_10pct", "Random ET₀ error, σ = 10%"), ("et0_error_30pct", "Random ET₀ error, σ = 30%"),
          ("rain_never_forecast", "Rain never forecast"), ("soil_entered_sand", "Wrong soil entered (sand for loam)"),
          ("et0_bias_+20pct", "ET₀ biased +20%"), ("et0_bias_-20pct", "ET₀ biased −20%"),
          ("et0_bias_-20pct_3level_check_7d", "ET₀ biased −20% + 3-level soil check every 7 d"),
          ("et0_bias_-20pct_3level_check_3d", "ET₀ biased −20% + 3-level soil check every 3 d")]
t2 = ["| Scenario | Stress days (drip) | Water vs equal-yield calendar (drip) | Stress days (furrow) | Water vs equal-yield calendar (furrow) |", "|---|---|---|---|---|"]
for key, label in labels:
    cells = []
    for method in ("drip", "furrow"):
        rs = sens[method][key]
        st = sum(float(r["stress_days"]) for r in rs) / len(rs)
        vs = sum((float(r["water_m3_ha"]) - float(r["safe_calendar_m3_ha"])) / float(r["safe_calendar_m3_ha"]) * 100 for r in rs) / len(rs)
        cells += [f"{st:.1f}", f"{vs:+.1f}%"]
    t2.append(f"| {label} | " + " | ".join(cells) + " |")

template = (ROOT / "paper" / "draft_template.md").read_text(encoding="utf-8")
out = template.replace("{{TABLE_SIMULATION}}", "\n".join(t1)).replace("{{TABLE_SENSITIVITY}}", "\n".join(t2))
(ROOT / "paper" / "Su-Tech_paper_draft.md").write_text(out, encoding="utf-8")
print("draft written,", len(out.split()), "words")
