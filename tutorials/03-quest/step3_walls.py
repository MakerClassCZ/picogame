# Quest -- step 3: walls (tile-based collision).
#
# What you learn: stop the hero walking through water/trees/walls. Convert a world
# pixel to a tile (tx = px // TILE), look the tile up, and treat some values as
# SOLID. can_walk() probes the hero's body (its four corners, inset a little) so it
# can't clip into a wall. We test the X and Y moves SEPARATELY, so the hero slides
# along a wall instead of sticking when you push diagonally into it.
#
# New vs step 2: solid_at()/can_walk() pixel->tile collision, per-axis movement.
#
# Run:  python3 sim/run.py tutorials/03-quest/step3_walls.py --hold RIGHT --shot /tmp/q3.png

import array
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

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
SOLID = (3, 4, 5, 6)                          # water, tree, wall, door block movement
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3

scene, _, _ = picogame_game.setup(background=pg.rgb565(0, 0, 0))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
hero_x, hero_y = TILE, TILE
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, 1))
        if char == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
scene.add(world)


def hero_bitmap():
    palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60), pg.rgb565(255, 225, 170)])
    stride = TILE * 4
    data = bytearray(stride * TILE)
    for f in range(4):
        for y in range(TILE):
            for x in range(TILE):
                face = ((f == 0 and y >= TILE - 4) or (f == 1 and y < 4) or
                        (f == 2 and x < 4) or (f == 3 and x >= TILE - 4))
                data[y * stride + f * TILE + x] = 2 if face else 1
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=palette, frames=4, stride=stride)


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=DOWN)
scene.add(hero)


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MAPCOLS or tile_y < 0 or tile_y >= MAPROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    # probe the hero's body corners (inset 2px) -- all must be free
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def follow():
    ox = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    oy = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(ox), int(oy))


follow()
while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        hero.frame = RIGHT if delta_x > 0 else LEFT
    elif delta_y:
        hero.frame = DOWN if delta_y > 0 else UP

    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):    # test X alone
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):    # then Y alone -> slide
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        follow()

    scene.refresh()
    clock.tick()
