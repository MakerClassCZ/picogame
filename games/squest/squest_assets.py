# AUTO-GENERATED from TinyJoypad TinySQuest sprite bank (GPLv3, Daniel C).
# Tiny 1-bit vertical-byte source; build(pg, name) unpacks to a colored picogame
# PAL8 atlas ON DEVICE at 1x (native size). The game sets each sprite's `.scale`
# to render at the on-screen size, so the bitmaps stay small (~12 KB less heap than
# pre-baking a 2.5x atlas) and the Sprite's scale-aware AABB keeps collisions identical.
# Regenerate: python tools/tinyjoypad_extract.py <bank.h> --scale 1 --module squest_assets.py
import array

SCALE = 1        # bake at native 1x; on-screen size comes from Sprite.scale (see the game)
FISH_COLORS = [(0, 252, 0), (248, 252, 0), (248, 0, 248), (248, 130, 20)]  # green / yellow / magenta / orange (4 distinct hues)

# name -> (packed_hex, src_w, pages, frames, (r, g, b))
_SPR = {
    'font': ('3e223e00003e00003a2a2e00222a3e000e083e002e2a3a003e2a3a00023a06003e2a3e002e2a3e00', 4, 1, 10, (255, 255, 255)),
    'sub': ('1828283f3f3e3e383838383838303068681828283f3f3e3e383838383838303058581828283f3f3e3e38383838383830303030686830303838383838383e3e3f3f282818585830303838383838383e3e3f3f282818303030303838383838383e3e3f3f282818', 17, 1, 6, (0, 172, 248)),
    'enemy_sub': ('0c141f1e1c1c18340c141f1e1c1c182c0c141f1e1c1c181834181c1c1e1f140c2c181c1c1e1f140c18181c1c1e1f140c', 8, 1, 6, (192, 192, 192)),
    'torp': ('010101', 3, 1, 1, (255, 255, 255)),
    'torp2': ('040501', 3, 1, 1, (255, 255, 255)),
    'fish': ('040a060f0e040a11040a060f0e040a12040a0e0f06040a09110a040e0f060a04120a040e0f060a04090a04060f0e0a04', 8, 1, 6, (248, 252, 0)),
    'diver': ('10140a18122020411014081a10212020101408183250110141202012180a1410202021101a0814100111503218081410', 8, 1, 6, (0, 200, 248)),
}


def build(pg, name, rgb=None, scale=None, palette=None):
    """Unpack + upscale one sprite to a picogame PAL8 Bitmap.

    Pass a shared `palette` array to reuse one pixel buffer across recolors
    (mutate palette[1] later) instead of building a fresh copy per color."""
    hx, w, pages, frames, col = _SPR[name]
    if rgb is not None:
        col = rgb
    sc = SCALE if scale is None else scale
    packed = bytes.fromhex(hx)
    h = pages * 8
    nw = round(w * sc)
    nh = round(h * sc)
    stride = nw * frames
    data = bytearray(stride * nh)
    for f in range(frames):
        fb = f * (w * pages)
        for y in range(nh):
            sy = int(y / sc)
            if sy >= h:
                sy = h - 1
            page = sy >> 3
            mask = 1 << (sy & 7)
            row = y * stride + f * nw
            prow = fb + page * w
            for x in range(nw):
                sx = int(x / sc)
                if sx >= w:
                    sx = w - 1
                if packed[prow + sx] & mask:
                    data[row + x] = 1
    pal = palette if palette is not None else array.array('H', [pg.rgb565(0, 0, 0), pg.rgb565(*col)])
    return pg.Bitmap(data, nw, nh, format=pg.PAL8, palette=pal,
                     frames=frames, stride=stride, transparent=0)


def fish(pg, level, scale=None):
    """Fish recolored for the level (cycles the original Col_Fish palette)."""
    return build(pg, 'fish', FISH_COLORS[level % 4], scale)
