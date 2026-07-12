# Quest -- step 8: a quest, a goal, and a win state (capstone).
#
# What you learn: tying the systems into an actual game. The NPC gives an objective
# (collect every coin); once you have them all, talking again OPENS the door (we
# rewrite those tiles from "door" to "path", so collision lets you through); stepping
# on the shrine tile wins. A small quest-stage variable drives the dialog text and
# the door. This is the whole loop: talk -> collect -> unlock -> reach the goal.
#
# The State object now carries the whole game: hp, coins, the quest stage, and the
# mode (EXPLORE/DIALOG/WON). dialog_lines() TAKES the state (dialog_lines(st)) instead
# of reaching for globals -- the tidy payoff of grouping state in one object.
#
# New vs step 7: a quest stage, objective-driven dialog, opening the door by editing
# tiles, a goal tile + WON state, and sound (a talk blip + a win chime).
#
# BIG PICTURE: you've now hand-built an RPG -- map, camera, collision, animation,
# items, NPC, combat, quest. You DON'T have to keep hand-coding maps like this: the
# editor (editor/) lets you paint the map, place the hero/NPC/coins, and FLAG tiles
# (solid/coin/goal) visually, then the picogame_scene loader builds the scene for
# you -- the exact things this file does by hand become data. See tutorials/README.md
# and examples/picogame_platformer_scene.py for a game whose level is loaded that way.
#
# Run:  python3 sim/run.py tutorials/03-quest/step8_quest.py --shot /tmp/q8.png

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
DIR = {DOWN: (0, 1), UP: (0, -1), LEFT: (-1, 0), RIGHT: (1, 0)}   # facing -> (dx, dy) step
FACING_ANIM = ("down", "up", "side", "side")  # animation per facing (left/right share the side art)
EXPLORE, DIALOG, WON = 0, 1, 2                # game modes (int constants, not strings)
WALK_FPS = 8                                  # walk-animation speed (frames per second)
MAX_HP = 6
HURT_FRAMES = 40   # ~1.3s of mercy after a hit (at 30 fps)
FLASH_FRAMES = 3   # how long the white hit-flash shows
BACKGROUND = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

# buffer_a/buffer_b = the engine's two shared render strips; immediate-mode draws
# (the dialog/win box below) paint straight into buffer_a
scene, buffer_a, buffer_b = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# optional audio: a talk blip + a bright win chime (no asset needed). None if no backend.
try:
    import picogame_audio
    audio = picogame_audio.Audio()
    snd_talk = picogame_audio.tone(520, 30)       # short blip on dialog advance
    snd_win = picogame_audio.tone(880, 220)       # bright chime on QUEST COMPLETE
except Exception:
    audio = None
    snd_talk = snd_win = None

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
START = (TILE, TILE)
npc_x, npc_y = TILE, TILE
coin_spots, enemy_spots, door_tiles = [], [], []
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, GRASS))
        if char == "P":
            START = (tile_x * TILE, tile_y * TILE)
        elif char == "N":
            npc_x, npc_y = tile_x * TILE, tile_y * TILE
        elif char == "*":
            coin_spots.append((tile_x * TILE, tile_y * TILE))
        elif char == "E":
            enemy_spots.append((tile_x * TILE, tile_y * TILE))
        elif char == "D":
            door_tiles.append((tile_x, tile_y))
scene.add(world)

coin_bitmap = shp.circle(8, pg.rgb565(245, 215, 60))
coins = [pg.Sprite(coin_bitmap, x + 4, y + 4) for (x, y) in coin_spots]
for coin in coins:
    scene.add(coin)
slime_bitmap = shp.circle(14, pg.rgb565(120, 200, 80))
enemies = [pg.Sprite(slime_bitmap, x + 1, y + 1) for (x, y) in enemy_spots]
for enemy in enemies:
    scene.add(enemy)
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
hero = pg.Sprite(BM["down"][0], START[0], START[1])
walk = picogame_anim.AnimatedSprite(hero, {
    "down": (BM["down"], WALK_FPS, True),
    "up":   (BM["up"], WALK_FPS, True),
    "side": (BM["side"], WALK_FPS, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BACKGROUND)
dialog = ui.TextBox(pg, terminalio.FONT, 8, H - 64, W - 16, 58, WHITE, NAVY, maxlines=4)
NUMCOINS = len(coins)


class State:
    """The whole game's mutable state -- one object, passed where a function needs it."""
    def __init__(self):
        self.facing = DOWN
        self.coins = 0
        self.hp = MAX_HP
        self.hurt_cooldown = 0
        self.stage = 0                   # 0 not started, 1 collecting, 2 door open
        self.mode = EXPLORE             # EXPLORE / DIALOG / WON
        self.frame_count = 0             # frames elapsed (slimes chase every other frame)
        self.overlay_shown = False       # draw dialog/win modal once, not every frame


st = State()


def solid_at(pixel_x, pixel_y):
    tile_x, tile_y = pixel_x // TILE, pixel_y // TILE
    if tile_x < 0 or tile_x >= MAPCOLS or tile_y < 0 or tile_y >= MAPROWS:
        return True
    return world.tile(tile_x, tile_y) in SOLID


def can_walk(pixel_x, pixel_y):
    return not (solid_at(pixel_x + 2, pixel_y + 2) or solid_at(pixel_x + TILE - 3, pixel_y + 2) or
                solid_at(pixel_x + 2, pixel_y + TILE - 3) or solid_at(pixel_x + TILE - 3, pixel_y + TILE - 3))


def near(a, bx, by, d=TILE):
    # True if sprite a is within d px of the point (bx, by) on both axes (a box test)
    return abs(a.x - bx) < d and abs(a.y - by) < d


def camera_follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


def dialog_lines(st):
    if st.stage == 0:
        return ["Villager:", "Bring me all %d coins and" % NUMCOINS,
                "I'll open the shrine door.", "(press A)"]
    if st.stage == 1 and st.coins < NUMCOINS:
        return ["Villager:", "You have %d of %d coins." % (st.coins, NUMCOINS),
                "Keep looking!", "(press A)"]
    return ["Villager:", "The door is open.",
            "Seek the shrine within.", "(press A)"]


def open_door():
    for (tile_x, tile_y) in door_tiles:
        world.tile(tile_x, tile_y, PATH)              # door -> path (no longer SOLID)
    scene.invalidate()


camera_follow()
dt = 1 / 30
while True:
    btn.poll()
    st.frame_count += 1

    if st.mode == WON:
        if not st.overlay_shown:              # draw ONCE -> no per-frame flicker
            scene.refresh()
            dialog.draw(scene.display, buffer_a, ["You reached the shrine!", "", "QUEST COMPLETE", "(press A)"])
            if audio:
                audio.sfx(snd_win)            # bright chime on the win
            st.overlay_shown = True
        if btn.just_pressed(btn.A):
            st.mode = EXPLORE
            scene.invalidate()
        clock.tick()
        continue

    if st.mode == DIALOG:
        if not st.overlay_shown:              # draw ONCE -> no per-frame flicker
            scene.refresh()
            dialog.draw(scene.display, buffer_a, dialog_lines(st))
            st.overlay_shown = True
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            if audio:
                audio.sfx(snd_talk)           # blip on dialog advance
            if st.stage == 0:
                st.stage = 1
            elif st.stage == 1 and st.coins >= NUMCOINS:
                st.stage = 2
                open_door()
            st.mode = EXPLORE
            scene.invalidate()
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
        walk.play(FACING_ANIM[st.facing])
        walk.tick(dt)
    else:
        hero.bitmap = BM[FACING_ANIM[st.facing]][0]   # still: pose A of the current facing

    if btn.just_pressed(btn.B):
        ddx, ddy = DIR[st.facing]
        ax, ay = hero.x + ddx * TILE, hero.y + ddy * TILE
        for enemy in enemies:
            if enemy.visible and abs(enemy.x - ax) < TILE and abs(enemy.y - ay) < TILE:
                enemy.visible = False

    if st.frame_count % 2 == 0:
        for enemy in enemies:
            if not enemy.visible:
                continue
            # which way to the hero: -1, 0 or +1 per axis (a compact sign())
            chase_dx = (hero.x > enemy.x) - (hero.x < enemy.x)
            chase_dy = (hero.y > enemy.y) - (hero.y < enemy.y)
            if chase_dx and can_walk(enemy.x + chase_dx, enemy.y):
                enemy.move(enemy.x + chase_dx, enemy.y)
            if chase_dy and can_walk(enemy.x, enemy.y + chase_dy):
                enemy.move(enemy.x, enemy.y + chase_dy)

    if st.hurt_cooldown > 0:
        st.hurt_cooldown -= 1
        if st.hurt_cooldown == HURT_FRAMES - FLASH_FRAMES:  # end the hit-flash after 3 frames
            hero.flash = None
    else:
        for enemy in enemies:
            # 13px: slime radius (~7) + hero half-width (~8), i.e. they're touching
            if enemy.visible and near(enemy, hero.x, hero.y, 13):
                st.hp -= 1
                st.hurt_cooldown = HURT_FRAMES
                hero.flash = WHITE        # white hit-flash on damage
                if st.hp <= 0:
                    st.hp = MAX_HP
                    hero.move(START[0], START[1])
                    camera_follow()
                break

    # pick up any coin we're standing on (within ~12px on both axes = close enough)
    for coin in coins:
        if coin.visible and abs(hero.x - coin.x) < 12 and abs(hero.y - coin.y) < 12:
            coin.visible = False
            st.coins += 1

    # reach the shrine (goal tile) once the door is open
    if st.stage >= 2:
        # the tile under the hero's centre
        center_tile_x = (hero.x + TILE // 2) // TILE
        center_tile_y = (hero.y + TILE // 2) // TILE
        if world.tile(center_tile_x, center_tile_y) == GOAL:
            st.mode = WON
            st.overlay_shown = False

    if near(hero, npc.x, npc.y):
        hud.set("HP %d  COINS %d/%d  A:TALK" % (st.hp, st.coins, NUMCOINS))
        if btn.just_pressed(btn.A):
            st.mode = DIALOG
            st.overlay_shown = False
    else:
        if st.stage < 1 or st.coins < NUMCOINS:
            objective = "FIND THE COINS"
        elif st.stage >= 2:
            objective = "DOOR OPEN!"
        else:
            objective = "RETURN TO NPC"
        hud.set("HP %d  COINS %d/%d  %s" % (st.hp, st.coins, NUMCOINS, objective))

    scene.refresh()
    dt = clock.tick()
