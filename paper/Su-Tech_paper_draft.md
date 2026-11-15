# Su-Tech: explainable irrigation scheduling from the FAO-56 water balance, with a closed-loop soil check

**Author:** Osman Tolobek · [school, city — to be filled in]
**Status:** DRAFT for the author's revision. Sections marked **[AUTHOR]** need the author's own text or data; the pot experiment (Section 4.4) has **no results yet**.

## Abstract

Irrigation decisions in southern Kazakhstan are made under tight water limits, yet farm-level scheduling tools remain hard to use for small farms. We present Su-Tech, a decision-support system that turns weather, crop, soil and irrigation-method data into a daily irrigate/wait decision, a water volume and a pump cost, and explains every calculation step in a Telegram chat. The core is the FAO-56 root-zone water balance with a water-stress coefficient Ks. We evaluate it in a retrospective simulation on real weather (NASA POWER, five irrigated regions, 2021–2025, cotton and maize, drip and furrow irrigation), comparing Su-Tech with fixed irrigation calendars that use the same irrigation method. At equal yield (≥ 98% relative yield in every season) Su-Tech used **18–34% less water** (95% bootstrap intervals about ±2 percentage points; in the worst single location-season the saving was still 11–26%) and had no days of crop water stress, in 25 of 25 location-seasons for each crop/method combination. Against an uncalibrated calendar with the same mean dose, Su-Tech used 2–9% *more* water, but avoided 38–65 days of stress per season; the saving therefore exists only when yield is held equal. A sensitivity analysis shows that random forecast errors are almost harmless, while a systematic −20% ET₀ bias causes 71–73 stress days per season; a weekly three-level soil-moisture check (wet / normal / dry), implemented in the bot, removes the stress and retains 19–21% saving. These results are model-versus-model; a bench experiment with weighed pots (protocol and tools included) is designed to test them.

**Keywords:** irrigation scheduling, FAO-56, water balance, decision support, Kazakhstan, closed-loop control.

## 1 Introduction

Southern Kazakhstan relies on the transboundary Syr Darya for irrigated agriculture, and in 2026 the government set regional water-consumption caps (Turkestan Region: 3.8 billion m³) and planned reductions of water-intensive crops [R7]. Under such limits the timing and dose of each irrigation matter for farmers and for the basin. Established tools exist — most notably FAO's CROPWAT [R2] — but they are desktop programs aimed at specialists, whereas a small farm needs a short answer on a phone: *irrigate now or wait, how much, and at what energy cost?*

**Research questions.** (1) At equal yield, how much water can daily FAO-56 water-balance scheduling save compared with fixed irrigation calendars in Kazakhstan's irrigated regions? (2) How robust is the decision to errors in the inputs (forecast ET₀, rainfall, soil type)? (3) Can a cheap farmer-supplied soil check correct systematic forecast error?

**Contribution.** (a) An open implementation of the FAO-56 balance with Ks in two languages of code (Python reference, JavaScript production) that agree on 675 reference scenarios; (b) a reproducible retrospective study on real weather with an equal-yield baseline; (c) a quantified failure mode (systematic ET₀ bias) and a remedy that is built into the product; (d) a bench-experiment protocol and tooling for ground-truth testing. The author's own part is described under *Author contribution and use of AI*.

## 2 Related work and gap

**FAO-56 and CROPWAT.** The FAO-56 guidelines [R1] define reference evapotranspiration (Penman–Monteith) and the dual-purpose crop coefficient and root-zone balance approach used here. CROPWAT 8.0 implements these procedures and builds irrigation schedules from a daily soil-water balance [R2]; one evaluation concluded it should not be used without calibrating crop coefficients to local conditions [R3]. The same calibration caveat applies to our crop and soil parameters.

**Mobile scheduling tools.** Smartphone applications built on FAO-56 exist: CropFit for cotton in the US Southeast delivers daily push notifications from a daily balance, and extension summaries report water reductions of up to 40–44% with yield gains [R4] (extension reports, not independently reviewed here); IrriMobile estimates ET₀ with neural networks for green maize and was found to overestimate irrigation requirements by 8–19% [R5]. A reported ET-based scheduling study in Central Asia found 32–35% water saving over two years [R6] (to be verified against the primary source). We found no published evaluation of a *messaging-bot* scheduling tool, nor one that evaluates a farmer-supplied soil check as a correction to forecast bias. *[Search log: paper/literature_log.md. A systematic search by the author is still needed before claiming novelty.]*

**Gap.** A step-by-step, explainable, phone-native tool for small farms in Kazakhstan, evaluated against an equal-yield baseline and with a quantified robustness analysis and built-in correction.

## 3 Methods

### 3.1 Water balance
For each day, root-zone depletion follows FAO-56 chapter 8:
`Dr,i = clamp(Dr,i−1 + ETc − Peff − I, 0, TAW)`, with `TAW = 1000 (θFC − θWP) Zr`, `RAW = p·TAW`, `ETc = Ks·Kc·ET₀` and, when `Dr > RAW`, `Ks = (TAW − Dr) / ((1 − p)·TAW)` (FAO-56 eq. 84, using start-of-day depletion). Water driven below `Dr = 0` is deep percolation. Effective rainfall is 0 below 5 mm and 0.75·P otherwise (a project simplification, not an FAO formula). Root depth grows linearly to the end of crop development. Su-Tech decides "irrigate" when depletion reaches `min(RAW, delivery-system threshold)` and applies the computed depletion; gross volume is `net / efficiency` (drip 0.90, furrow 0.50). Crop, soil and efficiency parameters are project values, not a local calibration.

### 3.2 ET₀ and weather
Daily weather comes from NASA POWER (2 m temperature, dew point, wind, all-sky shortwave radiation, precipitation) [R8] for the coordinates of five regional centres (Turkestan, Shymkent, Kyzylorda, Taraz, Taldykorgan), 2021–2025. ET₀ is computed with an own implementation of FAO-56 Penman–Monteith, which reproduces intermediate quantities of FAO-56 Example 18 (e_s = 1.997 kPa, R_a = 41.09 MJ m⁻² d⁻¹ confirmed against an independent implementation; final ET₀ 3.88 mm d⁻¹ against ≈ 3.9 in the paper — **[AUTHOR: verify against the printed book]**). The production bot takes ET₀ and rainfall from Open-Meteo [R9].

### 3.3 Retrospective simulation
The "truth" model is the balance of Section 3.1 on real weather (planting 1 May; cotton 195 d, maize 125 d; loam). Two strategies irrigate the same field with the same irrigation method:
* **Su-Tech:** the production engine, tracking its own deficit and never seeing the truth state.
* **Calendar:** a fixed net dose every N days, sized from the long-term mean crop demand of the same location. A **plain** calendar uses that dose; an **equal-yield** ("safe") calendar multiplies it by the smallest factor (0.05 steps) for which *every* season at that location reaches ≥ 98% relative yield. The factor is chosen with hindsight of all five seasons, which favours the calendar (a farmer cannot know it in advance). Relative yield uses the FAO-33 relation `1 − Ya/Ym = Ky (1 − ETa/ETm)` [R10] with Ky = 0.85 (cotton) and 1.25 (maize).

The seasonal water balance closes to 10⁻¹² mm in all 500 runs. Su-Tech and calendar are compared as paired differences per location-season (25 per crop/method).

### 3.4 Sensitivity analysis
Su-Tech decides with a degraded forecast while the truth model uses real weather: random multiplicative ET₀ error (σ = 10, 20, 30%; 20 replicates, fixed seed), rainfall never forecast, wrong soil entered, and systematic ET₀ bias of ±20%. The bias scenario is repeated with a soil check that resets the app's deficit every 3 or 7 days, as the farmer's three-level judgement (wet = 0, normal = RAW/2, dry = RAW).

### 3.5 Bench experiment (designed, not yet run)
Twelve pots, two groups assigned by lottery (Su-Tech vs fixed schedule), 4–6 weeks, a fast-growing crop. A load cell with an HX711 amplifier weighs each pot daily; evaporation is the weight loss corrected for added water. Outcomes: model accuracy (RMSE, MAE, bias of predicted vs weighed ET), total water per pot, dry mass, dry mass per litre; Welch's t-test and Cohen's d. Protocol: `experiment/PROTOCOL.md`; tools: `experiment/collect.py`, `experiment/analyze.py`.

## 4 Results

### 4.1 Water use at equal yield
| Crop, method | Su-Tech water, m³/ha | Equal-yield calendar, m³/ha | Su-Tech saving (95% CI) | Worst–best season | Seasons with less water | Plain calendar (same mean dose): Su-Tech vs calendar | Stress days: Su-Tech / plain calendar | Relative yield: Su-Tech / plain calendar |
|---|---|---|---|---|---|---|---|---|
| cotton, drip | 11 321 | 15 536 | **27%** (25–29%) | 20–36% | 25/25 | +5.1% | 0 / 65 | 1.00 / 0.88 |
| cotton, furrow | 19 751 | 30 199 | **34%** (32–36%) | 26–44% | 25/25 | +1.7% | 0 / 60 | 1.00 / 0.87 |
| maize, drip | 9 039 | 11 009 | **18%** (16–19%) | 11–29% | 25/25 | +5.4% | 0 / 39 | 1.00 / 0.89 |
| maize, furrow | 15 781 | 21 848 | **27%** (26–29%) | 19–39% | 25/25 | +2.1% | 0 / 38 | 1.00 / 0.86 |

Su-Tech used less water than the equal-yield calendar in every one of the 25 location-seasons for each combination (the bootstrap intervals in Table 1 treat the 25 location-seasons as independent and are therefore optimistic; the worst-to-best range is given beside them), while that calendar still reached a mean relative yield of 99.3–99.6% (Su-Tech: 100% by construction of the model, no stress days). Compared with a *plain* calendar of the same mean dose Su-Tech used somewhat more water (+2 to +9% across the tested intervals) but kept the crop unstressed; the plain calendars suffered 38–65 stress days and a relative yield of 0.84–0.90. Deep percolation per season was 2–24 mm for Su-Tech, 127–150 mm for the plain calendars and 234–522 mm for the equal-yield calendars, whose larger doses are what costs the extra water (per-run values in `research/results/simulation_runs.csv`).

![Water use at equal yield](../docs/img/water_by_strategy.svg)

### 4.2 Robustness to input errors (cotton)
| Scenario | Stress days (drip) | Water vs equal-yield calendar (drip) | Stress days (furrow) | Water vs equal-yield calendar (furrow) |
|---|---|---|---|---|
| Perfect forecast | 0.0 | -26.9% | 0.0 | -34.3% |
| Random ET₀ error, σ = 10% | 0.0 | -26.6% | 0.0 | -34.1% |
| Random ET₀ error, σ = 30% | 0.0 | -23.5% | 0.0 | -31.0% |
| Rain never forecast | 0.0 | -25.5% | 0.0 | -32.1% |
| Wrong soil entered (sand for loam) | 0.0 | -26.9% | 0.0 | -34.3% |
| ET₀ biased +20% | 0.0 | -12.1% | 0.0 | -20.5% |
| ET₀ biased −20% | 72.8 | -41.7% | 70.8 | -48.0% |
| ET₀ biased −20% + 3-level soil check every 7 d | 0.0 | -19.3% | 0.0 | -20.7% |
| ET₀ biased −20% + 3-level soil check every 3 d | 0.0 | -14.7% | 0.0 | -8.8% |

Random errors had little effect. A systematic ET₀ underestimate accumulates in the app's own balance, because the app cannot see the soil, and caused 71–73 stress days. A weekly three-level soil check eliminated them while keeping 19–21% saving; checking every 3 days saved less (9–15%) because coarse repeated judgements trigger extra irrigations.

![Stress days under input errors](../docs/img/sensitivity_stress.svg)

### 4.3 Validation
ET₀ implementation vs FAO-56 Example 18: see 3.2 and `VALIDATION.md`. A comparison with CROPWAT 8.0 on identical inputs is **not yet done [AUTHOR]**. Python and JavaScript engines agree on 675 reference scenarios (relative tolerance 10⁻⁸).

### 4.4 Bench experiment
**[AUTHOR: results go here after the experiment — model accuracy (RMSE/MAE/bias), water per pot by group with Welch test and effect size, dry mass, and a photograph of the stand. Do not fill this section with simulated numbers.]**

## 5 Discussion

The saving of 18–34% is the price of safety that a fixed calendar must pay: because it cannot react to rain or heat waves, it needs a margin large enough for the worst season. Su-Tech's advantage is therefore timing, not a more efficient irrigation system, and it is largest where the baseline efficiency is lowest (furrow). The weak point is equally clear: a decision tool that integrates its own estimate drifts when inputs are biased, so a cheap, infrequent observation of the real soil is essential. This is built into the bot as a button, and the study supports a weekly rhythm.

## 6 Limitations
* Model against model, on reanalysis weather for regional centres, not farm stations; no field measurement of yield or water yet.
* Yield is estimated from the FAO-33 relation, not measured.
* One soil in the main analysis; fixed planting date; no salinity or capillary rise; crop and soil parameters are not locally calibrated.
* Su-Tech has perfect weather knowledge in the main comparison; forecast error is treated only in the sensitivity analysis.
* Drip-mode Su-Tech irrigates almost daily (94–129 events per season), which in practice needs automation.
* The soil check is simulated with the same three levels as the app; real farmer judgement may be noisier.
* Effective rainfall uses a simple project rule.

## 7 Conclusion
On five years of real weather in five regions, FAO-56 daily scheduling with a stress coefficient saved 18–34% water at equal yield and avoided crop stress, and a weekly farmer soil check made it robust to systematic forecast bias. These are model results and not yet measurements. In simple terms: a daily water-balance calculation can save a lot of water compared with a fixed schedule if the schedule must also protect the crop, but it needs an occasional look at the real soil to stay correct. The next steps are my bench experiment with weighed pots and, in 2027, a trial on a real field. **[Replace this paragraph with the final conclusion after the experiment.]**

## Author contribution and use of AI
I came up with the project and built the physical test stand myself: an Arduino Uno with a relay and a small pump, a soil-moisture sensor, a water-level sensor and a temperature and humidity sensor. I am now adding a scale for the pots, and in the coming weeks I will run the experiment on it; the results will go into Section 4.4 and are not in this draft yet.

I wrote the software with the help of an AI coding assistant (Claude Code). It wrote most of the code, the simulation and the first version of this text. I chose what to build and which questions to ask, and I am learning to explain each formula and each assumption myself; where my own understanding or measurements are still missing, this draft says so. The weather data come from NASA POWER, and the formulas come from the FAO-56 and FAO-33 papers listed below.

## Data and code availability
All code, cached weather, result tables and figures: `github.com/osmanri/sutech-core` (`research/`, `experiment/`, `bot/`). Reproduce with `python -m research.simulate && python -m research.sensitivity`.

## References
* [R1] Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration — Guidelines for computing crop water requirements.* FAO Irrigation and Drainage Paper 56. FAO, Rome.
* [R2] FAO. CROPWAT. https://www.fao.org/land-water/databases-and-software/cropwat
* [R3] Vozehova et al., evaluation of CROPWAT 8.0 (year/journal to be verified): https://www.czasopisma.pan.pl//Content/109794/PDF/Vozehova%20et%20al.pdf
* [R4] University of Georgia Extension, SI CropFit app: https://precisionagirrigation.extension.uga.edu/2025/06/setting-up-and-using-the-si-cropfit-app-for-irrigation-scheduling/
* [R5] "A smartphone APP for weather-based irrigation scheduling using artificial neural networks" (IrriMobile), Pesquisa Agropecuária Brasileira: https://apct.sede.embrapa.br/pab/article/view/26726
* [R6] "Managing Scarce Water Resources in Irrigated Agri-Food Systems of Central Asia: Two Case Studies": https://agris.fao.org/search/fr/records/64746b6bbf943c8c79805f10 (the 32–35% figure should be checked in the full text)
* [R7] Reports on 2026 irrigation limits for southern Kazakhstan: https://timesca.com/kazakhstan-sets-irrigation-limits-for-southern-regions-and-reduces-water-intensive-crops/
* [R8] NASA Langley Research Center POWER Project, funded through the NASA Earth Science/Applied Science Program. https://power.larc.nasa.gov/
* [R9] Open-Meteo. https://open-meteo.com/
* [R10] Doorenbos, J., Kassam, A.H. (1979). *Yield response to water.* FAO Irrigation and Drainage Paper 33. FAO, Rome.
