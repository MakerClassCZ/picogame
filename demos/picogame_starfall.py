# Starfall - a tiny arcade catch-and-dodge game, built to dogfood the picogame-game-design
# skill. Core loop: move your tray left/right, CATCH the green gems (score), DODGE the red
# bombs (lose a life). It speeds up as your score climbs. Three lives, instant restart.
#
# Design notes (the skill's method):
#  * core verb = catch; genre = endless/arcade; target feeling = quick tense reflexes.
#  * readability: gems are green CIRCLES, bombs are red SQUARES (shape + colour, not colour
#    alone) so it's colourblind-fair on a small screen.
#  * juice: a white pop-ring + a coin on catch; the tray flashes + screen shakes on a hit.
#  * difficulty: fall speed and spawn rate ramp with score, but stay fair (telegraphed fall).
#  * fits RP2040: a fixed pool of sprites (no per-frame alloc), generated shapes (no art).
#
# Run in the sim:  python3 sim/run.py examples/picogame_starfall.py --backend pygame
#            or:   python3 sim/run.py examples/picogame_starfall.py --frames 120 --hold LEFT --shot out.png

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui
import picogame_pool
import picogame_rand
import picogame_synth as snd
import picogame_sfx

W, H = board.DISPLAY.width, board.DISPLAY.height
BAR = 16
BG = pg.rgb565(16, 18, 34)
INK = pg.rgb565(255, 255, 255)
scene, bufA, bufB = picogame_game.setup(background=BG, top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# --- art: generated shapes (gem = green circle, bomb = red square) ---
GEM = shp.circle(13, pg.rgb565(80, 220, 120))
BOMB = shp.rect(12, 12, pg.rgb565(230, 70, 70))
TRAY = shp.rect(30, 8, pg.rgb565(120, 180, 255))
TRAY_HIT_COLOR = pg.rgb565(255, 120, 120)
POP = shp.ring(22, INK, 3)

# --- player tray ---
tray = pg.Sprite(TRAY, W // 2, H - 14)
tray.anchor = (0.5, 0.5)
scene.add(tray)

# --- a fixed pool of falling items (no per-frame allocation) ---
# picogame_pool.Pool: sprite.visible IS the alive flag; per-item state on sprite.data.
MAXITEMS = 6
items = picogame_pool.Pool(scene, GEM, MAXITEMS, anchor=(0.5, 0.5))
# Pre-seed each pool slot's .data once so spawns MUTATE in place (no per-spawn dict).
for s in items.items:
    s.data = {"bomb": False, "vy": 0.0, "suby": 0.0}

# --- catch pop (juice) ---
pop = pg.Sprite(POP, 0, 0)
pop.anchor = (0.5, 0.5)
pop.visible = False
scene.add(pop)

# --- juice helpers (picogame_fx): screen shake + dither fade (added LAST = on top) ---
import picogame_fx as fx
shaker = fx.Shake(scene, max_offset=6)
fader = fx.Fade(scene, W, H)                     # black dither fade overlay

# --- HUD ---
hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, pg.rgb565(10, 12, 24))
hud_l = hud.label(terminalio.FONT, 4, 3, INK, "SCORE 0   LIVES 3")
hud.draw()

rng = picogame_rand.Rand(0x2545)               # seeded = deterministic sim replays

# --- game state ---
class State:
    def __init__(self):
        self.score = 0
        self.lives = 3
        self.spawn_cd = 0
        self.mercy = 0                              # i-frames after a hit (deep-difficulty-flow generosity)
        self.freeze = 0                             # hit-stop frames (deep-game-feel C2)
        self.over = False
        self.last_score = -1                        # HUD change-detect (plain shadow ints, no per-frame tuple)
        self.last_lives = -1
        self.pop_t = 0


st = State()


def reset():
    global st
    st = State()
    items.free_all()
    fader.set(fader.LEVELS); fader.into(speed=2)    # fade in (picogame_fx dither)


def spawn():
    s = items.spawn()
    if s is None:                                   # pool full
        return
    bomb = rng.chance(0.35)                         # ~1/3 are bombs
    s.bitmap = BOMB if bomb else GEM
    s.move(8 + rng.below(W - 16), BAR + 6)
    d = s.data                                      # mutate in place (speed ramps with score)
    d["bomb"] = bomb
    d["vy"] = 1.6 + st.score * 0.02
    d["suby"] = float(BAR + 6)


kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if no audio
reset()
print("Starfall - LEFT/RIGHT catch gems, dodge bombs. A restarts when over.")

while True:
    btn.poll()
    kit.tick()                                   # drive the SFX sequencer every frame

    if st.over:
        if btn.just_pressed(btn.A):
            reset()
        fader.tick(); shaker.tick(0, 0)
        scene.refresh()
        if st.score != st.last_score or st.lives != st.last_lives:
            st.last_score = st.score
            st.last_lives = st.lives
            hud_l.set("GAME OVER  %d   A=RETRY" % st.score)
            hud.draw()
        clock.tick()
        continue

    # --- hit-stop: freeze gameplay a few frames on impact (keeps shaking) ---
    if st.freeze > 0:
        st.freeze -= 1
        fader.tick(); shaker.tick(0, 0)
        scene.refresh()
        clock.tick()
        continue

    # --- move tray ---
    tray.x += (btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)) * 5
    tray.x = max(16, min(W - 16, tray.x))
    base_y = H - 14
    tray.move(tray.x, base_y)

    # --- mercy i-frames after a hit: blink the tray, then restore (fairness) ---
    if st.mercy > 0:
        st.mercy -= 1
        tray.visible = (st.mercy // 3) & 1 == 0
        if st.mercy == 0:
            tray.visible = True
            tray.flash = None

    # --- spawn ---
    st.spawn_cd -= 1
    if st.spawn_cd <= 0:
        spawn()
        st.spawn_cd = max(10, 30 - st.score // 3)   # spawn faster as score climbs

    # --- fall + collide ---
    for s in items.items:
        if not s.visible:
            continue
        d = s.data
        d["suby"] += d["vy"]
        s.move(s.x, int(d["suby"]))
        # caught? half-extents: item radius 6 + tray half-width 15 / half-height 4
        if s.overlaps(tray):
            items.free(s)
            if d["bomb"]:
                if st.mercy == 0:                    # mercy window: a hit can't chain-kill you
                    st.lives -= 1
                    shaker.add(0.6)                  # big shake (picogame_fx, deep-game-feel C1)
                    st.freeze = 3                    # hit-stop (deep-game-feel C2)
                    st.mercy = 24
                    tray.flash = TRAY_HIT_COLOR
                    kit.hurt()
                    if st.lives <= 0:
                        kit.explosion()
                        st.over = True
                        st.last_score = -1            # force one HUD redraw on the game-over transition
                        fader.out(speed=2)           # fade to black on game over
            else:
                st.score += 1
                shaker.add(0.12)                     # tiny kick on catch
                kit.coin()
                pop.move(s.x, s.y); pop.visible = True
                st.pop_t = 5
        elif d["suby"] > H + 8:                        # fell off the bottom
            items.free(s)

    # --- pop fade (juice) ---
    if st.pop_t > 0:
        st.pop_t -= 1
        if st.pop_t == 0:
            pop.visible = False

    fader.tick(); shaker.tick(0, 0)
    scene.refresh()

    if st.score != st.last_score or st.lives != st.last_lives:
        st.last_score = st.score
        st.last_lives = st.lives
        hud_l.set("SCORE %d   LIVES %d" % (st.score, st.lives))
        hud.draw()
    clock.tick()
