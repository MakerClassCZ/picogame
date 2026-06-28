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
#
# Run:  python3 sim/run.py games/picoracer/code.py --backend pygame
#   or: python3 sim/run.py games/picoracer/code.py --frames 200 --hold B,RIGHT --shot /tmp/pr.png

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
import picogame_fx as fx_mod

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
fx = START_X
fy = START_Y
th = START_TH
speed = 0.0
ACCEL = 0.10                                     # gradual build-up to top speed
BRAKE = 0.35                                      # decisive braking into corners
DRAG = 0.125                                       # coast (lift off B) sheds ~2.5/s -> one lift clears a 90 corner
SPEED_MAX = 7.0
OFFROAD_MAX = 3.5                                 # grass deters but doesn't brick you
OFFROAD_DRAG = 0.93                              # grass friction per frame (tested sweet spot)
TURN = 3.8
GRIP_SPEED = 3.5                                 # full steering grip up to here...
TURN_MIN = 0.42                                  # ...falls to this fraction of TURN at SPEED_MAX (understeer)

cam = fx_mod.Camera(scene, W, H + BAR, lerp=1.0, world_w=WORLD_W, world_h=WORLD_H)
WHITE = pg.rgb565(255, 255, 255)
flash_t = 0                                      # countdown for the best-lap blink on the player car

# --- lap timing: cross the finish line rightward, but only after touching the far-side checkpoint ---
prev_fx = fx
cp_hit = False
lap = 0                                          # laps COMPLETED so far
lap_t = 0
best_t = 0
race_t = 0
NLAPS = 5
mode = "start"                                    # start -> race -> finish

# --- ghosts: each completed lap is recorded (decimated) and replayed by one ghost car, looping ---
REC_STEP = 3                                      # sample 1 of every 3 frames (RAM: ~14 KB for 4+1 traces)
REC_MAX = 420                                     # up to ~31 s lap captured
rec_x = array.array("h", [0] * REC_MAX)          # the lap being driven now
rec_y = array.array("h", [0] * REC_MAX)
rec_a = array.array("h", [0] * REC_MAX)
rec_n = 0
g_x = [array.array("h", [0] * REC_MAX) for _ in range(NGHOST)]   # one stored trace per ghost
g_y = [array.array("h", [0] * REC_MAX) for _ in range(NGHOST)]
g_a = [array.array("h", [0] * REC_MAX) for _ in range(NGHOST)]
g_len = [0] * NGHOST
g_pos = [0.0] * NGHOST                            # float playback cursor (samples), advances 1/REC_STEP per frame
g_done = [False] * NGHOST                         # reached the end of its lap -> park at the finish until re-sync

hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, pg.rgb565(14, 16, 30))
info = hud.label(terminalio.FONT, 4, 3, pg.rgb565(255, 255, 255), "LAP 1")
last_info = None

banner = ui.SceneLabel(scene, pg, terminalio.FONT, 0, H // 2 - 6,
                       pg.rgb565(255, 235, 110), pg.rgb565(0, 12, 42))
FIN_FMT = "FINISH  %02ds   BEST LAP %02ds   B: AGAIN"
banner.reserve(len(FIN_FMT % (0, 0)))


def show_banner(text, big=False):
    banner.set(text)
    banner.sprite.scale = 2 if big else 1
    cw = 12 if big else 6
    banner.sprite.move(max(2, (W - len(text) * cw) // 2), H // 2 - (12 if big else 6))


banner_t = 0                                     # frames a flash banner stays up (GO! / lap time)
countdown_t = 0
cd_phase = -1


def flash_banner(text, frames, big=False):
    global banner_t
    show_banner(text, big)
    banner_t = frames


def reset_race():                                # fresh race: clear all ghosts
    global fx, fy, th, speed, lap, lap_t, race_t, rec_n, prev_fx, cp_hit, flash_t
    fx, fy, th = START_X, START_Y, START_TH
    speed = 0.0
    lap = lap_t = race_t = rec_n = 0
    prev_fx = fx
    cp_hit = False
    flash_t = 0
    car.flash = 0
    for i in range(NGHOST):
        g_len[i] = 0
        g_pos[i] = 0.0
        g_done[i] = False
        ghosts[i].visible = False
    car.move(int(fx), int(fy))
    car.angle = th


def finish_lap():                                # store the just-driven lap as the next ghost
    global lap, lap_t, best_t, rec_n
    if best_t == 0 or lap_t < best_t:
        best_t = lap_t
    if lap < NGHOST:                             # laps 1..4 each spawn a ghost; lap 5 has no slot
        for i in range(rec_n):
            g_x[lap][i] = rec_x[i]
            g_y[lap][i] = rec_y[i]
            g_a[lap][i] = rec_a[i]
        g_len[lap] = rec_n
        g_pos[lap] = 0.0
    lap += 1
    lap_t = 0
    rec_n = 0
    for i in range(min(lap, NGHOST)):            # all active ghosts restart the lap together with the player
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
    rev = min(1.0, abs(speed) / SPEED_MAX)
    freq = IDLE_HZ + (REDLINE_HZ - IDLE_HZ) * (rev ** 0.75)
    if not on_road:
        freq *= 0.8
    engine.set(freq, 0.18 + 0.5 * rev)


def engine_silence():
    if engine is not None:                       # amp 0 = silent THIS buffer (no release tail), then
        engine.set(IDLE_HZ, 0.0)                 # release the held note + reset amp so the next race's
        engine.stop()                            # countdown doesn't roar at the last amplitude


print("PicoRacer - B gas, A brake, LEFT/RIGHT steer. 5 laps - each lap adds a ghost!")
car.move(int(fx), int(fy))
car.angle = th
hud.draw()
show_banner("PICORACER     B: START")

while True:
    btn.poll()

    if mode == "start" or mode == "finish":       # frozen title / results; B begins the countdown
        if btn.just_pressed(btn.B):
            reset_race()
            mode = "countdown"
            countdown_t = 0
            cd_phase = -1
            if engine:
                engine.start()
        else:
            engine_silence()
        cam.follow(fx, fy).apply()
        scene.refresh()
        clock.tick()
        continue

    if mode == "countdown":                        # 3 - 2 - 1 - GO!, with a blip each second
        countdown_t += 1
        ph = min(2, (countdown_t - 1) // 40)
        if ph != cd_phase:
            cd_phase = ph
            show_banner(("3", "2", "1")[ph], big=True)
            sfx(SFX_COUNT)
        if countdown_t > 120:
            sfx(SFX_GO)
            flash_banner("GO!", 28, big=True)
            last_info = None
            mode = "race"
        cam.follow(fx, fy).apply()
        scene.refresh()
        clock.tick()
        continue

    if banner_t > 0:                               # tick down a flash banner (GO! / lap time)
        banner_t -= 1
        if banner_t == 0:
            banner.set("")
    if flash_t > 0:                                # best-lap celebration: BLINK the car white
        flash_t -= 1
        car.flash = WHITE if (flash_t // 3) & 1 else 0
        if flash_t == 0:
            car.flash = 0
    lap_t += 1
    race_t += 1

    a_up = btn.is_pressed(btn.B)
    a_dn = btn.is_pressed(btn.A)
    a_left = btn.is_pressed(btn.LEFT)
    a_right = btn.is_pressed(btn.RIGHT)

    if a_up:
        speed += ACCEL
    elif a_dn:
        speed -= BRAKE
    else:
        speed -= DRAG if speed > 0 else -DRAG
        if abs(speed) < DRAG:
            speed = 0.0
    on_road = road.at_px(tm, min(WORLD_W - 1, int(fx)), min(WORLD_H - 1, int(fy)), tiles.B_SOLID)
    cap = SPEED_MAX if on_road else OFFROAD_MAX
    if not on_road:
        speed *= OFFROAD_DRAG
    speed = max(-cap * 0.5, min(cap, speed))
    engine_update(on_road)
    if speed != 0.0:
        if abs(speed) <= GRIP_SPEED:
            bite = min(1.0, abs(speed) / 2.5)
        else:                                    # above grip speed steering weakens -> understeer, brake to turn
            grip_t = (abs(speed) - GRIP_SPEED) / (SPEED_MAX - GRIP_SPEED)
            bite = 1.0 - grip_t * (1.0 - TURN_MIN)
        th += (a_right - a_left) * TURN * bite * (1 if speed > 0 else -1)

    rad = math.radians(th)
    fx += math.sin(rad) * speed
    fy += -math.cos(rad) * speed
    fx = max(0, min(WORLD_W, fx))
    fy = max(0, min(WORLD_H, fy))

    car.move(int(fx), int(fy))
    car.angle = th

    # --- lap: touch the far-left checkpoint, then cross the finish line rightward ---
    if fx < CP_X:
        cp_hit = True
    if cp_hit and prev_fx < FIN_X <= fx and FIN_Y0 <= fy < FIN_Y1:
        cp_hit = False
        ct = lap_t
        prev_best = best_t
        finish_lap()
        if lap >= NLAPS:
            show_banner(FIN_FMT % (race_t // 40, best_t // 40))
            mode = "finish"
            engine_silence()
        else:
            sfx(SFX_LAP)                          # chime crossing into the next lap
            pb = (prev_best == 0) or (ct < prev_best)
            if pb:
                flash_t = 18                      # ~3 white blinks on a NEW BEST lap only
            flash_banner("LAP %d  %02ds%s" % (lap, ct // 40, "  BEST!" if pb else ""), 70)
    prev_fx = fx

    # --- record this lap (decimated) ---
    if rec_n < REC_MAX and (lap_t - 1) % REC_STEP == 0:
        rec_x[rec_n] = int(fx)
        rec_y[rec_n] = int(fy)
        rec_a[rec_n] = int(th) % 360
        rec_n += 1

    # --- advance + draw each active ghost (loops its own trace, position interpolated) ---
    for i in range(min(lap, NGHOST)):
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
        ghosts[i].angle = g_a[i][i0]
        ghosts[i].visible = True

    cam.follow(fx, fy).apply()
    scene.refresh()

    show = (lap + 1, lap_t // 40, best_t // 40)
    if show != last_info:
        last_info = show
        msg = "LAP %d/%d  %02ds" % (min(lap + 1, NLAPS), NLAPS, lap_t // 40)
        if best_t:
            msg += "  BEST %02ds" % (best_t // 40)
        info.set(msg)
        hud.draw()
    clock.tick()
