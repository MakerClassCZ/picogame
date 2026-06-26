# A Super-Mario-style side-scroller on picogame - the genre we didn't have yet.
# Ties together: a LONG horizontal tilemap level (much wider than the screen) with
# a camera that follows the player (scene.set_view, horizontal), platformer gravity
# + tile collision, stompable walking enemies, collectible coins (tilemap tiles),
# pits, a goal flag, AND a coins/lives HUD as a FIXED scene layer (the new
# camera-independent layer) over the scrolling world. Generated art + picogame_ui.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_font.py, picogame_ui.py, picogame_shapes.py. Needs the latest firmware.

import array
import random
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import terminalio
import picogame_ui as ui
import picogame_shapes as shp
import picogame_tiles as tiles

W, H = 320, 240
TILE = 16
ROWS = H // TILE                 # 15
COLS = 80                        # level is 80*16 = 1280 px wide
LEVEL_W = COLS * TILE
BG = pg.rgb565(90, 150, 230)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
jbuf = picogame_input.Timer(6)     # jump buffer: honour a jump pressed just before landing
coyote = picogame_input.Timer(5)   # coyote time: still jump a few frames after leaving a ledge

DEBUG = False      # set True for a serial trace of the jump path (button/pos/vel/jump-decision)

# Tileset: 0 empty, 1 ground/brick (solid), 2 coin, 3 goal flag.
# TileFlags maps each tile INDEX to its meaning once, so collision/coin/goal are one-liners
# (tf.at_px / tf.at) instead of hand-rolled "== 1 / == 2 / == 3" index checks scattered around.
tf = tiles.TileFlags({1: tiles.SOLID, 2: tiles.COIN, 3: tiles.EXIT}, tile_px=TILE)
stride = TILE * 4
tdata = bytearray(stride * TILE)
for y in range(TILE):
    for x in range(TILE):
        tdata[y * stride + 1 * TILE + x] = 1                     # ground = full
        if abs(x - TILE // 2) <= 3 and abs(y - TILE // 2) <= 4:  # coin = dot
            tdata[y * stride + 2 * TILE + x] = 2
        if x in (6, 7, 8) or (y < 9 and 6 <= x <= 8 + (8 - y)):  # goal = flag-ish
            tdata[y * stride + 3 * TILE + x] = 3
tpal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(150, 90, 40),
                         pg.rgb565(245, 215, 50), pg.rgb565(40, 200, 80)])
tileset = pg.Bitmap(tdata, TILE, TILE, format=pg.PAL8, palette=tpal,
                    frames=4, stride=stride, transparent=0)
level = pg.Tilemap(tileset, COLS, ROWS)
scene.add(level)

PLAYER_H = 15                          # player rect height; anchor is bottom -> head at py-PLAYER_H
player = pg.Sprite(shp.rect(12, PLAYER_H, pg.rgb565(230, 40, 40)), 0, 0)
player.anchor = (0.5, 1.0)
enemies = [pg.Sprite(shp.rect(14, 14, pg.rgb565(150, 80, 40)), 0, 0, visible=False)
           for _ in range(8)]
for e in enemies:
    e.anchor = (0.5, 1.0)
    e.data = {}
scene.add_all(enemies)
scene.add(player)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4,
                  pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 0))   # fixed layer

_MV = [0, 0, False]
S = {}


def build_level():
    enemy_spawns = []
    coins = 0
    for ty in range(ROWS):
        for tx in range(COLS):
            level.tile(tx, ty, 0)
    # ground (2 tall) with a few pits
    pits = set()
    for g in (18, 19, 34, 35, 52):
        pits.add(g)
    for tx in range(COLS):
        if tx in pits:
            continue                 # leave a gap (pit) here
        level.tile(tx, ROWS - 1, 1)
        level.tile(tx, ROWS - 2, 1)
    # floating platforms
    for (px, py, ln) in ((10, 9, 4), (24, 8, 3), (40, 7, 5), (58, 9, 4), (64, 6, 4)):
        for k in range(ln):
            level.tile(px + k, py, 1)
    # coins above ground/platforms
    for (cx, cy, ln) in ((11, 7, 4), (25, 6, 3), (41, 5, 5), (28, 12, 3), (60, 7, 4)):
        for k in range(ln):
            level.tile(cx + k, cy, 2)
            coins += 1
    # goal flag near the end
    level.tile(COLS - 4, ROWS - 3, 3)
    level.tile(COLS - 4, ROWS - 4, 3)
    # enemy spawn columns (on the ground)
    for tx in (14, 30, 44, 48, 63):
        enemy_spawns.append(tx)
    S["coins_total"] = coins
    return enemy_spawns


def spawn_enemies(cols):
    for i, e in enumerate(enemies):
        if i < len(cols):
            e.data.update(on=True, x=cols[i] * TILE + 8.0, y=(ROWS - 2) * TILE, dir=-1)
            e.move(int(e.data["x"]), int(e.data["y"]))
            e.visible = True
        else:
            e.data["on"] = False
            e.visible = False


def solid_at(px, py):
    tx, ty = px // TILE, py // TILE
    if tx < 0 or tx >= COLS or ty < 0 or ty >= ROWS:
        return False
    return tf.at(level, tx, ty, tiles.B_SOLID)


def move_v(x, y, vy, hw):
    # ONE-WAY platforms: you jump UP through a platform from below and land on its TOP when falling.
    if vy > 0:                                   # falling
        # If the BODY (mid-height) is embedded in a platform - i.e. we jumped UP into it - fall
        # straight out the bottom (one-way pass-through, no getting stuck). Testing mid-body, not
        # the feet, is key: when simply STANDING, the feet sit on the platform's top edge (which
        # reads as "in" the tile) but the body is clear, so we still land normally.
        mid = y - PLAYER_H // 2
        if solid_at(x - hw + 2, mid) or solid_at(x + hw - 2, mid):
            _MV[0], _MV[1], _MV[2] = y + int(vy), vy, False
            return
        steps = int(vy)
        while steps > 0:
            if solid_at(x - hw + 2, y + 1) or solid_at(x + hw - 2, y + 1):
                _MV[0], _MV[1], _MV[2] = y, 0, True     # landed on the platform top
                return
            y += 1
            steps -= 1
        _MV[0], _MV[1], _MV[2] = y, vy, False
    else:                                        # rising: pass up through platforms (one-way)
        _MV[0], _MV[1], _MV[2] = y + int(vy), vy, False


def follow():
    ox = max(W - LEVEL_W, min(0, W // 2 - int(S["px"])))
    scene.set_view(int(ox), 0)


def reset_player():
    S["px"], S["py"] = 40.0, (ROWS - 2) * TILE
    S["vy"] = 0.0
    S["landed"] = False


def new_game():
    S.update(coins=0, lives=3, score=0)
    cols = build_level()
    spawn_enemies(cols)
    reset_player()
    follow()


new_game()
print("LEFT/RIGHT run, UP/B jump. Stomp enemies, grab coins, reach the green flag.")
frame = 0
while True:
    btn.poll()
    frame += 1

    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    if dx:
        nx = S["px"] + dx * 3
        if not (solid_at(int(nx) + dx * 6, int(S["py"]) - 4) or
                solid_at(int(nx) + dx * 6, int(S["py"]) - 12)):
            S["px"] = max(6, min(LEVEL_W - 6, nx))
    jpress = btn.just_pressed(btn.UP) or btn.just_pressed(btn.B)     # rising edge of either jump key
    jbuf.feed(jpress)                                                # remember an early jump press
    coyote.feed(S["landed"])                                         # remember being grounded
    jfired = coyote.is_active and jbuf.consume()
    if jfired:
        S["vy"] = -11.0
        S["landed"] = False
        coyote.t = 0                                                 # one jump per ledge window

    if DEBUG:
        # Print only on interesting events (a jump key edge, a jump firing, a landed change)
        # plus a 1 Hz heartbeat - enough to see WHY a press did/didn't become a jump, without
        # flooding the 30 fps serial. Read it on the USB console while jumping on HW.
        landed = S["landed"]
        if jpress or jfired or landed != S.get("_dbg_landed") or frame % 30 == 0:
            print("f%d UP=%d B=%d jpress=%d jbuf=%d coyote=%d landed=%d FIRE=%d py=%d vy=%.1f"
                  % (frame, btn.is_pressed(btn.UP), btn.is_pressed(btn.B), jpress,
                     jbuf.t, coyote.t, landed, jfired, int(S["py"]), S["vy"]))
        S["_dbg_landed"] = landed

    S["vy"] = min(7.0, S["vy"] + 0.6)
    move_v(int(S["px"]), int(S["py"]), S["vy"], 6)
    S["py"] = float(_MV[0])
    S["vy"] = _MV[1]
    S["landed"] = _MV[2]
    player.move(int(S["px"]), int(S["py"]))

    # fell in a pit
    if S["py"] > H + 20:
        S["lives"] -= 1
        if S["lives"] < 0:
            new_game()
        else:
            reset_player()
        follow()
        continue

    # coins: check the tile at the player's chest
    ctx, cty = int(S["px"]) // TILE, (int(S["py"]) - 8) // TILE
    if 0 <= ctx < COLS and 0 <= cty < ROWS and tf.at(level, ctx, cty, tiles.B_COIN):
        level.tile(ctx, cty, 0)
        S["coins"] += 1
        S["score"] += 100
    # goal
    gtx = int(S["px"]) // TILE
    if tf.at(level, gtx, ROWS - 3, tiles.B_EXIT):
        S["score"] += 1000
        new_game()

    # enemies
    for e in enemies:
        if not e.data.get("on"):
            continue
        nx = e.data["x"] + e.data["dir"] * 1.2
        # turn at wall or ledge
        if solid_at(int(nx) + e.data["dir"] * 7, int(e.data["y"]) - 6) or \
                not solid_at(int(nx) + e.data["dir"] * 7, int(e.data["y"]) + 2):
            e.data["dir"] = -e.data["dir"]
        else:
            e.data["x"] = nx
            e.move(int(nx), int(e.data["y"]))
        # player interaction
        if abs(e.data["x"] - S["px"]) < 12 and abs(e.data["y"] - S["py"]) < 16:
            if S["vy"] > 1 and S["py"] < e.data["y"] - 4:      # stomp
                e.data["on"] = False
                e.visible = False
                S["vy"] = -7.0
                S["score"] += 200
            else:                                              # hurt
                S["lives"] -= 1
                if S["lives"] < 0:
                    new_game()
                else:
                    reset_player()
                follow()
                break

    follow()
    hud.set("COINS %d/%d  LIVES %d  %05d" % (S["coins"], S["coins_total"], max(0, S["lives"]), S["score"]))
    scene.refresh()
    clock.tick()
