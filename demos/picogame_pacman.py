# TinyPacman on picogame - a maze/AI game (genre port of TinyJoypad's TinyPacman,
# PicoLibSDK). Exercises: a Tilemap used as the EAT-GRID (walls + pellets in one
# layer, pellets removed by tile(tx,ty,0) -> dirty-rect repaints just that cell),
# grid-locked movement with turn queuing, 4 ghosts with chase/scatter/frightened
# AI, the Sprite.bitmap setter (ghosts turn blue when frightened), pg.collide via
# tile coincidence, and a bundled-font HUD. Generated art.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_ui.py to CIRCUITPY. Needs the latest firmware.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_ui as ui
import picogame_shapes as shp
import picogame_fx as fx

BG = pg.rgb565(0, 0, 0)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

TILE = 10
# Tileset frame indices: 0 empty, 1 wall, 2 pellet, 3 power.
EMPTY, WALL, PELLET, POWER = 0, 1, 2, 3
# Compact maze: # wall, . pellet, o power, space = empty path, P pac, G ghost home.
MAZE = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "####.#   G   #.####",
    "####.# ##=## #.####",
    "    .  #GGG#  .    ",
    "####.# ##### #.####",
    "####.#       #.####",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#o.#.....P.....#.o#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]
ROWS = len(MAZE)
COLS = len(MAZE[0])
XOFF = (board.DISPLAY.width - COLS * TILE) // 2   # centre the maze horizontally at any width
YOFF = 22                                         # maze is ROWS*TILE=210 px -> +22 fits a 240-tall screen
SPEED = 2                      # px per step pac/ghosts advance; must divide TILE so that
                               # px/py can hit an exact multiple of TILE -> aligned()'s
                               # `px % TILE == 0` can ever be true (turns/eats only fire there)
FRIGHT_FRAMES = 180            # ~6s at 30fps that ghosts stay frightened after a power pellet


def dot_mask(big):
    # transparent TILE cell with a centred dot (pellet/power)
    data = bytearray(TILE * TILE)
    r = 2 if big else 1
    c = TILE // 2
    for y in range(TILE):
        for x in range(TILE):
            if abs(x - c) <= r and abs(y - c) <= r:
                data[y * TILE + x] = 1
    return data


# Tileset frames: 0 empty, 1 wall, 2 pellet, 3 power. shp.atlas() bakes the
# walls + centred-dot pellets into one multi-frame sheet (handles packing/stride).
empty = bytearray(TILE * TILE)
wall = bytearray(b"\x01" * (TILE * TILE))
tileset = shp.atlas([empty, wall, dot_mask(False), dot_mask(True)],
                    TILE, TILE, pg.rgb565(33, 33, 222))

maze = pg.Tilemap(tileset, COLS, ROWS)
maze.move(XOFF, YOFF)
scene.add(maze)

pac_start = (1, 1)
ghost_home = []


def fill_pellets():
    # (re)place the pellet/power tiles (values 2/3) from MAZE; returns the count.
    n = 0
    for ty in range(ROWS):
        for tx in range(COLS):
            ch = MAZE[ty][tx]
            if ch == ".":
                maze.tile(tx, ty, PELLET)
                n += 1
            elif ch == "o":
                maze.tile(tx, ty, POWER)
                n += 1
    return n


# wall pass + P/G detection (once), then lay the pellets via fill_pellets().
for ty in range(ROWS):
    for tx in range(COLS):
        ch = MAZE[ty][tx]
        if ch == "#":
            maze.tile(tx, ty, WALL)
        elif ch not in (".", "o"):
            maze.tile(tx, ty, EMPTY)
        if ch == "P":
            pac_start = (tx, ty)
        elif ch == "G":
            ghost_home.append((tx, ty))
_pellets_start = fill_pellets()

while len(ghost_home) < 4:
    ghost_home.append((COLS // 2, ROWS // 2))

# sprites: Pac-Man and the ghosts are round, so shp.circle() looks right for free
pac_bm = shp.circle(TILE, pg.rgb565(255, 230, 40))
GHOST_COLORS = [pg.rgb565(230, 40, 40), pg.rgb565(255, 150, 200),
                pg.rgb565(60, 230, 230), pg.rgb565(255, 170, 60)]
ghost_bms = [shp.circle(TILE, c) for c in GHOST_COLORS]
fright_bm = shp.circle(TILE, pg.rgb565(40, 40, 220))

pac = pg.Sprite(pac_bm, 0, 0)
ghosts = [pg.Sprite(ghost_bms[i], 0, 0) for i in range(4)]
scene.add_all(ghosts)
scene.add(pac)

hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 0), BG)
hud.reserve(24)
flash = fx.Fade(scene, board.DISPLAY.width, board.DISPLAY.height,
                color=pg.rgb565(255, 60, 60))   # juice: red flash when a ghost catches you

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIR_R, DIR_L, DIR_D, DIR_U = DIRS      # shared constants -> no per-frame tuple alloc

# game state (a State instance `st`)
# NOTE: the ghost-state dict list is named ghost_states to avoid colliding with
# the module-level `ghosts` Sprite list.
class State:
    def __init__(self):
        self.score = 0
        self.lives = 3
        self.fright = 0
        self.pac_tx = 0
        self.pac_ty = 0
        self.pac_px = 0
        self.pac_py = 0
        self.pac_dir = (0, 0)
        self.pac_want = (0, 0)
        self.ghost_states = []
        self.pellets_left = _pellets_start


st = State()


def tile_is_wall(tx, ty):
    if tx < 0 or tx >= COLS or ty < 0 or ty >= ROWS:
        return True
    return maze.tile(tx, ty) == WALL


def reset_positions():
    st.pac_tx, st.pac_ty = pac_start
    st.pac_px = pac_start[0] * TILE
    st.pac_py = pac_start[1] * TILE
    st.pac_dir = (0, 0)
    st.pac_want = (0, 0)
    st.ghost_states = []
    for i in range(4):
        gx, gy = ghost_home[i % len(ghost_home)]
        st.ghost_states.append({"px": gx * TILE, "py": gy * TILE,
                                "dir": (0, -1), "i": i})


def new_game():
    global st
    st = State()
    reset_positions()


def aligned(px, py):
    return px % TILE == 0 and py % TILE == 0


def ghost_choose(g):
    # at a tile centre, pick a non-reverse direction toward (chase) or away
    # (frightened) from pac; never into a wall.
    tx, ty = g["px"] // TILE, g["py"] // TILE
    rev = (-g["dir"][0], -g["dir"][1])
    best = None
    best_score = None
    for d in DIRS:
        if d == rev:
            continue
        if tile_is_wall(tx + d[0], ty + d[1]):
            continue
        nx, ny = tx + d[0], ty + d[1]
        dist = abs(nx - st.pac_tx) + abs(ny - st.pac_ty)
        sc = -dist if st.fright > 0 else dist
        # lower sc = better (chase: min dist; fright: max dist via negation)
        if best_score is None or sc < best_score:
            best_score = sc
            best = d
    if best is None:
        best = rev    # dead end -> reverse
    g["dir"] = best


new_game()
# HUD shadow: only reformat+draw the Label when SCORE/LIVES actually change.
_hud_score = -1
_hud_lives = -2
was_fright = False                    # edge-track fright so we swap ghost bitmaps once per edge
print("D-pad to move. Eat all pellets; power pellets let you eat the blue ghosts.")
while True:
    btn.poll()
    flash.tick()                      # animate the hit-flash (no-op while idle)
    if st.fright > 0:
        st.fright -= 1

    # frightened look: swap all 4 ghost bitmaps only on the fright start/expire edge
    fright_now = st.fright > 0
    if fright_now != was_fright:
        was_fright = fright_now
        for i in range(4):
            ghosts[i].bitmap = fright_bm if fright_now else ghost_bms[i]

    # --- pac ---
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx:
        st.pac_want = DIR_R if dx > 0 else DIR_L
    elif dy:
        st.pac_want = DIR_D if dy > 0 else DIR_U

    px, py = st.pac_px, st.pac_py
    if aligned(px, py):
        tx, ty = px // TILE, py // TILE
        w = st.pac_want
        if w != (0, 0) and not tile_is_wall(tx + w[0], ty + w[1]):
            st.pac_dir = w
        d = st.pac_dir
        if d != (0, 0) and tile_is_wall(tx + d[0], ty + d[1]):
            st.pac_dir = (0, 0)
        # eat
        cell = maze.tile(tx, ty)
        if cell == PELLET:
            maze.tile(tx, ty, EMPTY)
            st.score += 10
            st.pellets_left -= 1
        elif cell == POWER:
            maze.tile(tx, ty, EMPTY)
            st.score += 50
            st.fright = FRIGHT_FRAMES
            st.pellets_left -= 1
        st.pac_tx, st.pac_ty = tx, ty
    d = st.pac_dir
    px += d[0] * SPEED
    py += d[1] * SPEED
    # horizontal tunnel wrap
    if px < -TILE:
        px = COLS * TILE
    elif px > COLS * TILE:
        px = -TILE
    st.pac_px, st.pac_py = px, py
    pac.move(XOFF + px, YOFF + py)

    # --- ghosts ---
    for g in st.ghost_states:
        if aligned(g["px"], g["py"]):
            ghost_choose(g)
        gd = g["dir"]
        g["px"] += gd[0] * SPEED
        g["py"] += gd[1] * SPEED
        gspr = ghosts[g["i"]]
        gspr.move(XOFF + g["px"], YOFF + g["py"])
        # collision with pac (native box overlap; both are TILE-sized)
        if pac.overlaps(gspr):
            if st.fright > 0:
                st.score += 200
                hx, hy = ghost_home[g["i"] % len(ghost_home)]
                g["px"], g["py"] = hx * TILE, hy * TILE
                g["dir"] = (0, -1)
            else:
                st.lives -= 1
                flash.pulse()           # juice: flash the screen when caught
                if st.lives < 0:
                    new_game()
                else:
                    reset_positions()
                break

    if st.pellets_left <= 0:           # cleared -> rebuild pellets
        st.pellets_left = fill_pellets()
        reset_positions()

    if st.score != _hud_score or st.lives != _hud_lives:
        _hud_score = st.score
        _hud_lives = st.lives
        hud.set("SCORE %05d   LIVES %d" % (st.score, max(0, st.lives)))
    scene.refresh()
    clock.tick()
