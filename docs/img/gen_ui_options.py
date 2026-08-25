# /helpers/text-ui/ illustration: picogame_options.OptionsMenu - a settings box whose rows
# carry an editable VALUE (toggle / stepper / choice / action). UP/DOWN move the cursor,
# LEFT/RIGHT change the selected row's value (shown as <value> on the selected row), A
# returns the row key. Built on ui.SceneBox; scene.refresh() paints it.
import picogame as pg, picogame_game, picogame_font, terminalio
import picogame_options as opt

F = terminalio.FONT
W, H = picogame_game.screen()

BG = pg.rgb565(14, 16, 30)
scene, bufA, bufB = picogame_game.setup(background=BG)

WHITE = pg.rgb565(238, 238, 248)
DIM = pg.rgb565(140, 150, 175)
NAVY = pg.rgb565(20, 28, 58)
BORDER = pg.rgb565(96, 112, 158)


def cap(s, x, y, c=DIM):
    bmp, _, _ = picogame_font.render_text(pg, F, s, c, None)
    scene.add(pg.Sprite(bmp, x, y))


cap("picogame_options.OptionsMenu", 8, 8, WHITE)
cap("editable rows: toggle / step / choice", 8, 24)

rows = [
    {"key": "sfx", "label": "SFX", "kind": "toggle", "value": True},
    {"key": "music", "label": "Music", "kind": "toggle", "value": False},
    {"key": "lives", "label": "Lives", "kind": "stepper", "value": 3, "min": 1, "max": 5},
    {"key": "diff", "label": "Difficulty", "kind": "choice",
     "choices": ["Easy", "Normal", "Hard"], "i": 1},
    {"key": "start", "label": "Start Game", "kind": "action"},
]
menu = opt.OptionsMenu(scene, pg, F, 40, 52, 240, rows, WHITE, NAVY,
                       title="OPTIONS", border=BORDER)
menu.show()

while True:
    scene.refresh()
