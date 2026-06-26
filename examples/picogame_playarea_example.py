# Arbitrary play-rect demo: the scene renders only a centred column; the static side
# panels (score / next / frame) are drawn once OUTSIDE it. This is the Tetris/Fruitris
# layout on a landscape display - the playfield is a column, everything around it is
# fixed graphics the engine never recomputes.
#
# The trick: Scene(..., left=, right=, top=, bottom=) reserves a border the scene won't
# touch. Here left=right=110 -> a 100px-wide column in the middle of a 320px screen.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_clock
import picogame_ui as ui
import picogame_shapes as shp

W, H = board.DISPLAY.width, board.DISPLAY.height
SIDE = (W - 100) // 2                            # reserve sides -> a 100px play column
COL_BG = pg.rgb565(12, 14, 30)
PANEL = pg.rgb565(34, 44, 78)
WHITE = pg.rgb565(235, 240, 255)

# The scene paints only [SIDE, W-SIDE) x [0, H); the two side panels are ours.
scene, bufA, bufB = picogame_game.setup(background=COL_BG, strip_h=12, left=SIDE, right=SIDE)

# Something alive in the column (a bouncing block), to show the scene only touches it.
block = pg.Sprite(shp.rect(20, 20, pg.rgb565(240, 200, 60)), W // 2, 40)
block.anchor = (0.5, 0.5)
scene.add(block)

# Static side panels: drawn once outside the scene (a HudBar each = bg fill + labels).
left_panel = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, SIDE, H, PANEL)
left_panel.label(terminalio.FONT, 8, 10, WHITE, "SCORE")
score_lbl = left_panel.label(terminalio.FONT, 8, 26, WHITE, "00000")
left_panel.label(terminalio.FONT, 8, 60, WHITE, "LINES")
right_panel = ui.HudBar(pg, board.DISPLAY, bufA, W - SIDE, 0, SIDE, H, PANEL)
right_panel.label(terminalio.FONT, W - SIDE + 8, 10, WHITE, "NEXT")
# A real sprite in the reserved region: proves the border holds graphics the scene
# never recomputes, not just text. The panel paints it once on redraw().
right_panel.add(pg.Sprite(shp.rect(24, 24, pg.rgb565(240, 200, 60)), W - SIDE + 8, 28))
left_panel.redraw()
right_panel.redraw()

x, y, vx, vy = float(W // 2), 40.0, 1.8, 2.4
score = 0
clock = picogame_clock.Clock(30)                 # frame-paced like the other showcases
print("play-area demo: a centred column, static side panels.")
while True:
    x += vx
    y += vy
    if x < SIDE + 10 or x > W - SIDE - 10:       # bounce inside the column walls
        vx = -vx
        score += 1
        left_panel.set_text(score_lbl, "%05d" % score)   # panels update only on change
        left_panel.redraw()
    if y < 10 or y > H - 10:
        vy = -vy
    block.fx = x
    block.fy = y
    scene.refresh()
    clock.tick()
