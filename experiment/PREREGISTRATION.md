# Pre-registration of the pot experiment (draft to be registered on OSF before the first weighing)

Register this file **before** collecting any data on [OSF](https://osf.io). A registration cannot be
edited afterwards, so fill the bracketed fields and re-read `experiment/PROTOCOL.md` first. Nothing in brackets is decided yet.

**Title.** Does irrigation advised by Su-Tech use less water than a fixed-schedule irrigation at the same plant growth?
(pot experiment, [crop: lettuce or radish], [school, city], [start date])

**Hypotheses (directional, stated before data).**
- H1. Water given per pot, summed over the whole experiment, is lower in the Su-Tech group than in the control group.
- H2. Mean dry shoot mass in the Su-Tech population exceeds 90% of the mean in the control population.
- H3 (secondary). The daily evapotranspiration of a pot computed by the bot (FAO-56 balance with the pot's parameters) correlates
  with that pot's drainage-adjusted daily loss. Report Pearson r and the mean absolute error in mm/day, along with RMSE and bias.

**Design.** 12 identical pots, [crop and variety], same substrate and light. Random assignment by a written draw
(6 Su-Tech, 6 control), the draw record is kept. Control: a fixed volume every [N] days (N and the volume chosen and justified
before the start as an ordinary habit). Duration [4–6] weeks. Weights from one load cell (HX711), calibrated weekly with a known mass.

**Measurements.** Each day weigh the pot before irrigation, without its drainage collector. After watering, weigh it again after [fixed immediate drainage collection period] and measure the collected drainage. Gross water applied is the increase in pot mass plus immediate drainage. Measure delayed drainage separately before the next weighing. At the end, weigh dry shoots after drying at 60–70 °C to constant mass. Weather input and procedure for matching the model's ET to the weighed interval [specify before collection]. Follow `experiment/PROTOCOL.md` for the measurements and data format.

**Primary outcomes.** (1) Total water per pot, ml. (2) Dry shoot mass, g. **Secondary.** Water per gram of dry mass; H3.

**Analysis (fixed in advance).** Use the pot as the independent unit for the water and dry-mass comparisons. Report group means and standard deviations, the Su-Tech minus control difference with a two-sided 95% Welch–Satterthwaite interval, and the two-sided Welch test at α = 0.05. H1 is supported when the water interval is entirely below zero and the whole-experiment irrigation records are complete. Report Cohen's d using the pooled sample standard deviation and an approximate 95% normal interval. Interpret both the intervals and the small sample size when stating the result. [Welch–Satterthwaite interval](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/diffmean.htm) · [Variance approximation for Cohen's d, equation 2](https://journals.sagepub.com/doi/10.1002/cl2.70056)

For H2 estimate `mean(Su-Tech) − 0.90 × mean(control)` in grams. Apply the Welch standard error and degrees of freedom to Su-Tech observations and control observations multiplied by 0.90. The one-sided 95% lower confidence bound must be strictly above zero to demonstrate non-inferiority. This includes uncertainty in the estimated control mean. Report the number of missing outcome measurements and the reasons. If data are insufficient to calculate a bound, report it as unavailable. A lower bound that reaches zero or below leaves non-inferiority inconclusive.

For H3 pair Su-Tech predictions with drainage-adjusted daily ET rates for the same pot and weighing interval. Use consecutive sample rows that end on adjacent local dates and are 12–36 hours apart. Normalize the observed loss by elapsed hours. Disclose missing observations, excluded intervals, and unpaired predictions. Treat the accuracy metrics as descriptive because observations within a pot are repeated. When weights and water are available, retain and disclose negative computed losses. Preserve missing measurements as missing and keep the raw journal unchanged. Before interpreting the totals, check the assignment record and planned start and end dates against the log, including any pots or watering events that were never written to the file.

**Stopping rule.** The experiment stops at the planned date. It is not stopped or extended because of how the numbers look.

**What would change the plan.** Only a hardware failure or the death of more than two pots of one group for a reason unrelated
to irrigation; such an event and the decision are written down with the date.

**Known limitations (to be in the paper).** Indoor conditions, one crop, small sample, a single load cell, the bot's pot
parameters are the project's own, authored with an AI assistant for the code but not for the measurements.
