# Full TinySQuest on picogame - a Seaquest-style underwater shooter, faithful port of Daniel C's
# TinyJoypad TinySQuest (GPLv3) with the original art (squest_assets.py), PLUS: enemy submarines that
# fire torpedoes at you (dodge or shoot them down), a depth-gradient sea, kill bursts + screen shake,
# and a richer synthio SFX set incl. the classic low-oxygen heartbeat. No title screen - dives straight in.
#
#   * sub moves 4 ways, fires ONE torpedo at a time (only below the surface),
#   * three lanes carry fish + divers; from level 3, enemy subs fire horizontal torpedoes,
#   * oxygen drains; surface to refill - each surfacing rescues a diver, 6 divers clears the level,
#   * +3 per fish, +10 per sub, extra life every 100 pts, lives, levels speed up.
#
# Copy with squest_assets.py + picogame_game/input/clock/pool/fx (+ picogame_synth for sound). GPLv3.

import gc
import random
import board
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_pool
import array
import terminalio
import picogame_fx as fx
import picogame_palette as palette
import picogame_font as pgfont
import picogame_shapes as shp
import picogame_ui as ui
import squest_assets

# Sound: synthio SFX on the device (computed live - no sample RAM); silent in the simulator.
# Palette (sound-designer): short dry SQUARE beeps, bend only on the two zaps; kills/pickup/
# surface are quick rising arpeggios fired a frame apart; death is a descending square sink.
try:
    import picogame_synth as snd
    _synth = snd.Synth(sfx_level=0.8)

    def _n(midi, decay=0.04, amplitude=0.6, attack=0.003, bend=None):
        return snd.note(midi, snd.SQUARE, attack=attack, decay=decay, amplitude=amplitude, bend=bend)

    SND_FIRE = _n(88, 0.03, 0.55, bend=snd.pitch_bend(-5, 25))         # short high "pew"
    SND_EFIRE = _n(55, 0.05, 0.5, bend=snd.pitch_bend(-4, 35))         # low enemy "pwoo"
    SEQ_HIT = (_n(76, 0.035), _n(83, 0.035))                          # two-note up = fish kill
    SEQ_SUBHIT = tuple(_n(m, 0.045, 0.7) for m in (64, 71, 78))        # bigger 3-note rise = sub kill
    SEQ_PICK = (_n(84, 0.03, 0.55), _n(91, 0.03, 0.55))               # bright chime = diver grabbed
    SEQ_SURFACE = tuple(_n(m, 0.05) for m in (72, 76, 79, 84))         # major arpeggio = deliver/clear
    SEQ_CLEAR = tuple(_n(m, 0.06, 0.65) for m in (72, 76, 79, 84, 88, 91))  # bigger fanfare = LEVEL complete
    SEQ_EXTRA = (_n(72, 0.04), _n(79, 0.04), _n(84, 0.06))             # rising sting = extra life earned
    SEQ_DIE = (_n(64, 0.05), _n(56, 0.05), _n(48, 0.05),
               _n(40, 0.20, attack=0.004, bend=snd.pitch_bend(-4, 250)))  # descending sink = death
    SND_OXLOW = _n(60, 0.05, 0.5)                                      # oxygen heartbeat (hi)
    SND_OXLOW2 = _n(53, 0.05, 0.5)                                     # heartbeat (lo) - alternates
    REFILL_NOTES = [_n(50 + k * 3, 0.025, 0.45) for k in range(7)]     # pitch climbs as O2 fills

    _seq = []                                                         # pending arpeggio notes: [play_frame, note]

    def sfx(n):
        if n is not None:
            _synth.sfx(n)

    def sfx_seq(notes):                                               # schedule an arpeggio, one note per frame
        for i, nn in enumerate(notes):
            _seq.append([frame + i, nn])
except Exception:
    SND_FIRE = SND_EFIRE = SND_OXLOW = SND_OXLOW2 = None
    SEQ_HIT = SEQ_SUBHIT = SEQ_PICK = SEQ_SURFACE = SEQ_CLEAR = SEQ_EXTRA = SEQ_DIE = ()
    REFILL_NOTES = [None] * 7
    _seq = []

    def sfx(n):
        pass

    def sfx_seq(notes):
        pass


BG = pg.rgb565(0, 0, 78)
KEY = pg.rgb565(255, 0, 255)        # transparent key for overlays
WHITE = pg.rgb565(255, 255, 255)
scene, _, _ = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

W, H = board.DISPLAY.width, board.DISPLAY.height   # size-independent: lay out from the real display
HUD_H = 26
SURFACE_Y = HUD_H + 6            # sub at/above this depth = surfacing
SURFACE_TOP = SURFACE_Y - 8      # the sub breaches only a few px above the waterline when surfacing
FLOOR_Y = H - 24
LANES = (70, 130, 190)           # enemy lane centers
LEVELMAX = 8
# Sprites are baked at native 1x (squest_assets.SCALE=1); each gameplay/font sprite
# renders through the engine's nearest-neighbour draw scale to its old on-screen size.
# The collision constants below are in these ON-SCREEN (scaled) px - Sprite.overlaps is
# scale-aware, so a 1x bitmap at scale 2.5 reports the same bounds as the old 2.5x atlas.
SPR_SCALE = 2.5
SUB_W, SUB_H = 42, 20            # player sub frame size (17x8 art * 2.5)
ENEMY_W = 20
NPOOL = 9
NSUB = 3                          # enemy submarines on screen
NETORP = 4                        # enemy torpedoes in flight

# Build the gameplay sprites (no title art any more). Each is unpacked + upscaled on device.
A = {n: squest_assets.build(pg, n)
     for n in ("sub", "torp", "torp2", "enemy_sub", "diver", "font")}
# small submarine icon for the lives row (a sub silhouette reads better than the original art there)
LIFE_ICON = shp.from_mask([
    ".....##.......",
    ".....##.......",
    "..#########...",
    ".###########.#",
    ".#############",
    "..##########.#",
], pg.rgb565(70, 205, 250))
# one fish bitmap, recolored per level by mutating its palette (saves 3 full copies ~= 7 KB of RAM)
FISH_PAL = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(*squest_assets.FISH_COLORS[0])])
A["fish"] = squest_assets.build(pg, "fish", palette=FISH_PAL)
gc.collect()                      # drop transient unpack bytes before the long-lived layers

# --- background: a depth gradient (deep = dark) + an animated-feel waterline. Both zero/cheap RAM. ---
fx.Sky(scene, 0, SURFACE_Y, W, H - SURFACE_Y, pg.rgb565(0, 46, 120), pg.rgb565(0, 0, 26))  # StripDraw, 0 RAM
# animated waterline: a PAL8 band whose palette is cycled each frame (the Game Boy "flowing water" trick)
NWAVE = 6


def _wave(i):
    t = abs((i / NWAVE) * 2.0 - 1.0)             # 0..1..0 -> a bright crest with darker troughs, wraps
    return pg.rgb565(int(40 + 60 * (1 - t)), int(150 + 80 * (1 - t)), int(200 + 55 * (1 - t)))


WPAL = array.array("H", [KEY] + [_wave(i) for i in range(NWAVE)])
_wd = bytearray(W * 4)
for _y in range(4):
    for _x in range(W):
        _wd[_y * W + _x] = 1 + (_x // 5) % NWAVE
water = pg.Sprite(pg.Bitmap(_wd, W, 4, format=pg.PAL8, palette=WPAL, transparent=0), 0, SURFACE_Y - 3)
scene.add(water)

# --- ambient rising bubbles: a few wrapping dots drift up to the surface (cheap, like lastwing's stars) ---
BUBBLE = shp.rect(3, 3, pg.rgb565(160, 200, 235))    # softer foreground bubble
BUBBLE_DIM = shp.rect(3, 3, pg.rgb565(80, 125, 170))  # dimmer "deeper" bubble - some recede for a sense of depth
NBUB = 14
risers = []
for _i in range(NBUB):
    dim = (_i % 3 == 0)                                 # ~1/3 are the dim, slower, further-away ones
    b = pg.Sprite(BUBBLE_DIM if dim else BUBBLE, random.randint(0, W - 3),
                  SURFACE_Y + random.randint(0, FLOOR_Y - SURFACE_Y))
    b.data = (0.25 if dim else 0.4) + random.randint(0, 8) * 0.07   # gentle drift; dim ones rise slower
    scene.add(b)
    risers.append(b)

# --- pools + projectiles + player (render order = add order, bottom->top) ---
etorps = picogame_pool.Pool(scene, A["torp2"], NETORP)   # enemy torpedoes (behind subs/fish/player)
enemies = picogame_pool.Pool(scene, A["fish"], NPOOL)  # fish + divers
subs = picogame_pool.Pool(scene, A["enemy_sub"], NSUB)   # enemy submarines
torp = pg.Sprite(A["torp"], 0, 0, visible=False)
sub = pg.Sprite(A["sub"], (W - SUB_W) // 2, 120)
# render every 1x gameplay sprite at the old on-screen size (2.5x)
for _p in (etorps, enemies, subs):
    for _s in _p.items:
        _s.scale = SPR_SCALE
torp.scale = SPR_SCALE
sub.scale = SPR_SCALE
scene.add(torp)
scene.add(sub)
bubbles = pg.Particles(32, size=2, gravity=0.0, fade=True)   # kill bursts (no gravity - underwater)
scene.add(bubbles)
shaker = fx.Shake(scene, max_offset=5, decay=0.06)
death_fade = fx.Fade(scene, W, H, color=pg.rgb565(0, 8, 36))   # neutral dark dip on death (smoother than invert)

# --- HUD: oxygen bar (Canvas) + score digits + diver/life icons ---
HUD_W = W - 52                               # oxygen band ends just before the right-anchored score
OXB_W = HUD_W - 86                           # oxygen-bar width (from x84), derived from W -> responsive
hud = pg.Canvas(HUD_W, 14, transparent=KEY)  # only the pips+bar band, not the full WxBAR (saves ~9 KB)
hud.move(0, 5)
scene.add(hud)
DIG_W = 10
score_digits = [pg.Sprite(A["font"], W - 52 + i * DIG_W, 3) for i in range(5)]
for d in score_digits:
    d.scale = SPR_SCALE           # font baked 1x too -> scale to the old 10x20 glyph
    scene.add(d)
# "02" labels the oxygen bar - reuse the score's digit glyphs (frames 0 + 2 read as "O2"), no extra art
o2_label = [pg.Sprite(A["font"], 60 + i * DIG_W, 3) for i in range(2)]
o2_label[0].frame = 0
o2_label[1].frame = 2
for d in o2_label:
    d.scale = SPR_SCALE
    d.tint = pg.rgb565(0, 220, 120)   # green (multiply), matching the oxygen bar so they read as one unit
    scene.add(d)
# rescued-diver progress is shown as 6 pips on the HUD canvas (draw_oxygen): they ACCUMULATE across
# dives (you can't grab all 6 on one O2 load) and survive deaths; carrying the full 6 + surfacing clears.
live_icons = [pg.Sprite(LIFE_ICON, 6 + i * 16, H - 16, visible=False) for i in range(5)]
for d in live_icons:
    scene.add(d)
# goal prompt: blinks once you carry the full 6 divers - tells you HOW to clear the level (surface!)
_pb, _, _ = pgfont.render_text(pg, terminalio.FONT, "SURFACE!", pg.rgb565(255, 235, 110))
prompt = pg.Sprite(_pb, (W - 48) // 2, SURFACE_Y + 18, visible=False)
scene.add(prompt)

# white celebration flash, reused for level-clear (big pulse) + extra-life (small pulse)
deliver_flash = fx.Fade(scene, W, H, color=WHITE)

# centre banner (start / level-complete / game-over) - ONE prewarmed SceneLabel reused for every
# screen (a single text buffer, not three bitmaps - keeps squest inside its tight RAM budget).
gc.collect()
TXT_START, TXT_NEXT, TXT_OVER = "SQUEST   A: START", "NEXT LEVEL!   A", "GAME OVER   A: PLAY"
banner = ui.SceneLabel(scene, pg, terminalio.FONT, 0, H // 2 - 6, pg.rgb565(255, 235, 110), pg.rgb565(0, 12, 42))
banner.reserve(len(TXT_OVER))                              # size the buffer once on the clean heap


def show_banner(text):
    banner.set(text)
    banner.sprite.move(max(2, (W - len(text) * 6) // 2), H // 2 - 6)


def hide_banner():
    banner.set("")


# level counter, bottom-right: a "LVL" label + a font digit (reuses the score glyphs)
_lvlbm, _lvlw, _ = pgfont.render_text(pg, terminalio.FONT, "LVL", pg.rgb565(180, 210, 255))
lvl_label = pg.Sprite(_lvlbm, W - 17 - _lvlw, H - 15)
scene.add(lvl_label)
level_digit = pg.Sprite(A["font"], W - 14, H - 16)
level_digit.scale = SPR_SCALE
scene.add(level_digit)

PARK_X, PARK_Y = (W - SUB_W) // 2, SURFACE_TOP        # sub rests breaching the surface during screens

class State:
    def __init__(self):
        self.level = 1
        self.score = 0
        self.lives = 3
        self.ox = 90.0
        self.divers = 0
        self.facing = 1
        self.torp_vx = 0
        self.anim = 0
        self.ox_tick = 0
        self.spawn_tick = 0
        self.surfaced = 0
        self.sub_tick = 0
        self.life_mark = 0
        self.life_flash = 0
        self.mode = "start"


st = State()
_hud_key = None


def clear_field():                                   # despawn everything in play + holster the torpedo
    enemies.free_all()
    subs.free_all()
    etorps.free_all()
    torp.visible = False


def park_screen(text, mode):                         # freeze on a parked-sub screen (level-done / game-over)
    clear_field()
    sub.move(PARK_X, PARK_Y)
    prompt.visible = False
    show_banner(text)
    st.mode = mode


def reset_game():
    global st
    st = State()
    sub.move((W - SUB_W) // 2, 120)
    clear_field()
    level_setup()


def level_setup():
    FISH_PAL[1] = pg.rgb565(*squest_assets.FISH_COLORS[(st.level - 1) % 4])  # recolor every fish at once
    for e in enemies.items:
        if e.visible and e.data[0] != 1:
            e.touch()                                  # mark the recolored fish dirty so it repaints


def amount_sprites():
    lv = st.level
    return 1 if lv <= 2 else (2 if lv <= 6 else 3)


def speed():
    return 1 + st.level // 3


def draw_score():
    s = st.score
    for i in range(5):
        score_digits[4 - i].frame = s % 10
        s //= 10


def ox_barwidth():
    return int((OXB_W - 2) * max(0.0, min(1.0, (st.ox - 60) / 30.0)))


def draw_oxygen():
    hud.clear(KEY)
    d = st.divers
    for i in range(6):                               # 6 rescue pips: bright = carried, dim = still needed
        x = 4 + i * 9
        hud.fill_rect(x, 2, 7, 9, pg.rgb565(0, 210, 248) if i < d else pg.rgb565(35, 55, 85))
    hud.fill_rect(84, 3, OXB_W, 10, pg.rgb565(40, 80, 120))
    col = pg.rgb565(0, 220, 120) if st.ox > 70 else pg.rgb565(230, 120, 40)
    hud.fill_rect(85, 4, ox_barwidth(), 8, col)


def draw_hud():
    draw_score()
    for i in range(5):
        live_icons[i].visible = i < st.lives
    draw_oxygen()


def spawn_one():
    e = enemies.spawn()
    if e is None:
        return
    lane = LANES[random.randint(0, 2)]
    left = random.getrandbits(1)
    e.move(-ENEMY_W if left else W, lane)
    if any(o.visible and e.overlaps(o) for o in subs.items):   # don't appear under an enemy sub
        enemies.free(e)                                        # spot taken - skip (retry next spawn tick)
        return
    is_diver = (random.randint(0, 4) == 0)
    sp = speed()
    e.data = [1 if is_diver else 2, sp if left else -sp, 1 if left else 0]
    e.bitmap = A["diver"] if is_diver else A["fish"]   # fish color comes from the shared FISH_PAL
    e.frame = 3 if left else 0


def spawn_sub():
    s = subs.spawn()
    if s is None:
        return
    lane = LANES[random.randint(0, 2)]
    left = random.getrandbits(1)
    s.move(-ENEMY_W if left else W, lane)
    # same lane is fine, but don't pop in ON a fish/diver or another sub already at that spot
    if any(e.visible and s.overlaps(e) for e in enemies.items) or \
            any(o is not s and o.visible and s.overlaps(o) for o in subs.items):
        subs.free(s)
        return
    sp = max(1, speed())
    s.flash = 0
    s.data = [sp if left else -sp, random.randint(45, 100)]   # [vx, fire_cd]
    s.frame = 3 if left else 0


def fire_enemy_torp(s):
    et = etorps.spawn()
    if et is None:
        return
    vx = 7 if s.data[0] > 0 else -7
    et.data = [vx]
    et.move(s.x + (ENEMY_W if vx > 0 else -8), s.y + 8)
    sfx(SND_EFIRE)


def kill_sub(s):
    bubbles.emit(s.x + 10, s.y + 9, 12, 5, 24, pg.rgb565(255, 80, 20))    # fire
    bubbles.emit(s.x + 10, s.y + 9, 8, 2, 14, pg.rgb565(255, 240, 200))   # bright pressure release
    subs.free(s)
    st.score += 10
    shaker.add(0.4)                                  # subs jolt the screen (half a death's trauma)
    sfx_seq(SEQ_SUBHIT)
    maybe_extra_life()


def lose_life():
    shaker.add(0.7)
    death_fade.pulse(14, speed=1.3)
    st.lives -= 1
    st.ox = 90.0
    if st.lives < 0:
        game_over()                  # game over -> the start screen (press A to play again)
        return
    sub.move((W - SUB_W) // 2, 120)
    torp.visible = False


def surface_divers():
    # Divers PERSIST across dives + deaths (you can't grab all 6 on one O2 load). Surfacing just refills
    # O2; only surfacing with the full SIX delivers them -> bonus + next level. Otherwise keep diving.
    if st.divers >= 6:
        complete_level()
    else:
        sfx_seq(SEQ_SURFACE)                         # just a refill flourish; keep diving
    maybe_extra_life()


def maybe_extra_life():
    if st.score // 100 > st.life_mark:
        st.life_mark = st.score // 100
        if st.lives < 5:
            st.lives += 1
            st.life_flash = 18                       # blink the NEW life icon white (no screen flash)
            sfx_seq(SEQ_EXTRA)


def complete_level():
    bonus = (int(st.ox) - 60) * 4                    # 0..120: a fast clear (more O2 left) scores more
    st.score += 160 + max(0, bonus)
    st.level = st.level + 1 if st.level < LEVELMAX else 1
    st.divers = 0
    level_setup()
    draw_level()
    st.ox = 90.0
    st.surfaced = 1
    deliver_flash.pulse(14, speed=2.0)               # big white celebration flash
    shaker.add(1.0)
    sfx_seq(SEQ_CLEAR)
    park_screen(TXT_NEXT, "leveldone")               # park on the surface - a safe breather


def game_over():
    park_screen(TXT_OVER, "start")                   # game over -> the start screen (A to play again)


def draw_level():
    level_digit.frame = st.level if st.level < 10 else 0


def begin_play():
    reset_game()
    draw_level()
    hide_banner()
    st.mode = "play"


def resume_play():
    hide_banner()
    st.mode = "play"


def present():                                       # ambient + audio + flush, shared by play and the frozen screens
    i = 0
    while i < len(_seq):
        if _seq[i][0] <= frame:
            sfx(_seq[i][1])
            _seq.pop(i)
        else:
            i += 1
    if frame % 5 == 0:
        palette.cycle(WPAL, 1, NWAVE)
        water.touch()
    for b in risers:
        b.fy -= b.data
        if b.fy < SURFACE_Y:
            b.fy = FLOOR_Y
            b.fx = random.randint(0, W - 3)
    if st.life_flash > 0:                             # blink the just-earned life icon white, then clear
        st.life_flash -= 1
        idx = st.lives - 1
        if 0 <= idx < 5:
            live_icons[idx].flash = WHITE if st.life_flash and (st.life_flash // 3) % 2 == 0 else 0
    bubbles.tick()
    shaker.tick()
    death_fade.tick()
    deliver_flash.tick()
    scene.refresh()
    clock.tick()


print("TinySQuest. D-pad swim, B fire. Surface to refill O2 + rescue divers; enemy subs SHOOT.")
reset_game()
sub.move(PARK_X, PARK_Y)
draw_level()
show_banner(TXT_START)
st.mode = "start"                 # boot to the start screen; A dives in
gc.collect()                      # compact the heap after all setup before the steady-state loop
frame = 0
while True:
    btn.poll()
    frame += 1

    if st.mode != "play":                             # frozen screens: start / level-complete / game-over
        if btn.just_pressed(btn.A):
            resume_play() if st.mode == "leveldone" else begin_play()
        present()
        continue

    # --- player ---
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx:
        st.facing = dx
    if dx or dy:
        sub.move(max(0, min(W - SUB_W, sub.x + dx * 4)),
                 max(SURFACE_TOP, min(FLOOR_Y - SUB_H, sub.y + dy * 4)))
    if frame % 4 == 0:
        st.anim = (st.anim + 1) % 3
    sub.frame = st.anim + (3 if st.facing > 0 else 0)

    # --- fire one torpedo ---
    if (btn.just_pressed(btn.A) or btn.just_pressed(btn.B)) and not torp.visible:   # A or B fire (simple game)
        torp.visible = True
        st.torp_vx = 8 if st.facing > 0 else -8
        torp.move(sub.x + (SUB_W if st.facing > 0 else -8), sub.y + 8)
        sfx(SND_FIRE)
    if torp.visible:
        nx = torp.x + st.torp_vx
        if nx < -8 or nx > W:
            torp.visible = False
        else:
            torp.move(nx, torp.y)
    # hoist the player-torpedo collision point ONCE per frame (torp doesn't move again this frame);
    # reused across every fish/diver + enemy sub, instead of building a fresh tuple per target.
    torp_pt = (torp.x + 4, torp.y + 2)

    # --- spawn fish/divers, and (from level 3) enemy subs ---
    if frame % max(9, 18 - st.level) == 0 and st.spawn_tick < amount_sprites():
        spawn_one()
        st.spawn_tick += 1
    if frame % 40 == 0:
        st.spawn_tick = 0
    if st.level >= 3:
        cad = max(50, 150 - st.level * 12)               # subs come faster at higher levels
        if frame % cad == 0:
            spawn_sub()

    # --- fish / divers ---
    for e in enemies.items:
        if not e.visible:
            continue
        nx = e.x + e.data[1]
        if nx < -ENEMY_W or nx > W:
            enemies.free(e)
            continue
        e.move(nx, e.y)
        if frame % 6 == 0:                           # animate fish AND divers (a swim/kick cycle)
            base = 3 if e.data[1] > 0 else 0
            e.frame = base + ((e.frame + 1) % 3)
        if e.data[0] == 2 and torp.visible and e.overlaps(torp_pt):
            bubbles.emit(e.x + 10, e.y + 9, 10, 3, 18, pg.rgb565(255, 200, 60))
            enemies.free(e)
            torp.visible = False
            st.score += 3
            sfx_seq(SEQ_HIT)
            maybe_extra_life()
            continue
        if e.overlaps(sub, 4):
            if e.data[0] == 1:
                if st.divers < 6:
                    st.divers += 1
                    sfx_seq(SEQ_PICK)
                enemies.free(e)
            else:
                enemies.free(e)
                sfx_seq(SEQ_DIE)
                lose_life()

    # --- enemy submarines: move, animate, telegraph (blink), fire ---
    for s in subs.items:
        if not s.visible:
            continue
        nx = s.x + s.data[0]
        if nx < -ENEMY_W or nx > W:
            subs.free(s)
            continue
        s.move(nx, s.y)
        if frame % 6 == 0:
            base = 3 if s.data[0] > 0 else 0
            s.frame = base + ((s.frame + 1) % 3)
        fc = s.data[1] - 1
        s.data[1] = fc
        if 0 < fc <= 12:                                 # telegraph: blink white before firing
            s.flash = WHITE if (fc // 3) % 2 else 0
        elif fc <= 0:
            s.flash = 0
            if 0 <= s.x <= W - ENEMY_W:                  # only fire when on screen
                fire_enemy_torp(s)
            s.data[1] = max(22, random.randint(40, 85) - st.level * 4)
        # player torpedo kills the sub
        if torp.visible and s.overlaps(torp_pt):
            torp.visible = False
            kill_sub(s)
            continue
        # ramming the sub
        if s.overlaps(sub, 6):
            subs.free(s)
            sfx_seq(SEQ_DIE)
            lose_life()

    # --- enemy torpedoes: hit the player, or get shot down by the player's torpedo ---
    for et in etorps.items:
        if not et.visible:
            continue
        nx = et.x + et.data[0]
        if nx < -8 or nx > W:
            etorps.free(et)
            continue
        et.move(nx, et.y)
        et_pt = (et.x + 4, et.y + 3)                  # this enemy torpedo's point, computed once
        if torp.visible and torp.overlaps(et_pt):
            bubbles.emit(et.x + 4, et.y + 3, 6, 2, 12, pg.rgb565(180, 220, 255))
            etorps.free(et)
            torp.visible = False
            continue
        if sub.overlaps(et_pt, 4):
            etorps.free(et)
            sfx_seq(SEQ_DIE)
            lose_life()

    # --- oxygen (surface refills via a latch) + the classic low-O2 heartbeat ---
    if sub.y <= SURFACE_Y + 2:
        if not st.surfaced:
            st.surfaced = 1
            surface_divers()
        if st.ox < 90.0:                              # O2 refills GRADUALLY; the tick's pitch rises with the tank
            st.ox = min(90.0, st.ox + 2.5)
            if frame % 4 == 0:
                sfx(REFILL_NOTES[min(6, max(0, int((st.ox - 60) / 5)))])
    else:
        st.surfaced = 0
        st.ox_tick += 1
        if st.ox_tick >= 10:
            st.ox_tick = 0
            st.ox -= 1
            if st.ox <= 60:
                sfx_seq(SEQ_DIE)
                lose_life()
    ox = st.ox
    if ox < 72:                                          # accelerating TWO-TONE heartbeat as O2 drops
        interval = 10 if ox < 62 else (20 if ox < 66 else 30)
        if frame % interval == 0:
            sfx(SND_OXLOW if (frame // interval) % 2 else SND_OXLOW2)

    # --- HUD only when it actually changed (oxygen Canvas redraw is the costly bit) ---
    key = (st.score, st.divers, st.lives, ox_barwidth())
    if key != _hud_key:
        _hud_key = key
        draw_hud()

    prompt.visible = st.divers >= 6 and (frame // 8) % 2 == 0   # blink the SURFACE! goal cue
    present()
