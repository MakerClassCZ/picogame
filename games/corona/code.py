# CORONA - "Lantern-Bearer vs the Dark": a horde-survivor (AI PAL8 art + a juice/clarity pass).
# Dark beasts swarm the bright arena; you are the Lantern-Bearer (move only); your light auto-fires; kills
# scatter XP embers that your lantern's glow MAGNETS in; XP -> level-up (flare + the dark recoils) -> pick
# 1 of 3; survive. Juice: warm death-bursts + dissolve, XP pickup pops, low-HP gutter, rationed invert.
# Controls: D-pad move | X dash (i-frames) | A confirm (level-up / retry).
# Run:  cd repos/picogame-final && python3 sim/run.py games/picogame_corona.py --backend pygame

import gc
import math
import random
import picogame as pg
import picogame_cutscene as cut
import picogame_game
import picogame_input
import picogame_clock
import picogame_pool
import picogame_shapes as shp
import picogame_ui as ui
import terminalio
import board
import picogame_fx as fx
import corona_art as art        # PAL8 sprites from PixelLab MCP (Lantern-Bearer vs the Dark)

def C(r, g, b):
    return pg.rgb565(r, g, b)

BG = C(228, 206, 150)            # pale bone-gold corona (the last daylight; dark beasts pop by value)
HERO = C(255, 196, 60)           # warm-gold Lantern-Bearer - the ONLY warm+bright object (hue sovereignty)
# shadow-beasts: all cool-dark (pop by value on the bright ground), one accent hue each
E_COL = (C(40, 34, 58), C(64, 30, 66), C(28, 52, 60), C(46, 52, 86))   # creeper/skitterer/brute/shade
BOLT = C(255, 240, 180)          # warm lantern-light = your power
GEM = C(255, 205, 70)            # warm-gold ember gem
GLOW = C(255, 236, 176)          # the lantern's light-pool: same warm hue as the tan floor but clearly BRIGHTER,
                                 # so the sparse dither stipple reads as "lit ground" not a loud orange blob
                                 # (dither is hard stipple, not alpha - if GLOW ~= the floor the dots vanish). = XP magnet radius
GLOW_DITHER = 9                  # glow's stipple level; MUST be re-asserted after any glow.flash write -
                                 # firmware's one-effect-at-a-time clears the dither flag when flash is set/cleared
RED = C(210, 60, 70)
INK = C(40, 30, 20)

MAGNET = 42                      # XP embers within this radius are drawn to the lantern (= glow radius)
# death "banished by light" burst: WARM GOLD, sized by kill frequency (common creeper small, rare brute big)
DEATH_N = (4, 4, 10, 6)          # creeper / skitterer / brute / shade particle counts
DEATH_FRAMES = 4

W, H = 320, 240
TOP = 16
# arena bounds (player centre clamp) live in State (st.ax0..st.ay1) — set in reset()

scene, bufA, _ = picogame_game.setup(strip_h=8, background=BG)   # 8 = less RAM + faster on a DMA board
clock = picogame_clock.Clock(30)
btn = picogame_input.Buttons()

# ground terrain: value-noise BAKED ONCE into a Tilemap (static, dirty-rect -> ~0 per-frame cost).
# NOT a per-frame full-screen noise pass: the dirty-rect engine has no bg framebuffer, so live noise would
# have to repaint the whole screen every frame under the swarm - the Tilemap bakes it once, drawn like a board.
TILE = 8
GCOLS, GROWS = W // TILE, H // TILE
# RGB565-exact tan shades (R/B multiples of 8, G of 4) stepping the same direction, so the mottle
# reads as pure brightness on the real ST7789 panel -- non-565-aligned shades wobble in HUE (green/pink
# banding) after 565 rounding + panel gamma, which the sim doesn't show.
GROUND = (C(72, 64, 48), C(80, 72, 56), C(88, 80, 64))   # dark warm-brown mottle: 565-clean (R/B x8, G x4, monotonic),
                                                          # dark so the lantern glow reads as real light against it
NTAN = len(GROUND)
_ground = pg.Tilemap(shp.tileset_colors(TILE, TILE, list(GROUND)), GCOLS, GROWS)
scene.add(_ground)


def fill_ground():                # (re)paint the mottled tan floor from value-noise (baked once, static)
    for cy in range(GROWS):
        for cx in range(GCOLS):
            v = pg.value2d(cx * 0.22, cy * 0.22, seed=7)
            _ground.tile(cx, cy, 1 + min(NTAN - 1, int(v * NTAN)))


fill_ground()

# Challenge comes purely from the swarm (density / speed / tanks + elites), so the whole arena stays
# lit and every enemy is always visible/fair - no contracting darkness, no sight-fog.

# --- AI sprites (PixelLab MCP): warm Lantern-Bearer hero + concrete shadow-beasts (silhouette per type)
PLAYER_BM = art.ember(pg)                       # warm-gold lantern-bearer (the one warm+bright object)
ENEMY_BMS = (art.mote(pg),      # Creeper  - shadow-hound
             art.spindle(pg),   # Skitterer- thin insectoid
             art.hulk(pg),      # Brute    - horned mass
             art.wisp(pg))      # Shade    - floating wraith
E_HP = (8.0, 5.0, 22.0, 10.0)        # creeper / skitterer / brute / shade
# per-type HP growth/level: CHAFF barely scales (you keep mowing it = the power-fantasy reward);
# TANKS scale hard (they're the wall that survives your fire) -> challenge returns via being OVERWHELMED
# (tanks + elites + density + speed), NOT by turning every enemy into a bullet-sponge.
E_HPSCALE = (0.03, 0.03, 0.11, 0.10)
E_SPD = (0.9, 1.7, 0.5, 1.1)
SPAWN_IN = 20                        # frames a new enemy creeps in before full speed (edge-spawn reaction window)
E_NF = (2, 2, 1, 2)                   # frame count per type (brute baked 1-frame; others 2-frame walk)
BOLT_BM = shp.rect(5, 5, BOLT)
GEM_BM = shp.rect(5, 5, GEM)

player = pg.Sprite(PLAYER_BM, W // 2, (TOP + H) // 2)
player.anchor = (0.5, 0.5)
# the lantern's light-pool: a soft warm aura that makes the hero findable AND shows the XP-magnet reach
glow = pg.Sprite(shp.circle(MAGNET, GLOW), 0, 0)    # half-size bitmap, drawn 2x -> saves ~5KB RAM
glow.anchor = (0.5, 0.5)
glow.scale = 2.0                                    # 42px bitmap x2 = the 84px light-pool (magnet radius)
glow.dither = GLOW_DITHER                           # sparse stipple = a gentle see-through warm tint (denser read as a solid block on the panel)
scene.add(glow)
scene.add(player)

NEN, NBOLT, NGEM = 16, 6, 16      # more XP embers on screen (a magnet keeps them flowing in, not capped out)
enemies = picogame_pool.Pool(scene, ENEMY_BMS[0], NEN)
bolts = picogame_pool.Pool(scene, BOLT_BM, NBOLT)
gems = picogame_pool.Pool(scene, GEM_BM, NGEM)
for grp in (enemies, bolts, gems):
    for s in grp.items:
        s.anchor = (0.5, 0.5)

parts = pg.Particles(24, size=2, gravity=0.0, fade=True)   # warm death-bursts / pickup pops / level-up flare
scene.add(parts)
iflash = fx.InvertFlash(board.DISPLAY)     # free full-screen negative - RATIONED to level-up + death only

top_lbl = ui.SceneLabel(scene, pg, terminalio.FONT, 2, 2, INK, BG)
bot_lbl = ui.SceneLabel(scene, pg, terminalio.FONT, 2, H - 12, RED, BG)
top_lbl.reserve(38)          # pre-alloc glyph buffers NOW (fresh heap) - HUD/labels grow later otherwise
bot_lbl.reserve(30)          # -> was the on-device MemoryError (a grow-realloc on a fragmented heap)

# --- persistent best score (NVM on device; sim has no NVM -> just in-memory this session) ---
try:
    import picogame_save
    _save = picogame_save.Save("corona", {"best": ("I", 0)})
    best_score = _save.load()["best"]
except Exception:
    _save = None
    best_score = 0

# --- state ---
PLAY, LEVELUP, OVER = 0, 1, 2
UPGRADES = ("DMG+50%", "RATE+", "SPEED+")     # short (bot_lbl buffer is reserved for this width)


class State:                                  # all MUTABLE per-run game state (start values mirror reset())
    def __init__(self):
        self.state = PLAY
        self.px = W / 2
        self.py = (TOP + H) / 2
        self.hp = 5
        self.level = 1
        self.xp = 0
        self.xp_next = 5
        self.score = 0
        self.run_t = 0
        self.inv = 0
        self.dash_cd = 0
        self.fire_cd = 0
        self.dmg = 2.0
        self.fire_rate = 16.0
        self.move_spd = 2.4
        self.sel = 0
        self.ax0 = 8
        self.ay0 = TOP + 8
        self.ax1 = W - 8
        self.ay1 = H - 8


st = State()

# ---------------- audio (guarded: synthio device-only; sim silent -> no-ops). Warm palette (tri/sine). ----
_seq = []                                 # pending arpeggio notes [play_frame, note], drained each frame
try:
    import synthio                         # noqa
    import picogame_synth as snd

    _synth = snd.Synth(sfx_level=0.7, buffer_size=1024)   # smaller buffer = less RAM (latency still fine)
    SQ, TR, SI = snd.SQUARE, snd.TRIANGLE, snd.SINE

    def _n(m, w, dec=0.05, amp=0.5, att=0.003, bend=None):
        return snd.note(m, w, attack=att, decay=dec, amplitude=amp,
                        bend=snd.pitch_bend(bend[0], bend[1]) if bend else None)

    SND_EDEATH = _n(76, TR, 0.06, 0.42, bend=(7, 70))     # warm chime up - "banished by light"
    SND_PICKUP = _n(91, SI, 0.05, 0.4, bend=(5, 40))      # soft round ping
    SND_DASH = _n(60, TR, 0.08, 0.4, bend=(7, 80))        # soft rising sweep
    SND_ELITE = _n(38, SI, 0.2, 0.4, att=0.04, bend=(-2, 200))   # low hollow growl
    SND_BOLT = _n(96, SI, 0.012, 0.16)                           # tiny quiet "tick" per auto-shot
    SEQ_PHIT = (_n(45, TR, 0.05, 0.6, bend=(-4, 90)), _n(38, TR, 0.13, 0.5, bend=(-3, 150)))
    SEQ_LEVELUP = (_n(64, TR, 0.05, 0.5), _n(68, TR, 0.05, 0.5), _n(71, TR, 0.05, 0.5), _n(76, TR, 0.16, 0.58))
    SEQ_DEATH = (_n(55, TR, 0.07, 0.55), _n(48, TR, 0.07, 0.55), _n(41, TR, 0.1, 0.55), _n(34, TR, 0.28, 0.5, bend=(-4, 300)))

    def sfx(n):
        if n is not None:
            _synth.sfx(n)

    def sfx_seq(notes):
        for i, nn in enumerate(notes):
            _seq.append([_f + i, nn])
except Exception:
    SND_EDEATH = SND_PICKUP = SND_DASH = SND_ELITE = SND_BOLT = None
    SEQ_PHIT = SEQ_LEVELUP = SEQ_DEATH = ()

    def sfx(n):
        pass

    def sfx_seq(notes):
        pass


def reset():
    global st
    for grp in (enemies, bolts, gems):
        for s in grp.items:
            grp.free(s)
    parts.clear()
    fill_ground()                        # repaint the floor (static)
    st = State()                         # all run state back to start values (arena bounds, etc.)
    player.flash = 0                     # clear any leftover hit-flash/tint (else it sticks across runs)
    player.tint = 0
    player.dither = 0
    glow.flash = 0
    glow.dither = GLOW_DITHER            # re-assert: flash=0 clears ALL fx flags (one-effect-at-a-time)
    player.move(int(st.px), int(st.py))
    glow.move(int(st.px), int(st.py))


def spawn_enemy():
    e = enemies.spawn()
    if not e:
        return
    edge = random.randint(0, 3)
    if edge == 0:
        ex, ey = random.randint(st.ax0, st.ax1), st.ay0
    elif edge == 1:
        ex, ey = random.randint(st.ax0, st.ax1), st.ay1
    elif edge == 2:
        ex, ey = st.ax0, random.randint(st.ay0, st.ay1)
    else:
        ex, ey = st.ax1, random.randint(st.ay0, st.ay1)
    typ = random.choice((0, 0, 0, 1, 1, 2, 3))      # mostly mote; some spindle/hulk/wisp
    hp = E_HP[typ] * (1.0 + E_HPSCALE[typ] * (st.level - 1))   # chaff stays mow-able; tanks become the wall
    elite = random.random() < min(0.35, 0.03 * st.level)   # a bigger, tankier target of opportunity
    if elite:
        hp *= 2.5
        sfx(SND_ELITE)                    # telegraph the tanky one
    e.bitmap = ENEMY_BMS[typ]
    e.flash = 0
    e.dither = 0
    e.scale = 1.35 if elite else 1.0      # elite reads by SIZE (no new hue); brute lumber multiplies this
    e.data = [hp, float(ex), float(ey), typ, 0, elite, 0]  # [hp, subx, suby, type, death_t, elite, age]
    e.move(ex, ey)


def fire():
    best, bd = None, 999999
    for e in enemies.items:
        if e.visible:
            d2 = (e.data[1] - st.px) ** 2 + (e.data[2] - st.py) ** 2
            if d2 < bd:
                bd, best = d2, e
    if best is None or bd > 160 * 160:
        return
    b = bolts.spawn()
    if not b:
        return
    dx, dy = best.data[1] - st.px, best.data[2] - st.py
    d = math.sqrt(dx * dx + dy * dy) or 1.0
    b.data = [dx / d * 6.0, dy / d * 6.0, st.px, st.py]   # [vx, vy, subx, suby]
    b.move(int(st.px), int(st.py))
    sfx(SND_BOLT)                                    # tiny tick on each auto-shot


def slay(e):                             # enemy killed: drop XP, warm "banished" burst, then dissolve
    typ = e.data[3]
    st.score += 1
    for _n in range(2 if e.data[5] else 1):    # elites drop 2 XP embers -> worth diverting fire toward
        g = gems.spawn()
        if g:
            g.data = [e.data[1] + _n * 6, e.data[2]]
            g.move(int(e.data[1] + _n * 6), int(e.data[2]))
    parts.emit(int(e.data[1]), int(e.data[2]), DEATH_N[typ], 4, 12, BOLT)
    sfx(SND_EDEATH)
    e.data[4] = DEATH_FRAMES              # enter dissolve; the chase loop fades then frees it


def title_splash():
    """Full-screen PixelLab title art, streamed from flash (~0 heap). Blocks until A; auto-advances
    on the desktop sim (no `_host` on device) so headless runs don't stall. Skipped if unavailable."""
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
        pal = cut.palette(pg, __import__("corona_title_pal"))
        cut.play(pg, scene.display, bufA, btn, here + "/corona_title.dat",
                 pal=pal, w=160, h=120, caption="A: play", auto_hold=hold, clock=clock)
        scene.invalidate()
    except Exception:
        pass


title_splash()
reset()
print("CORONA prototype. Move = D-pad, X = dash, A = confirm. Survive the dark.")
_f = 0


def main():
    global _f, best_score            # best_score is a module global (NVM best); assigned on new-best at game over
    # --- per-frame loop in a FUNCTION: names become array-indexed locals, not globals-dict
    # lookups (measured on-device win; picogame-game-design hot-loop style guide).
    while True:
        btn.poll()
        _f += 1
        _i = 0                                    # drain scheduled arpeggio notes due this frame
        while _i < len(_seq):
            if _seq[_i][0] <= _f:
                sfx(_seq[_i][1])
                _seq.pop(_i)
            else:
                _i += 1

        if st.state == PLAY:
            st.run_t += 1
            # spawn ramp: faster over time (floor drops to 6f/5-per-sec, reached ~5 min - not capped at 2 min)
            interval = max(6, 40 - st.run_t // 90)
            if _f % interval == 0:
                spawn_enemy()
                if st.run_t > 600:                       # opposite-side pair later (encircle)
                    spawn_enemy()

            # --- player move ---
            mx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
            my = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
            st.px += mx * st.move_spd
            st.py += my * st.move_spd
            if btn.just_pressed(btn.X) and st.dash_cd <= 0:   # dash: blink + a mercy window of i-frames
                st.px += mx * 28
                st.py += my * 28
                st.inv = max(st.inv, 22)                    # brief invulnerability after the dash
                st.dash_cd = 90
                sfx(SND_DASH)
            if st.dash_cd > 0:
                st.dash_cd -= 1
            st.px = min(st.ax1, max(st.ax0, st.px))
            st.py = min(st.ay1, max(st.ay0, st.py))
            player.move(int(st.px), int(st.py))
            glow.move(int(st.px), int(st.py))
            anim_f = (_f >> 3) & 1                     # 2-frame walk (~4 fps)
            player.frame = anim_f
            player.flash = 0
            if st.inv > 0:
                st.inv -= 1
                player.dither = 8 if (_f & 1) else 0
            else:
                player.dither = 0
            if st.hp <= 1 and (_f % 20 < 10):         # last-breath danger cue: the lantern gutters (bright pulse)
                glow.flash = GLOW                     # flash overrides the stipple while it pulses
            else:
                glow.flash = 0
                glow.dither = GLOW_DITHER             # re-assert stipple (flash write clears the dither flag)

            # --- auto-fire ---
            st.fire_cd -= 1
            if st.fire_cd <= 0:
                fire()
                st.fire_cd = int(st.fire_rate)

            # clear LAST frame's hit-flash up front, so a hit set below actually renders (non-lethal hits too)
            for e in enemies.items:
                if e.visible and e.data[4] == 0:
                    e.flash = 0

            # --- bolts ---
            for b in bolts.items:
                if not b.visible:
                    continue
                d = b.data
                d[2] += d[0]
                d[3] += d[1]
                if d[2] < 0 or d[2] > W or d[3] < TOP or d[3] > H:
                    bolts.free(b)
                    continue
                b.move(int(d[2]), int(d[3]))
                for e in enemies.items:
                    if e.visible and e.data[4] == 0 and (e.data[1] - d[2]) ** 2 + (e.data[2] - d[3]) ** 2 < 10 * 10:
                        e.data[0] -= st.dmg
                        e.flash = BOLT
                        bolts.free(b)
                        if e.data[0] <= 0:
                            slay(e)
                        break

            # --- enemies chase + contact ---
            for e in enemies.items:
                if not e.visible:
                    continue
                d = e.data
                if d[4] > 0:                               # dead: bright dissolve, then free
                    d[4] -= 1
                    e.dither = (DEATH_FRAMES - d[4]) * 2
                    if d[4] == 0:
                        e.dither = 0
                        e.flash = 0
                        enemies.free(e)
                    continue
                if E_NF[d[3]] > 1:                         # 2-frame walk (scale held from spawn: 1.0 or elite 1.35)
                    e.frame = anim_f
                else:                                      # brute is 1-frame -> heavy lumber (x elite base scale)
                    e.scale = (1.35 if d[5] else 1.0) * (1.10 if anim_f else 1.0)
                spd = E_SPD[d[3]] * (1.0 + 0.02 * (st.level - 1))   # mild speed ramp with level (secondary pressure)
                d[6] += 1                                           # spawn-in: creep for the first ~0.6s so an
                if d[6] < SPAWN_IN:                                 # edge spawn (esp. the fast skitterer) is
                    spd *= 0.35 + 0.65 * d[6] / SPAWN_IN            # reactable - accelerates 35% -> full speed
                dx, dy = st.px - d[1], st.py - d[2]
                dist = math.sqrt(dx * dx + dy * dy) or 1.0
                d[1] += dx / dist * spd
                d[2] += dy / dist * spd
                e.move(int(d[1]), int(d[2]))
                if dist < 13 and st.inv <= 0:
                    st.hp -= 1
                    st.inv = 75 if st.hp <= 1 else 45     # comeback mercy: longer i-frames on the last life
                    player.flash = RED
                    sfx_seq(SEQ_PHIT)
                    if st.hp <= 0:
                        iflash.pulse()                    # death = a felt, screen-wide beat
                        sfx_seq(SEQ_DEATH)
                        st.state = OVER
                        if st.score > best_score:         # new personal best -> persist to NVM (device)
                            best_score = st.score
                            if _save:
                                try:
                                    _save.save({"best": best_score})
                                except Exception:
                                    pass

            # --- gems: the lantern's magnet pulls XP embers in, then collect ---
            for g in gems.items:
                if not g.visible:
                    continue
                gx, gy = g.data
                d2 = (gx - st.px) ** 2 + (gy - st.py) ** 2
                if d2 < MAGNET * MAGNET:                       # inside the light-pool: drift toward the hero
                    gd = math.sqrt(d2) or 1.0
                    pull = 3.0 + (1.0 - gd / MAGNET) * 3.0     # accelerates as it nears
                    gx += (st.px - gx) / gd * pull
                    gy += (st.py - gy) / gd * pull
                    g.data[0] = gx                         # mutate in place (no per-frame list alloc)
                    g.data[1] = gy
                    g.move(int(gx), int(gy))
                    d2 = (gx - st.px) ** 2 + (gy - st.py) ** 2
                if d2 < 14 * 14:                               # collected
                    gems.free(g)
                    parts.emit(int(st.px), int(st.py), 3, 2, 8, GEM)  # tiny pickup sparkle
                    sfx(SND_PICKUP)
                    st.xp += 1
                    if st.xp >= st.xp_next:
                        st.xp -= st.xp_next
                        st.level += 1
                        st.xp_next = 4 + st.level * 2
                        st.state = LEVELUP
                        st.sel = 0
                        # signature: "the lantern flares and the dark recoils"
                        parts.emit(int(st.px), int(st.py), 16, 6, 18, BOLT)
                        iflash.pulse()
                        sfx_seq(SEQ_LEVELUP)
                        st.inv = max(st.inv, 40)               # mercy window so you resume safely after a level
                        for en in enemies.items:
                            if en.visible and en.data[4] == 0:
                                kdx, kdy = en.data[1] - st.px, en.data[2] - st.py
                                kd = math.sqrt(kdx * kdx + kdy * kdy) or 1.0
                                en.data[1] += kdx / kd * 30
                                en.data[2] += kdy / kd * 30
                                en.move(int(en.data[1]), int(en.data[2]))

            top_lbl.set("HP %d  LV %d  XP %d/%d  %d  %ds" %
                        (st.hp, st.level, st.xp, st.xp_next, st.score, st.run_t // 30))
            bot_lbl.set("")

        elif st.state == LEVELUP:
            if btn.just_pressed(btn.RIGHT):
                st.sel = (st.sel + 1) % 3
            if btn.just_pressed(btn.LEFT):
                st.sel = (st.sel - 1) % 3
            if btn.just_pressed(btn.A):
                if st.sel == 0:
                    st.dmg *= 1.5
                elif st.sel == 1:
                    st.fire_rate = max(4.0, st.fire_rate - 3.0)
                else:
                    st.move_spd += 0.5
                st.state = PLAY
            top_lbl.set("LEVEL UP!  pick (L/R + A)")
            bot_lbl.set(" ".join(("[%s]" % u if i == st.sel else u) for i, u in enumerate(UPGRADES)))

        else:  # OVER
            top_lbl.set("DARK WINS %ds  score %d  best %d" % (st.run_t // 30, st.score, best_score))
            bot_lbl.set("A: again")
            if btn.just_pressed(btn.A):
                reset()

        iflash.tick()
        parts.tick()
        scene.refresh()
        clock.tick()


main()
