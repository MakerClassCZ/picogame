# Snake on picogame - grid-stepped movement with a turn queue and self/wall
# collision. The board is a pg.Tilemap (the engine's cheap grid: read/write cells,
# O(1) collision), so a step is just two cell writes - no per-step full redraw and
# no fixed sprite pool. Uses picogame_shapes for the tileset and picogame_ui for the HUD.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_ui.py, picogame_shapes.py. Needs the latest firmware.

from collections import deque
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_rand
import picogame_shapes as shp
import picogame_ui as ui
import picogame_synth as snd
import picogame_sfx

W, H = board.DISPLAY.width, board.DISPLAY.height
TILE = 10
COLS, ROWS = W // TILE - 2, (H - 20) // TILE - 1   # leave a margin (1 tile each side/bottom, YOFF top)
XOFF = (W - COLS * TILE) // 2
YOFF = 20
BG = pg.rgb565(8, 16, 8)
BODY, HEAD, FOOD = 1, 2, 3                       # tile values (0 = empty board)

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
rng = picogame_rand.Rand()

# tileset: 0 shows the green board bg; 1 body, 2 head, 3 food.
tileset = shp.tileset_colors(TILE, TILE,
                             [pg.rgb565(80, 230, 90),
                              pg.rgb565(200, 255, 140),
                              pg.rgb565(240, 80, 80)])
grid = pg.Tilemap(tileset, COLS, ROWS)
grid.move(XOFF, YOFF)
scene.add(grid)

hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)
hud.reserve(20)


def place_food():
    while True:
        food_x, food_y = rng.randint(0, COLS - 1), rng.randint(0, ROWS - 1)
        if grid.tile(food_x, food_y) == 0:
            grid.tile(food_x, food_y, FOOD)
            return


class State:
    def __init__(self, body):
        self.body = body                     # ordered cells, head at the right end (reused across games)
        self.direction = (1, 0)
        self.want = (1, 0)
        self.grow = 3
        self.score = 0
        self.step = 0


_body = deque((), COLS * ROWS)   # allocated ONCE at startup; drained (not reallocated) on restart
st = State(_body)


def new_game():
    global st
    grid.fill(0)
    while len(_body):                        # drain in place instead of allocating a fresh deque
        _body.popleft()
    st = State(_body)
    hx, hy = COLS // 2, ROWS // 2
    st.body.append((hx, hy))
    grid.tile(hx, hy, HEAD)
    place_food()


kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if the board has no audio
new_game()
print("D-pad to steer. Eat the red food, don't bite yourself or the walls.")
_shown_score, _shown_len = -1, -1
while True:
    btn.poll()

    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    # queue a turn (no instant reversal)
    if dx and (dx, 0) != (-st.direction[0], 0):
        st.want = (dx, 0)
    elif dy and (0, dy) != (0, -st.direction[1]):
        st.want = (0, dy)

    st.step += 1
    if st.step >= 5:                       # advance one cell every 5 frames
        st.step = 0
        st.direction = st.want
        hx, hy = st.body[-1]
        nx, ny = hx + st.direction[0], hy + st.direction[1]
        cell = grid.tile(nx, ny) if 0 <= nx < COLS and 0 <= ny < ROWS else BODY
        if cell == BODY or cell == HEAD:       # out-of-bounds already maps to BODY above
            kit.explosion()                # crash
            new_game()                     # -> restart
        else:
            grid.tile(hx, hy, BODY)        # old head becomes body
            grid.tile(nx, ny, HEAD)        # new head
            st.body.append((nx, ny))
            if cell == FOOD:
                st.score += 10
                st.grow += 2
                kit.coin()                 # ate the food
                place_food()
            if st.grow > 0:
                st.grow -= 1
            elif len(st.body) > 1:
                ox, oy = st.body.popleft() # drop the tail cell
                grid.tile(ox, oy, 0)

    body_len = len(st.body)
    if st.score != _shown_score or body_len != _shown_len:
        _shown_score, _shown_len = st.score, body_len
        hud.set("SCORE %04d   LEN %d" % (st.score, body_len))
    kit.tick()                             # drive the SFX sequencer (coin is a 2-note rise)
    scene.refresh()
    clock.tick()
