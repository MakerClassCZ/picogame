# Bounce -- step 8: juice (particles + sound).
#
# What you learn: feedback that makes a hit feel good. pg.Particles is a cheap
# burst system: emit(x, y, count, speed, life, colour) spawns particles, tick()
# advances them (with gravity), and the scene draws them. We burst on every brick
# break, in the brick's colour. And picogame_audio.tone() builds a short square-wave
# beep with no .wav file -- a tiny blip on each hit. (Audio is wrapped in try/except
# so it degrades gracefully where there's no audio output, e.g. the simulator.)
#
# New vs step 7: pg.Particles (emit/tick), picogame_audio.tone() + Audio().sfx().
#
# Run:  python3 sim/run.py tutorials/01-bounce/step8_particles.py --shot /tmp/s8.png

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
BW, BH = 32, 16
COLS, ROWS = W // BW, 6
BRICK_Y = 28
BG = pg.rgb565(8, 10, 24)

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

# optional audio: a beep on each hit (no asset needed). None if no audio backend.
try:
    import picogame_audio
    audio = picogame_audio.Audio()
    blip = picogame_audio.tone(660, 35)
except Exception:
    audio = None
    blip = None

brick_colors = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
                pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
brick_ts = shp.tileset_colors(BW, BH, brick_colors)
bricks = pg.Tilemap(brick_ts, COLS, ROWS)
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
particles = pg.Particles(96, size=2, gravity=0.12)    # NEW
scene.add(bricks)
scene.add(particles)                         # behind paddle+ball
scene.add(paddle)
scene.add(ball)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, pg.rgb565(255, 255, 255), BG)

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
    tile_x, tile_y = center_x // BW, (center_y - BRICK_Y) // BH
    if 0 <= tile_x < COLS and 0 <= tile_y < ROWS:
        cell = bricks.tile(tile_x, tile_y)
        if cell:
            bricks.tile(tile_x, tile_y, 0)
            bricks_left -= 1
            score += 10
            velocity_y = -velocity_y
            # burst in the brick's colour at the brick's centre
            bx_px = tile_x * BW + BW // 2
            by_px = BRICK_Y + tile_y * BH + BH // 2
            particles.emit(bx_px, by_px, 14, 3, 22, brick_colors[cell - 1])
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

    particles.tick()                         # advance the burst each frame
    hud.set("SCORE %05d   LIVES %d" % (score, lives))
    scene.refresh()
    clock.tick()
