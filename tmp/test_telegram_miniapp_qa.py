#!/usr/bin/env python3
"""Comprehensive QA Automation Script for Su-Tech Telegram Mini App.

Validates:
1. DOM Structure & Required IDs (soil-val, water-val, temp-val, btn-irrigate, chart-canvas, etc.)
2. Telegram Mini App viewport & theme metadata
3. CDN asset references (Tailwind, Chart.js, Lucide)
4. Live Endpoints (/api/telemetry, /api/irrigate, /api/stop, /api/recalculate)
5. Clean CSV Export Integrity (no NaN, valid columns)
"""

import sys
import os
import json
import urllib.request
import urllib.error
import re

def test_qa():
    print("=" * 70)
    print("SU-TECH TELEGRAM MINI APP QA AUTOMATION SUITE")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # STAGE 1: HTML DOM & Minimalist Telegram Styling Verification
    # ------------------------------------------------------------------------
    print("\n[STAGE 1] Validating templates/index.html DOM & Telegram Styling Rules...")
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "index.html")
    assert os.path.exists(html_path), f"ERROR: {html_path} does not exist!"

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Viewport check
    assert "user-scalable=no" in html, "Missing mobile lock user-scalable=no in viewport"
    assert "viewport-fit=cover" in html, "Missing viewport-fit=cover for Telegram Mini App"
    print("  [PASS] Viewport configured for Telegram Mini App")

    # Native Telegram Dark Color Palette
    assert "#0E1621" in html, "Missing Telegram background color #0E1621"
    assert "#17212B" in html, "Missing Telegram card slate color #17212B"
    assert "#2481CC" in html, "Missing Telegram native blue accent #2481CC"
    print("  [PASS] Native Telegram dark color palette verified (#0E1621, #17212B, #2481CC)")

    # Mandatory DOM IDs
    required_ids = [
        "soil-val",
        "water-val",
        "temp-val",
        "hum-val",
        "fao-val",
        "deficit-val",
        "btn-irrigate",
        "btn-recalc",
        "btn-export",
        "btn-stop",
        "chart-canvas",
        "comparison-chart",
        "soil-bar",
        "water-bar",
        "water-alert",
        "countdown-timer",
        "connection-badge",
    ]

    for dom_id in required_ids:
        pattern = f'id=["\']{dom_id}["\']'
        assert re.search(pattern, html), f"CRITICAL: Mandatory DOM ID '{dom_id}' missing in index.html!"
        print(f"  [PASS] Mandatory DOM ID found: #{dom_id}")

    # CDN scripts check
    assert "cdn.tailwindcss.com" in html, "Missing Tailwind CDN"
    assert "cdn.jsdelivr.net/npm/chart.js" in html, "Missing Chart.js CDN"
    assert "unpkg.com/lucide@latest" in html, "Missing Lucide Icons CDN"
    print("  [PASS] Valid CDN script tags present (Tailwind, Chart.js, Lucide)")

    # ------------------------------------------------------------------------
    # STAGE 2: Live Backend & Endpoints Validation (http://127.0.0.1:8000)
    # ------------------------------------------------------------------------
    print("\n[STAGE 2] Validating Live Server Endpoints (http://127.0.0.1:8000)...")
    base_url = "http://127.0.0.1:8000"

    # 1. GET /
    try:
        with urllib.request.urlopen(f"{base_url}/", timeout=3.0) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            content = resp.read().decode("utf-8")
            assert "Su-Tech" in content
            print("  [PASS] GET / -> HTTP 200 OK (Served rendered Telegram Mini App)")
    except Exception as e:
        print(f"  [FAIL] Could not connect to local server: {e}")
        return False

    # 2. GET /api/telemetry
    with urllib.request.urlopen(f"{base_url}/api/telemetry", timeout=3.0) as resp:
        assert resp.status == 200
        telemetry = json.loads(resp.read().decode("utf-8"))
        assert "metrics" in telemetry
        assert "soil_moisture_pct" in telemetry["metrics"]
        assert "water_tank_ml" in telemetry["metrics"]
        assert "temperature_c" in telemetry["metrics"]
        assert "fao56" in telemetry
        print(f"  [PASS] GET /api/telemetry -> HTTP 200 OK (Soil: {telemetry['metrics']['soil_moisture_pct']}%, Tank: {telemetry['metrics']['water_tank_ml']} ml)")

    # 3. POST /api/irrigate
    irrigate_req = urllib.request.Request(
        f"{base_url}/api/irrigate",
        data=json.dumps({"duration": 5.0, "force": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(irrigate_req, timeout=3.0) as resp:
        assert resp.status == 200
        irr_res = json.loads(resp.read().decode("utf-8"))
        assert irr_res["success"] is True
        print(f"  [PASS] POST /api/irrigate -> HTTP 200 OK (Pump activated for {irr_res['duration']}s)")

    # 4. POST /api/stop
    stop_req = urllib.request.Request(f"{base_url}/api/stop", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(stop_req, timeout=3.0) as resp:
        assert resp.status == 200
        stop_res = json.loads(resp.read().decode("utf-8"))
        assert stop_res["success"] is True
        print("  [PASS] POST /api/stop -> HTTP 200 OK (Emergency pump cut-off)")

    # 5. POST /api/recalculate
    recalc_req = urllib.request.Request(f"{base_url}/api/recalculate", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(recalc_req, timeout=3.0) as resp:
        assert resp.status == 200
        recalc_res = json.loads(resp.read().decode("utf-8"))
        assert recalc_res["success"] is True
        assert "fao56" in recalc_res
        print(f"  [PASS] POST /api/recalculate -> HTTP 200 OK (ET0 = {recalc_res['fao56']['et0_mm_day']} mm/day)")

    # 6. GET /api/export-csv
    with urllib.request.urlopen(f"{base_url}/api/export-csv", timeout=3.0) as resp:
        assert resp.status == 200
        csv_text = resp.read().decode("utf-8")
        assert "timestamp_iso" in csv_text
        assert "soil_moisture_pct" in csv_text
        assert "NaN" not in csv_text
        lines = [ln.strip() for ln in csv_text.splitlines() if ln.strip()]
        assert len(lines) >= 2, f"CSV should have at least header + 1 row, got {len(lines)}"
        print(f"  [PASS] GET /api/export-csv -> HTTP 200 OK (Clean CSV, {len(lines)} records, 0 NaN)")

    print("\n" + "=" * 70)
    print("[SUMMARY] ALL 17 CHECKS PASSED: 100% HEALTHY TELEGRAM MINI APP INTERFACE")
    print("=" * 70)
    return True

if __name__ == "__main__":
    if not test_qa():
        sys.exit(1)
