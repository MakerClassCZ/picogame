# /helpers/text-ui/ illustration: picogame_font.Label - an IMMEDIATE HUD text label.
# A Label re-renders only when its text changes; draw(display, buffer) repaints it via
# pg.render every frame (here: score / hi-score / lives as three opaque-bg labels).
import picogame as pg, picogame_game, picogame_font, terminalio

F = terminalio.FONT
W, H = picogame_game.screen()

BG = pg.rgb565(14, 16, 30)
WHITE = pg.rgb565(235, 235, 245)
DIM = pg.rgb565(140, 150, 175)
GOLD = pg.rgb565(240, 200, 90)
RED = pg.rgb565(225, 90, 95)
PANEL = pg.rgb565(24, 30, 58)

scene, bufA, bufB = picogame_game.setup(background=BG)


def cap(s, x, y, c=DIM):
    bmp, _, _ = picogame_font.render_text(pg, F, s, c, None)
    scene.add(pg.Sprite(bmp, x, y))


cap("picogame_font.Label", 8, 8, WHITE)
cap("immediate HUD text - drawn with", 8, 24)
cap(".draw(display, buffer) every frame", 8, 38)
scene.refresh()   # paint the background + captions once (labels persist on top)

# three immediate labels with an opaque background so they read as HUD chips
score = picogame_font.Label(pg, F, 12, 66, WHITE, PANEL)
score.set(" SCORE 04820 ")
hi = picogame_font.Label(pg, F, 12, 92, GOLD, PANEL)
hi.set(" HI    12750 ")
lives = picogame_font.Label(pg, F, 12, 118, RED, PANEL)
lives.set(" LIVES 3     ")

while True:
    score.draw(picogame_game.display(), bufA)
    hi.draw(picogame_game.display(), bufA)
    lives.draw(picogame_game.display(), bufA)
