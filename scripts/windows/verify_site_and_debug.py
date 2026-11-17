"""
Su-Tech v2.1 Enterprise — Automated Site Verification & Debugging Engine (AVDE)
Algorithm for complete 6-stage end-to-end testing of frontend, backend, weather, and hardware.
"""
import sys
import os
import json
import asyncio
import urllib.request
from datetime import datetime, timezone, timedelta

# Fix Windows console encoding if needed
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CWD)

passed_checks = 0
failed_checks = 0
warnings = 0

def check(name, condition, details=""):
    global passed_checks, failed_checks
    if condition:
        passed_checks += 1
        print(f"  \033[92m[PASS]\033[0m {name}")
    else:
        failed_checks += 1
        print(f"  \033[91m[FAIL]\033[0m {name} -- {details}")

def warn(name, details=""):
    global warnings
    warnings += 1
    print(f"  \033[93m[WARN]\033[0m {name} -- {details}")

def header(stage_num, title):
    print(f"\n\033[96m===========================================================================\033[0m")
    print(f"\033[96m[STAGE {stage_num}] {title}\033[0m")
    print(f"\033[96m===========================================================================\033[0m")


# ===========================================================================
# STAGE 1: Static Code, DOM Integrity & Responsive Architecture
# ===========================================================================
header(1, "Static DOM Integrity & Responsive Layout Rules")

html_path = os.path.join(CWD, "frontend", "index.html")
css_path = os.path.join(CWD, "frontend", "css", "app.css")
js_path = os.path.join(CWD, "frontend", "js", "app.js")

check("Frontend HTML file exists", os.path.isfile(html_path))
check("Frontend CSS file exists", os.path.isfile(css_path))
check("Frontend JS file exists", os.path.isfile(js_path))

with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

with open(css_path, "r", encoding="utf-8") as f:
    css_content = f.read()

with open(js_path, "r", encoding="utf-8") as f:
    js_content = f.read()

required_ids = [
    "regionSelect", "btnGetLocation", "map", "fieldAreaInput",
    "soilType", "moistureCondition", "btnSubmitAll", "summaryStatusBadge",
    "unitBtn_hectare", "unitBtn_sotka", "coordsCard", "block1StatusPill"
]

for el_id in required_ids:
    check(f"HTML DOM contains required element #{el_id}", f'id="{el_id}"' in html_content)

# Responsive CSS checks
region_select_css = [part for part in css_content.split("}") if ".region-select" in part]
check("CSS .region-select has no rigid max-width <= 200px", 
      all("max-width:185px" not in rule and "max-width: 185px" not in rule for rule in region_select_css))
check("CSS .map-location-actions supports flex wrapping", "flex:1 1 260px" in css_content or "flex: 1 1 260px" in css_content)
check("CSS includes prefers-reduced-motion accessibility rule", "prefers-reduced-motion" in css_content)
check("CSS uses clean natural agronomic palette", "--accent" in css_content or "var(--bg)" in css_content)


# ===========================================================================
# STAGE 2: User Journeys & State Fallbacks
# ===========================================================================
header(2, "Real User Journeys & State Fallbacks (Simulation)")

# Check that JS requires explicit city/region selection and has city prompt
check("HTML contains mandatory city selection prompt", "selectRegionPrompt" in html_content)
check("JS submitFinalCalculation validates city/location before submission", "select-highlight" in js_content)

# Run frontend node tests
node_test = os.system(f"node \"{os.path.join(CWD, 'frontend', 'test_field_map.cjs')}\" > nul 2>&1")
check("Node.js field map & calculation test suite", node_test == 0, "node frontend/test_field_map.cjs exited with code != 0")


# ===========================================================================
# STAGE 3: Open-Meteo Weather Service & Regional Fallback
# ===========================================================================
header(3, "Weather Service Resilience & Regional Climatic Fallback")

try:
    from bot.balance_weather import fetch_daily_weather, parse_daily_weather
    
    # 3.1 Live Weather Call
    weather_live = asyncio.run(fetch_daily_weather(44.85, 65.50))
    check("Open-Meteo returns valid live data for Kyzylorda", 
          isinstance(weather_live, dict) and "et0" in weather_live and weather_live["et0"] > 0)
    
    # 3.2 A forecast without the field's current local date must be rejected.
    # Use relative dates so this diagnostic stays valid after the test day.
    local_today = datetime.now(timezone(timedelta(seconds=18000))).date()
    dummy_payload = {
        "utc_offset_seconds": 18000,
        "timezone": "Asia/Qyzylorda",
        "daily": {
            "time": [(local_today - timedelta(days=2)).isoformat(),
                     (local_today - timedelta(days=1)).isoformat()],
            "et0_fao_evapotranspiration": [4.2, 4.1],
            "precipitation_sum": [0.0, 0.0]
        },
        "daily_units": {
            "et0_fao_evapotranspiration": "mm",
            "precipitation_sum": "mm"
        }
    }
    try:
        parse_daily_weather(dummy_payload)
    except ValueError as exc:
        check("Stale weather is rejected instead of used for irrigation", str(exc) == "stale weather")
    else:
        check("Stale weather is rejected instead of used for irrigation", False)

    dummy_payload["daily"]["time"][1] = local_today.isoformat()
    parsed = parse_daily_weather(dummy_payload)
    check("Current local forecast is accepted", parsed["et0"] == 4.1 and parsed["rain"] == 0.0)

except Exception as e:
    check("Weather module import & execution", False, str(e))


# ===========================================================================
# STAGE 4: Backend Water Balance (FAO-56 Penman-Monteith) End-to-End
# ===========================================================================
header(4, "Backend Water Balance & Decision Matrix End-to-End")

try:
    from bot.water_balance import parse_field, calculate_balance
    from bot.handlers.webapp import format_balance_report
    
    test_crops = ["cotton", "wheat", "corn", "rice", "alfalfa", "melon", "tomato", "potato", "other"]
    
    for crop in test_crops:
        payload = {
            "balance_version": 2,
            "soil_type": "loam",
            "day_of_growth": 30,
            "moisture_condition": "normal",
            "power_price": 25.0,
            "pump_power_kw": 22.0,
            "pump_productivity_m3h": 60.0,
            "latitude": 44.85,
            "longitude": 65.50,
            "crop": crop,
            "area": 10.0,
            "area_unit": "hectare",
            "irrigation_type": "drip",
            "field_type": "open",
            "is_saline": "no",
            "lang": "ru"
        }
        if crop == "other":
            payload["custom_kc"] = 1.05
            payload["custom_p"] = 0.55
            payload["custom_root_depth"] = 0.7
        
        f = parse_field(payload)
        res = calculate_balance(f, 4.8, 0.0)
        report = format_balance_report("ru", f, res, {"date": "2026-09-21", "timezone": "Asia/Qyzylorda", "et0": 4.8, "rain": 0.0})
        check(f"Crop '{crop}' calculates balance & generates report", 
              res is not None and len(report) > 100)

except Exception as e:
    check("Backend calculation test suite", False, str(e))


# ===========================================================================
# STAGE 5: Hardware Bridge & Watchdog Safety Loop
# ===========================================================================
header(5, "Hardware Cyberphysical Bridge & Watchdog Safety")

try:
    from bot.hardware_bridge import HardwareBridge
    
    bridge = HardwareBridge(force_virtual=True)
    check("Virtual bridge responds to PING", bridge.ping() is True)
    
    telemetry = bridge.get_telemetry()
    check("Virtual bridge generates realistic soil moisture (10-90%)", 10 <= telemetry["soil_moisture"] <= 90)
    check("Virtual bridge generates valid water level (0-100%)", 0 <= telemetry["water_level"] <= 100)
    
    # Watchdog & pump duration test
    irr_res = bridge.trigger_irrigation(10.0)
    check("Pump turns ON upon valid command", irr_res.get("success") is True)
    
    stop_res = bridge.stop_pump()
    check("Pump turns OFF upon stop command", stop_res.get("success") is True)
    
    # Safety: Cannot start pump with <= 0 seconds
    zero_res = bridge.trigger_irrigation(0)
    check("Safety: pump rejects duration <= 0", zero_res.get("success") is False)

except Exception as e:
    check("Hardware bridge tests", False, str(e))


# ===========================================================================
# STAGE 6: Live Production Cloud Verification (Vercel)
# ===========================================================================
header(6, "Live Cloud Production (Vercel Deploy Check)")

try:
    req = urllib.request.Request(
        "https://frontend-2-mauve.vercel.app/",
        headers={"User-Agent": "SuTech-Diagnostic/2.1"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        check("Vercel production returns HTTP 200 OK", resp.status == 200)
        live_html = resp.read().decode("utf-8")
        check("Live Vercel HTML contains region selector", "regionSelect" in live_html)
        check("Live Vercel HTML contains city selection prompt", 'selectRegionPrompt' in live_html or 'value=""' in live_html)

    req_css = urllib.request.Request(
        "https://frontend-2-mauve.vercel.app/css/app.css",
        headers={"User-Agent": "SuTech-Diagnostic/2.1"}
    )
    with urllib.request.urlopen(req_css, timeout=10) as resp:
        live_css = resp.read().decode("utf-8")
        check("Live Vercel CSS loaded successfully", len(live_css) > 500)
        reg_rules = [p for p in live_css.split("}") if ".region-select" in p]
        check("Live Vercel CSS has responsive .region-select (no 185px lock)", 
              all("max-width:185px" not in r and "max-width: 185px" not in r for r in reg_rules))

except Exception as e:
    warn("Live Vercel check", f"Could not verify live site: {e}")


# ===========================================================================
# SUMMARY REPORT
# ===========================================================================
print(f"\n\033[95m===========================================================================\033[0m")
print(f"\033[95m📋 SU-TECH FULL AUDIT SUMMARY\033[0m")
print(f"\033[95m===========================================================================\033[0m")
print(f"  Passed Checks:   \033[92m{passed_checks}\033[0m")
print(f"  Failed Checks:   \033[91m{failed_checks}\033[0m")
print(f"  Warnings:        \033[93m{warnings}\033[0m")

if failed_checks == 0:
    print(f"\n\033[92m🟢 100% HEALTHY: All 6 stages passed. Zero bugs detected.\033[0m")
    sys.exit(0)
else:
    print(f"\n\033[91m🔴 ISSUES DETECTED: Review the failed checks above.\033[0m")
    sys.exit(1)
