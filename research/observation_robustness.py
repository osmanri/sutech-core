"""Stress-test weekly moisture observations and delayed delivery on the cached study weather."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import mean
from typing import Literal, cast

from bot.water_balance import CALCULATION_VERSION, FieldInput, calculate_balance
from research.simulate import (
    KY,
    LOCATIONS,
    ROOT,
    SAFE_MIN_YIELD,
    WEATHER_DIR,
    YEARS,
    Decide,
    best_safe_calendar,
    calendar_decider,
    engine_variant,
    fetch_power,
    mean_daily_demand,
    root_zone_capacity,
    run_season,
    season_weather,
)

CROPS = ("cotton", "corn")
METHODS = ("drip", "furrow")
SOIL = "loam"
DELAYS = (0, 1, 3, 5)
ET0_FACTORS = (1.0, .8)
MISSING_PATTERNS = ("none", "alternate", "four-week", "all")
CATEGORY_LABELS = {-1: "one wetter", 0: "correct", 1: "one drier"}


@dataclass(frozen=True)
class Scenario:
    category_shift: int = 0
    missing_checks: Literal["none", "alternate", "four-week", "all"] = "none"
    delay_days: int = 0
    et0_factor: float = 1.0


@dataclass(frozen=True)
class Result:
    location: str
    year: int
    crop: str
    method: str
    scenario: Scenario
    water_m3_ha: float
    stress_days: int
    relative_yield: float
    calendar_m3_ha: float
    calendar_yield: float

    @property
    def water_change_pct(self) -> float:
        return (self.water_m3_ha / self.calendar_m3_ha - 1) * 100


def observation_decider(scenario: Scenario) -> Decide:
    """One pending order per field, booked at the advised dose and logged on delivery."""
    depletion = 0.0
    pending: tuple[int, float] | None = None

    def decide(day: int, true_dr: float, et0: float, rain: float, field: FieldInput) -> float:
        nonlocal depletion, pending
        if day and day % 7 == 0:
            missing = scenario.missing_checks
            missed = (
                missing == "all"
                or (missing == "alternate" and day % 14 == 7)
                or (missing == "four-week" and 70 <= day <= 91)
            )
            if not missed:
                _, raw = root_zone_capacity(field.soil, field.zr, field.p)
                levels = (0.0, raw / 2, raw)
                nearest = min(range(len(levels)), key=lambda level: abs(levels[level] - true_dr))
                reported = min(2, max(0, nearest + scenario.category_shift))
                depletion = levels[reported]

        forecast = calculate_balance(replace(field, yesterday=depletion), et0, rain)
        depletion = cast(float, forecast["deficit"])
        if pending is None and forecast["status"] in ("irrigate", "critical"):
            pending = (day + scenario.delay_days, depletion)
        if pending is None or pending[0] != day:
            return 0.0
        _, dose = pending
        pending = None
        depletion = max(0.0, depletion - dose)
        return dose

    return decide


def scenario_parameters():
    for et0_factor in ET0_FACTORS:
        for missing in MISSING_PATTERNS:
            for shift in ((0,) if missing == "all" else CATEGORY_LABELS):
                yield et0_factor, missing, shift


def cached_weather():
    # Guard all cache files up front, so a missing file can't cause an API request or alter the dataset.
    for location in LOCATIONS:
        for year in YEARS:
            path = WEATHER_DIR / f"power_{location}_{year}.json"
            if not path.is_file():
                raise FileNotFoundError(f"Study requires cached NASA POWER input: {path}")
    return {
        (location, year): fetch_power(location, lat, lon, year)
        for location, (lat, lon) in LOCATIONS.items() for year in YEARS
    }


def run_variant(variant: str, weather: dict) -> list[Result]:
    rows = []
    with engine_variant(variant):
        for location in LOCATIONS:
            for crop in CROPS:
                seasons = {year: season_weather(weather[location, year], crop, year) for year in YEARS}
                for method in METHODS:
                    demand = mean_daily_demand(crop, SOIL, method, list(seasons.values()))
                    interval, multiplier = best_safe_calendar(crop, SOIL, method, list(seasons.values()), demand)
                    calendar = calendar_decider(interval, demand * interval * multiplier)
                    for year, observed_weather in seasons.items():
                        baseline = run_season(crop, SOIL, method, observed_weather, calendar)
                        forecasts = {
                            factor: [(et0 * factor, rain) for et0, rain in observed_weather]
                            for factor in ET0_FACTORS
                        }
                        for et0_factor, missing, shift in scenario_parameters():
                            for delay in DELAYS:
                                scenario = Scenario(shift, missing, delay, et0_factor)
                                result = run_season(
                                    crop, SOIL, method, observed_weather, observation_decider(scenario),
                                    forecasts[et0_factor],
                                )
                                rows.append(Result(
                                    location, year, crop, method, scenario, result.gross_mm * 10,
                                    result.stress_days, result.relative_yield(KY[crop]), baseline.gross_mm * 10,
                                    baseline.relative_yield(KY[crop]),
                                ))
    return rows


def failure_counts(rows: list[Result]) -> tuple[int, int]:
    below_target = sum(row.relative_yield < SAFE_MIN_YIELD for row in rows)
    no_saving_at_target = sum(
        row.relative_yield >= SAFE_MIN_YIELD and row.water_m3_ha >= row.calendar_m3_ha for row in rows
    )
    return below_target, no_saving_at_target


def case_label(row: Result) -> str:
    cfg = row.scenario
    observation = CATEGORY_LABELS[cfg.category_shift] if cfg.missing_checks != "all" else "no checks"
    return (
        f"{row.location} {row.year}, {row.crop}, {observation}, "
        f"missing {cfg.missing_checks}, delay {cfg.delay_days} d"
    )


def report(variant: str, results: list[Result]) -> str:
    version = (
        "Published-study configuration (fao56.6-era coefficients, drip wetted fraction 1.0)"
        if variant == "historical"
        else f"Current open-field configuration ({CALCULATION_VERSION}, drip wetted fraction 0.35)"
    )
    lines = [
        f"# Moisture observation and delivery robustness ({variant})", "",
        version + ".", "",
        "Model-vs-model on cached NASA POWER weather, 5 locations × 5 years (2021–2025), cotton and maize, "
        "loam, 1 May planting. See [the scenario protocol](../OBSERVATION_ROBUSTNESS.md).", "",
        "## Failure regions", "",
        "Each cell shows **Y / W** among 50 paired cases for that method and setting. Y counts modeled yield below 98%. "
        "W counts cases reaching 98% where Su-Tech used at least as much water as the strongest fixed calendar. "
        "Counts describe the tested cases. Locations, years, scenarios and repeated checks share weather and trajectories.", "",
    ]
    grouped = defaultdict(list)
    for row in results:
        grouped[row.method, row.scenario].append(row)
    for et0_factor in ET0_FACTORS:
        et0_bias = round((et0_factor - 1) * 100)
        lines.extend([
            f"### ET₀ bias {et0_bias:+d}%", "",
            "| Missing checks | Reported category | "
            + " | ".join(f"{method}, {delay} d" for method in METHODS for delay in DELAYS) + " |",
            "|---|---|" + "---:|" * (len(METHODS) * len(DELAYS)),
        ])
        for factor, missing, shift in scenario_parameters():
            if factor != et0_factor:
                continue
            cells = []
            for method in METHODS:
                for delay in DELAYS:
                    y, w = failure_counts(grouped[method, Scenario(shift, missing, delay, factor)])
                    cells.append(f"{y} / {w}")
            category = CATEGORY_LABELS[shift] if missing != "all" else "—"
            lines.append(f"| {missing} | {category} | " + " | ".join(cells) + " |")
        lines.append("")

    lines.extend([
        "## Reference cases with immediate delivery", "",
        "| ET₀ bias | Method | Checks | Mean water difference vs calendar | Minimum modeled yield | Max stress days |",
        "|---|---|---|---:|---:|---:|",
    ])
    for factor in ET0_FACTORS:
        for method in METHODS:
            for missing, label in (("all", "none"), ("none", "weekly, correct category")):
                rows = grouped[method, Scenario(missing_checks=missing, et0_factor=factor)]
                lines.append(
                    f"| {round((factor - 1) * 100):+d}% | {method} | {label} | "
                    f"{mean(r.water_change_pct for r in rows):+.1f}% | "
                    f"{min(r.relative_yield for r in rows):.2%} | {max(r.stress_days for r in rows)} |"
                )

    lines.extend([
        "", "## Worst tested cases", "",
        "Water differences are paired with each case's calendar. The largest water difference uses "
        "cases reaching the 98% yield threshold. Ties show the first case in run order.", "",
        "| ET₀ bias | Method | Lowest modeled yield (case) | Most stress days (case) | "
        "Largest water difference at target yield (case) |",
        "|---|---|---|---|---|",
    ])
    for factor in ET0_FACTORS:
        for method in METHODS:
            rows = [r for r in results if r.method == method and r.scenario.et0_factor == factor]
            worst_yield = min(rows, key=lambda r: r.relative_yield)
            worst_stress = max(rows, key=lambda r: r.stress_days)
            at_target = [r for r in rows if r.relative_yield >= SAFE_MIN_YIELD]
            worst_water = max(at_target, key=lambda r: r.water_change_pct)
            lines.append(
                f"| {round((factor - 1) * 100):+d}% | {method} | "
                f"{worst_yield.relative_yield:.2%} ({case_label(worst_yield)}) | "
                f"{worst_stress.stress_days} ({case_label(worst_stress)}) | "
                f"{worst_water.water_change_pct:+.1f}% ({case_label(worst_water)}) |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "research" / "results")
    parser.add_argument("--csv", action="store_true", help="also write per-season rows")
    args = parser.parse_args()
    weather = cached_weather()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for variant in ("historical", "current"):
        rows = run_variant(variant, weather)
        stem = args.out_dir / f"observation_robustness_{variant}"
        stem.with_suffix(".md").write_text(report(variant, rows), encoding="utf-8", newline="\n")
        if args.csv:
            with stem.with_suffix(".csv").open("w", encoding="utf-8", newline="") as file:
                records = [asdict(row) for row in rows]
                scenarios = [record.pop("scenario") for record in records]
                columns = [*records[0], *scenarios[0]]
                writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(record | scenario for record, scenario in zip(records, scenarios, strict=True))
        print(f"{variant}: {len(rows)} simulated cases, {stem.with_suffix('.md')}")


if __name__ == "__main__":
    main()
