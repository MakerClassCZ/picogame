# Quest -- step 4: a walking animation.
#
# What you learn: time-based animation -- and giving the hero real art. We retire the
# placeholder square and draw a proper character from ASCII masks (down / up / side, with
# LEFT the side view mirrored by flip_x), with TWO poses per facing, then drive the walk
# with picogame_anim.AnimatedSprite: play(name) picks the facing's animation, tick(dt)
# advances it with the real dt from clock.tick() (so the walk speed is frame-rate
# independent); standing still we show the still pose.
#
# Here the frames are hand-drawn masks (no asset), so we animate by SWAPPING whole
# bitmaps. A REAL game usually loads a proper image sprite-sheet (a PNG baked with
# tools/png2picogame.py -> one multi-frame Bitmap) and animates by frame INDEX -- the
# same AnimatedSprite drives that too. See the bonus_art step / the assets guide.
#
# New vs step 3: the drawn masked hero (replacing the placeholder square) + sprite.flip_x
# for LEFT, two walk poses per facing, picogame_anim.AnimatedSprite over a bitmap list,
# play()/tick(dt), the dt from clock.tick().
#
# Run:  python3 sim/run.py tutorials/03-quest/step4_anim.py --hold RIGHT --shot /tmp/q4.png

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
FACING_ANIM = ("down", "up", "side", "side")   # animation per facing (left/right share the side art)
WALK_FPS = 8

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
# each entry:  name: (bitmap list, frames-per-second, loop?) -- AnimatedSprite accepts
# a list of Bitmaps to swap in, not only frame indices into one sheet
walk = picogame_anim.AnimatedSprite(hero, {
    "down": (BM["down"], WALK_FPS, True),
    "up":   (BM["up"], WALK_FPS, True),
    "side": (BM["side"], WALK_FPS, True)})
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


def camera_follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


camera_follow()
dt = 1 / 30      # assume one 30fps frame for the first tick; clock.tick() returns real dt after that
while True:
    btn.poll()
    # True/False count as 1/0, so this is -1 (left), 0, or +1 (right)
    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        facing = RIGHT if delta_x > 0 else LEFT
    elif delta_y:
        facing = DOWN if delta_y > 0 else UP
    hero.flip_x = (facing == LEFT)        # mirror the side art for LEFT

    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        camera_follow()
        walk.play(FACING_ANIM[facing])    # animate the walk while moving
        walk.tick(dt)
    else:
        hero.bitmap = BM[FACING_ANIM[facing]][0]   # still: pose A of the current facing

    scene.refresh()
    dt = clock.tick()
