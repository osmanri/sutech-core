"""Analyse the pot experiment: model accuracy and water saving, from raw CSV only.

Usage:
    python experiment/analyze.py data/log.csv --pot-area-cm2 177 \
        [--outcomes data/outcomes.csv] [--out experiment/results]

Standard library only. Produces summary.json, report.md and cumulative_water.svg.

See PROTOCOL.md for the mass balance, interval eligibility, and statistical plan.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import NormalDist, correlation, mean, stdev
from typing import Any, Iterator

GROUPS = ("sutech", "control")
MIN_INTERVAL_HOURS = 12.0
MAX_INTERVAL_HOURS = 36.0
CONTROL_MASS_FRACTION = 0.90


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


def _t_two_sided_p(t: float, df: float) -> float:
    return _betainc(df / 2.0, 0.5, df / (df + t * t))


def _t_critical(df: float, two_sided_p: float) -> float:
    lo, hi = 0.0, 1.0
    while _t_two_sided_p(hi, df) > two_sided_p:
        hi *= 2.0
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if _t_two_sided_p(mid, df) > two_sided_p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def welch_t_test(a: list[float], b: list[float]) -> dict[str, Any]:
    """Two-sided Welch t-test. Needs at least two values in each sample."""
    if len(a) < 2 or len(b) < 2:
        raise ValueError("each group needs at least 2 pots for a t-test")
    difference = mean(a) - mean(b)
    va, vb = stdev(a) ** 2 / len(a), stdev(b) ** 2 / len(b)
    variance = va + vb
    if variance == 0:
        return {"difference": difference, "se": None, "t": None, "df": None, "p": None, "difference_ci_95": None}
    se = math.sqrt(variance)
    t = difference / se
    df = 1 / ((va / variance) ** 2 / (len(a) - 1) + (vb / variance) ** 2 / (len(b) - 1))
    radius = _t_critical(df, 0.05) * se
    return {"difference": difference, "se": se, "t": t, "df": df, "p": _t_two_sided_p(t, df),
            "difference_ci_95": [difference - radius, difference + radius]}


def cohens_d(a: list[float], b: list[float]) -> float | None:
    pooled = math.sqrt(((len(a) - 1) * stdev(a) ** 2 + (len(b) - 1) * stdev(b) ** 2)
                       / (len(a) + len(b) - 2))
    return (mean(a) - mean(b)) / pooled if pooled else None


def error_metrics(observed: list[float], predicted: list[float]) -> dict[str, float | None]:
    if not observed or len(observed) != len(predicted):
        raise ValueError("need equal-length, non-empty observed and predicted series")
    err = [p - o for o, p in zip(observed, predicted, strict=True)]
    pearson_r = None
    if len(err) >= 2 and min(observed) != max(observed) and min(predicted) != max(predicted):
        pearson_r = correlation(observed, predicted)
    return {
        "n": len(err),
        "rmse_mm": math.sqrt(mean(e * e for e in err)),
        "mae_mm": mean(abs(e) for e in err),
        "bias_mm": mean(err),  # > 0: the model over-predicts water use
        "pearson_r": pearson_r,
    }


# ------------------------------------------------------------------ data

def _num(value: str | None) -> float | None:
    return float(value) if value and value.strip() else None


def _read_csv(path: Path, required: set[str]) -> Iterator[tuple[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, strict=True)
        try:
            header = reader.fieldnames or []
            if any(not name.strip() for name in header) or len(header) != len(set(header)):
                raise ValueError(f"{path}: CSV headers must be unique and nonempty")
            if missing := required - set(header):
                raise ValueError(f"{path}: missing CSV columns {', '.join(sorted(missing))}")
            for row in reader:
                where = f"{path}:{reader.line_num}"
                if None in row or None in row.values():
                    raise ValueError(f"{where}: incorrect CSV column count")
                yield where, row
        except csv.Error as exc:
            raise ValueError(f"{path}:{reader.line_num}: malformed CSV ({exc})") from exc


def _number(row: dict[str, str], field: str, where: str, *, minimum: float | None = 0,
            required: bool = False) -> float | None:
    try:
        value = _num(row.get(field))
    except ValueError as exc:
        raise ValueError(f"{where}: {field} must be numeric") from exc
    if value is None:
        if required:
            raise ValueError(f"{where}: {field} is required")
    elif not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ValueError(f"{where}: {field} must be finite" + (f" and at least {minimum}" if minimum is not None else ""))
    return value


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: dict[str, str] = {}
    seen: set[tuple[str, datetime, str]] = set()
    required = {"timestamp", "pot_id", "group", "event", "weight_g", "water_ml"}
    for where, row in _read_csv(path, required):
        pot, group, event = (row[k].strip() for k in ("pot_id", "group", "event"))
        if not pot or group not in GROUPS or event not in ("sample", "irrigation", "drainage", "note"):
            raise ValueError(f"{where}: invalid pot_id, group or event")
        if groups.setdefault(pot, group) != group:
            raise ValueError(f"{where}: group assignment changed for pot {pot!r}")
        try:
            timestamp = datetime.fromisoformat(row["timestamp"])
        except ValueError as exc:
            raise ValueError(f"{where}: timestamp must be ISO-8601 with a UTC offset") from exc
        if timestamp.utcoffset() is None:
            raise ValueError(f"{where}: timestamp must include a UTC offset")
        key = (pot, timestamp, event)
        if event != "note" and key in seen:
            raise ValueError(f"{where}: duplicate {event} timestamp for pot {pot!r}")
        seen.add(key)

        water = _number(row, "water_ml", where, required=event == "irrigation")
        drainage = _number(row, "drainage_ml", where)
        weight = _number(row, "weight_g", where)
        post_weight = _number(row, "post_weight_g", where)
        prediction = _number(row, "model_et_mm", where)
        _number(row, "pump_seconds", where)
        _number(row, "temp_c", where, minimum=None)
        for field in ("soil_pct", "hum_pct"):
            pct = _number(row, field, where)
            if pct is not None and pct > 100:
                raise ValueError(f"{where}: {field} must be at most 100")
        if (water is not None or post_weight is not None) and event != "irrigation":
            raise ValueError(f"{where}: water_ml and post_weight_g belong to an irrigation row")
        if drainage is not None and event not in ("irrigation", "drainage"):
            raise ValueError(f"{where}: drainage_ml belongs to an irrigation or drainage row")
        if (weight is not None or prediction is not None) and event != "sample":
            raise ValueError(f"{where}: weight_g and model_et_mm belong to a sample row")
        rows.append(dict(row, pot_id=pot, group=group, event=event, _t=timestamp))

    # Stable ordering preserves the order of distinct events recorded in the same second by old journals.
    return sorted(rows, key=lambda row: row["_t"])


def _unmeasured_dose(row: dict[str, Any]) -> bool:
    return row["event"] == "note" and row.get("note", "").startswith("MISSING_IRRIGATION_VOLUME:")


def daily_evaporation(rows: list[dict[str, Any]], pot_area_cm2: float,
                      max_gap_hours: float = MAX_INTERVAL_HOURS) -> list[dict[str, Any]]:
    """Daily evapotranspiration rates in mm/day from eligible weighing intervals."""
    return _evaporation_intervals(rows, pot_area_cm2, max_gap_hours)[0]


def _evaporation_intervals(rows: list[dict[str, Any]], pot_area_cm2: float,
                           max_gap_hours: float = MAX_INTERVAL_HOURS) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not math.isfinite(pot_area_cm2) or pot_area_cm2 <= 0:
        raise ValueError("pot area must be finite and positive")
    if not math.isfinite(max_gap_hours) or max_gap_hours < MIN_INTERVAL_HOURS:
        raise ValueError(f"maximum gap must be finite and at least {MIN_INTERVAL_HOURS:g} hours")
    by_pot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_pot[r["pot_id"]].append(r)

    days: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    excluded: Counter[str] = Counter()
    sample_dates: dict[str, set[date]] = {}
    missing_weights = unknown_drainage_events = 0
    for pot, items in by_pot.items():
        sample_dates[pot] = set()
        last_w: float | None = None
        last_t: datetime | None = None
        added = drained = 0.0
        drainage_known = irrigation_known = True
        for r in items:
            if _unmeasured_dose(r):
                irrigation_known = False
            if r["event"] in ("irrigation", "drainage"):
                if r["event"] == "irrigation":
                    added += float(r["water_ml"])
                drainage = _num(r.get("drainage_ml"))
                if drainage is None:
                    drainage_known = False
                    unknown_drainage_events += 1
                else:
                    drained += drainage
                continue
            if r["event"] != "sample":
                continue
            stamp = r["_t"]
            sample_dates[pot].add(stamp.date())
            w = _num(r["weight_g"])
            if w is None:
                missing_weights += 1
            if last_t is not None:
                hours = (stamp - last_t).total_seconds() / 3600.0
                reason = None
                if hours < MIN_INTERVAL_HOURS:
                    reason = "short_gap"
                elif hours > max_gap_hours:
                    reason = "long_gap"
                elif (stamp.date() - last_t.date()).days != 1:
                    reason = "nonconsecutive_local_dates"
                elif w is None or last_w is None:
                    reason = "missing_weight"
                elif not irrigation_known:
                    reason = "unknown_irrigation"
                elif not drainage_known:
                    reason = "unknown_drainage"
                if reason:
                    excluded[reason] += 1
                    exclusions.append({"pot_id": pot, "from": last_t.isoformat(), "to": stamp.isoformat(), "reason": reason})
                else:
                    loss_g = last_w + added - drained - w
                    days.append({"pot_id": pot, "group": r["group"], "date": stamp.date().isoformat(),
                                 "loss_g": loss_g, "elapsed_hours": hours,
                                 "observed_mm": loss_g / pot_area_cm2 * 10.0 * 24.0 / hours,
                                 "model_mm": _num(r.get("model_et_mm"))})
            last_w, last_t = w, stamp
            added = drained = 0.0
            drainage_known = irrigation_known = True

    all_dates = set().union(*sample_dates.values())
    span_days = (max(all_dates) - min(all_dates)).days + 1 if all_dates else 0
    paired = sum(d["model_mm"] is not None for d in days)
    predictions = sum(r["event"] == "sample" and _num(r.get("model_et_mm")) is not None for r in rows)
    summary = {"observed": len(days), "paired": paired,
               "missing_prediction": len(days) - paired, "unpaired_predictions": predictions - paired,
               "excluded": dict(excluded), "excluded_intervals": exclusions,
               "missing_scheduled_days": sum(span_days - len(dates) for dates in sample_dates.values()),
               "missing_weight_samples": missing_weights, "unknown_drainage_events": unknown_drainage_events,
               "negative_mass_balances": sum(d["loss_g"] < 0 for d in days)}
    return sorted(days, key=lambda e: (e["pot_id"], e["date"])), summary


def water_per_pot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pots: dict[str, dict[str, Any]] = {}
    for r in rows:
        p = pots.setdefault(r["pot_id"], {"group": r["group"], "water_ml": 0.0, "events": 0, "weighed": False})
        if r["event"] == "irrigation":
            p["water_ml"] += float(r["water_ml"])
            p["events"] += 1
        elif r["event"] == "sample" and _num(r["weight_g"]) is not None:
            p["weighed"] = True
    return pots


def compare_groups(values: dict[str, list[float]], a: str = "sutech", b: str = "control") -> dict[str, Any]:
    va, vb = values.get(a, []), values.get(b, [])
    res: dict[str, Any] = {
        a: {"n": len(va), "mean": mean(va) if va else None, "sd": stdev(va) if len(va) > 1 else None},
        b: {"n": len(vb), "mean": mean(vb) if vb else None, "sd": stdev(vb) if len(vb) > 1 else None},
    }
    if len(va) >= 2 and len(vb) >= 2:
        res["welch"] = welch_t_test(va, vb)
        d = cohens_d(va, vb)
        res["cohens_d"] = d
        res["cohens_d_ci_95"] = None
        if d is not None:
            variance = 1 / len(va) + 1 / len(vb) + d ** 2 / (2 * (len(va) + len(vb) - 2))
            radius = NormalDist().inv_cdf(0.975) * math.sqrt(variance)
            res["cohens_d_ci_95"] = [d - radius, d + radius]
        if mean(vb):
            res["difference_pct"] = (mean(va) - mean(vb)) / mean(vb) * 100.0
    return res


def _mass_noninferiority(masses: dict[str, list[float]]) -> dict[str, Any]:
    sutech, control = (masses.get(group, []) for group in GROUPS)
    result = {"estimand": "mean(sutech) - 0.90 * mean(control)", "maximum_relative_loss": 0.10,
              "confidence_level": 0.95, "estimate_g": None, "lower_bound_g": None, "demonstrated": None}
    if sutech and control:
        result["estimate_g"] = mean(sutech) - CONTROL_MASS_FRACTION * mean(control)
    if min(len(sutech), len(control)) < 2 or mean(control) <= 0:
        return result
    scaled = welch_t_test(sutech, [CONTROL_MASS_FRACTION * mass for mass in control])
    if scaled["df"] is not None:
        lower = scaled["difference"] - _t_critical(scaled["df"], 0.10) * scaled["se"]
        result.update(lower_bound_g=lower, demonstrated=lower > 0)
    return result


# ---------------------------------------------------------------- chart

def cumulative_water_svg(rows: list[dict[str, Any]], path: Path) -> None:
    """Cumulative recorded water, one line per measured pot."""
    t0 = rows[0]["_t"]
    series: dict[str, dict[str, list[tuple[float, float]]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["event"] == "sample" and _num(r["weight_g"]) is not None:
            series[r["group"]][r["pot_id"]]
        if r["event"] != "irrigation":
            continue
        days = (r["_t"] - t0).total_seconds() / 86400.0
        cum = series[r["group"]][r["pot_id"]]
        previous = cum[-1][1] if cum else 0.0
        cum.extend(((days, previous), (days, previous + float(r["water_ml"]))))
    max_day = (rows[-1]["_t"] - t0).total_seconds() / 86400.0 or 1.0
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
            final = pts[-1][1] if pts else 0.0
            line = " ".join(xy(d, v) for d, v in [(0.0, 0.0), *pts, (max_day, final)])
            parts.append(f'<polyline points="{line}" fill="none" stroke="{colors.get(group, "#555")}" '
                         f'stroke-width="1.5" opacity="0.7"/>')
        parts.append(f'<rect x="{left+10}" y="{top+6+ly*18}" width="12" height="12" fill="{colors.get(group, "#555")}"/>'
                     f'<text x="{left+28}" y="{top+16+ly*18}">{group}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------- report

def _fmt(x: Any, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _fmt_ci(interval: list[float] | None) -> str:
    return f"[{interval[0]:.2f}, {interval[1]:.2f}]" if interval is not None else "n/a"


def _load_masses(path: Path, pots: dict[str, dict[str, Any]]) -> dict[str, float]:
    masses: dict[str, float] = {}
    seen: set[str] = set()
    for where, row in _read_csv(path, {"pot_id", "group", "dry_mass_g"}):
        pot, group = row["pot_id"].strip(), row["group"].strip()
        if pot not in pots:
            raise ValueError(f"{where}: unknown pot {pot!r}")
        if pots[pot]["group"] != group:
            raise ValueError(f"{where}: group assignment does not match log for pot {pot!r}")
        if pot in seen:
            raise ValueError(f"{where}: duplicate outcome for pot {pot!r}")
        seen.add(pot)
        mass = _number(row, "dry_mass_g", where)
        if mass is not None:
            masses[pot] = mass
    return masses


def analyse(log_csv: Path, pot_area_cm2: float, outcomes_csv: Path | None, out_dir: Path) -> dict[str, Any]:
    rows = load_rows(log_csv)
    if not rows:
        raise ValueError("the log has no rows")

    days, coverage = _evaporation_intervals(rows, pot_area_cm2)
    paired = [d for d in days if d["model_mm"] is not None]
    summary: dict[str, Any] = {"pot_area_cm2": pot_area_cm2, "days_observed": len(days), "intervals": coverage}
    summary["contains_virtual_records"] = any(r.get("note", "").startswith("VIRTUAL:") for r in rows)
    summary["legacy_log_without_drainage_column"] = "drainage_ml" not in rows[0]
    if paired:
        summary["model_accuracy"] = error_metrics([d["observed_mm"] for d in paired],
                                                  [d["model_mm"] for d in paired])

    pots = water_per_pot(rows)
    by_group: dict[str, list[float]] = defaultdict(list)
    unmeasured = {r["pot_id"] for r in rows if _unmeasured_dose(r)}
    water_totals = {pot: p["water_ml"] for pot, p in pots.items() if p["weighed"] or p["events"]}
    for pot, water in water_totals.items():
        if pot not in unmeasured:
            by_group[pots[pot]["group"]].append(water)
    summary["water_ml_per_pot"] = compare_groups(by_group)
    summary["pots_without_water_observations"] = sorted(pots.keys() - water_totals.keys())
    summary["pots_with_unmeasured_irrigation"] = sorted(unmeasured)

    if outcomes_csv:
        measured_masses = _load_masses(outcomes_csv, pots)
        masses: dict[str, list[float]] = defaultdict(list)
        water_per_mass: dict[str, list[float]] = defaultdict(list)
        mass_per_litre: dict[str, list[float]] = defaultdict(list)
        for pot, mass in measured_masses.items():
            group = pots[pot]["group"]
            masses[group].append(mass)
            water = None if pot in unmeasured else water_totals.get(pot)
            if water is not None and mass > 0:
                water_per_mass[group].append(water / mass)
            if water is not None and water > 0:
                mass_per_litre[group].append(mass / (water / 1000.0))
        summary["pots_missing_dry_mass"] = sorted(pots.keys() - measured_masses.keys())
        summary["dry_mass_g"] = compare_groups(masses)
        summary["mass_noninferiority"] = _mass_noninferiority(masses)
        summary["water_ml_per_dry_mass_g"] = compare_groups(water_per_mass)
        summary["dry_mass_g_per_litre"] = compare_groups(mass_per_litre)

    summary_json = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(summary_json, encoding="utf-8")
    cumulative_water_svg(rows, out_dir / "cumulative_water.svg")

    lines = ["# Experiment results (generated from raw log)", ""]
    if summary["contains_virtual_records"]:
        lines.extend(["**This log contains virtual dry-run records. Its outputs are for software verification only.**", ""])
    lines += [f"Pot surface area is {pot_area_cm2:g} cm².", "", "## Weighing and prediction coverage", "",
             f"- {len(days)} usable weighing intervals, of which {coverage['paired']} had matching predictions.",
             f"- {coverage['missing_prediction']} usable intervals lacked a prediction.",
             f"- {coverage['unpaired_predictions']} recorded predictions lacked a usable interval.",
             f"- {coverage['missing_scheduled_days']} pot-days lacked a sample row within the observed date range.",
             f"- {coverage['missing_weight_samples']} sample rows lacked a measured weight.",
             f"- {coverage['unknown_drainage_events']} irrigation or drainage rows lacked a drainage measurement.",
             f"- {coverage['negative_mass_balances']} negative mass balances were retained."]
    lines.extend(f"- {n} intervals excluded for {reason.replace('_', ' ')}." for reason, n in coverage["excluded"].items())
    if summary["legacy_log_without_drainage_column"]:
        lines += ["", "The legacy CSV has no drainage column. Intervals without recorded irrigation rely on there being no delayed runoff."]
    lines.append("")
    acc = summary.get("model_accuracy")
    lines.extend(["## Model accuracy (Su-Tech vs weighed)", ""])
    if acc:
        lines += [f"- n = {acc['n']} pot intervals", f"- RMSE = {acc['rmse_mm']:.2f} mm/day",
                  f"- MAE = {acc['mae_mm']:.2f} mm/day",
                  f"- Bias = {acc['bias_mm']:+.2f} mm/day (positive values indicate over-prediction)",
                  f"- Pearson r = {_fmt(acc['pearson_r'], 3)}", "",
                  "These estimates describe the paired intervals. Repeated observations from a pot are dependent.", ""]
    else:
        lines.extend(["Accuracy is unavailable because no usable weighing interval had a matching prediction.", ""])
    for key, title in (("water_ml_per_pot", "Water used per pot, ml"),
                       ("dry_mass_g", "Dry mass per pot, g"),
                       ("water_ml_per_dry_mass_g", "Water per gram of dry mass, ml/g"),
                       ("dry_mass_g_per_litre", "Dry mass per litre of water, g/L")):
        c = summary.get(key)
        if not c:
            continue
        lines += [f"## {title}", "", "| group | n | mean | sd |", "|---|---|---|---|"]
        for g in GROUPS:
            lines.append(f"| {g} | {c[g]['n']} | {_fmt(c[g]['mean'])} | {_fmt(c[g]['sd'])} |")
        if "welch" in c:
            w = c["welch"]
            lines += ["", f"Su-Tech minus control = {_fmt(w['difference'])} (Welch 95% CI {_fmt_ci(w['difference_ci_95'])}).",
                      f"Welch t = {_fmt(w['t'])}, df = {_fmt(w['df'], 1)}, two-sided p = {_fmt(w['p'], 4)}.",
                      f"Cohen's d = {_fmt(c['cohens_d'])} (approximate 95% CI {_fmt_ci(c['cohens_d_ci_95'])})."]
            if "difference_pct" in c:
                lines.append(f"The observed relative difference was {c['difference_pct']:+.1f}% of the control mean.")
        else:
            lines.extend(["", "A comparison requires at least two measured pots per group."])
        if key == "water_ml_per_pot":
            lines.extend(["", "Totals cover recorded gross irrigation. A whole-experiment comparison depends on complete irrigation records.",
                          f"{len(unmeasured)} pots had a documented dose of unknown volume. Their totals and water-to-mass ratios were excluded.",
                          f"{len(summary['pots_without_water_observations'])} pots lacked any usable weight or irrigation volume."])
        lines.append("")
    if ni := summary.get("mass_noninferiority"):
        conclusion = {True: "demonstrated", False: "inconclusive", None: "unavailable"}[ni["demonstrated"]]
        lines.extend(["## Dry mass non-inferiority", "",
                      "The margin allows a 10% loss against the population control mean.",
                      f"Su-Tech mean minus 0.90 × control mean = {_fmt(ni['estimate_g'])} g.",
                      f"The one-sided 95% Welch lower bound is {_fmt(ni['lower_bound_g'])} g. Non-inferiority is {conclusion}.",
                      f"Dry mass is missing for {len(summary['pots_missing_dry_mass'])} logged pots.", ""])
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
    try:
        s = analyse(a.log_csv, a.pot_area_cm2, a.outcomes, a.out)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    print(json.dumps(s, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
