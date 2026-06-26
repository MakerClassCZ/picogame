# Starship -- step 1: a ship on screen (recap, with a shaped sprite).
#
# This second tutorial assumes you've done Bounce (01-bounce). It builds a top-down
# space shooter and covers what Bounce couldn't: rotation, vector thrust, object
# pools (bullets/enemies), circular collision, explosions, and game states.
#
# What you learn here (recap): a Sprite can be any shape. shp.from_mask turns an
# ASCII picture into a one-colour bitmap. anchor=(0.5, 0.5) puts the sprite's
# reference point at its CENTRE -- the natural choice for something that rotates.
#
# New: shp.from_mask, centre anchor.
#
# Run:  python3 sim/run.py tutorials/02-starship/step1_ship.py --shot /tmp/p1.png

import picogame as pg
import picogame_game
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
BG = pg.rgb565(0, 0, 8)

scene, bufA, bufB = picogame_game.setup(background=BG)
clock = picogame_clock.Clock(30)

SHIP_MASK = [
    "  #  ",
    "  #  ",
    " ### ",
    " ### ",
    "#####",
    "## ##",
]
ship = pg.Sprite(shp.from_mask(SHIP_MASK, pg.rgb565(200, 220, 255)), W // 2, H // 2)
ship.anchor = (0.5, 0.5)                     # rotate/position about the centre
scene.add(ship)

while True:
    scene.refresh()
    clock.tick()
