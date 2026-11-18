# Original Mini App design restored

The owner requested the entire design from before unslop, while retaining useful animation improvements from the other installed skills.

## Scope

- Restored `css/app.css` and `css/glass.css` byte for byte from frontend commit `ed6237f`, the version immediately preceding the unslop redesign.
- Restored the original HTML structure and all localized interface copy. The only markup differences from that version are asset cache versions and an additional motion stylesheet.
- Removed the neutral `workspace.css` layer. Original green glass surfaces, gradients, typography, section geometry, crop emoji, ticker and hero text are back.
- Kept calculation fixes, greenhouse applicability, Telegram integration, automatic themes, Windows-compatible tests and stationary submission under reduced motion.

## Motion-only improvements

`css/motion.css` contains no palette, type, radius or layout redesign. A FLIP animation moves the original selected gel surface over 180ms using transforms, including changes between labels of different widths. Rapid selection changes begin from the current visual position. Font/viewport resizes snap to the correct measured target. Reduced motion cancels active selection/help animations and immediately preserves the selected state.

User-opened help uses a short 180ms reveal; legacy CSS entrances are suppressed on those same children so the old and new animations cannot overlap. Button hit areas stay still. The old decorative button sheen loop is removed while its static glossy surface stays. Existing ambient design is preserved and paused when the page is hidden; the ticker also pauses when offscreen or hovered.

## Verification

- Original CSS buffers, original markup (apart from asset/motion tags) and original localization block match `ed6237f`.
- 15 frontend functional tests pass, including the greenhouse regression.
- Browser restoration checks pass in 30 viewport/theme/language combinations, including 320px and landscape, without horizontal overflow.
- Existing theme/validation, both-theme selection and button-motion browser checks pass. Rapid repeated selections finish aligned; live reduced-motion changes stop movement. Valid submission is tested through a local Telegram stub.
- Mini App build/secret-pattern scan and three shared-engine/demo/crop parity checks pass.

Impeccable's full-scene motion capture could not reach rest because the requested original design contains pre-existing ambient loops. A separate deterministic browser fixture pauses those baseline loops only during capture, then records actual interaction animations at 0–180ms plus boundary/settled frames. Its normal and reduced-motion evidence is scoped to header selection and does not certify ambient-animation or hardware performance. Production styles are not altered to satisfy the recorder.

Independent motion review approved this scoped header interaction with no material fixes. Independent code review verified both themes, single help animation, rapid open/close cancellation, live reduced-motion cancellation and twelve interrupted selection changes without jumps. No remaining actionable findings.

The previous unslop audit is retained as a historical record and is explicitly superseded for the current visual design.
