# Pico Wing - a tiny vertical shmup. You are the last interceptor holding the sky; raiders
# pour down from above. Move (D-pad), autofire (hold A), panic-bomb (B). Build a KILL CHAIN:
# every kill ramps a score multiplier, but a raider that slips past you resets it - greed vs safety.
# Three lives, instant restart. Grown from the journey demo's shooter segment into a real game.
#
# Design notes (the picogame-game-design skill's method):
#  * fantasy = the pico wing holding the sky; verb = SHOOT (+ dodge); genre = vertical shmup.
#  * twist ("and also") = a kill-chain multiplier an escaped raider resets.
#  * readability: player ship is grey + points UP; raiders are WARM-AMBER-tinted + point DOWN
#    (shape AND colour, high luminance contrast on the dark-blue sky, colourblind-fair on 320x240).
#  * juice: shoot/explosion beeps, hit-flash + particle burst on a kill, screen-shake + i-frame
#    blink on a player hit, a full-screen invert pulse on bomb.
#  * fairness: a forgiving central hitbox (< the 32px sprite); raiders are telegraphed (descend from the
#    top, > 8 frames to reach you); i-frames after a hit; a panic bomb; instant restart.
#  * difficulty: spawn cadence + raider speed ramp with time, in a sawtooth (a short lull every ~20 s).
#  * fits RP2040: fixed Sprite pools (no per-frame alloc), shared 32px PAL8 art (Kenney CC0), shape bg.
#
# Run:  python3 sim/run.py games/picogame_picowing.py --backend pygame
#   or: python3 sim/run.py games/picogame_picowing.py --frames 200 --hold A,LEFT --shot /tmp/lw.png

import board
import array
import gc
import terminalio
import picogame as pg
import picogame_cutscene as cut
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_ui as ui
import picogame_pool
import picogame_rand
import picogame_fx as fx
import plane                                       # Kenney Pixel Shmup ship (CC0), 32x32 PAL8
import enemy                                       # Kenney Pixel Shmup enemy (CC0), 32x32 PAL8

# Sound uses the signature SFX kit (picogame_sfx). The game keeps its own sfx("name") call
# sites; each name maps to a kit voice, and sfx_tick() runs once per frame in the loop.
import picogame_synth as snd
import picogame_sfx

_kit = picogame_sfx.Kit(snd.Synth())                 # silent no-op if the board has no audio
_SFX = {"shot": _kit.zap,        # player fire
        "hurt": _kit.hurt,       # player hit
        "kill": _kit.boom,       # raider destroyed
        "bomb": _kit.explosion,  # smart-bomb blast
        "jam": _kit.blip,        # gun overheated/locked (denied tick)
        "extra": _kit.powerup}   # extra life / milestone


def sfx(name):
    _SFX[name]()


def sfx_tick():
    _kit.tick()

try:
    import picogame_save
    _hi = picogame_save.Save("lastwing", {"hi": ("I", 0)})
except Exception:
    _hi = None                                        # NVM hi-score is optional (sim/some builds lack it)


def C(r, g, b):
    return pg.rgb565(r, g, b)


W, H = board.DISPLAY.width, board.DISPLAY.height
BAR = 16                                              # top HUD strip
SKY = C(18, 44, 104)
INK = C(10, 14, 36)
TEXT = C(228, 234, 255)
WHITE = C(255, 255, 255)

# Gun heat: holding fire overheats the gun and locks it; short bursts stay cool. Makes firing a
# decision again (so you can't just hold A and wall off every raider) and feeds the chain tension.
HEAT_PER_SHOT = 9                                     # +9/shot, fires every 6f -> ~12 shots (2.4s) to lock
COOL_IDLE = 2                                         # -2/frame when not firing (a 5-shot burst cools in <1s)
COOL_LOCKED = 3                                       # -3/frame while locked -> ~0.8s lockout
WARN_HEAT = 70                                        # bar turns red here (~0.8s telegraph before lock)
WARM_HEAT = 40                                        # bar turns orange here (warming up)
RESET_HEAT = 30                                       # gun unlocks once heat drains back to here

# Player<->raider hit radius (px between sprite centres). Ships are 32px; smaller felt too forgiving
# (wings overlapped with no hit). Lower = kinder, higher = stricter.
HIT_R = 20

# Bullet<->raider hit radius (px between centres). Generous so a shot near the raider still connects.
SHOT_R = 16

# --- HUD layout, derived from W so the left cluster (heat gauge + chain readout) never collides with
# the W-anchored life/bomb icons on a narrow (240) screen. At W=320 this reproduces the original layout
# (heat 82..141, chain at 150); on a 240 screen the chain right-anchors before the icons, shows just the
# multiplier, and the heat gauge compresses to fit the shrunken gap. ---
RIGHT_X = W - 90                                     # left edge of the right cluster (life icons)
FREE0 = 4 + 11 * 6 + 4                                # right edge of "SCORE 00000" + margin
FREE1 = RIGHT_X - 4                                   # left edge of the life icons - margin
CHAIN_W = max(18, min(74, (FREE1 - FREE0) - 30))     # chain readout budget (keeps >=30 px for the gauge)
CHAIN_X = FREE1 - CHAIN_W                             # right-anchored -> 150 at 320, 104 at 240
CHAIN_FULL = CHAIN_W >= 72                            # narrow -> show just "xN" (the multiplier)
HEAT_SEGS = 5
HEAT_X0 = FREE0 + 8                                   # 82 at 320
_heat_avail = CHAIN_X - 6 - HEAT_X0                   # px available for the gauge before the chain readout
HEAT_DX = max(3, min(12, _heat_avail // HEAT_SEGS))   # segment spacing (12 at 320, shrinks on narrow)
HEAT_SW = max(2, min(11, HEAT_DX - 1))                # segment width

scene, bufA, _ = picogame_game.setup(background=SKY, top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
rng = picogame_rand.Rand(0x5159)
shake = fx.Shake(scene)
bomb_flash = fx.InvertFlash(board.DISPLAY)   # FREE full-screen invert pulse for the bomb (HW)

# --- art ---
PLANE = plane.bitmap(pg)
# Raiders reuse the Kenney enemy SHAPE with a warm palette swap (tint only MULTIPLIES/darkens, so it
# can't turn the green art bright-amber); rebuilding the PAL8 bitmap gives full high-luminance control.
_WARM = array.array("H", [0, C(150, 40, 30), C(255, 130, 45), C(120, 45, 25),
                          C(255, 215, 130), C(235, 90, 45), C(255, 245, 190)])
ENEMY = pg.Bitmap(enemy.DATA, enemy.WIDTH, enemy.HEIGHT, format=enemy.FORMAT,
                  palette=_WARM, frames=enemy.FRAMES, stride=enemy.STRIDE,
                  transparent=enemy.TRANSPARENT)
BULLET = shp.rect(3, 9, C(250, 240, 120))
STAR = shp.rect(2, 2, C(120, 150, 210))
# HUD icons: a plane per life, a bomb per bomb.
LIFE_ICON = shp.from_mask([
    "....X....",
    "....X....",
    "....X....",
    ".XXXXXXX.",
    "XXXXXXXXX",
    "....X....",
    "....X....",
    "....X....",
    "..XX.XX..",
], C(205, 215, 235))                                   # cool grey, matches the ship
BOMB_ICON = shp.from_mask([
    "XX.........",
    "XX.######..",
    "...#######.",
    "...########",
    "...#######.",
    "XX.######..",
    "XX.........",
], C(255, 175, 70))                                    # amber
# Heat-gauge segments: 3 pre-built colours, swapped per heat band.
HEAT_G = shp.rect(HEAT_SW, 3, C(80, 200, 110))      # cool
HEAT_O = shp.rect(HEAT_SW, 3, C(255, 180, 60))      # warming
HEAT_R = shp.rect(HEAT_SW, 3, C(255, 70, 50))       # hot / locked

# --- scrolling starfield (cheap endless parallax: a few wrapping dots) ---
NSTAR = 18
stars = []
for i in range(NSTAR):
    s = pg.Sprite(STAR, rng.below(W), rng.below(H))
    s.data = 2 + rng.below(3)                          # fall speed
    scene.add(s)
    stars.append(s)

# --- player ---
plane = pg.Sprite(PLANE, W // 2, H - 40)
plane.anchor = (0.5, 0.5)
scene.add(plane)

# --- fixed pools (no per-frame allocation) ---
bullets = picogame_pool.Pool(scene, BULLET, 14, anchor=(0.5, 0.5))
enemies = picogame_pool.Pool(scene, ENEMY, 8, anchor=(0.5, 0.5))
for e in enemies.items:
    e.flip_y = True                                   # raiders point DOWN (warm-ember palette = the colour half)
    e.data = {"vy": 0.0, "drift": 0.0, "dive": False}  # pre-allocate ONE dict per slot; spawn mutates in place
ps = pg.Particles(180, size=2, gravity=0.0, fade=True)
scene.add(ps)

# --- HUD (fixed top strip) ---
# HudBar labels are a buffer-less StripDraw: a label only stores its string (nothing is rasterized or
# sized at creation), so the initial text below is just a placeholder - hud_refresh() sets the real
# values. (The WIDEST-text sizing idiom is only for SceneLabel/.reserve(), which owns a retained buffer.)
hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, INK)
l_score = hud.label(terminalio.FONT, 4, 4, TEXT, "SCORE 00000")
l_chain = hud.label(terminalio.FONT, CHAIN_X, 4, C(250, 220, 120), "x99  CHAIN 999")
# Lives + bombs shown as ICON sprites: the number VISIBLE = the count (toggled in hud_refresh).
# right-anchored from W so they stay on-screen on narrow (240) and wide (320) displays
life_icons = [hud.add(pg.Sprite(LIFE_ICON, RIGHT_X + i * 12, 4)) for i in range(3)]
bomb_icons = [hud.add(pg.Sprite(BOMB_ICON, W - 44 + i * 14, 5)) for i in range(3)]   # max 3 bombs
# Gun-heat gauge: 5 segments in the gap between SCORE and the CHAIN readout (set in hud_refresh).
heat_segs = [hud.add(pg.Sprite(HEAT_G, HEAT_X0 + i * HEAT_DX, 6)) for i in range(HEAT_SEGS)]
hud.draw()

# --- centre message (title / game-over overlay) ---
msg = ui.SceneLabel(scene, pg, terminalio.FONT, 0, 0, TEXT, SKY)
# Size the banner's buffer + cache its glyphs up front, on the clean heap (the longest line we show).
msg.reserve(len("GAME OVER  99999   BEST 99999   A"))

# --- game state ---
class State:
    def __init__(self):
        self.state = "title"
        self.score = 0
        self.best = 0
        self.lives = 3
        self.bombs = 2
        self.chain = 0
        self.mult = 1
        self.t = 0
        self.inv = 0
        self.fire_cd = 0
        self.bank = 99
        self.flash_t = 0
        self.heat = 0
        self.gun_locked = False
        self.next_bomb = 10000
        self.hud_dirty = True                          # set at the discrete HUD-state mutation sites


st = State()
if _hi is not None:
    try:
        st.best = _hi.load()["hi"]
    except Exception:
        pass


def set_msg(text):
    # centre a short line roughly (terminalio glyph ~6 px wide)
    msg.set(text)
    msg.sprite.move(max(2, W // 2 - len(text) * 3), H // 2 - 4)


def clear_actors():
    """Recycle every live raider and bullet, so a fresh state never inherits the last game's."""
    enemies.free_all()
    bullets.free_all()


def show_title():
    st.state = "title"
    set_msg("PICO WING   A: START")
    clear_actors()


def new_game():
    global st
    clear_actors()                                     # drop the previous game's raiders/bullets
    best = st.best                                      # preserve the running hi-score across restarts
    st = State()
    st.best = best
    st.state = "play"
    plane.move(W // 2, H - 40)
    plane.visible = True
    plane.flash = 0
    set_msg("")


def hud_refresh():
    l_score.set("SCORE %05d" % st.score)
    if not st.chain:
        l_chain.set("")
    elif CHAIN_FULL:
        l_chain.set("x%d  CHAIN %d" % (st.mult, st.chain))
    else:                                              # narrow screen: multiplier only (fits the budget)
        l_chain.set("x%d" % st.mult)
    lv, bo = st.lives, st.bombs
    for i, s in enumerate(life_icons):                 # N icons visible = the count
        s.visible = i < lv
    for i, s in enumerate(bomb_icons):
        s.visible = i < bo
    # heat gauge: N segments filled, colour by band; full red + blink when the gun is locked
    locked = st.gun_locked
    h = st.heat
    seg = HEAT_SEGS if locked else h * HEAT_SEGS // 100
    blink = locked and ((st.t // 4) & 1)
    col = HEAT_R if (locked or h >= WARN_HEAT) else (HEAT_O if h >= WARM_HEAT else HEAT_G)
    for i, s in enumerate(heat_segs):
        vis = (i < seg) and not blink
        s.visible = vis
        if vis:
            s.bitmap = col
    hud.draw()


def player_hit():
    st.lives -= 1
    st.chain = 0
    st.mult = 1
    st.hud_dirty = True                                # lives/chain/mult changed
    st.inv = 45                                        # mercy i-frames
    plane.flash = WHITE
    st.flash_t = 3                                      # momentary flash, then just blink
    shake.add(0.6)
    sfx("hurt")
    if st.lives <= 0:
        st.state = "over"
        if st.score > st.best:
            st.best = st.score
            if _hi is not None:
                try:
                    _hi.save({"hi": st.best})
                except Exception:
                    pass
        gc.collect()                                   # defrag at the run boundary before the banner
        set_msg("GAME OVER  %05d   BEST %05d   A" % (min(st.score, 99999), min(st.best, 99999)))
        plane.visible = False


def fire_bomb():
    if st.bombs <= 0:
        return
    st.bombs -= 1
    st.hud_dirty = True                                # bombs changed
    st.heat = max(0, st.heat - 40)                     # the bomb also vents the gun (escape a lockout)
    if st.gun_locked and st.heat <= RESET_HEAT:
        st.gun_locked = False
    shake.add(0.8)                                     # a big kick - this IS the panic button
    bomb_flash.pulse()                                 # full-screen invert pulse (hardware, free)
    # Nothing at the ship (flash/particles there would read as "we got hit"); punch = invert + shake.
    for e in enemies.items:                            # screen-clear (panic button)
        if e.visible:
            ps.emit(int(e.fx), int(e.fy), 14, 4, 22, C(250, 180, 90))
            enemies.free(e)
    sfx("bomb")


def update_play():
    t = st.t = st.t + 1
    # --- input: 8-dir move + clamp; bank the ship into horizontal motion ---
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    plane.fx = max(14, min(W - 14, plane.fx + dx * 3.4))
    plane.fy = max(BAR + 14, min(H - 14, plane.fy + dy * 3.4))
    bank = (1 if dx > 0 else (-1 if dx < 0 else 0))
    if bank != st.bank:                                # only re-bake the rotation on change
        st.bank = bank
        plane.angle = (bank * 14) % 360                # bank INTO the motion (nose toward travel)
    if btn.just_pressed(btn.B):
        fire_bomb()
    if st.score >= st.next_bomb:                       # earn a bomb every 10000 pts (kept capped at 3)
        st.next_bomb += 10000
        if st.bombs < 3:
            st.bombs += 1
            st.hud_dirty = True                        # earned a bomb
            sfx("extra")
    # --- autofire on hold, gated by GUN HEAT: hold too long and it overheats + locks ---
    a_held = btn.is_pressed(btn.A)
    if st.gun_locked:                                  # locked: must RELEASE the trigger to cool down
        if not a_held:
            st.heat -= COOL_LOCKED
            if st.heat <= RESET_HEAT:
                st.heat = max(0, st.heat)
                st.gun_locked = False
                st.hud_dirty = True                    # gun unlocked
        # holding A while jammed keeps it locked -- the lesson is "let go"
    elif a_held:
        if st.fire_cd == 0:
            b = bullets.spawn()
            if b:
                b.move(int(plane.fx), int(plane.fy) - 16)
                b.data = -8.0                          # fast, snappy player shot
                sfx("shot")
            st.fire_cd = 6
            st.heat += HEAT_PER_SHOT
            if st.heat >= 100:                         # overheated -> lock the gun
                st.heat = 100
                st.gun_locked = True
                st.hud_dirty = True                    # gun locked
                sfx("jam")
        else:
            st.fire_cd -= 1
    else:                                              # not firing: cool down (faster while a chain runs)
        st.heat -= COOL_IDLE + st.chain // 3
        if st.heat < 0:
            st.heat = 0
        st.fire_cd = 0                                 # ready to fire the instant A is tapped again
    # --- spawn raiders: cadence + speed ramp, with a short lull every ~20 s (sawtooth) ---
    interval = max(11, 30 - t // 160)
    lull = (t % 600) < 54                              # ~1.8 s breather each wave
    if not lull and t % interval == 0:
        e = enemies.spawn()
        if e:
            e.flash = 0                                # clear a leftover kill-flash from recycling
            e.move(20 + rng.below(W - 40), -16)
            speed = 1.5 + t / 1500.0
            diver = rng.chance(min(0.55, 0.15 + t / 4000.0))
            d = e.data                                 # pre-allocated dict - mutate in place (no per-spawn alloc)
            d["vy"] = speed
            d["drift"] = (rng.below(5) - 2) * 0.4
            d["dive"] = diver
    # --- bullets ---
    for b in bullets.items:
        if not b.visible:
            continue
        b.fy += b.data
        if b.fy < -10:
            bullets.free(b)
    # --- raiders ---
    inv = st.inv
    for e in enemies.items:
        if not e.visible:
            continue
        if e.data["dive"]:                             # divers bank toward the player (teeth)
            e.data["drift"] += 0.08 if plane.fx > e.fx else -0.08
            e.data["drift"] = max(-2.4, min(2.4, e.data["drift"]))
        e.fx += e.data["drift"]
        if e.fx < 14:                                  # bounce off the edges: a raider that flies off-screen
            e.fx = 14                                  # is unreachable (player is clamped on-screen too) ->
            e.data["drift"] = -e.data["drift"]         # an unavoidable, unfair chain break
        elif e.fx > W - 14:
            e.fx = W - 14
            e.data["drift"] = -e.data["drift"]
        e.fy += e.data["vy"]
        if e.fy > H + 16:                              # slipped past -> chain breaks (no life lost)
            enemies.free(e)
            st.chain = 0
            st.mult = 1
            st.hud_dirty = True                        # chain/mult reset
            continue
        if inv == 0 and e.near(plane, HIT_R):   # forgiving body hitbox (< the 32px sprite)
            enemies.free(e)
            ps.emit(int(plane.fx), int(plane.fy), 18, 5, 26, C(255, 120, 90))
            player_hit()
            return
        for b in bullets.items:
            if b.visible and b.near(e, SHOT_R):
                bullets.free(b)
                enemies.free(e)
                st.chain += 1
                st.mult = 1 + st.chain // 5
                st.score += 50 * st.mult
                st.hud_dirty = True                    # score/chain/mult changed
                ps.emit(int(e.fx), int(e.fy), 20, 5, 26, C(255, 210, 120))  # brighter, punchier kill burst
                sfx("kill")
                break
    if st.inv > 0:
        st.inv -= 1
        plane.visible = (st.inv // 3) % 2 == 0         # blink while invulnerable
    else:
        plane.visible = True


def title_splash():
    """Full-screen PixelLab intro art, streamed from flash (~0 heap), shown once before the start
    menu. Blocks until A; auto-advances on the desktop sim (no `_host` on device). Skipped if
    unavailable."""
    def _has(_m):
        try:
            __import__(_m); return True
        except ImportError:
            return False
    # Auto-advance the splash ONLY in headless runs (the smoke harness / the desktop sim's
    # --frames + screenshot runs, where no one can press A). The browser playground (has `bridge`)
    # and the device WAIT for A, like a real title screen.
    hold = 90 if (_has("smoke") or (_has("_host") and not _has("bridge"))) else 0
    try:
        try:
            here = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
        except NameError:
            here = "."      # the WASM playground execs the game without __file__; assets sit in cwd (/p)
        pal = cut.palette(pg, __import__("picowing_title_pal"))
        cut.play(pg, scene.display, bufA, btn, here + "/picowing_title.dat",
                 pal=pal, w=160, h=120, caption="A: start", auto_hold=hold, clock=clock)
        scene.invalidate()
    except Exception:
        pass


# --- main loop -------------------------------------------------------------
title_splash()                                         # the single full-screen intro (waits A)
new_game()                                             # -> straight into play, no second title screen
hud_refresh()
print("Pico Wing - D-pad move, hold A fire, B bomb. A to start.")


def main():
    # --- per-frame loop in a FUNCTION (not module scope): names become array-indexed locals,
    # not globals-dict lookups (measured on-device win; picogame-game-design hot-loop style guide).
    last_heat_band = -1                                    # int shadows (Menu idiom: two ints, not a tuple)
    last_blink = -1
    while True:
        btn.poll()
        # starfield scrolls in every state (motion behind the menus too)
        for s in stars:
            s.fy += s.data
            if s.fy > H:
                s.fy = -2
                s.fx = rng.below(W)
        if st.state == "title":
            if btn.just_pressed(btn.A):
                new_game()
        elif st.state == "play":
            update_play()
        elif st.state == "over":
            if btn.just_pressed(btn.A):                    # INSTANT restart, re-init in place
                new_game()
        if st.flash_t > 0:                                 # momentary player flash -> clear after a few frames
            st.flash_t -= 1
            if st.flash_t == 0:
                plane.flash = 0
        ps.tick()
        shake.tick()                                       # decaying screen-shake on top of the view
        bomb_flash.tick()                                  # restore the panel after the bomb's invert pulse
        # Discrete HUD state (score/chain/mult/lives/bombs/lock) sets st.hud_dirty at its mutation sites;
        # the animated heat gauge (band + locked-blink) is tracked by two int shadows - no per-frame tuple.
        hb = st.heat // 20
        blink = (st.t // 4 & 1) if st.gun_locked else 0
        if st.hud_dirty or hb != last_heat_band or blink != last_blink:
            last_heat_band = hb
            last_blink = blink
            st.hud_dirty = False
            hud_refresh()
        sfx_tick()
        scene.refresh()
        clock.tick()


main()
