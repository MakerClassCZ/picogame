# Quest -- step 2: walk around, camera follows.
#
# What you learn: world vs screen coordinates. The hero moves in WORLD space; after
# each move we call follow() to re-aim the camera. Near the world edges the clamp in
# follow() stops the camera and the hero walks toward the screen edge instead -- the
# classic top-down feel. The hero also FACES the way it moves (frame = facing).
# There's no wall collision yet, so you can walk over water and trees (step 3 fixes
# that).
#
# New vs step 1: 4-direction input, facing (sprite.frame), calling follow() on move.
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
MCOLS, MROWS = 30, 20
CH2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3            # facing -> frame

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(0, 0, 0))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*c) for c in TILE_RGB])
world = pg.Tilemap(tileset, MCOLS, MROWS)
hero_x, hero_y = TILE, TILE
for tile_y in range(MROWS):
    for tile_x in range(MCOLS):
        ch = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CH2TILE.get(ch, 1))
        if ch == "P":
            hero_x, hero_y = tile_x * TILE, tile_y * TILE
scene.add(world)


def hero_bitmap():
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


hero = pg.Sprite(hero_bitmap(), hero_x, hero_y, frame=DOWN)
scene.add(hero)


def follow():
    ox = max(W - MCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    oy = max(H - MROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(ox), int(oy))


follow()
while True:
    btn.poll()
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        hero.frame = RIGHT if delta_x > 0 else LEFT     # face horizontally
    elif delta_y:
        hero.frame = DOWN if delta_y > 0 else UP        # face vertically
    if delta_x or delta_y:
        hero.move(hero.x + delta_x * SPEED, hero.y + delta_y * SPEED)
        follow()

    scene.refresh()
    clock.tick()
