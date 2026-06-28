# Bounce -- step 9: from rectangles to sprites (the orthogonality lesson).
#
# What you learn: art is independent of mechanics. We built a COMPLETE game out of
# coloured rectangles. To make it look like a real game we change ONLY the bitmaps:
# the ball becomes a round disc (shp.circle) and the paddle gets a multi-colour
# bitmap with a highlight stripe. Compare this file to step 8: the entire game loop
# -- movement, bouncing, collision, scoring, particles -- is byte-for-byte the same.
# A Sprite doesn't care whether its bitmap is a rectangle, a generated shape, or a
# PNG you imported in the editor. (To use real PNG art: draw/import it in the editor,
# export a scene, and load it with picogame_scene -- see tutorials/README.md.)
#
# New vs step 8: only the two bitmap definitions changed (ball + paddle art).
#
# Run:  python3 sim/run.py tutorials/01-bounce/step9_sprites.py --shot /tmp/s9.png

import array
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

try:
    import picogame_audio
    audio = picogame_audio.Audio()
    blip = picogame_audio.tone(660, 35)
except Exception:
    audio = None
    blip = None


def paddle_art(w, h):
    """A 2-colour paddle bitmap: blue body + a lighter highlight on the top row.
    This is what 'real sprite art' is -- a PAL8 bitmap with more than one colour."""
    palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(70, 110, 210), pg.rgb565(150, 190, 255)])
    data = bytearray(b"\x01" * (w * h))      # index 1 = body
    for x in range(w):
        data[x] = 2                          # index 2 = highlight on the top row
    return pg.Bitmap(data, w, h, format=pg.PAL8, palette=palette, frames=1, stride=w, transparent=0)


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
# >>> the ONLY change from step 8: art instead of plain rectangles <<<
paddle = pg.Sprite(paddle_art(PADDLE_W, PADDLE_H), (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.circle(BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
# >>> everything below is identical to step 8 <<<
particles = pg.Particles(96, size=2, gravity=0.12)
scene.add(bricks)
scene.add(particles)
scene.add(paddle)
scene.add(ball)
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
    if 0 <= tile_x < COLS and 0 <= tile_y < ROWS:
        cell = bricks.tile(tile_x, tile_y)
        if cell:
            bricks.tile(tile_x, tile_y, 0)
            bricks_left -= 1
            score += 10
            velocity_y = -velocity_y
            particles.emit(tile_x * BRICK_W + BRICK_W // 2, BRICK_Y + tile_y * BRICK_H + BRICK_H // 2,
                           14, 3, 22, brick_colors[cell - 1])
            if audio:
                audio.sfx(blip)
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

    particles.tick()
    hud.set("SCORE %05d   LIVES %d" % (score, lives))
    scene.refresh()
    clock.tick()
