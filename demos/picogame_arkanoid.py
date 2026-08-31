# Arkanoid / Breakout on picogame - a size-independent showcase of most engine pillars at once:
# a Tilemap brick wall (bricks cleared on hit), Sprites (paddle + ball), pg.collide, Particles
# (break bursts), a bundled-font HUD, and the setup/input/clock helpers. Genre port of TinyJoypad's
# TinyArkanoid.
#
# The screen size is READ FROM THE DISPLAY and the layout is derived from it (brick width = W/COLS),
# so the SAME file runs on a 320-wide PicoPad and a 240-wide PicoSystem alike - the recommended way
# to write an example (don't hardcode 320x240). Copy with picogame_game.py / picogame_input.py /
# picogame_clock.py / picogame_shapes.py / picogame_ui.py (+ picogame_font.py, used by ui) to CIRCUITPY.


import math
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

W, H = picogame_game.screen()   # 240x240 on PicoSystem
COLS, ROWS = 10, 6                                 # brick wall: 10 x 6
BW, BH = W // COLS, 16                              # brick size (BW = 24 at W=240)
BRICK_Y = 28                                       # wall top (HUD strip above it)

# Tileset: frame 0 = empty (transparent), 1..4 = solid coloured bricks. The helper
# builds the 'empty + N solid tiles' arkanoid sheet; pal[i] is the colour of tile i.
BRICK_COLS = [pg.rgb565(220, 70, 70), pg.rgb565(230, 150, 50),
              pg.rgb565(70, 200, 90), pg.rgb565(80, 150, 230)]
# One brick type per row ON PURPOSE - genre SS1 lists silver/gold tiers as nice-to-have; a demo ships the MVP.
tileset = shp.tileset_colors(BW, BH, BRICK_COLS)
# Readable bricks: bake a 1px mortar edge (transparent -> the dark BG shows through) into each solid
# tile. Identity is carried by silhouette, not colour alone - touching same-colour fills read as one slab.
_d, _stride = tileset.data, BW * (len(BRICK_COLS) + 1)
for _f in range(1, len(BRICK_COLS) + 1):
    for _x in range(BW):
        _d[(BH - 1) * _stride + _f * BW + _x] = 0     # bottom mortar line
    for _y in range(BH):
        _d[_y * _stride + _f * BW + BW - 1] = 0       # right mortar line
pal = [pg.rgb565(0, 0, 0)] + BRICK_COLS


def fill_wall():
    """(Re)fill the brick wall; return the brick count."""
    for ty in range(ROWS):
        for tx in range(COLS):
            bricks.set_tile(tx, ty, 1 + (ty % 4))
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
score_label.reserve(len("SCORE 00000  LIVES 0  A:SERVE"))

# Ball state (kept as floats for smooth sub-pixel motion).
MAX_ANG = math.radians(60)      # paddle steers within +-60 deg of straight up; cos(60)=0.5
                                #  -> |vy| >= speed/2, the min-vy clamp is built into the formula
SPEED0 = 3.2                    # serve speed (px/frame @ 40 fps)
SPEED_STEPS = (4, 8, 12)        # rally hits that step the speed up (the original Breakout schedule)
SPEED_MAX = 5.0
bx, by = W / 2.0, H / 2.0
vx, vy = 0.0, 0.0
speed = SPEED0
hits = 0                        # paddle hits this rally (resets on serve)
serving = True                  # ball rides the paddle until A serves it
score = 0
lives = 3
_shown_score, _shown_lives, _shown_serving = -1, -1, None


def steer(rel):
    """Player-authored angle: -1..+1 across the paddle -> velocity at the current speed."""
    global vx, vy
    a = max(-1.0, min(1.0, rel)) * MAX_ANG
    vx = speed * math.sin(a)
    vy = -speed * math.cos(a)


kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if the board has no audio
print("L/R: move the paddle | A: serve. Break all the bricks!")
while True:
    btn.poll()
    move = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if move:
        paddle.move(max(0, min(W - PADDLE_W, paddle.x + move * 5)), paddle.y)

    if serving:                                    # ball rides the paddle; A serves it
        bx = paddle.x + (PADDLE_W - BALL) / 2.0
        by = paddle.y - BALL - 1
        vx = vy = 0.0                              # parked (a lost rally's velocity must not leak in)
        if btn.just_pressed(btn.A):
            serving = False
            speed, hits = SPEED0, 0
            steer(0.35 if paddle.x + PADDLE_W / 2 < W / 2 else -0.35)   # serve toward the open side

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
        hits += 1
        if hits in SPEED_STEPS:                    # rally speed-up: 4th, 8th, 12th paddle hit
            speed = min(speed + 0.5, SPEED_MAX)
        steer((bx + BALL / 2 - (paddle.x + PADDLE_W / 2)) / (PADDLE_W / 2))
        kit.blip()                                 # paddle bounce (light tick)

    # Brick hit - test the tile under the ball centre.
    tx = int((bx + BALL / 2) // BW)
    ty = int((by + BALL / 2 - BRICK_Y) // BH)
    if 0 <= tx < COLS and 0 <= ty < ROWS:
        cell = bricks.get_tile(tx, ty)
        if cell:
            bricks.set_tile(tx, ty, 0)
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
        serving = True

    if bricks_left == 0:                           # wall cleared -> a fresh one
        kit.powerup()                              # milestone
        bricks_left = fill_wall()
        serving = True

    ball.move(int(bx), int(by))
    particles.tick()
    if score != _shown_score or lives != _shown_lives or serving != _shown_serving:
        _shown_score, _shown_lives, _shown_serving = score, lives, serving
        score_label.set("SCORE %05d  LIVES %d%s"                    # re-renders only on change
                        % (score, lives, "  A:SERVE" if serving else ""))
    kit.tick()
    scene.refresh()                                             # paints the world + the fixed HUD layer
    clock.tick()
