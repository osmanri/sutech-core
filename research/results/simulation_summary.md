# Retrospective simulation: Su-Tech vs fixed calendar

25 location-seasons per crop/method (Turkestan, Shymkent, Kyzylorda, Taraz, Taldykorgan; 2021–2025), loam, same irrigation method for both strategies.
Model-vs-model on reanalysis weather — see LIMITATIONS in research/simulate.py.

| crop | method | strategy | water m³/ha (sd) | events | stress days | rel. yield | deep perc. mm | Su-Tech vs this | Su-Tech used less in |
|---|---|---|---|---|---|---|---|---|---|
| corn | drip | calendar_3d | 8796 (1143) | 41 | 39.1 | 0.895 | 150 | 2.8 % | 7/25 |
| corn | drip | calendar_5d | 8581 (1115) | 24 | 39.4 | 0.886 | 150 | 5.4 % | 5/25 |
| corn | drip | calendar_5d_safe | 11009 (1667) | 24 | 4.6 | 0.995 | 234 | -17.6 % | 25/25 |
| corn | drip | calendar_7d | 8510 (1106) | 17 | 39.2 | 0.875 | 149 | 6.3 % | 5/25 |
| corn | drip | sutech | 9039 (1210) | 94 | 0.0 | 1.000 | 11 | — | — |
| corn | furrow | calendar_10d | 15446 (2007) | 12 | 38.2 | 0.858 | 149 | 2.1 % | 8/25 |
| corn | furrow | calendar_10d_safe | 21848 (3472) | 12 | 4.3 | 0.993 | 310 | -27.5 % | 25/25 |
| corn | furrow | calendar_14d | 14416 (1873) | 8 | 38.0 | 0.835 | 148 | 9.4 % | 3/25 |
| corn | furrow | calendar_7d | 15317 (1990) | 17 | 39.2 | 0.875 | 149 | 3.0 % | 8/25 |
| corn | furrow | sutech | 15781 (2292) | 18 | 0.0 | 1.000 | 2 | — | — |
| cotton | drip | calendar_3d | 10904 (1590) | 64 | 65.3 | 0.886 | 134 | 4.0 % | 8/25 |
| cotton | drip | calendar_5d | 10790 (1573) | 38 | 64.6 | 0.882 | 132 | 5.1 % | 7/25 |
| cotton | drip | calendar_5d_safe | 15536 (2364) | 38 | 6.0 | 0.995 | 410 | -26.9 % | 25/25 |
| cotton | drip | calendar_7d | 10733 (1565) | 27 | 63.8 | 0.877 | 132 | 5.7 % | 7/25 |
| cotton | drip | sutech | 11321 (1622) | 129 | 0.0 | 1.000 | 24 | — | — |
| cotton | furrow | calendar_10d | 19422 (2832) | 19 | 60.1 | 0.869 | 143 | 1.7 % | 10/25 |
| cotton | furrow | calendar_10d_safe | 30199 (5244) | 19 | 5.1 | 0.996 | 522 | -34.3 % | 25/25 |
| cotton | furrow | calendar_14d | 18604 (2713) | 13 | 56.9 | 0.859 | 127 | 6.1 % | 7/25 |
| cotton | furrow | calendar_7d | 19320 (2817) | 27 | 63.8 | 0.877 | 132 | 2.2 % | 9/25 |
| cotton | furrow | sutech | 19751 (3201) | 23 | 0.0 | 1.000 | 5 | — | — |

Water-balance closure check: max |error| = 2.33e-12 mm over all 500 runs.
