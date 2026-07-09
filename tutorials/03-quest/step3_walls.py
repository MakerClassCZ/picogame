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
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3        # facing -> frame index

scene, _, _ = picogame_game.setup(background=pg.rgb565(0, 0, 0))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
hero_x, hero_y = TILE, TILE
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, GRASS))
        if char == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
scene.add(world)


# a PLACEHOLDER hero: a plain red square with a brighter bar on the facing edge, so you
# can see which way it points. 4 frames = 4 directions (frame = facing). Step 4 replaces
# it with a real drawn character.
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


def camera_follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


camera_follow()
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
        camera_follow()

    scene.refresh()
    clock.tick()
