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
import picogame_synth as snd
import picogame_sfx
import picogame_math as m
import picogame_pool

W, H = board.DISPLAY.width, board.DISPLAY.height
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
# Pre-seed each pool slot's .data once so spawns MUTATE in place (no per-spawn dict).
for s in rocks.items:
    s.data = {"size": 0, "vx": 0.0, "vy": 0.0, "x": 0.0, "y": 0.0}
for s in bullets.items:
    s.data = {"vx": 0.0, "vy": 0.0, "life": 0, "x": 0.0, "y": 0.0}
exhaust = pg.Particles(40, size=2, gravity=0.0)   # engine puff out the ship's tail (no gravity in space)
scene.add(exhaust)
scene.add(ship)

hud = picogame_font.Label(pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)

class State:
    def __init__(self):
        self.ang = 0
        self.sx = float(W // 2)
        self.sy = float(H // 2)
        self.vx = 0.0
        self.vy = 0.0
        self.score = 0
        self.lives = 3
        self.fire_cd = 0
        self.inv = 60
        self.wave = 3


st = State()


def wrap(x, y):
    return m.wrap(x, 0, W), m.wrap(y, 0, H)


def spawn_rock(size, x, y, vx, vy):
    r = rocks.spawn()
    if r is None:
        return
    d = r.data
    d["size"] = size
    d["vx"] = vx
    d["vy"] = vy
    d["x"] = float(x)
    d["y"] = float(y)
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
    global st
    st = State()
    rocks.free_all()
    bullets.free_all()
    new_wave(st.wave)


new_game()
kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if no audio
print("LEFT/RIGHT rotate, UP thrust, B fire. Clear the asteroids.")
frame = 0
_shown_score, _shown_lives = -1, -1
while True:
    btn.poll()
    frame += 1
    st.fire_cd -= 1
    if st.inv > 0:
        st.inv -= 1

    # rotate / thrust  (ang in turns 0..1; nose-up so dir = (sin_t, -cos_t))
    if btn.is_pressed(btn.LEFT):
        st.ang = (st.ang - TURN) % 1.0
    if btn.is_pressed(btn.RIGHT):
        st.ang = (st.ang + TURN) % 1.0
    dx, dy = m.sin_t(st.ang), -m.cos_t(st.ang)
    if btn.is_pressed(btn.UP):
        st.vx += dx * 0.25
        st.vy += dy * 0.25
        if frame & 1:                                  # exhaust puff from the tail, every other frame
            exhaust.emit(int(st.sx - dx * 9), int(st.sy - dy * 9), 2, 2, 10,
                         pg.rgb565(255, 150, 40))
    # cap + drift
    sp = m.length(st.vx, st.vy)
    if sp > 5:
        st.vx *= 5 / sp
        st.vy *= 5 / sp
    st.vx *= 0.99
    st.vy *= 0.99
    st.sx, st.sy = wrap(st.sx + st.vx, st.sy + st.vy)
    ship.angle = st.ang * 360.0       # runtime affine rotation
    ship.move(int(st.sx), int(st.sy))
    ship.visible = (st.inv <= 0) or (frame & 1)

    # fire
    if btn.just_pressed(btn.B) and st.fire_cd <= 0:
        b = bullets.spawn()
        if b:
            d = b.data
            d["vx"] = dx * 7
            d["vy"] = dy * 7
            d["life"] = 30
            d["x"] = st.sx
            d["y"] = st.sy
            b.move(int(st.sx), int(st.sy))
            st.fire_cd = 6
            kit.zap()                  # fire

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
                st.score += (3 - sz) * 20
                kit.boom()                   # asteroid destroyed
                if sz < 2:                       # split into two smaller
                    for s in (-1, 1):
                        spawn_rock(sz + 1, rx, ry, rvx + s * 0.8, rvy - s * 0.8)
                break
        # ship hit
        if st.inv <= 0 and r.visible and ship.near(r, rr + 6):
            st.lives -= 1
            st.inv = 90
            st.sx, st.sy = float(W // 2), float(H // 2)
            st.vx = st.vy = 0.0
            if st.lives < 0:
                kit.explosion()
                new_game()
            else:
                kit.hurt()

    if rocks.count() == 0:
        st.wave += 1
        kit.powerup()                # wave cleared
        new_wave(st.wave)

    kit.tick()
    exhaust.tick()
    scene.refresh()
    shown_lives = max(0, st.lives)
    if st.score != _shown_score or shown_lives != _shown_lives:
        _shown_score, _shown_lives = st.score, shown_lives
        hud.set("SCORE %05d   SHIPS %d" % (st.score, shown_lives))
    hud.draw(scene.display, bufA)
    clock.tick()
