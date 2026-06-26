# Starship -- step 4: asteroids to dodge (a second pool + waves).
#
# What you learn: reuse the pool pattern for enemies, and spawn a "wave". Rocks come
# in 3 sizes (we keep the size in sprite.data and pick a matching ring bitmap with
# sprite.bitmap). A wave spreads N rocks around the screen, each drifting with its
# own velocity. shp.ring draws a hollow circle.
#
# New vs step 3: a rocks Pool with per-rock size/velocity, choosing a bitmap per
# rock (sprite.bitmap), spawning a wave.
#
# Run:  python3 sim/run.py tutorials/02-starship/step4_rocks.py --shot /tmp/p4.png

import math
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_pool

W, H = 320, 240
BG = pg.rgb565(0, 0, 8)
NF = 16

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

ship_bm = shp.poly_frames(18, [(0, -8), (6, 7), (0, 4), (-6, 7)], NF, pg.rgb565(200, 220, 255))
DIRS = [(math.sin(f * 2 * math.pi / NF), -math.cos(f * 2 * math.pi / NF)) for f in range(NF)]
bullet_bm = shp.circle(4, pg.rgb565(255, 255, 120))
ROCK_BM = [shp.ring(40, pg.rgb565(170, 140, 100), 3),    # size 0 = big
           shp.ring(24, pg.rgb565(170, 140, 100), 3),    # size 1 = medium
           shp.ring(13, pg.rgb565(170, 140, 100), 2)]    # size 2 = small

ship = pg.Sprite(ship_bm, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
rocks = picogame_pool.Pool(scene, ROCK_BM[0], 16, anchor=(0.5, 0.5))   # NEW
bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))
scene.add(ship)

angle = 0
velocity_x = velocity_y = 0.0
fire_cd = 0
wave = 3


def wrap(x, y):
    return x % W, y % H


def spawn_rock(size, x, y, rvx, rvy):
    r = rocks.spawn()
    if r is None:
        return
    r.data = {"size": size, "vx": rvx, "vy": rvy}
    r.bitmap = ROCK_BM[size]                  # pick the bitmap for this size
    r.fx, r.fy = float(x), float(y)


def new_wave(n):
    for i in range(n):
        a = i * 2 * math.pi / n
        spawn_rock(0, (W // 2 + int(140 * math.cos(a))) % W,
                   (H // 2 + int(110 * math.sin(a))) % H,
                   math.cos(a) * 1.2, math.sin(a) * 1.2)


new_wave(wave)
while True:
    btn.poll()
    fire_cd -= 1
    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % NF
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % NF
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25; velocity_y += delta_y * 0.25
    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)
    if speed > 5:
        velocity_x *= 5 / speed; velocity_y *= 5 / speed
    velocity_x *= 0.99; velocity_y *= 0.99
    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)
    ship.frame = angle

    if btn.just_pressed(btn.B) and fire_cd <= 0:
        b = bullets.spawn()
        if b:
            b.data = {"vx": delta_x * 7, "vy": delta_y * 7, "life": 30}
            b.move(ship.x, ship.y)
            fire_cd = 6
    for b in bullets.items:
        if not b.visible:
            continue
        b.data["life"] -= 1
        if b.data["life"] <= 0:
            bullets.free(b)
            continue
        b.fx, b.fy = wrap(b.fx + b.data["vx"], b.fy + b.data["vy"])

    # drift the rocks
    for r in rocks.items:
        if not r.visible:
            continue
        r.fx, r.fy = wrap(r.fx + r.data["vx"], r.fy + r.data["vy"])

    scene.refresh()
    clock.tick()
