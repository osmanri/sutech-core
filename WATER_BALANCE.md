# Su-Tech: daily water balance v2

The active WebApp handler requires `balance_version: 2`. Cached older WebApps
receive a localized request to reopen the app; the old moisture-threshold
algorithm is not used by the live route.

## Inputs and model

- FC/PWP, crop Kc/p/root ranges and method thresholds/efficiencies follow the
  supplied project specification in `bot/water_balance.py`.
- Stage calendars are editable. Wheat uses a spring example, cotton and the
  annual vegetable/maize crops use illustrative FAO Table 11 schedules.
  Alfalfa's 10/20/20/10-day first-cycle schedule is a project starting assumption,
  not a calibrated local recommendation. Subsequent cuts require current custom
  crop parameters; cycles do not silently restart.
- Kc is constant initially and in mid-season, linear during development/late
  season. Zr grows linearly from the specified minimum on day 0 to maximum at
  the end of development. Calendar dates beyond the season are rejected.
- The user may supply current Kc, p and root depth for “other”. Coefficients sent
  by the old frontend never overwrite global crop constants.
- Effective rain is 0 below 5 mm, otherwise 75%. These and the irrigation
  thresholds are project policies, not universal FAO prescriptions.
- The farmer selects an observable soil condition. The server maps recently
  irrigated/rain to 0, normal moisture to 0.5 × RAW and dry soil to RAW. The
  client cannot submit a millimetre value.
- Deficit = starting deficit + ET0 × Kc − effective rain, clamped to [0, TAW]. Values
  above TAW are flagged. Strict comparison `deficit > RAW` has priority over
  `deficit >= min(method threshold, RAW)`; equality with RAW triggers irrigation
  but is not classified critical.
- Net volume = deficit × 10 × hectares when irrigation is indicated, otherwise
  0. Gross volume divides net by efficiency. No rounding before decisions.
- Pump inputs are power in kW (form default 22) and productivity in m³/h
  (default 60). Electricity cost = gross m³ / productivity × power × tariff.
  Both systems cover the same current deficit; the traditional baseline is
  `current deficit × 10 × hectares × (1.35 / 0.5)`. Reports show the two costs
  and their difference in tenge and kWh, rounded to two decimal places only
  at display time. Missing pump inputs produce an explicit “not calculated”.
- A recommendation never confirms irrigation. Persistent multi-field state and
  an owner-checked irrigation reset are implemented in `bot/field_state.py`.

## Weather and special cases

Open-Meteo `daily.et0_fao_evapotranspiration` and `daily.precipitation_sum`, mm,
`timezone=auto`, `forecast_days=1`. The report explicitly describes an end-of-day
forecast, not measured current depletion or already fallen rain. Returned units,
date, finite/nonnegative values are validated; API errors yield no fabricated
recommendation. Do not substitute surface moisture for root-zone depletion.

Greenhouse ET0 must be supplied for the actual microclimate; external rain is
excluded. Outdoor weather remains fetched for provenance, but cannot substitute
for greenhouse ET0. Salinity is retained as a warning that leaching water needs
separate assessment, without the former arbitrary +15%. Flooded rice bypasses
the generic balance and requests water-layer/percolation/drainage data.

Reports are saved in history; the existing owner-checked explanation snapshots
preserve each report's values and survive process restart while SQLite persists.
An ephemeral hosting filesystem can still erase SQLite on redeploy.

## Sources

- [FAO-56 chapter 8: TAW, RAW and root-zone balance](https://www.fao.org/4/x0490e/x0490e0e.htm)
- [FAO-56 chapter 6: illustrative stage lengths and Kc interpolation](https://www.fao.org/4/x0490e/x0490e0b.htm)
- [Open-Meteo daily variables](https://open-meteo.com/en/docs)

## Validation and release

Run `python -m unittest test_water_balance test_balance_integration
test_compact_report test_report_explanation test_bot_platform test_premium_emoji`
and `node frontend/test_field_map.cjs`.

Deploy the backend and the nested frontend repository together. On the previous
frontend version the new backend responds with “reopen the app” rather than
silently assuming soil, age or moisture condition. Test a newly generated
Telegram report and its explanation after deployment.
