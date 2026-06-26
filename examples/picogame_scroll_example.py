# picogame camera/scrolling demo: a world larger than the screen, with the view
# following the player via scene.set_view(). Copy with picogame_game.py,
# picogame_input.py, picogame_clock.py, picogame_math.py. Tilemap firmware required.
#
# The whole world (tilemap + sprites) lives in scene coordinates; set_view() scrolls.
# Scrolling repaints the whole screen each moved frame; standing still falls back to
# cheap dirty-rect (set_view only forces a repaint when the offset actually changes).

import time
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_math as vec
import picogame_shapes as shapes

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(0, 0, 0))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

W, H = 320, 240
TILE = 16
MAP_W, MAP_H = 40, 30                 # 640 x 480 world (bigger than the screen)
WORLD_W, WORLD_H = MAP_W * TILE, MAP_H * TILE

# 4-tile opaque tileset (grass / dirt / water / path); frame i = solid colour i.
tileset = shapes.color_frames(TILE, TILE, (
    pg.rgb565(40, 120, 50), pg.rgb565(120, 90, 50),
    pg.rgb565(40, 90, 200), pg.rgb565(180, 170, 120),
))

world = pg.Tilemap(tileset, MAP_W, MAP_H)
world.fill(0)                          # grass everywhere
# a few features: a water lake, dirt paths, scattered patches
for ty in range(8, 14):
    for tx in range(5, 12):
        world.tile(tx, ty, 2)          # lake
for tx in range(MAP_W):
    world.tile(tx, 15, 3)              # horizontal path
for ty in range(MAP_H):
    world.tile(20, ty, 1)              # vertical dirt road


player = pg.Sprite(shapes.circle(16, pg.rgb565(240, 220, 80)), WORLD_W // 2, WORLD_H // 2)
markers = [pg.Sprite(shapes.circle(12, pg.rgb565(220, 80, 80)), 16 + i * 90, 40 + (i % 3) * 70)
           for i in range(6)]
scene.add_all([world, player] + markers)


def follow():
    ox = vec.clamp(W // 2 - (player.x + 8), W - WORLD_W, 0)
    oy = vec.clamp(H // 2 - (player.y + 8), H - WORLD_H, 0)
    scene.set_view(int(ox), int(oy))


follow()
print("D-pad scrolls the world (view follows the player). Stand still = cheap dirty-rect.")
SPEED = 3
fps_t = time.monotonic()
fps_n = 0
while True:
    btn.poll()
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx or dy:
        player.move(int(vec.clamp(player.x + dx * SPEED, 0, WORLD_W - 16)),
                    int(vec.clamp(player.y + dy * SPEED, 0, WORLD_H - 16)))
        follow()
    scene.refresh()
    fps_n += 1
    now = time.monotonic()
    if now - fps_t >= 1.0:
        print("FPS: %.1f  pos=(%d,%d)" % (fps_n / (now - fps_t), player.x, player.y))
        fps_t = now
        fps_n = 0
    clock.tick()
