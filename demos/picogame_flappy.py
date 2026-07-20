# Flappy on picogame - one-button gravity + an endless stream of scrolling gap
# obstacles. Tests continuous horizontal obstacle scrolling on a fixed pool, simple
# physics, and gap collision. Tall pipe sprites SHARE one bitmap (positioned so only
# part shows), so 8 pipe sprites cost one 30x240 bitmap. Uses picogame_shapes.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_ui.py, picogame_shapes.py, picogame_pool.py.
# Needs the latest firmware.

import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_ui as ui
import picogame_shapes as shp
import picogame_pool
import picogame_synth as snd
import picogame_sfx

W, H = board.DISPLAY.width, board.DISPLAY.height
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

bird = pg.Sprite(shp.circle(18, pg.rgb565(255, 220, 40)), BIRD_X, 120)
bird.anchor = (0.5, 0.5)
PIPE_BM_H = 120                    # visible pipe segments are never taller than ~112px
pipe_bm = shp.rect(PIPE_W, PIPE_BM_H, pg.rgb565(70, 200, 90))
# Two fixed pools (top + bottom) sharing one tall bitmap; per-pipe state lives on
# the top sprite's `.data`. The pipes are always live, so we spawn() them once.
tops = picogame_pool.Pool(scene, pipe_bm, N_PIPES)
bottoms = picogame_pool.Pool(scene, pipe_bm, N_PIPES)
pipes = []        # each: (top_sprite, bottom_sprite)
for i in range(N_PIPES):
    t = tops.spawn()
    b = bottoms.spawn()
    t.data = {"x": 0, "gap": 0, "scored": False}   # per-pipe dict made ONCE; place_pipe mutates it
    pipes.append((t, b))
scene.add(bird)

hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)
hud.reserve(16)

by = 120.0
vy = 0.0
score = 0
dead = 0


def place_pipe(p, x):
    t, b = p
    gap_y = random.randint(50, H - 50 - GAP)
    d = t.data                         # mutate the pipe's existing dict (no per-recycle alloc)
    d["x"] = x
    d["gap"] = gap_y
    d["scored"] = False
    t.move(x, gap_y - PIPE_BM_H)       # top pipe: bottom edge at gap_y
    b.move(x, gap_y + GAP)             # bottom pipe: top edge at gap_y+GAP


def new_game():
    global by, vy, score, dead
    by = 120.0
    vy = 0.0
    score = 0
    dead = 0
    bird.move(BIRD_X, 120)
    for i, p in enumerate(pipes):
        place_pipe(p, W + i * SPACING)


new_game()
kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if no audio
print("Press B (or A) to flap. Thread the gaps.")


def main():
    global by, score, vy
    # --- per-frame loop in a FUNCTION: names become array-indexed locals, not globals-dict
    # lookups (measured on-device win; picogame-game-design hot-loop style guide).
    _hud_score = -1        # HUD shadow: reformat+draw the Label only when SCORE changes
    while True:
        btn.poll()

        if btn.just_pressed(btn.B) or btn.just_pressed(btn.A):
            vy = -6.0
            kit.jump()                 # flap
        vy = min(8.0, vy + 0.5)
        by += vy
        if by < 8:
            by = 8
            vy = 0
        if by > H - 8:                 # hit ground -> restart
            kit.explosion()
            new_game()
            continue
        bird.move(BIRD_X, int(by))

        for t, b in pipes:
            d = t.data
            d["x"] -= SPEED
            x = d["x"]
            if x < -PIPE_W:
                rightmost = max(pp[0].data["x"] for pp in pipes)   # x of the pipe currently furthest right
                place_pipe((t, b), rightmost + SPACING)            # recycle this pipe one gap beyond it
                continue
            t.move(x, d["gap"] - PIPE_BM_H)
            b.move(x, d["gap"] + GAP)
            # score when bird passes the pipe centre
            if not d["scored"] and x + PIPE_W < BIRD_X:
                d["scored"] = True
                score += 1
                kit.coin()             # passed a pipe
            # collision: the bird's box touches either pipe; the gap between them is safe
            if bird.overlaps(t) or bird.overlaps(b):
                kit.explosion()
                new_game()
                break

        scene.refresh()
        kit.tick()
        if score != _hud_score:
            _hud_score = score
            hud.set("SCORE %d" % score)
        clock.tick()


main()
