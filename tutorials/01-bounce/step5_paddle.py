# Bounce -- step 5: the paddle hits the ball, and you can miss.
#
# What you learn: box collision + a control feel trick. pg.collide(ax1,ay1,ax2,ay2,
# bx1,by1,bx2,by2) is a fast axis-aligned overlap test. On a paddle hit we send the
# ball upward, and nudge vx by WHERE on the paddle it landed -- so you can aim. If
# the ball falls below the screen it's a miss: lose a life and re-serve.
#
# New vs step 4: pg.collide, steering the bounce by hit offset, lives + reset.
#
# Run:  python3 sim/run.py tutorials/01-bounce/step5_paddle.py --hold LEFT --shot /tmp/s5.png

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

velocity_x, velocity_y = 2.4, -2.6
lives = 3


def serve():
    global velocity_x, velocity_y
    ball.move(W // 2, H // 2)
    velocity_x, velocity_y = 2.4, -2.6


while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if delta_x:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + delta_x * 5)), paddle.y)

    ball.fx += velocity_x
    ball.fy += velocity_y
    if ball.fx < 0:
        ball.fx = 0; velocity_x = -velocity_x
    elif ball.fx > W - BALL:
        ball.fx = W - BALL; velocity_x = -velocity_x
    if ball.fy < 0:
        ball.fy = 0; velocity_y = -velocity_y

    # paddle bounce: only when moving DOWN and the boxes overlap
    if velocity_y > 0 and pg.collide(ball.x, ball.y, ball.x + BALL, ball.y + BALL,
                             paddle.x, paddle.y, paddle.x + PADDLE_W, paddle.y + PADDLE_H):
        velocity_y = -abs(velocity_y)
        # steer: distance of ball centre from paddle centre -> sideways speed
        velocity_x += (ball.x + BALL / 2 - (paddle.x + PADDLE_W / 2)) * 0.06

    if ball.fy > H:                          # missed the ball
        lives -= 1
        if lives <= 0:
            lives = 3
        serve()

    scene.refresh()
    clock.tick()
