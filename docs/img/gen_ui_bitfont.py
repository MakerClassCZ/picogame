# /helpers/text-ui/ illustration: picogame_bitfont - an 8x8 OUTLINED, transparent-bg font
# with game glyphs (hearts/arrows/...). The built-in dark outline gives contrast so text
# reads cleanly OVER gameplay without a HUD box. Shown here over a busy scene.
import picogame as pg, picogame_game, picogame_bitfont as bf

W, H = picogame_game.screen()

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(34, 92, 54))

# a busy "world" background so the outline's value is visible
world = pg.Canvas(W, H)
world.clear(pg.rgb565(34, 92, 54))
for i in range(0, W, 28):
    world.fill_rect(i, 0, 14, H, pg.rgb565(46, 116, 66))
for i in range(0, H, 40):
    world.fill_rect(0, i, W, 6, pg.rgb565(58, 74, 40))
scene.add(world)
world.move(0, 0)

WHITE = pg.rgb565(255, 255, 255)
GOLD = pg.rgb565(255, 214, 90)
RED = pg.rgb565(235, 70, 80)

# outlined text sits directly over the scene (transparent bg + dark outline = contrast)
b1, w1, h1 = bf.render_text(pg, "SCORE 04820", fg=WHITE)
scene.add(pg.Sprite(b1, 10, 12))

b2, w2, h2 = bf.render_text(pg, "picogame_bitfont", fg=GOLD)
scene.add(pg.Sprite(b2, 10, 40))

b3, w3, h3 = bf.render_text(pg, "outlined text over gameplay", fg=WHITE)
scene.add(pg.Sprite(b3, 10, 60))

# game glyphs: hearts, arrows, star, note
b4, w4, h4 = bf.render_text(pg, "LIVES " + bf.HEART * 3, fg=RED)
scene.add(pg.Sprite(b4, 10, H - 24))

b5, w5, h5 = bf.render_text(pg, bf.ARROW_L + bf.ARROW_R + " " + bf.STAR + " " + bf.NOTE,
                            fg=GOLD)
scene.add(pg.Sprite(b5, W - w5 - 10, H - 24))

while True:
    scene.refresh()
