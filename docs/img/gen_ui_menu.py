# /helpers/text-ui/ illustration: picogame_ui.SceneMenu - a cursor menu that lives IN the
# scene (built on SceneBox). UP/DOWN move the '>' cursor, A confirms, B cancels. Painted by
# scene.refresh(), so it stays put over a live scene. show() reveals it; the cursor is on
# the first item here.
import picogame as pg, picogame_game, picogame_font, terminalio
import picogame_ui as ui

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


cap("picogame_ui.SceneMenu", 8, 10, WHITE)
cap("cursor menu - UP/DOWN move, A picks", 8, 26)

menu = ui.SceneMenu(scene, pg, F, 92, 70,
                    ["NEW GAME", "CONTINUE", "OPTIONS", "QUIT"],
                    WHITE, NAVY, title="MAIN MENU", border=BORDER)
menu.show()

while True:
    scene.refresh()
