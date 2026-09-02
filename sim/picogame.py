# Desktop simulator implementation of the `picogame` C engine API. Pure Python,
# full-redraw (no dirty-rect needed on a PC), drawing into the host framebuffer.
# Mirrors the C semantics: wire-order RGB565, PAL8/RGB565 bitmaps with frames /
# transparent / flip, anchors, the view offset (camera) + fixed (HUD) layers,
# Tilemap / Particles / Canvas, and collide. Lets games run unchanged on a host.

import math as _math
import _host

RGB565 = 0
PAL8 = 1
API_LEVEL = 1                # feature-gate level, mirrors the firmware module constant
STRIP_H = 8                  # render-strip height default, mirrors the DMA-board firmware value
RGB444_SUPPORTED = False     # capability flag (mirrors firmware); the desktop sim renders RGB565
FAST_DISPLAY_SUPPORTED = True   # the sim's Display wrapper mirrors the fast backend's API
FRAMEBUFFER_SUPPORTED = False  # mirrors firmware: constant always present
_W = _host.W
_H = _host.H

_KIND_SPRITE = 0
_KIND_TILEMAP = 1
_KIND_PARTICLES = 2
_KIND_CANVAS = 3
_KIND_STRIPDRAW = 4
_strict_dirty = False       # --strict-dirty: skip an always_dirty=False StripDraw that was not
                            #  invalidate()d - the sim otherwise full-repaints and hides the bug




def _set_strict_dirty(on):
    global _strict_dirty
    _strict_dirty = bool(on)


def _sd_rect(sd):
    """The layer's on-screen rect, clipped to the framebuffer."""
    return (max(0, sd.x), min(_W, sd.x + sd._w),
            max(0, sd.y), min(_H, sd.y + sd._h))


def _sd_grab(sd):
    """Copy the layer's rect out of the live framebuffer (strict-dirty bookkeeping only)."""
    fb = _host.fb
    x0, x1, y0, y1 = _sd_rect(sd)
    return [fb[y * _W + x0:y * _W + x1] for y in range(y0, y1)]


def _sd_paint(sd, stash):
    """Put a stash back. False if it no longer fits the rect (the layer was moved/resized)."""
    fb = _host.fb
    x0, x1, y0, y1 = _sd_rect(sd)
    if len(stash) != y1 - y0 or (stash and len(stash[0]) != x1 - x0):
        return False
    for i, y in enumerate(range(y0, y1)):
        fb[y * _W + x0:y * _W + x1] = stash[i]
    return True
_KIND_TRIANGLES = 5
_SIM_STRIP_H = 8        # emulate the device's banded render so per-strip bugs surface


def rgb565(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


class Bitmap:
    def __init__(self, data, width, height, *, format=RGB565, palette=None,
                 frames=1, stride=0, transparent=None):
        self._data = data
        self.width = width
        self.height = height
        self.format = format
        self.palette = palette
        self.frames = frames
        self.stride = stride if stride else width * frames
        self.transparent = transparent
        self._has_transparent = transparent is not None
        # is RGB565 data stored as 16-bit units (array/list) or raw 2-byte LE?
        self._u16 = not isinstance(data, (bytes, bytearray, memoryview))


def _src_pixel(bm, sx, sy):
    """Return the wire-RGB565 value at (sx, sy) in the atlas, or None if transparent."""
    if bm.format == PAL8:
        idx = bm._data[sy * bm.stride + sx]
        if bm._has_transparent and idx == bm.transparent:
            return None
        if idx >= len(bm.palette):
            # The C blitter does NOT clamp (documented UB contract: indices MUST be
            # < palette length; on device this reads past the palette and can even
            # fault). The sim raises instead, so a bad asset surfaces at dev time.
            raise ValueError("PAL8 index %d out of palette (%d entries) - fix the asset"
                             % (idx, len(bm.palette)))
        return bm.palette[idx]
    # RGB565
    if bm._u16:
        v = bm._data[sy * bm.stride + sx]
    else:
        off = (sy * bm.stride + sx) * 2
        v = bm._data[off] | (bm._data[off + 1] << 8)
    if bm._has_transparent and v == bm.transparent:
        return None
    return v


# 4x4 ordered (Bayer) dither thresholds, mirrors the firmware (shared-module/picogame).
_BAYER4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def _mul565(a, b):
    # multiply two wire-order RGB565 pixels per channel (TINT), mirrors picogame_mul565
    ca = ((a >> 8) | (a << 8)) & 0xFFFF
    cb = ((b >> 8) | (b << 8)) & 0xFFFF
    r = ((ca >> 11) & 0x1F) * ((cb >> 11) & 0x1F) // 31
    g = ((ca >> 5) & 0x3F) * ((cb >> 5) & 0x3F) // 63
    bl = (ca & 0x1F) * (cb & 0x1F) // 31
    o = (r << 11) | (g << 5) | bl
    return ((o >> 8) | (o << 8)) & 0xFFFF


def _fxput(fb, i, v, x, y, shadow, flash, dither, tint=None):
    # per-pixel effect, mirrors picogame_fx_put in the C engine (one effect at a time)
    if dither and _BAYER4[y & 3][x & 3] < dither:
        return                      # pixel skipped -> background shows through (translucency)
    if flash:                       # falsy (None/0) = off, mirrors the firmware binding
        fb[i] = flash
    elif tint:
        fb[i] = _mul565(v, tint)
    elif shadow:
        fb[i] = _scale_wire(fb[i], 1, 2)
    else:
        fb[i] = v


# Set False to force every blit down the general path -- the two must agree pixel for pixel.
# selftest_blit.py flips this to fuzz one against the other; nothing else should touch it.
_FAST_BLIT = True


def _blit(bm, dx0, dy0, frame, flip_x, flip_y, clip, scale=1.0, shadow=False, flash=None,
          dither=0, tint=None, transpose=False):
    if bm is None:
        return
    sw, sh = bm.width, bm.height
    if bm.frames > 1:
        frame %= bm.frames
    else:
        frame = 0
    fcol = frame * sw
    cx0, cy0, cx1, cy1 = clip
    fb = _host.fb
    # 8.8 fixed-point scale, mirroring the C engine (sprite.scale is quantized to
    # uint16 8.8 on device; the setter clamps it >= 1/256).
    scale_q = int(scale * 256)
    if scale_q < 1:
        scale_q = 1
    # C honours transpose ONLY on the fast path (scale == 256); the scaled blitter
    # ignores it (see picogame_blit_bitmap / blit_sprite in shared-module).
    if transpose and scale_q == 256:       # cheap 90deg (mirrors the C transpose path)
        dw, dh = sh, sw                     # footprint swaps
        xs = max(dx0, cx0, 0); ys = max(dy0, cy0, 0)
        xe = min(dx0 + dw, cx1, _W); ye = min(dy0 + dh, cy1, _H)
        for y in range(ys, ye):
            ly = y - dy0                    # -> source X
            su0 = sw - 1 - ly if flip_x else ly
            for x in range(xs, xe):
                lx = x - dx0                # -> source Y
                sv = sh - 1 - lx if flip_y else lx
                v = _src_pixel_row(bm, sv * bm.stride + fcol, su0)
                if v is not None:
                    _fxput(fb, y * _W + x, v, x, y, shadow, flash, dither, tint)
        return
    # destination extent grows with scale; each dest pixel maps back to a source
    # pixel by nearest-neighbour (same technique as PicoLibSDK DrawImgMat, but
    # axis-aligned). scale == 1.0 (scale_q == 256) reduces to the 1:1 path.
    # Size math mirrors the C scaled blitter EXACTLY: FLOOR of dim * 8.8 scale,
    # and NO 1px minimum (C: dw <= 0 || dh <= 0 -> nothing drawn).
    dw = (sw * scale_q) >> 8
    dh = (sh * scale_q) >> 8
    if dw <= 0 or dh <= 0:
        return
    step = (1 << 24) // scale_q            # source px per dest px, 16.16 (mirrors C)
    cx0, cy0, cx1, cy1 = clip
    x_start = max(dx0, cx0, 0)
    y_start = max(dy0, cy0, 0)
    x_end = min(dx0 + dw, cx1, _W)
    y_end = min(dy0 + dh, cy1, _H)
    fb = _host.fb

    # FAST PATH: 1:1, no flips, no per-pixel effect, PAL8 - i.e. every tile of a tilemap and most
    # sprite blits. The general loop below spends two Python CALLS per destination pixel
    # (_src_pixel_row + _fxput); at ~80k pixels a frame that call overhead, not the pixel work, is
    # what makes a sim frame expensive. Same reads, same writes, same ValueError - just inlined.
    # Deliberately NOT a cache: nothing here can go stale, so a mutated bitmap needs no invalidation.
    if (_FAST_BLIT and scale_q == 256 and not flip_x and not flip_y and not shadow and not flash
            and not dither and tint is None and bm.format == PAL8):
        data = bm._data
        pal = bm.palette
        npal = len(pal)
        transp = bm.transparent if bm._has_transparent else -1
        for y in range(y_start, y_end):
            srow = (y - dy0) * bm.stride + fcol
            drow = y * _W
            sx = x_start - dx0
            for x in range(x_start, x_end):
                idx = data[srow + sx]
                sx += 1
                if idx == transp:
                    continue
                if idx >= npal:
                    # C does NOT clamp (UB contract) - raise to surface asset bugs, as _src_pixel_row does.
                    raise ValueError("PAL8 index %d out of palette (%d entries) - fix the asset"
                                     % (idx, npal))
                fb[drow + x] = pal[idx]
        return

    for y in range(y_start, y_end):
        sy = ((y - dy0) * step) >> 16
        if sy >= sh:
            sy = sh - 1
        if flip_y:
            sy = sh - 1 - sy
        srow = sy * bm.stride + fcol
        drow = y * _W
        for x in range(x_start, x_end):
            sx = ((x - dx0) * step) >> 16
            if sx >= sw:
                sx = sw - 1
            if flip_x:
                sx = sw - 1 - sx
            v = _src_pixel_row(bm, srow, sx)
            if v is not None:
                _fxput(fb, drow + x, v, x, y, shadow, flash, dither, tint)


def _src_pixel_row(bm, srow, sx):
    if bm.format == PAL8:
        idx = bm._data[srow + sx]
        if bm._has_transparent and idx == bm.transparent:
            return None
        if idx >= len(bm.palette):
            # C does NOT clamp (UB contract, see _src_pixel) - raise to surface asset bugs.
            raise ValueError("PAL8 index %d out of palette (%d entries) - fix the asset"
                             % (idx, len(bm.palette)))
        return bm.palette[idx]
    if bm._u16:
        v = bm._data[srow + sx]
    else:
        off = (srow + sx) * 2
        v = bm._data[off] | (bm._data[off + 1] << 8)
    if bm._has_transparent and v == bm.transparent:
        return None
    return v


class Sprite:
    def __init__(self, bitmap, x=0, y=0, *, frame=0, visible=True, flip_x=False, flip_y=False):
        self.bitmap = bitmap
        self._x = float(x)
        self._y = float(y)
        self.frame = frame
        self.visible = visible
        self.flip_x = flip_x
        self.flip_y = flip_y
        self._anchor_x = 0.0
        self._anchor_y = 0.0
        self.scale = 1.0          # uniform draw scale (nearest-neighbour)
        self.angle = 0.0          # rotation in degrees (about the anchor); 0 = fast path
        # blit effect: ONE shared slot (device parity). shadow/flash/dither/tint are
        # properties below - setting one clears the others (last-set-wins).
        self._fx_mode = None      # None | "shadow" | "flash" | "dither" | "tint"
        self._fx_val = None
        self.transpose = False    # swap x/y -> cheap 90deg (with flips = all 8 orientations)
        self.data = None

    @property
    def x(self):
        return int(_math.floor(self._x))

    @x.setter
    def x(self, v):
        self._x = float(v)

    @property
    def y(self):
        return int(_math.floor(self._y))

    @y.setter
    def y(self, v):
        self._y = float(v)

    @property
    def fx(self):
        return self._x

    @fx.setter
    def fx(self, v):
        self._x = float(v)

    @property
    def fy(self):
        return self._y

    @fy.setter
    def fy(self, v):
        self._y = float(v)

    # ---- blit effects: one shared slot, exactly like the device ----
    # On device the four effects are flag bits over ONE effect slot (set_effect in
    # shared-bindings/picogame): assigning a truthy value to any of shadow/flash/
    # tint/dither CLEARS the other three (last-set-wins); assigning a falsy value
    # clears only that effect (so `spr.flash = 0` can't wipe an active dither).
    # Draw priority in C is dither > flash > tint > shadow - moot with exclusivity
    # (at most one is ever active) but _fxput tests in that same order.
    def _set_fx(self, mode, value):
        if value:
            self._fx_mode = mode
            self._fx_val = value
        elif self._fx_mode == mode:
            self._fx_mode = None
            self._fx_val = None

    @property
    def shadow(self):
        return self._fx_mode == "shadow"   # darken-mode: opaque pixels dim the destination

    @shadow.setter
    def shadow(self, v):
        self._set_fx("shadow", bool(v))

    @property
    def flash(self):
        # flash: opaque pixels drawn as this wire-RGB565 colour; 0 when off (firmware parity -
        # 0 also DISABLES it, so pure black can never be the flash colour)
        return self._fx_val if self._fx_mode == "flash" else 0

    @flash.setter
    def flash(self, v):
        self._set_fx("flash", v)

    @property
    def dither(self):
        # 0=opaque .. 16=invisible: Bayer dither -> fake transparency
        return self._fx_val if self._fx_mode == "dither" else 0

    @dither.setter
    def dither(self, v):
        self._set_fx("dither", v)

    @property
    def tint(self):
        # tint: multiply opaque pixels by this colour (keeps shading); 0 when off (firmware parity)
        return self._fx_val if self._fx_mode == "tint" else 0

    @tint.setter
    def tint(self, v):
        self._set_fx("tint", v)

    @property
    def anchor(self):
        return (self._anchor_x, self._anchor_y)

    @anchor.setter
    def anchor(self, t):
        self._anchor_x, self._anchor_y = t[0], t[1]

    def move(self, x, y):
        self._x = float(x)
        self._y = float(y)

    def touch(self):
        # No-op in the sim (it repaints fully every frame). On device this forces a repaint
        # after an in-place bitmap mutation (e.g. StreamSheet); see shared-bindings.
        pass

    def _topleft(self):
        w = self.bitmap.width if self.bitmap else 0
        h = self.bitmap.height if self.bitmap else 0
        scale_q = max(1, int(self.scale * 256))
        w = (w * scale_q) >> 8               # anchor is a fraction of the SCALED size
        h = (h * scale_q) >> 8               # (FLOOR of 8.8 scale, like C picogame_sprite_topleft)
        if self.transpose and scale_q == 256:   # footprint swaps only on the fast path (like C)
            w, h = h, w
        return (self.x - int(self._anchor_x * w), self.y - int(self._anchor_y * h))

    def _bounds(self):
        # drawn box (x1, y1, x2, y2); x2/y2 = far corner. Mirrors C picogame_sprite_aabb:
        # angle==0 -> floor-scaled size + transpose (fast path only) + anchor offset;
        # angle!=0 -> rotated-corners bbox + the C margins (-1,-1,+2,+2).
        w = self.bitmap.width if self.bitmap else 0
        h = self.bitmap.height if self.bitmap else 0
        scale_q = max(1, int(self.scale * 256))
        if self.angle == 0:
            sw = (w * scale_q) >> 8
            sh = (h * scale_q) >> 8
            if self.transpose and scale_q == 256:
                sw, sh = sh, sw
            tx = self.x - int(self._anchor_x * sw)
            ty = self.y - int(self._anchor_y * sh)
            return (tx, ty, tx + sw, ty + sh)
        # rotated: transform the 4 UNSCALED-rect corners about the anchor pivot
        # (pivot in SOURCE pixels, scale applied to the corner deltas), floor each,
        # take the min/max bbox, then add C's margins. Mirrors corners_bbox +
        # picogame_sprite_aabb. NOTE: C uses a Q15 sine LUT at WHOLE degrees and
        # Q16 fixed-point; _math.sin/cos on a float angle can differ by +-1 px at
        # quantization boundaries (accepted residual).
        pivx = int(self._anchor_x * w)
        pivy = int(self._anchor_y * h)
        a = _math.radians(self.angle)
        cs, sn = _math.cos(a), _math.sin(a)
        sc = scale_q / 256.0
        minx = miny = 1 << 30
        maxx = maxy = -(1 << 30)
        for (cx, cy) in ((0, 0), (w, 0), (0, h), (w, h)):
            du = (cx - pivx) * sc
            dv = (cy - pivy) * sc
            X = int(_math.floor(du * cs - dv * sn))
            Y = int(_math.floor(du * sn + dv * cs))
            if X < minx:
                minx = X
            if X > maxx:
                maxx = X
            if Y < miny:
                miny = Y
            if Y > maxy:
                maxy = Y
        px, py = self.x, self.y
        return (px + minx - 1, py + miny - 1, px + maxx + 2, py + maxy + 2)

    def _other_box(self, b):
        if isinstance(b, Sprite):
            return b._bounds()
        if len(b) == 2:                       # a point -> zero-size box
            return (b[0], b[1], b[0], b[1])
        return (b[0], b[1], b[2], b[3])       # a rect

    def overlaps(self, other, inset=0):
        # AABB overlap; `other` = Sprite | (x, y) | (x1, y1, x2, y2). inset shrinks THIS box only.
        ax1, ay1, ax2, ay2 = self._bounds()
        bx1, by1, bx2, by2 = self._other_box(other)
        return (ax1 + inset <= bx2 and ax2 - inset >= bx1 and
                ay1 + inset <= by2 and ay2 - inset >= by1)

    def near(self, other, r):
        # circle: centres within r (no sqrt); `other` = Sprite | (x, y).
        ax1, ay1, ax2, ay2 = self._bounds()
        acx, acy = (ax1 + ax2) // 2, (ay1 + ay2) // 2
        if isinstance(other, Sprite):
            bx1, by1, bx2, by2 = other._bounds()
            bcx, bcy = (bx1 + bx2) // 2, (by1 + by2) // 2
        else:
            bcx, bcy = other[0], other[1]
        dx, dy = acx - bcx, acy - bcy
        return dx * dx + dy * dy < r * r


def _blit_affine(bm, frame, flip_x, flip_y, clip, px, py, pivx, pivy, scale, ang_deg, shadow=False, flash=None, dither=0, tint=None):
    """Rotated+scaled blit (nearest-neighbour, inverse-mapped) -- the affine path,
    mirroring PicoLibSDK DrawImgMat. (px,py)=screen pos the anchor maps to;
    (pivx,pivy)=that anchor in SOURCE pixels; rotation is about it."""
    if bm is None:
        return
    sw, sh = bm.width, bm.height
    frame = frame % bm.frames if bm.frames > 1 else 0
    fcol = frame * sw
    a = _math.radians(ang_deg)
    cs, sn = _math.cos(a), _math.sin(a)
    # forward-transform the 4 corners -> screen bounding box
    xs, ys = [], []
    for (u, v) in ((0, 0), (sw, 0), (0, sh), (sw, sh)):
        du, dv = (u - pivx) * scale, (v - pivy) * scale
        xs.append(px + du * cs - dv * sn)
        ys.append(py + du * sn + dv * cs)
    cx0, cy0, cx1, cy1 = clip
    x0 = max(int(_math.floor(min(xs))), cx0, 0)
    x1 = min(int(_math.ceil(max(xs))), cx1, _W)
    y0 = max(int(_math.floor(min(ys))), cy0, 0)
    y1 = min(int(_math.ceil(max(ys))), cy1, _H)
    fb = _host.fb
    inv = 1.0 / scale
    for Y in range(y0, y1):
        dy = Y - py
        for X in range(x0, x1):
            dx = X - px
            iu = int(pivx + inv * (cs * dx + sn * dy))
            iv = int(pivy + inv * (-sn * dx + cs * dy))
            if 0 <= iu < sw and 0 <= iv < sh:
                sx = sw - 1 - iu if flip_x else iu
                sy = sh - 1 - iv if flip_y else iv
                val = _src_pixel_row(bm, sy * bm.stride + fcol, sx)
                if val is not None:
                    _fxput(fb, Y * _W + X, val, X, Y, shadow, flash, dither, tint)


def _draw_sprite(s, vx, vy, clip):
    if not s.visible:
        return
    if s.angle == 0:                     # axis-aligned fast path (scale only)
        tx, ty = s._topleft()
        _blit(s.bitmap, tx + vx, ty + vy, s.frame, s.flip_x, s.flip_y, clip, s.scale,
              s.shadow, s.flash, s.dither, s.tint, s.transpose)
    else:                                # full affine (rotation about the anchor)
        w = s.bitmap.width if s.bitmap else 0
        h = s.bitmap.height if s.bitmap else 0
        _blit_affine(s.bitmap, s.frame, s.flip_x, s.flip_y, clip,
                     s.x + vx, s.y + vy, s._anchor_x * w, s._anchor_y * h, s.scale, s.angle,
                     s.shadow, s.flash, s.dither, s.tint)


class Tilemap:
    def __init__(self, tileset, cols, rows):
        self._tileset = tileset
        self._map_w = cols
        self._map_h = rows
        self._grid = bytearray(cols * rows)
        self._orient = None        # lazy: bit0 flipX, bit1 flipY, bit2 transpose per cell
        self._ox = 0
        self._oy = 0

    # read-only getters mirroring the firmware (position via move(); size from ctor)
    @property
    def x(self):
        return self._ox

    @property
    def y(self):
        return self._oy

    @property
    def cols(self):
        return self._map_w

    @property
    def rows(self):
        return self._map_h

    def get_tile(self, tx, ty):
        if tx < 0 or tx >= self._map_w or ty < 0 or ty >= self._map_h:
            return 0
        return self._grid[ty * self._map_w + tx]

    def set_tile(self, tx, ty, value, *, flip_x=False, flip_y=False, transpose=False):
        if tx < 0 or tx >= self._map_w or ty < 0 or ty >= self._map_h:
            return None
        off = ty * self._map_w + tx
        self._grid[off] = value
        o = (1 if flip_x else 0) | (2 if flip_y else 0) | (4 if transpose else 0)
        if o and self._orient is None:
            self._orient = bytearray(self._map_w * self._map_h)
        if self._orient is not None:
            self._orient[off] = o
        return None

    def fill(self, value):
        for i in range(len(self._grid)):
            self._grid[i] = value
            if self._orient is not None:
                self._orient[i] = 0

    def move(self, x, y):
        self._ox = x
        self._oy = y

    def _draw(self, vx, vy, clip):
        tw, th = self._tileset.width, self._tileset.height
        nframes = self._tileset.frames
        # Only walk the tiles the clip rect can actually show. _blit rejects an off-screen tile
        # anyway, but a map is usually far wider than the screen (a 80x15 level = 1200 tiles against
        # ~315 visible), so the call overhead alone was most of a sim frame. Pure culling: the
        # skipped tiles contribute no pixels, so output is unchanged.
        cx0, cy0, cx1, cy1 = clip
        # A TRANSPOSED tile draws tw x th swapped, so on a non-square tileset its footprint reaches
        # outside the cell these bounds are derived from. An audit reported culling dropping such a
        # tile; I could NOT reproduce it end to end, so treat this as cheap insurance against a
        # geometry the bounds do not model, not as a fix for a demonstrated bug. selftest_blit's
        # tilemap fuzz has never generated the case either - if you go looking, start there.
        pad = 1 if (self._orient is not None and tw != th) else 0
        tx_lo = max(0, (cx0 - self._ox - vx) // tw - pad)
        tx_hi = min(self._map_w, (cx1 - self._ox - vx) // tw + 1 + pad)
        ty_lo = max(0, (cy0 - self._oy - vy) // th - pad)
        ty_hi = min(self._map_h, (cy1 - self._oy - vy) // th + 1 + pad)
        for ty in range(ty_lo, ty_hi):
            for tx in range(tx_lo, tx_hi):
                off = ty * self._map_w + tx
                v = self._grid[off]
                if v >= nframes:
                    continue        # C skips out-of-range tile indices (no wrap)
                o = self._orient[off] if self._orient is not None else 0
                _blit(self._tileset, self._ox + tx * tw + vx, self._oy + ty * th + vy,
                      v, bool(o & 1), bool(o & 2), clip, 1.0, False, None, 0, None, bool(o & 4))


class Particles:
    def __init__(self, capacity, *, size=1, gravity=0.0, fade=False):
        self._cap = capacity
        self._size = size
        self._gravity = gravity
        self._fade = fade
        self._px = []
        self._py = []
        self._vx = []
        self._vy = []
        self._life = []
        self._life0 = []
        self._color = []

    def emit(self, x, y, count, speed=1, life=30, color=0xFFFF):
        if count < 0:
            raise ValueError("count must be >= 0")
        if speed < 0:
            raise ValueError("speed must be >= 0")
        if life <= 0:
            raise ValueError("life must be > 0")
        import random
        for _ in range(count):
            if len(self._px) >= self._cap:
                break
            self._px.append(float(x))
            self._py.append(float(y))
            self._vx.append(random.uniform(-speed, speed))
            self._vy.append(random.uniform(-speed, speed))
            self._life.append(life)
            self._life0.append(max(1, life))
            self._color.append(color)

    def tick(self):
        i = 0
        while i < len(self._px):
            self._px[i] += self._vx[i]
            self._py[i] += self._vy[i]
            self._vy[i] += self._gravity
            if self._life[i] <= 0:
                for a in (self._px, self._py, self._vx, self._vy, self._life, self._life0, self._color):
                    a[i] = a[-1]
                    a.pop()
                continue
            self._life[i] -= 1
            i += 1

    def clear(self):
        for a in (self._px, self._py, self._vx, self._vy, self._life, self._life0, self._color):
            del a[:]

    def _draw(self, vx, vy, clip):
        fb = _host.fb
        sz = self._size
        cx0, cy0, cx1, cy1 = clip
        for i in range(len(self._px)):
            x0 = int(self._px[i]) + vx
            y0 = int(self._py[i]) + vy
            c = self._color[i]
            if self._fade:
                c = _scale_wire(c, self._life[i], self._life0[i])
            for yy in range(max(y0, cy0, 0), min(y0 + sz, cy1, _H)):
                drow = yy * _W
                for xx in range(max(x0, cx0, 0), min(x0 + sz, cx1, _W)):
                    fb[drow + xx] = c


def _scale_wire(wire, num, den):
    c = ((wire >> 8) | (wire << 8)) & 0xFFFF
    r = ((c >> 11) & 0x1F) * num // den
    g = ((c >> 5) & 0x3F) * num // den
    b = (c & 0x1F) * num // den
    out = (r << 11) | (g << 5) | b
    return ((out >> 8) | (out << 8)) & 0xFFFF


class _U16Buf:
    """A 16-bit-unit view over a raw 2-byte-LE bytearray, so a sim Canvas can SHARE the
    exact backing buffer of a Bitmap (which reads RGB565 as 2-byte LE). Mirrors device
    semantics where Canvas(buffer=) and Bitmap(buf) alias the same memory."""
    __slots__ = ("ba",)

    def __init__(self, ba):
        self.ba = ba

    def __len__(self):
        return len(self.ba) // 2

    def __getitem__(self, i):
        return self.ba[2 * i] | (self.ba[2 * i + 1] << 8)

    def __setitem__(self, i, v):
        self.ba[2 * i] = v & 0xFF
        self.ba[2 * i + 1] = (v >> 8) & 0xFF


class Canvas:
    def __init__(self, width, height, *, transparent=None, buffer=None):
        # On device `buffer` (an arena slice / shared band buffer) is drawn into directly so the
        # Canvas can alias another object's memory (e.g. a Bitmap fed to pg.render). The sim mirrors
        # that aliasing via _U16Buf when a real bytes-like buffer is passed; otherwise it allocates.
        self._w = width
        self._h = height
        self._transparent = transparent
        self._has_transparent = transparent is not None
        if isinstance(buffer, (bytearray, memoryview)):
            self._data = _U16Buf(buffer)
        else:
            self._data = [0] * (width * height)
        self.x = 0
        self.y = 0

    # read-only size getters mirroring the firmware (internals use w/h)
    @property
    def width(self):
        return self._w

    @property
    def height(self):
        return self._h

    def move(self, x, y):
        self.x = x
        self.y = y

    def clear(self, color):
        for i in range(len(self._data)):
            self._data[i] = color

    def pixel(self, x, y, color):
        if 0 <= x < self._w and 0 <= y < self._h:
            self._data[y * self._w + x] = color

    def fill_rect(self, x, y, w, h, color):
        for yy in range(max(0, y), min(self._h, y + h)):
            base = yy * self._w
            for xx in range(max(0, x), min(self._w, x + w)):
                self._data[base + xx] = color

    def text(self, x, y, s, fg, font, bg=None):
        # Sim mirror of the firmware Canvas.text(): composite glyphs straight into the surface.
        # The device does this in C with no Python glyph cache; here we reuse the sim's glyph
        # rasterizer (RAM is free in the sim) - the OUTPUT pixels are identical either way.
        # The firmware accepts ONLY fontio.BuiltinFont - mirror that strictly, or a game that
        # passes an ExtraFont works in the sim and TypeErrors on the device (bitten 2026-07).
        if type(font).__name__ not in ("_Font", "BuiltinFont"):
            raise TypeError("font must be of type BuiltinFont, not %s" % type(font).__name__)
        import picogame_font as _pf
        fw, fh = font.get_bounding_box()[:2]
        for ch in s:
            rows = _pf._glyph_rows(font, ord(ch), fw, fh)
            for gy in range(fh):
                cy = y + gy
                if not (0 <= cy < self._h):
                    continue
                r = rows[gy]
                base = cy * self._w
                for gx in range(fw):
                    cx = x + gx
                    if not (0 <= cx < self._w):
                        continue
                    if r[gx]:
                        self._data[base + cx] = fg
                    elif bg is not None:
                        self._data[base + cx] = bg
            x += fw

    def blit(self, bitmap, x, y, frame=0, flip_x=False, flip_y=False):
        fw, fh = bitmap.width, bitmap.height
        for ry in range(fh):
            cy = y + ry
            if not (0 <= cy < self._h):
                continue
            sy = (fh - 1 - ry) if flip_y else ry
            base = cy * self._w
            for rx in range(fw):
                cx = x + rx
                if not (0 <= cx < self._w):
                    continue
                sx = (fw - 1 - rx) if flip_x else rx
                v = _src_pixel(bitmap, frame * fw + sx, sy)
                if v is not None:
                    self._data[base + cx] = v

    def mode7(self, texture, horizon, y_off, z, rx0, ry0, rsx, rsy, cam_x, cam_y):
        # Perspective ground plane (Mode-7). sy is a row WITHIN this surface; the
        # absolute screen row is sy + y_off (0 for a full Canvas, strip y for a
        # StripDraw view). Integer math IDENTICAL to the firmware C: per-row 1/z
        # distance divide, per-pixel 16.16 texture accumulate with pow2 wrap.
        # texture must have power-of-2 width/height. rx0/ry0 = left-ray dir (Q16),
        # rsx/rsy = per-pixel ray delta (Q16), z = posZ (Q16), cam_x/y = Q16.
        F = 16
        tw, th = texture.width, texture.height
        shx = F - (tw.bit_length() - 1)          # world(1.0)->one tile
        shy = F - (th.bit_length() - 1)
        mx, my = tw - 1, th - 1
        stride = texture.stride
        y0 = max(0, horizon - y_off + 1)
        for sy in range(y0, self._h):
            denom = (sy + y_off) - horizon
            if denom <= 0:
                continue
            rowdist = z // denom
            stepx = (rowdist * rsx) >> F
            stepy = (rowdist * rsy) >> F
            fx = cam_x + ((rowdist * rx0) >> F)
            fy = cam_y + ((rowdist * ry0) >> F)
            base = sy * self._w
            for sx in range(self._w):
                tx = (fx >> shx) & mx
                ty = (fy >> shy) & my
                v = _src_pixel_row(texture, ty * stride + tx, 0)
                if v is not None:
                    self._data[base + sx] = v
                fx += stepx
                fy += stepy

    def rect(self, x, y, w, h, color):
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def fill_circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            span = int(_math.sqrt(max(0, r * r - dy * dy)))
            self.fill_rect(cx - span, cy + dy, 2 * span + 1, 1, color)

    # ---- extra primitives (harvested from PicoLibSDK's draw set) ----
    def circle(self, cx, cy, r, color):
        x, y, err = r, 0, 1 - r
        while x >= y:
            for px, py in ((x, y), (y, x), (-x, y), (-y, x), (-x, -y), (-y, -x), (x, -y), (y, -x)):
                self.pixel(cx + px, cy + py, color)
            y += 1
            if err < 0:
                err += 2 * y + 1
            else:
                x -= 1
                err += 2 * (y - x) + 1

    def ring(self, cx, cy, r, thickness, color):
        inner = max(0, r - thickness)
        for dy in range(-r, r + 1):
            out = int(_math.sqrt(max(0, r * r - dy * dy)))
            if abs(dy) <= inner:
                ins = int(_math.sqrt(max(0, inner * inner - dy * dy)))
                self.fill_rect(cx - out, cy + dy, out - ins, 1, color)
                self.fill_rect(cx + ins + 1, cy + dy, out - ins, 1, color)
            else:
                self.fill_rect(cx - out, cy + dy, 2 * out + 1, 1, color)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, color):
        (ya, xa), (yb, xb), (yc, xc) = sorted(((y0, x0), (y1, x1), (y2, x2)))
        def ex(y, ay, ax, by, bx):
            return ax if by == ay else ax + (bx - ax) * (y - ay) // (by - ay)
        for y in range(ya, yc + 1):
            if y < yb:
                xs, xe = ex(y, ya, xa, yb, xb), ex(y, ya, xa, yc, xc)
            else:
                xs, xe = ex(y, yb, xb, yc, xc), ex(y, ya, xa, yc, xc)
            if xs > xe:
                xs, xe = xe, xs
            self.fill_rect(xs, y, xe - xs + 1, 1, color)

    def fill_triangles(self, verts, colors, n, x_off=0, y_off=0):
        # Sim of the native Canvas.fill_triangles batch fill (C loops over the rasteriser in ONE
        # Python/C crossing on device). verts = int16 x0,y0,x1,y1,x2,y2 per tri; colors = wire RGB565.
        # x_off/y_off translate every vertex before clipping (pass y_off=-vy to replay one
        # screen-space batch into each StripDraw view; off-band triangles are rejected).
        h = self.height
        w = self.width
        for i in range(n):
            p = i * 6
            y0 = verts[p + 1] + y_off
            y1 = verts[p + 3] + y_off
            y2 = verts[p + 5] + y_off
            if (y0 < 0 and y1 < 0 and y2 < 0) or (y0 >= h and y1 >= h and y2 >= h):
                continue
            x0 = verts[p] + x_off
            x1 = verts[p + 2] + x_off
            x2 = verts[p + 4] + x_off
            if (x0 < 0 and x1 < 0 and x2 < 0) or (x0 >= w and x1 >= w and x2 >= w):
                continue
            self.fill_triangle(x0, y0, x1, y1, x2, y2, colors[i])

    def road(self, ri0, tab, rl, rr, d05_q8, d07_q8, colors):
        # Sim of the native Canvas.road (C: shared-module/picogame/Canvas.c picogame_canvas_road):
        # one racing-road strip, all rows in one call. ri0 = road-table row of THIS surface's row 0
        # (negative rows = sky); tab = int16 rows of {edge_w, dash_hw, wb05_q8, wb07_q8, flags};
        # rl/rr = per-row integer edges (road_edges output); d05/d07 = Q8 scroll phases; colors =
        # 6x uint16 {sky, road_a, road_b, rumble_a, rumble_b, dash}. Golden-tested against the C
        # (selftest_road.py). Grass under the road and the finish chequer stay the caller's job.
        ntab = len(tab) // 5
        nedge = min(len(rl), len(rr))
        if nedge < ntab:
            ntab = nedge                       # never read past the shorter per-frame arrays
        if ntab <= 0 or len(colors) < 6:
            return
        w = self._w
        data = self._data
        sky = colors[0]
        for ly in range(self._h):
            ri = ri0 + ly
            if ri < 0:                         # above the horizon: sky
                base = ly * w
                for x in range(base, base + w):
                    data[x] = sky
                continue
            if ri >= ntab:
                ri = ntab - 1
            ti = ri * 5
            band = ((d05_q8 + tab[ti + 2]) >> 8) & 1
            road_c = colors[1] if band else colors[2]
            rumble = colors[3] if band else colors[4]
            l = rl[ri]
            r = rr[ri]
            if r <= l:
                continue
            self._span(ly, l, r - 1, road_c)
            ew = tab[ti]
            self._span(ly, l, l + ew - 1, rumble)
            self._span(ly, r - ew, r - 1, rumble)
            if (tab[ti + 4] & 1) and (((d07_q8 + tab[ti + 3]) >> 8) & 1):
                mid = (l + r) >> 1
                dw = tab[ti + 1]
                self._span(ly, mid - dw, mid + dw - 1, colors[5])

    def _span(self, y, xs, xe, color):
        # clipped horizontal run [xs, xe] inclusive - mirror of the C span565()
        if y < 0 or y >= self._h:
            return
        if xs < 0:
            xs = 0
        if xe >= self._w:
            xe = self._w - 1
        if xs <= xe:
            base = y * self._w
            data = self._data
            for x in range(base + xs, base + xe + 1):
                data[x] = color

    def vspans(self, x0s, x1s, tops, bots, colors, n, x_off=0, y_off=0):
        # Sim of the native Canvas.vspans batch fill (C loops over fill_rect in ONE Python/C
        # crossing on device). Span i covers x0s[i]..x1s[i] by tops[i]..bots[i] (both exclusive)
        # in colors[i]; all five are uint16 arrays. x_off/y_off translate before clipping (pass
        # x_off=-vx, y_off=-vy to replay one screen-space batch into each StripDraw view).
        h = self.height
        w = self.width
        for i in range(n):
            t = tops[i] + y_off
            b = bots[i] + y_off
            if b <= 0 or t >= h or b <= t:
                continue
            x0 = x0s[i] + x_off
            x1 = x1s[i] + x_off
            if x1 <= 0 or x0 >= w or x1 <= x0:
                continue
            self.fill_rect(x0, t, x1 - x0, b - t, colors[i])

    def triangle(self, x0, y0, x1, y1, x2, y2, color):
        self.line(x0, y0, x1, y1, color)
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x0, y0, color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        for dy in range(-ry, ry + 1):
            span = int(rx * _math.sqrt(max(0.0, 1.0 - (dy * dy) / float(ry * ry)))) if ry else 0
            self.fill_rect(cx - span, cy + dy, 2 * span + 1, 1, color)

    def ellipse(self, cx, cy, rx, ry, color):
        steps = max(8, int(6.2832 * max(rx, ry)))
        for i in range(steps):
            a = 6.2832 * i / steps
            self.pixel(cx + int(rx * _math.cos(a)), cy + int(ry * _math.sin(a)), color)

    def fill_round_rect(self, x, y, w, h, r, color):
        r = min(r, w // 2, h // 2)
        self.fill_rect(x + r, y, w - 2 * r, h, color)
        self.fill_rect(x, y + r, r, h - 2 * r, color)
        self.fill_rect(x + w - r, y + r, r, h - 2 * r, color)
        for ccx, ccy in ((x + r, y + r), (x + w - r - 1, y + r),
                         (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.fill_circle(ccx, ccy, r, color)

    def frame3d(self, x, y, w, h, light, dark):
        """A bevelled UI box: light top/left edge, dark bottom/right edge."""
        self.fill_rect(x, y, w, 1, light)
        self.fill_rect(x, y, 1, h, light)
        self.fill_rect(x, y + h - 1, w, 1, dark)
        self.fill_rect(x + w - 1, y, 1, h, dark)

    def _draw(self, vx, vy, clip):
        fb = _host.fb
        cx0, cy0, cx1, cy1 = clip
        ox, oy = self.x + vx, self.y + vy
        key = self._transparent
        for yy in range(max(oy, cy0, 0), min(oy + self._h, cy1, _H)):
            srow = (yy - oy) * self._w
            drow = yy * _W
            for xx in range(max(ox, cx0, 0), min(ox + self._w, cx1, _W)):
                v = self._data[srow + (xx - ox)]
                if self._has_transparent and v == key:
                    continue
                fb[drow + xx] = v


class StripDraw:
    """Immediate-mode draw layer: holds NO pixel buffer. Each refresh, for every
    render strip overlapping its rect, calls ``callback(view, vx, vy, vw, vh)`` with a
    Canvas ``view`` pointing at the live strip -- so you draw straight into the frame
    (zero RAM vs a Canvas's w*h*2 bytes). view-local (0,0) is screen (vx, vy). Its rect
    is repainted every frame: use it for animated / scanline content (pseudo-3D,
    gradients, procedural backgrounds), not static art. Mirrors the firmware type."""

    def __init__(self, callback, x=0, y=0, width=0, height=0, *, always_dirty=True):
        self._callback = callback
        self.x = x
        self.y = y
        self._w = width
        self._h = height
        self.always_dirty = always_dirty   # device-only effect (the sim has no dirty-rect; it full-repaints)
        if always_dirty and width * height >= (_W * _H) // 2:
            # The sim can't SHOW this cost (it repaints everything anyway), so at least name it:
            # a big always_dirty layer marks its whole rect dirty every frame, which on device
            # drags every other layer's strips into the repaint - the measured 14 fps trap.
            _host.note("full-screen StripDraw, always_dirty=True (%dx%d). Correct IF its content "
                       "really changes every frame (a road, a raycaster, a scrolling sky). If it "
                       "changes only sometimes (HUD, menu, overlay), on DEVICE it repaints every "
                       "frame and drags the whole scene out of dirty-rect (measured: 14 fps on a "
                       "static screen) - then pass always_dirty=False and invalidate() on change. "
                       "The sim cannot tell the two apart: it has no dirty-rect at all."
                       % (width, height))
        self._pending = True
        self._sd_own = None              # --strict-dirty only: this layer's own last output, and
        self._sd_below = None            #  the pixels beneath it when that output was made
        self._view = Canvas(1, 1)        # reused; data/w/h repointed per strip

    def invalidate(self, x=None, y=None, w=None, h=None):
        # firmware contract: no args = whole layer, ALL FOUR = a sub-rect; a partial rectangle
        # raises (it is a bug, not a request for "everything"). The sim has no dirty-rect (it
        # full-repaints), so a full rect is accepted for API parity but otherwise ignored.
        if sum(v is not None for v in (x, y, w, h)) not in (0, 4):
            raise ValueError("invalid rect")
        self._pending = True

    # read/write rect size mirroring the firmware properties (internals use w/h)
    @property
    def width(self):
        return self._w

    @width.setter
    def width(self, v):
        self._w = v

    @property
    def height(self):
        return self._h

    @height.setter
    def height(self, v):
        self._h = v

    def _draw(self, vx, vy, clip):
        fb = _host.fb
        cx0, cy0, cx1, cy1 = clip
        # Match the FIRMWARE exactly: the view spans the WHOLE region (clip) width and vx is the region
        # origin (not the layer's x). The layer's rect only gates which ROWS are drawn (its y-range).
        # So a callback must draw at ABSOLUTE screen coords minus (vx, vy), and fill only its own rect
        # (a `view.clear()` fills the whole region width). Mirrors v->w = region_w in the C blitter.
        # Screen-space by design (like Triangles): the scene view offset is NOT applied - the C
        # compositor keeps a StripDraw's rows at self.y whether or not the layer is fixed.
        ry = self.y
        y_lo, y_hi = max(ry, cy0, 0), min(ry + self._h, cy1, _H)
        if cx0 >= cx1 or y_lo >= y_hi:
            return
        rw = cx1 - cx0
        view = self._view
        view._w = rw
        view._has_transparent = False
        view.x = view.y = 0
        sy = y_lo
        while sy < y_hi:
            sh = min(_SIM_STRIP_H, y_hi - sy)
            view._h = sh
            # The strip already holds the background + lower layers (as on device):
            # seed the view from fb, let the callback draw over it, copy back.
            data = [0] * (rw * sh)
            for ly in range(sh):
                drow = (sy + ly) * _W + cx0
                srow = ly * rw
                for lx in range(rw):
                    data[srow + lx] = fb[drow + lx]
            view._data = data
            self._callback(view, cx0, sy, rw, sh)
            for ly in range(sh):
                drow = (sy + ly) * _W + cx0
                srow = ly * rw
                for lx in range(rw):
                    fb[drow + lx] = data[srow + lx]
            sy += sh


class Triangles:
    """Retained SCREEN-SPACE triangle batch, drawn by the compositor in C on device (no
    Python per strip -- unlike StripDraw it stays composable by core1/async refresh).
    ``verts`` = int16 array (x0,y0,x1,y1,x2,y2 per triangle), ``colors`` = uint16 wire-RGB565
    per triangle -- both CALLER-OWNED (fill them in place each frame). Assign ``count`` to
    how many triangles should draw (marks the layer dirty). Mirrors the firmware type."""

    def __init__(self, verts, colors):
        self._verts = verts
        self._colors = colors
        self._cap = min(len(verts) // 6, len(colors))
        self._count = 0
        self._view = Canvas(1, 1)          # reused; data/w/h repointed per draw

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, n):
        self._count = max(0, min(int(n), self._cap))

    def _draw(self, vx, vy, clip):
        # Screen-space by design (the view offset is not applied) -- one full-region view.
        if self._count == 0:
            return
        fb = _host.fb
        cx0, cy0, cx1, cy1 = clip
        cx0, cy0 = max(cx0, 0), max(cy0, 0)
        cx1, cy1 = min(cx1, _W), min(cy1, _H)
        if cx0 >= cx1 or cy0 >= cy1:
            return
        rw, rh = cx1 - cx0, cy1 - cy0
        view = self._view
        view._w = rw
        view._h = rh
        view.x = view.y = 0
        view._has_transparent = False
        data = [0] * (rw * rh)
        for ly in range(rh):
            drow = (cy0 + ly) * _W + cx0
            srow = ly * rw
            data[srow:srow + rw] = fb[drow:drow + rw]
        view._data = data
        view.fill_triangles(self._verts, self._colors, self._count, -cx0, -cy0)
        for ly in range(rh):
            drow = (cy0 + ly) * _W + cx0
            srow = ly * rw
            fb[drow:drow + rw] = data[srow:srow + rw]


def _kind(item):
    if isinstance(item, Sprite):
        return _KIND_SPRITE
    if isinstance(item, Tilemap):
        return _KIND_TILEMAP
    if isinstance(item, Particles):
        return _KIND_PARTICLES
    if isinstance(item, Canvas):
        return _KIND_CANVAS
    if isinstance(item, StripDraw):
        return _KIND_STRIPDRAW
    if isinstance(item, Triangles):
        return _KIND_TRIANGLES
    raise TypeError("expected Sprite/Tilemap/Particles/Canvas/StripDraw/Triangles")


def _draw_item(item, kind, vx, vy, clip):
    if kind == _KIND_SPRITE:
        _draw_sprite(item, vx, vy, clip)
    elif kind == _KIND_TILEMAP:
        item._draw(vx, vy, clip)
    elif kind == _KIND_PARTICLES:
        item._draw(vx, vy, clip)
    else:
        if _strict_dirty and kind == _KIND_STRIPDRAW and not item.always_dirty:
            # Device rule (Scene.c:117 + the strip compositor): a clean layer is skipped ONLY while
            # nothing else dirties its rect - any overlapping repaint re-runs its callback. So we
            # restore the layer's OWN last output (not the composite, which would burn in whatever
            # a passing sprite drew ON TOP of it), and only while what lies BENEATH it is unchanged.
            below = _sd_grab(item)
            if (not item._pending and item._sd_own is not None
                    and below == item._sd_below and _sd_paint(item, item._sd_own)):
                return                # frozen: a forgotten invalidate() still shows stale content
            item._sd_below = below    # something changed under it (or it was invalidated): redraw
            item._draw(vx, vy, clip)
            item._sd_own = _sd_grab(item)
            item._pending = False
            return
        item._draw(vx, vy, clip)
        if kind == _KIND_STRIPDRAW:
            item._pending = False


class Display:
    def __init__(self, display, *, rgb444=False):
        self.display = display
        self.rgb444 = rgb444        # honoured on device (COLMOD + pack); the sim renders RGB565

    def render(self, sprites, buffer_a, buffer_b, x0, y0, x1, y1, *, background=0):
        # Mirrors the firmware fast Display.render (double-buffered DMA on device);
        # the sim just draws the region and presents (buffering is invisible here).
        render(self.display, sprites, buffer_a, x0, y0, x1, y1, background=background)


_FULL = (0, 0, _W, _H)


class Scene:
    def __init__(self, display, buffer_a, buffer_b, *, background=0,
                 top=0, bottom=0, left=0, right=0):
        self.display = display
        self._background = background
        self._items = []
        self._kinds = []
        self._fixed = []
        self._ox = 0
        self._oy = 0
        # reserved border insets; scene renders only [left, _W-right) x [top, _H-bottom)
        self._top = top
        self._bottom = bottom
        self._left = left
        self._right = right
        self._pending_checks = []             # layers awaiting the reserved-band check

    def add(self, item, *, fixed=False):
        self._items.append(item)
        self._kinds.append(_kind(item))
        self._fixed.append(fixed)
        self._pending_checks.append(item)     # judged at the first refresh, not here: at add()
        return item                           #  time a layer is often still parked at (0,0)

    def _check_reserved(self, item):
        # A layer that lies ENTIRELY inside a setup(top=/bottom=/left=/right=) band never draws -
        # the scene doesn't touch reserved margins (that space belongs to HudBar / pg.render). It
        # is dropped in silence on device too, so say it here rather than let a blank HUD look
        # like a broken callback.
        #
        # Judged at the FIRST REFRESH, in SCREEN coordinates, and only for a layer that is visible
        # and non-empty. Doing it at add() in world coordinates cried wolf on every ordinary idiom -
        # a picogame_pool.Pool parks unspawned sprites at (0,0) invisible, a scrolling world puts
        # most sprites outside the current view, and "construct, then place" is how games are
        # written. It fired on five shipped games, which is how a warning stops being read.
        if not (self._top or self._bottom or self._left or self._right):
            return
        try:
            if isinstance(item, StripDraw):
                if item._w <= 0 or item._h <= 0:
                    return                    # an empty rect draws nothing anywhere; not this bug
                x1, y1, x2, y2 = item.x, item.y, item.x + item._w, item.y + item._h
            elif isinstance(item, Sprite):
                if not item.visible:
                    return                    # a parked/pooled sprite is not "silently dead"
                x1, y1, x2, y2 = item._bounds()
            else:
                return
            if item in self._items:           # non-fixed layers scroll with the view
                i = self._items.index(item)
                if not self._fixed[i] and not isinstance(item, StripDraw):
                    x1 += self._ox
                    x2 += self._ox
                    y1 += self._oy
                    y2 += self._oy
        except Exception:
            return
        if x2 <= 0 or y2 <= 0 or x1 >= _W or y1 >= _H:
            return                            # simply OFF-SCREEN (parked, pooled, scrolled away):
        #                                       normal, and nothing to do with a reserved band
        in_band = ((self._top and y2 <= self._top)
                   or (self._bottom and y1 >= _H - self._bottom)
                   or (self._left and x2 <= self._left)
                   or (self._right and x1 >= _W - self._right))
        if in_band:
            _host.note("a %s at (%d,%d)-(%d,%d) lies entirely inside the band reserved by "
                       "setup(top=%d, bottom=%d, left=%d, right=%d) - the scene never draws "
                       "there, so this layer is silently dead. Paint the band with HudBar / "
                       "pg.render, or move the layer into the play area."
                       % (type(item).__name__, x1, y1, x2, y2,
                          self._top, self._bottom, self._left, self._right))

    def add_all(self, items):
        for it in items:
            self.add(it)

    def remove(self, item):
        # Mirrors the firmware: unlink a previously add()ed item (identity match);
        # the next refresh repaints over where it was (the sim always repaints the
        # play rect, so no ghost by construction). The item itself is untouched and
        # can be add()ed again later. ValueError if not in the scene.
        for i, it in enumerate(self._items):
            if it is item:
                del self._items[i]
                del self._kinds[i]
                del self._fixed[i]
                return
        raise ValueError("item not in scene")

    def set_view(self, ox, oy):
        self._ox = ox
        self._oy = oy

    @property
    def view(self):
        return (self._ox, self._oy)

    def invalidate(self):
        pass

    def refresh(self):
        bg = self._background
        fb = _host.fb
        prev = list(fb)                      # for the no-change return value (firmware parity)
        x0 = self._left                      # play rect; the reserved border is left untouched
        x1 = _W - self._right
        y0 = self._top
        y1 = _H - self._bottom
        for y in range(y0, y1):
            row = y * _W
            for x in range(x0, x1):
                fb[row + x] = bg
        clip = (x0, y0, x1, y1)
        for item, kind, fx in zip(self._items, self._kinds, self._fixed):
            vx = 0 if fx else self._ox
            vy = 0 if fx else self._oy
            _draw_item(item, kind, vx, vy, clip)
        _host.present()
        if self._pending_checks:             # first frame with real positions: judge the layers
            for it in self._pending_checks:
                self._check_reserved(it)
            del self._pending_checks[:]
        if fb == prev:                       # firmware parity: a no-change frame returns None
            return None
        return [x0, y0, x1, y1]


def render(display, layers, buffer, x0, y0, x1, y1, *, background=0):
    fb = _host.fb
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(_W, x1)
    cy1 = min(_H, y1)
    for y in range(cy0, cy1):
        drow = y * _W
        for x in range(cx0, cx1):
            fb[drow + x] = background
    clip = (cx0, cy0, cx1, cy1)
    # Mirror the firmware: immediate render handles ALL layer kinds, not just Sprites - so a StripDraw
    # composited via view.text() is a 0-RAM immediate HUD / text screen (no retained buffer).
    for it in layers:
        _draw_item(it, _kind(it), 0, 0, clip)
    # Firmware parity: the C composites the region into `buffer` strip by strip (strip height =
    # len(buffer)//2 // region width), so after the call the buffer holds the LAST strip - the WHOLE
    # region when the buffer covers it. The devtest readback relies on this; keep the copy faithful.
    rw = cx1 - cx0
    if buffer is not None and rw > 0:
        strip_h = (len(buffer) // 2) // rw
        if strip_h < 1:
            raise ValueError("render buffer smaller than one row")
        for sy in range(cy0, cy1, strip_h):
            k = 0
            for y in range(sy, min(sy + strip_h, cy1)):
                drow = y * _W
                for x in range(cx0, cx1):
                    v = fb[drow + x]
                    buffer[k] = v & 0xFF
                    buffer[k + 1] = (v >> 8) & 0xFF
                    k += 2
    _host.present()


def invert(display, on):
    # Hardware colour inversion (INVON/INVOFF). The sim emulates it: present()/_to_image() show the
    # framebuffer's negative while `on`, so InvertFlash is visible in the preview, screenshots and GIFs.
    _host._inverted = bool(on)


def collide(x1, y1, x2, y2, ax1, ay1, ax2=None, ay2=None):
    # Inclusive AABB: boxes collide when they TOUCH (bounce-on-contact game feel). Pass sprite
    # boxes as (x, y, x+w, y+h). Mirrors the firmware. (render is half-open -- different domain:
    # pixels vs hitboxes.)
    if ax2 is None or ay2 is None:            # 6-arg form: box vs the POINT (ax1, ay1)
        return x1 <= ax1 <= x2 and y1 <= ay1 <= y2
    return x1 <= ax2 and ax1 <= x2 and y1 <= ay2 and ay1 <= y2


def raycast(map, mw, mh, posx, posy, lrx, lry, srx, sry, sh, stride, ncols, wcolors, top, bot, col, dist,
            runs=None):
    # Sim implementation of the native picogame.raycast wall-caster (the C DDA primitive on device;
    # like Canvas.mode7, the sim provides the same op in Python). Same 16.16 inputs: pos/leftRay/rayStep
    # are Q16; it reconstructs floats, runs the per-column DDA and fills top/bot (px), col (wire RGB565
    # from wcolors[cell*2+side]) and dist (16.16 perpendicular distance). Used by picogame_ray.Raycaster.
    # Optional `runs` (uint16 buffer, len>=5*ncols as five ncols planes [x0|x1|top|bot|col]): also
    # emit the RLE-merged wall runs (x in pixels = column*stride) and return the run count.
    px = posx / 65536.0
    py = posy / 65536.0
    half = sh >> 1
    ipx = posx >> 16
    ipy = posy >> 16
    for c in range(ncols):
        rdx = (lrx + c * srx) / 65536.0
        rdy = (lry + c * sry) / 65536.0
        mapx = ipx
        mapy = ipy
        ddx = abs(1.0 / rdx) if rdx else 1e30
        ddy = abs(1.0 / rdy) if rdy else 1e30
        if rdx < 0:
            stepx = -1
            sidex = (px - mapx) * ddx
        else:
            stepx = 1
            sidex = (mapx + 1.0 - px) * ddx
        if rdy < 0:
            stepy = -1
            sidey = (py - mapy) * ddy
        else:
            stepy = 1
            sidey = (mapy + 1.0 - py) * ddy
        side = 0
        cell = 1
        for _ in range(64):
            if sidex < sidey:
                sidex += ddx
                mapx += stepx
                side = 0
            else:
                sidey += ddy
                mapy += stepy
                side = 1
            cell = map[mapy * mw + mapx] if (0 <= mapx < mw and 0 <= mapy < mh) else 1
            if cell:
                break
        perp = (sidex - ddx) if side == 0 else (sidey - ddy)
        if perp < 0.01:
            perp = 0.01
        lh = int(sh / perp)
        t = half - (lh >> 1)
        b = t + lh
        if t < 0:
            t = 0
        if b > sh:
            b = sh
        top[c] = t
        bot[c] = b
        ct = cell if (cell * 2 + 1) < len(wcolors) else 1
        col[c] = wcolors[ct * 2 + side]
        dist[c] = int(perp * 65536)
    if runs is not None and ncols > 0:
        cap = len(runs) // 5                      # five uint16 planes (mirrors the C layout)
        n = min(ncols, cap)
        nr = 0
        rstart = 0
        for c in range(1, n + 1):
            if c == n or top[c] != top[rstart] or bot[c] != bot[rstart] or col[c] != col[rstart]:
                runs[nr] = rstart * stride
                runs[cap + nr] = c * stride
                runs[2 * cap + nr] = top[rstart]
                runs[3 * cap + nr] = bot[rstart]
                runs[4 * cap + nr] = col[rstart]
                nr += 1
                rstart = c
        return nr
    return None


# The sim renders in float (CPython), so pseudo-3D primitives take the float path; a game reads
# picogame.FPU to pack its camera/point buffers to match (float here, 16.16 fixed on RP2040).
FPU = 1


# Q15 sine LUT - the SAME 91-entry table as the firmware (pg_sin_q15_quad), so the sim's
# road_edges is bit-identical to the C (golden-tested in selftest_road.py).
_SIN_Q15 = (
    0, 572, 1144, 1715, 2286, 2856, 3425, 3993, 4560, 5126,
    5690, 6252, 6813, 7371, 7927, 8481, 9032, 9580, 10126, 10668,
    11207, 11743, 12275, 12803, 13328, 13848, 14364, 14876, 15383, 15886,
    16383, 16876, 17364, 17846, 18323, 18794, 19260, 19720, 20173, 20621,
    21062, 21497, 21925, 22347, 22762, 23170, 23571, 23964, 24351, 24730,
    25101, 25465, 25821, 26169, 26509, 26841, 27165, 27481, 27788, 28087,
    28377, 28659, 28932, 29196, 29451, 29697, 29934, 30162, 30381, 30591,
    30791, 30982, 31163, 31335, 31498, 31650, 31794, 31927, 32051, 32165,
    32269, 32364, 32448, 32523, 32587, 32642, 32687, 32722, 32747, 32762,
    32767,
)


def _sin_q15(deg):
    deg %= 360
    if deg <= 90:
        return _SIN_Q15[deg]
    if deg <= 180:
        return _SIN_Q15[180 - deg]
    if deg <= 270:
        return -_SIN_Q15[deg - 180]
    return -_SIN_Q15[360 - deg]


def _sin_q15_lerp(deg_q16):
    d0 = deg_q16 >> 16
    frac = deg_q16 & 0xFFFF
    a = _sin_q15(d0)
    return a + (((_sin_q15(d0 + 1) - a) * frac) >> 16)


def _i32(v):
    # int32 wrap - the C accumulators are int32_t and games near the limits must degrade the
    # SAME way in the sim as on the device (wrong pixels, never a different picture per host).
    return ((v + 0x80000000) & 0xFFFFFFFF) - 0x80000000


def road_edges(rl, rr, hw, n, cx0, dist, cfg):
    """Sim of the native pg.road_edges (C: picogame_road_edges): one racing-road frame's
    curve accumulator + integer edge tables in a single call. rl/rr = int16 outputs for
    Canvas.road, hw = int32 Q16 per-row half-widths, cx0 = Q16 screen centre (incl.
    lateral offset), dist = integer world distance, cfg = int32[7] curve/hill config
    [f1_q20, f2_q20, amp1k_q16, amp2k_q16, world_step, curve_step, d_row_off].
    Fixed-point port of the C, same LUT sine - golden-tested (selftest_road.py)."""
    n = min(n, len(rl), len(rr), len(hw))
    if n <= 0 or len(cfg) < 7:
        return
    f1, f2, a1k, a2k = cfg[0], cfg[1], cfg[2], cfg[3]
    wstep, cstep, drow = cfg[4], cfg[5], cfg[6]
    cx = cx0
    ddx = 0
    ck = 0
    cnt = 0
    for i in range(n - 1, -1, -1):
        if cnt == 0:
            d = _i32(dist + (drow - i) * wstep)
            ck = _i32(_i32((_sin_q15_lerp((d * f1) >> 4) * a1k) >> 15)
                      + _i32((_sin_q15_lerp((d * f2) >> 4) * a2k) >> 15))
            cnt = cstep
        cnt -= 1
        ddx = _i32(ddx + ck)
        cx = _i32(cx + ddx)
        h = hw[i]
        vl = _i32(cx - h)
        vr = _i32(cx + h)
        v = (vl >> 16) if vl >= 0 else -((-vl) >> 16)      # trunc-toward-zero, as the C int()
        rl[i] = ((v + 0x8000) & 0xFFFF) - 0x8000           # int16 cast semantics
        v = (vr >> 16) if vr >= 0 else -((-vr) >> 16)
        rr[i] = ((v + 0x8000) & 0xFFFF) - 0x8000


def project(cam, pts, n, out_sx, out_sy):
    """Sim implementation of the native picogame.project batch projector (C on device: float on an
    FPU board, 16.16 fixed on RP2040). Projects `n` world points to screen; a point behind the near
    plane gets sentinel -32768. cam = ex,ey,ez, rx,rz, ux,uy,uz, fx,fy,fz, focal, cx0, cy0, near."""
    ex, ey, ez = cam[0], cam[1], cam[2]
    rx, rz = cam[3], cam[4]
    ux, uy, uz = cam[5], cam[6], cam[7]
    fx, fy, fz = cam[8], cam[9], cam[10]
    focal, cx0, cy0, near = cam[11], cam[12], cam[13], cam[14]
    for i in range(n):
        X = pts[i * 3] - ex
        Y = pts[i * 3 + 1] - ey
        Z = pts[i * 3 + 2] - ez
        cz = X * fx + Y * fy + Z * fz
        if cz < near:
            out_sx[i] = -32768
            out_sy[i] = -32768
            continue
        k = focal / cz
        out_sx[i] = int(cx0 + (X * rx + Z * rz) * k)
        out_sy[i] = int(cy0 - (X * ux + Y * uy + Z * uz) * k)


# ---- procedural value-noise (the engine's noise lives here in the sim; on device
# it's the fast C version in the picogame firmware module). Same algorithm. ----
def _nhash(x, y, seed):
    h = (x * 374761393 + y * 668265263 + seed * 362437) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def _nsmooth(t):
    return t * t * (3.0 - 2.0 * t)


def value2d(x, y, *, seed=0):
    xi = int(_math.floor(x))
    yi = int(_math.floor(y))
    xf = x - xi
    yf = y - yi
    a = _nhash(xi, yi, seed)
    b = _nhash(xi + 1, yi, seed)
    c = _nhash(xi, yi + 1, seed)
    d = _nhash(xi + 1, yi + 1, seed)
    u = _nsmooth(xf)
    v = _nsmooth(yf)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def value1d(x, *, seed=0):
    xi = int(_math.floor(x))
    xf = x - xi
    a = _nhash(xi, 0, seed)
    b = _nhash(xi + 1, 0, seed)
    return a + (b - a) * _nsmooth(xf)


def fbm2d(x, y, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5):
    total = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * value2d(x * freq, y * freq, seed=seed)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm if norm else 0.0


def fbm1d(x, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5):
    total = 0.0
    amp = 1.0
    freq = 1.0
    norm = 0.0
    for _ in range(octaves):
        total += amp * value1d(x * freq, seed=seed)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm if norm else 0.0


# NOTE: on device the canonical value2d/value1d/fbm2d/fbm1d are the FIXED-POINT C impl
# (the float version was retired). Here in the sim they stay float -- the difference is a
# sub-perceptual Q0.16 quantization, and the sim is the PC preview. The old `*_fx` aliases
# were removed along with the public `_fx` names (there's no float to contrast with now).
