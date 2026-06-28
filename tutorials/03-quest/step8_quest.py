# Quest -- step 8: a quest, a goal, and a win state (capstone).
#
# What you learn: tying the systems into an actual game. The NPC gives an objective
# (collect every coin); once you have them all, talking again OPENS the door (we
# rewrite those tiles from "door" to "path", so collision lets you through); stepping
# on the shrine tile wins. A small quest-stage variable drives the dialog text and
# the door. This is the whole loop: talk -> collect -> unlock -> reach the goal.
#
# New vs step 7: a quest stage, objective-driven dialog, opening the door by editing
# tiles, a goal tile + win state.
#
# BIG PICTURE: you've now hand-built an RPG -- map, camera, collision, animation,
# items, NPC, combat, quest. You DON'T have to keep hand-coding maps like this: the
# editor (editor/) lets you paint the map, place the hero/NPC/coins, and FLAG tiles
# (solid/coin/goal) visually, then the picogame_scene loader builds the scene for
# you -- the exact things this file does by hand become data. See tutorials/README.md
# and examples/picogame_platformer_scene.py for a game whose level is loaded that way.
#
# Run:  python3 sim/run.py tutorials/03-quest/step8_quest.py --shot /tmp/q8.png

import array
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_anim
import picogame_shapes as shp
import picogame_ui as ui

W, H = 320, 240
TILE = 16
SPEED = 2
MAP = [
    "##############################",
    "#.....:......................#",
    "#.....:........*.............#",
    "#..##.:.............~~~~~~...#",
    "#..##.:.............~~~~~~...#",
    "#.....N.............~~~~~~...#",
    "#.....:.......E.....~~~~~~...#",
    "#.....:......................#",
    "#.....:.....*.........*......#",
    "#.....:......................#",
    "#:::::::P:::::::::*::::::::::#",
    "#.....:...................*..#",
    "#.....:.............E........#",
    "#.....:...WWWWWWW............#",
    "#.....:...W.....W......##....#",
    "#.....:.*.W..G..W......##....#",
    "#.....:...W.....W........E...#",
    "#.....:...WWWDWWW............#",
    "#.....:......................#",
    "##############################",
]
MAPCOLS, MAPROWS = 30, 20
CHAR2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]
SOLID = (3, 4, 5, 6)
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
DIR = {DOWN: (0, 1), UP: (0, -1), LEFT: (-1, 0), RIGHT: (1, 0)}
FACE_NAME = ("down", "up", "left", "right")
BACKGROUND = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

scene, buffer_a, buffer_b = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
START = (TILE, TILE)
npc_x, npc_y = TILE, TILE
coin_spots, enemy_spots, door_tiles = [], [], []
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, 1))
        if char == "P":
            START = (tile_x * TILE, tile_y * TILE)
        elif char == "N":
            npc_x, npc_y = tile_x * TILE, tile_y * TILE
        elif char == "*":
            coin_spots.append((tile_x * TILE, tile_y * TILE))
        elif char == "E":
            enemy_spots.append((tile_x * TILE, tile_y * TILE))
        elif char == "D":
            door_tiles.append((tile_x, tile_y))
scene.add(world)

coin_bitmap = shp.circle(8, pg.rgb565(245, 215, 60))
coins = [pg.Sprite(coin_bitmap, x + 4, y + 4) for (x, y) in coin_spots]
for coin in coins:
    scene.add(coin)
slime_bitmap = shp.circle(14, pg.rgb565(120, 200, 80))
enemies = [pg.Sprite(slime_bitmap, x + 1, y + 1) for (x, y) in enemy_spots]
for enemy in enemies:
    scene.add(enemy)
npc = pg.Sprite(shp.rect(TILE, TILE, pg.rgb565(230, 200, 60)), npc_x, npc_y)
scene.add(npc)


def hero_bitmap():
    palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60),
                            pg.rgb565(255, 225, 170), pg.rgb565(120, 40, 30)])
    stride = TILE * 8
    data = bytearray(stride * TILE)
    for f in range(4):
        for s in range(2):
            fr = f * 2 + s
            for y in range(s, TILE):
                yy = y - s
                for x in range(TILE):
                    face = ((f == 0 and yy >= TILE - 4) or (f == 1 and yy < 4) or
                            (f == 2 and x < 4) or (f == 3 and x >= TILE - 4))
                    data[y * stride + fr * TILE + x] = 2 if face else 1
            lx = 4 if s == 0 else 6
            for x in (lx, TILE - 1 - lx):
                data[(TILE - 1) * stride + fr * TILE + x] = 3
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=palette, frames=8,
                     stride=stride, transparent=0)


hero = pg.Sprite(hero_bitmap(), START[0], START[1], frame=0)
walk = picogame_anim.AnimatedSprite(hero, {
    "down": ([0, 1], 8, True), "up": ([2, 3], 8, True),
    "left": ([4, 5], 8, True), "right": ([6, 7], 8, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BACKGROUND)
dialog = ui.TextBox(pg, terminalio.FONT, 8, H - 64, W - 16, 58, WHITE, NAVY, maxlines=4)

facing = DOWN
coins_collected = 0
hp = 6
hurt_cooldown = 0
stage = 0                                     # 0 not started, 1 collecting, 2 door open
state = "over"
frame = 0
NUMCOINS = len(coins)
overlay_shown = False                         # draw dialog/win modal once, not every frame


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MAPCOLS or tile_y < 0 or tile_y >= MAPROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def near(a, bx, by, d=TILE):
    return abs(a.x - bx) < d and abs(a.y - by) < d


def follow():
    ox = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    oy = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(ox), int(oy))


def dialog_lines():
    if stage == 0:
        return ["Villager:", "Bring me all %d coins and" % NUMCOINS,
                "I'll open the shrine door.", "(press A)"]
    if stage == 1 and coins_collected < NUMCOINS:
        return ["Villager:", "You have %d of %d coins." % (coins_collected, NUMCOINS),
                "Keep looking!", "(press A)"]
    return ["Villager:", "The door is open.",
            "Seek the shrine within.", "(press A)"]


def open_door():
    for (tile_x, tile_y) in door_tiles:
        world.tile(tile_x, tile_y, 2)                 # door -> path (no longer SOLID)
    scene.invalidate()


follow()
dt = 1 / 30
while True:
    btn.poll()
    frame += 1

    if state == "win":
        if not overlay_shown:                 # draw ONCE -> no per-frame flicker
            scene.refresh()
            dialog.draw(board.DISPLAY, buffer_a, ["You reached the shrine!", "", "QUEST COMPLETE", "(press A)"])
            overlay_shown = True
        if btn.just_pressed(btn.A):
            state = "over"; scene.invalidate()
        clock.tick()
        continue

    if state == "dialog":
        if not overlay_shown:                 # draw ONCE -> no per-frame flicker
            scene.refresh()
            dialog.draw(board.DISPLAY, buffer_a, dialog_lines())
            overlay_shown = True
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            if stage == 0:
                stage = 1
            elif stage == 1 and coins_collected >= NUMCOINS:
                stage = 2
                open_door()
            state = "over"; scene.invalidate()
        clock.tick()
        continue

    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        facing = RIGHT if delta_x > 0 else LEFT
    elif delta_y:
        facing = DOWN if delta_y > 0 else UP
    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        follow(); walk.play(FACE_NAME[facing]); walk.tick(dt)
    else:
        hero.frame = facing * 2

    if btn.just_pressed(btn.B):
        ddx, ddy = DIR[facing]
        ax, ay = hero.x + ddx * TILE, hero.y + ddy * TILE
        for enemy in enemies:
            if enemy.visible and abs(enemy.x - ax) < TILE and abs(enemy.y - ay) < TILE:
                enemy.visible = False

    if frame % 2 == 0:
        for enemy in enemies:
            if not enemy.visible:
                continue
            sx = (hero.x > enemy.x) - (hero.x < enemy.x)
            sy = (hero.y > enemy.y) - (hero.y < enemy.y)
            if sx and can_walk(enemy.x + sx, enemy.y):
                enemy.move(enemy.x + sx, enemy.y)
            if sy and can_walk(enemy.x, enemy.y + sy):
                enemy.move(enemy.x, enemy.y + sy)

    if hurt_cooldown > 0:
        hurt_cooldown -= 1
    else:
        for enemy in enemies:
            if enemy.visible and near(enemy, hero.x, hero.y, 13):
                hp -= 1
                hurt_cooldown = 40
                if hp <= 0:
                    hp = 6
                    hero.move(START[0], START[1]); follow()
                break

    for coin in coins:
        if coin.visible and abs(hero.x - coin.x) < 12 and abs(hero.y - coin.y) < 12:
            coin.visible = False; coins_collected += 1

    # reach the shrine (goal tile) once the door is open
    if stage >= 2:
        ctx = (hero.x + TILE // 2) // TILE
        cty = (hero.y + TILE // 2) // TILE
        if world.tile(ctx, cty) == 7:
            state = "win"; overlay_shown = False

    if near(hero, npc.x, npc.y):
        hud.set("HP %d  COINS %d/%d  A:TALK" % (hp, coins_collected, NUMCOINS))
        if btn.just_pressed(btn.A):
            state = "dialog"; overlay_shown = False
    else:
        objective = "FIND THE COINS" if stage < 1 or coins_collected < NUMCOINS else ("DOOR OPEN!" if stage >= 2 else "RETURN TO NPC")
        hud.set("HP %d  COINS %d/%d  %s" % (hp, coins_collected, NUMCOINS, objective))

    scene.refresh()
    dt = clock.tick()
