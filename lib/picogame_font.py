# picogame text helper: render strings into picogame.Bitmap using ANY
# fontio font (e.g. the bundled terminalio.FONT) - no extra assets, no reflash.
#
# The builtin font is a monospace tile sheet. get_glyph(cp) returns a Glyph
# object whose `.bitmap` is the (shared) 1-bit sheet and `.tile_index` locates
# the glyph; get_bounding_box() is the cell size.
#
# Rendering composes the glyphs into an 8-bit paletted Bitmap (index 0 = bg,
# index 1 = fg). With an opaque bg, redrawing a Label fully overwrites the old
# text, so score/HUD updates need no separate clear.

import array


def render_text(pg, font, text, fg, bg=None):
    """Render `text` (any fontio font) -> the tuple `(bmp, w, h)` (a PAL8 picogame.Bitmap + its
    pixel size). Use as `bmp, w, h = render_text(...)`. fg/bg are wire colors from pg.rgb565();
    bg=None makes the background transparent (index 0). (See render_text_pal to also get the palette.)"""
    bmp, w, h, _data, _pal = _render_into(pg, font, text, fg, bg, None)
    return bmp, w, h


def render_text_pal(pg, font, text, fg, bg=None):
    """Like render_text, but ALSO returns the PAL8 palette as an array('H'):
    (bmp, w, h, palette). Keep the palette ref and mutate palette[1] (the fg)
    for a colour shimmer without rebuilding the bitmap - the C Bitmap reads the
    same buffer, so the change shows up immediately (Bitmap.palette is not a
    Python attribute on device, so mutate THIS array, not bmp.palette)."""
    bmp, w, h, _data, palette = _render_into(pg, font, text, fg, bg, None)
    return bmp, w, h, palette


# Per-glyph rasterized masks, cached so the slow per-pixel fontio read happens ONCE per glyph.
# Key: (id(font), codepoint) -> list of fh row `bytes` (each fw long, value 1=fg / 0=bg). Composing a
# string then memcpys whole rows into the buffer (data[d:d+fw] = rows[gy]) -- no per-pixel Python and
# no per-render allocation. (Cache RAM ~ unique-chars * fw * fh, one-off: ~a few KB for a HUD charset.)
_MASKS = {}


def _glyph_rows(font, cp, fw, fh):
    """Return one glyph as fh row-`bytes`, rasterizing it ONCE (the slow per-pixel read) then caching."""
    key = (id(font), cp)
    rows = _MASKS.get(key)
    if rows is not None:
        return rows
    g = font.get_glyph(cp)
    if g is None:                            # blank cell: one shared empty row, repeated
        rows = [bytes(fw)] * fh
    else:
        sheet = g.bitmap                     # shared 1-bit tile sheet
        tiles_per_row = sheet.width // fw
        ti = g.tile_index
        tx = (ti % tiles_per_row) * fw
        ty = (ti // tiles_per_row) * fh
        rows = []
        for gy in range(fh):
            r = bytearray(fw)
            sy = ty + gy
            for gx in range(fw):
                if sheet[tx + gx, sy]:
                    r[gx] = 1
            rows.append(bytes(r))            # immutable -> safe to share across renders
    _MASKS[key] = rows
    return rows


def _render_into(pg, font, text, fg, bg, buf):
    """Core renderer. Composes `text` into `buf` (reused when large enough, else a fresh bytearray) by
    memcpy-ing cached per-glyph row masks -- the per-pixel rasterization runs once per glyph (see
    _glyph_rows), not per render, and the compose allocates nothing. Every pixel in [0,w*h) is written
    (fg=1 / bg=0), so a reused buffer needs no clear. Returns (bmp, w, h, data, palette); a widget keeps
    `data` and passes it back as `buf` next time, so a re-render allocates no new bytearray."""
    fw, fh = font.get_bounding_box()[:2]
    n = len(text)
    w = fw * max(1, n)
    h = fh
    size = w * h
    data = buf if (buf is not None and len(buf) >= size) else bytearray(size)
    for i in range(n):
        ox = i * fw
        rows = _glyph_rows(font, ord(text[i]), fw, fh)
        for gy in range(fh):
            d = gy * w + ox
            data[d:d + fw] = rows[gy]        # whole-row memcpy: no per-pixel Python, no alloc
    if bg is None:
        palette = array.array("H", [pg.rgb565(0, 0, 0), fg])
        transparent = 0
    else:
        palette = array.array("H", [bg, fg])
        transparent = None
    bmp = pg.Bitmap(data, w, h, format=pg.PAL8, palette=palette,
                    frames=1, stride=w, transparent=transparent)
    return bmp, w, h, data, palette


class Label:
    """A positioned text label drawn immediately to the display (good for HUD).
    Re-renders only when the text changes; draw() repaints just its rectangle."""

    def __init__(self, pg, font, x, y, fg, bg):
        self.pg = pg
        self.font = font
        self.x = x
        self.y = y
        self.fg = fg
        self.bg = bg  # opaque background so updates overwrite cleanly
        self.text = None
        self.sprite = None
        self._slist = [None]   # reused 1-element list for draw() (no per-frame alloc)
        self._buf = None       # reused glyph buffer (no per-render bytearray alloc)
        self.w = 0
        self.h = 0

    def move(self, x, y):
        """Reposition the label (forces a re-render at the new spot on next set/draw)."""
        self.x = x
        self.y = y
        self.text = None

    def set(self, text):
        text = str(text)
        if text == self.text:
            return False
        self.text = text
        bmp, w, h, self._buf, _ = _render_into(self.pg, self.font, text, self.fg, self.bg, self._buf)
        self.w, self.h = w, h
        self.sprite = self.pg.Sprite(bmp, self.x, self.y)
        self._slist[0] = self.sprite
        return True

    def draw(self, display, buffer):
        if self.sprite is None:
            return
        self.pg.render(display, self._slist, buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)
