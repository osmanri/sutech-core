"""Photo treatments for the 'big photo, then text' slides.
full(): full-bleed 16:9, slightly softened, tinted to the logo greens, darker on the text side.
half(): a half-slide photo (sharper, closer to natural colour) whose inner edge fades into the slide background.
"""
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

BASE = (0, 42, 32)          # #002A20, the slide background


def _cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def _tint(im, keep=0.35, shadow='#00110d', light='#4f9a5f'):
    g = ImageOps.colorize(ImageOps.grayscale(ImageEnhance.Contrast(im).enhance(1.08)), black=shadow, white=light)
    return Image.blend(g, ImageEnhance.Color(im).enhance(0.8), keep)


def _ramp(w, h, a0, a1, horizontal=True):
    """alpha ramp a0..a1 (0-255) across the image."""
    g = Image.linear_gradient('L')
    g = g.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT) if horizontal else g
    g = g.resize((w, h))
    return g.point(lambda v: round(a0 + (a1 - a0) * v / 255))


def full(src, dst, blur=2.0, left=215, right=90, keep=0.35, flip=False, top=0, bottom=0):
    im = _cover(Image.open(src).convert('RGB'), 1920, 1080)
    if flip:
        im = ImageOps.mirror(im)
    im = _tint(im, keep).filter(ImageFilter.GaussianBlur(blur))
    dark = Image.new('RGB', im.size, BASE)
    mask = _ramp(*im.size, left, right)      # dark overlay strength: strong on the left, lighter right
    if top or bottom:                        # plus a vertical ramp: light at the top, dark under the text
        from PIL import ImageChops
        v = _ramp(im.width, im.height, top, bottom, horizontal=False)
        mask = ImageChops.lighter(mask, v)
    im = Image.composite(dark, im, mask)
    im.save(dst, quality=88)


def half(src, dst, w=1000, h=1080, side='right', keep=0.55, fade=360, dim=60):
    im = _cover(Image.open(src).convert('RGB'), w, h)
    im = _tint(im, keep, light='#5aa36a')
    im = Image.composite(Image.new('RGB', im.size, BASE), im, Image.new('L', im.size, dim))
    # fade the inner edge into the background colour
    ramp = Image.linear_gradient('L').rotate(90, expand=True).resize((fade, h))   # 255 (left) -> 0 (right)
    mask = Image.new('L', im.size, 0)
    if side == 'right':
        mask.paste(ramp, (0, 0))
    else:
        mask.paste(ImageOps.mirror(ramp), (w - fade, 0))
    im = Image.composite(Image.new('RGB', im.size, BASE), im, mask)
    im.save(dst, quality=88)


def split(src_l, src_r, dst):
    """two full-height halves side by side (dry | green) for the 'weak spot' slide."""
    L, R = Image.new('RGB', (1920, 1080)), None
    a = _tint(_cover(Image.open(src_l).convert('RGB'), 960, 1080), 0.6, light='#8aa060')
    b = _tint(_cover(Image.open(src_r).convert('RGB'), 960, 1080), 0.7, light='#6ab87a')
    a = Image.composite(Image.new('RGB', a.size, BASE), a, Image.new('L', a.size, 160))
    b = Image.composite(Image.new('RGB', b.size, BASE), b, Image.new('L', b.size, 165))
    L.paste(a, (0, 0)); L.paste(b, (960, 0))
    L.save(dst, quality=88)
