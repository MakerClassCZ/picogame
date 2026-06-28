# Bounce -- step 3: a ball with velocity (whole-pixel movement).
#
# What you learn: velocity. Velocity is just how many pixels a thing moves each
# frame: velocity_x across, velocity_y down. Add the velocity to the ball's
# position every frame and it travels in a straight line. Here we move in WHOLE
# pixels -- integer velocity, integer position -- which is all this step needs.
#
# New vs step 2: a velocity (velocity_x, velocity_y) added to ball.x / ball.y each
# frame. The ball flies off-screen for now -- step 4 makes it bounce.
#
# Run:  python3 sim/run.py tutorials/01-bounce/step3_ball.py --shot /tmp/s3.png

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
PADDLE_W, PADDLE_H = 44, 8
BALL = 6

scene, _, _ = picogame_game.setup(background=pg.rgb565(8, 10, 24))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.rect(BALL, BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
scene.add(paddle)
scene.add(ball)

velocity_x, velocity_y = 3, -3              # NEW: whole pixels moved per frame

while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if delta_x:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + delta_x * 5)), paddle.y)

    # move the ball by its velocity (whole pixels)
    ball.move(ball.x + velocity_x, ball.y + velocity_y)

    scene.refresh()
    clock.tick()
