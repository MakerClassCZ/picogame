# picogame FX demo - try the engine + helper effects directly on the PicoPad.
#   sprite.flash (native)   A: the creature flashes white on a hit
#   sprite.dither (native)  X cycles the creature through dither (translucent) ...
#   sprite.tint (native)    ... -> tint red -> tint blue (coloured, keeps shading) ...
#   sprite.transpose (native) ... -> 90deg rotation (cheap, no shimmer)
#   Tilemap orientation     background = ONE tile drawn in many orientations (flip + 90deg)
#   picogame_palette.cycle  animated "water" band (palette cycling, ~0 extra art)
#   picogame_fx.Shake       B: trauma screen shake
#   picogame_fx.Fade        Y: dither fade-out then fade-in (a scene transition)
#   picogame_rand           A also bursts randomly-coloured stars that dither-fade out
#   arrows                  move the creature
#
# Needs the flash/dither/tint/transpose firmware (built 2026-06). Copy as code.py + picogame_*.
# Try in the sim:  python3 sim/run.py examples/picogame_fxdemo.py --backend pygame

import math
import array
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shapes
import picogame_ui as ui
import picogame_fx as fx
import picogame_rand as rnd
import picogame_palette as palette
import picogame_pool as pool

W, H = board.DISPLAY.width, board.DISPLAY.height
BAR = 16
WATER_H = 22
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(24, 26, 40), top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
R = rnd.Rand(1234)


def make_pal8(w, h, fill):
    """tiny helper: build a 1-frame PAL8 Bitmap from a (palette, index-grid) the caller fills."""
    data = bytearray(w * h)
    pal = fill(data, w, h)
    return pg.Bitmap(data, w, h, format=pg.PAL8, palette=array.array("H", pal),
                     frames=1, stride=w, transparent=0)


# --- background TILEMAP: one asymmetric "corner" tile, drawn in many orientations ---
T = 16
def _corner(data, w, h):
    for y in range(h):
        for x in range(w):
            data[y * w + x] = 1 if y < 5 else (2 if x < 5 else 0)   # L hugging top-left (asymmetric)
    return [pg.rgb565(0, 0, 0), pg.rgb565(70, 90, 150), pg.rgb565(110, 60, 120)]
corner = make_pal8(T, T, _corner)
COLS, ROWS = W // T, (H - BAR - WATER_H) // T
bg = pg.Tilemap(corner, COLS, ROWS)
bg.move(0, BAR)
# pinwheel: each 2x2 block shows 4 orientations (incl. 90deg transpose) -> rotation is obvious
ORIENTS = [(False, False, False), (False, False, True),    # normal, transpose(90)
           (True, True, False), (True, True, True)]         # 180, transpose+180
for ty in range(ROWS):
    for tx in range(COLS):
        fxx, fyy, trr = ORIENTS[(tx & 1) + (ty & 1) * 2]
        bg.tile(tx, ty, 0, flip_x=fxx, flip_y=fyy, transpose=trr)
scene.add(bg)

# --- animated WATER band: a PAL8 bar whose palette indices 1..6 CYCLE (flowing) ---
def _water(data, w, h):
    for y in range(h):
        for x in range(w):
            data[y * w + x] = 1 + ((x // 5 + y // 2) % 6)        # diagonal bands of indices 1..6
    return [pg.rgb565(0, 0, 0)] + [pg.rgb565(20 + i * 12, 90 + i * 18, 180 + i * 12) for i in range(6)]
water_bmp = make_pal8(W, WATER_H, _water)
water = pg.Sprite(water_bmp, 0, H - WATER_H)
scene.add(water)

# --- two orbiting GHOSTS: permanently dithered (live translucency) ---
GHOST = shapes.circle(26, pg.rgb565(230, 230, 255))
ghosts = []
for _ in range(2):
    g = pg.Sprite(GHOST, 0, 0)
    g.anchor = (0.5, 0.5)
    g.dither = 8
    scene.add(g)
    ghosts.append(g)

# --- star burst pool (rand colours + animated dither fade) ---
STAR_BMPS = [shapes.circle(10, c) for c in
             (pg.rgb565(255, 240, 120), pg.rgb565(120, 230, 255), pg.rgb565(255, 150, 200))]
stars = pool.Pool(scene, STAR_BMPS[0], 16, anchor=(0.5, 0.5))

# --- the player creature: a DIRECTIONAL triangle (so transpose/rotation is visible) ---
def _tri(data, w, h):
    for y in range(h):
        half = (y * (w // 2)) // h                              # widens downward -> apex at top
        for x in range(w // 2 - half, w // 2 + half):
            data[y * w + x] = 1 if y > h - 6 else 2             # tip lighter, base darker (shading)
    return [pg.rgb565(0, 0, 0), pg.rgb565(255, 200, 70), pg.rgb565(230, 140, 40)]
creature = pg.Sprite(make_pal8(28, 28, _tri), W // 2, (H - WATER_H) // 2 + BAR)
creature.anchor = (0.5, 0.5)
scene.add(creature)

# --- juice helpers (Fade LAST = on top) ---
shaker = fx.Shake(scene, max_offset=6)
fader = fx.Fade(scene, W, H)

hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, pg.rgb565(10, 12, 24))
hud_l = hud.label(terminalio.FONT, 3, 3, pg.rgb565(255, 255, 255), "")

RED = pg.rgb565(255, 60, 60)
BLUE = pg.rgb565(80, 120, 255)
# (name, apply-fn) for the creature effect cycle on X
FX_MODES = [
    ("normal", lambda c: None),
    ("dither", lambda c: setattr(c, "dither", 8)),
    ("tint red", lambda c: setattr(c, "tint", RED)),
    ("tint blue", lambda c: setattr(c, "tint", BLUE)),
    ("rotate 90", lambda c: setattr(c, "transpose", True)),
]
fxi = 0
flash_t = 0
fading = 0
t = 0
last_hud = None


def set_creature_fx(i):
    creature.dither = 0
    creature.tint = 0
    creature.transpose = False
    FX_MODES[i][1](creature)


def burst(cx, cy):
    for _ in range(6):
        s = stars.spawn()
        if s is None:
            break
        ang = R.random() * 6.283
        spd = 2.0 + R.random() * 2.5
        s.bitmap = R.choice(STAR_BMPS)
        s.dither = 0
        s.move(int(cx), int(cy))
        s.data = {"fx": float(cx), "fy": float(cy),
                  "vx": math.cos(ang) * spd, "vy": math.sin(ang) * spd, "d": 0.0}


print("FX demo - A flash+stars, B shake, X creature fx, Y fade, arrows move.")

while True:
    btn.poll()
    t += 1

    creature.x += (btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)) * 4
    creature.y += (btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)) * 4
    creature.x = max(20, min(W - 20, creature.x))
    creature.y = max(BAR + 20, min(H - WATER_H - 16, creature.y))

    if btn.just_pressed(btn.A):
        creature.flash = pg.rgb565(255, 255, 255)
        flash_t = 4
        burst(creature.x, creature.y)
    if btn.just_pressed(btn.B):
        shaker.add(0.8)
    if btn.just_pressed(btn.X):
        fxi = (fxi + 1) % len(FX_MODES)
        set_creature_fx(fxi)
    if btn.just_pressed(btn.Y) and fading == 0:
        fader.out(speed=2)
        fading = 1

    if flash_t > 0:
        flash_t -= 1
        if flash_t == 0:
            creature.flash = 0
            set_creature_fx(fxi)                          # restore the chosen effect after the flash

    if fading and fader.tick():
        if fading == 1:                              # reached black -> now fade back in
            fader.into(speed=2)
            fading = 2
        else:                                        # reached clear -> done
            fading = 0

    # animate the water by cycling its palette (Game-Boy trick: ~6 array writes, 0 extra art)
    if t % 4 == 0:
        palette.cycle(water_bmp.palette, 1, 6)
        water.touch()

    for i, g in enumerate(ghosts):
        a = t * 0.04 + i * 3.14159
        g.move(int(creature.x + math.cos(a) * 56), int(creature.y + math.sin(a) * 36))

    for s in stars.items:
        if not s.visible:
            continue
        st = s.data
        st["fx"] += st["vx"]
        st["fy"] += st["vy"]
        st["vx"] *= 0.96
        st["vy"] *= 0.96
        st["d"] += 0.8
        s.move(int(st["fx"]), int(st["fy"]))
        s.dither = int(st["d"])
        if st["d"] >= 16:
            stars.free(s)

    shaker.tick(0, 0)
    scene.refresh()

    hi = FX_MODES[fxi][0]
    if hi != last_hud:
        last_hud = hi
        hud_l.set("X:%s  A flash  B shake  Y fade" % hi)
        hud.draw()
    clock.tick()
