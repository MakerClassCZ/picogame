# Arkanoid / Breakout on picogame - a size-independent showcase of most engine pillars at once:
# a Tilemap brick wall (bricks cleared on hit), Sprites (paddle + ball), pg.collide, Particles
# (break bursts), a bundled-font HUD, and the setup/input/clock helpers. Genre port of TinyJoypad's
# TinyArkanoid.
#
# The screen size is READ FROM THE DISPLAY and the layout is derived from it (brick width = W/COLS),
# so the SAME file runs on a 320-wide PicoPad and a 240-wide PicoSystem alike - the recommended way
# to write an example (don't hardcode 320x240). Copy with picogame_game.py / picogame_input.py /
# picogame_clock.py / picogame_shapes.py / picogame_ui.py (+ picogame_font.py, used by ui) to CIRCUITPY.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui
import picogame_synth as snd
import picogame_sfx

BG = pg.rgb565(8, 10, 24)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

W, H = board.DISPLAY.width, board.DISPLAY.height   # 240x240 on PicoSystem
COLS, ROWS = 10, 6                                 # brick wall: 10 x 6
BW, BH = W // COLS, 16                              # brick size (BW = 24 at W=240)
BRICK_Y = 28                                       # wall top (HUD strip above it)

# Tileset: frame 0 = empty (transparent), 1..4 = solid coloured bricks. The helper
# builds the 'empty + N solid tiles' arkanoid sheet; pal[i] is the colour of tile i.
BRICK_COLS = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
              pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
tileset = shp.tileset_colors(BW, BH, BRICK_COLS)
pal = [pg.rgb565(0, 0, 0)] + BRICK_COLS


def fill_wall():
    """(Re)fill the brick wall; return the brick count."""
    for ty in range(ROWS):
        for tx in range(COLS):
            bricks.tile(tx, ty, 1 + (ty % 4))
    return COLS * ROWS


bricks = pg.Tilemap(tileset, COLS, ROWS)
bricks.move(0, BRICK_Y)
bricks_left = fill_wall()


PADDLE_W, PADDLE_H = 44, 8
BALL = 6
paddle = pg.Sprite(shp.rect(PADDLE_W, PADDLE_H, pg.rgb565(220, 220, 230)), (W - PADDLE_W) // 2, H - 16)
ball = pg.Sprite(shp.rect(BALL, BALL, pg.rgb565(255, 240, 120)), W // 2, H // 2)
particles = pg.Particles(64, size=2, gravity=0.12)

scene.add_all([bricks, particles, paddle, ball])
# HUD as a fixed scene layer: scene.refresh() paints it (no extra per-frame draw).
score_label = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, pg.rgb565(255, 255, 255), BG)
score_label.reserve(21)

# Ball state (kept as floats for smooth sub-pixel motion).
bx, by = W / 2.0, H / 2.0
vx, vy = 2.4, -2.6
score = 0
lives = 3
_shown_score, _shown_lives = -1, -1


def reset_ball():
    global bx, by, vx, vy
    bx, by = W / 2.0, H / 2.0
    vx, vy = 2.4, -2.6
    ball.move(int(bx), int(by))


kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if the board has no audio
print("D-pad / L-R: move the paddle. Break all the bricks!")
while True:
    btn.poll()
    move = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if move:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + move * 5)), paddle.y)

    bx += vx
    by += vy
    if bx < 0:                                     # left/right walls
        bx = 0; vx = -vx
    elif bx > W - BALL:
        bx = W - BALL; vx = -vx
    if by < 0:                                     # ceiling
        by = 0; vy = -vy

    # Paddle bounce - steer by where the ball hits the paddle.
    if vy > 0 and pg.collide(int(bx), int(by), int(bx) + BALL, int(by) + BALL,
                             paddle.x, paddle.y, paddle.x + PADDLE_W, paddle.y + PADDLE_H):
        vy = -abs(vy)
        vx += (bx + BALL / 2 - (paddle.x + PADDLE_W / 2)) * 0.06
        vx = max(-4.0, min(4.0, vx))
        kit.blip()                                 # paddle bounce (light tick)

    # Brick hit - test the tile under the ball centre.
    tx = int((bx + BALL / 2) // BW)
    ty = int((by + BALL / 2 - BRICK_Y) // BH)
    if 0 <= tx < COLS and 0 <= ty < ROWS:
        cell = bricks.tile(tx, ty)
        if cell:
            bricks.tile(tx, ty, 0)
            bricks_left -= 1
            score += 10
            vy = -vy
            cx = tx * BW + BW // 2
            cy = BRICK_Y + ty * BH + BH // 2
            particles.emit(cx, cy, 14, 3, 22, pal[cell])
            kit.hit()                              # brick break (rotates pitch on a fast rally)

    if by > H:                                     # missed the ball
        lives -= 1
        if lives <= 0:                             # game over -> restart
            kit.explosion()
            score, lives = 0, 3
            bricks_left = fill_wall()
        else:
            kit.hurt()                             # lost a life
        reset_ball()

    if bricks_left == 0:                           # wall cleared -> a fresh one
        kit.powerup()                              # milestone
        bricks_left = fill_wall()
        reset_ball()

    ball.move(int(bx), int(by))
    particles.tick()
    if score != _shown_score or lives != _shown_lives:
        _shown_score, _shown_lives = score, lives
        score_label.set("SCORE %05d  LIVES %d" % (score, lives))    # re-renders only on change
    kit.tick()
    scene.refresh()                                             # paints the world + the fixed HUD layer
    clock.tick()
