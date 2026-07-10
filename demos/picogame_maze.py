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

# flat COLS*ROWS bytearrays indexed [y*COLS + x] (was list-of-lists ~10 KB in ~58 GC blocks).
maze = bytearray(COLS * ROWS)                   # generated layout (WALL/FLOOR/DOOR)
seen = bytearray(COLS * ROWS)                   # 0/1 revealed flag


class State:
    def __init__(self):
        self.px = 1
        self.py = 1
        self.dx = 1
        self.dy = 1
        self.level = 1
        self.reveal_door = 0


st = State()


def generate():
    # iterative recursive-backtracker on odd cells (avoids deep recursion on device)
    for i in range(COLS * ROWS):
        maze[i] = WALL
        seen[i] = 0
    sx, sy = 1, 1
    maze[sy * COLS + sx] = FLOOR
    stack = [(sx, sy)]
    while stack:
        x, y = stack[-1]
        nb = []
        for ddx, ddy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            nx, ny = x + ddx, y + ddy
            if 1 <= nx < COLS - 1 and 1 <= ny < ROWS - 1 and maze[ny * COLS + nx] == WALL:
                nb.append((nx, ny, ddx, ddy))
        if nb:
            nx, ny, ddx, ddy = rng.choice(nb)
            maze[(y + ddy // 2) * COLS + (x + ddx // 2)] = FLOOR
            maze[ny * COLS + nx] = FLOOR
            stack.append((nx, ny))
        else:
            stack.pop()


def place_door():
    # a floor cell far (bottom-right quadrant) from the start
    for _ in range(200):
        x = COLS - 2 - rng.below(COLS // 2)
        y = ROWS - 2 - rng.below(ROWS // 2)
        if maze[y * COLS + x] == FLOOR:
            st.dx, st.dy = x, y
            maze[y * COLS + x] = DOOR
            return
    st.dx, st.dy = COLS - 2, ROWS - 2
    maze[st.dy * COLS + st.dx] = DOOR


def draw_all_hidden():
    tm.fill(HIDDEN)


def reveal(cx, cy):
    # reveal a 5x5 area around (cx,cy); paint newly-seen cells' real tile (floor/wall/door)
    for y in range(max(0, cy - 2), min(ROWS, cy + 3)):
        for x in range(max(0, cx - 2), min(COLS, cx + 3)):
            if not seen[y * COLS + x]:
                seen[y * COLS + x] = 1
                tm.tile(x, y, maze[y * COLS + x])


def new_level():
    generate()
    place_door()
    draw_all_hidden()
    st.px, st.py = 1, 1
    st.reveal_door = 0
    reveal(st.px, st.py)
    tm.tile(st.px, st.py, PLAYER)


new_level()
hud.draw()
print("Maze - arrows move, A reveals the door. Find the exit.")

while True:
    btn.poll()
    nx, ny = st.px, st.py
    # btn.repeat gives grid auto-repeat for free: True on press, then every 5 frames while held
    ddx = btn.repeat(btn.RIGHT, 5, 5) - btn.repeat(btn.LEFT, 5, 5)
    ddy = btn.repeat(btn.DOWN, 5, 5) - btn.repeat(btn.UP, 5, 5)
    if ddx:                                     # horizontal takes precedence over vertical
        nx += 1 if ddx > 0 else -1
    elif ddy:
        ny += 1 if ddy > 0 else -1

    if (nx != st.px or ny != st.py) and 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny * COLS + nx] != WALL:
        tm.tile(st.px, st.py, maze[st.py * COLS + st.px])   # restore the tile we leave (floor/door)
        st.px, st.py = nx, ny
        if st.px == st.dx and st.py == st.dy:     # reached the exit -> next level
            st.level += 1
            title.set("MAZE  LVL %d" % st.level)
            hud.draw()
            new_level()
        else:
            reveal(st.px, st.py)
            tm.tile(st.px, st.py, PLAYER)

    # A = flash the hidden door location as a hint, then restore it
    if btn.just_pressed(btn.A):
        st.reveal_door = 24
    if st.reveal_door > 0:
        st.reveal_door -= 1
        if st.reveal_door == 0:
            tm.tile(st.dx, st.dy, DOOR if seen[st.dy * COLS + st.dx] else HIDDEN)   # restore
        else:
            tm.tile(st.dx, st.dy, DOOR if (st.reveal_door // 4) % 2 else HIDDEN)   # blink

    scene.refresh()
    clock.tick()
