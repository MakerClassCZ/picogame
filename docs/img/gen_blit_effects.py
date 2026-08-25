import picogame as pg, picogame_game, picogame_shapes as shp, picogame_ui as ui, terminalio
BG = pg.rgb565(18, 22, 38)
WHITE = pg.rgb565(255, 255, 255)
scene, _, _ = picogame_game.setup(background=BG)
gem = shp.circle(34, pg.rgb565(245, 170, 40))             # the one bitmap, reused 5x
panel = shp.rect(46, 46, pg.rgb565(150, 155, 170))        # light panel behind, so dither/shadow read
labels = ["normal", "flash", "tint", "dither", "shadow"]
xs = [40, 104, 168, 232, 296]
y = 96
for i, x in enumerate(xs):
    p = pg.Sprite(panel, x, y); p.anchor = (0.5, 0.5); scene.add(p)
    s = pg.Sprite(gem, x, y); s.anchor = (0.5, 0.5)
    if i == 1:   s.flash = WHITE
    elif i == 2: s.tint = pg.rgb565(90, 235, 120)
    elif i == 3: s.dither = 8
    elif i == 4: s.shadow = True
    scene.add(s)
    ui.SceneLabel(scene, pg, terminalio.FONT, x - 20, y + 34, WHITE, BG).set(labels[i])
while True:
    scene.refresh()
