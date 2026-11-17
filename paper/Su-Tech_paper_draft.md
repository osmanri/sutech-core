# Su-Tech: explainable irrigation scheduling from the FAO-56 water balance, with a closed-loop soil check

**Author:** Osman Tolobek · [school, city — to be filled in]
**Status:** DRAFT for the author's revision (updated 17 November 2026). Sections marked **[AUTHOR]** need the author's own text or data; the pot experiment (Section 4.6) has **no results yet**. Tables 1–3 are produced by `research/` and reproduce with `REPRODUCE.md`.

## Abstract

Irrigation decisions in southern Kazakhstan are made under tight water limits, yet farm-level scheduling tools remain hard to use for small farms. We present Su-Tech, a decision-support system that turns weather, crop, soil and irrigation-method data into a daily irrigate/wait decision, a water volume and a pump cost, and explains every calculation step in a Telegram chat. The core is the FAO-56 root-zone water balance with a water-stress coefficient Ks. We evaluate it in a retrospective simulation on real weather (NASA POWER, five irrigated regions, 2021–2025, cotton and maize, drip and furrow irrigation), comparing Su-Tech with fixed irrigation calendars that use the same irrigation method. Against the strongest fixed calendar — interval and dose optimised with hindsight so that every season keeps ≥ 98% relative yield — Su-Tech used **15–28% less water** (95% bootstrap intervals about ±2 percentage points; worst single location-season 9–20%) and had no days of crop water stress, in 25 of 25 location-seasons for each crop/method combination. Across two distinct soils and three planting dates (36 combinations) the saving was 14–42% and held in every season. Against an uncalibrated calendar with the same mean dose, Su-Tech used 2–9% *more* water, but avoided 38–65 days of stress per season; the saving therefore exists only when yield is held equal. A sensitivity analysis shows that random forecast errors are almost harmless, while a systematic −20% ET₀ bias causes 71–73 stress days per season; a weekly three-level soil-moisture check (wet / normal / dry), implemented in the bot, removes the stress and retains 14–17% saving. When the real crop and soil differ from the bot's parameters by 15–20%, the weekly check keeps stress at 0.0–0.4 days per season, but the saving falls from about 23% to zero (+3% water on average in the worst direction). These results are model-versus-model; a bench experiment with weighed pots (pre-registered protocol and tools included) is designed to test them.

**Keywords:** irrigation scheduling, FAO-56, water balance, decision support, Kazakhstan, closed-loop control.

## 1 Introduction

Southern Kazakhstan relies on the transboundary Syr Darya for irrigated agriculture, and in 2026 the government set regional water-consumption caps (Turkestan Region: 3.8 billion m³) and planned reductions of water-intensive crops [R7]. Under such limits the timing and dose of each irrigation matter for farmers and for the basin. Established tools exist — most notably FAO's CROPWAT [R2] — but they are desktop programs aimed at specialists, whereas a small farm needs a short answer on a phone: *irrigate now or wait, how much, and at what energy cost?*

**Research questions.** (1) At equal yield, how much water can daily FAO-56 water-balance scheduling save compared with fixed irrigation calendars in Kazakhstan's irrigated regions? (2) How robust is the decision to errors in the inputs (forecast ET₀, rainfall, soil type)? (3) Can a cheap farmer-supplied soil check correct systematic forecast error?

**Contribution.** (a) An open implementation of the FAO-56 balance with Ks in two languages of code (Python reference, JavaScript production) that agree on 675 reference scenarios; (b) a reproducible retrospective study on real weather with an equal-yield baseline; (c) a quantified failure mode (systematic ET₀ bias) and a remedy that is built into the product; (d) a bench-experiment protocol and tooling for ground-truth testing. The author's own part is described under *Author contribution and use of AI*.

## 2 Related work and gap

**FAO-56 and CROPWAT.** The FAO-56 guidelines [R1] define reference evapotranspiration (Penman–Monteith) and the dual-purpose crop coefficient and root-zone balance approach used here. CROPWAT 8.0 implements these procedures and builds irrigation schedules from a daily soil-water balance [R2]; an evaluation against field measurements in southern Ukraine (2012–2017; sweet and grain maize, soybean, sorghum) found large differences between calculated and measured evapotranspiration, up to 46% for drip-irrigated sweet maize, and concluded that CROPWAT 8.0 should not be used without calibrating the crop coefficients [R3]. The same calibration caveat applies to our crop and soil parameters.

**Mobile scheduling tools.** Smartphone applications built on FAO-56 exist: CropFit for cotton in the US Southeast delivers daily push notifications from a daily balance, and extension summaries report water reductions of up to 40–44% with yield gains [R4] (extension reports, not independently reviewed here); IrriMobile estimates ET₀ with neural networks and, compared with an FAO-56 Penman–Monteith schedule on green maize, overestimated irrigation requirements by 8% (temperature and humidity inputs) and 19% (temperature only) [R5]. For Central Asia, a conference presentation reports ET-based irrigation scheduling pilots in Uzbekistan with water savings of about 32–35% over two years [R6] (a secondary summary of a presentation, not a peer-reviewed measurement; we cite it only as context). We found no published evaluation of a *messaging-bot* scheduling tool, nor one that evaluates a farmer-supplied soil check as a correction to forecast bias. *[Search log: paper/literature_log.md. A systematic search by the author is still needed before claiming novelty.]*

**Gap.** A step-by-step, explainable, phone-native tool for small farms in Kazakhstan, evaluated against an equal-yield baseline and with a quantified robustness analysis and built-in correction.

## 3 Methods

### 3.1 Water balance
For each day, root-zone depletion follows FAO-56 chapter 8:
`Dr,i = clamp(Dr,i−1 + ETc − Peff − I, 0, TAW)`, with `TAW = 1000 (θFC − θWP) Zr`, `RAW = p·TAW`, `ETc = Ks·Kc·ET₀` and, when `Dr > RAW`, `Ks = (TAW − Dr) / ((1 − p)·TAW)` (FAO-56 eq. 84, using start-of-day depletion). Water driven below `Dr = 0` is deep percolation. Effective rainfall is 0 below 5 mm and 0.75·P otherwise (a project simplification, not an FAO formula). Root depth grows linearly to the end of crop development. Su-Tech decides "irrigate" when depletion reaches `min(RAW, delivery-system threshold)` and applies the computed depletion; gross volume is `net / efficiency` (drip 0.90, furrow 0.50). Crop, soil and efficiency parameters are project values, not a local calibration.

### 3.2 ET₀ and weather
Daily weather comes from NASA POWER (2 m temperature, dew point, wind, all-sky shortwave radiation, precipitation) [R8] for the coordinates of five regional centres (Turkestan, Shymkent, Kyzylorda, Taraz, Taldykorgan), 2021–2025. ET₀ is computed with an own implementation of FAO-56 Penman–Monteith, which reproduces intermediate quantities of FAO-56 Example 18 (e_s = 1.997 kPa, R_a = 41.09 MJ m⁻² d⁻¹ confirmed against an independent implementation; final ET₀ 3.880 mm d⁻¹ against 3.88 ≈ 3.9 in the book, net radiation 13.28 MJ m⁻² d⁻¹ as in the book; checked against the book's text on 17 November 2026). The production bot takes ET₀ and rainfall from Open-Meteo [R9].

### 3.3 Retrospective simulation
The "truth" model is the balance of Section 3.1 on real weather (planting 1 May; cotton 195 d, maize 125 d; loam). Two strategies irrigate the same field with the same irrigation method:
* **Su-Tech:** the production engine, tracking its own deficit and never seeing the truth state.
* **Calendar:** a fixed net dose every N days, sized from the long-term mean crop demand of the same location. A **plain** calendar uses that dose. The **best calendar** — the main baseline — searches the interval (drip 1–7 d, furrow 5–21 d) and, for each interval, the smallest dose multiplier (bisection, tolerance 0.005) for which *every* season at that location reaches ≥ 98% relative yield; the combination with the least water wins. Both are chosen with hindsight of all five seasons, which favours the calendar (a farmer cannot know them in advance). An earlier version used a fixed 5-day (drip) or 10-day (furrow) interval; on sandy soil such a calendar cannot reach the yield target at any dose, which motivated the stronger baseline. Relative yield uses the FAO-33 relation `1 − Ya/Ym = Ky (1 − ETa/ETm)` [R10] with Ky = 0.85 (cotton) and 1.25 (maize).

The seasonal water balance closes to 10⁻¹² mm in all 500 runs. Su-Tech and calendar are compared as paired differences per location-season (25 per crop/method).

### 3.4 Sensitivity analysis
Su-Tech decides with a degraded forecast while the truth model uses real weather: random multiplicative ET₀ error (σ = 10, 20, 30%; 20 replicates, fixed seed), rainfall never forecast, wrong soil entered, and systematic ET₀ bias of ±20%. The bias scenario is repeated with a soil check that resets the app's deficit every 3 or 7 days, as the farmer's three-level judgement (wet = 0, normal = RAW/2, dry = RAW).

### 3.5 Robustness to soil and planting date
The best-calendar comparison is repeated for every combination of soil (sand, loam, clay), planting date (15 April, 1 May, 15 May), crop and irrigation method — 36 combinations of 25 location-seasons each (`research/robustness.py`).

### 3.6 Bench experiment (designed, not yet run)
Twelve pots, two groups assigned by lottery (Su-Tech vs fixed schedule), 4–6 weeks, a fast-growing crop. A load cell with an HX711 amplifier weighs each pot daily; evaporation is the weight loss corrected for added water. Outcomes: model accuracy (RMSE, MAE, bias of predicted vs weighed ET), total water per pot, dry mass, dry mass per litre; Welch's t-test and Cohen's d. Protocol: `experiment/PROTOCOL.md`; tools: `experiment/collect.py`, `experiment/analyze.py`.

## 4 Results

### 4.1 Water use at equal yield
| Crop, method | Su-Tech water, m³/ha | Best equal-yield calendar, m³/ha | Su-Tech saving (95% CI) | Worst–best season | Seasons with less water | Plain calendar (same mean dose): Su-Tech vs calendar | Stress days: Su-Tech / plain calendar | Relative yield: Su-Tech / plain calendar |
|---|---|---|---|---|---|---|---|---|
| cotton, drip | 11 321 | 15 117 | **25%** (23–27%) | 18–34% | 25/25 | +5.1% | 0 / 65 | 1.00 / 0.88 |
| cotton, furrow | 19 751 | 27 600 | **28%** (26–30%) | 20–38% | 25/25 | +1.7% | 0 / 60 | 1.00 / 0.87 |
| maize, drip | 9 039 | 10 709 | **15%** (14–17%) | 9–25% | 25/25 | +5.4% | 0 / 39 | 1.00 / 0.89 |
| maize, furrow | 15 781 | 19 525 | **19%** (17–21%) | 12–30% | 25/25 | +2.1% | 0 / 38 | 1.00 / 0.86 |

Su-Tech used less water than the equal-yield calendar in every one of the 25 location-seasons for each combination (the bootstrap intervals in Table 1 treat the 25 location-seasons as independent and are therefore optimistic; the worst-to-best range is given beside them), while the best calendar — daily for drip, every 5 days for furrow, with doses 1.18–1.49 × mean demand — still had 6–10 days of mild stress and a relative yield of 99.2–99.4% (Su-Tech: no stress days). Compared with a *plain* calendar of the same mean dose Su-Tech used somewhat more water (+2 to +9% across the tested intervals) but kept the crop unstressed; the plain calendars suffered 38–65 stress days and a relative yield of 0.84–0.90. Deep percolation per season was 2–24 mm for Su-Tech, 127–150 mm for the plain calendars and 210–394 mm for the best calendars, whose larger doses are what costs the extra water (per-run values in `research/results/simulation_runs.csv`).

![Water use at equal yield](../docs/img/water_by_strategy.svg)

### 4.2 Other soils and planting dates
Over all 36 soil × planting-date × crop × method combinations Su-Tech used less water than the best calendar in every season (36/36 combinations, 25/25 seasons each), with a mean saving of 26% and a range of 14–42%; it never had stress days. The saving is largest on sand (26–42%), where a calendar must over-irrigate heavily because the root zone stores little water, and 14–29% on loam. **Clay gave results identical to loam**: in the project's soil parameters both have the same available water (θFC − θWP = 0.15), so the model cannot distinguish them — effectively two soils were tested. Worst single season anywhere: 6% saving. Full table: `research/results/robustness.md`.

### 4.3 Robustness to input errors (cotton)
| Scenario | Stress days (drip) | Water vs equal-yield calendar (drip) | Stress days (furrow) | Water vs equal-yield calendar (furrow) |
|---|---|---|---|---|
| Perfect forecast | 0.0 | -24.8% | 0.0 | -28.3% |
| Random ET₀ error, σ = 10% | 0.0 | -24.5% | 0.0 | -28.0% |
| Random ET₀ error, σ = 30% | 0.0 | -21.3% | 0.0 | -24.8% |
| Rain never forecast | 0.0 | -23.4% | 0.0 | -26.0% |
| Wrong soil entered (sand for loam) | 0.0 | -24.8% | 0.0 | -28.3% |
| ET₀ biased +20% | 0.0 | -9.6% | 0.0 | -13.2% |
| ET₀ biased −20% | 72.8 | -40.1% | 70.8 | -43.2% |
| ET₀ biased −20% + 3-level soil check every 7 d | 0.0 | -17.0% | 0.0 | -13.5% |
| ET₀ biased −20% + 3-level soil check every 3 d | 0.0 | -12.2% | 0.0 | -0.5% |

Random errors had little effect. A systematic ET₀ underestimate accumulates in the app's own balance, because the app cannot see the soil, and caused 71–73 stress days. A weekly three-level soil check eliminated them while keeping 14–17% saving; checking every 3 days nearly removed the saving (0–12%) because coarse repeated judgements trigger extra irrigations. An accurate sensor (±10 mm) read weekly kept 19–23%.

![Stress days under input errors](../docs/img/sensitivity_stress.svg)

### 4.4 Validation
ET₀ implementation vs FAO-56 Example 18: see 3.2 and `../docs/audits/VALIDATION.md`. A comparison with CROPWAT 8.0 on identical inputs is **not yet done [AUTHOR]**. Python and JavaScript engines agree on 1 425 reference scenarios (relative tolerance 10⁻⁸), and the production engine equals an independently written FAO-56 re-derivation on 5 000 random fields. All coefficients (Kc, depletion fraction, root depth, stage lengths where tabulated, soil water, wetted fraction, salt tolerance) were compared with FAO-56 Tables 11, 12, 19, 20, 22 and 23; two soil values and one Kc were corrected, and the project's own choices (stage calendars of wheat, maize and tomato, minimum root depth, delivery thresholds, rainfall rule, greenhouse factor) are marked as such (`docs/COEFFICIENT_CHECK.md`).

### 4.5 A wrong model
The main comparison lets the bot and the simulated field share the same equations. To remove that circularity, `research/misspecified.py` makes the real crop and soil differ from the bot's parameters (crop coefficient ±15%, plant-available soil water ±20%, and the two worst combinations; loam; cotton and maize; drip and furrow; 100 seasons per row) and searches the strongest equal-yield calendar on the *real* field. With the weekly three-level soil check the bot's crop stress stayed at 0.0–0.4 days per season (calendar 6.9–10.6) and the worst-season relative yield at 0.997 or better. The water saving ranged from 23% (soil holds 20% less than assumed) through 17.5% (parameters correct) and 4% (crop uses 15% less) to **−2.8% on average, +27.7% in the worst season** (crop uses 15% less *and* soil holds 20% more: the bot over-irrigates and uses more water than the best calendar, at full yield). Without the weekly check, a bot that underestimates the crop by 15% had 28 stress days per season (45 in the worst combination; worst-season yield 0.92). The saving therefore depends on how close the bot's parameters are to the real field, and the weekly check is part of the method. Table: `research/results/misspecified.md`.

### 4.6 Bench experiment
**[AUTHOR: results go here after the experiment — model accuracy (RMSE/MAE/bias), water per pot by group with Welch test and effect size, dry mass, and a photograph of the stand. Do not fill this section with simulated numbers.]**

## 5 Discussion

The saving of 15–28% (14–42% across soils and planting dates; about 23% down to zero when the bot's parameters are wrong by 15–20%) is the price of safety that a fixed calendar must pay: because it cannot react to rain or heat waves, it needs a margin large enough for the worst season. Su-Tech's advantage is therefore timing, not a more efficient irrigation system, and it is largest where the baseline efficiency is lowest (furrow). The weak point is equally clear: a decision tool that integrates its own estimate drifts when inputs are biased, so a cheap, infrequent observation of the real soil is essential. This is built into the bot as a button, and the study supports a weekly rhythm.

## 6 Limitations
* Model against model, on reanalysis weather for regional centres, not farm stations; no field measurement of yield or water yet.
* Yield is estimated from the FAO-33 relation, not measured.
* Soils differ in the model only by available water; clay and loam coincide, so two soils were effectively tested. No salinity or capillary rise; crop and soil parameters are not locally calibrated.
* The best calendar is chosen with hindsight of all seasons, which favours the calendar; a real farmer could not achieve it.
* Su-Tech has perfect weather knowledge in the main comparison; forecast error is treated only in the sensitivity analysis.
* Drip-mode Su-Tech irrigates almost daily (94–129 events per season), which in practice needs automation.
* The soil check is simulated with the same three levels as the app; real farmer judgement may be noisier.
* Effective rainfall uses a simple project rule.
* The published tables were computed without the FAO-56 eq. 60 correction of the initial crop coefficient for the part of the surface wetted by drip irrigation; with it the drip saving is higher (cotton 31%, maize 20%), see `REPRODUCE.md`. The bench experiment and a field pilot are planned and have no data yet.

## 7 Conclusion
On five years of real weather in five regions, FAO-56 daily scheduling with a stress coefficient saved 15–28% water against the strongest fixed calendar at equal yield (14–42% across soils and planting dates) and avoided crop stress, and a weekly farmer soil check made it robust to systematic forecast bias. These are model results and not yet measurements. In simple terms: a daily water-balance calculation can save a lot of water compared with a fixed schedule if the schedule must also protect the crop, but it needs an occasional look at the real soil to stay correct. The next steps are my bench experiment with weighed pots and, in 2027, a trial on a real field. **[Replace this paragraph with the final conclusion after the experiment.]**

## Author contribution and use of AI
I came up with the project and built the physical test stand myself: an Arduino Uno with a relay and a small pump, a soil-moisture sensor, a water-level sensor and a temperature and humidity sensor. I am now adding a scale for the pots, and in the coming weeks I will run the experiment on it; the results will go into Section 4.6 and are not in this draft yet.

I wrote the software with the help of an AI coding assistant (Claude Code). It wrote most of the code, the simulation and the first version of this text. I chose what to build and which questions to ask, and I am learning to explain each formula and each assumption myself; where my own understanding or measurements are still missing, this draft says so. The weather data come from NASA POWER, and the formulas come from the FAO-56 and FAO-33 papers listed below.

## Data and code availability
All code, cached weather, result tables and figures: `github.com/osmanri/sutech-core` (`research/`, `experiment/`, `bot/`). Reproduce with the commands in `REPRODUCE.md` (offline, about a minute). Licence: MIT; citation file `CITATION.cff`. The pot experiment is pre-registered in `experiment/PREREGISTRATION.md` (to be registered on OSF before the first weighing).

## References
* [R1] Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration — Guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56. FAO, Rome.
* [R2] FAO. CROPWAT. https://www.fao.org/land-water/databases-and-software/cropwat
* [R3] Vozhehova, R.A., Lavrynenko, Yu.O., Kokovikhin, S.V., Lykhovyd, P.V., Biliaieva, I.M., Drobitko, A.V., Nesterchuk, V.V. (2018). Assessment of the CROPWAT 8.0 software reliability for evapotranspiration and crop water requirements calculations. *Journal of Water and Land Development* 39, 147–152. doi:10.2478/jwld-2018-0070.
* [R4] University of Georgia Extension, SI CropFit app: https://precisionagirrigation.extension.uga.edu/2025/06/setting-up-and-using-the-si-cropfit-app-for-irrigation-scheduling/
* [R5] Ferreira, L.B., da Cunha, F.F., de Oliveira, R.A., Rodrigues, T.F. (2020). A smartphone APP for weather-based irrigation scheduling using artificial neural networks. *Pesquisa Agropecuária Brasileira* 55, e01839. doi:10.1590/s1678-3921.pab2020.v55.01839.
* [R6] Nangia, V. (2016). Managing scarce water resources in irrigated agri-food systems of Central Asia: two case studies. Conference presentation, ASA/CSSA/SSSA International Annual Meeting, Phoenix. https://repo.mel.cgiar.org/handle/20.500.11766/5976 (the 32–35% figure is quoted from a secondary summary; the slides themselves have not been read).
* [R7] Reports on 2026 irrigation limits for southern Kazakhstan: https://timesca.com/kazakhstan-sets-irrigation-limits-for-southern-regions-and-reduces-water-intensive-crops/
* [R8] NASA Langley Research Center POWER Project, funded through the NASA Earth Science/Applied Science Program. https://power.larc.nasa.gov/
* [R9] Open-Meteo. https://open-meteo.com/
* [R10] Doorenbos, J., Kassam, A.H. (1979). *Yield response to water.* FAO Irrigation and Drainage Paper 33. FAO, Rome.
