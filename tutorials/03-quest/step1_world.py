# Quest -- step 1: a world bigger than the screen.
#
# This third tutorial builds a top-down RPG. It teaches what Bounce and Starship
# couldn't: a scrolling world larger than the display, a camera that follows the
# hero, tile-based wall collision, a walk animation, items, an NPC you talk to, and
# light combat. Do 01-bounce and 02-starship first.
#
# What you learn here: a Tilemap can be a whole WORLD (30x20 tiles = 480x320 px,
# bigger than the 320x240 screen). scene.set_view(offset_x, offset_y) chooses which part of the
# world is on screen -- that's the camera. We centre it on the hero. The hero lives
# in WORLD coordinates; the view offset decides where that lands on screen.
#
# New: a large Tilemap from an ASCII map, shp.tileset_colors, scene.set_view, and a
# placeholder hero (a red square with a facing edge). Step 4 gives it real drawn art.
#
# Run:  python3 sim/run.py tutorials/03-quest/step1_world.py --shot /tmp/q1.png

import array
import picogame as pg
import picogame_game
import picogame_clock
import picogame_shapes as shp

W, H = 320, 240
TILE = 16

# . grass  : path  ~ water(solid)  # tree(solid)  W wall(solid)  D door  G goal
# P player  N npc  * coin  E enemy
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
# map char -> tile value (entities sit on grass; the tile under them is grass/path)
# tile values (frame index into the colour tileset; 0 = empty)
GRASS, PATH, WATER, TREE, WALL, DOOR, GOAL = 1, 2, 3, 4, 5, 6, 7
CHAR2TILE = {".": GRASS, "P": GRASS, "N": GRASS, "*": GRASS, "E": GRASS,
             ":": PATH, "~": WATER, "#": TREE, "W": WALL, "D": DOOR, "G": GOAL}
# tile colours for values 1..7 (value 0 is unused)
TILE_RGB = [(40, 120, 50),    # GRASS
            (180, 160, 110),  # PATH
            (40, 90, 200),    # WATER
            (20, 80, 30),     # TREE
            (120, 120, 130),  # WALL
            (150, 90, 40),    # DOOR
            (240, 210, 60)]   # GOAL

scene, _, _ = picogame_game.setup(background=pg.rgb565(0, 0, 0))
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
hero_x, hero_y = TILE, TILE                   # world pixel position of the hero
# build the Tilemap cell by cell from the ASCII map above
for tile_y in range(MAPROWS):
    row = MAP[tile_y]
    for tile_x in range(MAPCOLS):
        char = row[tile_x] if tile_x < len(row) else "."   # rows are full width; "." is just a safety net
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, GRASS))   # unknown chars fall back to GRASS
        if char == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
scene.add(world)


# a PLACEHOLDER hero: a plain red square with a brighter bar on the facing edge, so you
# can see which way it points. 4 frames = 4 directions (frame = facing). We prototype
# with a shape now and draw a real animated character in step 4.
RED = pg.rgb565(210, 80, 60)
EDGE = pg.rgb565(255, 225, 170)


def hero_bitmap():
    palette = array.array("H", [pg.rgb565(0, 0, 0), RED, EDGE])   # index 0 = transparent
    stride = TILE * 4                                             # 4 frames side by side, 1 byte/px
    data = bytearray(stride * TILE)
    for facing in range(4):                                       # 0 down, 1 up, 2 left, 3 right
        for y in range(TILE):
            for x in range(TILE):
                on_facing_edge = ((facing == 0 and y >= TILE - 3) or (facing == 1 and y < 3) or
                                  (facing == 2 and x < 3) or (facing == 3 and x >= TILE - 3))
                data[y * stride + facing * TILE + x] = 2 if on_facing_edge else 1
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=palette, frames=4, stride=stride)


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=0)
scene.add(hero)


def camera_follow():
    # centre the camera on the hero, clamped so we never show past the world edges
    # The view offset = how far the world is shifted left/up on screen: 0 (world edge
    # at screen edge) down to negative as we scroll right/down.
    offset_x = W // 2 - (hero.x + TILE // 2)          # centre the hero...
    offset_x = min(0, offset_x)                       # ...but never past the left edge
    offset_x = max(W - MAPCOLS * TILE, offset_x)      # ...nor past the right edge
    offset_y = H // 2 - (hero.y + TILE // 2)          # centre the hero...
    offset_y = min(0, offset_y)                       # ...but never past the top edge
    offset_y = max(H - MAPROWS * TILE, offset_y)      # ...nor past the bottom edge
    scene.set_view(int(offset_x), int(offset_y))


camera_follow()
while True:
    scene.refresh()
    clock.tick()
