# picogame particles demo. Copy with picogame_game.py, picogame_input.py,
# picogame_clock.py. Requires the particles firmware.
#
# D-pad moves the emitter, A fires a burst, B is a continuous fountain. Particles
# fall under gravity and age out; the scene only repaints where they are.

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 8, 16))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

W, H = 320, 240
ps = pg.Particles(256, size=2, gravity=0.2)


cursor = pg.Sprite(shp.rect(4, 4, pg.rgb565(255, 255, 255)), 160, 120)
scene.add_all([ps, cursor])

COLORS = [pg.rgb565(255, 180, 40), pg.rgb565(80, 200, 255), pg.rgb565(255, 80, 120)]
ci = 0
print("D-pad move emitter | A burst | B fountain")
while True:
    btn.poll()
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)
    dy = btn.is_pressed(btn.DOWN) - btn.is_pressed(btn.UP)
    if dx or dy:
        cursor.move(max(0, min(W - 4, cursor.x + dx * 3)),
                    max(0, min(H - 4, cursor.y + dy * 3)))
    if btn.just_pressed(btn.A):
        ps.emit(cursor.x, cursor.y, 60, 4, 40, COLORS[ci % 3])
        ci += 1
    if btn.is_pressed(btn.B):
        ps.emit(cursor.x, cursor.y, 4, 3, 35, pg.rgb565(120, 220, 255))
    ps.tick()
    scene.refresh()
    clock.tick()
