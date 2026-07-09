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
# tile values (frame index into the colour tileset; 0 = empty)
GRASS, PATH, WATER, TREE, WALL, DOOR, GOAL = 1, 2, 3, 4, 5, 6, 7
CHAR2TILE = {".": GRASS, "P": GRASS, "N": GRASS, "*": GRASS, "E": GRASS,
             ":": PATH, "~": WATER, "#": TREE, "W": WALL, "D": DOOR, "G": GOAL}
TILE_RGB = [(40, 120, 50),    # GRASS
            (180, 160, 110),  # PATH
            (40, 90, 200),    # WATER
            (20, 80, 30),     # TREE
            (120, 120, 130),  # WALL
            (150, 90, 40),    # DOOR
            (240, 210, 60)]   # GOAL
SOLID = (WATER, TREE, WALL, DOOR)         # these tiles block movement
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
FACING_ANIM = ("down", "up", "side", "side")  # animation per facing (left/right share the side art)
EXPLORE, DIALOG = 0, 1                        # game modes (int constants, not strings)
WALK_FPS = 8                                  # walk-animation speed (frames per second)
BACKGROUND = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

# buffer_a/buffer_b = the engine's two shared render strips; immediate-mode draws
# (the dialog box below) paint straight into buffer_a
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
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, GRASS))
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


# --- the hero: ASCII pixel art you can edit. '#' = a pixel, '.' = transparent. One
# colour = a 1-bit silhouette; the FACING reads from the shape: DOWN has eyes, UP is
# the back of the head, SIDE is a profile with a nose (LEFT = SIDE mirrored at runtime
# with flip_x). Two poses per facing make the walk -- the legs scissor between A and B.
HERO_COLOR = pg.rgb565(235, 90, 70)
DOWN_A = [
    "................",
    ".....####.......",
    "....######......",
    "....######......",
    "....#.##.#......",   # eye gaps -> the face
    "....######......",
    ".....####.......",
    "...########.....",
    "..##########....",
    "..##########....",
    "..##########....",
    "...########.....",
    "....##..##......",
    "...###..##......",
    "..###...##......",   # left foot forward
    "..##............",
]
DOWN_B = [
    "................",
    ".....####.......",
    "....######......",
    "....######......",
    "....#.##.#......",
    "....######......",
    ".....####.......",
    "...########.....",
    "..##########....",
    "..##########....",
    "..##########....",
    "...########.....",
    "....##..##......",
    "....##..###.....",
    "....##...###....",   # right foot forward
    "..........##....",
]
UP_A = [
    "................",
    ".....####.......",
    "....######......",
    "....######......",
    "....######......",   # solid head = the hero's back
    "....######......",
    ".....####.......",
    "...########.....",
    "..##########....",
    "..##########....",
    "..##########....",
    "...########.....",
    "....##..##......",
    "...###..##......",
    "..###...##......",
    "..##............",
]
UP_B = [
    "................",
    ".....####.......",
    "....######......",
    "....######......",
    "....######......",
    "....######......",
    ".....####.......",
    "...########.....",
    "..##########....",
    "..##########....",
    "..##########....",
    "...########.....",
    "....##..##......",
    "....##..###.....",
    "....##...###....",
    "..........##....",
]
SIDE_A = [
    "................",
    ".....####.......",
    "....#####.......",
    "....######......",
    "....#####.#.....",   # nose nub -> faces right (flip_x -> left)
    "....######......",
    ".....####.......",
    "....######......",
    "....######.#....",   # arm swung forward
    "....######.#....",
    "....######......",
    ".....####.......",
    "...##....##.....",   # legs split
    "..##......##....",
    "..##......##....",
    "..#........#....",
]
SIDE_B = [
    "................",
    ".....####.......",
    "....#####.......",
    "....######......",
    "....#####.#.....",
    "....######......",
    ".....####.......",
    "....######......",
    "....######......",   # arm tucked in
    "....######......",
    "....######......",
    ".....####.......",
    ".....####.......",   # legs pass under the body
    ".....####.......",
    "....##..##......",
    "....#....#......",
]
BM = {"down": [shp.from_mask(DOWN_A, HERO_COLOR), shp.from_mask(DOWN_B, HERO_COLOR)],
      "up":   [shp.from_mask(UP_A, HERO_COLOR), shp.from_mask(UP_B, HERO_COLOR)],
      "side": [shp.from_mask(SIDE_A, HERO_COLOR), shp.from_mask(SIDE_B, HERO_COLOR)]}
hero = pg.Sprite(BM["down"][0], hero_x, hero_y)
walk = picogame_anim.AnimatedSprite(hero, {
    "down": (BM["down"], WALK_FPS, True),
    "up":   (BM["up"], WALK_FPS, True),
    "side": (BM["side"], WALK_FPS, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BACKGROUND)
dialog = ui.TextBox(pg, terminalio.FONT, 8, H - 64, W - 16, 58, WHITE, NAVY, maxlines=4)
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


def camera_follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


camera_follow()
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
    hero.flip_x = (st.facing == LEFT)         # mirror the side art for LEFT

    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        camera_follow()
        walk.play(FACING_ANIM[st.facing])     # animate the walk while moving
        walk.tick(dt)
    else:
        hero.bitmap = BM[FACING_ANIM[st.facing]][0]   # still: pose A of the current facing

    # pick up any coin we're standing on (within ~12px on both axes = close enough)
    for coin in coins:
        if coin.visible and abs(hero.x - coin.x) < 12 and abs(hero.y - coin.y) < 12:
            coin.visible = False
            st.coins += 1

    if near_npc():
        hud.set("COINS %d/%d   A: TALK" % (st.coins, len(coins)))
        if btn.just_pressed(btn.A):
            st.mode = DIALOG
            st.dlg_shown = False
    else:
        hud.set("COINS %d/%d" % (st.coins, len(coins)))

    scene.refresh()
    dt = clock.tick()
