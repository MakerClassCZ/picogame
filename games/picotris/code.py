# Picotris on picogame - a Tilemap + PLAY-AREA showcase. The well is a Tilemap in a RESERVED centre
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

# --- audio: WARM synthio SFX (picogame_synth), built ONCE at import (~0 sample RAM). Warmth =
# a rounded odd-harmonic wavetable (a softened square, kin to the old tone() voice) + a Biquad
# LOW_PASS per note + percussive envelopes; the line-clear is a small rising arpeggio scheduled
# through _seq (drained one note per few frames in the loop). Guarded: no synthio (the sim) =
# silent no-ops.
_frame = 0
_seq = []                                  # pending arpeggio notes [play_frame, note]
try:
    import math
    import synthio                         # noqa: F401  (device-only; ImportError in the sim)
    import picogame_synth as snd

    _synth = snd.Synth(sfx_level=0.7)

    def _wave(harmonics):                  # summed harmonics with rolloff = a baked low-pass
        acc = [0.0] * 256
        for h, a in harmonics:
            w = 2 * math.pi * h / 256
            for i in range(256):
                acc[i] += a * math.sin(w * i)
        m = max(abs(v) for v in acc) or 1.0
        return array.array("h", [int(28000 * v / m) for v in acc])

    _SOFT = _wave([(n, (1.0 / n) / (1 + (n / 7.0) ** 2)) for n in range(1, 13, 2)])  # rounded square

    def _n(m, dec=0.04, amp=0.5, cut=1600, rel=0.08, bend=None):
        return snd.note(m, _SOFT, attack=0.005, decay=dec, release=rel, amplitude=amp,
                        cutoff=cut, bend=snd.pitch_bend(bend[0], bend[1]) if bend else None)

    SND_MOVE = _n(69, 0.025, 0.30, 1500)                        # soft tick (was tone(220, 35))
    SND_ROT = _n(73, 0.03, 0.35, 1800, bend=(2, 30))            # brighter tick + tiny up-chirp (was 330 Hz)
    SND_LOCK = _n(41, 0.08, 0.65, 800, rel=0.2, bend=(-2, 70))  # firm low thunk (was tone(170, 60))
    SEQ_CLEAR = (_n(72, 0.04, 0.5, 2200), _n(76, 0.04, 0.5, 2200),      # rising clear arpeggio
                 _n(79, 0.05, 0.55, 2400), _n(84, 0.12, 0.6, 2400, rel=0.2))  # (was tone(880, 130))

    def sfx(n):
        if n is not None:
            _synth.sfx(n)                  # monophonic one-shot; retriggers its bend LFO

    def sfx_seq(notes):
        for i, nn in enumerate(notes):
            _seq.append([_frame + i * 2, nn])
except Exception:
    SND_MOVE = SND_ROT = SND_LOCK = None
    SEQ_CLEAR = ()

    def sfx(n):
        pass

    def sfx_seq(notes):
        pass


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
       (20, 20, 30), (78, 86, 120), (245, 248, 255)]   # palette idx 8=edge, 9=ghost, 10=white
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

# next-piece preview: 4 mini cells that SHARE the main `tileset` (0 extra bitmaps). Each cell is a
# HudBar icon sprite showing the piece's colour via its .frame; set_next() positions the 4 visible
# cells (one per block of the shape's spawn rotation) and hides any unused slots.
NGRID = 4                                              # a 4x4 box holds any spawn rotation
NPX = TILE                                             # mini cell = one tileset frame (12px)
next_cells = [pg.Sprite(tileset, 0, 0, visible=False) for _ in range(4)]

# --- side panels: static chrome the scene never repaints (one redraw; updated only on change) ---
left_panel = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, SIDE, H, PANEL)
left_panel.label(terminalio.FONT, 18, 14, VALUE, "PICOTRIS")
left_panel.label(terminalio.FONT, 8, H - 54, LABEL, "< >  move")
left_panel.label(terminalio.FONT, 8, H - 40, LABEL, "A   rotate")
left_panel.label(terminalio.FONT, 8, H - 26, LABEL, "v   drop")
left_panel.draw()

right_panel = ui.HudBar(pg, board.DISPLAY, bufA, RX, 0, SIDE, H, PANEL)
right_panel.label(terminalio.FONT, RX + 10, 10, LABEL, "SCORE")
# HudBar labels are buffer-less (just hold a string); "0" is only a placeholder refresh_hud() overwrites.
score_lbl = right_panel.label(terminalio.FONT, RX + 10, 24, VALUE, "0")
right_panel.label(terminalio.FONT, RX + 10, 48, LABEL, "LINES")
lines_lbl = right_panel.label(terminalio.FONT, RX + 10, 62, VALUE, "0")
right_panel.label(terminalio.FONT, RX + 10, 86, LABEL, "LEVEL")
level_lbl = right_panel.label(terminalio.FONT, RX + 10, 100, VALUE, "0")
right_panel.label(terminalio.FONT, RX + 10, 126, LABEL, "NEXT")
NEXT_OX = RX + (SIDE - NPX * NGRID) // 2                # top-left of the 4x4 preview box
NEXT_OY = 142
for _c in next_cells:
    right_panel.add(_c)                                # blitted into the band at its own x/y + frame


def set_next(name):
    col, rots = SHAPES[name]
    cells0 = rots[0]
    for i in range(4):
        cx, cy = cells0[i]
        s = next_cells[i]
        s.frame = col                                  # solid colour tile from the shared tileset
        s.move(NEXT_OX + cx * NPX, NEXT_OY + cy * NPX)
        s.visible = True

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


def fits(name, rot, ox, oy):
    # Allocation-free collision test: walk the 4 SHAPE offsets inline, no list/tuple built per query.
    rots = SHAPES[name][1]
    for (cx, cy) in rots[rot % len(rots)]:
        x = ox + cx
        y = oy + cy
        if x < 0 or x >= COLS or y >= ROWS:
            return False
        if y >= 0 and grid[y][x]:
            return False
    return True


def refresh_hud():
    score_lbl.set("%d" % score)      # HudBar.draw() below repaints the whole band; .set just stores the string
    lines_lbl.set("%d" % lines)
    level_lbl.set("%d" % level)
    right_panel.draw()


def spawn():
    global nxt, score, lines, level
    cur["name"] = nxt
    cur["rot"] = 0
    cur["x"] = 3
    cur["y"] = -1
    nxt = bag.next()
    set_next(nxt)                                       # reposition the 4 shared-tileset preview cells
    right_panel.draw()
    if not fits(cur["name"], 0, 3, -1):                 # board full = game over -> fresh game, score reset
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
    sfx(SND_LOCK)
    full = [r for r in range(ROWS) if all(grid[r])]
    if full:
        flash = [full, 12]                              # blink the full rows (handled in the loop), then clear
        sfx_seq(SEQ_CLEAR)                              # the reward: a rising arpeggio over the flash
    else:
        spawn()


def resolve_flash():
    global flash, score, lines, level
    full = flash[0]
    for r in full:
        del grid[r]
        grid.insert(0, [0] * COLS)
    lines += len(full)
    # points by lines cleared 0/1/2/3/4 (Tetris) x (level+1)
    score += (0, 40, 100, 300, 1200)[len(full)] * (level + 1)
    level = lines // 10
    flash = None
    refresh_hud()
    spawn()


def render_board():
    name, rot, cx, cy = cur["name"], cur["rot"], cur["x"], cur["y"]
    shape = SHAPES[name][1][rot % len(SHAPES[name][1])]
    # Precompute the 4 piece + 4 ghost cells as int keys (y*COLS+x) ONCE, so the 10x18 sweep tests
    # membership with an int key (no per-cell (x,y) tuple, no 180-360 throwaway allocs per frame).
    pset = set()
    for (dx, dy) in shape:
        pset.add((cy + dy) * COLS + cx + dx)
    gy = cy                                             # ghost = drop the piece straight down
    while fits(name, rot, cx, gy + 1):
        gy += 1
    gset = set()
    for (dx, dy) in shape:
        gset.add((gy + dy) * COLS + cx + dx)
    color = SHAPES[name][0]
    for y in range(ROWS):
        row = grid[y]
        base = y * COLS
        for x in range(COLS):
            k = base + x
            if k in pset:
                v = color
            elif row[x] == 0 and k in gset:
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
    _frame += 1
    _i = 0                                    # drain scheduled arpeggio notes due this frame
    while _i < len(_seq):
        if _seq[_i][0] <= _frame:
            sfx(_seq[_i][1])
            _seq.pop(_i)
        else:
            _i += 1
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
        if btn.just_pressed(btn.LEFT) and fits(cur["name"], cur["rot"], cur["x"] - 1, cur["y"]):
            cur["x"] -= 1
            changed = True
            sfx(SND_MOVE)
        if btn.just_pressed(btn.RIGHT) and fits(cur["name"], cur["rot"], cur["x"] + 1, cur["y"]):
            cur["x"] += 1
            changed = True
            sfx(SND_MOVE)
        if btn.just_pressed(btn.A):
            nr = (cur["rot"] + 1) % len(SHAPES[cur["name"]][1])
            if fits(cur["name"], nr, cur["x"], cur["y"]):
                cur["rot"] = nr
                changed = True
                sfx(SND_ROT)
        grav += 1
        interval = 1 if btn.is_pressed(btn.DOWN) else INTERVALS[min(level, len(INTERVALS) - 1)]
        if grav >= interval:
            grav = 0
            if fits(cur["name"], cur["rot"], cur["x"], cur["y"] + 1):
                cur["y"] += 1
            else:
                lock_piece()
            changed = True
    if changed and not flash:
        render_board()
        changed = False
    scene.refresh()
    clock.tick()
