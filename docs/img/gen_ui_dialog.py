# /helpers/text-ui/ illustration: picogame_ui.SceneBox - a bordered multi-line dialog box
# pinned in the scene. A buffer-less StripDraw: scene.refresh() composites its panel +
# frame3d border + text straight into the live strip (0 retained RAM), so it sits cleanly
# over a scrolling/animated world. show(lines) once; refresh() paints it.
import picogame as pg, picogame_game, terminalio
import picogame_ui as ui

F = terminalio.FONT
W, H = picogame_game.screen()

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(30, 54, 34))

# a simple "world" behind the dialog
world = pg.Canvas(W, H)
world.clear(pg.rgb565(30, 54, 34))
for i in range(0, W, 24):
    world.fill_rect(i, 0, 12, H, pg.rgb565(40, 72, 46))
scene.add(world)
world.move(0, 0)

WHITE = pg.rgb565(238, 238, 248)
NAVY = pg.rgb565(18, 26, 54)
BORDER = pg.rgb565(96, 112, 158)

box = ui.SceneBox(scene, pg, F, 8, H - 70, W - 16, 62, WHITE, NAVY, nlines=3, border=BORDER)
box.show(["Villager:", "Beware the slimes", "in the tall grass."])

while True:
    scene.refresh()
