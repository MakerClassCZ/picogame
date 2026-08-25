import picogame as pg, picogame_game, picogame_shapes as shp, picogame_ui as ui, terminalio
BG = pg.rgb565(16, 20, 34)
WHITE = pg.rgb565(255, 255, 255)
BLUE = pg.rgb565(70, 130, 240)
ORANGE = pg.rgb565(245, 150, 50)
scene, _, _ = picogame_game.setup(background=BG)


def box(x, y, w, h, col):
    o = pg.Sprite(shp.rect(w + 4, h + 4, WHITE), x, y); o.anchor = (0.5, 0.5); scene.add(o)
    s = pg.Sprite(shp.rect(w, h, col), x, y); s.anchor = (0.5, 0.5); scene.add(s)


def disc(x, y, d, col):
    r = pg.Sprite(shp.ring(d + 4, WHITE, 2), x, y); r.anchor = (0.5, 0.5); scene.add(r)
    s = pg.Sprite(shp.circle(d, col), x, y); s.anchor = (0.5, 0.5); scene.add(s)


# left: AABB -- two overlapping boxes (white outline = the bounding box that's tested)
box(72, 96, 54, 40, BLUE)
box(106, 116, 54, 40, ORANGE)
ui.SceneLabel(scene, pg, terminalio.FONT, 44, 162, WHITE, BG).set("AABB - boxes")
# right: circle/within -- two overlapping discs (ring = the radius that's tested)
disc(228, 96, 46, BLUE)
disc(262, 118, 46, ORANGE)
ui.SceneLabel(scene, pg, terminalio.FONT, 196, 162, WHITE, BG).set("circle - within")
while True:
    scene.refresh()
