# Changelog

## Unreleased, 25 November

- The Telegram home menu opens a guided irrigation calculation. Enter plot size in hectares, square metres, sotkas or rectangular dimensions, send the plot pin, and use a planting date or an approximate growth stage. The setup asks whether the crop is outdoors, in greenhouse soil, or on a substrate before recommending a dose. Heated greenhouses require measured indoor ET₀. Reported doses are labelled as estimates, and actual watering can be entered in litres or cubic metres.

## Unreleased, 21 November

- Deletion now blocks writes from an old session, including deferred calculations and AI answers. Interrupted erasure resumes on the next owner operation. Operational data expire on activity. The private backup tool supports authenticated encryption and offline staging recovery. See `docs/DATA_RECOVERY.md` for verified behavior and deployment limits.
- The offline browser demo includes three greenhouse examples, shared crop names and an explicit substrate restriction. CI checks the frontend together with the bot and exercises the demo in a mobile browser.
- The greenhouse presentation and English brief tie each claim to its evidence and include a worked seasonal cost example for scheduling and pump replacement.
- Research reports show how observation mistakes and delayed irrigation affect the historical and current models. The experiment analysis validates drainage and observation intervals and reports the dry-mass non-inferiority bound.
- Uncertain classifier results withhold candidate labels. Pump firmware rejects conflicting commands while running and validates flow calibration before using it for volume control.

## Unreleased, 18 November
- External-service failures preserve the original AI question/photo in Telegram. Late weather/Gemini responses are rejected before use, automatic retries exclude quota/auth and uncertain network failures, and delayed database writes cannot take over a newer lease or AI conversation. Field parameter resets preserve checks/watering logged during weather loading. The live SDK has no timers/HTTP cancellation; these are response acceptance deadlines, not hard request timeouts (see `docs/SERVICE_RELIABILITY.md`).
- Field status now describes input completeness rather than unmeasured confidence. "Why this?" states that field accuracy has not been measured; soil checks before a field reset no longer count as current checks.
- README, agronomist brief, jury notes and public site copy distinguish simulation results, formula checks and field measurements. `docs/EVIDENCE.md` records the published study configuration versus the live engine. Published result values are unchanged; historical PDF/PPTX regeneration remains in readiness Task 10.

Dates are 2026. The engine version is the `VERSION` constant of `serverless/tgcloud/lib/balance.js` (the same string as `CALCULATION_VERSION` in `bot/water_balance.py`).

## Unreleased, 18 November
- **Previous Mini App design restored at the owner's request.** Restored the complete pre-unslop layout, copy, typography, crop illustrations and original glass/green surfaces. Kept animation improvements in a separate motion-only stylesheet: transform-based selection continuity, short help reveals, stable controls and live reduced-motion support. Calculation fixes and Windows test compatibility are retained.
- **Mini App interface refined.** Preserved the logo and green brand palette while replacing glass, background gradients, emoji crop illustrations and the decorative ticker with readable field controls and a calmer map workspace. Added short selection and help transitions, visible keyboard focus and a skip link; reduced-motion preferences apply to live interactions and submission. RU/KZ/EN, automatic themes and the existing calculation/Telegram flows are preserved.
- **Website verification on Windows.** Demo imports use file URLs and the results test accepts CRLF line endings; browser checks cover responsive layouts, themes, validation and motion.

## Unreleased, 17 November
- **Engine fao56.10: greenhouse applicability applies to every crop.** Rice no longer bypasses the substrate/heated-greenhouse restrictions. Legacy saved advice is checked again before display or watering; old buttons and persisted watering conversations cannot continue a watering flow for an unsupported case. Python reports and explanations show the restriction without a volume or a fabricated cost saving. The Mini App now sends greenhouse settings for rice too. Python/JavaScript crop matrices and stored-field regressions cover the restriction.

## 0.9.0, 17 November
- **Theme switch removed (website).** The Mini App no longer has a light/dark/auto picker: the page always follows the device (or Telegram). A choice saved by an earlier version is ignored and cleared.
- **Documentation and site brought in step with the bot.** README feature list, agronomist brief (new section on checking and correcting the bot), jury Q&A (expert mode, self-check, no scheduler), about page in EN/RU/KZ. No engine change, so the study numbers are unchanged.
- **Soil-check reminder without a scheduler.** The Telegram Serverless platform has no way to run code on a schedule, so the bot cannot message farmers by itself. Instead, a field not checked for more than 7 days (or never) is marked 🔔 in «My fields», and its card says how long ago it was checked and asks for a check (replacing the generic request, so it is not repeated).
- **Short setup in the bot chat: five questions + «We assumed».** Crop, area, location, planting date (date like 15.05 or 15.05.2026, or days), irrigation method; the rest has safe defaults (loam, normal moisture, open field, no salinity, no pump). The last screen lists every assumption and has «Refine» buttons for soil (with a rough rolling test), moisture, greenhouse/field, salinity and pump. The Mini App form is unchanged.
- **Field self-check (bot).** «Why this?» shows how far the model was from the farmer's last (up to 4) soil checks, in mm and as a share of RAW. If at least 3 checks all miss in the same direction by more than 10% of RAW, it says so and points to the Kc multiplier in expert mode. It only reports: the bot never changes a field by itself.
- **Expert mode (bot).** Field screen → «Expert mode»: an agronomist can set p, root depth and a Kc multiplier for one field. Values are range-checked, applied from today on top of FAO-56 (past days are not recalculated), marked «changed manually» with the table value, kept when the field is restarted, listed in the «Why this?» card and in the CSV with a change log. «Back to FAO values» removes every override. Not available for rice and custom crops. The shared engine (`balance.js`) is unchanged.
- **Report polish for agronomists.** Details card shows the growth stage, day, root depth, localized soil name and units, weather source, rounded numbers; volume is rounded sensibly; a note explains a large first-day volume on drip (accumulated deficit); field CSV export now includes parameters, engine version, waterings and soil checks.
- **Engine fao56.9.** Pump daily limit (20 h/day: a larger volume is advised over several days); initial Kc scaled by the wetted fraction for drip (FAO-56 eq. 60); salinity: leaching water (FAO-29 eq. 9) and salt yield loss (FAO-56 Table 23) from laboratory ECw/ECe, nothing invented without them; greenhouse on a substrate or heated without a measured ET0 gets no advice, with the reason.
- **Coefficients checked against FAO-56 Tables 11, 12, 19, 20, 22, 23** (`docs/COEFFICIENT_CHECK.md`); fixed soil θFC/θWP of loam and clay (outside the Table 19 ranges, available water unchanged) and the initial Kc of melon.
- **Crop catalog** `crops/catalog.json`: 17 crops from one file, generated Python/JS tables and Mini App list; ten new crops (sugar beet, sunflower, barley, cucumber, sweet pepper, eggplant, cabbage, onion, carrot, watermelon).
- **Website:** project page, browser demo (the bot's own engine), results page, privacy page, liquid-glass design in the logo colours; Mini App publishes from `main`.
- **Bot:** each advice shows a confidence level (high / medium / low) and what raises it; "Why this?" lists the assumptions, where each number comes from and what changes if the crop or soil differ from the table; soil-check screen with sampling depth and a feel test; "My data" screen with delete-my-data (double confirmation).
- **Research:** study with a wrong model (real crop Kc ±15 %, soil water ±20 %): `research/results/misspecified.md`. The published study runs without the drip wetted-fraction correction so its numbers reproduce (`REPRODUCE.md`).
- **Project hygiene:** MIT licence, `CITATION.cff`, pre-registration draft, automatic deploy and daily backup workflows, tests moved to `tests/`, documents to `docs/`.

## 0.8.0, November (before the review)
- Bot and Mini App on Telegram Serverless; photo diagnosis; demo for the jury; pitch deck sources.
