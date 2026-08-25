#!/usr/bin/env python3
# Explanatory diagrams for the concept pages:
#   /concepts/how-it-works/  -> howitworks_dirtyrect.png, howitworks_loop.png
#   /concepts/drawing-paths/ -> drawingpaths_compositor.png, drawingpaths_layers.png
# Plain PIL, no engine — clean dark diagrams matching the site theme.  python3 gen_concepts.py
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(__file__)
BG    = (18, 20, 32)
BOX   = (32, 36, 56)
BOX2  = (26, 30, 48)
EDGE  = (70, 78, 110)
FG    = (232, 234, 245)
MUTE  = (150, 158, 185)
BLUE  = (96, 156, 235)
GREEN = (70, 210, 130)
GOLD  = (240, 200, 90)
RED   = (228, 96, 100)
DIM   = (44, 48, 70)

def font(sz, bold=False):
    base = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try: return ImageFont.truetype(base, sz)
    except Exception: return ImageFont.load_default()
def mono(sz):
    try: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", sz)
    except Exception: return ImageFont.load_default()

F   = font(14); FB = font(14, True); FS = font(11); FSB = font(11, True); FT = font(17, True); M = mono(12)

def rbox(d, x, y, w, h, r=8, fill=BOX, edge=EDGE, ew=1):
    d.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill, outline=edge, width=ew)

def ctext(d, cx, cy, s, fnt=F, fill=FG):
    l, t, rr, b = d.textbbox((0, 0), s, font=fnt)
    d.text((cx - (rr - l) / 2, cy - (b - t) / 2 - t), s, font=fnt, fill=fill)

def ltext(d, x, y, s, fnt=F, fill=FG):
    d.text((x, y), s, font=fnt, fill=fill)

def arrow(d, x0, y0, x1, y1, color=BLUE, w=3, head=8):
    d.line([x0, y0, x1, y1], fill=color, width=w)
    import math
    a = math.atan2(y1 - y0, x1 - x0)
    for s in (0.5, -0.5):
        d.line([x1, y1, x1 - head * math.cos(a - s), y1 - head * math.sin(a - s)], fill=color, width=w)


# ---------------------------------------------------------------- 1. dirty-rect
def dirtyrect():
    W, H = 660, 300
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    ctext(d, W // 2, 20, "You change what moved — refresh() redraws only that", FT, FG)
    # a mock screen
    sx, sy, sw, sh = 40, 55, 300, 210
    rbox(d, sx, sy, sw, sh, r=6, fill=(20, 26, 52), edge=EDGE)
    # dim static background bits
    for (bx, by, bw, bh) in [(20, 20, 60, 18), (200, 30, 70, 14), (30, 160, 250, 30)]:
        d.rounded_rectangle([sx+bx, sy+by, sx+bx+bw, sy+by+bh], radius=4, fill=DIM)
    d.text((sx + 12, sy + 12), "static background — untouched", font=FS, fill=MUTE)
    # the ball: old (ghost) + new (bright) + the dirty rect around both
    oldx, newx, by = sx + 120, sx + 170, sy + 110
    d.ellipse([oldx-14, by-14, oldx+14, by+14], fill=(60, 66, 96))       # ghost old pos
    d.ellipse([newx-14, by-14, newx+14, by+14], fill=GOLD)               # new pos
    # dirty rect enclosing both
    dr = [oldx-20, by-20, newx+20, by+20]
    for i in range(dr[0], dr[2], 7):                                      # dashed rect
        d.line([i, dr[1], i+4, dr[1]], fill=GREEN, width=2); d.line([i, dr[3], i+4, dr[3]], fill=GREEN, width=2)
    for i in range(dr[1], dr[3], 7):
        d.line([dr[0], i, dr[0], i+4], fill=GREEN, width=2); d.line([dr[2], i, dr[2], i+4], fill=GREEN, width=2)
    d.text((sx + 90, sy + 175), "ball.x += 3", font=M, fill=FG)
    # right: explanation column
    ex = 380
    rbox(d, ex, 70, 240, 60, fill=BOX)
    ltext(d, ex+14, 82, "The dirty rectangle", FSB, GREEN)
    ltext(d, ex+14, 102, "old + new position of what moved", FS, MUTE)
    rbox(d, ex, 145, 240, 55, fill=BOX)
    ltext(d, ex+14, 156, "Only this region is redrawn", FSB, FG)
    ltext(d, ex+14, 176, "and sent to the display", FS, MUTE)
    rbox(d, ex, 215, 240, 55, fill=BOX)
    ltext(d, ex+14, 226, "Nothing moved?", FSB, FG)
    ltext(d, ex+14, 246, "nothing is sent at all", FS, MUTE)
    arrow(d, sx + sw + 4, by, ex - 6, 100, color=GREEN)
    im.save(os.path.join(HERE, "howitworks_dirtyrect.png")); print("dirtyrect", im.size)


# ---------------------------------------------------------------- 2. game loop
def loop():
    W, H = 660, 190
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    ctext(d, W // 2, 18, "The game loop — the same four steps every frame", FT, FG)
    steps = [("1  poll()", "read input", BLUE),
             ("2  update", "move, rules, spawn", GOLD),
             ("3  refresh()", "draw what changed", GREEN),
             ("4  tick()", "cap the framerate", MUTE)]
    n = len(steps); bw, bh, gap = 130, 66, 22
    total = n * bw + (n - 1) * gap
    x0 = (W - total) // 2; y = 60
    for i, (t, s, c) in enumerate(steps):
        x = x0 + i * (bw + gap)
        rbox(d, x, y, bw, bh, fill=BOX, edge=c, ew=2)
        ctext(d, x + bw // 2, y + 22, t, FB, c)
        ctext(d, x + bw // 2, y + 44, s, FS, MUTE)
        if i < n - 1:
            arrow(d, x + bw + 3, y + bh // 2, x + bw + gap - 3, y + bh // 2, color=EDGE, w=2)
    # loop-back arrow under the row
    ly = y + bh + 20
    d.line([x0 + total - bw // 2, y + bh, x0 + total - bw // 2, ly], fill=EDGE, width=2)
    d.line([x0 + total - bw // 2, ly, x0 + bw // 2, ly], fill=EDGE, width=2)
    arrow(d, x0 + bw // 2, ly, x0 + bw // 2, y + bh + 3, color=EDGE, w=2)
    ctext(d, W // 2, ly + 1, " repeat ", FS, MUTE)
    im.save(os.path.join(HERE, "howitworks_loop.png")); print("loop", im.size)


# ---------------------------------------------------------------- 3. compositor
def compositor():
    W, H = 680, 300
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    ctext(d, W // 2, 18, "One compositor, two output backends", FT, FG)
    # source
    rbox(d, 30, 120, 150, 60, fill=BOX, edge=GOLD, ew=2)
    ctext(d, 105, 140, "dirty region", FB, GOLD); ctext(d, 105, 160, "(what changed)", FS, MUTE)
    # compositor
    rbox(d, 220, 115, 130, 70, fill=BOX, edge=BLUE, ew=2)
    ctext(d, 285, 138, "layer", FB, BLUE); ctext(d, 285, 158, "compositor", FB, BLUE)
    arrow(d, 182, 150, 218, 150, color=EDGE)
    # backend A: SPI strips
    rbox(d, 400, 55, 250, 90, fill=BOX2, edge=GREEN)
    ltext(d, 414, 64, "SPI panel", FSB, GREEN)
    for i in range(4):                                          # horizontal strips
        yy = 86 + i * 13
        d.rounded_rectangle([414, yy, 470, yy + 9], radius=2, fill=GREEN if i == 1 else DIM)
    ltext(d, 482, 92, "walks dirty region in", FS, MUTE)
    ltext(d, 482, 108, "horizontal strips →", FS, MUTE)
    ltext(d, 482, 124, "sends them to the panel", FS, MUTE)
    arrow(d, 352, 135, 398, 100, color=EDGE)
    # backend B: framebuffer
    rbox(d, 400, 160, 250, 110, fill=BOX2, edge=GOLD)
    ltext(d, 414, 169, "Scanout framebuffer (Fruit Jam)", FSB, GOLD)
    ltext(d, 414, 192, "composites straight into the buffer:", FS, MUTE)
    rbox(d, 414, 212, 110, 46, fill=DIM); ctext(d, 469, 226, "16-bit", FSB, FG); ctext(d, 469, 244, "RGB565", FS, MUTE)
    rbox(d, 532, 212, 110, 46, fill=DIM); ctext(d, 587, 226, "8-bit", FSB, FG); ctext(d, 587, 244, "RGB332 (640×480)", FS, MUTE)
    arrow(d, 352, 165, 398, 200, color=EDGE)
    im.save(os.path.join(HERE, "drawingpaths_compositor.png")); print("compositor", im.size)


# ---------------------------------------------------------------- 4. layer kinds + RAM
def layers():
    W, H = 760, 300
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    ctext(d, W // 2, 18, "Five layer kinds — and the RAM they retain", FT, FG)
    rows = [("Sprite",   "the bitmap: PAL8 w·h  /  RGB565 w·h·2", GOLD, 0.55),
            ("Tilemap",  "cols·rows (1 B/cell) + tileset — cheap", GREEN, 0.28),
            ("Canvas",   "w·h·2 RETAINED — static, reused panel", RED, 0.85),
            ("StripDraw","0 retained bytes — dynamic HUD / full-frame", BLUE, 0.05),
            ("Particles","a fixed pool — sparks, trails, pops", MUTE, 0.2)]
    y = 52; rh = 44; lx = 30; barx = 150; barw = 250
    for name, desc, c, frac in rows:
        rbox(d, lx, y, 110, rh - 8, fill=BOX, edge=c, ew=2)
        ctext(d, lx + 55, y + (rh - 8) // 2, name, FSB, c)
        # RAM bar
        d.rounded_rectangle([barx, y + 6, barx + barw, y + rh - 14], radius=4, fill=DIM)
        wfill = max(6, int(barw * frac))
        d.rounded_rectangle([barx, y + 6, barx + wfill, y + rh - 14], radius=4, fill=c)
        ltext(d, barx + barw + 12, y + 8, desc, FS, MUTE)
        y += rh
    ltext(d, barx, y + 2, "← less RAM", FS, MUTE)
    ltext(d, barx + barw - 60, y + 2, "more RAM →", FS, MUTE)
    im.save(os.path.join(HERE, "drawingpaths_layers.png")); print("layers", im.size)


dirtyrect(); loop(); compositor(); layers()
