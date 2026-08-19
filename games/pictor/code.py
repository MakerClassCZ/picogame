# Pictor - MEADOW (level 1), 320x240 PicoPad. A faithful slice of PicoLibSDK's "Pictor"
# (Miroslav Nemecek). You play Jill (a walker who jumps with gravity) OR transform into the
# Bird (a free flyer) - B/X switches form. Shoot bugs (fly/wasp/hornet) that sweep in from
# the right with different flight patterns and shoot back. Collect the floating PicoPad part
# for bonus points. Survive the meadow (a timed level) on a health bar.
#
# Controls: arrows move (UP = jump as Jill / fly up as Bird), A = shoot, B/X = transform.
# Copy pic_*.mpy + jill.bin + the picogame_* helpers to CIRCUITPY.
#
# Art reused from PicoLibSDK via tools/picolib_img.py (see THIRD_PARTY.md). The engine is
# original. Validated in the simulator.

import gc
import time
import random

import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_rand
import picogame_shapes as shp
from picogame_pool import Pool

import pic_meadow
import pic_meadow3
import pic_strips
import pic_jill
import pic_bird
import pic_fly
import pic_wasp
import pic_hornet
import pic_shuriken
import pic_seed
import pic_bullet
import pic_explosion

# Background FILL = the meadow's OWN sky colour (sampled), so the thin sky band left above the ground
# layer (which is pushed down to cover the foreground seam) is seamless with the meadow's painted sky.
SKY = pg.rgb565(49, 133, 164)
BAR_BG = pg.rgb565(18, 26, 50)
WHITE = pg.rgb565(255, 255, 255)
W, H = picogame_game.screen()
BAR_TOP = 20                                   # reserved HUD strip: SCORE + MAX best (top)
BAR_BOT = 20                                   # reserved HUD strip: LIFE / LOAD / TIME gauges (bottom)
scene, bufA, bufB = picogame_game.setup(background=SKY, strip_h=6, top=BAR_TOP, bottom=BAR_BOT)  # 6 = less RAM + faster on DMA
btn = picogame_input.Buttons()

# --- frame-rate rebase (the original PicoLibSDK Pictor runs its game loop at ~12 FPS: GAMELEN 700
# frames == "~1 minute"). Every original constant is per-frame-at-12-FPS, so we express speeds as
# original_px_per_frame * SPEED_SCALE and durations as original_frames / SPEED_SCALE. Change FPS in
# one place and the whole game keeps the ORIGINAL wall-clock feel (a slow, floaty, dense level). ---
FPS = 30
SPEED_SCALE = 12.0 / FPS                        # original px/frame -> our px/frame (0.4 @30 FPS)
ANIM_DIV = max(1, int(FPS / 12 + 0.5))          # frames per animation step (~12 Hz cadence @ any FPS)
clock = picogame_clock.Clock(FPS)


def dur(frames):
    return int(round(frames / SPEED_SCALE))     # original frame-count -> our frame-count

# play band the actors/enemies live in
TOP = BAR_TOP + 4
BOTTOM = H - BAR_BOT - 4
GROUND = H - BAR_BOT - 6                        # Jill's feet rest here (centre = GROUND - h/2)
WALK_REST_Y = GROUND - 50                       # Jill's centre-Y when standing on the ground

# Jump physics (original ACT_JUMPSPEED=10 px/frame, gravity 1 px/frame^2 -> ~55 px high, ~1.67 s
# airtime). Velocity scales by SPEED_SCALE, acceleration by SPEED_SCALE^2, so the real-world
# trajectory (height + airtime in seconds) is preserved at any FPS.
JUMP_V = 10.0 * SPEED_SCALE
GRAVITY = 1.0 * SPEED_SCALE * SPEED_SCALE
LEVEL_FRAMES = dur(700)                         # original GAMELEN 700 @12 FPS ~= 58 s meadow, then loop
BANNER_LEN = 80                                 # frames the clear/game-over banner holds (frozen scene)
# Damage per hit (bullet OR body contact), out of 100 HP: original ACT_HIT_WALK 3 / ACT_HIT_FLY 6.
# There are NO i-frames in the original - every hit lands (each bullet/enemy is removed on contact so
# it hits once). The Bird takes DOUBLE damage: agile but fragile -> the transform is a real trade-off.
HIT_WALK = 3
HIT_FLY = 6
HIT_FLASH = 5                                   # cosmetic only: brief white blink + blood splat (BLOOD_TIME 5)
POPUP_FRAMES = FPS // 2                          # a floating score popup lives ~0.5 s (original 6 frames @12)
POPUP_RISE = 2 * SPEED_SCALE                     # rises 2 px/frame (scaled)


rng = picogame_rand.Rand(0x1234)


# --- parallax meadow (back -> front), faithful to the original (BG_SPEED ratio 1:2:3) ---
# PARALLAX_MID adds the middle layer (meadow2 = half-res 320x32 @2x, ~10.8 KB). Measured on real
# hardware 2026-07-05: even half-res, the 3rd layer overflows the RP2040 heap (MemoryError on the
# Bird stream buffer after the 3 backgrounds load) -> FALSE on a plain RP2040 (2-layer, fits).
# --- parallax layers ---------------------------------------------------------------------------
# Each background is a stack of small row-strip files (assets/<name>_NN.bin). With
# picogame.xip_map the strips blit straight out of flash and cost NO RAM, which is the only reason
# the middle layer can be the ORIGINAL 640x64 art (40 KB) on an RP2040. Without it (older
# firmware, the simulator, the web playground) the strips are read into RAM instead - ground plus
# foreground fit, the middle layer does not, so it is dropped and the seam below fills its band.
PARALLAX_MID = pic_strips.XIP or getattr(gc, "mem_free", lambda: 9_999_999)() > 200_000
gnd_strips = pic_strips.strips(pg, "meadow", pic_meadow.STRIDE, pic_meadow.H, 16,
                               pic_meadow.PAL, pic_meadow.TRANSP)    # 320x80 drawn 2x -> 640x160, covers y20..180
fore_strips = pic_strips.strips(pg, "meadow3", pic_meadow3.STRIDE, pic_meadow3.H, 8,
                                pic_meadow3.PAL, pic_meadow3.TRANSP)  # 640x40 white-transparent; rows 0-7 = grass fringe
if PARALLAX_MID:
    try:
        import pic_meadow2f as pic_meadow2                            # the original hedge + flowers
        mid_strips = pic_strips.strips(pg, "meadow2", pic_meadow2.STRIDE, pic_meadow2.H, 8,
                                       pic_meadow2.PAL, pic_meadow2.TRANSP)
    except MemoryError:
        PARALLAX_MID = False
# SEAM (2-layer form): a ZERO-COPY Bitmap over the ground art's own bottom 4 rows (76-79 = the near
# tan path/soil), scrolled at ground speed through the 8-px band the foreground's transparent grass
# fringe would otherwise leave showing the static fill. Rows 76-79 live in the last ground strip.
if not PARALLAX_MID:
    _last_top, _last_bm, _last_buf = gnd_strips[-1]
    seam_bm = pg.Bitmap(memoryview(_last_buf)[(76 - _last_top) * pic_meadow.STRIDE:], 320, 4,
                        format=pg.PAL8, palette=pic_meadow.PAL, stride=pic_meadow.STRIDE)
# each layer: (strips, scale, wrap_width, top_y, speed, phase). Speeds 1:2:3 * SPEED_SCALE; phase is
# an initial horizontal offset (the seam is shifted so its copy of the ground's bottom rows doesn't
# mirror the rows the ground shows just above it).
LAYERS = [(gnd_strips, 2, 640, BAR_TOP, 1 * SPEED_SCALE, 0)]
if PARALLAX_MID:
    # Placement follows the original: BG2_Y = BG_Y + BG_HEIGHT - 70 = 110, plus the 16-line
    # correction for the 64-line meadow art -> 126.
    LAYERS.append((mid_strips, 1, 640, 126, 2 * SPEED_SCALE, 0))
else:
    LAYERS.append(([(0, seam_bm, None)], 2, 640, H - 60, 1 * SPEED_SCALE, 320))
LAYERS.append((fore_strips, 1, 640, H - 60, 3 * SPEED_SCALE, 0))      # foreground hugs the bottom
bg_layers = []
for _strips, _sc, _w, _y, _spd, _ph in LAYERS:
    _pair = []
    for _top, _bm, _buf in _strips:
        _a = pg.Sprite(_bm, -_ph, _y + _top * _sc)
        _b = pg.Sprite(_bm, _w - _ph, _y + _top * _sc)
        _a.scale = _sc
        _b.scale = _sc
        _pair.append(_a)
        _pair.append(_b)
    scene.add_all(_pair)
    # [strips (a0,b0,a1,b1,...), wrap width, speed, float offset, last integer x] - the scroll keeps
    # ONE float per layer and writes the strips' integer x only when it changes: the ground moves
    # 0.4 px/frame, so its sprites are touched on 2 frames in 5 (no dirty rects on the other 3),
    # and each write is the Sprite.x int fast path (no per-sprite float get/set/round).
    bg_layers.append([_pair, _w, _spd, float(-_ph), -_ph])

# --- enemies: one reusable pool; each entry swaps to its type's bitmap + flight pattern ---
# pattern: 0 = straight (fly), 1 = sine wobble (wasp), 2 = big sine + vertical drift (hornet)
# original ENEMY_SPEED 3 / ENEMY_SLOWSPEED 1 px/frame, scaled. Types differ by flight PATTERN, not speed.
ENEMY_SPEED = 3 * SPEED_SCALE                   # 1.2 px/frame @30 FPS
ENEMY_SLOW = 1 * SPEED_SCALE                    # 0.4 px/frame (the gentle up/down drift)
ENEMY_TYPES = [
    {"bm": pic_fly.bitmap(pg), "score": 10, "r": 18},
    {"bm": pic_wasp.bitmap(pg), "score": 20, "r": 20},
    {"bm": pic_hornet.bitmap(pg), "score": 50, "r": 24},
]
# original ENEMY_MAX 20 concurrent; trimmed to 14 to fit the RP2040 heap (each pool slot = a Sprite +
# its state dict). Still a dense swarm. RP2350 has room for 20.
MAX_ENEMIES = 10                                # 3-layer parallax costs ~4 KB heap; trimmed so the peak
                                                # concurrent-sprite Scene arrays still fit. Still a swarm.
ENEMY_FIRE_P = int(1200 * SPEED_SCALE)          # per-frame fire chance /65536 (original ENEMY_GEN_BUL 1200)

# Flight = piecewise-linear segment templates (original enemy.cpp Moves[]). Each segment is
# (steps, dx, dy): steps in OUR frames (original count / SPEED_SCALE), dx/dy already scaled px/frame,
# steps==0 = endless final segment. An enemy walks its segments; hitting the band edge ends the
# current segment (and flips the endless slow-up <-> slow-down drifters).
_E = ENEMY_SPEED
_S = ENEMY_SLOW


def _seg(steps, dx, dy):
    return (int(round(steps / SPEED_SCALE)) if steps else 0, dx, dy)


MOVES = [
    [_seg(0, -_E, 0)],                                                                # 0 straight left
    [_seg(0, -_E, -_S)],                                                              # 1 left + slow up
    [_seg(0, -_E, _S)],                                                               # 2 left + slow down
    [_seg(20, -_E, 0), _seg(30, -_E, _E), _seg(5, -_E, 0), _seg(10, -_E, -_E), _seg(0, -_E, 0)],   # 3 dip down
    [_seg(20, -_E, 0), _seg(30, -_E, -_E), _seg(5, -_E, 0), _seg(10, -_E, _E), _seg(0, -_E, 0)],   # 4 rise up
    [_seg(10, -_E, 0), _seg(10, -_E, -_E), _seg(5, -_E, 0), _seg(20, -_E, _E), _seg(5, -_E, 0),
     _seg(20, -_E, -_E), _seg(5, -_E, 0), _seg(10, -_E, _E), _seg(0, -_E, 0)],        # 5 saw
    [_seg(10, -_E, 0), _seg(10, -_E, _E), _seg(5, -_E, 0), _seg(20, -_E, -_E), _seg(5, -_E, 0),
     _seg(20, -_E, _E), _seg(5, -_E, 0), _seg(10, -_E, -_E), _seg(0, -_E, 0)],        # 6 saw (inverted)
    [_seg(40, -_E, 0), _seg(20, 0, -_E), _seg(0, -_E, 0)],                            # 7 climb
    [_seg(40, -_E, 0), _seg(20, 0, _E), _seg(0, -_E, 0)],                             # 8 dive
]
MOVE_POOL = (3, 5, 9)                            # fly picks templates 0..2, wasp 0..4, hornet 0..8
# each live enemy carries its per-entity state on spr.data = {"x","y","mv","seg","step","t"}
enemies = Pool(scene, ENEMY_TYPES[0]["bm"], MAX_ENEMIES, anchor=(0.5, 0.5))
# pre-allocate each slot's state dict ONCE - spawn_enemy() mutates it in place (no per-spawn dict).
for _e in enemies.items:
    _e.data = {"x": 0.0, "y": 0.0, "mv": 0, "seg": 0, "step": 0, "t": ENEMY_TYPES[0]}

# --- player projectiles (shuriken / seed): one pool, each shot carries (vx, vy, frames) ---
shuri_bm = pic_shuriken.bitmap(pg)
seed_bm = pic_seed.bitmap(pg)
MAX_SHOTS = 6                                   # reload x TTL math: Bird ~4, Jill's 3-way <=6 concurrent
SHOT_HITS = 10                                  # original missile "hits": one shot pierces up to 10 enemies
shots = Pool(scene, shuri_bm, MAX_SHOTS, anchor=(0.5, 0.5))
# pre-allocate each shot slot's state dict ONCE - fire() mutates it (no per-shot tuple).
for _s in shots.items:
    _s.data = {"vx": 0, "vy": 0, "nf": 1, "hits": 1, "spin": 0, "a": 0}
SPIN_STEP = 40                                  # deg/frame runtime rotation (0-RAM; replaces baked frames)

# --- enemy bullets ---
bullet_bm = pic_bullet.bitmap(pg)
BULLET_SPEED = 5 * SPEED_SCALE                  # original BULLET_SPEED 5 px/frame, scaled (2.0 @30 FPS)
MAX_BULLETS = 10                                # trimmed for RP2040 heap (10 enemies firing) (orig BULLET_MAX 30)
bullets = Pool(scene, bullet_bm, MAX_BULLETS, anchor=(0.5, 0.5))

# --- explosions: small pool, 8-frame burst; spr.data = elapsed frame counter ---
EXP_FRAMES = pic_explosion.FRAMES
EXP_LIFE = EXP_FRAMES * ANIM_DIV                 # total frames a boom lives
booms = Pool(scene, pic_explosion.bitmap(pg), 3, anchor=(0.5, 0.5))

# --- blood splat: a small red stipple at the player's hit point for HIT_FLASH frames (original DispBlood) ---
blood = pg.Sprite(shp.circle(9, pg.rgb565(200, 30, 30)), 0, 0)
blood.anchor = (0.5, 0.5)
blood.dither = 5                               # a bit see-through so it reads as a splat, not a dot
blood.visible = False
scene.add(blood)

# (bonus removed: the collectible PicoPad-part only pays off across the original's 12 worlds; in this
# single-level slice it was a pointless +200. Frees its asset + a scene item -> RAM for a crisp mid layer.)

# --- player + the two actor forms (Jill = walk, Bird = fly) ---
# Player sheets: mapped 0-copy from XIP flash when the .bin is contiguous on CIRCUITPY (11 Bitmaps
# over slices of one memoryview - frame swap = pointer swap, 0 reads, no frame buffer in RAM), else
# StreamSheet (one frame in RAM, re-read from flash on each animation step).
jill_sheet = pic_strips.sheet(pg, pic_jill.BIN, pic_jill.W, pic_jill.H, pic_jill.FRAMES, pic_jill.PAL, pic_jill.TRANSP)
bird_sheet = pic_strips.sheet(pg, pic_bird.BIN, pic_bird.W, pic_bird.H, pic_bird.FRAMES, pic_bird.PAL, pic_bird.TRANSP)
# kind 'walk': gravity + jump, streamed frames; kind 'fly': free movement, 4-frame in-RAM sheet
# reloads: original Jill 30 / Bird 6 frames @12 FPS (2.5 s vs 0.5 s) -> Jill = a slow deliberate
# 3-way volley, Bird = a fast bullet hose. shot_speed = original MISSILE_SPEED 10 px/frame, scaled.
SHOT_SPEED = 10 * SPEED_SCALE                   # 4.0 px/frame @30 FPS (both forms)
SHOT_SPREAD_VY = 4 * SPEED_SCALE                # Jill's 3-way vertical spread (original dy=+-4)
ACTORS = [
    {"name": "JILL", "kind": "walk", "r": 22, "reload": dur(30), "spread": True, "shot_bm": shuri_bm,
     "shot_frames": pic_shuriken.FRAMES, "shot_speed": SHOT_SPEED},
    {"name": "BIRD", "kind": "fly", "r": 24, "reload": dur(6), "spread": False, "shot_bm": seed_bm,
     "shot_frames": 1, "shot_speed": SHOT_SPEED},
]
# ground shadow under Jill: a grounding cue at a FIXED y regardless of jump height (original ACT_SHADOWY).
# Faithful to the original PicoLibSDK (DrawBlit1Shadow of a flat 32x7 oval that DARKENS the background):
# a flat ellipse mask drawn with the engine's native `shadow` blit effect (picogame_darken halves the
# background RGB) -> a true translucent shadow that works on ANY ground (tan or grass), unlike a fixed
# colour, and with none of the stipple-checkerboard a dithered disc shows on the ST7789 panel.
SHADOW_Y = H - 30
def _ellipse_bm(w, h):
    data = bytearray(w * h)
    rx = (w - 1) / 2.0
    ry = (h - 1) / 2.0
    for _y in range(h):
        for _x in range(w):
            if ((_x - rx) / rx) ** 2 + ((_y - ry) / ry) ** 2 <= 1.0:
                data[_y * w + _x] = 1
    return shp._bm(data, w, h, pg.rgb565(0, 0, 0))   # colour irrelevant: shadow mode darkens the dest
shadow = pg.Sprite(_ellipse_bm(30, 7), 0, SHADOW_Y)
shadow.anchor = (0.5, 0.5)
shadow.shadow = True                           # native darken-the-background effect (like DrawBlit1Shadow)
shadow.visible = False
scene.add(shadow)

player = pg.Sprite(jill_sheet.bitmap, 60, WALK_REST_Y)
player.anchor = (0.5, 0.5)
scene.add(player)


def set_actor(i):
    _snd.sfx(SND_MORPH, priority=25, window=6)
    st.act = i % len(ACTORS)
    st.last_jf = -1                             # form changed -> force a re-stream on the next frame
    if ACTORS[st.act]["kind"] == "fly":
        player.bitmap = bird_sheet.use(0)
        st.on_ground = False
    else:
        # Bird -> Jill keeps the current height and FALLS under gravity (no teleport to the ground);
        # only counts as grounded if she is already at/below the rest line.
        st.pvy = 0.0
        st.on_ground = st.py >= WALK_REST_Y
        player.bitmap = jill_sheet.use(10)


# --- HUD (styled after the original): top = SCORE + MAX best, bottom = LIFE / LOAD / TIME gauges ---
gc.collect()
MAX_HP = 100
SCORE_HI = pg.rgb565(90, 230, 110)             # SCORE turns green while it beats the stored best
MAX_COL = pg.rgb565(150, 170, 210)
FRAME_LINE = pg.rgb565(120, 170, 230)          # light-blue band frame edge (facing the play area)
TRACK = pg.rgb565(40, 50, 70)
GREEN = pg.rgb565(70, 220, 110)
RED = pg.rgb565(230, 90, 70)
AMBER = pg.rgb565(240, 180, 70)
FONT = terminalio.FONT

# persistent best score (NVM). Absent/!available on the sim -> just start at 0.
import picogame_save
try:
    _save = picogame_save.Save("pictor", {"best": ("I", 0)})
    max_score = _save.load()["best"]
except Exception:
    _save = None
    max_score = 0

BAR_H = 8
BAR_Y = H - BAR_BOT + 7
LIFE_W, LOAD_W, TIME_W = 70, 30, 70
LIFE_X, LOAD_X, TIME_X = 32, 138, 204

# The HUD is TWO buffer-less StripDraw bands (no picogame_ui, no retained gauge Bitmaps, no per-change
# alloc): each callback composites bg + frame line + gauges + text straight into the live strip via
# view.fill_rect / view.text. `hud` holds the values the callbacks read (updated only on a change).
hud = {"score": 0, "max": 0, "score_col": WHITE,
       "life": LIFE_W, "life_col": GREEN, "load": 1, "load_col": AMBER, "time": 1}


# StripDraw contract: (vx, vy) = the render region's origin -> draw at screen coords minus both.
def _draw_top(view, vx, vy, vw, vh):
    view.clear(BAR_BG)
    view.fill_rect(0 - vx, BAR_TOP - 1 - vy, W, 1, FRAME_LINE)
    view.text(6 - vx, 6 - vy, "SCORE %07d" % hud["score"], hud["score_col"], FONT)
    view.text(W - 86 - vx, 6 - vy, "MAX %07d" % hud["max"], MAX_COL, FONT)


def _draw_bot(view, vx, vy, vw, vh):
    view.clear(BAR_BG)
    view.fill_rect(0 - vx, (H - BAR_BOT) - vy, W, 1, FRAME_LINE)
    y = BAR_Y - vy
    view.text(LIFE_X - 28 - vx, y - 1, "LIFE", WHITE, FONT)
    view.fill_rect(LIFE_X - vx, y, LIFE_W, BAR_H, TRACK)
    view.fill_rect(LIFE_X - vx, y, hud["life"], BAR_H, hud["life_col"])
    view.text(LOAD_X - 28 - vx, y - 1, "LOAD", WHITE, FONT)
    view.fill_rect(LOAD_X - vx, y, LOAD_W, BAR_H, TRACK)
    view.fill_rect(LOAD_X - vx, y, hud["load"], BAR_H, hud["load_col"])
    view.text(TIME_X - 28 - vx, y - 1, "TIME", WHITE, FONT)
    view.fill_rect(TIME_X - vx, y, TIME_W, BAR_H, TRACK)
    view.fill_rect(TIME_X - vx, y, hud["time"], BAR_H, GREEN)


top_sd = pg.StripDraw(_draw_top, 0, 0, W, BAR_TOP)
bot_sd = pg.StripDraw(_draw_bot, 0, H - BAR_BOT, W, BAR_BOT)


def draw_top():
    pg.render(scene.display, [top_sd], bufA, 0, 0, W, BAR_TOP, background=BAR_BG)


def draw_bot():
    pg.render(scene.display, [bot_sd], bufA, 0, H - BAR_BOT, W, H, background=BAR_BG)


def draw_gauges():
    # per-frame gauge changes (the LOAD bar moves 2 px/frame while the Bird reloads): re-render
    # only the 8-row gauge band, not the whole 20-row bar (the labels above it don't change)
    pg.render(scene.display, [bot_sd], bufA, 0, BAR_Y, W, BAR_Y + BAR_H, background=BAR_BG)

# --- floating score popups: small moving text sprites. DIGIT-ONLY cache -> only glyphs {0,1,2,5}
# enter the Python glyph cache (picogame_font._MASKS); the banner letters never do (see below). ---
import picogame_font as pgfont

TEXT_CACHE = {}
for _s in ("10", "20", "50", "200"):            # plain azure value, no "+" (original PointDisp)
    TEXT_CACHE[_s], _, _ = pgfont.render_text(pg, terminalio.FONT, _s, pg.rgb565(120, 200, 255), None)

POPUPS = 3
# placeholder bitmap, swapped on show; spr.data = elapsed frame counter
popups = Pool(scene, TEXT_CACHE["10"], POPUPS, anchor=(0.5, 0.5))   # placeholder; swapped to the value on show

# centred banner ("MEADOW CLEAR!" / "GAME OVER") - drawn by a 0-RAM StripDraw through the C font path
# (view.text) only while shown, so its LETTER glyphs NEVER enter the Python glyph cache (_MASKS).
def _draw_banner(view, vx, vy, vw, vh):
    view.clear(BAR_BG)
    view.text(st.banner_x, (H // 2 - 6) - vy, st.banner_msg, WHITE, FONT)


banner_sd = pg.StripDraw(_draw_banner, 0, H // 2 - 10, W, 20)


def draw_banner():
    pg.render(scene.display, [banner_sd], bufA, 0, H // 2 - 10, W, H // 2 + 10, background=BAR_BG)

class State:
    def __init__(self):
        self.act = 0
        self.px = 60.0
        self.py = float(WALK_REST_Y)
        self.pvy = 0.0
        self.on_ground = True
        self.score = 0
        self.hp = MAX_HP
        self.fire_cd = 0
        self.hitflash = 0                       # cosmetic hit-blink timer (does NOT gate damage)
        self.blood_t = 0                        # blood-splat display timer
        self.level_t = LEVEL_FRAMES
        self.banner = 0                         # >0 = showing "MEADOW CLEAR"
        self.banner_msg = ""                    # banner text + its centred x (were module globals)
        self.banner_x = 0
        self.frame = 0
        self.last_jf = -1                       # last streamed player frame index (re-stream only on change)
        self.last_score = -1                    # HUD change-tracking (redraw a bar only when it changes)
        self.last_max = -1
        self.last_life_px = -1
        self.last_load_px = -1
        self.last_time_px = -1


st = State()

# --- sound: synthio SFX, one voice, no assets ---------------------------------------------------
# The original PicoLibSDK Pictor plays ADPCM samples (gun/throw, enemyhit, glass, fail, bigbonus);
# those would be tens of KB on top of 90 KB of art, so the same EVENTS are synthesised instead.
# picogame_synth is silent-by-design when audio is unavailable (no synthio, no pin, tight heap) -
# `available` says which, and PICOGAME_DEBUG=1 prints the reason rather than swallowing it.
import picogame_synth as snd

_snd = snd.Synth(sfx_level=0.75, buffer_size=1024)   # small buffer: latency is fine, RAM is not
if _snd.available:
    _SQ, _TR, _SI = snd.SQUARE, snd.TRIANGLE, snd.SINE
    SND_THROW = snd.note(84, _SQ, decay=0.035, amplitude=0.30, bend=snd.pitch_bend(-9, 45))
    SND_SEED = snd.note(96, _SQ, decay=0.020, amplitude=0.22, bend=snd.pitch_bend(-5, 25))
    SND_HIT = snd.note(72, _TR, decay=0.045, amplitude=0.45, bend=snd.pitch_bend(-7, 60))
    SND_BOOM = snd.note(40, _TR, decay=0.20, amplitude=0.55, attack=0.004,
                        bend=snd.pitch_bend(-5, 220))
    SND_HURT = snd.note(52, _TR, decay=0.14, amplitude=0.60, bend=snd.pitch_bend(-6, 160))
    SND_MORPH = snd.note(64, _SI, decay=0.10, amplitude=0.45, bend=snd.pitch_bend(9, 110))
    SEQ_CLEAR = ((0, snd.note(69, _TR, decay=0.06, amplitude=0.5)), (3, snd.note(73, _TR, decay=0.06, amplitude=0.5)),
                 (6, snd.note(76, _TR, decay=0.06, amplitude=0.5)), (9, snd.note(81, _TR, decay=0.22, amplitude=0.55)))
    SEQ_OVER = ((0, snd.note(57, _TR, decay=0.08, amplitude=0.55)), (4, snd.note(50, _TR, decay=0.08, amplitude=0.55)),
                (9, snd.note(43, _TR, decay=0.30, amplitude=0.5, bend=snd.pitch_bend(-4, 320))))
else:
    SND_THROW = SND_SEED = SND_HIT = SND_BOOM = SND_HURT = SND_MORPH = None
    SEQ_CLEAR = SEQ_OVER = ()



def fire():
    a = ACTORS[st.act]
    x = player.x + 24                               # spawn 24px ahead of the player
    y = player.y
    vs = (-SHOT_SPREAD_VY, 0, SHOT_SPREAD_VY) if a["spread"] else (0,)
    for vy in vs:
        s = shots.spawn()
        if s:
            s.bitmap = a["shot_bm"]
            d = s.data                                  # pre-allocated dict - mutate in place
            d["vx"] = a["shot_speed"]
            d["vy"] = vy
            d["nf"] = a["shot_frames"]
            d["hits"] = SHOT_HITS                    # piercing charge (original missiles kill up to 10)
            d["spin"] = 1 if a["shot_bm"] is shuri_bm else 0   # shuriken spins (angle); seed doesn't
            d["a"] = 0
            s.angle = 0
            s.frame = 0
            s.move(int(x), int(y))
    _snd.sfx(SND_THROW if a["spread"] else SND_SEED)


def enemy_fire(e):
    s = bullets.spawn()
    if s:
        s.move(int(e.data["x"]) - 20, int(e.data["y"]))   # spawn 20px ahead of the enemy (toward the player)


def boom(x, y):
    _snd.sfx(SND_BOOM, priority=20, window=6)    # outranks shot spam for a few frames
    b = booms.spawn()
    if b:
        b.data = 0
        b.frame = 0
        b.scale = 0.8                            # runtime scale-ramp gives the 2-frame burst expansion punch
        b.move(int(x), int(y))


def popup(x, y, n):
    bmp = TEXT_CACHE["%d" % n]                           # pre-rendered at startup - no per-kill alloc
    p = popups.spawn()
    if p:
        p.bitmap = bmp
        p.move(int(x), int(y))
        p.data = 0


def spawn_enemy():
    e = enemies.spawn()
    if not e:
        return
    # type composition ramp (original enemy.cpp): hornet share = 0 until half-level then -> ~100% at
    # the end (an end-of-level hornet storm); wasp share ramps 0 -> ~76%; the rest are flies.
    elapsed = LEVEL_FRAMES - st.level_t
    gen_hornet = (2 * elapsed - LEVEL_FRAMES) * 65536 // LEVEL_FRAMES   # <=0 in the first half
    gen_wasp = elapsed * 50000 // LEVEL_FRAMES
    r = rng.below(65536)
    if r < gen_hornet:
        ti = 2                                          # hornet
    elif r < gen_wasp:
        ti = 1                                          # wasp
    else:
        ti = 0                                          # fly
    t = ENEMY_TYPES[ti]
    d = e.data                                          # pre-allocated dict - mutate in place
    d["x"] = float(W + 30)
    d["y"] = float(TOP + t["r"] + rng.below(max(1, BOTTOM - TOP - 2 * t["r"])))
    d["mv"] = rng.below(MOVE_POOL[ti])                  # pick a flight template from this type's pool
    d["seg"] = 0
    d["step"] = 0
    d["fr"] = -1                                        # last wing-flap frame written to the sprite
    d["t"] = t
    e.bitmap = t["bm"]


def damage():
    # form-based damage, no i-frames (each bullet/enemy is removed on contact so it hits exactly once)
    st.hp -= HIT_WALK if ACTORS[st.act]["kind"] == "walk" else HIT_FLY
    if st.hp < 0:
        st.hp = 0
    _snd.sfx(SND_HURT, priority=30, window=8)    # the player's own damage always cuts through
    st.hitflash = HIT_FLASH
    st.blood_t = HIT_FLASH
    blood.move(int(player.x), int(player.y))
    blood.visible = True


def reset_level():
    st.score = 0
    st.hp = MAX_HP
    st.level_t = LEVEL_FRAMES
    rng.seed(0x1234)
    enemies.free_all()
    shots.free_all()
    bullets.free_all()
    booms.free_all()
    popups.free_all()


print("Pictor MEADOW. Arrows move/jump, A shoot, B/X transform.")
set_actor(0)
draw_top()
draw_bot()



def main():
    global max_score   # persisted best (module-level try/except init) — stays module-global per the
    #                    skill's rule for cross-run values; banner_msg/banner_x moved into State.
    # --- per-frame loop in a FUNCTION: names become array-indexed locals, not globals-dict
    # lookups (measured on-device win; picogame-game-design hot-loop style guide).
    while True:
        st.frame += 1
        btn.poll()
        # --- level-clear / game-over pause: the banner is drawn ONCE over a FROZEN scene (the scene is not
        # refreshed while it holds), so there's a single push and NO flicker. On the last frame it invalidates
        # so the next refresh repaints cleanly. ---
        if st.banner > 0:
            if st.banner == BANNER_LEN:
                draw_banner()
            st.banner -= 1
            if st.banner == 0:
                scene.invalidate()
                reset_level()
                set_actor(st.act)
            _snd.tick()
            clock.tick()
            continue

        # --- transform (B or X) - BEFORE reading `a`, so the new form takes effect this frame ---
        if btn.just_pressed(btn.B) or btn.just_pressed(btn.X):
            set_actor(st.act + 1)
            st.fire_cd = ACTORS[st.act]["reload"]   # new form starts fully unloaded (no transform-fire exploit)
        a = ACTORS[st.act]

        # --- movement: walk (gravity+jump) vs fly (free) ---
        dx = (btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)) * 4   # True/False = 1/0 -> -1, 0, or +1
        st.px = min(W - 20, max(35, st.px + dx))       # original ACT_MINX/MAXX: Jill can reach the right edge
        if a["kind"] == "walk":
            if st.on_ground and btn.is_pressed(btn.UP):
                st.pvy = -JUMP_V
                st.on_ground = False
            st.pvy += GRAVITY
            st.py += st.pvy
            if st.py >= WALK_REST_Y:
                st.py = float(WALK_REST_Y)
                st.pvy = 0.0
                st.on_ground = True
            player.move(int(st.px), int(st.py))
            if not st.on_ground:
                jf = 8 if st.pvy < 0 else 9
            else:
                jf = (st.frame // ANIM_DIV) % 8
            if jf != st.last_jf:                        # the animation frame only changes every ANIM_DIV frames
                st.last_jf = jf
                player.bitmap = jill_sheet.use(jf)     # XipSheet: pointer swap (dirty by itself);
                player.touch()                          # StreamSheet: in-place buffer -> touch needed
        else:  # fly
            dy = (btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)) * 4
            st.py = min(BOTTOM - 28, max(TOP + 28, st.py + dy))
            player.move(int(st.px), int(st.py))
            bf = (st.frame // ANIM_DIV) % pic_bird.FRAMES
            if bf != st.last_jf:
                st.last_jf = bf
                player.bitmap = bird_sheet.use(bf)
                player.touch()

        # ground shadow follows Jill (grounding cue at a fixed y); hidden as the flying Bird
        if a["kind"] == "walk":
            shadow.move(int(st.px), SHADOW_Y)
            shadow.visible = True
        else:
            shadow.visible = False

        # --- shoot ---
        if st.fire_cd > 0:
            st.fire_cd -= 1
        if btn.is_pressed(btn.A) and st.fire_cd == 0:
            fire()
            st.fire_cd = a["reload"]

        # --- scroll parallax: one offset per layer; strips move only on integer change ---
        for L in bg_layers:
            w = L[1]
            off = L[3] - L[2]
            if off <= -w:
                off += w
            L[3] = off
            xi = int(off)
            if xi != L[4]:
                L[4] = xi
                pair = L[0]
                for i in range(0, len(pair), 2):
                    pair[i].x = xi
                    pair[i + 1].x = xi + w

        # --- spawn enemies: per-frame probability ramping 8000->14000 /65536 over the level (scaled),
        # capped at MAX_ENEMIES by the pool. A slow dense swarm, densest near the end. ---
        if st.banner == 0:
            progress = 1.0 - st.level_t / LEVEL_FRAMES          # 0 at start -> 1 at level end
            # per-frame roll via the C random module: picogame_rand's xorshift overflows the small
            # int on RP2040 -> ~5 mpz allocs per call (~250 us + GC churn); rng stays for spawn picks
            if random.getrandbits(16) < int((8000 + 6000 * progress) * SPEED_SCALE):
                spawn_enemy()

        # --- player shots: fly out, spin, expire ---
        for s in shots.items:
            if not s.visible:
                continue
            d = s.data
            nf = d["nf"]
            s.fx = s.fx + d["vx"]
            s.fy = s.fy + d["vy"]
            # original missiles REFLECT off the play-band top/bottom (they don't die there); a spread
            # shuriken bounces up/down and keeps travelling right until it leaves the right edge.
            if s.fy < TOP + 6:
                s.fy = TOP + 6
                d["vy"] = -d["vy"]
            elif s.fy > BOTTOM - 6:
                s.fy = BOTTOM - 6
                d["vy"] = -d["vy"]
            if d["spin"]:                               # runtime rotation = 0-RAM spin (int accumulator, no float churn)
                d["a"] = (d["a"] + SPIN_STEP) % 360
                s.angle = d["a"]
            elif nf > 1:
                s.frame = (st.frame // ANIM_DIV) % nf
            if s.fx > W + 10:
                shots.free(s)

        # --- enemy bullets: fly left, hit player ---
        for s in bullets.items:
            if not s.visible:
                continue
            s.fx = s.fx - BULLET_SPEED
            if s.fx < -10:
                bullets.free(s)
            elif s.near(player, a["r"]):
                bullets.free(s)
                damage()

        # --- enemies: pattern movement, wing flap, shoot, collide ---
        efr = (st.frame // ANIM_DIV) % pic_fly.FRAMES
        for e in enemies.items:
            if not e.visible:
                continue
            d = e.data
            t = d["t"]
            # walk the current move segment (steps, dx, dy)
            seg = MOVES[d["mv"]][d["seg"]]
            d["x"] += seg[1]
            d["y"] += seg[2]
            # clamp Y to the band; on an edge, end this segment (advance) + flip the endless drifters
            clamped = False
            if d["y"] < TOP + t["r"]:
                d["y"] = float(TOP + t["r"])
                clamped = True
                if d["mv"] == 1:                            # slow-up -> slow-down
                    d["mv"] = 2
                    d["seg"] = 0
            elif d["y"] > BOTTOM - t["r"]:
                d["y"] = float(BOTTOM - t["r"])
                clamped = True
                if d["mv"] == 2:                            # slow-down -> slow-up
                    d["mv"] = 1
                    d["seg"] = 0
            # advance the segment (steps==0 = endless final segment, never advances)
            if seg[0] != 0:
                if clamped:
                    d["seg"] += 1                           # edge hit -> jump to next segment
                    d["step"] = 0
                else:
                    d["step"] += 1
                    if d["step"] >= seg[0]:
                        d["step"] = 0
                        d["seg"] += 1
                if d["seg"] >= len(MOVES[d["mv"]]):
                    d["seg"] = len(MOVES[d["mv"]]) - 1
            e.fx = d["x"]
            e.fy = d["y"]
            if efr != d["fr"]:                              # wing flap changes every ANIM_DIV frames only
                d["fr"] = efr
                e.frame = efr
            if d["x"] < -30:
                enemies.free(e)
                continue
            # enemy fire: per-frame chance (original ENEMY_GEN_BUL), memoryless, fires while entering too
            if random.getrandbits(16) < ENEMY_FIRE_P:
                enemy_fire(e)
            # hit by a player shot? (piercing: the shot survives until its `hits` charge runs out)
            for s in shots.items:
                if s.visible and s.near(e, t["r"]):
                    s.data["hits"] -= 1
                    if s.data["hits"] <= 0:
                        shots.free(s)
                    enemies.free(e)
                    st.score += t["score"]
                    boom(d["x"], d["y"])
                    popup(d["x"], d["y"], t["score"])
                    break
            # caught the player? contact destroys the enemy AND awards its score (original HitActor)
            if e.visible and e.near(player, a["r"]):
                enemies.free(e)
                boom(d["x"], d["y"])
                st.score += t["score"]
                popup(d["x"], d["y"], t["score"])
                damage()

        # --- explosions ---
        for b in booms.items:
            if not b.visible:
                continue
            b.data += 1
            b.frame = b.data // ANIM_DIV
            b.scale = 0.8 + 0.7 * b.data / EXP_LIFE  # 0.8 -> 1.5 expanding blast (0-RAM, replaces 2 baked frames)
            if b.data // ANIM_DIV >= EXP_FRAMES:
                booms.free(b)

        # --- score popups: rise + expire ---
        for p in popups.items:
            if not p.visible:
                continue
            p.data += 1
            p.fy = p.fy - POPUP_RISE
            if p.data > POPUP_FRAMES:
                popups.free(p)

        # --- hit feedback: brief white flash on the player + a fading blood splat (no i-frames) ---
        if st.hitflash > 0:
            st.hitflash -= 1
            player.flash = WHITE if (st.hitflash & 1) else 0
        else:
            player.flash = 0
        if st.blood_t > 0:
            st.blood_t -= 1
            if st.blood_t == 0:
                blood.visible = False

        # --- level timer / clear banner / death ---
        # --- level timer + clear/death trigger (the banner countdown + freeze is handled at the loop top) ---
        st.level_t -= 1
        if st.level_t <= 0 or st.hp <= 0:
            st.banner = BANNER_LEN
            player.visible = True
            st.banner_msg = "GAME OVER" if st.hp <= 0 else "MEADOW CLEAR!"
            _snd.sfx_seq(SEQ_OVER if st.hp <= 0 else SEQ_CLEAR, priority=40, window=40)
            st.banner_x = (W - len(st.banner_msg) * 6) // 2  # ~centre (6 px/glyph)
            if st.score > max_score:                         # persist the best score to NVM
                max_score = st.score
            if _save:
                try:
                    _save.save({"best": max_score})
                except Exception:
                    pass

        scene.refresh()                                 # this frame (banner just triggered) = the frozen frame

        # --- HUD redraws (only when something visibly changes) ---
        # top bar: SCORE (green while beating the best) + MAX. Draw once even if both changed.
        top_dirty = False
        if st.score != st.last_score:
            st.last_score = st.score
            if st.score > max_score:
                max_score = st.score                        # live best; persisted at level end
            hud["score"] = st.score
            hud["score_col"] = SCORE_HI if st.score >= max_score else WHITE
            top_dirty = True
        if max_score != st.last_max:
            st.last_max = max_score
            hud["max"] = max_score
            top_dirty = True
        if top_dirty:
            draw_top()
        # bottom bar: LIFE / LOAD (reload) / TIME (elapsed) gauges - redraw only when a pixel width moves.
        reload = a["reload"]
        life_px = max(1, st.hp * LIFE_W // MAX_HP)
        load_px = LOAD_W if st.fire_cd <= 0 else max(1, (reload - st.fire_cd) * LOAD_W // reload)
        time_px = max(1, (LEVEL_FRAMES - st.level_t) * TIME_W // LEVEL_FRAMES)
        if life_px != st.last_life_px or load_px != st.last_load_px or time_px != st.last_time_px:
            st.last_life_px = life_px
            st.last_load_px = load_px
            st.last_time_px = time_px
            hud["life"] = life_px
            hud["life_col"] = GREEN if st.hp > 30 else RED
            hud["load"] = load_px
            hud["load_col"] = GREEN if st.fire_cd <= 0 else AMBER
            hud["time"] = time_px
            draw_gauges()

        _snd.tick()          # advances the SFX protection window + any pending fanfare tail
        clock.tick()


main()
