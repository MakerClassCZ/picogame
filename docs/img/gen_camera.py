import picogame as pg, picogame_game, picogame_shapes as shp
BG = pg.rgb565(30, 40, 60)
scene, _, _ = picogame_game.setup(background=BG)
# a world bigger than the 320x240 screen; set_view scrolls into the middle of it.
T = 26
COLS, ROWS = 22, 16
ts = shp.tileset_colors(T, T, [pg.rgb565(60, 150, 90), pg.rgb565(150, 110, 70), pg.rgb565(90, 140, 230)])
tm = pg.Tilemap(ts, COLS, ROWS)
for ty in range(ROWS):
    for tx in range(COLS):
        if (tx + ty) % 2 == 0:
            tm.set_tile(tx, ty, 1)
        elif tx % 4 == 0 or ty % 4 == 0:
            tm.set_tile(tx, ty, 2)
        else:
            tm.set_tile(tx, ty, 3)
scene.add(tm)
player = pg.Sprite(shp.circle(22, pg.rgb565(245, 80, 80)), 210, 175); player.anchor = (0.5, 0.5); scene.add(player)
scene.set_view(-120, -95)                                  # camera scrolled into the bigger world
# a fixed HUD layer: stays put on screen no matter where the camera is
bar = pg.Sprite(shp.rect(320, 20, pg.rgb565(14, 16, 30)), 0, 0); bar.anchor = (0, 0); scene.add(bar, fixed=True)
for i in range(3):                                         # mock HUD pips on the fixed bar
    pip = pg.Sprite(shp.rect(14, 10, pg.rgb565(245, 200, 60)), 6 + i * 18, 5); pip.anchor = (0, 0)
    scene.add(pip, fixed=True)
while True:
    scene.refresh()
