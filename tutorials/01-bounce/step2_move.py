# Bounce -- step 2: move the paddle with the buttons.
#
# What you learn: input. picogame_input.Buttons reads the board's buttons into a
# bitmask each frame; btn.is_pressed(btn.LEFT) is the held state. We move the paddle
# and clamp it to the screen so it can't leave.
#
# New vs step 1: picogame_input.Buttons, btn.poll()/btn.is_pressed(), sprite.move(),
# clamping with max()/min().
#
# Run:  python3 sim/run.py tutorials/01-bounce/step2_move.py --hold RIGHT --shot /tmp/s2.png

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
PADDLE_W, PADDLE_H = 44, 8
SPEED = 5

scene, _, _ = picogame_game.setup(background=pg.rgb565(8, 10, 24))
btn = picogame_input.Buttons()              # NEW: the buttons
clock = picogame_clock.Clock(40)

paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)
scene.add(paddle)

while True:
    btn.poll()                            # sample the buttons once per frame
    # RIGHT minus LEFT gives -1 / 0 / +1 -- a tidy way to read a 1-axis control.
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if delta_x:
        x = paddle.x + delta_x * SPEED
        x = max(0, min(W - PADDLE_W, x))    # clamp inside the screen
        paddle.move(x, paddle.y)

    scene.refresh()
    clock.tick()
