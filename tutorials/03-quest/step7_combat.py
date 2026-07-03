# Quest -- step 7: enemies and bump combat.
#
# What you learn: simple chasing AI, taking damage, and attacking. Slimes step
# toward the hero (slower than you, and they respect walls via can_walk). Touching
# one costs HP and starts a brief "can't be hurt again" cooldown (hurt_cooldown) so one touch doesn't
# drain you instantly. Press B to swing: we defeat any slime in the tile just ahead
# of the way you're facing. HP shows in the HUD; reaching 0 sends you back to start.
#
# The State object from step 6 keeps paying off: HP, the hurt cooldown and a frame
# counter just become more `st.` fields -- no new globals, no `global` soup.
#
# New vs step 6: enemy sprites with chase AI, player HP + a brief hurt cooldown + knock-back,
# a white hit-flash (sprite.flash) on damage, a B attack in the facing direction. (A still
# talks to the NPC.)
#
# Run:  python3 sim/run.py tutorials/03-quest/step7_combat.py --hold B --shot /tmp/q7.png

import array
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
CHAR2TILE = {".": 1, "P": 1, "N": 1, "*": 1, "E": 1, ":": 2, "~": 3, "#": 4,
           "W": 5, "D": 6, "G": 7}
TILE_RGB = [(40, 120, 50), (180, 160, 110), (40, 90, 200), (20, 80, 30),
            (120, 120, 130), (150, 90, 40), (240, 210, 60)]
SOLID = (3, 4, 5, 6)
DOWN, UP, LEFT, RIGHT = 0, 1, 2, 3
DIR = {DOWN: (0, 1), UP: (0, -1), LEFT: (-1, 0), RIGHT: (1, 0)}
FACE_NAME = ("down", "up", "left", "right")
EXPLORE, DIALOG = 0, 1                        # game modes (int constants, not strings)
BACKGROUND = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)

scene, buffer_a, buffer_b = picogame_game.setup(background=BACKGROUND)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

tileset = shp.tileset_colors(TILE, TILE, [pg.rgb565(*color) for color in TILE_RGB])
world = pg.Tilemap(tileset, MAPCOLS, MAPROWS)
START = (TILE, TILE)
npc_x, npc_y = TILE, TILE
coin_spots, enemy_spots = [], []
for tile_y in range(MAPROWS):
    for tile_x in range(MAPCOLS):
        char = MAP[tile_y][tile_x] if tile_x < len(MAP[tile_y]) else "."
        world.tile(tile_x, tile_y, CHAR2TILE.get(char, 1))
        if char == "P":
            START = (tile_x * TILE, tile_y * TILE)
        elif char == "N":
            npc_x, npc_y = tile_x * TILE, tile_y * TILE
        elif char == "*":
            coin_spots.append((tile_x * TILE, tile_y * TILE))
        elif char == "E":
            enemy_spots.append((tile_x * TILE, tile_y * TILE))
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


def hero_bitmap():
    palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(210, 80, 60),
                            pg.rgb565(255, 225, 170), pg.rgb565(120, 40, 30)])
    stride = TILE * 8
    data = bytearray(stride * TILE)
    for f in range(4):
        for s in range(2):
            fr = f * 2 + s
            for y in range(s, TILE):
                yy = y - s
                for x in range(TILE):
                    face = ((f == 0 and yy >= TILE - 4) or (f == 1 and yy < 4) or
                            (f == 2 and x < 4) or (f == 3 and x >= TILE - 4))
                    data[y * stride + fr * TILE + x] = 2 if face else 1
            lx = 4 if s == 0 else 6
            for x in (lx, TILE - 1 - lx):
                data[(TILE - 1) * stride + fr * TILE + x] = 3
    return pg.Bitmap(data, TILE, TILE, format=pg.PAL8, palette=palette, frames=8,
                     stride=stride, transparent=0)


hero = pg.Sprite(hero_bitmap(), START[0], START[1], frame=0)
walk = picogame_anim.AnimatedSprite(hero, {
    "down": ([0, 1], 8, True), "up": ([2, 3], 8, True),
    "left": ([4, 5], 8, True), "right": ([6, 7], 8, True)})
scene.add(hero)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4, WHITE, BACKGROUND)
dialog = ui.TextBox(pg, terminalio.FONT, 8, H - 60, W - 16, 54, WHITE, NAVY, maxlines=4)
LINES = ["Villager:", "Slimes ahead! Press B to", "swing at them.", "(press A)"]


class State:
    """All the mutable game variables in one place (grows as the game does)."""
    def __init__(self):
        self.facing = DOWN
        self.coins = 0
        self.hp = 6
        self.hurt_cooldown = 0            # frames of mercy after a hit (i-frames)
        self.mode = EXPLORE              # EXPLORE = walking around, DIALOG = talking
        self.frame = 0                   # frame counter (slimes chase every other frame)
        self.dlg_shown = False           # draw the modal once, not every frame


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
    return abs(a.x - bx) < d and abs(a.y - by) < d


def follow():
    offset_x = max(W - MAPCOLS * TILE, min(0, W // 2 - (hero.x + TILE // 2)))
    offset_y = max(H - MAPROWS * TILE, min(0, H // 2 - (hero.y + TILE // 2)))
    scene.set_view(int(offset_x), int(offset_y))


follow()
dt = 1 / 30
while True:
    btn.poll()
    st.frame += 1

    if st.mode == DIALOG:
        if not st.dlg_shown:                  # draw ONCE -> no per-frame flicker
            scene.refresh()
            dialog.draw(board.DISPLAY, buffer_a, LINES)
            st.dlg_shown = True
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            st.mode = EXPLORE; scene.invalidate()
        clock.tick()
        continue

    delta_x = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    delta_y = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if delta_x:
        st.facing = RIGHT if delta_x > 0 else LEFT
    elif delta_y:
        st.facing = DOWN if delta_y > 0 else UP
    moved = False
    if delta_x and can_walk(hero.x + delta_x * SPEED, hero.y):
        hero.move(hero.x + delta_x * SPEED, hero.y); moved = True
    if delta_y and can_walk(hero.x, hero.y + delta_y * SPEED):
        hero.move(hero.x, hero.y + delta_y * SPEED); moved = True
    if moved:
        follow(); walk.play(FACE_NAME[st.facing]); walk.tick(dt)
    else:
        hero.frame = st.facing * 2

    # attack: defeat a slime in the tile ahead of the facing
    if btn.just_pressed(btn.B):
        ddx, ddy = DIR[st.facing]
        ax, ay = hero.x + ddx * TILE, hero.y + ddy * TILE
        for enemy in enemies:
            if enemy.visible and abs(enemy.x - ax) < TILE and abs(enemy.y - ay) < TILE:
                enemy.visible = False

    # slimes chase (slower: move every other frame) and respect walls
    if st.frame % 2 == 0:
        for enemy in enemies:
            if not enemy.visible:
                continue
            sx = (hero.x > enemy.x) - (hero.x < enemy.x)
            sy = (hero.y > enemy.y) - (hero.y < enemy.y)
            if sx and can_walk(enemy.x + sx, enemy.y):
                enemy.move(enemy.x + sx, enemy.y)
            if sy and can_walk(enemy.x, enemy.y + sy):
                enemy.move(enemy.x, enemy.y + sy)

    # take damage on contact (unless the cooldown from the last hit is still running)
    if st.hurt_cooldown > 0:
        st.hurt_cooldown -= 1              # count the "safe" frames down
        if st.hurt_cooldown == 37:        # ...and end the hit-flash after 3 frames
            hero.flash = None
    else:
        for enemy in enemies:
            if enemy.visible and near(enemy, hero.x, hero.y, 13):
                st.hp -= 1
                st.hurt_cooldown = 40     # 40 frames where another touch can't hurt you
                hero.flash = WHITE        # white blit-flash for 3 frames: "I got hit"
                if st.hp <= 0:                # down -> back to start, full HP
                    st.hp = 6
                    hero.move(START[0], START[1])
                    follow()
                break

    for coin in coins:
        if coin.visible and abs(hero.x - coin.x) < 12 and abs(hero.y - coin.y) < 12:
            coin.visible = False; st.coins += 1

    if near(hero, npc.x, npc.y):
        hud.set("HP %d  COINS %d/%d  A:TALK B:SWING" % (st.hp, st.coins, len(coins)))
        if btn.just_pressed(btn.A):
            st.mode = DIALOG; st.dlg_shown = False
    else:
        hud.set("HP %d  COINS %d/%d" % (st.hp, st.coins, len(coins)))

    scene.refresh()
    dt = clock.tick()
