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
# Run:  python3 sim/run.py games/picowing/code.py --backend pygame
#   or: python3 sim/run.py games/picowing/code.py --frames 200 --hold A,LEFT --shot /tmp/pw.png

import board
import array
import gc
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shapes
import picogame_ui as ui
import picogame_pool
import picogame_rand
import picogame_fx
import plane                                       # Kenney Pixel Shmup ship (CC0), 32x32 PAL8
import enemy                                       # Kenney Pixel Shmup enemy (CC0), 32x32 PAL8

try:
    import picogame_audio
    audio = picogame_audio.Audio()
except Exception:
    audio = None                                      # audio is optional (no-op if unavailable)

# Pre-build the SFX waveforms ONCE (tone() allocates a sample buffer; never do that per hit -> hitch).
SFX = {}
if audio:
    SFX["hurt"] = picogame_audio.tone(180, 90)
    SFX["bomb"] = picogame_audio.tone(90, 160)
    SFX["shot"] = picogame_audio.tone(880, 24)
    SFX["kill"] = picogame_audio.tone(150, 70)
    SFX["jam"] = picogame_audio.tone(70, 60)          # low buzz when the gun overheats/locks
    SFX["extra"] = picogame_audio.tone(1200, 80)      # bright chime when you earn a bomb

try:
    import picogame_save
    _hi = picogame_save.Save("picowing", {"hi": ("I", 0)})
except Exception:
    _hi = None                                        # NVM hi-score is optional (sim/some builds lack it)


def C(r, g, b):
    return pg.rgb565(r, g, b)


def sfx(name):
    if audio:
        audio.sfx(SFX[name])

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
RESET_HEAT = 30                                       # gun unlocks once heat drains back to here

# Player<->raider hit radius (px between sprite centres). Ships are 32px; smaller felt too forgiving
# (wings overlapped with no hit). Lower = kinder, higher = stricter.
HIT_R = 20

scene, bufA, _ = picogame_game.setup(background=SKY, top=BAR)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
rng = picogame_rand.Rand(0x5159)
shake = picogame_fx.Shake(scene)
bomb_flash = picogame_fx.InvertFlash(board.DISPLAY)   # FREE full-screen invert pulse for the bomb (HW)

# --- art ---
PLANE = plane.bitmap(pg)
# Raiders reuse the Kenney enemy SHAPE with a warm palette swap (tint only MULTIPLIES/darkens, so it
# can't turn the green art bright-amber); rebuilding the PAL8 bitmap gives full high-luminance control.
_WARM = array.array("H", [0, C(150, 40, 30), C(255, 130, 45), C(120, 45, 25),
                          C(255, 215, 130), C(235, 90, 45), C(255, 245, 190)])
ENEMY = pg.Bitmap(enemy.DATA, enemy.WIDTH, enemy.HEIGHT, format=enemy.FORMAT,
                  palette=_WARM, frames=enemy.FRAMES, stride=enemy.STRIDE,
                  transparent=enemy.TRANSPARENT)
BULLET = shapes.rect(3, 9, C(250, 240, 120))
STAR = shapes.rect(2, 2, C(120, 150, 210))
# HUD icons: a plane per life, a bomb per bomb.
LIFE_ICON = shapes.from_mask([
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
BOMB_ICON = shapes.from_mask([
    "XX.........",
    "XX.######..",
    "...#######.",
    "...########",
    "...#######.",
    "XX.######..",
    "XX.........",
], C(255, 175, 70))                                    # amber
# Heat-gauge segments: 3 pre-built colours, swapped per heat band.
HEAT_G = shapes.rect(11, 3, C(80, 200, 110))           # cool
HEAT_O = shapes.rect(11, 3, C(255, 180, 60))           # warming
HEAT_R = shapes.rect(11, 3, C(255, 70, 50))            # hot / locked

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
ps = pg.Particles(180, size=2, gravity=0.0, fade=True)
scene.add(ps)

# --- HUD (fixed top strip) ---
# Create the labels at their WIDEST text so each glyph buffer is sized on the clean startup heap,
# not re-allocated mid-game on a fragmented one (see SceneLabel.prewarm / the memory docs).
hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, BAR, INK)
l_score = hud.label(terminalio.FONT, 4, 4, TEXT, "SCORE 00000")
l_chain = hud.label(terminalio.FONT, 150, 4, C(250, 220, 120), "x99  CHAIN 999")
# Lives + bombs shown as ICON sprites: the number VISIBLE = the count (toggled in hud_refresh).
life_icons = [hud.add(pg.Sprite(LIFE_ICON, 230 + i * 12, 4)) for i in range(3)]
bomb_icons = [hud.add(pg.Sprite(BOMB_ICON, 276 + i * 14, 5)) for i in range(3)]   # max 3 bombs
# Gun-heat gauge: 5 segments in the gap between SCORE and the CHAIN readout (set in hud_refresh).
heat_segs = [hud.add(pg.Sprite(HEAT_G, 82 + i * 12, 6)) for i in range(5)]
hud.draw()

# --- centre message (title / game-over overlay) ---
msg = ui.SceneLabel(scene, pg, terminalio.FONT, 0, 0, TEXT, SKY)
# Size the banner's buffer + cache its glyphs up front, on the clean heap (the longest line we show).
msg.reserve(len("GAME OVER  99999   BEST 99999   A"))

# --- game state ---
G = {"state": "title", "score": 0, "best": 0, "lives": 3, "bombs": 2,
     "chain": 0, "mult": 1, "t": 0, "inv": 0, "fire_cd": 0, "bank": 99, "flash_t": 0,
     "heat": 0, "gun_locked": False, "next_bomb": 10000}
if _hi is not None:
    try:
        G["best"] = _hi.load()["hi"]
    except Exception:
        pass


def set_msg(text):
    # centre a short line roughly (terminalio glyph ~6 px wide)
    msg.set(text)
    msg.sprite.move(max(2, W // 2 - len(text) * 3), H // 2 - 4)


def clear_actors():
    """Recycle every live raider and bullet, so a fresh state never inherits the last game's."""
    for e in enemies.items:
        enemies.free(e)
    for b in bullets.items:
        bullets.free(b)


def show_title():
    G["state"] = "title"
    set_msg("PICO WING   A: START")
    clear_actors()


def new_game():
    clear_actors()                                     # drop the previous game's raiders/bullets
    G.update(score=0, lives=3, bombs=2, chain=0, mult=1, t=0, inv=0, fire_cd=0, flash_t=0,
             heat=0, gun_locked=False, next_bomb=10000, state="play")
    plane.move(W // 2, H - 40)
    plane.visible = True
    plane.flash = 0
    set_msg("")


def hud_refresh():
    l_score.set("SCORE %05d" % G["score"])
    l_chain.set(("x%d  CHAIN %d" % (G["mult"], G["chain"])) if G["chain"] else "")
    lv, bo = G["lives"], G["bombs"]
    for i, s in enumerate(life_icons):                 # N icons visible = the count
        s.visible = i < lv
    for i, s in enumerate(bomb_icons):
        s.visible = i < bo
    # heat gauge: N segments filled, colour by band; full red + blink when the gun is locked
    locked = G["gun_locked"]
    h = G["heat"]
    seg = 5 if locked else h * 5 // 100
    blink = locked and ((G["t"] // 4) & 1)
    col = HEAT_R if (locked or h >= WARN_HEAT) else (HEAT_O if h >= 40 else HEAT_G)
    for i, s in enumerate(heat_segs):
        vis = (i < seg) and not blink
        s.visible = vis
        if vis:
            s.bitmap = col
    hud.draw()


def player_hit():
    G["lives"] -= 1
    G["chain"] = 0
    G["mult"] = 1
    G["inv"] = 45                                      # mercy i-frames
    plane.flash = WHITE
    G["flash_t"] = 3                                    # momentary flash, then just blink
    shake.add(0.6)
    sfx("hurt")
    if G["lives"] <= 0:
        G["state"] = "over"
        if G["score"] > G["best"]:
            G["best"] = G["score"]
            if _hi is not None:
                try:
                    _hi.save({"hi": G["best"]})
                except Exception:
                    pass
        gc.collect()                                   # defrag at the run boundary before the banner
        set_msg("GAME OVER  %05d   BEST %05d   A" % (G["score"], G["best"]))
        plane.visible = False


def fire_bomb():
    if G["bombs"] <= 0:
        return
    G["bombs"] -= 1
    G["heat"] = max(0, G["heat"] - 40)                 # the bomb also vents the gun (escape a lockout)
    if G["gun_locked"] and G["heat"] <= RESET_HEAT:
        G["gun_locked"] = False
    shake.add(0.8)                                     # a big kick - this IS the panic button
    bomb_flash.pulse()                                 # full-screen invert pulse (hardware, free)
    # Nothing at the ship (flash/particles there would read as "we got hit"); punch = invert + shake.
    for e in enemies.items:                            # screen-clear (panic button)
        if e.visible:
            ps.emit(int(e.fx), int(e.fy), 14, 4, 22, C(250, 180, 90))
            enemies.free(e)
    sfx("bomb")


def update_play():
    t = G["t"] = G["t"] + 1
    # --- input: 8-dir move + clamp; bank the ship into horizontal motion ---
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    plane.fx = max(14, min(W - 14, plane.fx + dx * 3.4))
    plane.fy = max(BAR + 14, min(H - 14, plane.fy + dy * 3.4))
    bank = (1 if dx > 0 else (-1 if dx < 0 else 0))
    if bank != G["bank"]:                              # only re-bake the rotation on change
        G["bank"] = bank
        plane.angle = (bank * 14) % 360                # bank INTO the motion (nose toward travel)
    if btn.just_pressed(btn.B):
        fire_bomb()
    if G["score"] >= G["next_bomb"]:                   # earn a bomb every 10000 pts (kept capped at 3)
        G["next_bomb"] += 10000
        if G["bombs"] < 3:
            G["bombs"] += 1
            sfx("extra")
    # --- autofire on hold, gated by GUN HEAT: hold too long and it overheats + locks ---
    a_held = btn.is_pressed(btn.A)
    if G["gun_locked"]:                                # locked: must RELEASE the trigger to cool down
        if not a_held:
            G["heat"] -= COOL_LOCKED
            if G["heat"] <= RESET_HEAT:
                G["heat"] = max(0, G["heat"])
                G["gun_locked"] = False
        # holding A while jammed keeps it locked -- the lesson is "let go"
    elif a_held:
        if G["fire_cd"] == 0:
            b = bullets.spawn()
            if b:
                b.move(int(plane.fx), int(plane.fy) - 16)
                b.data = -8.0                          # fast, snappy player shot
                sfx("shot")
            G["fire_cd"] = 6
            G["heat"] += HEAT_PER_SHOT
            if G["heat"] >= 100:                       # overheated -> lock the gun
                G["heat"] = 100
                G["gun_locked"] = True
                sfx("jam")
        else:
            G["fire_cd"] -= 1
    else:                                              # not firing: cool down (faster while a chain runs)
        G["heat"] -= COOL_IDLE + G["chain"] // 3
        if G["heat"] < 0:
            G["heat"] = 0
        G["fire_cd"] = 0                               # ready to fire the instant A is tapped again
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
            e.data = {"vy": speed, "drift": (rng.below(5) - 2) * 0.4, "dive": diver}
    # --- bullets ---
    for b in bullets.items:
        if not b.visible:
            continue
        b.fy += b.data
        if b.fy < -10:
            bullets.free(b)
    # --- raiders ---
    inv = G["inv"]
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
            G["chain"] = 0
            G["mult"] = 1
            continue
        if inv == 0 and e.near(plane, HIT_R):   # forgiving body hitbox (< the 32px sprite)
            enemies.free(e)
            ps.emit(int(plane.fx), int(plane.fy), 18, 5, 26, C(255, 120, 90))
            player_hit()
            return
        for b in bullets.items:
            if b.visible and b.near(e, 16):
                bullets.free(b)
                enemies.free(e)
                G["chain"] += 1
                G["mult"] = 1 + G["chain"] // 5
                G["score"] += 50 * G["mult"]
                ps.emit(int(e.fx), int(e.fy), 20, 5, 26, C(255, 210, 120))  # brighter, punchier kill burst
                sfx("kill")
                break
    if G["inv"] > 0:
        G["inv"] -= 1
        plane.visible = (G["inv"] // 3) % 2 == 0       # blink while invulnerable
    else:
        plane.visible = True


# --- main loop -------------------------------------------------------------
show_title()
hud_refresh()
print("PICO WING - D-pad move, hold A fire, B bomb. A to start.")
last_hud = None
while True:
    btn.poll()
    # starfield scrolls in every state (motion behind the menus too)
    for s in stars:
        s.fy += s.data
        if s.fy > H:
            s.fy = -2
            s.fx = rng.below(W)
    if G["state"] == "title":
        if btn.just_pressed(btn.A):
            new_game()
    elif G["state"] == "play":
        update_play()
    elif G["state"] == "over":
        if btn.just_pressed(btn.A):                    # INSTANT restart, re-init in place
            new_game()
    if G["flash_t"] > 0:                               # momentary player flash -> clear after a few frames
        G["flash_t"] -= 1
        if G["flash_t"] == 0:
            plane.flash = 0
    ps.tick()
    shake.tick()                                       # decaying screen-shake on top of the view
    bomb_flash.tick()                                  # restore the panel after the bomb's invert pulse
    key = (G["score"], G["chain"], G["mult"], G["lives"], G["bombs"],
           G["heat"] // 20, G["gun_locked"], (G["t"] // 4 & 1) if G["gun_locked"] else 0)
    if key != last_hud:
        last_hud = key
        hud_refresh()
    scene.refresh()
    clock.tick()
