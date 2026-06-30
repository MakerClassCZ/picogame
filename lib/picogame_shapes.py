# picogame_shapes: generators that BAKE single-colour PAL8 Bitmaps (rect/circle/ring/atlas/...),
# so a game gets placeholder sprite/tile art in code - no PNG assets, no firmware. NOT the C
# Canvas (which draws into a LIVE surface): shapes returns a reusable Bitmap for a Sprite/Tilemap.
# Index 0 = transparent, 1 = colour.
#
#   import picogame_shapes as shp
#   ball = shp.circle(8, pg.rgb565(255, 255, 0))
#   tiles = shp.atlas([empty, wall, dot], 10, 10, pg.rgb565(40, 90, 200))
#   ship = shp.poly_frames(16, [(0,-7),(5,6),(-5,6)], 16, pg.rgb565(200,220,255))

import array
import math
import picogame as pg


def _bm(data, w, h, color, frames=1, stride=None, transparent=0):
    stride = stride if stride is not None else w * frames
    pal = array.array("H", [pg.rgb565(0, 0, 0), color])
    return pg.Bitmap(data, w, h, format=pg.PAL8, palette=pal,
                     frames=frames, stride=stride, transparent=transparent)


def rect(w, h, color):
    """A filled w x h rectangle."""
    return _bm(bytearray(b"\x01" * (w * h)), w, h, color)


def circle(d, color):
    """A filled disc of diameter d."""
    data = bytearray(d * d)
    r = (d - 1) / 2.0
    rr = (r + 0.4) ** 2
    for y in range(d):
        for x in range(d):
            if (x - r) ** 2 + (y - r) ** 2 <= rr:
                data[y * d + x] = 1
    return _bm(data, d, d, color)


def ring(d, color, thickness=2):
    """A circle outline of diameter d."""
    data = bytearray(d * d)
    r = (d - 1) / 2.0
    outer = (r + 0.4) ** 2
    inner = (r - thickness + 0.4) ** 2
    for y in range(d):
        for x in range(d):
            dist = (x - r) ** 2 + (y - r) ** 2
            if inner <= dist <= outer:
                data[y * d + x] = 1
    return _bm(data, d, d, color)


def from_mask(mask, color):
    """mask: list of strings, '#'/'X'/'1' = set. Returns a bitmap sized to it."""
    h = len(mask)
    w = max(len(r) for r in mask)
    data = bytearray(w * h)
    for y, row in enumerate(mask):
        for x, ch in enumerate(row):
            if ch in "#X1":
                data[y * w + x] = 1
    return _bm(data, w, h, color)


def atlas(frames_data, w, h, color):
    """Pack a list of w*h index buffers (0/1) into a horizontal multi-frame Bitmap.
    Replaces the hand-rolled `for f/for y/for x` packing loop in every game."""
    n = len(frames_data)
    stride = w * n
    data = bytearray(stride * h)
    for f, src in enumerate(frames_data):
        for y in range(h):
            base = y * stride + f * w
            srow = y * w
            for x in range(w):
                if src[srow + x]:
                    data[base + x] = 1
    return _bm(data, w, h, color, frames=n, stride=stride)


def color_frames(w, h, colors):
    """A multi-frame w x h bitmap where frame i is a solid fill of colors[i] -
    e.g. a tileset of solid coloured cells, or a gem sheet where frame = colour.
    (match3 / platformer built this by hand.) Index 0 stays transparent."""
    import array as _array
    n = len(colors)
    stride = w * n
    data = bytearray(stride * h)
    for f in range(n):
        idx = f + 1
        for y in range(h):
            base = y * stride + f * w
            for x in range(w):
                data[base + x] = idx
    pal = _array.array("H", [pg.rgb565(0, 0, 0)] + list(colors))
    return pg.Bitmap(data, w, h, format=pg.PAL8, palette=pal,
                     frames=n, stride=stride, transparent=0)


def tileset_colors(w, h, colors):
    """A tileset bitmap: frame 0 = EMPTY (transparent), frame i = a solid fill of
    colors[i-1]. So a Tilemap reads tile value 0 as empty and 1..N as coloured
    tiles - the 'empty + N solid bricks/dots' sheet arkanoid/pacman/digdug each
    built by hand. (Differs from color_frames, whose frame 0 is already a colour.)"""
    import array as _array
    n = len(colors)
    frames = n + 1
    stride = w * frames
    data = bytearray(stride * h)
    for f in range(1, frames):                  # frame 0 left all-zero (transparent)
        for y in range(h):
            base = y * stride + f * w
            for x in range(w):
                data[base + x] = f
    pal = _array.array("H", [pg.rgb565(0, 0, 0)] + list(colors))
    return pg.Bitmap(data, w, h, format=pg.PAL8, palette=pal,
                     frames=frames, stride=stride, transparent=0)


def poly_frames(size, points, nframes, color, fill=True):
    """Bake `nframes` rotations of a polygon (points around centre, +y down) into a
    size x size multi-frame atlas - the engine has no runtime rotation, so this is
    the 'pre-rotated frames' pattern for asteroids/ships/turrets."""
    c = size / 2.0
    frames = []
    for f in range(nframes):
        ang = f * 2.0 * math.pi / nframes
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(c + (px * ca - py * sa), c + (px * sa + py * ca)) for (px, py) in points]
        buf = bytearray(size * size)
        if fill:
            _fill_poly(buf, size, pts)
        else:
            _stroke_poly(buf, size, pts)
        frames.append(buf)
    return atlas(frames, size, size, color)


def _fill_poly(buf, size, pts):
    n = len(pts)
    for y in range(size):
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (x2 - x1) * (y - y1) / (y2 - y1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            a = max(0, int(xs[k]))
            b = min(size - 1, int(xs[k + 1]))
            for x in range(a, b + 1):
                buf[y * size + x] = 1


def _stroke_poly(buf, size, pts):
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        steps = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
        for s in range(steps + 1):
            x = int(x1 + (x2 - x1) * s / steps)
            y = int(y1 + (y2 - y1) * s / steps)
            if 0 <= x < size and 0 <= y < size:
                buf[y * size + x] = 1
