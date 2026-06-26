# picogame Canvas demo: draw primitives + an animated gauge on a transparent
# overlay, with moving sprites BEHIND it so the transparency is visible.
# Copy with picogame_game.py to CIRCUITPY. Requires Canvas firmware.

import picogame as pg
import picogame_game
import picogame_clock
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(12, 16, 36))

W, H = 320, 240


# Background movers: these slide left-right BEHIND the overlay. Wherever the
# Canvas is transparent (the magenta key), you see these blobs through it;
# wherever a shape was drawn, the shape covers them.
blob = shp.rect(24, 24, pg.rgb565(230, 60, 200))
movers = [pg.Sprite(blob, 30 + i * 80, 70 + (i % 2) * 90) for i in range(4)]
scene.add_all(movers)

KEY = pg.rgb565(255, 0, 255)            # transparent key
cv = pg.Canvas(220, 130, transparent=KEY)
cv.move(50, 50)
scene.add(cv)                            # overlay sits ON TOP of the movers
cv.clear(KEY)                            # fully transparent to start
cv.fill_rect(10, 10, 60, 30, pg.rgb565(220, 80, 80))
cv.rect(80, 10, 60, 30, pg.rgb565(80, 220, 120))
cv.line(10, 55, 200, 95, pg.rgb565(120, 180, 255))
cv.fill_circle(165, 75, 20, pg.rgb565(240, 220, 60))

print("Canvas overlay over moving blobs. Blobs show through the transparent gaps.")
mv = [3, -3, 3, -3]
t = 0
clock = picogame_clock.Clock(30)
while True:
    for i in range(len(movers)):
        s = movers[i]
        x = s.x + mv[i]
        if x < 0 or x > W - 24:
            mv[i] = -mv[i]
            x = s.x + mv[i]
        s.move(x, s.y)

    w = 10 + (t % 180)
    cv.fill_rect(10, 105, 200, 10, pg.rgb565(25, 25, 40))   # gauge background
    cv.fill_rect(10, 105, w, 10, pg.rgb565(60, 220, 120))   # gauge fill
    scene.refresh()
    t += 3
    clock.tick()
