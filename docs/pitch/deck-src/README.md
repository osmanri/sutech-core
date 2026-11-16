# Presentation sources

The Su-Tech pitch deck (PowerPoint, native objects) is generated, not drawn by hand.

| File | Role |
|---|---|
| `deck7.js` | the deck: slide structure of the mentor's deck, "big photo, then text" layouts, speaker notes (pptxgenjs) |
| `animate.py` | adds real PowerPoint motion: Morph transitions and staggered entrance animations |
| `assets6.js` | renders line icons (Phosphor, MIT), glow blobs and the base background |
| `process2.py`, `build_all.py` | turn free Wikimedia Commons photos into dark, tinted slide backgrounds |

Build (needs `pptxgenjs`, `playwright`, Pillow, the fonts Manrope + Inter):

```bash
OUT=static.pptx node deck7.js <path-to-pptx-skill>
python animate.py static.pptx Su-Tech.pptx
```

Photo credits (all from Wikimedia Commons): see the last slide. The logo and the bot screenshots are the author's own.
Icons: Phosphor Icons (MIT). Fonts: Manrope and Inter (SIL OFL).
