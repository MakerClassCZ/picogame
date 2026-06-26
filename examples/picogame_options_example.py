# Smoke/demo for picogame_options.OptionsMenu (the provisional settings menu split out of ui).
import board
import picogame as pg
import picogame_game
import picogame_input
import picogame_options as opt
import terminalio

W, H = board.DISPLAY.width, board.DISPLAY.height
WHITE = pg.rgb565(255, 255, 255)
NAVY = pg.rgb565(20, 24, 64)
BORDER = pg.rgb565(120, 140, 220)

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 8, 16))
btn = picogame_input.Buttons()
font = terminalio.FONT

menu = opt.OptionsMenu(scene, pg, font, 40, 40, 240, [
    {"key": "diff", "label": "Difficulty", "kind": "choice", "choices": ["Easy", "Normal", "Hard"]},
    {"key": "vol", "label": "Volume", "kind": "stepper", "value": 7, "min": 0, "max": 10},
    {"key": "snd", "label": "Sound", "kind": "toggle", "value": True},
    {"key": "done", "label": "Start", "kind": "action"},
], WHITE, NAVY, title="OPTIONS", border=BORDER)
menu.show()

while True:
    btn.poll()
    k = menu.tick(btn)
    if k == "done":
        print("Start -> diff=%s vol=%s snd=%s" % (menu.value("diff"), menu.value("vol"), menu.value("snd")))
    elif k == opt.CANCEL:
        menu.hide()
    scene.refresh()
