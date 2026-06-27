# Train - a logic "snake puzzle" ported from PicoLibSDK (Miroslav Nemecek), 320x240 PicoPad.
#
# The locomotive auto-moves; steer with the arrows. It leaves a trail (Dir map) that the
# wagons follow like a snake's tail. Drive over every item to collect it (the train grows);
# once the board is clear the gate opens - reach it to finish. Crashing into a wall, the
# closed gate or your own train restarts the level.
#
# 50 levels, each with a 5-letter code. Boots straight into level 1 (no title screen, to fit RAM);
# press A in-game to type a level code (edited in the HUD bar) and jump there - that replaces a
# continue/save. The board is ONE Tilemap; the info bar is a reserved top strip carrying all text.
# Needs train_tiles + train_levels. 320-wide board -> PicoPad (won't fit 240).

import gc
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input    # keypad/polling backend is chosen automatically per board
import picogame_clock
import picogame_ui as ui
import train_tiles
import train_levels as L

W, H = board.DISPLAY.width, board.DISPLAY.height
BARH = 16                                          # reserved info strip (top)
MAPW, MAPH = L.MAPW, L.MAPH                         # 20 x 12
ANIM_DT = 0.16                                      # animation tick (~6/s); the train steps every
PHASES = 3                                          # 3rd phase -> ~2 steps/s (the original's feel)
FONT = terminalio.FONT

# Tile indices (match train_tiles frames / the original ITEMS(y,x) = x + y*20).
DIR_R, DIR_U, DIR_L, DIR_D = 0, 1, 2, 3
ITEMMIN, ITEMMAX = 0, 59
WAGONMIN = 60
LOCO = (142, 141, 140, 143)                         # by direction R,U,L,D
LOCOMIN, LOCOMAX = 140, 151
WOFF = (40, 20, 0, 60)                              # wagon row offset by direction R,U,L,D
GATE = GATEMIN = 152
GATEMAX = 157
WALL = 158
EMPTY = 159
CRASH = 160
CRASHMAX = 169                                      # crash explosion animates 160..169
CRASH_DUR = 0.7                                     # seconds the wreck/explosion shows

# play sub-states (inside PLAYING) + top-level game states
WAIT, GO, CRASH_ST, FINISH = 0, 1, 2, 3
PWENTRY, PLAYING = 11, 12                         # top-level states (no title / transition screens)

BG = pg.rgb565(20, 24, 40)
INK = pg.rgb565(235, 240, 255)
PANEL = pg.rgb565(28, 34, 60)
FRAME = pg.rgb565(90, 120, 200)
scene, bufA, bufB = picogame_game.setup(background=BG, strip_h=BARH, top=BARH)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
TURNS = ((btn.LEFT, DIR_L), (btn.RIGHT, DIR_R), (btn.UP, DIR_U), (btn.DOWN, DIR_D))  # hoisted: no per-frame alloc

tiles_bmp = train_tiles.tileset(pg)                 # shared by the board AND the intro train sprites
tm = pg.Tilemap(tiles_bmp, MAPW, MAPH)
tm.move(0, BARH)                                    # board sits below the info bar
scene.add(tm)
Dir = bytearray(MAPW * MAPH)                        # train trail (not drawn)

# Single HUD bar (top). Like the PicoLibSDK original's bottom info row, it carries EVERYTHING text:
# score/level during play, and the editable code field when A activates code entry. It renders via
# pg.render into bufA (no persistent text buffer to speak of) - so there is NO 31 KB overlay Canvas
# and no 4 prewarmed SceneLabels eating the heap; that headroom is what lets the synth audio fit.
info = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BARH, BG)
# Init with the WIDEST line to size the reused text buffer once. (We do NOT prewarm the whole A-Z
# charset here: rasterizing 42 glyphs up front created ~380 tiny scattered objects that FRAGMENTED the
# heap so a later 1 KB alloc failed even with 26 KB free. With audio off there's ~38 KB headroom, so the
# few extra code glyphs cache on demand into a clean heap instead.)
info_lbl = info.label(FONT, 4, 3, INK, "LEVEL 00/00   SCORE 0000   XXXXX   A:CODE")
gc.collect()

# --- audio: synthio SFX. With the heap-fragmenting glyph prewarm gone there's ~38 KB free here, so the
# Mixer/Synthesizer fits and actually plays. Guarded: if a build is ever still too tight it falls back to
# silent (MemoryError, not ImportError) instead of crashing. ---
try:
    import picogame_synth as snd
    _audio = snd.Synth(sfx_level=0.8)
    SFX_STEP = snd.note(48, snd.SQUARE, attack=0, decay=0.03, amplitude=0.12)   # train chug
    SFX_COIN = snd.note(72, snd.TRIANGLE, decay=0.10, bend=snd.pitch_bend(7, 80))  # collect
    SFX_CRASH = snd.note(40, snd.NOISE, attack=0, decay=0.35, amplitude=0.6, cutoff=2500)
    SUCCESS = (snd.note(72, snd.SQUARE, decay=0.12),                            # win arpeggio
               snd.note(76, snd.SQUARE, decay=0.12),
               snd.note(79, snd.SQUARE, decay=0.22))

    def sfx(n):
        if n is not None:
            _audio.sfx(n)
except Exception:
    SFX_STEP = SFX_COIN = SFX_CRASH = None
    SUCCESS = (None, None, None)

    def sfx(n):
        pass

gc.collect()

# Game state
gstate = PLAYING
level = 1
state = WAIT
cur_dir = DIR_R
dir_queue = []                                       # up to 2 buffered turns
head_x = head_y = gate_x = gate_y = 0
length = 1
items = 0
score = 0
phase = 0                                            # animation phase 0..2
anim_acc = 0.0
crash_t = 0.0
finish_t = 0.0
finish_i = 0
pw_slots = bytearray(5)                              # 5 letter indices 0..25 (A..Z)
pw_pos = 0


def show_info():
    # current level code shown for the player to note; "A:CODE" hints that A opens the code editor
    info_lbl.set("LEVEL %02d/%d   SCORE %04d   %s   A:CODE" % (level, L.LEVNUM, score, L.PASSWORDS[level]))
    info.draw()


def clear_board():                                   # blank board behind a menu/code screen
    for i in range(MAPW * MAPH):
        Dir[i] = 0
    for y in range(MAPH):
        for x in range(MAPW):
            tm.tile(x, y, EMPTY)


def init_level(lev):
    global head_x, head_y, gate_x, gate_y, length, items, state, cur_dir, phase
    base = lev * MAPW * MAPH
    items = 0
    for i in range(MAPW * MAPH):
        Dir[i] = 0
    for y in range(MAPH):
        for x in range(MAPW):
            t = L.LEVELS[base + x + y * MAPW]
            tm.tile(x, y, t)
            if LOCOMIN <= t <= LOCOMAX:
                head_x, head_y = x, y
            elif t == GATE:
                gate_x, gate_y = x, y
            elif ITEMMIN <= t <= ITEMMAX:
                items += 1
    state = WAIT
    length = 1                                       # reset the train (fixes wagons surviving a crash)
    cur_dir = DIR_R
    phase = 0
    dir_queue.clear()
    show_info()


def step():
    global head_x, head_y, length, items, state, score, cur_dir, crash_t, finish_t, finish_i
    tile = tm.tile                                  # cache method + trail/width as locals (hot path)
    _D = Dir
    _mw = MAPW
    x, y, d = head_x, head_y, cur_dir
    if d == DIR_L:
        x -= 1
    elif d == DIR_U:
        y -= 1
    elif d == DIR_R:
        x += 1
    else:
        y += 1

    # crash: off the board, or into anything that isn't empty / an open gate / an item
    if x < 0 or x >= _mw or y < 0 or y >= MAPH:
        b = WALL
    else:
        b = tile(x, y)
    if not (b == EMPTY or (GATEMIN < b <= GATEMAX) or (ITEMMIN <= b <= ITEMMAX)):
        tile(head_x, head_y, CRASH)
        sfx(SFX_CRASH)
        state = CRASH_ST
        crash_t = CRASH_DUR
        return

    # advance the locomotive, record the trail direction
    xold, yold = head_x, head_y
    tile(x, y, LOCO[d])
    _D[x + y * _mw] = d
    head_x, head_y = x, y

    # shift the wagons forward along the trail
    for _ in range(length - 1):
        wx, wy = xold, yold
        dd = _D[wx + wy * _mw]
        if dd == DIR_L:
            wx += 1
        elif dd == DIR_U:
            wy += 1
        elif dd == DIR_R:
            wx -= 1
        else:
            wy -= 1
        w = tile(wx, wy)
        while w >= WAGONMIN + 20:
            w -= 20
        tile(xold, yold, w + WOFF[dd])
        xold, yold = wx, wy

    if ITEMMIN <= b <= ITEMMAX:                     # collected an item -> grow + new wagon
        length += 1
        w = b + WAGONMIN
        while w >= WAGONMIN + 20:
            w -= 20
        tile(xold, yold, w + WOFF[_D[xold + yold * _mw]])
        items -= 1
        if items == 0:
            tile(gate_x, gate_y, GATEMIN + 1)       # all collected -> open the gate
        score += 10
        show_info()
        sfx(SFX_COIN)
    else:
        tile(xold, yold, EMPTY)                     # nothing collected -> vacate the tail end
        sfx(SFX_STEP)                               # train chug each move

    if head_x == gate_x and head_y == gate_y:       # reached the (open) gate
        state = FINISH
        finish_t = 0.0
        finish_i = 0


def anim_level():
    # Cycle the animation of every item, the locomotive and the opening gate; the train
    # itself only STEPS once every PHASES ticks (~2/s) - that slower rate is the original's.
    global phase, state, cur_dir
    tile = tm.tile                                  # cache the method (240 cells x2 calls per tick)
    for y in range(MAPH):
        for x in range(MAPW):
            b = tile(x, y)
            if ITEMMIN <= b <= ITEMMAX:             # items: 3-frame loop (tile rows 0-2)
                while b >= ITEMMIN + 20:
                    b -= 20
                tile(x, y, b + phase * 20)
            elif LOCOMIN <= b <= LOCOMAX:           # locomotive: 3 frames per direction
                while b >= LOCOMIN + 4:
                    b -= 4
                tile(x, y, b + phase * 4)
            elif GATEMIN < b < GATEMAX:             # gate swinging open
                tile(x, y, b + 1)
    phase += 1
    if phase >= PHASES:                             # every 3rd tick: take one train step
        phase = 0
        if dir_queue:
            if state == WAIT:
                state = GO
            cur_dir = dir_queue.pop(0)
        if state == GO:
            step()


# --- screens ---------------------------------------------------------------
def start_level(lev, fresh=True):
    global level, score, gstate
    level = lev
    if fresh:
        score = 0
    init_level(lev)                                  # advances straight in - no title / transition screen
    gstate = PLAYING


def pw_code():
    return "".join(chr(65 + s) for s in pw_slots)


def pw_render():
    # the editable code lives in the HUD bar (the PicoLibSDK info row); [.] marks the active letter
    parts = [("[%s]" if i == pw_pos else " %s ") % chr(65 + pw_slots[i]) for i in range(5)]
    info_lbl.set("CODE " + "".join(parts) + " A:OK B:ESC")
    info.draw()


def go_pwentry():                                    # A during play -> edit a level code in the HUD bar
    global gstate, pw_pos
    gstate = PWENTRY
    for i in range(5):
        pw_slots[i] = 0
    pw_pos = 0
    pw_render()


def pw_confirm():
    word = pw_code()
    for lev in range(1, L.LEVNUM + 1):
        if L.PASSWORDS[lev] == word:
            start_level(lev, fresh=True)
            return
    info_lbl.set("WRONG CODE      B:ESC")  # invalid -> stay; an arrow resumes editing
    info.draw()


# --- main loop -------------------------------------------------------------
start_level(1)                                       # start straight on level 1 (no title screen)
gc.collect()
print("Train - arrows steer, reach the gate; A = enter a level code to jump.")
while True:
    dt = clock.tick()
    btn.poll()

    if gstate == PWENTRY:                            # editing a level code in the HUD; the board is frozen
        if btn.just_pressed(btn.B):
            gstate = PLAYING                         # cancel -> resume the current level
            show_info()
        elif btn.just_pressed(btn.A):
            pw_confirm()
        else:
            moved = True
            if btn.just_pressed(btn.UP):
                pw_slots[pw_pos] = (pw_slots[pw_pos] + 1) % 26
            elif btn.just_pressed(btn.DOWN):
                pw_slots[pw_pos] = (pw_slots[pw_pos] - 1) % 26
            elif btn.just_pressed(btn.LEFT):
                pw_pos = (pw_pos - 1) % 5
            elif btn.just_pressed(btn.RIGHT):
                pw_pos = (pw_pos + 1) % 5
            else:
                moved = False
            if moved:
                pw_render()

    elif gstate == PLAYING:
        if btn.just_pressed(btn.A):                  # A -> level-code editor (PicoLibSDK "KEY-A:PSW")
            go_pwentry()
        else:
            # queue up to 2 turns so quick taps aren't lost (lets you pre-steer a corner)
            for mask, d in TURNS:
                if btn.just_pressed(mask) and len(dir_queue) < 2 and (not dir_queue or dir_queue[-1] != d):
                    dir_queue.append(d)
            if state == CRASH_ST:
                crash_t -= dt
                # step the explosion 160..169 across the crash duration
                f = CRASH + int((CRASH_DUR - crash_t) / CRASH_DUR * (CRASHMAX - CRASH + 1))
                tm.tile(head_x, head_y, f if f < CRASHMAX else CRASHMAX)
                if crash_t <= 0:
                    init_level(level)               # restart the scene
            elif state == FINISH:
                finish_t += dt                      # play the win arpeggio, then advance straight in
                while finish_i < 3 and finish_t >= finish_i * 0.12:
                    sfx(SUCCESS[finish_i])
                    finish_i += 1
                if finish_t >= 0.7:
                    if level < L.LEVNUM:
                        start_level(level + 1, fresh=False)
                    else:
                        start_level(1)              # all levels done -> loop back to level 1
            else:                                   # WAIT/GO: tick the animation (steps inside)
                anim_acc += dt
                if anim_acc >= ANIM_DT:
                    anim_acc = 0.0
                    anim_level()

    scene.refresh()
