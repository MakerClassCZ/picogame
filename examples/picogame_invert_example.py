# Display-inversion demo - exercises the panel's hardware colour inversion (ST7789/ST7735
# INVON/INVOFF) exposed as picogame.invert + the picogame_fx.InvertFlash helper. Inversion sends
# NO pixel data: the whole screen flips to its negative instantly, so it's a FREE full-screen
# hit-flash (cheaper than a Fade overlay). A bright, colourful scene makes the flip obvious.
#
#   A  -> hit-flash: invert for a few frames, then back (InvertFlash.pulse)
#   B  -> toggle a PERSISTENT inversion on/off (picogame.invert directly)
#
# NOTE: on the desktop simulator invert is a silent no-op (it's a hardware feature), so the scene
# just sits there; run it on a real ST7789 PicoPad to see the screen flip. Copy picogame_* helpers.

import board
import terminalio
import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_fx as fx
import picogame_shapes as shp
import picogame_ui as ui

W, H = board.DISPLAY.width, board.DISPLAY.height
# fast=False: the invert command (picogame.invert) goes out on the SAME synchronous bus as the
# pixels, so INVON/INVOFF can't be lost in the fast Display's async DMA stream (which left the
# panel stuck inverted - the revert command raced the DMA). Fine here: no scrolling, low FPS.
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(20, 24, 40), fast=False)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# A colourful scene so the inversion is dramatic (every colour -> its negative).
bars = [
    (pg.rgb565(230, 60, 60), 30),
    (pg.rgb565(240, 170, 40), 78),
    (pg.rgb565(240, 230, 60), 126),
    (pg.rgb565(70, 200, 90), 174),
]
for col, y in bars:
    s = pg.Sprite(shp.rect(W - 80, 28, col), 40, y)
    scene.add(s)

ball = pg.Sprite(shp.circle(28, pg.rgb565(80, 160, 255)), W // 2, H // 2)
ball.anchor = (0.5, 0.5)
scene.add(ball)

# The PicoPad's ST7789 init sends INVON, so the panel's NORMAL/correct state is invert=True.
# InvertFlash(normal=True) (the default) flips to invert=False for the flash, then restores INVON.
NORMAL = True
flash = fx.InvertFlash(board.DISPLAY, frames=6, normal=NORMAL)   # the free hardware hit-flash
inverted = False                                  # persistent-invert state (B toggles vs NORMAL)

hud = ui.SceneLabel(scene, pg, terminalio.FONT, 6, 6, pg.rgb565(255, 255, 255), pg.rgb565(20, 24, 40))
hud.set("A flash-invert   B toggle invert")

print("A = hardware invert flash | B = toggle persistent invert (device only)")
bx, by, vx, vy = float(W // 2), float(H // 2), 2.3, 1.7
while True:
    btn.poll()

    if btn.just_pressed(btn.A):
        flash.pulse()                             # invert for `frames`, then auto-revert
    if btn.just_pressed(btn.B):
        inverted = not inverted                   # toggle relative to the panel's NORMAL state
        pg.invert(board.DISPLAY, (not NORMAL) if inverted else NORMAL)

    # a little motion so it doesn't look frozen
    bx += vx
    by += vy
    if bx < 20 or bx > W - 20:
        vx = -vx
    if by < 40 or by > H - 20:
        vy = -vy
    ball.move(int(bx), int(by))

    scene.refresh()
    flash.tick()        # AFTER refresh: the INVON/INVOFF is the frame's LAST bus op, so a render
    clock.tick()          # can't clobber it. (Logic is verified in sim; this guards a HW timing race.)
