"""Analyse the pot experiment: model accuracy and water saving, from raw CSV only.

Usage:
    python experiment/analyze.py data/log.csv --pot-area-cm2 177 \
        [--outcomes data/outcomes.csv] [--out experiment/results]

Standard library only. Produces summary.json, report.md and cumulative_water.svg.

Method (kept deliberately simple so it can be defended at an interview):
  * Evaporation of a pot between two consecutive weighings is
        loss_g = previous_weight + water_added_ml - current_weight
    (1 ml of water = 1 g). Dividing by the pot area gives millimetres of water.
  * Model accuracy = RMSE / MAE / bias of Su-Tech's predicted daily mm against
    that weighed mm.
  * Water saving = difference of total water per pot between groups, tested with
    Welch's t-test (does not assume equal variances; fine for n = 5-6 per group).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any


# ---------------------------------------------------------------- statistics

def _betacf(a: float, b: float, x: float) -> float:
    tiny, qab, qap, qam = 1e-30, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log(1.0 - x))
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def welch_t_test(a: list[float], b: list[float]) -> dict[str, float]:
    """Two-sided Welch t-test. Needs at least two values in each sample."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError("each group needs at least 2 pots for a t-test")
    ma, mb = mean(a), mean(b)
    va, vb = stdev(a) ** 2 / len(a), stdev(b) ** 2 / len(b)
    if va + vb == 0:
        return {"t": 0.0 if ma == mb else math.inf, "df": float(len(a) + len(b) - 2),
                "p": 1.0 if ma == mb else 0.0}
    t = (ma - mb) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    p = _betainc(df / 2.0, 0.5, df / (df + t * t))
    return {"t": t, "df": df, "p": p}


def cohens_d(a: list[float], b: list[float]) -> float:
    pooled = math.sqrt(((len(a) - 1) * stdev(a) ** 2 + (len(b) - 1) * stdev(b) ** 2)
                       / (len(a) + len(b) - 2))
    return (mean(a) - mean(b)) / pooled if pooled else 0.0


def error_metrics(observed: list[float], predicted: list[float]) -> dict[str, float]:
    if not observed or len(observed) != len(predicted):
        raise ValueError("need equal-length, non-empty observed and predicted series")
    err = [p - o for o, p in zip(observed, predicted, strict=True)]
    return {
        "n": len(err),
        "rmse_mm": math.sqrt(mean(e * e for e in err)),
        "mae_mm": mean(abs(e) for e in err),
        "bias_mm": mean(err),  # > 0: the model over-predicts water use
    }


# ------------------------------------------------------------------ data

def _num(value: str) -> float | None:
    try:
        return float(value) if value.strip() != "" else None
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["_t"] = datetime.fromisoformat(r["timestamp"])
    rows.sort(key=lambda r: r["_t"])
    return rows


def daily_evaporation(rows: list[dict[str, Any]], pot_area_cm2: float,
                      max_gap_hours: float = 36.0) -> list[dict[str, Any]]:
    """Weighed evaporation (mm) per pot and day. Intervals longer than
    max_gap_hours are skipped rather than interpolated (a missed weighing is
    reported, not guessed)."""
    by_pot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_pot[r["pot_id"]].append(r)

    per_day: dict[tuple[str, str], dict[str, Any]] = {}
    for pot, items in by_pot.items():
        last_w: float | None = None
        last_t: datetime | None = None
        added = 0.0
        for r in items:
            if r["event"] == "irrigation":
                added += _num(r["water_ml"]) or 0.0
                continue
            w = _num(r["weight_g"])
            if r["event"] != "sample" or w is None:
                continue
            if last_w is not None and last_t is not None:
                hours = (r["_t"] - last_t).total_seconds() / 3600.0
                if 0 < hours <= max_gap_hours:
                    loss_g = last_w + added - w
                    day = r["_t"].date().isoformat()
                    entry = per_day.setdefault((pot, day), {
                        "pot_id": pot, "group": r["group"], "date": day,
                        "loss_g": 0.0, "model_mm": []})
                    entry["loss_g"] += loss_g
                    m = _num(r["model_et_mm"])
                    if m is not None:
                        entry["model_mm"].append(m)
            last_w, last_t, added = w, r["_t"], 0.0
    out = []
    for e in per_day.values():
        e["observed_mm"] = e["loss_g"] / pot_area_cm2 * 10.0
        e["model_mm"] = mean(e["model_mm"]) if e["model_mm"] else None
        out.append(e)
    return sorted(out, key=lambda e: (e["pot_id"], e["date"]))


def water_per_pot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pots: dict[str, dict[str, Any]] = {}
    for r in rows:
        p = pots.setdefault(r["pot_id"], {"group": r["group"], "water_ml": 0.0, "events": 0})
        if r["event"] == "irrigation":
            p["water_ml"] += _num(r["water_ml"]) or 0.0
            p["events"] += 1
    return pots


def compare_groups(values: dict[str, list[float]], a: str = "sutech", b: str = "control") -> dict[str, Any]:
    va, vb = values.get(a, []), values.get(b, [])
    res: dict[str, Any] = {
        a: {"n": len(va), "mean": mean(va) if va else None, "sd": stdev(va) if len(va) > 1 else None},
        b: {"n": len(vb), "mean": mean(vb) if vb else None, "sd": stdev(vb) if len(vb) > 1 else None},
    }
    if len(va) >= 2 and len(vb) >= 2:
        res["welch"] = welch_t_test(va, vb)
        res["cohens_d"] = cohens_d(va, vb)
        if mean(vb):
            res["difference_pct"] = (mean(va) - mean(vb)) / mean(vb) * 100.0
    return res


# ---------------------------------------------------------------- chart

def cumulative_water_svg(rows: list[dict[str, Any]], path: Path) -> None:
    """Mean cumulative water per pot, by group (plain SVG, no dependencies)."""
    t0 = rows[0]["_t"]
    series: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["event"] != "irrigation":
            continue
        days = (r["_t"] - t0).total_seconds() / 86400.0
        cum = series[r["group"]][r["pot_id"]]
        cum.append((days, (cum[-1][1] if cum else 0.0) + (_num(r["water_ml"]) or 0.0)))
    max_day = max((d for g in series.values() for pts in g.values() for d, _ in pts), default=1.0) or 1.0
    max_ml = max((v for g in series.values() for pts in g.values() for _, v in pts), default=1.0) or 1.0
    w, h, left, bottom, top = 640, 380, 70, 50, 20
    colors = {"sutech": "#1a7a4a", "control": "#d97706"}

    def xy(d: float, v: float) -> str:
        return f"{left + d / max_day * (w - left - 20):.1f},{h - bottom - v / max_ml * (h - bottom - top):.1f}"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif" font-size="12">',
             f'<rect width="{w}" height="{h}" fill="#fff"/>',
             f'<line x1="{left}" y1="{h-bottom}" x2="{w-20}" y2="{h-bottom}" stroke="#333"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{h-bottom}" stroke="#333"/>',
             f'<text x="{w/2}" y="{h-10}" text-anchor="middle">Days from start</text>',
             f'<text x="16" y="{h/2}" transform="rotate(-90 16 {h/2})" text-anchor="middle">Cumulative water per pot, ml</text>',
             f'<text x="{left-6}" y="{h-bottom+4}" text-anchor="end">0</text>',
             f'<text x="{left-6}" y="{top+4}" text-anchor="end">{max_ml:.0f}</text>',
             f'<text x="{w-20}" y="{h-bottom+16}" text-anchor="end">{max_day:.0f}</text>']
    for ly, (group, pots) in enumerate(sorted(series.items())):
        for pts in pots.values():
            line = " ".join(xy(d, v) for d, v in [(0.0, 0.0)] + pts)
            parts.append(f'<polyline points="{line}" fill="none" stroke="{colors.get(group, "#555")}" '
                         f'stroke-width="1.5" opacity="0.7"/>')
        parts.append(f'<rect x="{left+10}" y="{top+6+ly*18}" width="12" height="12" fill="{colors.get(group, "#555")}"/>'
                     f'<text x="{left+28}" y="{top+16+ly*18}">{group}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------- report

def _fmt(x: Any, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def analyse(log_csv: Path, pot_area_cm2: float, outcomes_csv: Path | None, out_dir: Path) -> dict[str, Any]:
    rows = load_rows(log_csv)
    if not rows:
        raise SystemExit("the log has no rows")
    out_dir.mkdir(parents=True, exist_ok=True)

    days = daily_evaporation(rows, pot_area_cm2)
    paired = [d for d in days if d["model_mm"] is not None]
    summary: dict[str, Any] = {"pot_area_cm2": pot_area_cm2, "days_observed": len(days)}
    if paired:
        summary["model_accuracy"] = error_metrics([d["observed_mm"] for d in paired],
                                                  [d["model_mm"] for d in paired])

    pots = water_per_pot(rows)
    by_group: dict[str, list[float]] = defaultdict(list)
    for p in pots.values():
        by_group[p["group"]].append(p["water_ml"])
    summary["water_ml_per_pot"] = compare_groups(by_group)

    if outcomes_csv:
        with outcomes_csv.open(newline="", encoding="utf-8") as fh:
            masses: dict[str, list[float]] = defaultdict(list)
            wue: dict[str, list[float]] = defaultdict(list)
            for r in csv.DictReader(fh):
                m = _num(r["dry_mass_g"])
                if m is None or r["pot_id"] not in pots:
                    continue
                masses[r["group"]].append(m)
                if pots[r["pot_id"]]["water_ml"] > 0:
                    wue[r["group"]].append(m / (pots[r["pot_id"]]["water_ml"] / 1000.0))
        summary["dry_mass_g"] = compare_groups(masses)
        summary["dry_mass_g_per_litre"] = compare_groups(wue)

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    cumulative_water_svg(rows, out_dir / "cumulative_water.svg")

    lines = ["# Experiment results (generated from raw log)", "",
             f"Pot area: {pot_area_cm2} cm². Days with weighed evaporation: {len(days)}.", ""]
    acc = summary.get("model_accuracy")
    if acc:
        lines += ["## Model accuracy (Su-Tech vs weighed)", "",
                  f"- n = {acc['n']} pot-days", f"- RMSE = {acc['rmse_mm']:.2f} mm/day",
                  f"- MAE = {acc['mae_mm']:.2f} mm/day",
                  f"- Bias = {acc['bias_mm']:+.2f} mm/day (positive: model over-predicts)", ""]
    for key, title in (("water_ml_per_pot", "Water used per pot, ml"),
                       ("dry_mass_g", "Dry mass per pot, g"),
                       ("dry_mass_g_per_litre", "Dry mass per litre of water, g/L")):
        c = summary.get(key)
        if not c:
            continue
        lines += [f"## {title}", "", "| group | n | mean | sd |", "|---|---|---|---|"]
        for g in ("sutech", "control"):
            lines.append(f"| {g} | {c[g]['n']} | {_fmt(c[g]['mean'])} | {_fmt(c[g]['sd'])} |")
        if "welch" in c:
            w = c["welch"]
            lines += ["", f"Welch t = {w['t']:.2f}, df = {w['df']:.1f}, p = {w['p']:.4f}, "
                          f"Cohen's d = {c['cohens_d']:.2f}, difference = {_fmt(c.get('difference_pct'), 1)}%."]
        lines.append("")
    lines += ["![cumulative water](cumulative_water.svg)", ""]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log_csv", type=Path)
    ap.add_argument("--pot-area-cm2", type=float, required=True, help="soil surface area of one pot")
    ap.add_argument("--outcomes", type=Path, help="CSV: pot_id,group,dry_mass_g")
    ap.add_argument("--out", type=Path, default=Path("experiment/results"))
    a = ap.parse_args()
    s = analyse(a.log_csv, a.pot_area_cm2, a.outcomes, a.out)
    print(json.dumps(s, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
