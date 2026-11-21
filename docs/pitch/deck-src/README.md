# Presentation sources

The current greenhouse pilot deck is built with `pptxgenjs@3.12.0` using
`node greenhouse-en.cjs ../files/Su-Tech-Greenhouse-EN.pptx`. Export that deck
to PDF in PowerPoint so the two files contain the same six slides. Its cost
scenario and evidence references are in `../GREENHOUSE_BRIEF_EN.md`.

The original competition presentation below is kept for historical reference.

The Su-Tech pitch deck (PowerPoint, native objects) is generated, not drawn by hand.

| File | Role |
|---|---|
| `deck7.js` | the deck: slide structure of the mentor's deck, "big photo, then text" layouts, speaker notes (pptxgenjs) |
| `animate.py` | adds real PowerPoint motion: Morph transitions and staggered entrance animations |
| `assets6.js` | renders line icons (Phosphor, MIT), glow blobs and the base background |
| `deck-canva.js`, `prep_canva.py` | Canva edition (`files/Su-Tech-Canva.pptx`): same slides, only objects Canva imports cleanly (explicit hex colours and fonts, no masters, charts, tables or transparency; charts and fades baked into images) |
| `process2.py`, `build_all.py` | turn free Wikimedia Commons photos into dark, tinted slide backgrounds |

Build (needs `pptxgenjs`, `playwright`, Pillow, the fonts Manrope + Inter):

```bash
OUT=static.pptx node deck7.js <path-to-pptx-skill>
python animate.py static.pptx Su-Tech.pptx
# Canva edition (run in the folder with m/ and img/ assets):
python prep_canva.py && node deck-canva.js
```

In Canva: Create a design → Import file → `Su-Tech-Canva.pptx`. PowerPoint animations are not imported; add them in Canva (Animate).

Photo credits (all from Wikimedia Commons): see the last slide. The logo and the bot screenshots are the author's own.
Icons: Phosphor Icons (MIT). The blue double-drop icon next to the title of slide 1 (`icons/drops-duo.png`) is from Flaticon (free licence: keep the credit on slides 1 and 16; [add the author's name shown on the icon's Flaticon page, icon id 315339]). Fonts: Manrope and Inter (SIL OFL).
