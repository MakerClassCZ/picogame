# Bounce -- step 4: bounce off the walls.
#
# What you learn: reflection. A bounce is just flipping the velocity component that
# points into the wall, and pinning the position back to the edge so the ball can't
# tunnel out. Left/right flip velocity_x; the top flips velocity_y. We're still
# moving in whole pixels (integer velocity). We leave the BOTTOM open -- a ball that
# falls past it is a missed ball (step 5 turns that into "lose a life").
#
# New vs step 3: edge tests against ball.x/.y, inverting velocity_x/velocity_y on contact.
#
# Run:  python3 sim/run.py tutorials/01-bounce/step4_walls.py --shot /tmp/s4.png

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

velocity_x, velocity_y = 3, -3

while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if delta_x:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + delta_x * 5)), paddle.y)

    ball.move(ball.x + velocity_x, ball.y + velocity_y)

    # walls: flip the component heading into the wall, and pin to the edge
    if ball.x < 0:
        ball.move(0, ball.y)
        velocity_x = -velocity_x
    elif ball.x > W - BALL:
        ball.move(W - BALL, ball.y)
        velocity_x = -velocity_x
    if ball.y < 0:
        ball.move(ball.x, 0)
        velocity_y = -velocity_y

    scene.refresh()
    clock.tick()
