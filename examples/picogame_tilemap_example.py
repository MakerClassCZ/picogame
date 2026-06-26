# picogame Tilemap demo: a tile background with a sprite moving over it.
# REQUIRES the new firmware (Tilemap support) -> reflash firmware.uf2 first.
# Copy to CIRCUITPY/code.py.
#
# Proves the layered dirty-rect scene: when the hero moves, the vacated area is
# repainted with the TILEMAP (not a flat colour). B paints a tile under the hero.

import array
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock

W, H = 320, 240
BG = pg.rgb565(0, 0, 0)

# Build a 4-tile opaque tileset (16x16 each, horizontal atlas).
TILE, NT = 16, 4
pal = array.array("H", [
    pg.rgb565(15, 18, 30), pg.rgb565(60, 90, 200),
    pg.rgb565(50, 170, 90), pg.rgb565(210, 200, 80),
])
stride = TILE * NT
tdata = bytearray(stride * TILE)
for y in range(TILE):
    for x in range(TILE):
        tdata[y * stride + 0 * TILE + x] = 0
        tdata[y * stride + 1 * TILE + x] = 1 if ((x // 4 + y // 4) & 1) == 0 else 0
        tdata[y * stride + 2 * TILE + x] = 2 if (x in (0, TILE - 1) or y in (0, TILE - 1)) else 0
        tdata[y * stride + 3 * TILE + x] = 3 if (x % 4 == 2 and y % 4 == 2) else 0
tileset = pg.Bitmap(tdata, TILE, TILE, format=pg.PAL8, palette=pal, frames=NT, stride=stride)


def make_blob(size, r, g, b):
    bp = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(r, g, b),
                           pg.rgb565(min(r + 80, 255), min(g + 80, 255), min(b + 80, 255))])
    d = bytearray(size * size)
    c = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            if abs(x - c) + abs(y - c) <= c:
                d[y * size + x] = 2 if abs(x - c) + abs(y - c) <= c * 0.45 else 1
    return pg.Bitmap(d, size, size, format=pg.PAL8, palette=bp, transparent=0)


hero_bmp = make_blob(24, 240, 120, 60)

scene, bufA, bufB = picogame_game.setup(background=BG)
btns = picogame_input.Buttons()
clock = picogame_clock.Clock(fps=30)

MAP_W, MAP_H = W // TILE, H // TILE   # 20 x 15 -> fills the screen
bg = pg.Tilemap(tileset, MAP_W, MAP_H)
bg.fill(1)
for ty in range(MAP_H):
    bg.tile(0, ty, 2)
    bg.tile(MAP_W - 1, ty, 2)
for tx in range(MAP_W):
    bg.tile(tx, 0, 2)
    bg.tile(tx, MAP_H - 1, 2)

hero = pg.Sprite(hero_bmp, 150, 110)
scene.add(bg)      # bottom layer
scene.add(hero)    # on top

print("D-pad: move (tilemap shows through behind you)  |  B: paint a tile")
SPEED = 2
HERO = hero_bmp.width

while True:
    btns.poll()
    dx = btns.is_pressed(btns.RIGHT) - btns.is_pressed(btns.LEFT)
    dy = btns.is_pressed(btns.DOWN) - btns.is_pressed(btns.UP)
    if dx or dy:
        hero.move(max(0, min(W - HERO, hero.x + dx * SPEED)),
                  max(0, min(H - HERO, hero.y + dy * SPEED)))

    if btns.just_pressed(btns.B):
        bg.tile((hero.x + HERO // 2) // TILE, (hero.y + HERO // 2) // TILE, 3)

    scene.refresh()
    clock.tick()
