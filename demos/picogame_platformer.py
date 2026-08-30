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

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import terminalio
import picogame_ui as ui
import picogame_shapes as shp
import picogame_tiles as tiles
import picogame_synth as snd
import picogame_sfx

W, H = picogame_game.screen()
TILE = 16
ROWS = H // TILE                 # 15
COLS = 80                        # level is 80*16 = 1280 px wide
LEVEL_W = COLS * TILE
BG = pg.rgb565(90, 150, 230)
scene, bufA, bufB = picogame_game.setup(background=BG)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)
jump_buffer = picogame_input.Timer(6)     # jump buffer: honour a jump pressed just before landing
coyote = picogame_input.Timer(5)   # coyote time: still jump a few frames after leaving a ledge

DEBUG = False      # set True for a serial trace of the jump path (button/pos/vel/jump-decision)

# Tileset: 0 empty, 1 ground/brick (solid), 2 coin, 3 goal flag.
# TileFlags maps each tile INDEX to its meaning once, so collision/coin/goal are one-liners
# (tile_flags.at_px / tile_flags.at) instead of hand-rolled "== 1 / == 2 / == 3" index checks scattered around.
tile_flags = tiles.TileFlags({1: tiles.SOLID, 2: tiles.COIN, 3: tiles.EXIT}, tile_px=TILE)
stride = TILE * 4
tile_pixels = bytearray(stride * TILE)
for y in range(TILE):
    for x in range(TILE):
        tile_pixels[y * stride + 1 * TILE + x] = 1                     # ground = full
        if abs(x - TILE // 2) <= 3 and abs(y - TILE // 2) <= 4:  # coin = dot
            tile_pixels[y * stride + 2 * TILE + x] = 2
        if x in (6, 7, 8) or (y < 9 and 6 <= x <= 8 + (8 - y)):  # goal = flag-ish
            tile_pixels[y * stride + 3 * TILE + x] = 3
tile_palette = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(150, 90, 40),
                         pg.rgb565(245, 215, 50), pg.rgb565(40, 200, 80)])
tileset = pg.Bitmap(tile_pixels, TILE, TILE, format=pg.PAL8, palette=tile_palette,
                    frames=4, stride=stride, transparent=0)
level = pg.Tilemap(tileset, COLS, ROWS)
scene.add(level)

PLAYER_H = 15                          # player rect height; anchor is bottom -> head at py-PLAYER_H
player = pg.Sprite(shp.rect(12, PLAYER_H, pg.rgb565(230, 40, 40)), 0, 0)
player.anchor = (0.5, 1.0)
enemies = [pg.Sprite(shp.rect(14, 14, pg.rgb565(150, 80, 40)), 0, 0, visible=False)
           for _ in range(8)]
for enemy in enemies:
    enemy.anchor = (0.5, 1.0)
    enemy.data = {}
scene.add_all(enemies)
scene.add(player)
hud = ui.SceneLabel(scene, pg, terminalio.FONT, 4, 4,
                  pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 0))   # fixed layer
hud.reserve(40)   # the widest line this HUD ever sets ("COINS 19/19  LIVES 3  99999  BEST 99999")

_move_result = [0, 0, False]   # reused out-param [new_y, new_vy, landed] from move_v() (avoids a per-frame tuple alloc)

# game state (a State instance `st`)
class State:
    def __init__(self):
        self.px = 40.0
        self.py = 0.0
        self.vy = 0.0
        self.landed = False
        self.coins = 0
        self.coins_total = 0
        self.lives = 3
        self.score = 0
        self.invuln = 0        # mercy frames after a hit: without them the respawn puts you back
                               # inside the enemy that killed you and the next frame takes another life
        self._dbg_landed = False
        self.frame = 0


state = State()
best = 0          # best score across attempts - survives new_game()


def build_level():
    enemy_spawns = []
    coins = 0
    for ty in range(ROWS):
        for tx in range(COLS):
            level.set_tile(tx, ty, 0)
    # ground (2 tall) with a few pits
    pits = {18, 19, 34, 35, 52}
    for tx in range(COLS):
        if tx in pits:
            continue                 # leave a gap (pit) here
        level.set_tile(tx, ROWS - 1, 1)
        level.set_tile(tx, ROWS - 2, 1)
    # floating platforms
    for (plat_tx, plat_ty, length) in ((10, 9, 4), (24, 8, 3), (40, 7, 5), (58, 9, 4), (64, 6, 4)):
        for i in range(length):
            level.set_tile(plat_tx + i, plat_ty, 1)
    # coins above ground/platforms
    for (coin_tx, coin_ty, length) in ((11, 7, 4), (25, 6, 3), (41, 5, 5), (28, 12, 3), (60, 7, 4)):
        for i in range(length):
            level.set_tile(coin_tx + i, coin_ty, 2)
            coins += 1
    # goal flag near the end
    level.set_tile(COLS - 4, ROWS - 3, 3)
    level.set_tile(COLS - 4, ROWS - 4, 3)
    # enemy spawn columns (on the ground)
    for tx in (14, 30, 44, 48, 63):
        enemy_spawns.append(tx)
    state.coins_total = coins
    return enemy_spawns


def spawn_enemies(spawn_cols):
    for i, enemy in enumerate(enemies):
        if i < len(spawn_cols):
            enemy.data.update(alive=True, x=spawn_cols[i] * TILE + 8.0, y=(ROWS - 2) * TILE, facing=-1)
            enemy.move(int(enemy.data["x"]), int(enemy.data["y"]))
            enemy.visible = True
        else:
            enemy.data["alive"] = False
            enemy.visible = False


def solid_at(pixel_x, pixel_y):
    tx, ty = pixel_x // TILE, pixel_y // TILE
    if tx < 0 or tx >= COLS or ty < 0 or ty >= ROWS:
        return False
    return tile_flags.at(level, tx, ty, tiles.B_SOLID)


def move_v(x, y, vy, half_w):
    # ONE-WAY platforms: you jump UP through a platform from below and land on its TOP when falling.
    if vy > 0:                                   # falling
        # If the BODY (mid-height) is embedded in a platform - i.e. we jumped UP into it - fall
        # straight out the bottom (one-way pass-through, no getting stuck). Testing mid-body, not
        # the feet, is key: when simply STANDING, the feet sit on the platform's top edge (which
        # reads as "in" the tile) but the body is clear, so we still land normally.
        body_mid_y = y - PLAYER_H // 2
        if solid_at(x - half_w + 2, body_mid_y) or solid_at(x + half_w - 2, body_mid_y):
            _move_result[0], _move_result[1], _move_result[2] = y + int(vy), vy, False
            return
        steps = int(vy)
        while steps > 0:
            if solid_at(x - half_w + 2, y + 1) or solid_at(x + half_w - 2, y + 1):
                _move_result[0], _move_result[1], _move_result[2] = y, 0, True     # landed on the platform top
                return
            y += 1
            steps -= 1
        # Standing still, gravity is only +0.6/frame, so int(vy) is 0 and the loop above never ran -
        # without this probe `landed` would read False on those frames and flicker every other frame.
        # Jumping still worked (the coyote timer papered over it), but anything else keyed off
        # `landed` - a footstep sound, a grounded animation - would stutter.
        grounded = solid_at(x - half_w + 2, y + 1) or solid_at(x + half_w - 2, y + 1)
        _move_result[0], _move_result[1], _move_result[2] = y, (0 if grounded else vy), grounded
    else:                                        # rising: pass up through platforms (one-way)
        _move_result[0], _move_result[1], _move_result[2] = y + int(vy), vy, False


def follow():
    view_x = max(W - LEVEL_W, min(0, W // 2 - int(state.px)))
    scene.set_view(int(view_x), 0)


def reset_player(mercy=True):
    state.px, state.py = 40.0, (ROWS - 2) * TILE
    state.vy = 0.0
    state.landed = False
    # Mercy frames belong to a RESPAWN, not to the first spawn: the hurt path puts you back inside
    # the enemy that hit you. Granting them at game start just makes the player blink for 1.5 s
    # before anything has happened.
    state.invuln = 45 if mercy else 0


def new_game():
    global state
    state = State()
    spawn_cols = build_level()
    spawn_enemies(spawn_cols)
    reset_player(mercy=False)
    follow()


new_game()
kit = picogame_sfx.Kit(snd.Synth())          # signature SFX; silent no-op if no audio
print("LEFT/RIGHT run, UP/B jump. Stomp enemies, grab coins, reach the green flag.")


def main():
    # --- per-frame loop in a FUNCTION (not module scope): names become array-indexed locals,
    # not globals-dict lookups (measured on-device win; picogame-game-design hot-loop style guide).
    _shown_coins, _shown_lives, _shown_score, _shown_best = -1, -1, -1, -1
    while True:
        btn.poll()

        dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
        if dx:
            new_x = state.px + dx * 3
            if not (solid_at(int(new_x) + dx * 6, int(state.py) - 4) or
                    solid_at(int(new_x) + dx * 6, int(state.py) - 12)):
                state.px = max(6, min(LEVEL_W - 6, new_x))
        jump_pressed = btn.just_pressed(btn.UP) or btn.just_pressed(btn.B)     # rising edge of either jump key
        jump_buffer.feed(jump_pressed)                                                # remember an early jump press
        coyote.feed(state.landed)                                           # remember being grounded
        jump_fired = coyote.is_active and jump_buffer.consume()
        if jump_fired:
            state.vy = -11.0
            state.landed = False
            kit.jump()
            coyote.t = 0                                                 # one jump per ledge window

        if DEBUG:
            state.frame += 1
            # Print only on interesting events (a jump key edge, a jump firing, a landed change)
            # plus a 1 Hz heartbeat - enough to see WHY a press did/didn't become a jump, without
            # flooding the 30 fps serial. Read it on the USB console while jumping on HW.
            if jump_pressed or jump_fired or state.landed != state._dbg_landed or state.frame % 30 == 0:
                print("f%d UP=%d B=%d jump_pressed=%d jump_buffer=%d coyote=%d landed=%d FIRE=%d py=%d vy=%.1f"
                      % (state.frame, btn.is_pressed(btn.UP), btn.is_pressed(btn.B), jump_pressed,
                         jump_buffer.t, coyote.t, state.landed, jump_fired, int(state.py), state.vy))
            state._dbg_landed = state.landed

        if state.invuln > 0:
            state.invuln -= 1
            player.flash = pg.rgb565(255, 255, 255) if (state.invuln >> 2) & 1 else None
        state.vy = min(7.0, state.vy + 0.6)
        move_v(int(state.px), int(state.py), state.vy, 6)
        state.py = float(_move_result[0])
        state.vy = _move_result[1]
        state.landed = _move_result[2]
        player.move(int(state.px), int(state.py))

        # fell in a pit
        if state.py > H + 20:
            state.lives -= 1
            if state.lives < 0:
                kit.explosion()
                new_game()
            else:
                kit.hurt()
                reset_player()
            follow()
            continue

        # coins: check the tile at the player's chest
        chest_tx, chest_ty = int(state.px) // TILE, (int(state.py) - 8) // TILE
        if 0 <= chest_tx < COLS and 0 <= chest_ty < ROWS and tile_flags.at(level, chest_tx, chest_ty, tiles.B_COIN):
            level.set_tile(chest_tx, chest_ty, 0)
            state.coins += 1
            state.score += 100
            kit.coin()
        # goal
        goal_tx = int(state.px) // TILE
        if tile_flags.at(level, goal_tx, ROWS - 3, tiles.B_EXIT):
            state.score += 1000
            kit.powerup()
            # new_game() rebinds `state`, so the bonus (and the whole run) would vanish in the frame
            # it was awarded. Carry the result out first: a cleared level is the one thing worth
            # remembering across attempts.
            global best
            best = max(best, state.score)
            new_game()

        # enemies
        for enemy in enemies:
            if not enemy.data.get("alive"):
                continue
            new_x = enemy.data["x"] + enemy.data["facing"] * 1.2
            # turn at wall or ledge
            if solid_at(int(new_x) + enemy.data["facing"] * 7, int(enemy.data["y"]) - 6) or \
                    not solid_at(int(new_x) + enemy.data["facing"] * 7, int(enemy.data["y"]) + 2):
                enemy.data["facing"] = -enemy.data["facing"]
            else:
                enemy.data["x"] = new_x
                enemy.move(int(new_x), int(enemy.data["y"]))
            # player interaction: native box collision, then stomp-vs-hurt discrimination
            if player.overlaps(enemy):
                if state.vy > 1 and state.py <= enemy.data["y"] + 6:     # falling onto its head -> stomp
                    enemy.data["alive"] = False
                    enemy.visible = False
                    state.vy = -7.0
                    state.score += 200
                    kit.boom()
                elif state.invuln <= 0:                            # hurt (mercy window aside)
                    state.lives -= 1
                    if state.lives < 0:
                        kit.explosion()
                        new_game()
                    else:
                        kit.hurt()
                        reset_player()
                    follow()
                    break

        follow()
        shown_lives = max(0, state.lives)
        # `best` belongs in this test: clearing the level awards the bonus and then restarts, so
        # coins/lives/score land back on their starting values - identical to what is already shown -
        # and without `best` here the new record never repaints. A win then looks like nothing happened.
        if (state.coins != _shown_coins or shown_lives != _shown_lives
                or state.score != _shown_score or best != _shown_best):
            _shown_coins, _shown_lives, _shown_score, _shown_best = state.coins, shown_lives, state.score, best
            hud.set("COINS %d/%d  LIVES %d  %05d  BEST %05d"
                    % (state.coins, state.coins_total, shown_lives, state.score, best))
        kit.tick()
        scene.refresh()
        clock.tick()


main()
