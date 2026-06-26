# Snake on picogame - grid-stepped movement with a turn queue and self/wall
# collision. The board is a pg.Tilemap (the engine's cheap grid: read/write cells,
# O(1) collision), so a step is just two cell writes - no per-step full redraw and
# no fixed sprite pool. Uses picogame_shapes for the tileset and picogame_ui for the HUD.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_ui.py, picogame_shapes.py. Needs the latest firmware.

from collections import deque
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_rand
import picogame_shapes as shp
import picogame_ui as ui

W, H = 320, 240
TILE = 10
COLS, ROWS = 30, 21
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


def place_food():
    global food
    while True:
        fx, fy = rng.randint(0, COLS - 1), rng.randint(0, ROWS - 1)
        if grid.tile(fx, fy) == 0:
            food = (fx, fy)
            grid.tile(fx, fy, FOOD)
            return


def new_game():
    global body, direction, want, grow, score
    grid.fill(0)
    body = deque((), COLS * ROWS)        # ordered cells, head at the right end
    hx, hy = COLS // 2, ROWS // 2
    body.append((hx, hy))
    grid.tile(hx, hy, HEAD)
    direction = (1, 0)
    want = (1, 0)
    grow = 3
    score = 0
    place_food()


new_game()
print("D-pad to steer. Eat the red food, don't bite yourself or the walls.")
step = 0
while True:
    btn.poll()

    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    # queue a turn (no instant reversal)
    if dx and (dx, 0) != (-direction[0], 0):
        want = (dx, 0)
    elif dy and (0, dy) != (0, -direction[1]):
        want = (0, dy)

    step += 1
    if step >= 5:                          # advance one cell every 5 frames
        step = 0
        direction = want
        hx, hy = body[-1]
        nx, ny = hx + direction[0], hy + direction[1]
        cell = grid.tile(nx, ny) if 0 <= nx < COLS and 0 <= ny < ROWS else BODY
        if nx < 0 or nx >= COLS or ny < 0 or ny >= ROWS or cell == BODY or cell == HEAD:
            new_game()                     # crash -> restart
        else:
            grid.tile(hx, hy, BODY)        # old head becomes body
            grid.tile(nx, ny, HEAD)        # new head
            body.append((nx, ny))
            if cell == FOOD:
                score += 10
                grow += 2
                place_food()
            if grow > 0:
                grow -= 1
            elif len(body) > 1:
                ox, oy = body.popleft()    # drop the tail cell
                grid.tile(ox, oy, 0)

    hud.set("SCORE %04d   LEN %d" % (score, len(body)))
    scene.refresh()
    clock.tick()
