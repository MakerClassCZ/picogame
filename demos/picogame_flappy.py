# Flappy on picogame - one-button gravity + an endless stream of scrolling gap
# obstacles. Tests continuous horizontal obstacle scrolling on a fixed pool, simple
# physics, and gap collision. Tall pipe sprites SHARE one bitmap (positioned so only
# part shows), so 8 pipe sprites cost one 30x240 bitmap. Uses picogame_shapes.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_font.py, picogame_shapes.py, picogame_pool.py.
# Needs the latest firmware.

import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_font
import picogame_shapes as shp
import picogame_pool

W, H = 320, 240
BG = pg.rgb565(90, 180, 230)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

PIPE_W = 34
GAP = 78
SPEED = 3
N_PIPES = 4
SPACING = 110
BIRD_X = 70
BIRD_R = 9

bird = pg.Sprite(shp.circle(18, pg.rgb565(255, 220, 40)), BIRD_X, 120)
bird.anchor = (0.5, 0.5)
pipe_bm = shp.rect(PIPE_W, H, pg.rgb565(70, 200, 90))
# Two fixed pools (top + bottom) sharing one tall bitmap; per-pipe state lives on
# the top sprite's `.data`. The pipes are always live, so we spawn() them once.
tops = picogame_pool.Pool(scene, pipe_bm, N_PIPES)
bottoms = picogame_pool.Pool(scene, pipe_bm, N_PIPES)
pipes = []        # each: (top_sprite, bottom_sprite)
for i in range(N_PIPES):
    t = tops.spawn()
    b = bottoms.spawn()
    pipes.append((t, b))
scene.add(bird)

hud = picogame_font.Label(pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)
S = {}


def place_pipe(p, x):
    t, b = p
    gap_y = random.randint(50, H - 50 - GAP)
    t.data = {"x": x, "gap": gap_y, "scored": False}
    t.move(x, gap_y - H)               # top pipe: bottom edge at gap_y
    b.move(x, gap_y + GAP)             # bottom pipe: top edge at gap_y+GAP


def new_game():
    S.update(by=120.0, vy=0.0, score=0, dead=0)
    bird.move(BIRD_X, 120)
    for i, p in enumerate(pipes):
        place_pipe(p, W + i * SPACING)


new_game()
print("Press B (or A) to flap. Thread the gaps.")
frame = 0
while True:
    btn.poll()
    frame += 1

    if btn.just_pressed(btn.B) or btn.just_pressed(btn.A):
        S["vy"] = -6.0
    S["vy"] = min(8.0, S["vy"] + 0.5)
    S["by"] += S["vy"]
    if S["by"] < 8:
        S["by"] = 8
        S["vy"] = 0
    if S["by"] > H - 8:                 # hit ground -> restart
        new_game()
        continue
    bird.move(BIRD_X, int(S["by"]))

    for t, b in pipes:
        d = t.data
        d["x"] -= SPEED
        x = d["x"]
        if x < -PIPE_W:
            place_pipe((t, b), max(pp[0].data["x"] for pp in pipes) + SPACING)
            continue
        t.move(x, d["gap"] - H)
        b.move(x, d["gap"] + GAP)
        # score when bird passes the pipe centre
        if not d["scored"] and x + PIPE_W < BIRD_X:
            d["scored"] = True
            S["score"] += 1
        # collision: the bird's box touches either pipe; the gap between them is safe
        if bird.overlaps(t) or bird.overlaps(b):
            new_game()
            break

    scene.refresh()
    hud.set("SCORE %d" % S["score"])
    hud.draw(board.DISPLAY, bufA)
    clock.tick()
