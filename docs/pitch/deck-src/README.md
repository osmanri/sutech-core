# Presentation sources

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
Icons: Phosphor Icons (MIT). Fonts: Manrope and Inter (SIL OFL).
