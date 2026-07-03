# Quest -- step 4: a walking animation.
#
# What you learn: time-based animation. We upgrade the hero to an 8-frame sheet --
# two frames per facing (a small step "bob") -- and drive it with
# picogame_anim.AnimatedSprite: named animations, advanced by tick(dt). While the
# hero moves we play() the animation for the current facing and tick it with the
# frame's real dt (from clock.tick()); when standing still we show the still frame.
# Using dt (not a frame counter) keeps the walk speed the same at any frame rate.
#
# New vs step 3: an 8-frame hero, picogame_anim.AnimatedSprite, play()/tick(dt),
# the dt returned by clock.tick().
#
# Run:  python3 sim/run.py tutorials/03-quest/step4_anim.py --hold RIGHT --shot /tmp/q4.png

import array
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_anim
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
SOLID = (3, 4, 5, 6)
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
FACE_NAME = ("down", "up", "left", "right")

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
    """8 frames = 4 facings x 2 walk steps. Step 1 bobs the body down 1px so the
    walk reads as motion. frame index = facing*2 + step."""
    palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60),
                            pg.rgb565(255, 225, 170), pg.rgb565(120, 40, 30)])
    stride = TILE * 8
    data = bytearray(stride * TILE)
    for f in range(4):
        for s in range(2):
            fr = f * 2 + s
            bob = s                       # bob down 1px on the second step
            for y in range(bob, TILE):
                yy = y - bob
                for x in range(TILE):
                    face = ((f == 0 and yy >= TILE - 4) or (f == 1 and yy < 4) or
                            (f == 2 and x < 4) or (f == 3 and x >= TILE - 4))
                    data[y * stride + fr * TILE + x] = 2 if face else 1
            # two feet at the bottom, swapping sides per step (extra motion cue)
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

facing = DOWN


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MAPCOLS or tile_y < 0 or tile_y >= MAPROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


follow()
dt = 1 / 30
while True:
    btn.poll()
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
        walk.play(FACE_NAME[facing])      # animate the walk while moving
        walk.tick(dt)
    else:
        hero.frame = facing * 2           # still frame for the current facing

    scene.refresh()
    dt = clock.tick()
