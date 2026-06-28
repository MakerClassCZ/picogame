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
BACKGROUND = pg.rgb565(0, 0, 8)
FRAMES = 16

scene, _, _ = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

ship_bitmap = shp.poly_frames(18, [(0, -8), (6, 7), (0, 4), (-6, 7)], FRAMES, pg.rgb565(200, 220, 255))
DIRS = [(math.sin(frame * 2 * math.pi / FRAMES), -math.cos(frame * 2 * math.pi / FRAMES)) for frame in range(FRAMES)]
bullet_bitmap = shp.circle(4, pg.rgb565(255, 255, 120))
ROCK_BITMAP = [shp.ring(40, pg.rgb565(170, 140, 100), 3),    # size 0 = big
           shp.ring(24, pg.rgb565(170, 140, 100), 3),    # size 1 = medium
           shp.ring(13, pg.rgb565(170, 140, 100), 2)]    # size 2 = small

ship = pg.Sprite(ship_bitmap, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
rocks = picogame_pool.Pool(scene, ROCK_BITMAP[0], 16, anchor=(0.5, 0.5))   # NEW
bullets = picogame_pool.Pool(scene, bullet_bitmap, 6, anchor=(0.5, 0.5))
scene.add(ship)

angle = 0
velocity_x = velocity_y = 0.0
fire_cooldown = 0
wave = 3


def wrap(x, y):
    return x % W, y % H


def spawn_rock(size, x, y, velocity_x, velocity_y):
    rock = rocks.spawn()
    if rock is None:
        return
    rock.data = {"size": size, "velocity_x": velocity_x, "velocity_y": velocity_y}
    rock.bitmap = ROCK_BITMAP[size]                  # pick the bitmap for this size
    rock.fx, rock.fy = float(x), float(y)


def new_wave(count):
    for i in range(count):
        angle_rad = i * 2 * math.pi / count
        spawn_rock(0, (W // 2 + int(140 * math.cos(angle_rad))) % W,
                   (H // 2 + int(110 * math.sin(angle_rad))) % H,
                   math.cos(angle_rad) * 1.2, math.sin(angle_rad) * 1.2)


new_wave(wave)
while True:
    btn.poll()
    fire_cooldown -= 1
    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % FRAMES
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % FRAMES
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25; velocity_y += delta_y * 0.25
    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)
    if speed > 5:
        velocity_x *= 5 / speed; velocity_y *= 5 / speed
    velocity_x *= 0.99; velocity_y *= 0.99
    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)
    ship.frame = angle

    if btn.just_pressed(btn.B) and fire_cooldown <= 0:
        bullet = bullets.spawn()
        if bullet:
            bullet.data = {"velocity_x": delta_x * 7, "velocity_y": delta_y * 7, "life": 30}
            bullet.move(ship.x, ship.y)
            fire_cooldown = 6
    for bullet in bullets.items:
        if not bullet.visible:
            continue
        bullet.data["life"] -= 1
        if bullet.data["life"] <= 0:
            bullets.free(bullet)
            continue
        bullet.fx, bullet.fy = wrap(bullet.fx + bullet.data["velocity_x"], bullet.fy + bullet.data["velocity_y"])

    # drift the rocks
    for rock in rocks.items:
        if not rock.visible:
            continue
        rock.fx, rock.fy = wrap(rock.fx + rock.data["velocity_x"], rock.fy + rock.data["velocity_y"])

    scene.refresh()
    clock.tick()
