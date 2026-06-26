# Starship -- step 7: explosions, thrust flame, and sound.
#
# What you learn: particles for two different effects, plus audio. One Particles
# system gives us BOTH a burst on a rock's destruction (many fast, fading sparks)
# and a thrust flame (a few short-lived sparks behind the ship each frame while
# thrusting). fade=True dims particles as they age. tone() beeps for firing and a
# lower boom for explosions. Audio is optional (try/except) so it's silent but safe
# where there's no audio output.
#
# New vs step 6: pg.Particles(fade=True), emit for explosions AND exhaust,
# picogame_audio for fire/boom beeps.
#
# Run:  python3 sim/run.py tutorials/02-starship/step7_particles.py --hold UP,B --shot /tmp/p7.png

import math
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_pool
import picogame_ui as ui

W, H = 320, 240
BG = pg.rgb565(0, 0, 8)
NF = 16

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

try:
    import picogame_audio
    audio = picogame_audio.Audio()
    snd_fire = picogame_audio.tone(880, 25)
    snd_boom = picogame_audio.tone(160, 90)
except Exception:
    audio = None

ship_bm = shp.poly_frames(18, [(0, -8), (6, 7), (0, 4), (-6, 7)], NF, pg.rgb565(200, 220, 255))
DIRS = [(math.sin(f * 2 * math.pi / NF), -math.cos(f * 2 * math.pi / NF)) for f in range(NF)]
bullet_bm = shp.circle(4, pg.rgb565(255, 255, 120))
ROCK_BM = [shp.ring(40, pg.rgb565(170, 140, 100), 3),
           shp.ring(24, pg.rgb565(170, 140, 100), 3),
           shp.ring(13, pg.rgb565(170, 140, 100), 2)]
ROCK_R = [20, 12, 6]

ship = pg.Sprite(ship_bm, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
rocks = picogame_pool.Pool(scene, ROCK_BM[0], 16, anchor=(0.5, 0.5))
bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))
sparks = pg.Particles(160, size=2, fade=True)     # NEW
scene.add(sparks)
scene.add(ship)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BG)

angle = 0
velocity_x = velocity_y = 0.0
fire_cd = 0
lives = 3
inv = 60
wave = 3
score = 0
frame = 0


def wrap(x, y):
    return x % W, y % H


def spawn_rock(size, x, y, rvx, rvy):
    r = rocks.spawn()
    if r is None:
        return
    r.data = {"size": size, "vx": rvx, "vy": rvy}
    r.bitmap = ROCK_BM[size]
    r.fx, r.fy = float(x), float(y)


def new_wave(n):
    for i in range(n):
        a = i * 2 * math.pi / n
        spawn_rock(0, (W // 2 + int(140 * math.cos(a))) % W,
                   (H // 2 + int(110 * math.sin(a))) % H,
                   math.cos(a) * 1.2, math.sin(a) * 1.2)


def respawn():
    global velocity_x, velocity_y, inv
    ship.fx, ship.fy = float(W // 2), float(H // 2)
    velocity_x = velocity_y = 0.0
    inv = 90


new_wave(wave)
while True:
    btn.poll()
    frame += 1
    fire_cd -= 1
    if inv > 0:
        inv -= 1

    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % NF
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % NF
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25; velocity_y += delta_y * 0.25
        # thrust flame: a couple of orange sparks shot out the back
        sparks.emit(ship.x - int(delta_x * 8), ship.y - int(delta_y * 8), 2, 2, 10, pg.rgb565(255, 150, 40))
    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)
    if speed > 5:
        velocity_x *= 5 / speed; velocity_y *= 5 / speed
    velocity_x *= 0.99; velocity_y *= 0.99
    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)
    ship.frame = angle
    ship.visible = (inv <= 0) or (frame & 1)

    if btn.just_pressed(btn.B) and fire_cd <= 0:
        b = bullets.spawn()
        if b:
            b.data = {"vx": delta_x * 7, "vy": delta_y * 7, "life": 30}
            b.move(ship.x, ship.y)
            fire_cd = 6
            if audio:
                audio.sfx(snd_fire)
    for b in bullets.items:
        if not b.visible:
            continue
        b.data["life"] -= 1
        if b.data["life"] <= 0:
            bullets.free(b)
            continue
        b.fx, b.fy = wrap(b.fx + b.data["vx"], b.fy + b.data["vy"])

    for r in rocks.items:
        if not r.visible:
            continue
        r.fx, r.fy = wrap(r.fx + r.data["vx"], r.fy + r.data["vy"])
        size = r.data["size"]
        rr = ROCK_R[size]
        for b in bullets.items:
            if not b.visible:
                continue
            if b.near(r, rr):
                bullets.free(b)
                rocks.free(r)
                score += (3 - size) * 20
                sparks.emit(r.x, r.y, 18, 3, 26, pg.rgb565(255, 200, 120))   # explosion
                if audio:
                    audio.sfx(snd_boom)
                if size < 2:
                    for s in (-1, 1):
                        spawn_rock(size + 1, r.fx, r.fy,
                                   r.data["vx"] + s * 0.8, r.data["vy"] - s * 0.8)
                break
        if inv <= 0 and r.visible and ship.near(r, rr + 6):
            lives -= 1
            sparks.emit(ship.x, ship.y, 24, 4, 30, pg.rgb565(120, 200, 255))
            respawn()
            if lives < 0:
                lives = 3
                score = 0
                rocks.free_all()
                new_wave(wave)
            break

    if rocks.count() == 0:
        wave += 1
        new_wave(wave)

    sparks.tick()                            # advance all particles
    hud.set("SCORE %05d   SHIPS %d" % (score, max(0, lives)))
    scene.refresh()
    clock.tick()
