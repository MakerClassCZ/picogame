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
# HudBar labels are buffer-less StripDraw: they just hold a string (no per-label glyph buffer to size),
# so there's nothing to init to a widest line - show_info() sets the real text before the first draw.
info_lbl = info.label(FONT, 4, 3, INK)
gc.collect()

# --- audio: synthio SFX. With the heap-fragmenting glyph prewarm gone there's ~38 KB free here, so the
# Mixer/Synthesizer fits and actually plays. Guarded: if a build is ever still too tight it falls back to
# silent (MemoryError, not ImportError) instead of crashing. ---
try:
    import picogame_synth as snd
    _synth = snd.Synth(sfx_level=0.8)
    SFX_STEP = snd.note(48, snd.SQUARE, attack=0, decay=0.03, amplitude=0.12)   # train chug
    SFX_COIN = snd.note(72, snd.TRIANGLE, decay=0.10, bend=snd.pitch_bend(7, 80))  # collect
    SFX_CRASH = snd.note(40, snd.NOISE, attack=0, decay=0.35, amplitude=0.6, cutoff=2500)
    SUCCESS = (snd.note(72, snd.SQUARE, decay=0.12),                            # win arpeggio
               snd.note(76, snd.SQUARE, decay=0.12),
               snd.note(79, snd.SQUARE, decay=0.22))

    def sfx(n):
        if n is not None:
            _synth.sfx(n)
except Exception:
    SFX_STEP = SFX_COIN = SFX_CRASH = None
    SUCCESS = (None, None, None)

    def sfx(n):
        pass

gc.collect()

# Game state
class State:
    def __init__(self):
        self.gstate = PLAYING
        self.level = 1
        self.state = WAIT
        self.cur_dir = DIR_R
        self.dir_queue = []                          # up to 2 buffered turns
        self.head_x = self.head_y = self.gate_x = self.gate_y = 0
        self.length = 1
        self.items = 0
        self.score = 0
        self.phase = 0                               # animation phase 0..2
        self.anim_acc = 0.0
        self.crash_t = 0.0
        self.finish_t = 0.0
        self.finish_i = 0
        self.pw_slots = bytearray(5)                 # 5 letter indices 0..25 (A..Z)
        self.pw_pos = 0


st = State()


def show_info():
    # current level code shown for the player to note; "A:CODE" hints that A opens the code editor
    info_lbl.set("LEVEL %02d/%d   SCORE %04d   %s   A:CODE" % (st.level, L.LEVNUM, st.score, L.PASSWORDS[st.level]))
    info.draw()


def init_level(lev):
    base = lev * MAPW * MAPH
    st.items = 0
    for i in range(MAPW * MAPH):
        Dir[i] = 0
    for y in range(MAPH):
        for x in range(MAPW):
            t = L.LEVELS[base + x + y * MAPW]
            tm.tile(x, y, t)
            if LOCOMIN <= t <= LOCOMAX:
                st.head_x, st.head_y = x, y
            elif t == GATE:
                st.gate_x, st.gate_y = x, y
            elif ITEMMIN <= t <= ITEMMAX:
                st.items += 1
    st.state = WAIT
    st.length = 1                                    # reset the train (fixes wagons surviving a crash)
    st.cur_dir = DIR_R
    st.phase = 0
    st.dir_queue.clear()
    show_info()


def step():
    tile = tm.tile                                  # cache method + trail/width as locals (hot path)
    _D = Dir
    _mw = MAPW
    x, y, d = st.head_x, st.head_y, st.cur_dir
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
        tile(st.head_x, st.head_y, CRASH)
        sfx(SFX_CRASH)
        st.state = CRASH_ST
        st.crash_t = CRASH_DUR
        return

    # advance the locomotive, record the trail direction
    xold, yold = st.head_x, st.head_y
    tile(x, y, LOCO[d])
    _D[x + y * _mw] = d
    st.head_x, st.head_y = x, y

    # shift the wagons forward along the trail
    for _ in range(st.length - 1):
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
        st.length += 1
        w = b + WAGONMIN
        while w >= WAGONMIN + 20:
            w -= 20
        tile(xold, yold, w + WOFF[_D[xold + yold * _mw]])
        st.items -= 1
        if st.items == 0:
            tile(st.gate_x, st.gate_y, GATEMIN + 1)  # all collected -> open the gate
        st.score += 10
        show_info()
        sfx(SFX_COIN)
    else:
        tile(xold, yold, EMPTY)                     # nothing collected -> vacate the tail end
        sfx(SFX_STEP)                               # train chug each move

    if st.head_x == st.gate_x and st.head_y == st.gate_y:   # reached the (open) gate
        st.state = FINISH
        st.finish_t = 0.0
        st.finish_i = 0


def anim_level():
    # Cycle the animation of every item, the locomotive and the opening gate; the train
    # itself only STEPS once every PHASES ticks (~2/s) - that slower rate is the original's.
    tile = tm.tile                                  # cache the method (240 cells x2 calls per tick)
    for y in range(MAPH):
        for x in range(MAPW):
            b = tile(x, y)
            if ITEMMIN <= b <= ITEMMAX:             # items: 3-frame loop (tile rows 0-2)
                while b >= ITEMMIN + 20:
                    b -= 20
                tile(x, y, b + st.phase * 20)
            elif LOCOMIN <= b <= LOCOMAX:           # locomotive: 3 frames per direction
                while b >= LOCOMIN + 4:
                    b -= 4
                tile(x, y, b + st.phase * 4)
            elif GATEMIN < b < GATEMAX:             # gate swinging open
                tile(x, y, b + 1)
    st.phase += 1
    if st.phase >= PHASES:                          # every 3rd tick: take one train step
        st.phase = 0
        if st.dir_queue:
            if st.state == WAIT:
                st.state = GO
            st.cur_dir = st.dir_queue.pop(0)
        if st.state == GO:
            step()


# --- screens ---------------------------------------------------------------
def start_level(lev, fresh=True):
    st.level = lev
    if fresh:
        st.score = 0
    init_level(lev)                                  # advances straight in - no title / transition screen
    st.gstate = PLAYING


def pw_code():
    return "".join(chr(65 + s) for s in st.pw_slots)


def pw_render():
    # the editable code lives in the HUD bar (the PicoLibSDK info row); [.] marks the active letter
    parts = [("[%s]" if i == st.pw_pos else " %s ") % chr(65 + st.pw_slots[i]) for i in range(5)]
    info_lbl.set("CODE " + "".join(parts) + " A:OK B:ESC")
    info.draw()


def go_pwentry():                                    # A during play -> edit a level code in the HUD bar
    st.gstate = PWENTRY
    for i in range(5):
        st.pw_slots[i] = 0
    st.pw_pos = 0
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

    if st.gstate == PWENTRY:                         # editing a level code in the HUD; the board is frozen
        if btn.just_pressed(btn.B):
            st.gstate = PLAYING                      # cancel -> resume the current level
            show_info()
        elif btn.just_pressed(btn.A):
            pw_confirm()
        else:
            moved = True
            if btn.just_pressed(btn.UP):
                st.pw_slots[st.pw_pos] = (st.pw_slots[st.pw_pos] + 1) % 26
            elif btn.just_pressed(btn.DOWN):
                st.pw_slots[st.pw_pos] = (st.pw_slots[st.pw_pos] - 1) % 26
            elif btn.just_pressed(btn.LEFT):
                st.pw_pos = (st.pw_pos - 1) % 5
            elif btn.just_pressed(btn.RIGHT):
                st.pw_pos = (st.pw_pos + 1) % 5
            else:
                moved = False
            if moved:
                pw_render()

    elif st.gstate == PLAYING:
        if btn.just_pressed(btn.A):                  # A -> level-code editor (PicoLibSDK "KEY-A:PSW")
            go_pwentry()
        else:
            # queue up to 2 turns so quick taps aren't lost (lets you pre-steer a corner)
            for mask, d in TURNS:
                if btn.just_pressed(mask) and len(st.dir_queue) < 2 and (not st.dir_queue or st.dir_queue[-1] != d):
                    st.dir_queue.append(d)
            if st.state == CRASH_ST:
                st.crash_t -= dt
                # step the explosion 160..169 across the crash duration
                f = CRASH + int((CRASH_DUR - st.crash_t) / CRASH_DUR * (CRASHMAX - CRASH + 1))
                tm.tile(st.head_x, st.head_y, f if f < CRASHMAX else CRASHMAX)
                if st.crash_t <= 0:
                    init_level(st.level)            # restart the scene
            elif st.state == FINISH:
                st.finish_t += dt                   # play the win arpeggio, then advance straight in
                while st.finish_i < 3 and st.finish_t >= st.finish_i * 0.12:
                    sfx(SUCCESS[st.finish_i])
                    st.finish_i += 1
                if st.finish_t >= 0.7:
                    if st.level < L.LEVNUM:
                        start_level(st.level + 1, fresh=False)
                    else:
                        start_level(1)              # all levels done -> loop back to level 1
            else:                                   # WAIT/GO: tick the animation (steps inside)
                st.anim_acc += dt
                if st.anim_acc >= ANIM_DT:
                    st.anim_acc = 0.0
                    anim_level()

    scene.refresh()
