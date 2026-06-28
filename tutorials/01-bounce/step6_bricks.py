# Bounce -- step 6: a wall of bricks (a Tilemap).
#
# What you learn: the Tilemap. A grid of tiles backed by ONE bitmap (a tileset),
# stored as 1 byte per cell -- far cheaper than a Sprite per brick. We build the
# tileset with shp.tileset_colors (frame 0 = empty, 1..4 = colours), fill the grid,
# and on a ball hit we find the tile under the ball, read it, and set it to 0 to
# clear it. Map a pixel to a tile with  tx = (px - origin_x) // tile_w.
#
# New vs step 5: pg.Tilemap, shp.tileset_colors, pixel->tile mapping, clearing a tile.
#
# Run:  python3 sim/run.py tutorials/01-bounce/step6_bricks.py --shot /tmp/s6.png

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
PADDLE_W, PADDLE_H = 44, 8
BALL = 6
BRICK_W, BRICK_H = 32, 16                              # brick (tile) size
COLS, ROWS = W // BRICK_W, 6                       # 10 x 6 wall
BRICK_Y = 28                                  # wall top (leaves a HUD strip)

scene, _, _ = picogame_game.setup(background=pg.rgb565(8, 10, 24))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

# tileset: value 0 empty, 1..4 = four brick colours
brick_colors = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
                pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
bricks = pg.Tilemap(shp.tileset_colors(BRICK_W, BRICK_H, brick_colors), COLS, ROWS)
bricks.move(0, BRICK_Y)


def build_wall():
    global bricks_left
    for tile_y in range(ROWS):
        for tile_x in range(COLS):
            bricks.tile(tile_x, tile_y, 1 + (tile_y % 4))    # row -> colour 1..4
    bricks_left = COLS * ROWS


build_wall()
paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.rect(BALL, BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
scene.add(bricks)                            # add the wall first (drawn under the ball)
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

    if velocity_y > 0 and pg.collide(ball.x, ball.y, ball.x + BALL, ball.y + BALL,
                             paddle.x, paddle.y, paddle.x + PADDLE_W, paddle.y + PADDLE_H):
        velocity_y = -abs(velocity_y)
        velocity_x += (ball.x + BALL / 2 - (paddle.x + PADDLE_W / 2)) * 0.06

    # brick hit: the tile under the ball's centre
    center_x, center_y = ball.x + BALL // 2, ball.y + BALL // 2
    tile_x = center_x // BRICK_W
    tile_y = (center_y - BRICK_Y) // BRICK_H
    if 0 <= tile_x < COLS and 0 <= tile_y < ROWS and bricks.tile(tile_x, tile_y):
        bricks.tile(tile_x, tile_y, 0)               # clear the brick
        bricks_left -= 1
        velocity_y = -velocity_y
        if bricks_left == 0:                 # cleared the wall -> rebuild
            build_wall()
            serve()

    if ball.fy > H:
        lives -= 1
        if lives <= 0:
            lives = 3
            build_wall()
        serve()

    scene.refresh()
    clock.tick()
