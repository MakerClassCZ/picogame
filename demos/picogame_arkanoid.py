# Arkanoid / Breakout on picogame - a demonstration game touching most engine
# pillars at once: Tilemap (the brick wall, bricks cleared on hit), Sprites
# (paddle + ball), pg.collide, Particles (brick-break bursts), bundled-font HUD,
# and the helpers (setup / input / clock). Genre port of TinyJoypad's TinyArkanoid.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_shapes.py, picogame_ui.py, picogame_font.py, picogame_fx.py to
# CIRCUITPY. Requires the Tilemap+Particles firmware.

import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shapes
import picogame_ui as ui
import picogame_fx as fx

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 10, 24))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

W, H = 320, 240
BW, BH = 32, 16                       # brick (tile) size
COLS, ROWS = W // BW, 6               # 10 x 6 brick wall
BRICK_Y = 28                          # wall top (leaves a HUD strip on top)

# Tileset: frame 0 = empty (transparent), 1..4 = coloured bricks (built by helper).
brick_colors = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
                pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
tileset = shapes.tileset_colors(BW, BH, brick_colors)

bricks = pg.Tilemap(tileset, COLS, ROWS)
bricks.move(0, BRICK_Y)
for ty in range(ROWS):
    for tx in range(COLS):
        bricks.tile(tx, ty, 1 + (ty % 4))
bricks_left = COLS * ROWS


PADDLE_W, PADDLE_H = 44, 8
paddle = pg.Sprite(shapes.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)), (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shapes.rect(6, 6, pg.rgb565(255, 240, 120)), W // 2, H // 2)
particles = pg.Particles(128, size=2, gravity=0.12)

scene.add_all([bricks, particles, paddle, ball])
# HUD as a fixed scene layer: painted by scene.refresh(), no per-frame draw call.
score_label = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, pg.rgb565(255, 255, 255), pg.rgb565(8, 10, 24))
flash = fx.Fade(scene, W, H, color=pg.rgb565(255, 255, 255))   # juice: flash on a lost ball

bx, by = float(ball.x), float(ball.y)
vx, vy = 2.4, -2.6
score = 0
lives = 3


def reset_ball():
    global bx, by, vx, vy
    bx, by = W / 2, H / 2
    vx, vy = 2.4, -2.6
    ball.move(int(bx), int(by))


print("D-pad / L-R: move paddle. Break all the bricks!")
while True:
    btn.poll()
    flash.tick()                      # animate the hit-flash (no-op while idle)
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if dx:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + dx * 5)), paddle.y)

    bx += vx
    by += vy
    if bx < 0:
        bx = 0
        vx = -vx
    elif bx > W - 6:
        bx = W - 6
        vx = -vx
    if by < 0:
        by = 0
        vy = -vy

    # paddle bounce (steer by where it hits)
    if vy > 0 and pg.collide(int(bx), int(by), int(bx) + 6, int(by) + 6,
                             paddle.x, paddle.y, paddle.x + PADDLE_W, paddle.y + PADDLE_H):
        vy = -abs(vy)
        vx += (bx + 3 - (paddle.x + PADDLE_W / 2)) * 0.06

    # brick hit (tile under the ball centre)
    tx = int((bx + 3) // BW)
    ty = int((by + 3 - BRICK_Y) // BH)
    if 0 <= tx < COLS and 0 <= ty < ROWS:
        cell = bricks.tile(tx, ty)
        if cell:
            bricks.tile(tx, ty, 0)
            bricks_left -= 1
            score += 10
            vy = -vy
            cx, cy = tx * BW + BW // 2, BRICK_Y + ty * BH + BH // 2
            particles.emit(cx, cy, 14, 3, 22, brick_colors[cell - 1])

    if by > H:                          # missed
        lives -= 1
        flash.pulse()                   # juice: flash the screen on a lost ball
        if lives <= 0:
            reset_ball()
            score = 0
            lives = 3
            for ty in range(ROWS):
                for tx in range(COLS):
                    bricks.tile(tx, ty, 1 + (ty % 4))
            bricks_left = COLS * ROWS
        else:
            reset_ball()

    if bricks_left == 0:                # cleared -> new wall
        for ty in range(ROWS):
            for tx in range(COLS):
                bricks.tile(tx, ty, 1 + (ty % 4))
        bricks_left = COLS * ROWS
        reset_ball()

    ball.move(int(bx), int(by))
    particles.tick()
    score_label.set("SCORE %05d   LIVES %d" % (score, lives))   # re-renders only on change
    scene.refresh()                                             # paints the fixed HUD layer too
    clock.tick()
