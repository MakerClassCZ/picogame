# Quest -- step 6: an NPC you can talk to.
#
# What you learn: interaction + a simple state machine for dialog. An NPC is a
# sprite; when the hero stands next to it and presses A we switch to a "dialog"
# state: the world keeps drawing underneath, and picogame_ui.TextBox draws a
# multi-line message box on top (a screen-space overlay, drawn after scene.refresh).
# While in dialog we DON'T process movement -- the game is paused on the box until
# you press a button to dismiss it.
#
# New vs step 5: an NPC sprite, an over/dialog state, picogame_ui.TextBox, freezing
# the world during dialog, an adjacency "PRESS A" prompt.
#
# Run:  python3 sim/run.py tutorials/03-quest/step6_npc.py --shot /tmp/q6.png

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
MCOLS, MROWS = 30, 20
CH2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]
SOLID = (3, 4, 5, 6)
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
FACE_NAME = ("down", "up", "left", "right")
BG = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*c) for c in TILE_RGB])
world = pg.Tilemap(tileset, MCOLS, MROWS)
hero_x, hero_y = TILE, TILE
npc_x, npc_y = TILE, TILE
coin_spots = []
for tile_y in range(MROWS):
    for tile_x in range(MCOLS):
        ch = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CH2TILE.get(ch, 1))
        if ch == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
        elif ch == "N":
            npc_x, npc_y = tile_x * TILE, tile_y * TILE
        elif ch == "*":
            coin_spots.append((tile_x * TILE, tile_y * TILE))
scene.add(world)

coin_bm = shp.circle(8, pg.rgb565(245, 215, 60))
coins = [pg.Sprite(coin_bm, x + 4, y + 4) for (x, y) in coin_spots]
for c in coins:
    scene.add(c)
npc = pg.Sprite(shp.rect(TILE, TILE, pg.rgb565(230, 200, 60)), npc_x, npc_y)
scene.add(npc)


def hero_bitmap():
    pal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60),
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
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=pal, frames=8,
                     stride=stride, transparent=0)


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=0)
walk = picogame_anim.AnimatedSprite(hero, {
    "down": ([0, 1], 8, True), "up": ([2, 3], 8, True),
    "left": ([4, 5], 8, True), "right": ([6, 7], 8, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BG)
dlg = ui.TextBox(pg, terminalio.FONT, 8, H - 60, W - 16, 54, WHITE, NAVY, maxlines=4)
LINES = ["Villager:", "Beware the slimes in the", "tall grass, traveller.", "(press A)"]

facing = DOWN
got = 0
state = "over"
dlg_shown = False                             # draw the modal once, not every frame


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MCOLS or tile_y < 0 or tile_y >= MROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def near_npc():
    return abs(hero.x - npc.x) <= TILE and abs(hero.y - npc.y) <= TILE


def follow():
    ox = max(W - MCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    oy = max(H - MROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(ox), int(oy))


follow()
dt = 1 / 30
while True:
    btn.poll()

    if state == "dialog":
        if not dlg_shown:                     # draw ONCE -> no per-frame flicker
            scene.refresh()                   # world frozen under the box
            dlg.draw(board.DISPLAY, bufA, LINES)
            dlg_shown = True
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            state = "over"
            scene.invalidate()                # repaint over the box next frame
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
        follow()
        walk.play(FACE_NAME[facing]); walk.tick(dt)
    else:
        hero.frame = facing * 2

    for c in coins:
        if c.visible and abs(hero.x - c.x) < 12 and abs(hero.y - c.y) < 12:
            c.visible = False
            got += 1

    if near_npc():
        hud.set("COINS %d/%d   A: TALK" % (got, len(coins)))
        if btn.just_pressed(btn.A):
            state = "dialog"; dlg_shown = False
    else:
        hud.set("COINS %d/%d" % (got, len(coins)))

    scene.refresh()
    dt = clock.tick()
