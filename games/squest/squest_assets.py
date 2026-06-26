# AUTO-GENERATED from TinyJoypad TinySQuest sprite bank (GPLv3, Daniel C).
# Tiny 1-bit vertical-byte source; build(pg, name) unpacks + upscales
# (nearest-neighbor x SCALE) to a colored picogame PAL8 atlas ON DEVICE.
# Regenerate: python tools/tinyjoypad_extract.py <bank.h> --scale 2.5 --module squest_assets.py
import array

SCALE = 2.5
FISH_COLORS = [(0, 252, 0), (248, 252, 0), (248, 0, 248), (248, 130, 20)]  # green / yellow / magenta / orange (4 distinct hues)

# name -> (packed_hex, src_w, pages, frames, (r, g, b))
_SPR = {
    'font': ('3e223e00003e00003a2a2e00222a3e000e083e002e2a3a003e2a3a00023a06003e2a3e002e2a3e00', 4, 1, 10, (255, 255, 255)),
    'sub': ('1828283f3f3e3e383838383838303068681828283f3f3e3e383838383838303058581828283f3f3e3e38383838383830303030686830303838383838383e3e3f3f282818585830303838383838383e3e3f3f282818303030303838383838383e3e3f3f282818', 17, 1, 6, (0, 172, 248)),
    'sub_blink': ('1828283f3f3e3e383838383838303068681828283f3f3e3e383838383838303068680000000000000000000000000000000000686830303838383838383e3e3f3f282818686830303838383838383e3e3f3f2828180000000000000000000000000000000000', 17, 1, 6, (0, 172, 248)),
    'sub_boom': ('000000000008081414140808000000000000000022220808001400080822220000008282829210100044444400101092828282000000000010102828281010000000000000000022220808001400080822220000008282829210100044444400101092828282', 17, 1, 6, (248, 160, 0)),
    'enemy_sub': ('0c141f1e1c1c18340c141f1e1c1c182c0c141f1e1c1c181834181c1c1e1f140c2c181c1c1e1f140c18181c1c1e1f140c', 8, 1, 6, (192, 192, 192)),
    'torp': ('010101', 3, 1, 1, (255, 255, 255)),
    'torp2': ('040501', 3, 1, 1, (255, 255, 255)),
    'fish': ('040a060f0e040a11040a060f0e040a12040a0e0f06040a09110a040e0f060a04120a040e0f060a04090a04060f0e0a04', 8, 1, 6, (248, 252, 0)),
    'diver': ('10140a18122020411014081a10212020101408183250110141202012180a1410202021101a0814100111503218081410', 8, 1, 6, (0, 200, 248)),
    'hud_diver': ('ffffffdfdf5fbfcfefd7df', 11, 1, 1, (0, 200, 248)),
    'hud_live': ('ff83c7c7c3c1c1c7e7', 9, 1, 1, (248, 80, 0)),
    'logo': ('0f030101ffff01010f0010f3f3000030f0e03030f0e0001070f0d000d03010c0c0c000c09e39393173f7e400c0e0301010e0f00010f0f0000090f0f000c0e07050507060006050d0d0900010f8fc101000000203030302000000020303020002030300020303021818110f030000000000000001010102020201000000010302010f0f0800010303020103030200010302020301000302020201000001030201', 80, 2, 1, (0, 172, 248)),
    'start': ('fe0101912949910109f90901f12929f101f92929d10109f90901010101f10949d101f12929f101f9112111f901f92909010101fe07080808090908080809080809080809080908080908080908080808080809090908090808090809080808090809090908080807', 52, 2, 1, (0, 252, 0)),
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
