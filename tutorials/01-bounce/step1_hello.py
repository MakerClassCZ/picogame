# Bounce -- step 1: get ONE thing on screen.
#
# What you learn: the picogame render loop. A game is (a) a Scene you add objects
# to ONCE, then (b) a loop that moves things and calls scene.refresh(). The engine
# is retained-mode: you don't redraw by hand, you change object state and refresh.
#
# New in this step: picogame_game.setup(), picogame_shapes.rect(), pg.Sprite,
# scene.add(), scene.refresh(), the frame clock.
#
# Run it:  python3 sim/run.py tutorials/01-bounce/step1_hello.py --shot /tmp/s1.png
# On device: copy this file + the lib/ helpers to CIRCUITPY.

import picogame as pg
import picogame_game
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
PADDLE_W, PADDLE_H = 44, 8

# setup() takes over the display and gives us a Scene + its two strip buffers.
scene, _, _ = picogame_game.setup(background=pg.rgb565(8, 10, 24))
clock = picogame_clock.Clock(40)            # cap the loop to 40 FPS

# A "paddle" is just a Sprite whose bitmap is a solid rectangle. shp.rect(w,h,color)
# makes that bitmap -- a rectangle and an image sprite are the SAME kind of object
# (we'll prove that in step 9 by swapping the bitmap for art, with no other change).
paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)

scene.add(paddle)                            # add it to the scene ONCE

while True:
    scene.refresh()                          # the engine draws the scene
    clock.tick()                             # sleep to the next frame
