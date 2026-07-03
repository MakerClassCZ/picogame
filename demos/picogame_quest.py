# Picogame Quest - a genre port of TEAM ARG's Arduboy RPG "Arduventure".
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
# picogame_ui.py, picogame_tiles.py. Needs the latest firmware. Generated art.

import array
import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_ui as ui
import picogame_tiles as tiles

W, H = board.DISPLAY.width, board.DISPLAY.height
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

# battle enemy sprite (drawn screen-space in battle mode); preallocated + reused.
# 8x8 solid square rendered at scale 6.0 -> 48x48 (native nearest-neighbour scale is
# pixel-identical for a flat-colour square, at ~1/36 the bitmap RAM of a 48x48 buffer).
enemy_bm = solid(8, 8, pg.rgb565(150, 60, 200))
enemy_sprite = pg.Sprite(enemy_bm, W // 2 - 24, 50)
enemy_sprite.scale = 6.0
_ENEMY_LIST = [enemy_sprite]

# ---- UI: now uses picogame_ui (TextBox + Menu) instead of a hand-rolled box ----
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

class State:
    def __init__(self):
        self.level = 1
        self.hp = 20
        self.hpmax = 20
        self.mp = 10
        self.mpmax = 10
        self.atk = 5
        self.dfn = 7
        self.spd = 3
        self.xp = 0
        self.gold = 0
        self.steps = 0
        self.mode = "over"
        self.facing = 1
        self.px = player_tile[0] * TILE
        self.py = player_tile[1] * TILE
        self.menu = 0
        self.enemy = None
        self.msg = ""
        self.msg_t = 0
        self.battle_dirty = True         # set when the battle VISUAL state (hp/mp/msg/msg_t) changes


st = State()


def new_game():
    global st
    st = State()
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
    ox = max(W - MCOLS * TILE, min(0, W // 2 - (st.px + TILE // 2)))
    oy = max(H - MROWS * TILE, min(0, H // 2 - (st.py + TILE // 2)))
    scene.set_view(int(ox), int(oy))


def start_battle():
    lv = st.level
    st.enemy = {"hp": 3 * lv + 4, "hpmax": 3 * lv + 4, "atk": 6 * lv // 2 + 2,
                "dfn": 3 * lv, "spd": 5 * lv, "lv": lv}
    st.mode = "battle"
    st.menu = 0
    st.msg = "A wild slime appears!"
    st.msg_t = 40
    st.battle_dirty = True   # force a fresh battle-screen draw on entry
    scene.invalidate()


def battle_msg(s, t=30):
    st.msg = s
    st.msg_t = t
    st.battle_dirty = True   # every hp/mp/msg-changing battle action funnels through here


def enemy_turn():
    e = st.enemy
    if random.randint(0, 20) > 3:          # ENEMY_MISS_CHANCE 3
        dmg = max(e["atk"] * st.level // (st.dfn), 1)
        st.hp = max(0, st.hp - dmg)
        battle_msg("Slime hits! -%d HP" % dmg)
    else:
        battle_msg("Slime missed!")
    if st.hp <= 0:
        battle_msg("You died... game over.", 60)


def gain_xp(elv):
    st.xp += elv * 30 // st.level
    if st.xp >= 200:
        st.xp -= 200
        st.level += 1
        st.hpmax += 7
        st.mpmax += 4
        st.atk += 3
        st.dfn += 6
        st.spd += 5
        st.hp = st.hpmax
        st.mp = st.mpmax
        battle_msg("LEVEL UP! Now level %d" % st.level, 50)


new_game()
print("Overworld: D-pad walk, B talk to NPC. Random encounters -> turn battle.")
while True:
    btn.poll()

    if st.mode == "over":
        dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
        dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
        if dx:
            st.facing = 3 if dx > 0 else 2
        elif dy:
            st.facing = 1 if dy > 0 else 0
        player.frame = st.facing
        moved = False
        if dx:
            nx = st.px + dx * 2
            if can_walk(nx, st.py):
                st.px = nx
                moved = True
        if dy:
            ny = st.py + dy * 2
            if can_walk(st.px, ny):
                st.py = ny
                moved = True
        if moved:
            player.move(st.px, st.py)
            follow()
            st.steps += 1
            if st.steps > 120 and random.randint(0, 9) < 7:
                st.steps = 0
                start_battle()
        # talk to NPC
        near = abs(st.px - npc.x) <= TILE and abs(st.py - npc.y) <= TILE
        if near and btn.just_pressed(btn.B):
            st.mode = "dialog"
            dlg.show(["Villager:", "Beware the slimes in",   # set ONCE on entering dialog
                      "the tall grass, hero.", "(press B)"])
        scene.refresh()

    elif st.mode == "dialog":
        scene.refresh()           # Panel is a scene layer -> drawn here, single present, no flicker
        if btn.just_pressed(btn.B) or btn.just_pressed(btn.A):
            dlg.hide()
            st.mode = "over"
            scene.invalidate()

    elif st.mode == "battle":
        e = st.enemy
        # Static turn-based screen. Split the VISUAL state (hp/mp/msg -> a full wipe + forced
        # redraw) from the menu SELECTION: a moved cursor must NOT trigger the wipe, or the whole
        # screen blinks. So on a visual change we wipe + force everything; on a selection-only
        # change we just let bmenu.draw() repaint its two affected rows (cheap, no wipe).
        if st.battle_dirty:
            st.battle_dirty = False
            pg.render(board.DISPLAY, _ENEMY_LIST, bufA, 0, 0, W, H, background=pg.rgb565(8, 8, 24))
            enemy_box.draw(board.DISPLAY, bufA,
                           ["Lv%d slime  HP %d/%d" % (e["lv"], e["hp"], e["hpmax"])], force=True)
            if st.msg_t > 0:
                msg_box.draw(board.DISPLAY, bufA, [st.msg], force=True)
            else:
                stats_box.draw(board.DISPLAY, bufA,
                               ["HP %d/%d  MP %d/%d  Lv%d" % (st.hp, st.hpmax, st.mp, st.mpmax, st.level)],
                               force=True)
                bmenu.draw(board.DISPLAY, bufA, force=True)
        elif st.msg_t <= 0:
            bmenu.draw(board.DISPLAY, bufA)         # selection moved: per-row repaint, no wipe/blink
        if st.msg_t > 0:
            st.msg_t -= 1
            if st.msg_t == 0:
                st.battle_dirty = True     # message expired: `msg_t > 0` flipped -> redraw stats + menu
            if st.hp <= 0 and st.msg_t == 0:
                new_game()
            if e["hp"] <= 0 and st.msg_t == 0:
                st.mode = "over"
                scene.invalidate()
        else:
            act = bmenu.tick(btn)
            if act is not None and act >= 0:
                if act == 0:        # attack
                    ch = random.randint(0, 25 if st.spd > e["spd"] else 20)
                    if ch < 2:
                        battle_msg("You missed!")
                    else:
                        crit = 2 if ch > 18 else 1
                        dmg = max(1, st.atk * crit * st.level // e["dfn"])
                        e["hp"] = max(0, e["hp"] - dmg)
                        battle_msg("Hit! -%d HP" % dmg)
                    if e["hp"] <= 0:
                        gain_xp(e["lv"])
                        st.gold += e["lv"] * random.randint(1, 3)
                        if st.xp < 200:    # gain_xp may have queued a level msg
                            battle_msg("You win! +gold", 50)
                    else:
                        enemy_turn()
                elif act == 1:      # magic
                    if st.mp >= 4:
                        st.mp -= 4
                        dmg = max(1, (st.atk + st.atk // 2) * st.level // e["dfn"])
                        e["hp"] = max(0, e["hp"] - dmg)
                        battle_msg("Magic! -%d HP" % dmg)
                        if e["hp"] <= 0:
                            gain_xp(e["lv"])
                            st.gold += e["lv"]
                        else:
                            enemy_turn()
                    else:
                        battle_msg("Not enough MP!")
                elif act == 2:      # heal
                    if st.mp >= 5:
                        st.mp -= 5
                        st.hp = min(st.hpmax, st.hp + 12)
                        battle_msg("Healed +12 HP")
                        enemy_turn()
                    else:
                        battle_msg("Not enough MP!")
                else:               # flee
                    if random.randint(0, 1):
                        st.mode = "over"
                        scene.invalidate()
                    else:
                        battle_msg("Couldn't escape!")
                        enemy_turn()

    clock.tick()
