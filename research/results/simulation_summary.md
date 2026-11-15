# Retrospective simulation: Su-Tech vs fixed calendar

25 location-seasons per crop/method (Turkestan, Shymkent, Kyzylorda, Taraz, Taldykorgan; 2021–2025), loam, same irrigation method for both strategies.
Model-vs-model on reanalysis weather — see LIMITATIONS in research/simulate.py.

| crop | method | strategy | water m³/ha (sd) | events | stress days | rel. yield | deep perc. mm | Su-Tech vs this (95% CI) | worst / best pair | Su-Tech used less in |
|---|---|---|---|---|---|---|---|---|---|---|
| corn | drip | calendar_3d | 8796 (1143) | 41 | 39.1 | 0.895 | 150 | 2.8 % [0.9; 4.7] | 10.9 / -6.5 | 7/25 |
| corn | drip | calendar_5d | 8581 (1115) | 24 | 39.4 | 0.886 | 150 | 5.4 % [3.4; 7.3] | 13.7 / -4.1 | 5/25 |
| corn | drip | calendar_5d_safe | 11009 (1667) | 24 | 4.6 | 0.995 | 234 | -17.6 % [-19.4; -15.8] | -10.6 / -29.0 | 25/25 |
| corn | drip | calendar_7d | 8510 (1106) | 17 | 39.2 | 0.875 | 149 | 6.3 % [4.3; 8.2] | 14.6 / -3.3 | 5/25 |
| corn | drip | sutech | 9039 (1210) | 94 | 0.0 | 1.000 | 11 | — | — | — |
| corn | furrow | calendar_10d | 15446 (2007) | 12 | 38.2 | 0.858 | 149 | 2.1 % [-0.2; 4.4] | 12.3 / -8.8 | 8/25 |
| corn | furrow | calendar_10d_safe | 21848 (3472) | 12 | 4.3 | 0.993 | 310 | -27.5 % [-29.4; -25.6] | -19.3 / -39.1 | 25/25 |
| corn | furrow | calendar_14d | 14416 (1873) | 8 | 38.0 | 0.835 | 148 | 9.4 % [6.9; 11.9] | 20.3 / -2.3 | 3/25 |
| corn | furrow | calendar_7d | 15317 (1990) | 17 | 39.2 | 0.875 | 149 | 3.0 % [0.6; 5.3] | 13.2 / -8.0 | 8/25 |
| corn | furrow | sutech | 15781 (2292) | 18 | 0.0 | 1.000 | 2 | — | — | — |
| cotton | drip | calendar_3d | 10904 (1590) | 64 | 65.3 | 0.886 | 134 | 4.0 % [1.8; 6.1] | 12.0 / -6.3 | 8/25 |
| cotton | drip | calendar_5d | 10790 (1573) | 38 | 64.6 | 0.882 | 132 | 5.1 % [2.9; 7.2] | 13.1 / -5.3 | 7/25 |
| cotton | drip | calendar_5d_safe | 15536 (2364) | 38 | 6.0 | 0.995 | 410 | -26.9 % [-28.7; -25.2] | -19.9 / -35.9 | 25/25 |
| cotton | drip | calendar_7d | 10733 (1565) | 27 | 63.8 | 0.877 | 132 | 5.7 % [3.4; 7.8] | 13.7 / -4.8 | 7/25 |
| cotton | drip | sutech | 11321 (1622) | 129 | 0.0 | 1.000 | 24 | — | — | — |
| cotton | furrow | calendar_10d | 19422 (2832) | 19 | 60.1 | 0.869 | 143 | 1.7 % [-1.0; 4.2] | 11.2 / -10.0 | 10/25 |
| cotton | furrow | calendar_10d_safe | 30199 (5244) | 19 | 5.1 | 0.996 | 522 | -34.3 % [-36.3; -32.3] | -25.8 / -44.0 | 25/25 |
| cotton | furrow | calendar_14d | 18604 (2713) | 13 | 56.9 | 0.859 | 127 | 6.1 % [3.3; 8.8] | 16.1 / -6.1 | 7/25 |
| cotton | furrow | calendar_7d | 19320 (2817) | 27 | 63.8 | 0.877 | 132 | 2.2 % [-0.5; 4.8] | 11.8 / -9.6 | 9/25 |
| cotton | furrow | sutech | 19751 (3201) | 23 | 0.0 | 1.000 | 5 | — | — | — |

Water-balance closure check: max |error| = 2.33e-12 mm over all 500 runs.
