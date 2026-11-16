"""Canva-safe assets: transparency baked into PNG alpha, charts drawn as images."""
import glob, os
from PIL import Image, ImageDraw

def fade(src, dst, keep):
    im = Image.open(src).convert('RGBA')
    a = im.getchannel('A').point(lambda v: int(v * keep))
    im.putalpha(a); im.save(dst)

for f in glob.glob('img/d-*-lime.png'):
    n = os.path.basename(f)[2:-9]
    fade(f, f'c/d-{n}-big.png', 0.20)    # 80% transparent
    fade(f, f'c/d-{n}-small.png', 0.32)  # 68% transparent
fade('m/dots.png', 'c/dots.png', 0.38)

def ring(dst, parts, hole, S=1200):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    start = -90
    for frac, col in parts:
        end = start + 360 * frac
        d.pieslice([8, 8, S - 8, S - 8], start, end, fill=col, outline=(0, 42, 32, 255), width=10)
        start = end
    if hole:
        r = S * hole / 2; c = S / 2
        d.ellipse([c - r, c - r, c + r, c + r], fill=(0, 0, 0, 0))
    im.resize((600, 600), Image.LANCZOS).save(dst)

ring('c/donut-72.png', [(0.72, (129, 202, 42, 255)), (0.28, (46, 95, 75, 255))], 0.64)
ring('c/pie-50.png', [(0.5, (229, 57, 53, 255)), (0.5, (46, 95, 75, 255))], 0)
print('ok', len(glob.glob('c/*')))
