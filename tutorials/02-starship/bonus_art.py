# Starship -- BONUS: the finished game (step 8) with REAL pixel art swapped in.
#
# Same lesson as Bounce step 9, now with downloaded CC0 art: the ENTIRE game below is
# identical to step8_states.py -- only the two bitmap lines changed (ship + bullet).
# The ship is a real Kenney "Pixel Shmup" sprite (CC0), pre-rotated into 16 frames
# offline by tools/png2picogame (pre-baked frames are crisper + cheaper for constant spin, so we just set
# ship.frame = angle); the bullet is a Kenney laser tile. Art is orthogonal to code.
#
# Assets: tutorials/02-starship/art_ship.py + art_bullet.py (generated from
# assets/kenney/*.png, CC0 -- see assets/kenney/CREDITS.txt). To use YOUR own art,
# run a PNG strip through tools/png2picogame.py and import it the same way -- see
# tutorials/ASSETS.md.
#
# Run:  python3 sim/run.py tutorials/02-starship/bonus_art.py --hold B --shot /tmp/pbonus.png

import math
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp
import picogame_pool
import picogame_ui as ui
import art_ship                               # <-- generated from angle_rad CC0 PNG
import art_bullet

W, H = 320, 240
BACKGROUND = pg.rgb565(0, 0, 8)
FRAMES = 16
TITLE, PLAY, GAMEOVER = 0, 1, 2

scene, _, _ = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

try:
    import picogame_audio
    audio = picogame_audio.Audio()
    snd_fire = picogame_audio.tone(880, 25)
    snd_boom = picogame_audio.tone(160, 90)
except Exception:
    audio = None

ship_bitmap = art_ship.bitmap(pg)                 # <-- was shp.poly_frames(...) : real ship, 16 frames
DIRS = [(math.sin(frame * 2 * math.pi / FRAMES), -math.cos(frame * 2 * math.pi / FRAMES)) for frame in range(FRAMES)]
bullet_bitmap = art_bullet.bitmap(pg)             # <-- was shp.circle(...) : real laser tile
ROCK_BITMAP = [shp.ring(40, pg.rgb565(170, 140, 100), 3),
           shp.ring(24, pg.rgb565(170, 140, 100), 3),
           shp.ring(13, pg.rgb565(170, 140, 100), 2)]
ROCK_RADIUS = [20, 12, 6]

ship = pg.Sprite(ship_bitmap, W // 2, H // 2)
ship.anchor = (0.5, 0.5)
rocks = picogame_pool.Pool(scene, ROCK_BITMAP[0], 16, anchor=(0.5, 0.5))
bullets = picogame_pool.Pool(scene, bullet_bitmap, 6, anchor=(0.5, 0.5))
sparks = pg.Particles(160, size=2, fade=True)
scene.add(sparks)
scene.add(ship)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, pg.rgb565(255, 255, 255), BACKGROUND)
msg = ui.SceneLabel(scene, pg, terminalio.FONT, 96, 112, pg.rgb565(255, 255, 255), BACKGROUND)

state = TITLE
angle = 0
velocity_x = velocity_y = 0.0
fire_cooldown = 0
lives = 3
invincible = 0
wave = 3
score = 0
frame = 0


def wrap(x, y):
    return x % W, y % H


def spawn_rock(size, x, y, velocity_x, velocity_y):
    rock = rocks.spawn()
    if rock is None:
        return
    rock.data = {"size": size, "velocity_x": velocity_x, "velocity_y": velocity_y}
    rock.bitmap = ROCK_BITMAP[size]
    rock.fx, rock.fy = float(x), float(y)


def new_wave(count):
    for i in range(count):
        angle_rad = i * 2 * math.pi / count
        spawn_rock(0, (W // 2 + int(140 * math.cos(angle_rad))) % W,
                   (H // 2 + int(110 * math.sin(angle_rad))) % H,
                   math.cos(angle_rad) * 1.2, math.sin(angle_rad) * 1.2)


def new_game():
    global angle, velocity_x, velocity_y, fire_cooldown, lives, invincible, wave, score
    angle = 0; velocity_x = velocity_y = 0.0; fire_cooldown = 0; lives = 3; invincible = 60; wave = 3; score = 0
    ship.fx, ship.fy = float(W // 2), float(H // 2)
    rocks.free_all()
    bullets.free_all()
    sparks.clear()
    new_wave(wave)


while True:
    btn.poll()
    frame += 1

    if state == TITLE:
        ship.visible = False
        msg.set("STARSHIP   PRESS A")
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            new_game()
            state = PLAY
        scene.refresh()
        clock.tick()
        continue

    if state == GAMEOVER:
        msg.set("GAME OVER  %05d  A=MENU" % score)
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            state = TITLE
        sparks.tick()
        scene.refresh()
        clock.tick()
        continue

    # ---- state == PLAY ----
    msg.set(" ")
    fire_cooldown -= 1
    if invincible > 0:
        invincible -= 1
    if btn.is_pressed(btn.LEFT):
        angle = (angle - 1) % FRAMES
    if btn.is_pressed(btn.RIGHT):
        angle = (angle + 1) % FRAMES
    delta_x, delta_y = DIRS[angle]
    if btn.is_pressed(btn.UP):
        velocity_x += delta_x * 0.25; velocity_y += delta_y * 0.25
        sparks.emit(ship.x - int(delta_x * 8), ship.y - int(delta_y * 8), 2, 2, 10, pg.rgb565(255, 150, 40))
    speed = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)
    if speed > 5:
        velocity_x *= 5 / speed; velocity_y *= 5 / speed
    velocity_x *= 0.99; velocity_y *= 0.99
    ship.fx, ship.fy = wrap(ship.fx + velocity_x, ship.fy + velocity_y)
    ship.frame = angle
    ship.visible = (invincible <= 0) or (frame & 1)

    if btn.just_pressed(btn.B) and fire_cooldown <= 0:
        bullet = bullets.spawn()
        if bullet:
            bullet.data = {"velocity_x": delta_x * 7, "velocity_y": delta_y * 7, "life": 30}
            bullet.move(ship.x, ship.y)
            fire_cooldown = 6
            if audio:
                audio.sfx(snd_fire)
    for bullet in bullets.items:
        if not bullet.visible:
            continue
        bullet.data["life"] -= 1
        if bullet.data["life"] <= 0:
            bullets.free(bullet)
            continue
        bullet.fx, bullet.fy = wrap(bullet.fx + bullet.data["velocity_x"], bullet.fy + bullet.data["velocity_y"])

    for rock in rocks.items:
        if not rock.visible:
            continue
        rock.fx, rock.fy = wrap(rock.fx + rock.data["velocity_x"], rock.fy + rock.data["velocity_y"])
        size = rock.data["size"]
        radius = ROCK_RADIUS[size]
        for bullet in bullets.items:
            if not bullet.visible:
                continue
            if bullet.near(rock, radius):
                bullets.free(bullet)
                rocks.free(rock)
                score += (3 - size) * 20
                sparks.emit(rock.x, rock.y, 18, 3, 26, pg.rgb565(255, 200, 120))
                if audio:
                    audio.sfx(snd_boom)
                if size < 2:
                    for sign in (-1, 1):
                        spawn_rock(size + 1, rock.fx, rock.fy,
                                   rock.data["velocity_x"] + sign * 0.8, rock.data["velocity_y"] - sign * 0.8)
                break
        if invincible <= 0 and rock.visible and ship.near(rock, radius + 6):
            lives -= 1
            sparks.emit(ship.x, ship.y, 24, 4, 30, pg.rgb565(120, 200, 255))
            ship.fx, ship.fy = float(W // 2), float(H // 2)
            velocity_x = velocity_y = 0.0
            invincible = 90
            if lives < 0:
                state = GAMEOVER
            break

    if rocks.count() == 0:
        wave += 1
        new_wave(wave)

    sparks.tick()
    hud.set("SCORE %05d   SHIPS %d" % (score, max(0, lives)))
    scene.refresh()
    clock.tick()
