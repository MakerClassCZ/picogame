# picogame text helper: render strings into a picogame.Bitmap from a FIXED-GRID TILED
# fontio font (e.g. the bundled terminalio.FONT) - no extra assets, no reflash.
#
# SCOPE: this handles a monospace tile-sheet font - every glyph is a `get_bounding_box()`
# cell on a shared 1-bit sheet, located by `get_glyph(cp).tile_index`. It does NOT honor
# per-glyph width/height/offset/advance metrics, so a variable-width / adaptive fontio
# font would be mis-spaced. Use a fixed-grid tiled font (terminalio.FONT qualifies).
#
# Rendering composes the glyphs into an 8-bit paletted Bitmap (index 0 = bg, index 1 = fg).
# With an opaque bg, redrawing a Label overwrites the old text (Label.draw also clears the
# previous footprint, so shrinking / moving / clearing leaves no stale pixels).

import array

_EMPTY = []   # shared sprite list for a hidden Label.draw() (just fills bg, composites nothing)


def render_text(pg, font, text, fg, bg=None):
    """Render `text` (fixed-grid tiled fontio font) -> the tuple `(bmp, w, h)` (a PAL8
    picogame.Bitmap + its pixel size). Use as `bmp, w, h = render_text(...)`. fg/bg are wire
    colors from pg.rgb565(); bg=None makes the background transparent (index 0). (See
    render_text_pal to also get the palette.)"""
    bmp, w, h, _data, _pal = _render_into(pg, font, text, fg, bg, None)
    return bmp, w, h


def render_text_pal(pg, font, text, fg, bg=None):
    """Like render_text, but ALSO returns the PAL8 palette as an array('H'):
    (bmp, w, h, palette). Keep the palette ref and mutate palette[1] (the fg) for a colour
    shimmer without rebuilding the bitmap. With IMMEDIATE render()/Label.draw() the change
    shows up on the next draw. In a RETAINED Scene an in-place palette change isn't
    auto-detected - call sprite.touch() / scene.invalidate() after mutating it (same as
    picogame_palette). Mutate THIS array, not bmp.palette (not a Python attribute on device)."""
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
    Re-renders only when the text changes; draw() repaints its rectangle AND clears the
    previous footprint, so shrinking, moving, or set("") leaves no stale pixels."""

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
        self._drawn = None     # (x0,y0,x1,y1) last painted, so the next draw erases it

    def move(self, x, y):
        """Reposition the label. Keeps the current sprite in sync (so a draw() before the next
        set() moves it, and clears the old spot) and forces a re-render at the new x/y on set()."""
        self.x = x
        self.y = y
        self.text = None
        if self.sprite is not None:
            self.sprite.move(x, y)

    def set(self, text):
        text = str(text)
        if text == self.text:
            return False
        self.text = text
        if text == "":                     # empty = hidden: don't leave stale glyph pixels behind
            self.sprite = None
            self._slist[0] = None
            self.w = self.h = 0
            return True
        bmp, w, h, self._buf, _ = _render_into(self.pg, self.font, text, self.fg, self.bg, self._buf)
        self.w, self.h = w, h
        self.sprite = self.pg.Sprite(bmp, self.x, self.y)
        self._slist[0] = self.sprite
        return True

    def draw(self, display, buffer):
        has_new = self.sprite is not None
        old = self._drawn
        if not has_new and old is None:
            return                         # nothing shown and nothing to erase
        if has_new:
            x0, y0 = self.x, self.y
            x1, y1 = self.x + self.w, self.y + self.h
            if old is not None:            # union with the old footprint so shrink/move erases it
                if old[0] < x0:
                    x0 = old[0]
                if old[1] < y0:
                    y0 = old[1]
                if old[2] > x1:
                    x1 = old[2]
                if old[3] > y1:
                    y1 = old[3]
        else:
            x0, y0, x1, y1 = old           # hidden: just clear the last footprint
        self.pg.render(display, self._slist if has_new else _EMPTY, buffer,
                       x0, y0, x1, y1, background=self.bg)
        self._drawn = (self.x, self.y, self.x + self.w, self.y + self.h) if has_new else None
