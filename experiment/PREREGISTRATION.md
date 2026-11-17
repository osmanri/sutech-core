# Pre-registration of the pot experiment (draft to be registered on OSF before the first weighing)

Register this file as it is, **before** collecting any data, on https://osf.io (Preregistration). A registration cannot be
edited afterwards, so fill the bracketed fields and re-read `experiment/PROTOCOL.md` first. Nothing in brackets is decided yet.

**Title.** Does irrigation advised by Su-Tech use less water than a fixed-schedule irrigation at the same plant growth?
(pot experiment, [crop: lettuce or radish], [school, city], [start date])

**Hypotheses (directional, stated before data).**
- H1. Water given per pot, summed over the whole experiment, is lower in the Su-Tech group than in the control group.
- H2. Dry shoot mass at the end is not lower in the Su-Tech group by more than 10 % of the control mean (non-inferiority margin).
- H3 (secondary). The daily evapotranspiration of a pot computed by the bot (FAO-56 balance with the pot's parameters) correlates
  with the daily weight loss of that pot: report Pearson r and the mean absolute error in mm.

**Design.** 12 identical pots, [crop and variety], same substrate and light. Random assignment by a written draw
(6 Su-Tech, 6 control), the draw record is kept. Control: a fixed volume every [N] days (N and the volume chosen and justified
before the start as an ordinary habit). Duration [4–6] weeks. Weights from one load cell (HX711), calibrated weekly with a known mass.

**Measurements.** Daily: pot weight before and after watering (water given = difference). End: dry shoot mass after drying at
60–70 °C to constant mass. Weather: [sensor or Open-Meteo ET0].

**Primary outcomes.** (1) Total water per pot, ml. (2) Dry shoot mass, g. **Secondary.** Water per gram of dry mass; H3.

**Analysis (fixed in advance).** Welch's t-test, two-sided, alpha = 0.05; effect size as Cohen's d with its 95 % confidence
interval; H2 by comparing the lower confidence bound of the difference in means with -10 % of the control mean. Report the numbers
with their spread and say plainly when the sample (n = 6 per group) is too small to conclude. No outlier is removed after the
fact; a missed day stays missing; the raw log is never edited by hand.

**Stopping rule.** The experiment stops at the planned date. It is not stopped or extended because of how the numbers look.

**What would change the plan.** Only a hardware failure or the death of more than two pots of one group for a reason unrelated
to irrigation; such an event and the decision are written down with the date.

**Known limitations (to be in the paper).** Indoor conditions, one crop, small sample, a single load cell, the bot's pot
parameters are the project's own, authored with an AI assistant for the code but not for the measurements.
