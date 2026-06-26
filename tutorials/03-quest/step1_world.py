# Quest -- step 1: a world bigger than the screen.
#
# This third tutorial builds a top-down RPG. It teaches what Bounce and Starship
# couldn't: a scrolling world larger than the display, a camera that follows the
# hero, tile-based wall collision, a walk animation, items, an NPC you talk to, and
# light combat. Do 01-bounce and 02-starship first.
#
# What you learn here: a Tilemap can be a whole WORLD (30x20 tiles = 480x320 px,
# bigger than the 320x240 screen). scene.set_view(ox, oy) chooses which part of the
# world is on screen -- that's the camera. We centre it on the hero. The hero lives
# in WORLD coordinates; the view offset decides where that lands on screen.
#
# New: a large Tilemap from an ASCII map, shp.tileset_colors, scene.set_view.
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
MCOLS, MROWS = 30, 20
# map char -> tile value (entities sit on grass; the tile under them is grass/path)
CH2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
# tile colours for values 1..7 (value 0 is unused)
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(0, 0, 0))
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*c) for c in TILE_RGB])
world = pg.Tilemap(tileset, MCOLS, MROWS)
hero_x, hero_y = TILE, TILE                   # world pixel position of the hero
for tile_y in range(MROWS):
    row = MAP[tile_y]
    for tile_x in range(MCOLS):
        ch = row[tile_x] if tile_x < len(row) else "."
        world.tile(tile_x, tile_y, CH2TILE.get(ch, 1))
        if ch == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
scene.add(world)


def hero_bitmap():
    """A simple hero: a 16x16 body with a lighter 'face' nub on the facing edge.
    frame 0=down, 1=up, 2=left, 3=right."""
    pal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60), pg.rgb565(255, 225, 170)])
    stride = TILE * 4
    data = bytearray(stride * TILE)
    for f in range(4):
        for y in range(TILE):
            for x in range(TILE):
                face = ((f == 0 and y >= TILE - 4) or (f == 1 and y < 4) or
                        (f == 2 and x < 4) or (f == 3 and x >= TILE - 4))
                data[y * stride + f * TILE + x] = 2 if face else 1
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=pal, frames=4, stride=stride)


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=0)
scene.add(hero)


def follow():
    # centre the camera on the hero, clamped so we never show past the world edges
    ox = max(W - MCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    oy = max(H - MROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(ox), int(oy))


follow()
while True:
    scene.refresh()
    clock.tick()
