# Quest -- step 2: walk around, camera follows.
#
# What you learn: world vs screen coordinates. The hero moves in WORLD space; after
# each move we call camera_follow() to re-aim the camera. Near the world edges the clamp in
# camera_follow() stops the camera and the hero walks toward the screen edge instead -- the
# classic top-down feel. The hero also FACES the way it moves -- its `frame` picks the
# direction (0 down, 1 up, 2 left, 3 right). There's no wall collision yet, so you can
# walk over water and trees (step 3 fixes that).
#
# New vs step 1: 4-direction input, facing via sprite.frame, camera_follow() on move.
#
# Run:  python3 sim/run.py tutorials/03-quest/step2_walk.py --hold DOWN --shot /tmp/q2.png

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
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3            # facing -> frame index

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


def camera_follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


camera_follow()
while True:
    btn.poll()
    # True/False count as 1/0, so this is -1 (left), 0, or +1 (right)
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        hero.frame = RIGHT if delta_x > 0 else LEFT     # face horizontally
    elif delta_y:
        hero.frame = DOWN if delta_y > 0 else UP        # face vertically
    if delta_x or delta_y:
        hero.move(hero.x + delta_x * SPEED, hero.y + delta_y * SPEED)
        camera_follow()

    scene.refresh()
    clock.tick()
