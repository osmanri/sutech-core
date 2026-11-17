# Reproduce Su-Tech results

Everything below runs offline on a laptop. The weather is cached in `research/data/weather` (NASA POWER, five
regions of Kazakhstan, 2021–2025), so no internet is needed. Needs Python 3.11+ and Node 22+.

```bash
# 1. All tests (Python 349, bot 1 490+). The bot tests that need the website run when the submodule is present:
git clone --recurse-submodules https://github.com/osmanri/sutech-core.git && cd sutech-core
python3 run_tests.py
cd serverless && npm ci --ignore-scripts && node --experimental-loader ./test/sdk-loader.mjs --test $(ls test/*.test.js | grep -v transport) && cd ..

# 2. The main study: Su-Tech against the strongest fixed calendar at equal yield (about 20 s)
python3 -m research.simulate --source power          # -> research/results/simulation_summary.md and .csv

# 3. Robustness (wrong forecasts, wrong soil), and the study with a wrong model (real crop and soil differ from the bot)
python3 -m research.sensitivity                      # -> research/results/sensitivity_*.md
python3 -m research.robustness                       # -> research/results/robustness.md
python3 -m research.misspecified                     # -> research/results/misspecified.md

# 4. Regenerate the crop tables from the catalog and check nothing drifted
python3 crops/build.py --check
```

**Which engine produced the published numbers.** The published study (README of `research/`, the website, the slides) was
computed with the engine before the drip wetted-fraction correction (FAO-56 eq. 60). The study switches that correction
off by default, so step 2 reproduces the published tables (to floating-point noise, about 1e-16). To see the effect of the
correction: `SUTECH_STUDY_WETTED_FRACTION=on python3 -m research.simulate` (drip saving cotton 25 → 31 %, maize 15 → 20 %).

**What these numbers are and are not.** A computer study of the FAO-56 balance on real weather. It is not a field
measurement. The pot experiment (`experiment/PROTOCOL.md`) and a field pilot are planned; no results from them exist yet.

**The engine itself.** `bot/water_balance.py` (Python reference) and `serverless/tgcloud/lib/balance.js` (live bot and the
website demo) must give the same numbers: 1 425 Python reference scenarios are checked in JavaScript on every change, and
5 000 random fields are checked against an independent re-derivation of the FAO-56 equations
(`serverless/test/independent-audit.test.js`). Coefficients and their sources: `docs/COEFFICIENT_CHECK.md`, `docs/METHOD.md`.
