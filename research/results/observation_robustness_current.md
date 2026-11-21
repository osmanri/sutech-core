# Moisture observation and delivery robustness (current)

Current open-field configuration (fao56.10, drip wetted fraction 0.35).

Model-vs-model on cached NASA POWER weather, 5 locations × 5 years (2021–2025), cotton and maize, loam, 1 May planting. See [the scenario protocol](../OBSERVATION_ROBUSTNESS.md).

## Failure regions

Each cell shows **Y / W** among 50 paired cases for that method and setting. Y counts modeled yield below 98%. W counts cases reaching 98% where Su-Tech used at least as much water as the strongest fixed calendar. Counts describe the tested cases. Locations, years, scenarios and repeated checks share weather and trajectories.

### ET₀ bias +0%

| Missing checks | Reported category | drip, 0 d | drip, 1 d | drip, 3 d | drip, 5 d | furrow, 0 d | furrow, 1 d | furrow, 3 d | furrow, 5 d |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| none | one wetter | 0 / 0 | 0 / 0 | 12 / 0 | 47 / 0 | 0 / 0 | 0 / 0 | 23 / 0 | 48 / 0 |
| none | correct | 0 / 0 | 0 / 0 | 0 / 0 | 4 / 0 | 0 / 1 | 0 / 0 | 0 / 0 | 2 / 0 |
| none | one drier | 0 / 50 | 0 / 50 | 0 / 49 | 0 / 31 | 0 / 50 | 0 / 50 | 0 / 50 | 0 / 32 |
| alternate | one wetter | 0 / 0 | 0 / 0 | 10 / 0 | 42 / 0 | 0 / 0 | 1 / 0 | 15 / 0 | 44 / 0 |
| alternate | correct | 0 / 0 | 0 / 0 | 0 / 0 | 6 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 2 / 0 |
| alternate | one drier | 0 / 50 | 0 / 47 | 0 / 27 | 0 / 10 | 0 / 49 | 0 / 48 | 0 / 35 | 0 / 17 |
| four-week | one wetter | 0 / 0 | 0 / 0 | 7 / 0 | 41 / 0 | 0 / 0 | 0 / 0 | 19 / 0 | 45 / 0 |
| four-week | correct | 0 / 0 | 0 / 0 | 0 / 0 | 3 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 2 / 0 |
| four-week | one drier | 0 / 50 | 0 / 50 | 0 / 47 | 0 / 27 | 0 / 50 | 0 / 50 | 0 / 44 | 0 / 33 |
| all | — | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

### ET₀ bias -20%

| Missing checks | Reported category | drip, 0 d | drip, 1 d | drip, 3 d | drip, 5 d | furrow, 0 d | furrow, 1 d | furrow, 3 d | furrow, 5 d |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| none | one wetter | 0 / 0 | 0 / 0 | 24 / 0 | 49 / 0 | 0 / 0 | 7 / 0 | 43 / 0 | 50 / 0 |
| none | correct | 0 / 0 | 0 / 0 | 0 / 0 | 8 / 0 | 0 / 3 | 0 / 0 | 0 / 0 | 9 / 0 |
| none | one drier | 0 / 50 | 0 / 50 | 0 / 48 | 0 / 28 | 0 / 50 | 0 / 50 | 0 / 49 | 0 / 30 |
| alternate | one wetter | 0 / 0 | 0 / 0 | 28 / 0 | 49 / 0 | 5 / 0 | 18 / 0 | 38 / 0 | 49 / 0 |
| alternate | correct | 0 / 0 | 0 / 0 | 0 / 0 | 12 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 6 / 0 |
| alternate | one drier | 0 / 43 | 0 / 37 | 0 / 17 | 0 / 3 | 0 / 50 | 0 / 46 | 0 / 31 | 0 / 12 |
| four-week | one wetter | 8 / 0 | 15 / 0 | 38 / 0 | 50 / 0 | 19 / 0 | 24 / 0 | 42 / 0 | 49 / 0 |
| four-week | correct | 0 / 0 | 0 / 0 | 1 / 0 | 19 / 0 | 0 / 0 | 0 / 0 | 2 / 0 | 16 / 0 |
| four-week | one drier | 0 / 50 | 0 / 50 | 0 / 44 | 0 / 17 | 0 / 50 | 0 / 50 | 0 / 41 | 0 / 31 |
| all | — | 38 / 0 | 42 / 0 | 48 / 0 | 50 / 0 | 50 / 0 | 50 / 0 | 50 / 0 | 50 / 0 |

## Reference cases with immediate delivery

| ET₀ bias | Method | Checks | Mean water difference vs calendar | Minimum modeled yield | Max stress days |
|---|---|---|---:|---:|---:|
| +0% | drip | none | -25.3% | 100.00% | 0 |
| +0% | drip | weekly, correct category | -26.6% | 100.00% | 0 |
| +0% | furrow | none | -23.7% | 100.00% | 0 |
| +0% | furrow | weekly, correct category | -13.5% | 100.00% | 0 |
| -20% | drip | none | -40.5% | 92.16% | 88 |
| -20% | drip | weekly, correct category | -17.9% | 100.00% | 0 |
| -20% | furrow | none | -39.5% | 89.00% | 89 |
| -20% | furrow | weekly, correct category | -11.9% | 100.00% | 0 |

## Worst tested cases

Water differences are paired with each case's calendar. The largest water difference uses cases reaching the 98% yield threshold. Ties show the first case in run order.

| ET₀ bias | Method | Lowest modeled yield (case) | Most stress days (case) | Largest water difference at target yield (case) |
|---|---|---|---|---|
| +0% | drip | 76.11% (Turkestan 2021, corn, one wetter, missing none, delay 5 d) | 58 (Turkestan 2021, corn, one wetter, missing none, delay 5 d) | +112.1% (Taldykorgan 2022, cotton, one drier, missing none, delay 0 d) |
| +0% | furrow | 66.11% (Turkestan 2025, corn, one wetter, missing none, delay 5 d) | 87 (Turkestan 2025, corn, one wetter, missing none, delay 5 d) | +111.2% (Taldykorgan 2021, cotton, one drier, missing none, delay 0 d) |
| -20% | drip | 68.48% (Turkestan 2025, corn, one wetter, missing alternate, delay 5 d) | 95 (Kyzylorda 2025, cotton, no checks, missing all, delay 3 d) | +95.8% (Taldykorgan 2022, cotton, one drier, missing none, delay 0 d) |
| -20% | furrow | 64.83% (Turkestan 2025, corn, one wetter, missing none, delay 5 d) | 95 (Kyzylorda 2021, cotton, no checks, missing all, delay 3 d) | +124.6% (Taldykorgan 2022, cotton, one drier, missing none, delay 0 d) |
