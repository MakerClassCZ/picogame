# picogame_palette - cheap colour effects on PAL8 art by mutating the PALETTE, not the pixels
# (the classic Game Boy trick). Animated water/lava (cycle), recolour a shared bitmap (swap), and
# a smooth brightness/colour fade (fade) - all for a handful of array writes, ZERO extra art.
#
# IMPORTANT: the dirty-rect renderer reads the palette at blit time but does NOT notice a palette
# change on its own. After any change here, call `sprite.touch()` on the sprites using that bitmap
# (or `scene.invalidate()` / repaint the Tilemap region) so the change actually shows. Cost = a
# repaint of the affected sprites/tiles that frame, so cycle a small BAND (a strip of water), not
# the whole screen.
#
# Palette entries are wire-order RGB565 ints (as `rgb565()` / a Bitmap's `array('H')` palette).
#
#   import picogame_palette as pal
#   base = pal.snapshot(water_bmp.palette)          # save the original once
#   ...each frame:
#       pal.cycle(water_bmp.palette, 8, 11)         # flow indices 8..11
#       for s in water_sprites: s.touch()
#   ...fade out over ~20 frames:
#       pal.fade(spr_bmp.palette, base, t)          # t 0..1 toward black; spr.touch()

import array


def snapshot(palette):
    """A copy (array 'H') of a palette - save the ORIGINAL before fading/cycling so you can
    restore it or fade relative to it."""
    return array.array("H", palette)


def restore(palette, base):
    for i in range(len(base)):
        palette[i] = base[i]


def _reverse(p, a, b):
    while a < b:
        p[a], p[b] = p[b], p[a]
        a += 1
        b -= 1


def cycle(palette, lo, hi, step=1):
    """Rotate palette entries [lo..hi] inclusive by `step` (wraps). Reserve a run of indices for
    'flowing' colours (water/lava/portal/waterfall), paint art with them, and they animate.
    In-place (no per-call allocation) - safe to call every frame."""
    n = hi - lo + 1
    if n <= 1:
        return
    step %= n
    if step == 0:
        return
    # right-rotate [lo..hi] by `step` via three in-place reversals (zero allocation)
    _reverse(palette, lo, hi)
    _reverse(palette, lo, lo + step - 1)
    _reverse(palette, lo + step, hi)


def swap(dst_palette, src_palette):
    """Copy one palette over another - GBC-style recolour: keep one PAL8 bitmap, hand it a
    different palette for player 1/2, normal/frightened, team colours. Cheaper than a 2nd bitmap."""
    for i in range(min(len(dst_palette), len(src_palette))):
        dst_palette[i] = src_palette[i]


def _unwire(c):
    n = ((c >> 8) | (c << 8)) & 0xFFFF             # wire -> native RGB565
    return (n >> 11) & 0x1F, (n >> 5) & 0x3F, n & 0x1F


def _wire(r, g, b):
    n = ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)
    return ((n >> 8) | (n << 8)) & 0xFFFF


def fade(palette, base, t, target=0, skip=None):
    """Lerp every entry of `palette` from the saved `base` toward the `target` wire colour by
    `t` (0.0 = base .. 1.0 = target). target=0 (black) = fade out; a white target = fade to white.
    `skip` = an index left untouched (e.g. a transparent index). Call `touch()` after."""
    tr, tg, tb = _unwire(target)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    for i in range(len(base)):
        if i == skip:
            continue
        c = base[i]                                   # inline un/rewire: no per-entry tuple/call alloc
        n = ((c >> 8) | (c << 8)) & 0xFFFF
        r = (n >> 11) & 0x1F
        g = (n >> 5) & 0x3F
        b = n & 0x1F
        r = int(r + (tr - r) * t)
        g = int(g + (tg - g) * t)
        b = int(b + (tb - b) * t)
        m = ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)
        palette[i] = ((m >> 8) | (m << 8)) & 0xFFFF
