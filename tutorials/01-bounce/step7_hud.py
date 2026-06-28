# Bounce -- step 7: a score + lives status bar.
#
# What you learn: text / HUD. picogame_ui.SceneLabel renders text into the scene as a
# "fixed" layer -- it's drawn by scene.refresh() like everything else, and (because
# it's fixed) it would stay put even if the world scrolled (it doesn't here, but
# you'll want that in a platformer). It uses the bundled terminalio.FONT, so no font
# asset is needed. Call label.set(...) each frame; it only re-renders when the text
# actually changes.
#
# New vs step 6: terminalio.FONT, picogame_ui.SceneLabel, a running score.
#
# Run:  python3 sim/run.py tutorials/01-bounce/step7_hud.py --shot /tmp/s7.png

import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui

W, H = 320, 240
PADDLE_W, PADDLE_H = 44, 8
BALL = 6
BRICK_W, BRICK_H = 32, 16
COLS, ROWS = W // BRICK_W, 6
BRICK_Y = 28
BACKGROUND = pg.rgb565(8, 10, 24)

scene, _, _ = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

brick_colors = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
                pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
bricks = pg.Tilemap(shp.tileset_colors(BRICK_W, BRICK_H, brick_colors), COLS, ROWS)
bricks.move(0, BRICK_Y)


def build_wall():
    global bricks_left
    for tile_y in range(ROWS):
        for tile_x in range(COLS):
            bricks.tile(tile_x, tile_y, 1 + (tile_y % 4))
    bricks_left = COLS * ROWS


build_wall()
paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)),
                   (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.rect(BALL, BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
scene.add(bricks)
scene.add(paddle)
scene.add(ball)
# NEW: a HUD label. Adding it to the scene happens inside SceneLabel (as a fixed layer).
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, pg.rgb565(255, 255, 255), BACKGROUND)

velocity_x, velocity_y = 2.4, -2.6
score = 0
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

    center_x, center_y = ball.x + BALL // 2, ball.y + BALL // 2
    tile_x, tile_y = center_x // BRICK_W, (center_y - BRICK_Y) // BRICK_H
    if 0 <= tile_x < COLS and 0 <= tile_y < ROWS and bricks.tile(tile_x, tile_y):
        bricks.tile(tile_x, tile_y, 0)
        bricks_left -= 1
        score += 10                          # NEW: score on a hit
        velocity_y = -velocity_y
        if bricks_left == 0:
            build_wall()
            serve()

    if ball.fy > H:
        lives -= 1
        if lives <= 0:
            lives = 3
            score = 0
            build_wall()
        serve()

    hud.set("SCORE %05d   LIVES %d" % (score, lives))   # update text, then draw it
    scene.refresh()                                      # draws the scene incl. the HUD
    clock.tick()
