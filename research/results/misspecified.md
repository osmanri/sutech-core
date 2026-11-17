# Su-Tech when the model is wrong about the real crop and soil (loam)

Real crop Kc and soil plant-available water differ from the bot's parameters. Calendar = the strongest equal-yield calendar searched with hindsight on the REAL field. 5 regions x 5 seasons per row.

| scenario | strategy | water vs calendar (mean / worst season) | seasons with less water | stress days (Su-Tech / calendar) | relative yield (Su-Tech mean / worst) |
|---|---|---|---|---|---|
| model_correct | sutech_no_check | -21.9 % / -8.8 % | 100/100 | 0.0 / 8.2 | 1.000 / 1.000 |
| model_correct | sutech_weekly_check | -17.5 % / +1.0 % | 99/100 | 0.0 / 8.2 | 1.000 / 1.000 |
| crop_uses_15pct_less | sutech_no_check | -3.3 % / +14.0 % | 64/100 | 0.0 / 9.4 | 1.000 / 1.000 |
| crop_uses_15pct_less | sutech_weekly_check | -4.0 % / +13.3 % | 68/100 | 0.0 / 9.4 | 1.000 / 1.000 |
| crop_uses_15pct_more | sutech_no_check | -34.6 % / -23.9 % | 100/100 | 28.3 / 7.5 | 0.982 / 0.947 |
| crop_uses_15pct_more | sutech_weekly_check | -17.2 % / -2.8 % | 100/100 | 0.1 / 7.5 | 1.000 / 1.000 |
| soil_holds_20pct_less | sutech_no_check | -26.3 % / -14.3 % | 100/100 | 0.3 / 7.1 | 1.000 / 0.999 |
| soil_holds_20pct_less | sutech_weekly_check | -22.6 % / -9.2 % | 100/100 | 0.2 / 7.1 | 1.000 / 0.999 |
| soil_holds_20pct_more | sutech_no_check | -17.2 % / -2.5 % | 100/100 | 0.0 / 9.6 | 1.000 / 1.000 |
| soil_holds_20pct_more | sutech_weekly_check | -12.3 % / +10.1 % | 91/100 | 0.0 / 9.6 | 1.000 / 1.000 |
| worst_dry_crop_more_soil_less | sutech_no_check | -37.9 % / -27.8 % | 100/100 | 44.8 / 6.9 | 0.961 / 0.919 |
| worst_dry_crop_more_soil_less | sutech_weekly_check | -22.8 % / -11.7 % | 100/100 | 0.4 / 6.9 | 1.000 / 0.997 |
| worst_wet_crop_less_soil_more | sutech_no_check | +3.5 % / +23.3 % | 34/100 | 0.0 / 10.6 | 1.000 / 1.000 |
| worst_wet_crop_less_soil_more | sutech_weekly_check | +2.8 % / +27.7 % | 41/100 | 0.0 / 10.6 | 1.000 / 1.000 |
