# picogame M4 demo: HUD text using the bundled font (terminalio.FONT).
# Copy picogame_font.py, picogame_game.py, picogame_ui.py and this file
# (as code.py) to CIRCUITPY. Pure Python over the engine -> no reflash needed.
#
# A few sprites move in the lower area (dirty-rect scene); a score + FPS label
# live IN the scene as fixed (camera-independent) HUD layers, painted by the
# single scene.refresh() - the firmware's built-in font, zero font assets.

import time
import array
import random
import board
import terminalio
import picogame as pg
import picogame_game
import picogame_ui

W, H = 320, 240
BG = pg.rgb565(20, 24, 40)
HUD_BG = pg.rgb565(0, 0, 0)
WHITE = pg.rgb565(255, 255, 255)
YELLOW = pg.rgb565(255, 210, 60)


def make_blob(size, r, g, b):
    pal = array.array("H", [
        pg.rgb565(0, 0, 0),
        pg.rgb565(r, g, b),
        pg.rgb565(min(r + 80, 255), min(g + 80, 255), min(b + 80, 255)),
    ])
    data = bytearray(size * size)
    c = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            if abs(x - c) + abs(y - c) <= c:
                data[y * size + x] = 2 if abs(x - c) + abs(y - c) <= c * 0.45 else 1
    return pg.Bitmap(data, size, size, format=pg.PAL8, palette=pal, transparent=0)


print("building assets...")
blob = make_blob(24, 70, 160, 230)
# One call: take over the display, alloc strip buffers, build the Scene.
scene, _bufA, _bufB = picogame_game.setup(background=BG)

HUD_H = 18
random.seed(7)
movers = []
mv = []
for i in range(6):
    s = pg.Sprite(blob, random.randint(0, W - 24), random.randint(HUD_H + 2, H - 24))
    scene.add(s)
    movers.append(s)
    mv.append([random.choice((-2, 2)), random.choice((-2, 2))])

# HUD labels live IN the scene as fixed layers - scene.refresh() paints them,
# so no per-frame draw call and no one-time full-screen clear are needed.
score_label = picogame_ui.SceneLabel(scene, pg, terminalio.FONT, 4, 2, YELLOW, HUD_BG)
fps_label = picogame_ui.SceneLabel(scene, pg, terminalio.FONT, 210, 2, WHITE, HUD_BG)

print("HUD demo running... (Ctrl-C to stop)")
score = 0
frame = 0
fps_t = time.monotonic()
fps_frames = 0
fps_val = 0.0

while True:
    for i in range(len(movers)):
        s = movers[i]
        x = s.x + mv[i][0]
        y = s.y + mv[i][1]
        if x < 0 or x > W - 24:
            mv[i][0] = -mv[i][0]
            x = s.x + mv[i][0]
        if y < HUD_H + 2 or y > H - 24:
            mv[i][1] = -mv[i][1]
            y = s.y + mv[i][1]
        s.move(x, y)

    score += 1
    # set() alone updates the text (skips re-render when unchanged); the single
    # scene.refresh() below repaints both the game area and the HUD layers.
    score_label.set("SCORE %06d" % score)
    fps_label.set("%d FPS" % int(fps_val))

    scene.refresh()                       # game area + fixed HUD (dirty-rect)

    frame += 1
    fps_frames += 1
    now = time.monotonic()
    if now - fps_t >= 1.0:
        fps_val = fps_frames / (now - fps_t)
        print("FPS: %.1f" % fps_val)
        fps_t = now
        fps_frames = 0
