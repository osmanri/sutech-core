# Su-Tech Mini App: audit and direction

The user requested unslop, then Impeccable, Taste Skill and Motion React, to remove generic AI styling and improve the website with restrained animation. Direction presented in chat; user instructed to follow the skill.

## Audit

Local `frontend/index.html`, mobile viewport 390 × 844, plus the rendering source:

| Finding | Location | Treatment |
| --- | --- | --- |
| Glass, inner highlights, colored shadows on every surface | `css/glass.css`, panels and controls | Opaque neutral surfaces, quiet hairlines |
| Drifting radial background blobs | `css/glass.css`, body pseudo-elements | Plain neutral canvas |
| Gradient text, heavy headline, vague outcome claim | hero, `js/app.js` translations | Specific irrigation title, solid text, weight 500 |
| Decorative marquee and repeated claims | signal strip, ticker copy | Remove decorative ticker |
| Emoji crop illustrations and region labels | crop cards, `js/app.js` | Text crop choices, existing line icons elsewhere |
| Sheen, floating panels and scrolling 3D effects | `css/app.css`, `css/glass.css` | Motion only for user-triggered feedback |
| Tiny labels and wide tracking | settings, hero caption, status | 12–16px type, sentence case |
| Several CSS redesign layers compete | app/theme/glass stylesheet cascade | Replace glass with one explicit workspace presentation layer |

## Direction

- Product: irrigation planning from weather and field parameters, for growers.
- Character: calm, precise, practical.
- World: field maps and an agronomist's notebook; neutral chrome, original green brand and logo.
- Moments: the actual satellite map and the irrigation calculation, without invented data or decorative images.
- Signature: a thin green marker at the active navigation step.

## Approaches

1. Small cleanup preserves most glass styling but leaves competing effects throughout the screen.
2. Focused unslop pass preserves product, section order and brand while simplifying all interface surfaces. Selected direction.
3. Full replatforming or marketing redesign would expand scope without improving the calculation workflow.

## Constraints and verification

Keep FAO calculations and shared engine byte-identical, Telegram integration, all crops, form validation and RU/KZ/EN. Keep automatic light/dark themes. Use the current plain HTML/CSS/JS stack. Motion React is installed as a skill; use applicable motion principles without introducing React solely for animations.

Use 4px spacing steps, 8–10px controls and 16px panels; neutral light/dark ramps, three text roles, one brand accent. Keep visible keyboard focus and readable selected/disabled/error states. Animate transform/opacity, with reduced-motion support and no decorative loops.

Check 375px, 390px, landscape and desktop, three languages and both themes, input selection, validation, help disclosure and calculator behavior. Baseline: map/weather/theme tests pass; demo test has Windows absolute-import incompatibility and results test assumes LF line endings.

Audit uses [unslop](https://github.com/heydamir/unslop) by [Damir Sokolovsky](https://x.com/heydamir), CC BY 4.0.
