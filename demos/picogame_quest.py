# Picogame Quest
# Representative slice exercising the engine's WEAK SPOTS for non-action games:
#   * tilemap overworld + camera (scene.set_view follows the player),
#   * 4-direction walk + AABB-vs-solid-tile collision,
#   * an NPC you talk to -> a multi-line DIALOG box (screen-space overlay),
#   * random encounters -> a TURN-BASED BATTLE screen (menu cursor, HP/MP bars,
#     the original's damage/XP formulas), win -> XP -> level up.
# This is the first text/menu/state-machine-heavy game on the engine, so it's the
# real ergonomics test for UI. See ENGINE_ERGONOMICS.md.
#
# Copy with picogame_game.py, picogame_input.py, picogame_clock.py,
# picogame_font.py. Needs the latest firmware. Generated art.

import array
import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_font
import picogame_ui as ui
import picogame_tiles as tiles

W, H = 320, 240
BG = pg.rgb565(20, 60, 30)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

TILE = 16
# Overworld: # tree(solid), ~ water(solid), . grass, : path, N npc, P player
OVER = [
    "########################",
    "#......::::::..........#",
    "#..##..:..~~..:..####..#",
    "#..##..:..~~..:........#",
    "#......:......:..N.....#",
    "#..:::::::::::::::::...#",
    "#..:..........:.....##.#",
    "#..:..####....:..~~.##.#",
    "#..:..####....:..~~....#",
    "#..:..........:.......##",
    "#..::::::P:::::........#",
    "#.............:..####..#",
    "#..~~~........:..####..#",
    "#..~~~..####..:........#",
    "#.......####..::::::...#",
    "########################",
]
MROWS = len(OVER)
MCOLS = len(OVER[0])


def solid(w, h, *cols):
    pal = array.array("H", (pg.rgb565(0, 0, 0),) + cols)
    return pg.Bitmap(bytearray(b"\x01" * (w * h)), w, h, format=pg.PAL8,
                     palette=pal, transparent=None)


def tile_frame(buf, stride, f, fill):
    for y in range(TILE):
        for x in range(TILE):
            buf[y * stride + f * TILE + x] = fill


# tileset frames: 0 grass, 1 tree, 2 water, 3 path
stride = TILE * 4
atlas = bytearray(stride * TILE)
tile_frame(atlas, stride, 0, 1)   # grass
tile_frame(atlas, stride, 1, 2)   # tree
tile_frame(atlas, stride, 2, 3)   # water
tile_frame(atlas, stride, 3, 4)   # path
tpal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(40, 120, 50),
                         pg.rgb565(20, 80, 30), pg.rgb565(40, 90, 200),
                         pg.rgb565(180, 160, 110)])
tileset = pg.Bitmap(atlas, TILE, TILE, format=pg.PAL8, palette=tpal,
                    frames=4, stride=stride, transparent=None)

world = pg.Tilemap(tileset, MCOLS, MROWS)
npc_tile = (16, 4)
player_tile = (8, 10)
for ty in range(MROWS):
    for tx in range(MCOLS):
        ch = OVER[ty][tx]
        v = {"#": 1, "~": 2, ":": 3}.get(ch, 0)
        world.tile(tx, ty, v)
        if ch == "N":
            npc_tile = (tx, ty)
        elif ch == "P":
            player_tile = (tx, ty)
scene.add(world)

# Tile metadata: trees (1) and water (2) are solid. TileFlags + at_px replaces the
# hand-rolled solid_at side table and probe boilerplate.
tflags = tiles.TileFlags({1: tiles.SOLID, 2: tiles.SOLID}, tile_px=TILE)

npc = pg.Sprite(solid(TILE, TILE, pg.rgb565(230, 200, 60)),
                npc_tile[0] * TILE, npc_tile[1] * TILE)
# player: 4 generated facing frames (a body with a coloured "face" nub)
pframes = bytearray(TILE * 4 * TILE)
pstride = TILE * 4
for f in range(4):
    for y in range(TILE):
        for x in range(TILE):
            v = 1
            if (f == 0 and y < 4) or (f == 1 and y >= TILE - 4) or \
               (f == 2 and x < 4) or (f == 3 and x >= TILE - 4):
                v = 2
            pframes[y * pstride + f * TILE + x] = v
ppal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(220, 80, 60),
                         pg.rgb565(255, 230, 180)])
player_bm = pg.Bitmap(pframes, TILE, TILE, format=pg.PAL8, palette=ppal,
                      frames=4, stride=pstride, transparent=None)
player = pg.Sprite(player_bm, player_tile[0] * TILE, player_tile[1] * TILE)
scene.add_all([npc, player])

# battle enemy sprite (drawn screen-space in battle mode); preallocated + reused
enemy_bm = solid(48, 48, pg.rgb565(150, 60, 200))
enemy_sprite = pg.Sprite(enemy_bm, W // 2 - 24, 50)
_ENEMY_LIST = [enemy_sprite]
_EMPTY = []

# ---- UI: now uses picogame_ui (TextBox + Menu) instead of a hand-rolled box ----
DIR = ((0, -1), (0, 1), (-1, 0), (1, 0))   # up/down/left/right -> player frame
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(10, 10, 40)
# Overworld dialog = an in-scene Panel (Canvas + HUD labels as scene layers): painted by the one
# scene.refresh() per frame, so it never fights the world for the screen (no flicker). This is the
# journey-demo approach; ui.TextBox (used below for the battle screen) is for screen-space screens.
dlg = ui.SceneBox(scene, pg, terminalio.FONT, 8, H - 66, W - 16, 58, WHITE, NAVY, nlines=4,
               border=pg.rgb565(120, 140, 220))
enemy_box = ui.TextBox(pg, terminalio.FONT, 8, 8, W - 16, 20,
                       pg.rgb565(255, 200, 200), pg.rgb565(30, 8, 8), maxlines=1)
msg_box = ui.TextBox(pg, terminalio.FONT, 8, H - 70, W - 16, 22,
                     pg.rgb565(255, 255, 120), NAVY, maxlines=1)
stats_box = ui.TextBox(pg, terminalio.FONT, 8, H - 96, W - 16, 20, WHITE, NAVY, maxlines=1)
bmenu = ui.Menu(pg, terminalio.FONT, 8, H - 72, ["ATTACK", "MAGIC", "HEAL", "FLEE"],
                WHITE, NAVY)

P = {}


def new_game():
    P.update(level=1, hp=20, hpmax=20, mp=10, mpmax=10, atk=5, dfn=7, spd=3,
             xp=0, gold=0, steps=0, mode="over", facing=1,
             px=player_tile[0] * TILE, py=player_tile[1] * TILE,
             menu=0, enemy=None, msg="", msg_t=0)
    follow()


def solid_at(px, py):
    if px < 0 or px >= MCOLS * TILE or py < 0 or py >= MROWS * TILE:
        return True
    return tflags.at_px(world, px, py, tiles.B_SOLID)


def can_walk(px, py):
    # AABB probe (player is ~TILE, test its 4 mid-edges)
    return not (solid_at(px + 2, py + 2) or solid_at(px + TILE - 3, py + 2) or
                solid_at(px + 2, py + TILE - 3) or solid_at(px + TILE - 3, py + TILE - 3))


def follow():
    ox = max(W - MCOLS * TILE, min(0, W // 2 - (P["px"] + TILE // 2)))
    oy = max(H - MROWS * TILE, min(0, H // 2 - (P["py"] + TILE // 2)))
    scene.set_view(int(ox), int(oy))


def start_battle():
    lv = P["level"]
    region = 0
    P["enemy"] = {"hp": 3 * lv + 4, "hpmax": 3 * lv + 4, "atk": 6 * lv // 2 + 2,
                  "dfn": 3 * lv, "spd": 5 * lv, "lv": lv}
    P["mode"] = "battle"
    P["menu"] = 0
    P["msg"] = "A wild slime appears!"
    P["msg_t"] = 40
    P["bsig"] = None        # force a fresh battle-screen draw on entry
    scene.invalidate()


def battle_msg(s, t=30):
    P["msg"] = s
    P["msg_t"] = t


def enemy_turn():
    e = P["enemy"]
    if random.randint(0, 20) > 3:          # ENEMY_MISS_CHANCE 3
        dmg = max(e["atk"] * P["level"] // (P["dfn"]), 1)
        P["hp"] = max(0, P["hp"] - dmg)
        battle_msg("Slime hits! -%d HP" % dmg)
    else:
        battle_msg("Slime missed!")
    if P["hp"] <= 0:
        battle_msg("You died... game over.", 60)


def gain_xp(elv):
    P["xp"] += elv * 30 // P["level"]
    if P["xp"] >= 200:
        P["xp"] -= 200
        P["level"] += 1
        P["hpmax"] += 7
        P["mpmax"] += 4
        P["atk"] += 3
        P["dfn"] += 6
        P["spd"] += 5
        P["hp"] = P["hpmax"]
        P["mp"] = P["mpmax"]
        battle_msg("LEVEL UP! Now level %d" % P["level"], 50)


BATTLE_MENU = ("ATTACK", "MAGIC", "HEAL", "FLEE")
new_game()
print("Overworld: D-pad walk, B talk to NPC. Random encounters -> turn battle.")
frame = 0
while True:
    btn.poll()
    frame += 1

    if P["mode"] == "over":
        dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
        dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
        if dx:
            P["facing"] = 3 if dx > 0 else 2
        elif dy:
            P["facing"] = 1 if dy > 0 else 0
        player.frame = P["facing"]
        moved = False
        if dx:
            nx = P["px"] + dx * 2
            if can_walk(nx, P["py"]):
                P["px"] = nx
                moved = True
        if dy:
            ny = P["py"] + dy * 2
            if can_walk(P["px"], ny):
                P["py"] = ny
                moved = True
        if moved:
            player.move(P["px"], P["py"])
            follow()
            P["steps"] += 1
            if P["steps"] > 120 and random.randint(0, 9) < 7:
                P["steps"] = 0
                start_battle()
        # talk to NPC
        near = abs(P["px"] - npc.x) <= TILE and abs(P["py"] - npc.y) <= TILE
        if near and btn.just_pressed(btn.B):
            P["mode"] = "dialog"
            P["msg"] = 0
            dlg.show(["Villager:", "Beware the slimes in",   # set ONCE on entering dialog
                      "the tall grass, hero.", "(press B)"])
        scene.refresh()

    elif P["mode"] == "dialog":
        scene.refresh()           # Panel is a scene layer -> drawn here, single present, no flicker
        if btn.just_pressed(btn.B) or btn.just_pressed(btn.A):
            dlg.hide()
            P["mode"] = "over"
            scene.invalidate()

    elif P["mode"] == "battle":
        e = P["enemy"]
        # Static turn-based screen. Split the VISUAL state (hp/mp/msg -> a full wipe + forced
        # redraw) from the menu SELECTION: a moved cursor must NOT trigger the wipe, or the whole
        # screen blinks. So on a visual change we wipe + force everything; on a selection-only
        # change we just let bmenu.draw() repaint its two affected rows (cheap, no wipe).
        vsig = (e["hp"], P["hp"], P["mp"], P["msg"], P["msg_t"] > 0)
        if vsig != P.get("bvsig"):
            P["bvsig"] = vsig
            pg.render(board.DISPLAY, _ENEMY_LIST, bufA, 0, 0, W, H, background=pg.rgb565(8, 8, 24))
            enemy_box.draw(board.DISPLAY, bufA,
                           ["Lv%d slime  HP %d/%d" % (e["lv"], e["hp"], e["hpmax"])], force=True)
            if P["msg_t"] > 0:
                msg_box.draw(board.DISPLAY, bufA, [P["msg"]], force=True)
            else:
                stats_box.draw(board.DISPLAY, bufA,
                               ["HP %d/%d  MP %d/%d  Lv%d" % (P["hp"], P["hpmax"], P["mp"], P["mpmax"], P["level"])],
                               force=True)
                bmenu.draw(board.DISPLAY, bufA, force=True)
        elif P["msg_t"] <= 0:
            bmenu.draw(board.DISPLAY, bufA)         # selection moved: per-row repaint, no wipe/blink
        if P["msg_t"] > 0:
            P["msg_t"] -= 1
            if P["hp"] <= 0 and P["msg_t"] == 0:
                new_game()
            if e["hp"] <= 0 and P["msg_t"] == 0:
                P["mode"] = "over"
                scene.invalidate()
        else:
            act = bmenu.tick(btn)
            if act is not None and act >= 0:
                if act == 0:        # attack
                    ch = random.randint(0, 25 if P["spd"] > e["spd"] else 20)
                    if ch < 2:
                        battle_msg("You missed!")
                    else:
                        crit = 2 if ch > 18 else 1
                        dmg = max(1, P["atk"] * crit * P["level"] // e["dfn"])
                        e["hp"] = max(0, e["hp"] - dmg)
                        battle_msg("Hit! -%d HP" % dmg)
                    if e["hp"] <= 0:
                        gain_xp(e["lv"])
                        P["gold"] += e["lv"] * random.randint(1, 3)
                        if P["xp"] < 200:    # gain_xp may have queued a level msg
                            battle_msg("You win! +gold", 50)
                    else:
                        enemy_turn()
                elif act == 1:      # magic
                    if P["mp"] >= 4:
                        P["mp"] -= 4
                        dmg = max(1, (P["atk"] + P["atk"] // 2) * P["level"] // e["dfn"])
                        e["hp"] = max(0, e["hp"] - dmg)
                        battle_msg("Magic! -%d HP" % dmg)
                        if e["hp"] <= 0:
                            gain_xp(e["lv"])
                            P["gold"] += e["lv"]
                        else:
                            enemy_turn()
                    else:
                        battle_msg("Not enough MP!")
                elif act == 2:      # heal
                    if P["mp"] >= 5:
                        P["mp"] -= 5
                        P["hp"] = min(P["hpmax"], P["hp"] + 12)
                        battle_msg("Healed +12 HP")
                        enemy_turn()
                    else:
                        battle_msg("Not enough MP!")
                else:               # flee
                    if random.randint(0, 1):
                        P["mode"] = "over"
                        scene.invalidate()
                    else:
                        battle_msg("Couldn't escape!")
                        enemy_turn()

    clock.tick()
