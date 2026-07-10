# PicoRacer - a top-down racing game with a moving camera, on the (CC0) Kenney Racing Pack.
# The track is a hand-laid 44x28 Tilemap (built in the track editor, deduped to 14 tiles with
# per-cell flip/transpose, + a 2-cell grass border). The car is a Kenney top-down sprite rotated
# at runtime by its heading; the camera follows it across a world bigger than the screen.
#
# A race is 5 LAPS, and after each lap a GHOST car joins - a replay of that lap of yours, so the
# final lap has all 5 cars on track (you in red + blue/green/yellow/black ghosts of laps 1-4).
#
# Controls: B gas (and START), A brake/reverse, LEFT/RIGHT steer. Drive on the tarmac; grass slows
# you. Copy picogame_* helpers + picoracer_track + race_cars assets to CIRCUITPY.

import math
import array
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_ui as ui
import picogame_tiles as tiles
import picogame_fx as fx

import picoracer_track as track
import race_cars

W, H = board.DISPLAY.width, board.DISPLAY.height
T = track.TILE                                   # 32
BAR = 16                                          # HUD bar height
GRASS = pg.rgb565(96, 168, 78)
scene, bufA, bufB = picogame_game.setup(background=GRASS, top=BAR)   # strip_h = board default (8)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(40)

# --- track: tileset (frame 0 transparent, 1..14 = road tiles) + the laid-out tilemap ---
tileset = track.bitmap(pg)
tm = track.build(pg, tileset)
scene.add(tm)
COLS, ROWS = track.COLS, track.ROWS
WORLD_W, WORLD_H = COLS * T, ROWS * T

# Every placed tile (frames 1..14) is drivable road -> SOLID; empty cells (frame 0) are grass.
road = tiles.TileFlags({f: tiles.SOLID for f in range(1, track.FRAMES)}, tile_px=T)

# --- start / finish: bottom straight crossed at column 34, driving RIGHT ---
FIN_COL = 34                                     # +2 for the grass border (track.BORDER)
FIN_X = FIN_COL * T
FIN_Y0, FIN_Y1 = 23 * T, 26 * T                 # the bottom-straight y-band (only this straight counts)
CP_X = 6 * T                                     # checkpoint: the car must reach the far LEFT each lap
START_X = (FIN_COL - 0.5) * T
START_Y = 24.5 * T
START_TH = 90.0                                  # 0 = nose up, +clockwise -> 90 faces right

# --- cars: player (red) drawn ON TOP of up to 4 ghosts (blue/green/yellow/black) ---
NGHOST = 4
ghosts = [pg.Sprite(race_cars.bitmap(pg, 1 + i), 0, 0) for i in range(NGHOST)]
for g in ghosts:
    g.anchor = (0.5, 0.5)
    g.visible = False
    scene.add(g)
car = pg.Sprite(race_cars.bitmap(pg, 0), 0, 0)
car.anchor = (0.5, 0.5)
scene.add(car)

# --- car state (world pixels, heading in degrees) ---
ACCEL = 0.10                                     # gradual build-up to top speed
BRAKE = 0.35                                      # decisive braking into corners
DRAG = 0.125                                       # coast (lift off B) sheds ~2.5/s -> one lift clears a 90 corner
SPEED_MAX = 7.0
OFFROAD_MAX = 3.5                                 # grass deters but doesn't brick you
OFFROAD_DRAG = 0.93                              # grass friction per frame (tested sweet spot)
TURN = 3.8
GRIP_SPEED = 3.5                                 # full steering grip up to here...
TURN_MIN = 0.42                                  # ...falls to this fraction of TURN at SPEED_MAX (understeer)

cam = fx.Camera(scene, W, H + BAR, lerp=1.0, world_w=WORLD_W, world_h=WORLD_H)
WHITE = pg.rgb565(255, 255, 255)

NLAPS = 5


# --- game state (car pos/heading, lap timing, banners/countdown) ---
class State:
    def __init__(self):
        self.subx = START_X
        self.suby = START_Y
        self.th = START_TH
        self.speed = 0.0
        self.flash_t = 0                         # countdown for the best-lap blink on the player car
        # lap timing: cross the finish line rightward, but only after touching the far-side checkpoint
        self.prev_subx = START_X
        self.cp_hit = False
        self.lap = 0                             # laps COMPLETED so far
        self.lap_t = 0
        self.best_t = 0
        self.race_t = 0
        self.mode = "start"                      # start -> race -> finish
        self.rec_n = 0
        self.banner_t = 0                        # frames a flash banner stays up (GO! / lap time)
        self.countdown_t = 0
        self.cd_phase = -1
        self.last_lap = -1                       # HUD shadow ints (no per-frame tuple)
        self.last_lsec = -1
        self.last_bsec = -1


st = State()

# --- ghosts: each completed lap is recorded (decimated) and replayed by one ghost car, looping ---
REC_STEP = 3                                      # sample 1 of every 3 frames (RAM: ~14 KB for 4+1 traces)
REC_MAX = 420                                     # up to ~31 s lap captured
rec_x = array.array("h", [0] * REC_MAX)          # the lap being driven now
rec_y = array.array("h", [0] * REC_MAX)
rec_a = array.array("B", [0] * REC_MAX)          # angle//2 packed into a byte (0..179); *2 on use
g_x = [array.array("h", [0] * REC_MAX) for _ in range(NGHOST)]   # one stored trace per ghost
g_y = [array.array("h", [0] * REC_MAX) for _ in range(NGHOST)]
g_a = [array.array("B", [0] * REC_MAX) for _ in range(NGHOST)]
g_len = [0] * NGHOST
g_pos = [0.0] * NGHOST                            # float playback cursor (samples), advances 1/REC_STEP per frame
g_done = [False] * NGHOST                         # reached the end of its lap -> park at the finish until re-sync

hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, pg.rgb565(14, 16, 30))
info = hud.label(terminalio.FONT, 4, 3, pg.rgb565(255, 255, 255), "LAP 1")

banner = ui.SceneLabel(scene, pg, terminalio.FONT, 0, H // 2 - 6,
                       pg.rgb565(255, 235, 110), pg.rgb565(0, 12, 42))
FIN_FMT = "FINISH  %02ds   BEST LAP %02ds   B: AGAIN"
banner.reserve(len(FIN_FMT % (0, 0)))


def show_banner(text, big=False):
    banner.set(text)
    banner.sprite.scale = 2 if big else 1
    cw = 12 if big else 6
    banner.sprite.move(max(2, (W - len(text) * cw) // 2), H // 2 - (12 if big else 6))


def flash_banner(text, frames, big=False):
    show_banner(text, big)
    st.banner_t = frames


def reset_race():                                # fresh race: clear all ghosts
    st.subx, st.suby, st.th = START_X, START_Y, START_TH
    st.speed = 0.0
    st.lap = st.lap_t = st.race_t = st.rec_n = 0
    st.prev_subx = st.subx
    st.cp_hit = False
    st.flash_t = 0
    car.flash = 0
    for i in range(NGHOST):
        g_len[i] = 0
        g_pos[i] = 0.0
        g_done[i] = False
        ghosts[i].visible = False
    car.move(int(st.subx), int(st.suby))
    car.angle = st.th


def finish_lap():                                # store the just-driven lap as the next ghost
    global rec_x, rec_y, rec_a
    if st.best_t == 0 or st.lap_t < st.best_t:
        st.best_t = st.lap_t
    if st.lap < NGHOST:                          # laps 1..4 each spawn a ghost; lap 5 has no slot
        # rec_* and this ghost slot are same-size arrays -> swap the buffer REFERENCES instead of
        # copying up to 1260 elements. The just-driven trace becomes the ghost; the ghost's old
        # (now-unused) buffer becomes the fresh recording buffer (rec_n resets to 0, so its stale
        # contents are never read). Playback reads only [0, g_len) -> identical to the element-copy.
        rec_x, g_x[st.lap] = g_x[st.lap], rec_x
        rec_y, g_y[st.lap] = g_y[st.lap], rec_y
        rec_a, g_a[st.lap] = g_a[st.lap], rec_a
        g_len[st.lap] = st.rec_n
        g_pos[st.lap] = 0.0
    st.lap += 1
    st.lap_t = 0
    st.rec_n = 0
    for i in range(min(st.lap, NGHOST)):         # all active ghosts restart the lap together with the player
        g_pos[i] = 0.0
        g_done[i] = False


# --- engine sound: a deep SAW drone whose pitch tracks the revs (device-only; silent in sim) ---
IDLE_HZ, REDLINE_HZ = 42.0, 175.0
try:
    import picogame_synth as snd
    _synth = snd.Synth(sfx_level=0.5)
    engine = snd.Drone(_synth, waveform=snd.SAW, amplitude=0.0)
    SFX_COUNT = snd.note(72, snd.SQUARE, decay=0.10)     # 3..1 countdown blip
    SFX_GO = snd.note(84, snd.SQUARE, decay=0.16)        # GO!
    SFX_LAP = snd.note(88, snd.TRIANGLE, decay=0.20)     # chime crossing into the next lap
except Exception:                                # no synthio (simulator) -> silent, logic still runs
    _synth = None
    engine = None
    SFX_COUNT = SFX_GO = SFX_LAP = None


def sfx(n):
    if _synth is not None:                         # held notes (the engine drone) now survive sfx (lib fix)
        _synth.sfx(n)


def engine_update(on_road):
    if engine is None:
        return
    rev = min(1.0, abs(st.speed) / SPEED_MAX)
    freq = IDLE_HZ + (REDLINE_HZ - IDLE_HZ) * (rev ** 0.75)
    if not on_road:
        freq *= 0.8
    engine.set(freq, 0.18 + 0.5 * rev)


def engine_silence():
    if engine is not None:                       # amp 0 = silent THIS buffer (no release tail), then
        engine.set(IDLE_HZ, 0.0)                 # release the held note + reset amp so the next race's
        engine.stop()                            # countdown doesn't roar at the last amplitude


print("PicoRacer - B gas, A brake, LEFT/RIGHT steer. 5 laps - each lap adds a ghost!")
car.move(int(st.subx), int(st.suby))
car.angle = st.th
hud.draw()
show_banner("PICORACER     B: START")

while True:
    btn.poll()

    if st.mode == "start" or st.mode == "finish":  # frozen title / results; B begins the countdown
        if btn.just_pressed(btn.B):
            reset_race()
            st.mode = "countdown"
            st.countdown_t = 0
            st.cd_phase = -1
            if engine:
                engine.start()
        else:
            engine_silence()
        cam.follow(st.subx, st.suby).apply()
        scene.refresh()
        clock.tick()
        continue

    if st.mode == "countdown":                     # 3 - 2 - 1 - GO!, with a blip each second
        st.countdown_t += 1
        ph = min(2, (st.countdown_t - 1) // 40)
        if ph != st.cd_phase:
            st.cd_phase = ph
            show_banner(("3", "2", "1")[ph], big=True)
            sfx(SFX_COUNT)
        if st.countdown_t > 120:
            sfx(SFX_GO)
            flash_banner("GO!", 28, big=True)
            st.last_lap = st.last_lsec = st.last_bsec = -1
            st.mode = "race"
        cam.follow(st.subx, st.suby).apply()
        scene.refresh()
        clock.tick()
        continue

    if st.banner_t > 0:                            # tick down a flash banner (GO! / lap time)
        st.banner_t -= 1
        if st.banner_t == 0:
            banner.set("")
    if st.flash_t > 0:                             # best-lap celebration: BLINK the car white
        st.flash_t -= 1
        car.flash = WHITE if (st.flash_t // 3) & 1 else 0
        if st.flash_t == 0:
            car.flash = 0
    st.lap_t += 1
    st.race_t += 1

    a_up = btn.is_pressed(btn.B)
    a_dn = btn.is_pressed(btn.A)
    a_left = btn.is_pressed(btn.LEFT)
    a_right = btn.is_pressed(btn.RIGHT)

    if a_up:
        st.speed += ACCEL
    elif a_dn:
        st.speed -= BRAKE
    else:
        st.speed -= DRAG if st.speed > 0 else -DRAG
        if abs(st.speed) < DRAG:
            st.speed = 0.0
    on_road = road.at_px(tm, min(WORLD_W - 1, int(st.subx)), min(WORLD_H - 1, int(st.suby)), tiles.B_SOLID)
    cap = SPEED_MAX if on_road else OFFROAD_MAX
    if not on_road:
        st.speed *= OFFROAD_DRAG
    st.speed = max(-cap * 0.5, min(cap, st.speed))
    engine_update(on_road)
    if st.speed != 0.0:
        if abs(st.speed) <= GRIP_SPEED:
            bite = min(1.0, abs(st.speed) / 2.5)
        else:                                    # above grip speed steering weakens -> understeer, brake to turn
            grip_t = (abs(st.speed) - GRIP_SPEED) / (SPEED_MAX - GRIP_SPEED)
            bite = 1.0 - grip_t * (1.0 - TURN_MIN)
        st.th += (a_right - a_left) * TURN * bite * (1 if st.speed > 0 else -1)

    rad = math.radians(st.th)
    st.subx += math.sin(rad) * st.speed
    st.suby += -math.cos(rad) * st.speed
    st.subx = max(0, min(WORLD_W, st.subx))
    st.suby = max(0, min(WORLD_H, st.suby))

    car.move(int(st.subx), int(st.suby))
    car.angle = st.th

    # --- lap: touch the far-left checkpoint, then cross the finish line rightward ---
    if st.subx < CP_X:
        st.cp_hit = True
    if st.cp_hit and st.prev_subx < FIN_X <= st.subx and FIN_Y0 <= st.suby < FIN_Y1:
        st.cp_hit = False
        lap_time = st.lap_t
        prev_best = st.best_t
        finish_lap()
        if st.lap >= NLAPS:
            show_banner(FIN_FMT % (st.race_t // 40, st.best_t // 40))
            st.mode = "finish"
            engine_silence()
        else:
            sfx(SFX_LAP)                          # chime crossing into the next lap
            pb = (prev_best == 0) or (lap_time < prev_best)
            if pb:
                st.flash_t = 18                   # ~3 white blinks on a NEW BEST lap only
            flash_banner("LAP %d  %02ds%s" % (st.lap, lap_time // 40, "  BEST!" if pb else ""), 70)
    st.prev_subx = st.subx

    # --- record this lap (decimated) ---
    if st.rec_n < REC_MAX and (st.lap_t - 1) % REC_STEP == 0:
        rec_x[st.rec_n] = int(st.subx)
        rec_y[st.rec_n] = int(st.suby)
        rec_a[st.rec_n] = (int(st.th) % 360) // 2
        st.rec_n += 1

    # --- advance + draw each active ghost (loops its own trace, position interpolated) ---
    for i in range(min(st.lap, NGHOST)):
        n = g_len[i]
        if n < 2:
            continue
        if not g_done[i]:                        # play the lap once, then park at the finish until re-sync
            p = g_pos[i] + 1.0 / REC_STEP
            if p >= n - 1:
                p = n - 1
                g_done[i] = True
            g_pos[i] = p
        p = g_pos[i]
        i0 = int(p)
        i1 = i0 + 1 if i0 + 1 < n else i0
        fr = p - i0
        gx = g_x[i][i0] + (g_x[i][i1] - g_x[i][i0]) * fr
        gy = g_y[i][i0] + (g_y[i][i1] - g_y[i][i0]) * fr
        ghosts[i].move(int(gx), int(gy))
        ghosts[i].angle = g_a[i][i0] * 2
        ghosts[i].visible = True

    cam.follow(st.subx, st.suby).apply()
    scene.refresh()

    lap1 = st.lap + 1
    lsec = st.lap_t // 40
    bsec = st.best_t // 40
    if lap1 != st.last_lap or lsec != st.last_lsec or bsec != st.last_bsec:
        st.last_lap, st.last_lsec, st.last_bsec = lap1, lsec, bsec
        msg = "LAP %d/%d  %02ds" % (min(st.lap + 1, NLAPS), NLAPS, st.lap_t // 40)
        if st.best_t:
            msg += "  BEST %02ds" % (st.best_t // 40)
        info.set(msg)
        hud.draw()
    clock.tick()
