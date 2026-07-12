# Missile Command on picogame - genre port of TinyJoypad's TinyMissile.
# Particle-heavy showcase: move a crosshair, fire blasts that detonate as particle
# explosions and wipe incoming missiles caught in the radius; defend the cities.
# Copy with picogame_game/input/clock/ui/audio/pool. Requires Particles firmware.

import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_ui as ui
import picogame_synth as snd
import picogame_sfx
import picogame_pool
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(10, 8, 30))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if no audio

W, H = board.DISPLAY.width, board.DISPLAY.height
GROUND = H - 14
BLAST_R = 34


cross_bmp = shp.rect(7, 7, pg.rgb565(255, 255, 255))
warhead_bmp = shp.rect(4, 4, pg.rgb565(255, 120, 120))
city_bmp = shp.rect(24, 12, pg.rgb565(90, 200, 120))

particles = pg.Particles(192, size=2, gravity=0.0)
crosshair = pg.Sprite(cross_bmp, W // 2, H // 2)

CITY_XS = [30 + i * 52 for i in range(5)]
cities = [pg.Sprite(city_bmp, cx, GROUND, visible=True) for cx in CITY_XS]

# --- classic Missile Command "rays": each incoming warhead streaks a trail from where it entered
# the sky to its current position, and firing draws a beam from the ground battery to the target.
# Drawn with view.line into the render strips (StripDraw = zero extra buffer). ---
TRAIL_COL = pg.rgb565(255, 90, 60)
BEAM_COL = pg.rgb565(120, 230, 255)
BATTERY = (W // 2, GROUND)
beam = [0, 0, 0, 0, 0]                   # x0, y0, x1, y1, frames-left


def draw_rays(view, vx, vy, vw, vh):
    for m in incoming.items:
        if m.visible:
            view.line(int(m.data[4]) - vx, -vy, int(m.data[0]) - vx, int(m.data[1]) - vy, TRAIL_COL)
    if beam[4] > 0:
        view.line(beam[0] - vx, beam[1] - vy, beam[2] - vx, beam[3] - vy, BEAM_COL)


scene.add(pg.StripDraw(draw_rays, 0, 0, W, GROUND))   # bottom layer: rays under the sprites
scene.add(particles)
scene.add_all(cities)
# Pool gives spawn()/free()/free_all()/items and uses sprite.visible AS the alive
# flag; float kinematics ride on sprite.data = [x, y, vx, vy, entry_x]. It adds its
# sprites to the scene here, keeping the original z-order (warheads under crosshair).
incoming = picogame_pool.Pool(scene, warhead_bmp, 8)
scene.add(crosshair)
# HUD as a scene-layer label (painted BY scene.refresh): an immediate Label.draw() over a live fast
# Display fights the scene's strip push and flickers. SceneLabel is the right component here.
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, pg.rgb565(255, 230, 160), pg.rgb565(10, 8, 30))
hud.reserve(21)

score = 0
frame = 0
# shadow copies of the last-shown HUD values - only format+set the string when
# SCORE or the live-city count actually changed (avoids a throwaway %-format
# alloc every frame). Shadows start at -1 so the first frame always draws.
_h_score = -1
_h_cities = -1


def live_cities():
    return [c for c in cities if c.visible]


def count_live_cities():
    # same alive test as live_cities() but no throwaway list - used on the
    # every-frame paths (restart check + HUD) where only the count is needed.
    n = 0
    for c in cities:
        if c.visible:
            n += 1
    return n


def spawn():
    cs = live_cities()
    if not cs:
        return
    m = incoming.spawn()                        # first free sprite, now visible (or None)
    if m is None:
        return
    x = random.randint(0, W - 4)
    target = random.choice(cs).x + 12
    steps = 90 + random.randint(0, 60)
    # [x, y, vx, vy, entry_x] (float pos); entry_x = fixed top end of the trail ray
    m.data = [float(x), 0.0, (target - x) / steps, (GROUND - 0) / steps, float(x)]
    m.move(x, 0)


print("D-pad aim | B fire blast. Defend the cities!")
while True:
    btn.poll()
    frame += 1
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx or dy:
        crosshair.move(max(0, min(W - 7, crosshair.x + dx * 5)),
                       max(16, min(GROUND, crosshair.y + dy * 5)))

    if btn.just_pressed(btn.B):
        ex, ey = crosshair.x + 3, crosshair.y + 3
        beam[0], beam[1], beam[2], beam[3], beam[4] = BATTERY[0], BATTERY[1], ex, ey, 4
        particles.emit(ex, ey, 26, 5, 24, pg.rgb565(255, 200, 60))
        kit.boom()                 # blast detonation
        for m in incoming.items:
            if not m.visible:
                continue
            ddx, ddy = m.data[0] - ex, m.data[1] - ey
            if ddx * ddx + ddy * ddy < BLAST_R * BLAST_R:   # squared dist, no sqrt
                incoming.free(m)
                score += 25
                particles.emit(int(m.data[0]), int(m.data[1]), 10, 4, 18, pg.rgb565(255, 120, 120))

    if frame % 40 == 0:
        spawn()

    for m in incoming.items:
        if not m.visible:
            continue
        m.data[0] += m.data[2]
        m.data[1] += m.data[3]
        if m.data[1] >= GROUND:
            incoming.free(m)
            # destroy the nearest living city
            best = None
            for c in cities:
                if c.visible and (best is None or abs(c.x + 12 - m.data[0]) < abs(best.x + 12 - m.data[0])):
                    best = c
            if best is not None:
                best.visible = False
                kit.hurt()             # a city lost
                particles.emit(best.x + 12, GROUND, 20, 4, 22, pg.rgb565(90, 200, 120))
        else:
            m.move(int(m.data[0]), int(m.data[1]))

    n_cities = count_live_cities()
    if n_cities == 0:            # all gone -> restart
        kit.explosion()
        score = 0
        for c in cities:
            c.visible = True
        incoming.free_all()
        n_cities = len(cities)

    if beam[4] > 0:                          # the firing beam is a brief flash
        beam[4] -= 1
    kit.tick()
    particles.tick()
    if score != _h_score or n_cities != _h_cities:   # before refresh -> painted by it
        _h_score, _h_cities = score, n_cities
        hud.set("SCORE %05d  CITIES %d" % (score, n_cities))
    scene.refresh()
    clock.tick()
