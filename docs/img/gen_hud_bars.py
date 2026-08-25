# FEATURES.md §9 illustration: the four ways to build a status bar, stacked so you
# can see what each looks like. (Illustrative -- a real game uses one per HUD.)
import picogame as pg, picogame_game, picogame_font, terminalio

F = terminalio.FONT
W = 320
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(14, 16, 30))

WHITE = pg.rgb565(235, 235, 245)
DIM = pg.rgb565(140, 150, 175)
RED = pg.rgb565(225, 70, 80)


def text(s, x, y, fg, bg=None):
    bmp, _, _ = picogame_font.render_text(pg, F, s, fg, bg)
    scene.add(pg.Sprite(bmp, x, y))


# A -- SceneLabel: text as a scene layer (just text on the world background)
text("A  SceneLabel - text as a scene layer", 8, 6, DIM)
text("SCORE 04820     HI 12750", 8, 22, WHITE)

# B -- reserved zone + HudBar: a flat-colour strip with score + lives
text("B  reserved zone + HudBar - flat strip, 0 RAM", 8, 52, DIM)
barB = pg.Canvas(W - 16, 22)
barB.clear(pg.rgb565(28, 38, 66))
for i in range(3):                       # three "hearts" as little squares
    barB.fill_rect(W - 16 - 24 - i * 18, 7, 10, 9, RED)
scene.add(barB)
barB.move(8, 66)
text("SCORE 04820", 14, 70, WHITE)       # text sits on top (added later = on top)

# C -- Canvas: a bevelled gauge widget, sized to its content
text("C  Canvas - bevelled gauge widget", 8, 98, DIM)
gauge = pg.Canvas(150, 22)
gauge.frame3d(0, 0, 150, 22, pg.rgb565(90, 100, 130), pg.rgb565(20, 24, 40))
gauge.fill_rect(3, 3, 144, 16, pg.rgb565(24, 28, 44))         # track
gauge.fill_rect(3, 3, 92, 16, pg.rgb565(70, 210, 120))        # fill (~64%)
scene.add(gauge)
gauge.move(8, 112)

# D -- StripDraw: a zero-buffer animated / gradient bar
text("D  StripDraw - animated / gradient, 0 RAM", 8, 144, DIM)


def grad(view, vx, vy, vw, vh):
    for x in range(vw):
        t = (vx + x) * 255 // W
        view.fill_rect(x, 0, 1, vh, pg.rgb565(t, 90, 255 - t))


scene.add(pg.StripDraw(grad, 8, 158, W - 16, 22))

while True:
    scene.refresh()
