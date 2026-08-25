# /helpers/text-ui/ illustration: picogame_ui.HudBar - a status strip drawn OUTSIDE the
# scene, in a band the scene reserves with setup(..., top=BAR). Zero retained RAM: a
# buffer-less StripDraw composites bg + icon sprites + text labels straight into the strip.
import picogame as pg, picogame_game, picogame_bitfont as bf, terminalio
import picogame_ui as ui

F = terminalio.FONT
W, H = picogame_game.screen()
BAR = 22

BG = pg.rgb565(18, 24, 40)
scene, bufA, bufB = picogame_game.setup(background=BG, top=BAR)

# a bit of "gameplay" under the bar so it reads as an in-game HUD
world = pg.Canvas(W, H - BAR)
world.clear(pg.rgb565(24, 40, 60))
for i in range(0, W, 32):
    world.fill_rect(i, 0, 16, H - BAR, pg.rgb565(30, 52, 78))
scene.add(world)
world.move(0, BAR)

WHITE = pg.rgb565(235, 235, 245)
GOLD = pg.rgb565(240, 200, 90)
RED = pg.rgb565(235, 70, 80)

hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, pg.rgb565(28, 38, 66))
score = hud.label(F, 6, 7, WHITE, "SCORE 04820")
coins = hud.label(F, 150, 7, GOLD, "COINS 12")

# icon sprites (hearts) blitted into the bar at the right edge
hb, hw, hh = bf.render_text(pg, bf.HEART * 3, fg=RED)
hud.add(pg.Sprite(hb, W - hw - 6, 7))

while True:
    scene.refresh()
    hud.draw()
