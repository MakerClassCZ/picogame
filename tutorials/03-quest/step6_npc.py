# Quest -- step 6: an NPC you can talk to (and a State object to tidy up).
#
# What you learn: interaction + a simple state machine for dialog, AND how to keep
# the growing pile of game variables under control. An NPC is a sprite; when the hero
# stands next to it and presses A we switch to a DIALOG mode: the world keeps drawing
# underneath, and picogame_ui.TextBox draws a multi-line message box on top (a
# screen-space overlay, drawn after scene.refresh). While in dialog we DON'T process
# movement -- the game is paused on the box until you press a button to dismiss it.
#
# State object: the loose module variables have been piling up (facing, coins, a
# mode, a "dialog shown" flag...) and the next steps add HP, a cooldown, a quest
# stage. Instead of a scatter of globals (and a `global` in every function that
# touches them), we group them in ONE `class State` and make `st = State()`. Now it's
# `st.coins`, `st.mode`, with no `global` needed. Objects that never get REASSIGNED
# (the hero Sprite, the world Tilemap, the labels) stay plain module-level names;
# State holds only the mutable scalars. The game mode is a named INT constant
# (EXPLORE / DIALOG) rather than a magic string, so a branch reads `st.mode ==
# DIALOG`.
#
# New vs step 5: an NPC sprite, a State object, a mode machine (EXPLORE/DIALOG),
# picogame_ui.TextBox, freezing the world during dialog, an adjacency "PRESS A" prompt.
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
MAPCOLS, MAPROWS = 30, 20
CHAR2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]
SOLID = (3, 4, 5, 6)
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
FACE_NAME = ("down", "up", "left", "right")
EXPLORE, DIALOG = 0, 1                        # game modes (int constants, not strings)
BACKGROUND = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

scene, buffer_a, buffer_b = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
hero_x, hero_y = TILE, TILE
npc_x, npc_y = TILE, TILE
coin_spots = []
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, 1))
        if char == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
        elif char == "N":
            npc_x, npc_y = tile_x * TILE, tile_y * TILE
        elif char == "*":
            coin_spots.append((tile_x * TILE, tile_y * TILE))
scene.add(world)

coin_bitmap = shp.circle(8, pg.rgb565(245, 215, 60))
coins = [pg.Sprite(coin_bitmap, x + 4, y + 4) for (x, y) in coin_spots]
for coin in coins:
    scene.add(coin)
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


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=0)
walk = picogame_anim.AnimatedSprite(hero, {
    "down": ([0, 1], 8, True), "up": ([2, 3], 8, True),
    "left": ([4, 5], 8, True), "right": ([6, 7], 8, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BACKGROUND)
dialog = ui.TextBox(pg, terminalio.FONT, 8, H - 60, W - 16, 54, WHITE, NAVY, maxlines=4)
LINES = ["Villager:", "Beware the slimes in the", "tall grass, traveller.", "(press A)"]


class State:
    """All the mutable game variables in one place (was a pile of module globals)."""
    def __init__(self):
        self.facing = DOWN
        self.coins = 0
        self.mode = EXPLORE               # EXPLORE = walking around, DIALOG = talking
        self.dlg_shown = False            # draw the modal once, not every frame


st = State()


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MAPCOLS or tile_y < 0 or tile_y >= MAPROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def near_npc():
    return abs(hero.x - npc.x) <= TILE and abs(hero.y - npc.y) <= TILE


def follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


follow()
dt = 1 / 30
while True:
    btn.poll()

    if st.mode == DIALOG:
        if not st.dlg_shown:                  # draw ONCE -> no per-frame flicker
            scene.refresh()                   # world frozen under the box
            dialog.draw(board.DISPLAY, buffer_a, LINES)
            st.dlg_shown = True
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            st.mode = EXPLORE
            scene.invalidate()                # repaint over the box next frame
        clock.tick()
        continue

    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        st.facing = RIGHT if delta_x > 0 else LEFT
    elif delta_y:
        st.facing = DOWN if delta_y > 0 else UP

    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        follow()
        walk.play(FACE_NAME[st.facing]); walk.tick(dt)
    else:
        hero.frame = st.facing * 2

    for coin in coins:
        if coin.visible and abs(hero.x - coin.x) < 12 and abs(hero.y - coin.y) < 12:
            coin.visible = False
            st.coins += 1

    if near_npc():
        hud.set("COINS %d/%d   A: TALK" % (st.coins, len(coins)))
        if btn.just_pressed(btn.A):
            st.mode = DIALOG; st.dlg_shown = False
    else:
        hud.set("COINS %d/%d" % (st.coins, len(coins)))

    scene.refresh()
    dt = clock.tick()
