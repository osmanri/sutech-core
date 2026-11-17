# Su-Tech when the model is wrong about the real crop and soil (loam)

Real crop Kc and soil plant-available water differ from the bot's parameters. Calendar = the strongest equal-yield calendar searched with hindsight on the REAL field. 5 regions x 5 seasons per row.

| scenario | strategy | water vs calendar (mean / worst season) | seasons with less water | stress days (Su-Tech / calendar) | relative yield (Su-Tech mean / worst) |
|---|---|---|---|---|---|
| model_correct | sutech_no_check | -24.5 % / -11.9 % | 100/100 | 0.0 / 7.9 | 1.000 / 1.000 |
| model_correct | sutech_weekly_check | -20.0 % / +1.0 % | 99/100 | 0.0 / 7.9 | 1.000 / 1.000 |
| crop_uses_15pct_less | sutech_no_check | -6.4 % / +9.0 % | 73/100 | 0.0 / 9.0 | 1.000 / 1.000 |
| crop_uses_15pct_less | sutech_weekly_check | -7.2 % / +10.9 % | 79/100 | 0.0 / 9.0 | 1.000 / 1.000 |
| crop_uses_15pct_more | sutech_no_check | -36.8 % / -26.1 % | 100/100 | 24.8 / 7.2 | 0.984 / 0.947 |
| crop_uses_15pct_more | sutech_weekly_check | -19.8 % / -2.8 % | 100/100 | 0.1 / 7.2 | 1.000 / 1.000 |
| soil_holds_20pct_less | sutech_no_check | -28.8 % / -16.8 % | 100/100 | 0.3 / 6.9 | 1.000 / 0.999 |
| soil_holds_20pct_less | sutech_weekly_check | -24.9 % / -9.2 % | 100/100 | 0.2 / 6.9 | 1.000 / 0.999 |
| soil_holds_20pct_more | sutech_no_check | -20.0 % / -6.8 % | 100/100 | 0.0 / 9.2 | 1.000 / 1.000 |
| soil_holds_20pct_more | sutech_weekly_check | -15.0 % / +10.1 % | 91/100 | 0.0 / 9.2 | 1.000 / 1.000 |
| worst_dry_crop_more_soil_less | sutech_no_check | -40.1 % / -30.0 % | 100/100 | 40.9 / 6.7 | 0.964 / 0.919 |
| worst_dry_crop_more_soil_less | sutech_weekly_check | -25.3 % / -14.3 % | 100/100 | 0.4 / 6.7 | 1.000 / 0.997 |
| worst_wet_crop_less_soil_more | sutech_no_check | +0.3 % / +17.7 % | 48/100 | 0.0 / 10.6 | 1.000 / 1.000 |
| worst_wet_crop_less_soil_more | sutech_weekly_check | -0.5 % / +27.7 % | 55/100 | 0.0 / 10.6 | 1.000 / 1.000 |
