# Self-review of the draft (rubric: `scientific-thinking-scholar-evaluation`)

Scored honestly, 1–5. A judge from a water or agronomy background will see the same gaps.

| Dimension | Score | Why | Fix (who) |
|---|---|---|---|
| Problem and research question | 4 | Clear, three concrete questions, scope stated | Add 2–3 sentences on why small farms specifically need this (author, from interviews) |
| Literature and context | **2** | Only a 3-search scoping pass; novelty claim is unproven | Systematic search (Scholar/Scopus), 15–25 sources, then rewrite §2 (author + Claude) |
| Methodology | 3 | Reproducible and explicit, but model-vs-model; calendar tuned with hindsight (stated); one soil | Add a second soil and a planting-date sweep (Claude, 1 day); the pot experiment is the real fix (author) |
| Data and evidence | **2** | No measured data yet; reanalysis weather for city coordinates; Ky from FAO-33, not measured | Pot experiment (§4.4); compare NASA ET₀ with one weather-station series (Claude + author) |
| Analysis | 4 | Paired comparison, closure check, sensitivity with seeds; no confidence intervals yet | Add bootstrap CIs to Table 1 (Claude, 2 h) |
| Conclusions vs evidence | 3 | Wording is careful; relies on model assumptions | Keep "model estimate" in every claim until §4.4 exists |
| Reproducibility | 5 | Cached weather, scripts, tests, fixed seeds | — |
| Clarity | 3 | Dense; needs the author's own voice and a plain-language abstract | Author rewrites §1, §5, §7 |
| Ethics / authorship | 4 | AI use disclosed; contribution paragraph left to the author | Author writes it |

**Highest-value fixes in order:** (1) run the pot experiment, (2) systematic literature search, (3) bootstrap confidence intervals, (4) CROPWAT comparison, (5) second soil.
