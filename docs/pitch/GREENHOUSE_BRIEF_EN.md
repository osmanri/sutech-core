# Su-Tech | Greenhouse irrigation pilot

Su-Tech estimates daily irrigation for crops grown in soil. A grower can review
the crop, soil and weather inputs, record actual watering, and correct the
balance with a soil moisture observation. The goal of a pilot is to find out
whether the recommendation is useful in a specific greenhouse.

Show three browser examples at the meeting. Start with a tomato crop in an
unheated soil greenhouse. The estimate uses a project assumption of 70% of
outdoor reference evapotranspiration and excludes outdoor rain. In a heated
soil greenhouse the model accepts measured indoor ET₀. The demo uses an
illustrative 2.6 mm/day to show the input. For coconut coir, rockwool and other
substrates, the app withholds the recommendation. Ask the agronomist how they
use drainage and conductivity to manage that system.

The published water savings of 15–28% came from historical model scenarios for
cotton and maize under specific baseline and yield assumptions. The crop
calendar, soil parameters and threshold rules need local assessment. A useful
pilot records actual water, soil conditions, drainage as applicable, and crop
outcomes before comparing practices. The project has no greenhouse trial
results to report. Inspect [the evidence register](../EVIDENCE.md) for version
and comparison details.

The scenario below uses fictional inputs for one season in a 100 m² greenhouse.
Water is priced at 50 KZT/m³, electricity at 30 KZT/kWh and labour at 1,500 KZT/h.
Scheduling is assumed to use 18 m³ less water and one hour less labour. These
are scenario inputs. Pump electricity is volume divided by measured flow, then
multiplied by measured input power. Actual rates and operating points should
come from the grower.

| Seasonal cost or input | Calendar, existing pump | Su-Tech schedule, same pump | Su-Tech schedule, new pump |
|---|---:|---:|---:|
| Applied water, m³ | 120 | 102 | 102 |
| Pump input power, kW at 2 m³/h | 0.40 | 0.40 | 0.30 |
| Pump electricity, kWh | 24.0 | 20.4 | 15.3 |
| Recorded labour, h | 12 | 11 | 11 |
| Water cost, KZT | 6,000 | 5,100 | 5,100 |
| Electricity cost, KZT | 720 | 612 | 459 |
| Labour cost, KZT | 18,000 | 16,500 | 16,500 |
| Service cost, KZT | 0 | 1,200 | 1,200 |
| Allocated equipment cost, KZT | 0 | 0 | 500 |
| Total, KZT | **24,720** | **23,412** | **23,759** |

At the assumed volumes and labour hours, the same pump scheduling scenario
saves 1,308 KZT after service costs. The pump swap alone saves 153 KZT in
electricity but costs 500 KZT per season, increasing total cost by 347 KZT.
For the scheduling comparison the break-even service cost is 2,508 KZT. It
falls to 1,008 KZT when both schedules use the same labour hours. No revenue,
yield improvement or adoption cost is assumed. Reproduce with
`python -m research.economics`.

Questions for the agronomist: what crop and rooting medium are used, how is
watering decided today, what soil or drainage readings are available, and
can gross water and pump energy be metered separately? Agree on the comparison
and stopping conditions before collecting measurements.

Primary references:

- Allen, Pereira, Raes and Smith, *Crop Evapotranspiration*. Root zone balance,
  crop coefficients, and water stress. [FAO Irrigation and Drainage Paper 56](https://www.fao.org/4/x0490e/x0490e00.htm)
- Steduto, Hsiao, Fereres and Raes (eds.), *Crop Yield Response to Water*.
  Chapter 2 gives the original FAO yield response equation used in modeling.
  [FAO Irrigation and Drainage Paper 66, Chapter 2](https://www.fao.org/4/i2800e/i2800e02.pdf)
- Hydraulic Institute, Europump and US Department of Energy, *Pump Life Cycle
  Costs*. Flow, input power, duty and life cycle cost assumptions.
  [Executive summary](https://www.energy.gov/sites/prod/files/2014/05/f16/pumplcc_1001.pdf)

Su-Tech is a student project. The code was written with an AI assistant.
