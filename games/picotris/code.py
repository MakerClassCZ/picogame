# Picotris - a Tilemap + PLAY-AREA showcase. The well is a Tilemap in a RESERVED centre
# column (Scene left=/right=), so the scene paints ONLY that column; the side panels (score/lines/
# level + next-piece) are static chrome drawn once, never recomputed per frame. Dirty-rect means only
# the cells that actually change repaint. 7-bag randomiser, ghost piece, next preview, line-clear
# flash, level/speed ramp. Copy with picogame_game/input/clock/ui/rand (+ optional audio).

import array
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_rand
import picogame_ui as ui

try:
    import picogame_audio
    audio = picogame_audio.Audio()
    SFX = {"move": picogame_audio.tone(220, 35), "rot": picogame_audio.tone(330, 35),
           "lock": picogame_audio.tone(170, 60), "clear": picogame_audio.tone(880, 130)}
except Exception:
    audio = None
    SFX = {}


def sfx(name):
    if audio:
        audio.sfx(SFX[name])


W, H = board.DISPLAY.width, board.DISPLAY.height
COLS, ROWS, TILE = 10, 18, 12
WELL_W, WELL_H = COLS * TILE, ROWS * TILE             # 120 x 216
SIDE = (W - WELL_W) // 2                               # 100 -> reserve both margins
PY = (H - WELL_H) // 2                                 # 12
RX = W - SIDE                                           # right-panel origin x

COL_BG = pg.rgb565(12, 12, 20)                         # the well: a dark, recessed column
PANEL = pg.rgb565(30, 34, 54)                          # side panels: a lighter step = framed playfield
LABEL = pg.rgb565(150, 165, 205)
VALUE = pg.rgb565(235, 240, 255)

# The scene paints ONLY [SIDE, W-SIDE) x [0,H) - the well column. The two margins are ours to draw.
scene, bufA, bufB = picogame_game.setup(background=COL_BG, strip_h=12, left=SIDE, right=SIDE)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
rng = picogame_rand.Rand()

# pieces: name -> (colour index, [rotations]); each rotation = 4 (col,row) in a 4-box.
SHAPES = {
    "I": (1, [[(0, 1), (1, 1), (2, 1), (3, 1)], [(2, 0), (2, 1), (2, 2), (2, 3)]]),
    "O": (2, [[(1, 0), (2, 0), (1, 1), (2, 1)]]),
    "T": (3, [[(1, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (2, 1), (1, 2)],
              [(0, 1), (1, 1), (2, 1), (1, 2)], [(1, 0), (0, 1), (1, 1), (1, 2)]]),
    "S": (4, [[(1, 0), (2, 0), (0, 1), (1, 1)], [(1, 0), (1, 1), (2, 1), (2, 2)]]),
    "Z": (5, [[(0, 0), (1, 0), (1, 1), (2, 1)], [(2, 0), (1, 1), (2, 1), (1, 2)]]),
    "J": (6, [[(0, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (2, 0), (1, 1), (1, 2)],
              [(0, 1), (1, 1), (2, 1), (2, 2)], [(1, 0), (1, 1), (0, 2), (1, 2)]]),
    "L": (7, [[(2, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (1, 2), (2, 2)],
              [(0, 1), (1, 1), (2, 1), (0, 2)], [(0, 0), (1, 0), (1, 1), (1, 2)]]),
}
NAMES = list(SHAPES.keys())
# 7-bag: every piece once per shuffled cycle (no streaks/droughts), seedable via rng.
bag = picogame_rand.Bag(NAMES, rng)

# tileset frames: 0 empty | 1..7 piece colours (dark edge idx 8) | 8 white clear-flash | 9 ghost outline.
RGB = [(0, 0, 0), (60, 200, 220), (230, 220, 60), (190, 90, 220), (70, 200, 90),
       (220, 70, 70), (70, 110, 230), (230, 150, 50),
       (20, 20, 30), (78, 86, 120), (245, 248, 255)]   # 8=edge, 9=ghost dim, 10=white
pal = array.array("H", [pg.rgb565(*c) for c in RGB])
FRAMES = 10
stride = TILE * FRAMES
tdata = bytearray(stride * TILE)
for y in range(TILE):
    for x in range(TILE):
        edge = (x == 0 or y == 0 or x == TILE - 1 or y == TILE - 1)
        for f in range(1, 8):                          # solid colour tiles with a dark edge
            tdata[y * stride + f * TILE + x] = 8 if edge else f
        tdata[y * stride + 8 * TILE + x] = 10          # frame 8: solid white (line-clear flash)
        if edge:
            tdata[y * stride + 9 * TILE + x] = 9       # frame 9: ghost = dim outline, hollow
tileset = pg.Bitmap(tdata, TILE, TILE, format=pg.PAL8, palette=pal, frames=FRAMES, stride=stride, transparent=0)

well = pg.Tilemap(tileset, COLS, ROWS)
well.move(SIDE, PY)
scene.add(well)

# next-piece preview: one pre-built 32x32 mini-bitmap per shape (no per-spawn allocation), swapped in.
NTILE, NGRID = 8, 4
NEXT_BMP = {}
for nm, (col, rots) in SHAPES.items():
    nstride = NTILE * NGRID
    nd = bytearray(nstride * NTILE * NGRID)
    for (cx, cy) in rots[0]:
        for yy in range(NTILE):
            for xx in range(NTILE):
                edge = (xx == 0 or yy == 0 or xx == NTILE - 1 or yy == NTILE - 1)
                nd[(cy * NTILE + yy) * nstride + cx * NTILE + xx] = 8 if edge else col
    NEXT_BMP[nm] = pg.Bitmap(nd, nstride, NTILE * NGRID, format=pg.PAL8, palette=pal, transparent=0)

# --- side panels: static chrome the scene never repaints (one redraw; updated only on change) ---
left_panel = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, SIDE, H, PANEL)
left_panel.label(terminalio.FONT, 18, 14, VALUE, "PICOTRIS")
left_panel.label(terminalio.FONT, 8, H - 54, LABEL, "< >  move")
left_panel.label(terminalio.FONT, 8, H - 40, LABEL, "A   rotate")
left_panel.label(terminalio.FONT, 8, H - 26, LABEL, "v   drop")
left_panel.redraw()

right_panel = ui.HudBar(pg, board.DISPLAY, bufA, RX, 0, SIDE, H, PANEL)
right_panel.label(terminalio.FONT, RX + 10, 10, LABEL, "SCORE")
score_lbl = right_panel.label(terminalio.FONT, RX + 10, 24, VALUE, "0000000")   # widest -> sized once
right_panel.label(terminalio.FONT, RX + 10, 48, LABEL, "LINES")
lines_lbl = right_panel.label(terminalio.FONT, RX + 10, 62, VALUE, "0000")
right_panel.label(terminalio.FONT, RX + 10, 86, LABEL, "LEVEL")
level_lbl = right_panel.label(terminalio.FONT, RX + 10, 100, VALUE, "00")
right_panel.label(terminalio.FONT, RX + 10, 126, LABEL, "NEXT")
next_spr = right_panel.add(pg.Sprite(NEXT_BMP["T"], RX + (SIDE - NTILE * NGRID) // 2, 142))

# --- game state ---
grid = [[0] * COLS for _ in range(ROWS)]               # locked blocks (0 empty, 1..7 colour)
cur = {"name": "T", "rot": 0, "x": 3, "y": -1}
nxt = bag.next()
score = lines = level = 0
changed = True
flash = None                                            # [full_rows, frames_left] while a clear flashes
INTERVALS = (24, 20, 16, 13, 10, 8, 6, 5, 4, 3)        # gravity frames per cell, by level


def cells(name, rot, ox, oy):
    rots = SHAPES[name][1]
    return [(ox + cx, oy + cy) for (cx, cy) in rots[rot % len(rots)]]


def valid(cl):
    for (x, y) in cl:
        if x < 0 or x >= COLS or y >= ROWS:
            return False
        if y >= 0 and grid[y][x]:
            return False
    return True


def refresh_hud():
    right_panel.set_text(score_lbl, "%d" % score)      # set_text re-renders only on a real change
    right_panel.set_text(lines_lbl, "%d" % lines)
    right_panel.set_text(level_lbl, "%d" % level)
    right_panel.redraw()


def spawn():
    global nxt, score, lines, level
    cur["name"] = nxt
    cur["rot"] = 0
    cur["x"] = 3
    cur["y"] = -1
    nxt = bag.next()
    next_spr.bitmap = NEXT_BMP[nxt]                     # swap the preview (pre-built, no alloc)
    right_panel.redraw()
    if not valid(cells(cur["name"], 0, 3, -1)):         # board full = game over -> fresh game, score reset
        for r in range(ROWS):
            for c in range(COLS):
                grid[r][c] = 0
        score = lines = level = 0
        refresh_hud()


def lock_piece():
    global flash
    color = SHAPES[cur["name"]][0]
    for (x, y) in cells(cur["name"], cur["rot"], cur["x"], cur["y"]):
        if 0 <= y < ROWS:
            grid[y][x] = color
    for ry in range(ROWS):                              # commit the locked grid (drops ghost/piece overlay)
        row = grid[ry]
        for rx in range(COLS):
            well.tile(rx, ry, row[rx])
    sfx("lock")
    full = [r for r in range(ROWS) if all(grid[r])]
    if full:
        flash = [full, 12]                              # blink the full rows (handled in the loop), then clear
        sfx("clear")
    else:
        spawn()


def resolve_flash():
    global flash, score, lines, level
    full = flash[0]
    for r in full:
        del grid[r]
        grid.insert(0, [0] * COLS)
    lines += len(full)
    score += (0, 40, 100, 300, 1200)[len(full)] * (level + 1)
    level = lines // 10
    flash = None
    refresh_hud()
    spawn()


def render_board():
    name, rot, cx, cy = cur["name"], cur["rot"], cur["x"], cur["y"]
    pcells = set(cells(name, rot, cx, cy))
    gy = cy                                             # ghost = drop the piece straight down
    while valid(cells(name, rot, cx, gy + 1)):
        gy += 1
    gcells = set(cells(name, rot, cx, gy))
    color = SHAPES[name][0]
    for y in range(ROWS):
        row = grid[y]
        for x in range(COLS):
            if (x, y) in pcells:
                v = color
            elif row[x] == 0 and (x, y) in gcells:
                v = 9                                   # ghost outline on empty cells only
            else:
                v = row[x]
            well.tile(x, y, v)


spawn()
refresh_hud()
grav = 0
print("L/R move | A rotate | Down soft-drop")
while True:
    btn.poll()
    if flash:                                           # line-clear: blink the full rows, then clear them
        flash[1] -= 1
        white = (flash[1] // 3) % 2 == 1
        for r in flash[0]:
            for c in range(COLS):
                well.tile(c, r, 8 if white else grid[r][c])
        if flash[1] <= 0:
            resolve_flash()
            changed = True
    else:
        if btn.just_pressed(btn.LEFT) and valid(cells(cur["name"], cur["rot"], cur["x"] - 1, cur["y"])):
            cur["x"] -= 1
            changed = True
            sfx("move")
        if btn.just_pressed(btn.RIGHT) and valid(cells(cur["name"], cur["rot"], cur["x"] + 1, cur["y"])):
            cur["x"] += 1
            changed = True
            sfx("move")
        if btn.just_pressed(btn.A):
            nr = (cur["rot"] + 1) % len(SHAPES[cur["name"]][1])
            if valid(cells(cur["name"], nr, cur["x"], cur["y"])):
                cur["rot"] = nr
                changed = True
                sfx("rot")
        grav += 1
        interval = 1 if btn.is_pressed(btn.DOWN) else INTERVALS[min(level, len(INTERVALS) - 1)]
        if grav >= interval:
            grav = 0
            if valid(cells(cur["name"], cur["rot"], cur["x"], cur["y"] + 1)):
                cur["y"] += 1
            else:
                lock_piece()
            changed = True
    if changed and not flash:
        render_board()
        changed = False
    scene.refresh()
    clock.tick()
