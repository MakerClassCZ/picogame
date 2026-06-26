# Desktop simulator implementation of the `picogame` C engine API. Pure Python,
# full-redraw (no dirty-rect needed on a PC), drawing into the host framebuffer.
# Mirrors the C semantics: wire-order RGB565, PAL8/RGB565 bitmaps with frames /
# transparent / flip, anchors, the view offset (camera) + fixed (HUD) layers,
# Tilemap / Particles / Canvas, and collide. Lets games run unchanged on a host.

import math
import _host

RGB565 = 0
PAL8 = 1
RGB444_SUPPORTED = False     # capability flag (mirrors firmware); the desktop sim renders RGB565
W = _host.W
H = _host.H

_KIND_SPRITE = 0
_KIND_TILEMAP = 1
_KIND_PARTICLES = 2
_KIND_CANVAS = 3
_KIND_STRIPDRAW = 4
_SIM_STRIP_H = 8        # emulate the device's banded render so per-strip bugs surface


def rgb565(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


class Bitmap:
    def __init__(self, data, width, height, *, format=RGB565, palette=None,
                 frames=1, stride=0, transparent=None):
        self.data = data
        self.width = width
        self.height = height
        self.format = format
        self.palette = palette
        self.frames = frames
        self.stride = stride if stride else width * frames
        self.transparent = transparent
        self.has_transparent = transparent is not None
        # is RGB565 data stored as 16-bit units (array/list) or raw 2-byte LE?
        self._u16 = not isinstance(data, (bytes, bytearray, memoryview))


def _src_pixel(bm, sx, sy):
    """Return the wire-RGB565 value at (sx, sy) in the atlas, or None if transparent."""
    if bm.format == PAL8:
        idx = bm.data[sy * bm.stride + sx]
        if bm.has_transparent and idx == bm.transparent:
            return None
        if idx >= len(bm.palette):           # parity with the C blitter's per-access clamp (H2)
            idx = 0
        return bm.palette[idx]
    # RGB565
    if bm._u16:
        v = bm.data[sy * bm.stride + sx]
    else:
        off = (sy * bm.stride + sx) * 2
        v = bm.data[off] | (bm.data[off + 1] << 8)
    if bm.has_transparent and v == bm.transparent:
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
    if transpose:                          # cheap 90deg (mirrors the C transpose path); scale 1
        dw, dh = sh, sw                     # footprint swaps
        xs = max(dx0, cx0, 0); ys = max(dy0, cy0, 0)
        xe = min(dx0 + dw, cx1, W); ye = min(dy0 + dh, cy1, H)
        for y in range(ys, ye):
            ly = y - dy0                    # -> source X
            su0 = sw - 1 - ly if flip_x else ly
            for x in range(xs, xe):
                lx = x - dx0                # -> source Y
                sv = sh - 1 - lx if flip_y else lx
                v = _src_pixel_row(bm, sv * bm.stride + fcol, su0)
                if v is not None:
                    _fxput(fb, y * W + x, v, x, y, shadow, flash, dither, tint)
        return
    # destination extent grows with scale; each dest pixel maps back to a source
    # pixel by nearest-neighbour (same technique as PicoLibSDK DrawImgMat, but
    # axis-aligned). scale == 1.0 reduces to the 1:1 path.
    dw = max(1, int(round(sw * scale)))
    dh = max(1, int(round(sh * scale)))
    inv = 1.0 / scale
    cx0, cy0, cx1, cy1 = clip
    x_start = max(dx0, cx0, 0)
    y_start = max(dy0, cy0, 0)
    x_end = min(dx0 + dw, cx1, W)
    y_end = min(dy0 + dh, cy1, H)
    fb = _host.fb
    for y in range(y_start, y_end):
        sy = int((y - dy0) * inv)
        if sy >= sh:
            sy = sh - 1
        if flip_y:
            sy = sh - 1 - sy
        srow = sy * bm.stride + fcol
        drow = y * W
        for x in range(x_start, x_end):
            sx = int((x - dx0) * inv)
            if sx >= sw:
                sx = sw - 1
            if flip_x:
                sx = sw - 1 - sx
            v = _src_pixel_row(bm, srow, sx)
            if v is not None:
                _fxput(fb, drow + x, v, x, y, shadow, flash, dither, tint)


def _src_pixel_row(bm, srow, sx):
    if bm.format == PAL8:
        idx = bm.data[srow + sx]
        if bm.has_transparent and idx == bm.transparent:
            return None
        if idx >= len(bm.palette):           # parity with the C blitter's per-access clamp (H2)
            idx = 0
        return bm.palette[idx]
    if bm._u16:
        v = bm.data[srow + sx]
    else:
        off = (srow + sx) * 2
        v = bm.data[off] | (bm.data[off + 1] << 8)
    if bm.has_transparent and v == bm.transparent:
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
        self.anchor_x = 0.0
        self.anchor_y = 0.0
        self.scale = 1.0          # uniform draw scale (nearest-neighbour)
        self.angle = 0.0          # rotation in degrees (about the anchor); 0 = fast path
        self.shadow = False       # darken-mode: opaque pixels dim the destination (drop shadows / dimming)
        self.flash = None         # flash: opaque pixels drawn as this wire-RGB565 colour
        self.dither = 0           # 0=opaque .. 16=invisible: Bayer dither -> fake transparency
        self.tint = None          # tint: multiply opaque pixels by this colour (keeps shading)
        self.transpose = False    # swap x/y -> cheap 90deg (with flips = all 8 orientations)
        self.data = None

    @property
    def x(self):
        return int(math.floor(self._x))

    @x.setter
    def x(self, v):
        self._x = float(v)

    @property
    def y(self):
        return int(math.floor(self._y))

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

    @property
    def anchor(self):
        return (self.anchor_x, self.anchor_y)

    @anchor.setter
    def anchor(self, t):
        self.anchor_x, self.anchor_y = t[0], t[1]

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
        w = int(round(w * self.scale))       # anchor is a fraction of the SCALED size
        h = int(round(h * self.scale))
        return (self.x - int(self.anchor_x * w), self.y - int(self.anchor_y * h))

    def _bounds(self):
        # drawn box (x1, y1, x2, y2); x2/y2 = far corner (tl + size). Mirrors the C
        # picogame_sprite_aabb angle==0 path: scale + transpose, anchor offset. (The sim
        # ignores arbitrary rotation here; the device aabb pads a rotated box.)
        w = self.bitmap.width if self.bitmap else 0
        h = self.bitmap.height if self.bitmap else 0
        sw = int(w * self.scale)
        sh = int(h * self.scale)
        if self.transpose and self.scale == 1.0:
            sw, sh = sh, sw
        tx = self.x - int(self.anchor_x * sw)
        ty = self.y - int(self.anchor_y * sh)
        return (tx, ty, tx + sw, ty + sh)

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
    a = math.radians(ang_deg)
    cs, sn = math.cos(a), math.sin(a)
    # forward-transform the 4 corners -> screen bounding box
    xs, ys = [], []
    for (u, v) in ((0, 0), (sw, 0), (0, sh), (sw, sh)):
        du, dv = (u - pivx) * scale, (v - pivy) * scale
        xs.append(px + du * cs - dv * sn)
        ys.append(py + du * sn + dv * cs)
    cx0, cy0, cx1, cy1 = clip
    x0 = max(int(math.floor(min(xs))), cx0, 0)
    x1 = min(int(math.ceil(max(xs))), cx1, W)
    y0 = max(int(math.floor(min(ys))), cy0, 0)
    y1 = min(int(math.ceil(max(ys))), cy1, H)
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
                    _fxput(fb, Y * W + X, val, X, Y, shadow, flash, dither, tint)


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
                     s.x + vx, s.y + vy, s.anchor_x * w, s.anchor_y * h, s.scale, s.angle,
                     s.shadow, s.flash, s.dither, s.tint)


class Tilemap:
    def __init__(self, tileset, cols, rows):
        self.tileset = tileset
        self.map_w = cols
        self.map_h = rows
        self.grid = bytearray(cols * rows)
        self.orient = None        # lazy: bit0 flipX, bit1 flipY, bit2 transpose per cell
        self.ox = 0
        self.oy = 0

    # read-only getters mirroring the firmware (position via move(); size from ctor)
    @property
    def x(self):
        return self.ox

    @property
    def y(self):
        return self.oy

    @property
    def cols(self):
        return self.map_w

    @property
    def rows(self):
        return self.map_h

    def tile(self, tx, ty, value=None, *, flip_x=False, flip_y=False, transpose=False):
        if tx < 0 or tx >= self.map_w or ty < 0 or ty >= self.map_h:
            return 0
        if value is None:
            return self.grid[ty * self.map_w + tx]
        off = ty * self.map_w + tx
        self.grid[off] = value
        o = (1 if flip_x else 0) | (2 if flip_y else 0) | (4 if transpose else 0)
        if o and self.orient is None:
            self.orient = bytearray(self.map_w * self.map_h)
        if self.orient is not None:
            self.orient[off] = o
        return None

    def fill(self, v):
        for i in range(len(self.grid)):
            self.grid[i] = v
            if self.orient is not None:
                self.orient[i] = 0

    def move(self, x, y):
        self.ox = x
        self.oy = y

    def _draw(self, vx, vy, clip):
        tw, th = self.tileset.width, self.tileset.height
        for ty in range(self.map_h):
            for tx in range(self.map_w):
                off = ty * self.map_w + tx
                v = self.grid[off]
                o = self.orient[off] if self.orient is not None else 0
                _blit(self.tileset, self.ox + tx * tw + vx, self.oy + ty * th + vy,
                      v, bool(o & 1), bool(o & 2), clip, 1.0, False, None, 0, None, bool(o & 4))


class Particles:
    def __init__(self, capacity, size=1, gravity=0.0, fade=False):
        self.cap = capacity
        self.size = size
        self.gravity = gravity
        self.fade = fade
        self.px = []
        self.py = []
        self.vx = []
        self.vy = []
        self.life = []
        self.life0 = []
        self.color = []

    def emit(self, x, y, count, speed=1, life=30, color=0xFFFF):
        if count < 0:
            raise ValueError("count must be >= 0")
        if speed < 0:
            raise ValueError("speed must be >= 0")
        if life <= 0:
            raise ValueError("life must be > 0")
        import random
        for _ in range(count):
            if len(self.px) >= self.cap:
                break
            self.px.append(float(x))
            self.py.append(float(y))
            self.vx.append(random.uniform(-speed, speed))
            self.vy.append(random.uniform(-speed, speed))
            self.life.append(life)
            self.life0.append(max(1, life))
            self.color.append(color)

    def tick(self):
        i = 0
        while i < len(self.px):
            self.px[i] += self.vx[i]
            self.py[i] += self.vy[i]
            self.vy[i] += self.gravity
            if self.life[i] <= 0:
                for a in (self.px, self.py, self.vx, self.vy, self.life, self.life0, self.color):
                    a[i] = a[-1]
                    a.pop()
                continue
            self.life[i] -= 1
            i += 1

    def clear(self):
        for a in (self.px, self.py, self.vx, self.vy, self.life, self.life0, self.color):
            del a[:]

    def _draw(self, vx, vy, clip):
        fb = _host.fb
        sz = self.size
        cx0, cy0, cx1, cy1 = clip
        for i in range(len(self.px)):
            x0 = int(self.px[i]) + vx
            y0 = int(self.py[i]) + vy
            c = self.color[i]
            if self.fade:
                c = _scale_wire(c, self.life[i], self.life0[i])
            for yy in range(max(y0, cy0, 0), min(y0 + sz, cy1, H)):
                drow = yy * W
                for xx in range(max(x0, cx0, 0), min(x0 + sz, cx1, W)):
                    fb[drow + xx] = c


def _scale_wire(wire, num, den):
    c = ((wire >> 8) | (wire << 8)) & 0xFFFF
    r = ((c >> 11) & 0x1F) * num // den
    g = ((c >> 5) & 0x3F) * num // den
    b = (c & 0x1F) * num // den
    out = (r << 11) | (g << 5) | b
    return ((out >> 8) | (out << 8)) & 0xFFFF


class Canvas:
    def __init__(self, width, height, *, transparent=None, buffer=None):
        # `buffer` (external arena slice) is honoured on device for RAM; the sim has
        # plenty of RAM so it just allocates its own list and ignores it.
        self.w = width
        self.h = height
        self.transparent = transparent
        self.has_transparent = transparent is not None
        self.data = [0] * (width * height)
        self.x = 0
        self.y = 0

    # read-only size getters mirroring the firmware (internals use w/h)
    @property
    def width(self):
        return self.w

    @property
    def height(self):
        return self.h

    def move(self, x, y):
        self.x = x
        self.y = y

    def clear(self, color):
        for i in range(len(self.data)):
            self.data[i] = color

    def pixel(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.data[y * self.w + x] = color

    def fill_rect(self, x, y, w, h, color):
        for yy in range(max(0, y), min(self.h, y + h)):
            base = yy * self.w
            for xx in range(max(0, x), min(self.w, x + w)):
                self.data[base + xx] = color

    def blit(self, bm, x, y, frame=0, flip_x=False, flip_y=False):
        fw, fh = bm.width, bm.height
        for ry in range(fh):
            cy = y + ry
            if not (0 <= cy < self.h):
                continue
            sy = (fh - 1 - ry) if flip_y else ry
            base = cy * self.w
            for rx in range(fw):
                cx = x + rx
                if not (0 <= cx < self.w):
                    continue
                sx = (fw - 1 - rx) if flip_x else rx
                v = _src_pixel(bm, frame * fw + sx, sy)
                if v is not None:
                    self.data[base + cx] = v

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
            span = int(math.sqrt(max(0, r * r - dy * dy)))
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
            out = int(math.sqrt(max(0, r * r - dy * dy)))
            if abs(dy) <= inner:
                ins = int(math.sqrt(max(0, inner * inner - dy * dy)))
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

    def triangle(self, x0, y0, x1, y1, x2, y2, color):
        self.line(x0, y0, x1, y1, color)
        self.line(x1, y1, x2, y2, color)
        self.line(x2, y2, x0, y0, color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        for dy in range(-ry, ry + 1):
            span = int(rx * math.sqrt(max(0.0, 1.0 - (dy * dy) / float(ry * ry)))) if ry else 0
            self.fill_rect(cx - span, cy + dy, 2 * span + 1, 1, color)

    def ellipse(self, cx, cy, rx, ry, color):
        steps = max(8, int(6.2832 * max(rx, ry)))
        for i in range(steps):
            a = 6.2832 * i / steps
            self.pixel(cx + int(rx * math.cos(a)), cy + int(ry * math.sin(a)), color)

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
        key = self.transparent
        for yy in range(max(oy, cy0, 0), min(oy + self.h, cy1, H)):
            srow = (yy - oy) * self.w
            drow = yy * W
            for xx in range(max(ox, cx0, 0), min(ox + self.w, cx1, W)):
                v = self.data[srow + (xx - ox)]
                if self.has_transparent and v == key:
                    continue
                fb[drow + xx] = v


class StripDraw:
    """Immediate-mode draw layer: holds NO pixel buffer. Each refresh, for every
    render strip overlapping its rect, calls ``callback(view, vx, vy, vw, vh)`` with a
    Canvas ``view`` pointing at the live strip -- so you draw straight into the frame
    (zero RAM vs a Canvas's w*h*2 bytes). view-local (0,0) is screen (vx, vy). Its rect
    is repainted every frame: use it for animated / scanline content (pseudo-3D,
    gradients, procedural backgrounds), not static art. Mirrors the firmware type."""

    def __init__(self, callback, x=0, y=0, width=0, height=0):
        self.callback = callback
        self.x = x
        self.y = y
        self.w = width
        self.h = height
        self._view = Canvas(1, 1)        # reused; data/w/h repointed per strip

    # read/write rect size mirroring the firmware properties (internals use w/h)
    @property
    def width(self):
        return self.w

    @width.setter
    def width(self, v):
        self.w = v

    @property
    def height(self):
        return self.h

    @height.setter
    def height(self, v):
        self.h = v

    def _draw(self, vx, vy, clip):
        fb = _host.fb
        cx0, cy0, cx1, cy1 = clip
        rx, ry = self.x + vx, self.y + vy
        x_lo, x_hi = max(rx, cx0, 0), min(rx + self.w, cx1, W)
        y_lo, y_hi = max(ry, cy0, 0), min(ry + self.h, cy1, H)
        if x_lo >= x_hi or y_lo >= y_hi:
            return
        rw = x_hi - x_lo
        view = self._view
        view.w = rw
        view.has_transparent = False
        view.x = view.y = 0
        sy = y_lo
        while sy < y_hi:
            sh = min(_SIM_STRIP_H, y_hi - sy)
            view.h = sh
            # The strip already holds the background + lower layers (as on device):
            # seed the view from fb, let the callback draw over it, copy back.
            data = [0] * (rw * sh)
            for ly in range(sh):
                drow = (sy + ly) * W + x_lo
                srow = ly * rw
                for lx in range(rw):
                    data[srow + lx] = fb[drow + lx]
            view.data = data
            self.callback(view, x_lo, sy, rw, sh)
            for ly in range(sh):
                drow = (sy + ly) * W + x_lo
                srow = ly * rw
                for lx in range(rw):
                    fb[drow + lx] = data[srow + lx]
            sy += sh


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
    raise TypeError("expected Sprite/Tilemap/Particles/Canvas/StripDraw")


def _draw_item(item, kind, vx, vy, clip):
    if kind == _KIND_SPRITE:
        _draw_sprite(item, vx, vy, clip)
    elif kind == _KIND_TILEMAP:
        item._draw(vx, vy, clip)
    elif kind == _KIND_PARTICLES:
        item._draw(vx, vy, clip)
    else:
        item._draw(vx, vy, clip)


class Display:
    def __init__(self, busdisplay, *, rgb444=False):
        self.display = busdisplay
        self.rgb444 = rgb444        # honoured on device (COLMOD + pack); the sim renders RGB565

    def render(self, sprites, buffer_a, buffer_b, x0, y0, x1, y1, *, background=0):
        # Mirrors the firmware fast Display.render (double-buffered DMA on device);
        # the sim just draws the region and presents (buffering is invisible here).
        render(self.display, sprites, buffer_a, x0, y0, x1, y1, background=background)


_FULL = (0, 0, W, H)


class Scene:
    def __init__(self, display, buffer_a, buffer_b, *, background=0,
                 top=0, bottom=0, left=0, right=0):
        self.display = display
        self.background = background
        self.items = []
        self.kinds = []
        self.fixed = []
        self.ox = 0
        self.oy = 0
        # reserved border insets; scene renders only [left, W-right) x [top, H-bottom)
        self.top = top
        self.bottom = bottom
        self.left = left
        self.right = right

    def add(self, item, *, fixed=False):
        self.items.append(item)
        self.kinds.append(_kind(item))
        self.fixed.append(fixed)
        return item

    def add_all(self, items):
        for it in items:
            self.add(it)

    def set_view(self, ox, oy):
        self.ox = ox
        self.oy = oy

    @property
    def view(self):
        return (self.ox, self.oy)

    def invalidate(self):
        pass

    def refresh(self):
        bg = self.background
        fb = _host.fb
        x0 = self.left                      # play rect; the reserved border is left untouched
        x1 = W - self.right
        y0 = self.top
        y1 = H - self.bottom
        for y in range(y0, y1):
            row = y * W
            for x in range(x0, x1):
                fb[row + x] = bg
        clip = (x0, y0, x1, y1)
        for item, kind, fx in zip(self.items, self.kinds, self.fixed):
            vx = 0 if fx else self.ox
            vy = 0 if fx else self.oy
            _draw_item(item, kind, vx, vy, clip)
        _host.present()
        return [x0, y0, x1, y1]


def render(display, items, buffer, x0, y0, x1, y1, *, background=0):
    fb = _host.fb
    cx0 = max(0, x0)
    cy0 = max(0, y0)
    cx1 = min(W, x1)
    cy1 = min(H, y1)
    for y in range(cy0, cy1):
        drow = y * W
        for x in range(cx0, cx1):
            fb[drow + x] = background
    clip = (cx0, cy0, cx1, cy1)
    for it in items:
        _draw_sprite(it, 0, 0, clip)
    _host.present()


def invert(display, on):
    # Hardware colour inversion (INVON/INVOFF). The sim emulates it: present()/_to_image() show the
    # framebuffer's negative while `on`, so InvertFlash is visible in the preview, screenshots and GIFs.
    _host._inverted = bool(on)


def collide(*a):
    # Inclusive AABB: boxes collide when they TOUCH (bounce-on-contact game feel). Pass sprite
    # boxes as (x, y, x+w, y+h). Mirrors the firmware. (render is half-open -- different domain:
    # pixels vs hitboxes.)
    if len(a) == 8:
        x1, y1, x2, y2, ax1, ay1, ax2, ay2 = a
        return x1 <= ax2 and ax1 <= x2 and y1 <= ay2 and ay1 <= y2
    x1, y1, x2, y2, px, py = a
    return x1 <= px <= x2 and y1 <= py <= y2


# ---- procedural value-noise (the engine's noise lives here in the sim; on device
# it's the fast C version in the picogame firmware module). Same algorithm. ----
def _nhash(x, y, seed):
    h = (x * 374761393 + y * 668265263 + seed * 362437) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def _nsmooth(t):
    return t * t * (3.0 - 2.0 * t)


def value2d(x, y, *, seed=0):
    xi = int(math.floor(x))
    yi = int(math.floor(y))
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
    xi = int(math.floor(x))
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
        total += amp * value2d(x * freq, y * freq, seed)
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
        total += amp * value1d(x * freq, seed)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm if norm else 0.0


# NOTE: on device the canonical value2d/value1d/fbm2d/fbm1d are the FIXED-POINT C impl
# (the float version was retired). Here in the sim they stay float -- the difference is a
# sub-perceptual Q0.16 quantization, and the sim is the PC preview. The old `*_fx` aliases
# were removed along with the public `_fx` names (there's no float to contrast with now).
