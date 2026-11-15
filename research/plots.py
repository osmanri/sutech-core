"""Draw the two headline figures as dependency-free SVG from the result CSVs.

    python -m research.plots      ->  docs/img/water_by_strategy.svg, docs/img/sensitivity_stress.svg

Every bar is read from research/results/*.csv, nothing is typed in by hand.
"""

from __future__ import annotations

import csv
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
GREEN, AMBER, GREY, INK = "#1a7a4a", "#d97706", "#6b7280", "#1c2b1e"
NAMES = {"cotton": "Хлопок", "corn": "Кукуруза", "drip": "капля", "furrow": "арык"}


def _svg(w: int, h: int, body: list[str], title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{escape(title)}" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
            f'<title>{escape(title)}</title><rect width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="#d1e0d4"/>'
            + "".join(body) + "</svg>")


def _text(x: float, y: float, s: str, size: int = 13, anchor: str = "start", weight: str = "400", fill: str = INK) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{escape(s)}</text>'


def water_by_strategy(summary_csv: Path, out: Path) -> None:
    rows = list(csv.DictReader(summary_csv.open(encoding="utf-8")))
    groups = []
    for crop in ("cotton", "corn"):
        for method in ("drip", "furrow"):
            sut = next(r for r in rows if (r["crop"], r["method"], r["strategy"]) == (crop, method, "sutech"))
            safe = next(r for r in rows if r["crop"] == crop and r["method"] == method and r["strategy"].endswith("_safe"))
            groups.append((f"{NAMES[crop]}, {NAMES[method]}", float(sut["water_m3_ha"]), float(safe["water_m3_ha"]),
                           float(safe["sutech_vs_this_pct"])))
    w, h, left, right, top = 760, 400, 150, 40, 70
    vmax = max(g[2] for g in groups) * 1.08
    scale = (w - left - right) / vmax
    body = [_text(24, 32, "Вода за сезон при одинаковом урожае, м³/га", 17, weight="700"),
            _text(24, 52, "Su-Tech против поливательного графика, настроенного на тот же урожай (5 регионов × 5 сезонов)", 12, fill=GREY)]
    for i, (label, sut, safe, pct) in enumerate(groups):
        y = top + 20 + i * 62
        body += [_text(left - 12, y + 22, label, 13, "end", "600"),
                 f'<rect x="{left}" y="{y}" width="{sut * scale:.1f}" height="22" rx="4" fill="{GREEN}"/>',
                 _text(left + sut * scale + 8, y + 16, f"{sut:,.0f}".replace(",", " "), 12),
                 f'<rect x="{left}" y="{y + 26}" width="{safe * scale:.1f}" height="22" rx="4" fill="{AMBER}"/>',
                 _text(left + safe * scale + 8, y + 42, f"{safe:,.0f}".replace(",", " "), 12),
                 _text(w - right, y + 16, f"Su-Tech на {abs(pct):.0f}% меньше", 12, "end", "700", GREEN)]
    body += [f'<rect x="{left}" y="{h - 62}" width="14" height="14" rx="3" fill="{GREEN}"/>', _text(left + 20, h - 50, "Su-Tech", 12),
             f'<rect x="{left + 90}" y="{h - 62}" width="14" height="14" rx="3" fill="{AMBER}"/>',
             _text(left + 110, h - 50, "график с запасом, при котором урожай ≥ 98% в каждом сезоне", 12),
             _text(w - 16, h - 14, "модель на реальной погоде, не полевое измерение", 11, "end", fill=GREY)]
    out.write_text(_svg(w, h, body, "Расход воды за сезон: Su-Tech и график при одинаковом урожае"), encoding="utf-8")


def sensitivity(csv_path: Path, out: Path) -> None:
    by: dict[str, list[dict[str, str]]] = {}
    for r in csv.DictReader(csv_path.open(encoding="utf-8")):
        by.setdefault(r["scenario"], []).append(r)
    pick = [("perfect", "Идеальный прогноз"), ("et0_error_30pct", "Случайная ошибка ET₀ ±30%"),
            ("rain_never_forecast", "Дожди не учтены"), ("soil_entered_sand", "Неверная почва"),
            ("et0_bias_-20pct", "ET₀ занижена на 20%"),
            ("et0_bias_-20pct_3level_check_7d", "…и проверка влажности раз в 7 дней")]
    vals = [(label, sum(float(r["stress_days"]) for r in by[k]) / len(by[k])) for k, label in pick]
    w, h, left, right, top = 760, 330, 270, 60, 70
    vmax = max(v for _, v in vals) * 1.1
    body = [_text(24, 32, "Дни стресса растений за сезон (хлопок, капля)", 17, weight="700"),
            _text(24, 52, "Случайные ошибки почти безвредны; систематическая ошибка копится — и исправляется проверкой почвы", 12, fill=GREY)]
    for i, (label, v) in enumerate(vals):
        y = top + 12 + i * 36
        bad = v > 1
        body += [_text(left - 12, y + 17, label, 13, "end", "600" if bad else "400"),
                 f'<rect x="{left}" y="{y}" width="{max(v, 0.0) / vmax * (w - left - right):.1f}" height="24" rx="4" fill="{AMBER if bad else GREEN}"/>',
                 _text(left + v / vmax * (w - left - right) + 8, y + 17, f"{v:.1f}", 13, weight="700")]
    body.append(_text(w - 16, h - 14, "модель на реальной погоде, 5 регионов × 5 сезонов", 11, "end", fill=GREY))
    out.write_text(_svg(w, h, body, "Дни стресса растений при ошибках входных данных"), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = ROOT / "research" / "results"
    water_by_strategy(res / "simulation_summary.csv", OUT / "water_by_strategy.svg")
    sensitivity(res / "sensitivity_cotton_drip.csv", OUT / "sensitivity_stress.svg")
    print("wrote", *(p.name for p in sorted(OUT.glob("*.svg"))))


if __name__ == "__main__":
    main()
