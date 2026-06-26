# Bounce -- step 3: a ball with momentum (sub-pixel movement).
#
# What you learn: velocity + sub-pixel position. A Sprite stores its position as
# fixed-point, exposed as sprite.fx / sprite.fy (floats). Add a velocity to fx/fy
# every frame and the ball drifts smoothly -- even at speeds below 1 px/frame,
# which plain integer x/y could not represent. sprite.x / sprite.y are the rounded
# pixel coordinates the engine draws at.
#
# New vs step 2: sprite.fx/.fy (sub-pixel position), a velocity (vx, vy). The ball
# flies off-screen for now -- step 4 makes it bounce.
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

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 10, 24))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.rect(BALL, BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
scene.add(paddle)
scene.add(ball)

velocity_x, velocity_y = 2.4, -2.6                          # NEW: the ball's velocity (px per frame)

while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if delta_x:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + delta_x * 5)), paddle.y)

    # integrate velocity into the ball's sub-pixel position
    ball.fx += velocity_x
    ball.fy += velocity_y

    scene.refresh()
    clock.tick()
