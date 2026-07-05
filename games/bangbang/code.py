# picogame_bangbang.py - "Bang! Bang!" clone: a turn-based artillery duel (Scorched Earth / Gorillas
# family). Two tanks on destructible terrain take turns; LEFT/RIGHT aim the barrel, UP/DOWN set power,
# A or B fires. Modes: 1 player vs AI, or 2 players hot-seat (na strdacku).
#
# Engine fit (the "are we ready?" answer in code):
#   - retained Scene + dirty-rect: between shots almost nothing moves, so the whole thing is cheap;
#     only the shell sprite repaints per frame while in flight.
#   - Tilemap = destructible terrain: erode cells on impact (tile -> 0) and collide against tile data
#     (the engine-idiomatic replacement for pixel-readback craters -- see digdug/missile).
#   - Particles + Shake for explosion juice; plain-Python physics + a sample-and-score AI.
#
# Run in the simulator:
#   python3 sim/run.py games/picogame_bangbang.py --backend pygame                  # play it
#   python3 sim/run.py games/picogame_bangbang.py --frames 80 --shot /tmp/s.png     # headless shot

import math
import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui

# --- audio: build the SFX samples ONCE at startup, then play them async via the mixer. NEVER call
# tone() per shot - it only *builds* a sample (a Python array alloc), so doing it every shot stalls
# and allocates for nothing (that was the old beep bug). Guarded so the sim (no audio HW) stays silent.
audio = FIRE_SND = BOOM_SND = None
try:
    import picogame_audio
    audio = picogame_audio.Audio()                  # PWM on board.AUDIO (GP15), async 4-voice mixer
    FIRE_SND = picogame_audio.tone(650, 55)         # quick blip on launch
    BOOM_SND = picogame_audio.tone(90, 200)         # low thud on impact
except Exception:
    audio = None


def sfx(sample):
    if audio is not None and sample is not None:
        try:
            audio.sfx(sample)                       # fire-and-forget on a free mixer voice (non-blocking)
        except Exception:
            pass


# --- colours (ALWAYS via rgb565 - never raw 0xRRGGBB) ---
SKY    = pg.rgb565(28, 36, 70)
GROUND = pg.rgb565(122, 86, 54)
GRASS  = pg.rgb565(72, 168, 72)
INK    = pg.rgb565(255, 255, 255)
HUDBG  = pg.rgb565(12, 14, 26)
P1COL  = pg.rgb565(240, 96, 96)
P2COL  = pg.rgb565(96, 156, 240)
FIRE   = pg.rgb565(255, 198, 80)
DOTCOL = pg.rgb565(255, 255, 255)
# power-gauge pips: empty (dim) + a zone ramp (green -> amber -> red). Count of lit pips reads the
# power even without colour (kid-/colourblind-fair); colour is only a secondary cue.
PIP_DIM  = pg.rgb565(46, 52, 72)
PIP_LOW  = pg.rgb565(70, 200, 80)
PIP_MID  = pg.rgb565(240, 190, 40)
PIP_HIGH = pg.rgb565(235, 72, 56)

W, H = board.DISPLAY.width, board.DISPLAY.height
BAR = 16                              # reserved top HUD strip
TILE = 2
COLS = W // TILE                      # 160
ROWS = H // TILE                      # 120

# physics in pixels / seconds; fixed DT keeps it deterministic and matches the AI sim
DT = 1.0 / 30.0
GRAV = 240.0
# Range grows with v0^2, so a linear v0 squeezes the "hits the enemy" band into a sliver. Instead make
# the 45-deg RANGE linear in power (v0 = sqrt(GRAV*range)) -> every +10 power ≈ same extra distance, so
# the whole slider is useful. Tune: enemy (~290 px) is hit around power ~55; 100 sails well past.
RMIN = 40.0                          # 45-deg range floor in px (low power = a real but short lob)
RSPAN = 4.0                          # px of 45-deg range per power unit (gentler = wider usable band)
HITR = 7                             # direct-hit half-extent (px)
BLAST = 17                           # explosion splash radius (px)
CRATER = 14                          # terrain erosion radius (px)
ARM_CLEAR = 18                       # shell ignores collisions within this radius of its shooter (muzzle clearance)
AI_THINK = 18                        # frames the AI "aims" before firing
AI_ANG_LO, AI_ANG_HI, AI_ANG_STEP = 20, 80, 4    # angle candidate sweep (deg): lo..hi by step
AI_PWR_LO, AI_PWR_HI, AI_PWR_STEP = 25, 100, 6   # power candidate sweep: lo..hi by step
AI_ANG_N = len(range(AI_ANG_LO, AI_ANG_HI, AI_ANG_STEP))     # 15 angle steps
AI_PWR_N = len(range(AI_PWR_LO, AI_PWR_HI, AI_PWR_STEP))     # 13 power steps
AI_CANDS_N = AI_ANG_N * AI_PWR_N     # 195 (angle,power) candidates, addressed by index (no stored grid)
AI_STEP = 12                         # candidates evaluated PER frame, spread over AI_THINK -> no compute spike
AI_ANG_ERR = 6                       # AI aim scatter, degrees (bigger = dumber / more beatable)
AI_PWR_ERR = 10                      # AI power scatter

scene, bufA, bufB = picogame_game.setup(background=SKY, top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# --- HUD bar (0-RAM strip in the reserved border) ---
hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, HUDBG)
# whose-turn chip: a red (P1) / blue (P2) dot at the far left - the player colour, kid-readable
chip_bm = [shp.circle(10, P1COL), shp.circle(10, P2COL)]
turn_chip = hud.add(pg.Sprite(chip_bm[0], 4, 3))
# HUD positions are derived from W so the bar fits narrow (240) and wide (320) screens: a left cluster
# (chip - ANG - pips - power#) grows from x=0, and the right cluster (score - WIND) is anchored to W.
hud_l = hud.label(terminalio.FONT, 18, 3, INK, "")        # "ANG nn"
hud_r = hud.label(terminalio.FONT, W - 46, 3, INK, "")    # "WIND +n" (right-anchored)
# power gauge: 10 pips. frame 0 = empty (dim), 1/2/3 = green/amber/red. The COUNT of lit pips reads
# the power for a pre-reader; colour (by pip position) is a secondary cue; the number is for readers.
PIP_N = 10
pip_bm = shp.color_frames(5, 9, [PIP_DIM, PIP_LOW, PIP_MID, PIP_HIGH])
pips = [hud.add(pg.Sprite(pip_bm, 58 + i * 6, 4)) for i in range(PIP_N)]
hud_p = hud.label(terminalio.FONT, 122, 3, INK, "")       # power number, beside the gauge
hud_s = hud.label(terminalio.FONT, W - 70, 3, INK, "")    # running match score P1:P2 (left of WIND)

# --- terrain: a Tilemap whose cells we erode (0 = air, 1 = ground, 2 = grass cap) ---
tileset = shp.tileset_colors(TILE, TILE, [GROUND, GRASS])
tm = pg.Tilemap(tileset, COLS, ROWS)
scene.add(tm)
surf = [ROWS - 6] * COLS              # tile-row of the surface, per column

# --- tanks (created once; re-seated each round) ---
# hull = a little tank silhouette (per-player colour); barrel = a real cannon that points at the
# aim angle, drawn from PRE-BAKED rotation frames (poly_frames - the engine's "turret" pattern:
# crisp, zero runtime-rotation cost, just step .frame).
HULL = [
    "....#####....",
    "...#######...",
    "..#########..",
    ".###########.",
    "#############",
    "#############",
    "#.#.#.#.#.#.#",
]
GUNMETAL = pg.rgb565(205, 208, 218)
BARREL_N = 48                         # baked rotation steps (7.5 deg each)
BARREL_L = 9                          # barrel length (px)
_bar_pts = [(0, -1.3), (BARREL_L, -1.3), (BARREL_L, 1.3), (0, 1.3)]   # bar from centre -> +x
_bar_sz = BARREL_L * 2 + 4
hull_bm = [shp.from_mask(HULL, P1COL), shp.from_mask(HULL, P2COL)]
barrel_bm = shp.poly_frames(_bar_sz, _bar_pts, BARREL_N, GUNMETAL)   # shared rotation atlas

tanks = []
for _i, (_col, _dir, _hb) in enumerate(((6, 1, hull_bm[0]), (COLS - 7, -1, hull_bm[1]))):
    _x = _col * TILE + TILE // 2
    _s = pg.Sprite(_hb, _x, 0)
    _s.anchor = (0.5, 1.0)            # bottom-centre sits on the surface line
    scene.add(_s)
    _b = pg.Sprite(barrel_bm, _x, 0)
    _b.anchor = (0.5, 0.5)           # pivot at the bar's base == turret centre
    scene.add(_b)                    # added after the hull -> draws on top
    tanks.append({"x": _x, "home": _x, "dir": _dir, "spr": _s, "barrel": _b,
                  "angle": 45, "power": 50, "alive": True})

# --- aim indicator (a little dotted barrel line) ---
dot_bm = shp.circle(2, DOTCOL)
dots = []
for _ in range(5):
    d = pg.Sprite(dot_bm, -9, -9)
    d.anchor = (0.5, 0.5)
    d.visible = False
    scene.add(d)
    dots.append(d)

# --- the shell + explosion particles ---
proj = pg.Sprite(shp.circle(4, FIRE), -9, -9)
proj.anchor = (0.5, 0.5)
proj.visible = False
scene.add(proj)

parts = pg.Particles(48, size=2, gravity=0.25, fade=True)
scene.add(parts)
# NB: no camera-shake on impact - set_view() forces a FULL-screen repaint, and on the fine 2px
# Tilemap (160x120) doing that for ~16 frames stutters on RP2040. The explosion punch comes from
# the particle bursts (dirty-rect local = cheap) + the destroyed-tank flash instead.

# --- windsock: a wind indicator planted on a peak. 5 baked frames (droop=calm .. horizontal=max);
# frame reads STRENGTH, flip reads DIRECTION - an airport-sock affordance kids get at a glance, no text.
# The POLE is the centre column (col 3) so anchored bottom-centre it plants on the peak centre, and a
# flip keeps it centred. Static per round -> repaints ~once per round (near-free). ---
_SOCK = [
    ["...#....", "...##...", "...##...", "...##...", "...##...", "...#....", "...#....", "...#....", "...#....", "...#...."],
    ["...#....", "...##...", "...###..", "...##...", "...#.#..", "...#....", "...#....", "...#....", "...#....", "...#...."],
    ["...#....", "...###..", "...####.", "...##...", "...#....", "...#....", "...#....", "...#....", "...#....", "...#...."],
    ["...####.", "...####.", "...##...", "...#....", "...#....", "...#....", "...#....", "...#....", "...#....", "...#...."],
    ["...#####", "...#####", "...####.", "...#....", "...#....", "...#....", "...#....", "...#....", "...#....", "...#...."],
]


def _mbuf(rows):
    b = bytearray(8 * 10)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                b[y * 8 + x] = 1
    return b


WINDCOL = pg.rgb565(210, 60, 0)
sock_bm = shp.atlas([_mbuf(f) for f in _SOCK], 8, 10, WINDCOL)
del HULL, _SOCK, _bar_pts, _mbuf   # bake-time scaffolding only; final bitmaps own their own buffers
flag = pg.Sprite(sock_bm, W // 2, 0)  # x chosen each round: a peak near mid-field (set by pick_flag_spot)
flag.anchor = (0.5, 1.0)             # bottom-centre -> the pole base sits on the surface
flag.scale = 2                       # bigger so it reads from across the field (integer scale = crisp)
flag.visible = False
scene.add(flag)

# --- title / game-over text (scene-layer labels over the live scene) ---
t_title = ui.SceneLabel(scene, pg, terminalio.FONT, W // 2 - 40, H // 2 - 34, INK, SKY)
t_a     = ui.SceneLabel(scene, pg, terminalio.FONT, W // 2 - 66, H // 2 - 8, INK, SKY)
t_b     = ui.SceneLabel(scene, pg, terminalio.FONT, W // 2 - 66, H // 2 + 8, INK, SKY)
t_over  = ui.SceneLabel(scene, pg, terminalio.FONT, W // 2 - 70, H // 2 - 20, INK, SKY)
# t_over only gets its ~31-char banner at game-over (an aged heap); reserve its buffer NOW on the fresh
# startup heap so that later growth can't MemoryError. t_title/t_a/t_b get their long strings at startup.
t_over.reserve(31)

# --- mutable game state ---
class State:
    def __init__(self):
        self.state = "title"       # title | aim | fire | over
        self.mode = "ai"           # ai | 2p | demo (both sides AI = attract mode)
        self.cur = 0               # whose turn (tank index)
        self.wind = 0.0            # px/s^2, + = blows right
        self.winner = -1
        self.think = 0             # AI aim countdown
        self.hold = 0              # frames the player has held an aim key (for step acceleration)
        self.score = [0, 0]        # running match score P1:P2 (reset when a new match starts from the title)
        self.pfx = self.pfy = self.pvx = self.pvy = 0.0
        self.shooter = None        # the tank that fired the shell in flight (for muzzle-clearance arming)
        self.ai_i = 0              # incremental AI search cursor / best-so-far (spread over the aim frames)
        self.ai_best = (45, 50)
        self.ai_bd = 1e18
        self.hud_ang = None        # last aim (angle,power) drawn into the HUD/dots (skip redundant redraws)
        self.hud_pw = None
        self.flag_x = W // 2       # chosen each round: a peak near mid-field (set by pick_flag_spot)


st = State()


def surface_px(x):
    c = max(0, min(COLS - 1, int(x) // TILE))
    return surf[c] * TILE


NUDGE, LANE, WALL_MAX = 9, 4, 7       # shift <=NUDGE cols; LANE = IMMEDIATE cols scanned ahead (~8px);
                                      # WALL_MAX = rows that near wall may rise before we step aside.
                                      # Tuned so only ~1 in 8 starts nudges (a small ~6px shift) - a light
                                      # trim of unplayable spawns that still leaves hiding behind hills.

def front_wall(c, d):
    # rows the near terrain (within LANE toward the enemy) rises above the muzzle. Negative = downhill/open;
    # a small positive is a low hill you can lob over (kept - it's tactical); large = genuinely boxed in.
    ahead = min(surf[c + d * i] for i in range(1, LANE + 1))
    return surf[c] - ahead

def nudge_tanks():
    # Leave the terrain natural AND usually leave the tank home - hiding behind a hill is fun. Only when a
    # tank is genuinely walled in (front_wall >= WALL_MAX) do we step it to the NEAREST column that opens
    # up, a minimal move. This just trims how OFTEN a start is unplayable; it doesn't erase the tactic.
    for t in tanks:
        hc = t["home"] // TILE
        d = t["dir"]
        t["x"] = t["home"]                              # default: stay put
        if front_wall(hc, d) < WALL_MAX:
            continue                                    # open enough (incl. a low hill to arc over)
        for step in range(1, NUDGE + 1):               # boxed in -> nearest opening, small step
            found = None
            for c in (hc - step, hc + step):
                if 3 <= c < COLS - 3 and front_wall(c, d) < WALL_MAX:
                    found = c
                    break
            if found is not None:
                t["x"] = found * TILE + TILE // 2
                break                                   # none within NUDGE -> accept the boxed spot


def build_terrain():
    p1, p2 = random.uniform(0, 6.28), random.uniform(0, 6.28)
    amp = random.uniform(18, 34)
    base = H * 0.60
    for c in range(COLS):
        hpx = base + amp * math.sin(c * 0.09 + p1) + 12.0 * math.sin(c * 0.23 + p2)
        hpx = max(H * 0.40, min(H - TILE * 3, hpx))
        surf[c] = int(hpx) // TILE
    tm.fill(0)
    for c in range(COLS):
        sr = surf[c]
        tm.tile(c, sr, 2)                 # grass cap
        for r in range(sr + 1, ROWS):
            tm.tile(c, r, 1)              # ground below
    nudge_tanks()                         # reposition tanks to fairer nearby columns (terrain untouched)


def recompute_surf(cx):
    lo = max(0, cx // TILE - CRATER // TILE - 2)
    hi = min(COLS, cx // TILE + CRATER // TILE + 3)
    for c in range(lo, hi):
        r = surf[c]                       # erosion only LOWERS the surface -> scan down from the old one
        while r < ROWS and tm.tile(c, r) == 0:
            r += 1
        surf[c] = r if r < ROWS else ROWS - 1


def set_power_gauge(power):
    lit = int(round((power - 5) / 95.0 * PIP_N))            # 0..10 pips; pip1 ~power15, pip10 = power100
    for i, p in enumerate(pips):
        p.visible = True
        if i < lit:
            p.frame = 1 if i < 4 else (2 if i < 7 else 3)   # green / amber / red by position (zone cue)
        else:
            p.frame = 0                                     # empty (dim) - keeps the full scale visible


def hud_play_widgets(on):
    turn_chip.visible = on                                 # chip + pips belong to the play HUD only
    for p in pips:
        p.visible = on


def pick_flag_spot():
    lo, hi = COLS // 4, COLS - COLS // 4           # a peak in the central half of the field
    best = lo
    for c in range(lo, hi):
        if surf[c] < surf[best]:                   # smaller surface row = higher peak
            best = c
    st.flag_x = best * TILE + TILE // 2


def set_wind_flag():
    flag.frame = min(4, abs(int(st.wind)) // 12)   # 0 = calm/drooping .. 4 = horizontal/max
    flag.flip_x = st.wind < 0
    flag.move(st.flag_x, surface_px(st.flag_x))    # re-plant on the (possibly cratered) surface
    flag.visible = True


def update_hud():
    t = tanks[st.cur]
    hud_play_widgets(True)
    turn_chip.bitmap = chip_bm[st.cur]                     # whose turn: red dot = P1, blue = P2/AI
    hud_l.set("ANG %2d" % t["angle"])
    set_power_gauge(t["power"])                            # kid-readable pip bar ...
    hud_p.set("%d" % t["power"])                           # ... plus the number for readers
    hud_s.set("%d:%d" % (st.score[0], st.score[1]))
    hud_r.set("WIND %+d" % int(round(st.wind / 6.0)))
    hud.draw()


def place_barrel(t):
    """Point the cannon along the aim direction (screen-space, y-down) and pin it to the turret."""
    rad = math.radians(t["angle"])
    th = math.atan2(-math.sin(rad), math.cos(rad) * t["dir"])      # baked frame f points at angle f*2pi/N
    t["barrel"].frame = int(round(th / (2 * math.pi) * BARREL_N)) % BARREL_N
    t["barrel"].move(t["x"], t["spr"].y - 6)
    t["barrel"].visible = True


def update_dots(t):
    rad = math.radians(t["angle"])
    bx, by = t["x"], t["spr"].y - 7
    gap = 3 + t["power"] * 0.20            # longer dotted line = more power (complements the pip gauge)
    for i, d in enumerate(dots):
        dist = (i + 1) * gap
        d.move(int(bx + math.cos(rad) * dist * t["dir"]), int(by - math.sin(rad) * dist))
        d.visible = True
    place_barrel(t)


def hide_dots():
    for d in dots:
        d.visible = False


def shot_init(t, angle, power):
    """Initial (x, y, vx, vy) for a shell leaving the MUZZLE TIP, so it starts outside its own hull."""
    rad = math.radians(angle)
    v0 = math.sqrt(GRAV * (RMIN + power * RSPAN))      # range linear in power -> whole slider useful
    dx = math.cos(rad) * t["dir"]
    dy = -math.sin(rad)
    px = t["x"] + dx * (BARREL_L + 3)
    py = (t["spr"].y - 6) + dy * (BARREL_L + 3)
    return px, py, dx * v0, dy * v0


def fire(t):
    st.pfx, st.pfy, st.pvx, st.pvy = shot_init(t, t["angle"], t["power"])
    st.shooter = t
    proj.move(int(st.pfx), int(st.pfy))
    proj.visible = True
    hide_dots()
    sfx(FIRE_SND)
    st.state = "fire"


def sim_shot(t, angle, power):
    """Pure-physics trajectory used by the AI to score a candidate shot. Returns landing (x, y)."""
    x, y, vx, vy = shot_init(t, angle, power)
    enemy = tanks[1 - tanks.index(t)]
    ex = enemy["x"]                     # hoisted: constant across the ~300-step inner loop
    ey = enemy["spr"].y - 4
    hit2 = (HITR * 2) ** 2
    for _ in range(300):
        vy += GRAV * DT
        vx += st.wind * DT
        x += vx * DT
        y += vy * DT
        if y > H + 20 or x < -20 or x > W + 20:
            return (x, y)
        if (x - ex) ** 2 + (y - ey) ** 2 < hit2:
            return (x, y)
        if y >= 0:
            tx, ty = int(x) // TILE, int(y) // TILE
            if 0 <= tx < COLS and 0 <= ty < ROWS and tm.tile(tx, ty) != 0:
                return (x, y)
    return (x, y)


def explode(cx, cy):
    cx, cy = int(cx), int(cy)
    proj.visible = False                # hide the shell immediately so no stray shape lingers
    rT = CRATER // TILE + 2
    for c in range(max(0, cx // TILE - rT), min(COLS, cx // TILE + rT + 1)):
        for r in range(max(0, cy // TILE - rT), min(ROWS, cy // TILE + rT + 1)):
            ddx = c * TILE + TILE / 2 - cx
            ddy = r * TILE + TILE / 2 - cy
            if ddx * ddx + ddy * ddy <= CRATER * CRATER and tm.tile(c, r) != 0:
                tm.tile(c, r, 0)
    recompute_surf(cx)
    parts.emit(cx, cy, 30, 4, 16, FIRE)                      # fast bright sparks (positional - native emit takes no kwargs)
    parts.emit(cx, cy, 14, 2, 26, pg.rgb565(180, 90, 30))   # slower embers
    sfx(BOOM_SND)
    for t in tanks:                                 # splash damage
        if t["alive"] and (t["x"] - cx) ** 2 + (t["spr"].y - 4 - cy) ** 2 < BLAST * BLAST:
            t["alive"] = False
            t["spr"].flash = INK
            t["barrel"].visible = False             # blow the cannon off the wreck
    for t in tanks:                                 # re-seat survivors on the new surface
        if t["alive"]:
            t["spr"].move(t["x"], surface_px(t["x"]))
            place_barrel(t)
    set_wind_flag()                                 # re-plant the flag if the mid-field surface changed


def is_ai(idx):
    return st.mode == "demo" or (st.mode == "ai" and idx == 1)


def begin_aim():
    st.state = "aim"
    if is_ai(st.cur):
        st.think = AI_THINK
        st.ai_i, st.ai_best, st.ai_bd = 0, (45, 50), 1e18    # restart the spread-out shot search
    else:
        st.think = 0
    st.hud_ang = st.hud_pw = None    # force the next AI-think frame to draw at least once
    update_dots(tanks[st.cur])
    update_hud()


def end_shot():
    a0, a1 = tanks[0]["alive"], tanks[1]["alive"]
    if not (a0 and a1):
        st.winner = -1 if (not a0 and not a1) else (0 if a0 else 1)
        show_over()
    else:
        st.cur = 1 - st.cur
        begin_aim()


def step_fire():
    st.pvy += GRAV * DT
    st.pvx += st.wind * DT
    st.pfx += st.pvx * DT
    st.pfy += st.pvy * DT
    if st.pfy > H + 20 or st.pfx < -20 or st.pfx > W + 20:   # flew off-screen -> miss
        proj.visible = False
        end_shot()
        return
    proj.move(int(st.pfx), int(st.pfy))
    if st.shooter is not None and \
       (st.pfx - st.shooter["x"]) ** 2 + (st.pfy - (st.shooter["spr"].y - 4)) ** 2 < ARM_CLEAR ** 2:
        return                                           # still inside the muzzle-clearance bubble -> not armed
    for t in tanks:                                      # direct hit on a tank?
        if t["alive"] and abs(t["x"] - st.pfx) < HITR and abs((t["spr"].y - 4) - st.pfy) < HITR + 3:
            explode(st.pfx, st.pfy)
            end_shot()
            return
    if st.pfy >= 0:                                      # terrain?
        tx, ty = int(st.pfx) // TILE, int(st.pfy) // TILE
        if 0 <= tx < COLS and 0 <= ty < ROWS and tm.tile(tx, ty) != 0:
            explode(st.pfx, st.pfy)
            end_shot()
            return


def start_game():
    build_terrain()
    pick_flag_spot()
    st.wind = random.uniform(-55, 55)
    set_wind_flag()
    for i, t in enumerate(tanks):
        t["alive"] = True
        t["angle"], t["power"] = 45, 50
        t["spr"].flash = None
        t["spr"].visible = True
        t["spr"].move(t["x"], surface_px(t["x"]))
        place_barrel(t)
    st.cur = 0
    t_title.set("")
    t_a.set("")
    t_b.set("")
    t_over.set("")
    begin_aim()


def show_title():
    st.state = "title"
    hide_dots()
    proj.visible = False
    t_over.set("")
    t_title.set("BANG! BANG!")
    t_a.set("A  -  1 PLAYER vs AI")
    t_b.set("B = 2 PLAYERS   X = DEMO")
    hud_play_widgets(False)
    hud_p.set("")
    hud_s.set("")
    hud_l.set("L/R aim   U/D power")
    hud_r.set("")
    hud.draw()


def show_over():
    st.state = "over"
    hide_dots()
    if st.winner >= 0:
        st.score[st.winner] += 1            # tally the round before showing it
    if st.winner < 0:
        msg = "DRAW"
    elif st.winner == 0:
        msg = "P1 WINS!"
    else:
        msg = "AI WINS!" if st.mode == "ai" else "P2 WINS!"
    t_over.set(msg + "    A = NEXT   B = MENU")
    hud_play_widgets(False)
    hud_p.set("")
    hud_l.set(msg)
    hud_s.set("%d:%d" % (st.score[0], st.score[1]))
    hud_r.set("")
    hud.draw()


# build a backdrop terrain so the title screen isn't empty, then show the menu
build_terrain()
pick_flag_spot()
set_wind_flag()
for _t in tanks:
    _t["spr"].move(_t["x"], surface_px(_t["x"]))
    place_barrel(_t)
show_title()

while True:
    btn.poll()

    if st.state == "title":
        if btn.just_pressed(btn.A):
            _m = "ai"
        elif btn.just_pressed(btn.B):
            _m = "2p"
        elif btn.just_pressed(btn.X):
            _m = "demo"
        else:
            _m = None
        if _m:
            st.mode = _m
            st.score[0] = st.score[1] = 0    # new match -> reset score
            start_game()

    elif st.state == "aim":
        if is_ai(st.cur):
            t = tanks[st.cur]
            enemy = tanks[1 - st.cur]
            n = 0
            while st.ai_i < AI_CANDS_N and n < AI_STEP:   # score a chunk of candidates this frame
                ang = AI_ANG_LO + AI_ANG_STEP * (st.ai_i // AI_PWR_N)
                pw = AI_PWR_LO + AI_PWR_STEP * (st.ai_i % AI_PWR_N)
                st.ai_i += 1
                n += 1
                lx, ly = sim_shot(t, ang, pw)
                d = abs(lx - enemy["x"]) + abs(ly - (enemy["spr"].y - 4)) * 0.3
                if d < st.ai_bd:
                    st.ai_bd, st.ai_best = d, (ang, pw)
            t["angle"], t["power"] = st.ai_best              # provisional aim: barrel swings as it "thinks"
            st.think -= 1
            # dots + HUD depend only on (angle,power) here (x/dir/score/wind fixed this turn) -> redraw
            # ONLY when the provisional aim actually changed, not every one of the 18 think frames.
            if t["angle"] != st.hud_ang or t["power"] != st.hud_pw:
                st.hud_ang, st.hud_pw = t["angle"], t["power"]
                update_dots(t)
                update_hud()
            if st.think <= 0:
                t["angle"] = max(5, min(85, st.ai_best[0] + random.randint(-AI_ANG_ERR, AI_ANG_ERR)))
                t["power"] = max(5, min(100, st.ai_best[1] + random.randint(-AI_PWR_ERR, AI_PWR_ERR)))
                fire(t)
        else:
            t = tanks[st.cur]
            changed = False
            # angle is relative to facing: the key pointing AWAY from the enemy raises the barrel
            up_key = btn.LEFT if t["dir"] > 0 else btn.RIGHT
            dn_key = btn.RIGHT if t["dir"] > 0 else btn.LEFT
            held = (btn.is_pressed(up_key) or btn.is_pressed(dn_key) or
                    btn.is_pressed(btn.UP) or btn.is_pressed(btn.DOWN))
            st.hold = st.hold + 1 if held else 0
            step = 3 if st.hold > 8 else 1              # accelerate after ~0.3s held; ±1 on a tap (fine control)
            if btn.is_pressed(up_key):
                t["angle"] = min(85, t["angle"] + step); changed = True
            if btn.is_pressed(dn_key):
                t["angle"] = max(5, t["angle"] - step); changed = True
            if btn.is_pressed(btn.UP):
                t["power"] = min(100, t["power"] + step); changed = True
            if btn.is_pressed(btn.DOWN):
                t["power"] = max(5, t["power"] - step); changed = True
            if changed:
                update_dots(t)
                update_hud()
            if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
                fire(t)

    elif st.state == "fire":
        step_fire()

    elif st.state == "over":
        if btn.just_pressed(btn.A):
            start_game()          # next round, keep the running score
        elif btn.just_pressed(btn.B):
            show_title()          # back to menu (a new match resets the score)

    parts.tick()

    scene.refresh()
    clock.tick()
