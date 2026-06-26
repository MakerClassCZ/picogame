# TinyPacman on picogame - a maze/AI game (genre port of TinyJoypad's TinyPacman,
# PicoLibSDK). Exercises: a Tilemap used as the EAT-GRID (walls + pellets in one
# layer, pellets removed by tile(tx,ty,0) -> dirty-rect repaints just that cell),
# grid-locked movement with turn queuing, 4 ghosts with chase/scatter/frightened
# AI, the Sprite.bitmap setter (ghosts turn blue when frightened), pg.collide via
# tile coincidence, and a bundled-font HUD. Generated art.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_font.py to CIRCUITPY. Needs the latest firmware.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_font
import picogame_shapes as shp
import picogame_fx as fx

BG = pg.rgb565(0, 0, 0)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

TILE = 10
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
XOFF = (320 - COLS * TILE) // 2
YOFF = 22
SPEED = 2                      # must divide TILE


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

pellets_left = 0
pac_start = (1, 1)
ghost_home = []
for ty in range(ROWS):
    for tx in range(COLS):
        ch = MAZE[ty][tx]
        if ch == "#":
            maze.tile(tx, ty, 1)
        elif ch == ".":
            maze.tile(tx, ty, 2)
            pellets_left += 1
        elif ch == "o":
            maze.tile(tx, ty, 3)
            pellets_left += 1
        else:
            maze.tile(tx, ty, 0)
        if ch == "P":
            pac_start = (tx, ty)
        elif ch == "G":
            ghost_home.append((tx, ty))

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

hud = picogame_font.Label(pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 0), BG)
flash = fx.Fade(scene, board.DISPLAY.width, board.DISPLAY.height,
                color=pg.rgb565(255, 60, 60))   # juice: red flash when a ghost catches you

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
S = {}


def tile_is_wall(tx, ty):
    if tx < 0 or tx >= COLS or ty < 0 or ty >= ROWS:
        return True
    return maze.tile(tx, ty) == 1


def reset_positions():
    S["pac_tx"], S["pac_ty"] = pac_start
    S["pac_px"] = pac_start[0] * TILE
    S["pac_py"] = pac_start[1] * TILE
    S["pac_dir"] = (0, 0)
    S["pac_want"] = (0, 0)
    S["ghosts"] = []
    for i in range(4):
        gx, gy = ghost_home[i % len(ghost_home)]
        S["ghosts"].append({"px": gx * TILE, "py": gy * TILE,
                             "dir": (0, -1), "i": i})


def new_game():
    S.update(score=0, lives=3, fright=0)
    reset_positions()


def aligned(px, py):
    return px % TILE == 0 and py % TILE == 0


def move_entity(px, py, d):
    return px + d[0] * SPEED, py + d[1] * SPEED


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
        dist = abs(nx - S["pac_tx"]) + abs(ny - S["pac_ty"])
        sc = -dist if S["fright"] > 0 else dist
        # lower sc = better (chase: min dist; fright: max dist via negation)
        if best_score is None or sc < best_score:
            best_score = sc
            best = d
    if best is None:
        best = rev    # dead end -> reverse
    g["dir"] = best


new_game()
print("D-pad to move. Eat all pellets; power pellets let you eat the blue ghosts.")
frame = 0
while True:
    btn.poll()
    flash.tick()                      # animate the hit-flash (no-op while idle)
    frame += 1
    if S["fright"] > 0:
        S["fright"] -= 1

    # --- pac ---
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx or dy:
        S["pac_want"] = (dx, 0) if dx else (0, dy)

    px, py = S["pac_px"], S["pac_py"]
    if aligned(px, py):
        tx, ty = px // TILE, py // TILE
        w = S["pac_want"]
        if w != (0, 0) and not tile_is_wall(tx + w[0], ty + w[1]):
            S["pac_dir"] = w
        d = S["pac_dir"]
        if d != (0, 0) and tile_is_wall(tx + d[0], ty + d[1]):
            S["pac_dir"] = (0, 0)
        # eat
        cell = maze.tile(tx, ty)
        if cell == 2:
            maze.tile(tx, ty, 0)
            S["score"] += 10
            pellets_left -= 1
        elif cell == 3:
            maze.tile(tx, ty, 0)
            S["score"] += 50
            S["fright"] = 180
            pellets_left -= 1
        S["pac_tx"], S["pac_ty"] = tx, ty
    px, py = move_entity(px, py, S["pac_dir"])
    # horizontal tunnel wrap
    if px < -TILE:
        px = COLS * TILE
    elif px > COLS * TILE:
        px = -TILE
    S["pac_px"], S["pac_py"] = px, py
    pac.move(XOFF + px, YOFF + py)

    # --- ghosts ---
    for g in S["ghosts"]:
        if aligned(g["px"], g["py"]):
            ghost_choose(g)
        g["px"], g["py"] = move_entity(g["px"], g["py"], g["dir"])
        gx_s = XOFF + g["px"]
        gy_s = YOFF + g["py"]
        ghosts[g["i"]].move(gx_s, gy_s)
        # frightened look via bitmap swap
        ghosts[g["i"]].bitmap = fright_bm if S["fright"] > 0 else ghost_bms[g["i"]]
        # collision with pac (same tile)
        if abs(g["px"] - S["pac_px"]) < TILE and abs(g["py"] - S["pac_py"]) < TILE:
            if S["fright"] > 0:
                S["score"] += 200
                hx, hy = ghost_home[g["i"] % len(ghost_home)]
                g["px"], g["py"] = hx * TILE, hy * TILE
                g["dir"] = (0, -1)
            else:
                S["lives"] -= 1
                flash.pulse()           # juice: flash the screen when caught
                if S["lives"] < 0:
                    new_game()
                else:
                    reset_positions()
                break

    if pellets_left <= 0:           # cleared -> rebuild pellets
        for ty in range(ROWS):
            for tx in range(COLS):
                ch = MAZE[ty][tx]
                if ch == ".":
                    maze.tile(tx, ty, 2)
                    pellets_left += 1
                elif ch == "o":
                    maze.tile(tx, ty, 3)
                    pellets_left += 1
        reset_positions()

    hud.set("SCORE %05d   LIVES %d" % (S["score"], max(0, S["lives"])))
    hud.draw(board.DISPLAY, bufA)
    scene.refresh()
    clock.tick()
