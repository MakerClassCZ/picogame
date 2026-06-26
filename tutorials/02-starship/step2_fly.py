# Starship -- step 2: rotate, thrust, and wrap around the screen.
#
# What you learn: pre-baked rotation. For a ship that spins constantly, baking the
# rotations into frames is crisper and cheaper than rotating at runtime (sprite.angle).
# shp.poly_frames(size, points, N, colour) renders a polygon at N angles into
# one multi-frame bitmap; setting ship.frame = angle_index shows that rotation. A
# DIRS table holds the unit vector for each angle. UP thrusts along the facing
# vector into the sub-pixel velocity (vx, vy); we cap top speed and apply a little
# drag so it drifts like a spaceship. wrap() teleports across screen edges.
#
# New vs step 1: shp.poly_frames (pre-rotated frames), ship.frame, vector thrust
# into fx/fy, speed cap + drag, screen wrap.
#
# Run:  python3 sim/run.py tutorials/02-starship/step2_fly.py --hold UP --shot /tmp/p2.png

import math
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
BG = pg.rgb565(0, 0, 8)
NF = 16                                       # number of baked rotation frames

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# a ship polygon (points around the centre, +y is down), baked at NF angles
ship_bm = shp.poly_frames(18, [(0, -8), (6, 7), (0, 4), (-6, 7)], NF, pg.rgb565(200, 220, 255))
# facing unit vector for each frame: frame 0 points up (-y)
DIRS = [(math.sin(f * 2 * math.pi / NF), -math.cos(f * 2 * math.pi / NF)) for f in range(NF)]

ship = pg.Sprite(ship_bm, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
scene.add(ship)

angle = 0                                       # current rotation frame
velocity_x = velocity_y = 0.0                                 # velocity


def wrap(x, y):
    return x % W, y % H


while True:
    btn.poll()
    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % NF
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % NF
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25                       # accelerate along the facing vector
        velocity_y += delta_y * 0.25

    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)      # cap top speed
    if speed > 5:
        velocity_x *= 5 / speed
        velocity_y *= 5 / speed
    velocity_x *= 0.99                                # gentle drag
    velocity_y *= 0.99

    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)   # sub-pixel position + wrap
    ship.frame = angle                          # show the matching rotation

    scene.refresh()
    clock.tick()
