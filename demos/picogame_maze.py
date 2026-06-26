# Maze - a top-down hidden maze, ported from PicoLibSDK (Miroslav Nemecek) as a picogame
# exercise in Tilemap + procedural generation + fog-of-war. The maze is generated fresh each
# level (iterative recursive-backtracker); only the cells near you are revealed, so you explore
# blind to find the hidden DOOR. Reach it to advance.
#
# Controls: arrows = move one cell, A = briefly reveal the door (help). Copy picogame_* helpers.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui
import picogame_rand

W, H = board.DISPLAY.width, board.DISPLAY.height
T = 8                                           # tile size
BAR = 14
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 8, 14), strip_h=12, top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

COLS = W // T                                   # 40
ROWS = (H - BAR) // T                           # 28
# tile frames: 0 hidden, 1 floor, 2 wall, 3 door, 4 player
TILES = shp.tileset_colors(T, T, [
    pg.rgb565(10, 10, 16),                      # 0 hidden (fog)
    pg.rgb565(44, 44, 60),                      # 1 floor
    pg.rgb565(120, 92, 60),                     # 2 wall
    pg.rgb565(80, 220, 110),                    # 3 door
    pg.rgb565(255, 210, 80),                    # 4 player
])
HIDDEN, FLOOR, WALL, DOOR, PLAYER = 0, 1, 2, 3, 4
tm = pg.Tilemap(TILES, COLS, ROWS)
scene.add(tm)
tm.move(0, BAR)

hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, pg.rgb565(14, 16, 30))
title = hud.label(terminalio.FONT, 4, 1, pg.rgb565(255, 255, 255), "MAZE  LVL 1")

rng = picogame_rand.Rand(0x1234)               # seeded -> reproducible maze layouts

maze = [[WALL] * COLS for _ in range(ROWS)]     # generated layout (WALL/FLOOR/DOOR)
seen = [[False] * COLS for _ in range(ROWS)]
px = py = 1
dx = dy = 1
level = 1
reveal_door = 0


def generate():
    # iterative recursive-backtracker on odd cells (avoids deep recursion on device)
    for y in range(ROWS):
        for x in range(COLS):
            maze[y][x] = WALL
            seen[y][x] = False
    sx, sy = 1, 1
    maze[sy][sx] = FLOOR
    stack = [(sx, sy)]
    while stack:
        x, y = stack[-1]
        nb = []
        for ddx, ddy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = x + ddx, y + ddy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1 and maze[ny][nx] == WALL:
                nb.append((nx, ny, ddx, ddy))
        if nb:
            nx, ny, ddx, ddy = rng.choice(nb)
            maze[y + ddy // 2][x + ddx // 2] = FLOOR
            maze[ny][nx] = FLOOR
            stack.append((nx, ny))
        else:
            stack.pop()


def place_door():
    # a floor cell far (bottom-right quadrant) from the start
    global dx, dy
    for _ in range(200):
        x = COLS - 2 - rng.below(COLS // 2)
        y = ROWS - 2 - rng.below(ROWS // 2)
        if maze[y][x] == FLOOR:
            dx, dy = x, y
            maze[y][x] = DOOR
            return
    dx, dy = COLS - 2, ROWS - 2
    maze[dy][dx] = DOOR


def draw_all_hidden():
    for y in range(ROWS):
        for x in range(COLS):
            tm.tile(x, y, HIDDEN)


def reveal(cx, cy):
    # reveal a 5x5 area around (cx,cy); paint newly-seen cells' real tile (floor/wall/door)
    for y in range(max(0, cy - 2), min(ROWS, cy + 3)):
        for x in range(max(0, cx - 2), min(COLS, cx + 3)):
            if not seen[y][x]:
                seen[y][x] = True
                tm.tile(x, y, maze[y][x])


def new_level():
    global px, py, reveal_door
    generate()
    place_door()
    draw_all_hidden()
    px, py = 1, 1
    reveal_door = 0
    reveal(px, py)
    tm.tile(px, py, PLAYER)


new_level()
hud.redraw()
print("Maze - arrows move, A reveals the door. Find the exit.")

move_cd = 0
while True:
    btn.poll()
    nx, ny = px, py
    ddx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    ddy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if move_cd > 0:
        move_cd -= 1
    if (ddx or ddy) and move_cd == 0:           # move on press, then auto-repeat while held
        if ddx:
            nx += 1 if ddx > 0 else -1
        elif ddy:
            ny += 1 if ddy > 0 else -1
        move_cd = 5
    elif not (ddx or ddy):
        move_cd = 0                             # released -> next press is immediate

    if (nx, ny) != (px, py) and 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] != WALL:
        tm.tile(px, py, maze[py][px])           # restore the tile we leave (floor/door)
        px, py = nx, ny
        if (px, py) == (dx, dy):                 # reached the exit -> next level
            level += 1
            hud.set_text(title, "MAZE  LVL %d" % level)
            hud.redraw()
            new_level()
        else:
            reveal(px, py)
            tm.tile(px, py, PLAYER)

    # A = flash the hidden door location as a hint, then restore it
    if btn.just_pressed(btn.A):
        reveal_door = 24
    if reveal_door > 0:
        reveal_door -= 1
        if reveal_door == 0:
            tm.tile(dx, dy, DOOR if seen[dy][dx] else HIDDEN)   # restore
        else:
            tm.tile(dx, dy, DOOR if (reveal_door // 4) % 2 else HIDDEN)   # blink

    scene.refresh()
    clock.tick()
