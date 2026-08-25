import picogame as pg, picogame_game, picogame_shapes as shp, picogame_ui as ui, terminalio
BG = pg.rgb565(10, 12, 20)
WHITE = pg.rgb565(255, 255, 255)
scene, _, _ = picogame_game.setup(background=BG)
# a 4-frame explosion: a burst that grows then fades -- the kind of cycle picogame_anim steps.
cols = [pg.rgb565(255, 230, 120), pg.rgb565(255, 170, 40), pg.rgb565(230, 90, 40), pg.rgb565(150, 70, 50)]
ds = [14, 26, 40, 46]
xs = [52, 124, 196, 268]
y = 92
for i, x in enumerate(xs):
    cell = pg.Sprite(shp.rect(58, 58, pg.rgb565(30, 34, 48)), x, y); cell.anchor = (0.5, 0.5); scene.add(cell)
for i, x in enumerate(xs):
    bm = shp.ring(ds[i], cols[i], 3) if i == 3 else shp.circle(ds[i], cols[i])
    s = pg.Sprite(bm, x, y); s.anchor = (0.5, 0.5)
    if i == 3:
        s.dither = 8                                       # last frame fades out
    scene.add(s)
    ui.SceneLabel(scene, pg, terminalio.FONT, x - 16, y + 36, WHITE, BG).set("frame %d" % i)
while True:
    scene.refresh()
