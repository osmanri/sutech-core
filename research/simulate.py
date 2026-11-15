"""Retrospective season simulation: Su-Tech decisions vs a fixed irrigation calendar.

Both strategies irrigate the same field with the SAME method (same efficiency), so any
difference comes from timing and dose, not from better hardware. Weather is real
(default: NASA POWER daily data, ET0 computed here with FAO-56 Penman-Monteith;
alternative: Open-Meteo archive ET0) and cached in
research/data/weather so every number can be reproduced offline.

Model ("truth") — FAO-56 chapter 8 root-zone balance, daily:
    Dr_i = clamp(Dr_{i-1} + Ks*Kc*ET0 - Peff - I_net, 0, TAW)
  * water pushed below Dr = 0 is deep percolation (lost);
  * Ks (eq. 84) uses the start-of-day depletion;
  * Peff follows the project rule (0 below 5 mm, else 0.75 x rain) — same rule as the bot.
Su-Tech: every day the production engine (bot/water_balance.py) decides with its own
tracked deficit; when it says "irrigate" the computed deficit is applied.
Calendar: a fixed net dose every N days, sized from the long-term mean crop demand of
the same location (a well-informed farmer, not a straw man).
Yield proxy: FAO-33 seasonal relation 1 - Ya/Ym = Ky (1 - ETa/ETm).

LIMITATIONS (must be stated with any result): model-vs-model on reanalysis weather,
city-centre coordinates not farms, one soil, perfect weather knowledge for Su-Tech unless
sensitivity.py adds forecast error, no salinity, no capillary rise, fixed planting date.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, stdev
from collections.abc import Callable
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.et0 import et0_penman_monteith  # noqa: E402
from bot.water_balance import (CROPS, METHODS, calculate_balance, parse_field,  # noqa: E402
                               root_zone_capacity, stress_coefficient)

WEATHER_DIR = ROOT / "research" / "data" / "weather"
LOCATIONS = {  # irrigated-agriculture regions of Kazakhstan (city coordinates)
    "Turkestan": (43.30, 68.25), "Shymkent": (42.32, 69.60), "Kyzylorda": (44.85, 65.50),
    "Taraz": (42.90, 71.37), "Taldykorgan": (45.02, 78.37),
}
YEARS = (2021, 2022, 2023, 2024, 2025)
PLANTING = {"cotton": (5, 1), "corn": (5, 1)}
KY = {"cotton": 0.85, "corn": 1.25}  # FAO-33 seasonal yield response factors
CALENDAR_DAYS = {"drip": (3, 5, 7), "furrow": (7, 10, 14)}
SAFE_INTERVAL = {"drip": 5, "furrow": 10}
SAFE_MIN_YIELD = 0.98  # "safe" calendar: every season of the location keeps >= 98 % relative yield
PUMP_KW, PUMP_M3H = 22.0, 60.0  # project reference pump, for kWh only


# ---------------------------------------------------------------- weather

def fetch_weather(name: str, lat: float, lon: float, year: int, cache: Path = WEATHER_DIR) -> dict[str, tuple[float, float]]:
    """{iso_day: (et0_mm, rain_mm)} for a whole year, cached as JSON."""
    path = cache / f"{name}_{year}.json"
    if not path.exists():
        q = urllib.parse.urlencode(dict(latitude=lat, longitude=lon, start_date=f"{year}-01-01",
                                        end_date=f"{year}-12-31", timezone="auto",
                                        daily="et0_fao_evapotranspiration,precipitation_sum"))
        raw = None
        for attempt in range(6):  # the free API rate-limits bursts (HTTP 429): back off and retry
            try:
                with urllib.request.urlopen(f"https://archive-api.open-meteo.com/v1/archive?{q}", timeout=60) as r:
                    raw = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 5:
                    raise
                time.sleep(15 * (attempt + 1))
        time.sleep(1.0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
    d = json.loads(path.read_text(encoding="utf-8"))["daily"]
    out = {}
    for day, et0, rain in zip(d["time"], d["et0_fao_evapotranspiration"], d["precipitation_sum"], strict=True):
        if et0 is None or rain is None:
            raise ValueError(f"missing weather on {day} in {path.name}")
        out[day] = (float(et0), float(rain))
    return out


POWER_PARAMS = "T2M_MAX,T2M_MIN,T2MDEW,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"


def fetch_power(name: str, lat: float, lon: float, year: int, cache: Path = WEATHER_DIR) -> dict[str, tuple[float, float]]:
    """NASA POWER daily point data; ET0 computed with the project's FAO-56 Penman-Monteith
    (bot/et0.py: measured Rs, dew-point humidity, 2 m wind). {iso_day: (et0_mm, rain_mm)}."""
    path = cache / f"power_{name}_{year}.json"
    if not path.exists():
        q = urllib.parse.urlencode(dict(parameters=POWER_PARAMS, community="AG", latitude=lat, longitude=lon,
                                        start=f"{year}0101", end=f"{year}1231", format="JSON"))
        with urllib.request.urlopen(f"https://power.larc.nasa.gov/api/temporal/daily/point?{q}", timeout=120) as r:
            raw = json.load(r)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
        time.sleep(1.0)
    raw = json.loads(path.read_text(encoding="utf-8"))
    p, elevation = raw["properties"]["parameter"], raw["geometry"]["coordinates"][2]
    out = {}
    for key in p["T2M_MAX"]:
        v = {name_: p[name_][key] for name_ in POWER_PARAMS.split(",")}
        if any(x is None or x <= -998 for x in v.values()):
            raise ValueError(f"missing NASA POWER value on {key} for {name}")
        day = date(int(key[:4]), int(key[4:6]), int(key[6:]))
        et0 = et0_penman_monteith(t_max=v["T2M_MAX"], t_min=v["T2M_MIN"], t_dew=min(v["T2MDEW"], v["T2M_MIN"]),
                                  u2=v["WS2M"], rs=v["ALLSKY_SFC_SW_DWN"], elevation_m=elevation,
                                  lat_deg=lat, day_of_year=day.timetuple().tm_yday)
        out[day.isoformat()] = (et0, float(v["PRECTOTCORR"]))
    return out


SOURCES = {"power": fetch_power, "open-meteo": fetch_weather}


# ---------------------------------------------------------------- model

@dataclass
class Season:
    gross_mm: float = 0.0
    net_mm: float = 0.0
    events: int = 0
    eta: float = 0.0          # actual crop ET
    etm: float = 0.0          # potential crop ET (no stress)
    peff: float = 0.0
    deep_perc: float = 0.0
    stress_days: int = 0
    days: int = 0
    dr_start: float = 0.0
    dr_end: float = 0.0
    eff: float = 1.0

    def relative_yield(self, ky: float) -> float:
        return max(0.0, 1.0 - ky * (1.0 - (self.eta / self.etm if self.etm else 1.0)))

    def closure_error(self) -> float:
        """Water balance must close: inputs - outputs = change of storage (= -change of depletion)."""
        return (self.net_mm + self.peff - self.eta - self.deep_perc) - (self.dr_start - self.dr_end)


def payload(crop: str, soil: str, method: str, day: int) -> dict:
    return dict(balance_version=2, crop=crop, soil_type=soil, irrigation_type=method, area=1,
                area_unit="hectare", day_of_growth=day, moisture_condition="recent")


Decide = Callable[[int, float, float, float, object], float]  # -> net mm to apply today


def run_season(crop: str, soil: str, method: str, weather: list[tuple[float, float]],
               decide: Decide, forecast: list[tuple[float, float]] | None = None) -> Season:
    """Simulate one season. `weather` is the truth; `forecast` is what the app believes."""
    eff = METHODS[method][1]
    forecast = forecast or weather
    s = Season(eff=eff)
    dr = 0.0  # pre-plant irrigation fills the root zone
    s.dr_start = dr
    for day, ((et0, rain), (f_et0, f_rain)) in enumerate(zip(weather, forecast, strict=True)):
        field = parse_field(payload(crop, soil, method, day))
        taw, raw = root_zone_capacity(soil, field.zr, field.p)
        dr = min(dr, taw)  # roots grew: depletion is relative to the new, deeper zone
        if day == 0:
            s.dr_start = dr
        net = max(0.0, decide(day, dr, f_et0, f_rain, field))
        ks = stress_coefficient(dr, taw, raw, field.p)
        etm = et0 * field.kc
        eta = etm * ks
        peff = 0.0 if rain < 5 else rain * 0.75
        unbounded = dr + eta - peff - net
        perc = max(0.0, -unbounded)
        dr = min(taw, max(0.0, unbounded))
        s.days += 1
        s.stress_days += dr > raw + 1e-9
        s.eta += eta; s.etm += etm; s.peff += peff; s.deep_perc += perc
        if net > 0:
            s.net_mm += net; s.gross_mm += net / eff; s.events += 1
    s.dr_end = dr
    return s


def sutech_decider(crop: str, soil: str, method: str, app_soil: str | None = None,
                   check_every: int | None = None, sensor_sd_mm: float = 0.0,
                   rng=None, categorical: bool = False) -> tuple[Decide, Callable[[], None]]:
    """The production engine with its OWN deficit estimate (it never sees the truth).

    app_soil: the soil the farmer entered in the app, which may differ from the real one.
    check_every: every N days a soil-moisture reading replaces the app's estimate with the
    true depletion plus sensor noise N(0, sensor_sd_mm) (closed-loop correction).
    categorical: the check is the farmer's three-way judgement the bot offers (wet / normal / dry),
    i.e. depletion snapped to the nearest of 0, RAW/2, RAW — the same levels as the setup form.
    """
    state = {"d": 0.0}

    def decide(day, true_dr, f_et0, f_rain, field):
        if check_every and day > 0 and day % check_every == 0:
            noise = rng.gauss(0.0, sensor_sd_mm) if (rng and sensor_sd_mm) else 0.0
            reading = max(0.0, true_dr + noise)
            if categorical:
                raw = root_zone_capacity(soil, field.zr, field.p)[1]
                reading = min((0.0, raw / 2, raw), key=lambda level: abs(level - reading))
            state["d"] = reading
        if app_soil and app_soil != soil:
            field = parse_field(payload(crop, app_soil, method, day))
        r = calculate_balance(replace(field, yesterday=state["d"]), f_et0, f_rain)
        deficit = cast(float, r["deficit"])  # calculate_balance returns a mixed-type dict
        state["d"] = deficit
        if r["status"] in ("irrigate", "critical"):
            applied = deficit
            state["d"] = 0.0
            # r["deficit"] already contains today's forecast ETc and rain; with a perfect forecast
            # this refills the root zone exactly, with a wrong one the truth model shows the miss.
            return applied
        return 0.0

    def reset():
        state["d"] = 0.0
    return decide, reset


def calendar_decider(interval: int, dose_mm: float) -> Decide:
    return lambda day, dr, et0, rain, field: dose_mm if day > 0 and day % interval == 0 else 0.0


def season_weather(all_days: dict, crop: str, year: int) -> list[tuple[float, float]]:
    m, d = PLANTING[crop]
    start, length = date(year, m, d), sum(CROPS[crop][4])
    return [all_days[(start + timedelta(days=i)).isoformat()] for i in range(length)]


def mean_daily_demand(crop: str, soil: str, method: str, seasons: list[list[tuple[float, float]]]) -> float:
    """Long-term mean net irrigation need per day = mean(Kc*ET0 - Peff) over all seasons."""
    total, n = 0.0, 0
    for w in seasons:
        for day, (et0, rain) in enumerate(w):
            kc = parse_field(payload(crop, soil, method, day)).kc
            total += kc * et0 - (0.0 if rain < 5 else rain * 0.75)
            n += 1
    return max(0.0, total / n)


def safe_multiplier(crop, soil, method, seasons, interval, demand, step=0.05, limit=4.0) -> float:
    """Smallest fixed-dose multiplier that keeps EVERY season at >= SAFE_MIN_YIELD.

    A farmer cannot retune per year, so one dose is chosen per location with hindsight of all
    seasons; this gives the calendar its best possible equal-yield setting.
    """
    m = 1.0
    while m <= limit + 1e-9:
        ys = [run_season(crop, soil, method, w, calendar_decider(interval, demand * interval * m)).relative_yield(KY[crop])
              for w in seasons]
        if min(ys) >= SAFE_MIN_YIELD:
            return m
        m = round(m + step, 10)
    raise RuntimeError("no safe calendar dose found within the search limit")


# ---------------------------------------------------------------- experiment

def simulate(locations=LOCATIONS, years=YEARS, crops=("cotton", "corn"), methods=("drip", "furrow"),
             soil="loam", fetch=fetch_power) -> list[dict]:
    rows = []
    for loc, (lat, lon) in locations.items():
        weather = {y: fetch(loc, lat, lon, y) for y in years}
        for crop in crops:
            seasons = {y: season_weather(weather[y], crop, y) for y in years}
            for method in methods:
                demand = mean_daily_demand(crop, soil, method, list(seasons.values()))
                n_safe = SAFE_INTERVAL[method]
                safe_m = safe_multiplier(crop, soil, method, list(seasons.values()), n_safe, demand)
                for y in years:
                    decide, _ = sutech_decider(crop, soil, method)
                    strategies = {"sutech": run_season(crop, soil, method, seasons[y], decide)}
                    for n in CALENDAR_DAYS[method]:
                        strategies[f"calendar_{n}d"] = run_season(crop, soil, method, seasons[y],
                                                                  calendar_decider(n, demand * n))
                    strategies[f"calendar_{n_safe}d_safe"] = run_season(
                        crop, soil, method, seasons[y], calendar_decider(n_safe, demand * n_safe * safe_m))
                    for name, s in strategies.items():
                        rows.append(dict(location=loc, crop=crop, method=method, year=y, strategy=name,
                                         gross_m3_ha=s.gross_mm * 10, events=s.events,
                                         stress_days=s.stress_days, deep_perc_mm=s.deep_perc,
                                         rel_yield=s.relative_yield(KY[crop]),
                                         kwh_ha=s.gross_mm * 10 / PUMP_M3H * PUMP_KW,
                                         closure_mm=s.closure_error(),
                                         dose_multiplier=safe_m if name.endswith("_safe") else 1.0))
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    """Per crop x method x strategy: mean over location-years, and paired difference vs Su-Tech."""
    key = lambda r: (r["crop"], r["method"])
    out = []
    for (crop, method) in sorted({key(r) for r in rows}):
        sub = [r for r in rows if key(r) == (crop, method)]
        sut = {(r["location"], r["year"]): r for r in sub if r["strategy"] == "sutech"}
        for strat in sorted({r["strategy"] for r in sub}):
            rs = [r for r in sub if r["strategy"] == strat]
            diffs = [(sut[(r["location"], r["year"])]["gross_m3_ha"] - r["gross_m3_ha"]) / r["gross_m3_ha"] * 100
                     for r in rs if r["gross_m3_ha"] > 0]
            out.append(dict(
                crop=crop, method=method, strategy=strat, n=len(rs),
                water_m3_ha=mean(r["gross_m3_ha"] for r in rs),
                water_sd=stdev([r["gross_m3_ha"] for r in rs]) if len(rs) > 1 else 0.0,
                stress_days=mean(r["stress_days"] for r in rs),
                rel_yield=mean(r["rel_yield"] for r in rs),
                deep_perc_mm=mean(r["deep_perc_mm"] for r in rs),
                events=mean(r["events"] for r in rs),
                sutech_vs_this_pct=None if strat == "sutech" or not diffs else mean(diffs),
                sutech_less_water_in=None if strat == "sutech" else sum(d < 0 for d in diffs),
            ))
    return out


def write_outputs(rows: list[dict], summary: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (("simulation_runs.csv", rows), ("simulation_summary.csv", summary)):
        with (out_dir / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    f = lambda v, nd=0: "—" if v is None else f"{v:.{nd}f}"
    lines = ["# Retrospective simulation: Su-Tech vs fixed calendar", "",
             f"{len({(r['location'], r['year']) for r in rows})} location-seasons per crop/method "
             f"({', '.join(LOCATIONS)}; {YEARS[0]}–{YEARS[-1]}), loam, same irrigation method for both strategies.",
             "Model-vs-model on reanalysis weather — see LIMITATIONS in research/simulate.py.", "",
             "| crop | method | strategy | water m³/ha (sd) | events | stress days | rel. yield | deep perc. mm | Su-Tech vs this | Su-Tech used less in |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s in summary:
        lines.append(f"| {s['crop']} | {s['method']} | {s['strategy']} | {f(s['water_m3_ha'])} ({f(s['water_sd'])}) | "
                     f"{f(s['events'])} | {f(s['stress_days'], 1)} | {f(s['rel_yield'], 3)} | {f(s['deep_perc_mm'])} | "
                     f"{'—' if s['sutech_vs_this_pct'] is None else f(s['sutech_vs_this_pct'], 1) + ' %'} | "
                     f"{'—' if s['sutech_less_water_in'] is None else str(s['sutech_less_water_in']) + '/' + str(s['n'])} |")
    worst = max(abs(r["closure_mm"]) for r in rows)
    lines += ["", f"Water-balance closure check: max |error| = {worst:.2e} mm over all {len(rows)} runs.", ""]
    (out_dir / "simulation_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "results")
    ap.add_argument("--source", choices=sorted(SOURCES), default="power")
    a = ap.parse_args()
    rows = simulate(fetch=SOURCES[a.source])
    summary = summarise(rows)
    write_outputs(rows, summary, a.out)
    print((a.out / "simulation_summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
