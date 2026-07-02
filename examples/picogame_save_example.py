# picogame persistence demo (NVM): proves the save survives a reboot.
# A boot counter increments every power-on/reset (so you SEE persistence even without scoring);
# A adds to the score, B saves it as the highscore. The values are shown on screen AND printed.
# Copy with picogame_save.py + picogame_ui.py to CIRCUITPY. No reflash needed (NVM is built in).

import board
import terminalio

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_save
import picogame_ui as ui

# A tiny scene (just a background) so the frame loop renders — that's also what lets the desktop
# simulator cap the run with --frames. The persistence itself is all in picogame_save below.
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(12, 16, 34), top=40)
W = board.DISPLAY.width
btns = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

# The first arg is THIS game's key. A different game using the same NVM slot would fail the key
# check and get its own defaults, never our highscore.
save = picogame_save.Save("savedemo", {"hiscore": ("I", 0), "boots": ("H", 0)})
data = save.load()
data["boots"] += 1
save.save(data)        # persist the boot counter right away

hud = ui.HudBar(pg, board.DISPLAY, bufA, 0, 0, W, 40, pg.rgb565(20, 26, 50))
stat = hud.label(terminalio.FONT, 6, 6, pg.rgb565(255, 255, 255))
help_ = hud.label(terminalio.FONT, 6, 22, pg.rgb565(255, 180, 120))
score = 0


def draw_hud():
    stat.set("boot #%d   hiscore %d   score %d" % (data["boots"], data["hiscore"], score))
    help_.set("A +100   B save hiscore   RESET=test persistence")
    hud.draw()


draw_hud()
print("boot #%d  |  stored hiscore = %d" % (data["boots"], data["hiscore"]))
print("A = +100 score, B = save as hiscore. RESET the board to confirm it persisted.")

shown = None
while True:
    btns.poll()
    if btns.just_pressed(btns.A):
        score += 100
    if btns.just_pressed(btns.B):
        if score > data["hiscore"]:
            data["hiscore"] = score
            save.save(data)
            print("NEW HIGHSCORE saved:", score)
        else:
            print("not a highscore (best = %d)" % data["hiscore"])
    key = (score, data["hiscore"])
    if key != shown:                 # repaint the HUD only when a value changes
        shown = key
        draw_hud()
    scene.refresh()                  # render the frame (also lets the sim's --frames cap the run)
    clock.tick()
