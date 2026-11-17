# Changelog

Dates are 2026. The engine version is the `VERSION` constant of `serverless/tgcloud/lib/balance.js` (the same string as `CALCULATION_VERSION` in `bot/water_balance.py`).

## 0.9.0, 17 November
- **Engine fao56.9.** Pump daily limit (20 h/day: a larger volume is advised over several days); initial Kc scaled by the wetted fraction for drip (FAO-56 eq. 60); salinity: leaching water (FAO-29 eq. 9) and salt yield loss (FAO-56 Table 23) from laboratory ECw/ECe, nothing invented without them; greenhouse on a substrate or heated without a measured ET0 gets no advice, with the reason.
- **Coefficients checked against FAO-56 Tables 11, 12, 19, 20, 22, 23** (`docs/COEFFICIENT_CHECK.md`); fixed soil θFC/θWP of loam and clay (outside the Table 19 ranges, available water unchanged) and the initial Kc of melon.
- **Crop catalog** `crops/catalog.json`: 17 crops from one file, generated Python/JS tables and Mini App list; ten new crops (sugar beet, sunflower, barley, cucumber, sweet pepper, eggplant, cabbage, onion, carrot, watermelon).
- **Website:** project page, browser demo (the bot's own engine), results page, privacy page, liquid-glass design in the logo colours; Mini App publishes from `main`.
- **Bot:** each advice shows a confidence level (high / medium / low) and what raises it; "Why this?" lists the assumptions, where each number comes from and what changes if the crop or soil differ from the table; soil-check screen with sampling depth and a feel test; "My data" screen with delete-my-data (double confirmation).
- **Research:** study with a wrong model (real crop Kc ±15 %, soil water ±20 %): `research/results/misspecified.md`. The published study runs without the drip wetted-fraction correction so its numbers reproduce (`REPRODUCE.md`).
- **Project hygiene:** MIT licence, `CITATION.cff`, pre-registration draft, automatic deploy and daily backup workflows, tests moved to `tests/`, documents to `docs/`.

## 0.8.0, November (before the review)
- Bot and Mini App on Telegram Serverless; photo diagnosis; demo for the jury; pitch deck sources.
