# Starship -- step 3: fire bullets from an object pool.
#
# What you learn: pooling. Spawning objects (bullets, enemies, sparks) by creating
# Sprites at runtime causes memory churn. Instead, pre-allocate a fixed pool ONCE:
# picogame_pool.Pool makes N hidden sprites in the scene, spawn() reveals the first
# free one, free() hides it, and sprite.visible IS the alive flag. We keep each
# bullet's velocity + remaining life in sprite.data, and its position in fx/fy.
# A cooldown limits the fire rate.
#
# New vs step 2: picogame_pool.Pool, spawn/free, btn.just_pressed (a fresh press),
# per-bullet state in sprite.data, a fire cooldown + bullet lifetime.
#
# Run:  python3 sim/run.py tutorials/02-starship/step3_shoot.py --hold B --shot /tmp/p3.png

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

ship = pg.Sprite(ship_bm, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))   # NEW: 6-bullet pool
scene.add(ship)                              # add ship AFTER the pool so it draws on top

angle = 0
velocity_x = velocity_y = 0.0
fire_cd = 0


def wrap(x, y):
    return x % W, y % H


while True:
    btn.poll()
    fire_cd -= 1
    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % NF
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % NF
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25
        velocity_y += delta_y * 0.25
    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)
    if speed > 5:
        velocity_x *= 5 / speed; velocity_y *= 5 / speed
    velocity_x *= 0.99; velocity_y *= 0.99
    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)
    ship.frame = angle

    # fire: a fresh B press, if the cooldown has elapsed and a slot is free
    if btn.just_pressed(btn.B) and fire_cd <= 0:
        b = bullets.spawn()
        if b:
            b.data = {"vx": delta_x * 7, "vy": delta_y * 7, "life": 30}
            b.move(ship.x, ship.y)
            fire_cd = 6

    # advance live bullets; retire them when their life runs out
    for b in bullets.items:
        if not b.visible:
            continue
        b.data["life"] -= 1
        if b.data["life"] <= 0:
            bullets.free(b)
            continue
        b.fx, b.fy = wrap(b.fx + b.data["vx"], b.fy + b.data["vy"])

    scene.refresh()
    clock.tick()
