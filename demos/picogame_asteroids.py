# Asteroids on picogame - tests ROTATION (the engine's runtime affine sprite.angle
# spins one ship bitmap, no pre-baked frames), screen WRAP, vector thrust
# (sub-pixel fx/fy), and pooled bullets + splitting asteroids. Generated art via
# picogame_shapes; turn-trig + wrap via picogame_math.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_font.py, picogame_shapes.py, picogame_math.py. Needs the latest firmware.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_font
import picogame_shapes as shp
import picogame_math as m
import picogame_pool

W, H = 320, 240
BG = pg.rgb565(0, 0, 8)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

TURN = 1.0 / 16                           # ship rotation step (turns per frame)
SHIP = 18
# ONE upright ship bitmap; the engine's runtime affine sprite.angle spins it.
ship_bm = shp.poly_frames(SHIP, [(0, -8), (6, 7), (0, 4), (-6, 7)], 1,
                          pg.rgb565(200, 220, 255))

rock_bm = [shp.ring(40, pg.rgb565(170, 140, 100), 3),
           shp.ring(24, pg.rgb565(170, 140, 100), 3),
           shp.ring(13, pg.rgb565(170, 140, 100), 2)]
ROCK_R = [20, 12, 6]
bullet_bm = shp.circle(4, pg.rgb565(255, 255, 120))

ship = pg.Sprite(ship_bm, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
# Sprite pools (picogame_pool): visible = the alive flag, .data = per-shot state.
rocks = picogame_pool.Pool(scene, rock_bm[0], 12, anchor=(0.5, 0.5))
bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))
exhaust = pg.Particles(40, size=2, gravity=0.0)   # engine puff out the ship's tail (no gravity in space)
scene.add(exhaust)
scene.add(ship)

hud = picogame_font.Label(pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)
S = {}


def wrap(x, y):
    return m.wrap(x, 0, W), m.wrap(y, 0, H)


def spawn_rock(size, x, y, vx, vy):
    r = rocks.spawn()
    if r is None:
        return
    r.data = {"size": size, "vx": vx, "vy": vy, "x": float(x), "y": float(y)}
    r.bitmap = rock_bm[size]
    r.move(int(x), int(y))


def new_wave(n):
    for i in range(n):
        a = i / n                          # turns 0..1
        ca, sa = m.cos_t(a), m.sin_t(a)
        spawn_rock(0, (W // 2 + int(140 * ca)) % W,
                   (H // 2 + int(110 * sa)) % H,
                   ca * 1.2, sa * 1.2)


def new_game():
    S.update(ang=0, sx=float(W // 2), sy=float(H // 2), vx=0.0, vy=0.0,
             score=0, lives=3, fire_cd=0, inv=60, wave=3)
    rocks.free_all()
    bullets.free_all()
    new_wave(S["wave"])


new_game()
print("LEFT/RIGHT rotate, UP thrust, B fire. Clear the asteroids.")
frame = 0
while True:
    btn.poll()
    frame += 1
    S["fire_cd"] -= 1
    if S["inv"] > 0:
        S["inv"] -= 1

    # rotate / thrust  (ang in turns 0..1; nose-up so dir = (sin_t, -cos_t))
    if btn.is_pressed(btn.LEFT):
        S["ang"] = (S["ang"] - TURN) % 1.0
    if btn.is_pressed(btn.RIGHT):
        S["ang"] = (S["ang"] + TURN) % 1.0
    dx, dy = m.sin_t(S["ang"]), -m.cos_t(S["ang"])
    if btn.is_pressed(btn.UP):
        S["vx"] += dx * 0.25
        S["vy"] += dy * 0.25
        if frame & 1:                                  # exhaust puff from the tail, every other frame
            exhaust.emit(int(S["sx"] - dx * 9), int(S["sy"] - dy * 9), 2, 2, 10,
                         pg.rgb565(255, 150, 40))
    # cap + drift
    sp = m.length(S["vx"], S["vy"])
    if sp > 5:
        S["vx"] *= 5 / sp
        S["vy"] *= 5 / sp
    S["vx"] *= 0.99
    S["vy"] *= 0.99
    S["sx"], S["sy"] = wrap(S["sx"] + S["vx"], S["sy"] + S["vy"])
    ship.angle = S["ang"] * 360.0          # runtime affine rotation
    ship.move(int(S["sx"]), int(S["sy"]))
    ship.visible = (S["inv"] <= 0) or (frame & 1)

    # fire
    if btn.just_pressed(btn.B) and S["fire_cd"] <= 0:
        b = bullets.spawn()
        if b:
            b.data = {"vx": dx * 7, "vy": dy * 7, "life": 30, "x": S["sx"], "y": S["sy"]}
            b.move(int(S["sx"]), int(S["sy"]))
            S["fire_cd"] = 6

    # bullets
    for b in bullets.items:
        if not b.visible:
            continue
        b.data["life"] -= 1
        if b.data["life"] <= 0:
            bullets.free(b)
            continue
        b.data["x"], b.data["y"] = wrap(b.data["x"] + b.data["vx"], b.data["y"] + b.data["vy"])
        b.move(int(b.data["x"]), int(b.data["y"]))

    # rocks: move, wrap, collide (sprite.near - circular distance, reads sprite pos)
    for r in rocks.items:
        if not r.visible:
            continue
        r.data["x"], r.data["y"] = wrap(r.data["x"] + r.data["vx"], r.data["y"] + r.data["vy"])
        r.move(int(r.data["x"]), int(r.data["y"]))
        rr = ROCK_R[r.data["size"]]
        # bullet hits
        for b in bullets.items:
            if not b.visible:
                continue
            if b.near(r, rr):
                # snapshot this rock's state BEFORE freeing it: spawn() below reuses the
                # just-freed slot, so the first child overwrites r.data - read it now or the
                # second child sees the bumped size (-> spawn_rock(3) -> rock_bm IndexError).
                sz, rx, ry = r.data["size"], r.data["x"], r.data["y"]
                rvx, rvy = r.data["vx"], r.data["vy"]
                bullets.free(b)
                rocks.free(r)
                S["score"] += (3 - sz) * 20
                if sz < 2:                       # split into two smaller
                    for s in (-1, 1):
                        spawn_rock(sz + 1, rx, ry, rvx + s * 0.8, rvy - s * 0.8)
                break
        # ship hit
        if S["inv"] <= 0 and r.visible and ship.near(r, rr + 6):
            S["lives"] -= 1
            S["inv"] = 90
            S["sx"], S["sy"] = float(W // 2), float(H // 2)
            S["vx"] = S["vy"] = 0.0
            if S["lives"] < 0:
                new_game()

    if rocks.count() == 0:
        S["wave"] += 1
        new_wave(S["wave"])

    exhaust.tick()
    scene.refresh()
    hud.set("SCORE %05d   SHIPS %d" % (S["score"], max(0, S["lives"])))
    hud.draw(board.DISPLAY, bufA)
    clock.tick()
