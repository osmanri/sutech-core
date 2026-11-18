# Su-Tech Mini App Unslop Implementation Plan

> **For agentic workers:** Execute inline in this session, following the requested unslop passes.

**Goal:** Improve the existing field setup screen and add restrained, accessible motion.

**Architecture:** Keep HTML/JS behavior and shared calculations. Replace the glass stylesheet with a single workspace presentation layer, revise localized interface text, and retain useful selection feedback.

**Tech Stack:** Plain HTML, CSS, JavaScript; existing Leaflet and Telegram integration.

**Spec:** `docs/superpowers/specs/2026-11-17-mini-app-unslop-design.md`

## Global constraints

Preserve logo, product, section order, engine, RU/KZ/EN and automatic themes. No React migration or invented data. Follow unslop's nine passes in order.

## Review focus

Narrow translated labels; dark selected-state contrast; fixed-header clearance; keyboard focus on clipped controls; reduced-motion and interrupted interactions.

## Task: refine the field workspace

- [x] Install and read requested skills before product edits.
- [x] Spacing: align page/panel/control spacing to 4px steps.
- [x] Color: replace glass with neutral surfaces and one green accent.
- [x] Icons: remove decorative emoji, standardize existing line icons.
- [x] Copy: replace vague hero and shouting statuses in all languages.
- [x] Type: readable labels, weights 400/500/600, tabular figures.
- [x] Layout: preserve sections; desktop map beside settings, mobile in reading order.
- [x] Details: control radii, selected state, focus and error states.
- [x] Visuals: actual map is the rich moment; remove decorative filler.
- [x] Motion: brief feedback, subtle disclosure, transform/opacity only, reduced-motion support.
- [x] Run existing functional tests, update obsolete visual expectations, check responsive browser behavior and inspect final screenshots.
- [x] Update changelog and record validation and delivery status.

Validation and independent review are recorded in `docs/audits/UNSLOP_2026-11-18.md`. Frontend implementation is committed as `1046ca0`; publication follows the existing working-branch pull request and Mini App deployment workflow.
