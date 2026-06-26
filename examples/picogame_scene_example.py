# Validation driver for the declarative scene format: loads a baked level
# (world1_scene.SCENE) via picogame_scene.load(), then runs a minimal loop that
# auto-walks the player right so the follow-camera scrolls - proving the loader
# builds the tilemap + sprites + group + fixed HUD + camera, and that tile-property
# queries (solid/coin/goal) work. Copy with picogame_scene.py, picogame_ui.py,
# picogame_font.py + world1_scene.py. Runs on device or the simulator.

import board
import terminalio
import picogame as pg
import picogame_scene as pgs
import picogame_fx as fx
import world1_scene

view = pgs.load(pg, world1_scene.SCENE, font=terminalio.FONT)
player = view.named["player"]
enemies = view.group("enemies")
W = 320
cam = view.camera                      # ("follow", "player", "x", x0, y0, x1, y1)
bounds_w = cam[5]
camera = fx.Camera(view.scene, W, 240, world_w=bounds_w)  # follow + clamp for us

# one-time sanity prints of tile-property queries
print("solid at ground (0,14):", view.is_solid(0, 14))     # expect True
print("solid at sky   (0,0):", view.is_solid(0, 0))         # expect False
print("tile_is coin (11,3):", view.tile_has(11, 3, "coin"))  # a coin in the map
print("enemies:", len(enemies), " camera:", cam[0], cam[2])

frame = 0
while True:
    player.move(player.x + 2, player.y)            # auto-walk to show scrolling
    if player.x > bounds_w - 20:
        player.move(40, player.y)
    camera.follow(player.x, 120, snap=True).apply()   # follow + clamp (fx.Camera)
    view.named["score"].set("X %d" % player.x)     # fixed HUD updates while scrolling
    view.scene.refresh()
    frame += 1
