# picogame Sprite.bitmap setter demo: swap a sprite's graphic at runtime.
# Tests three cases the dirty-rect tracker must handle:
#   1. same-size swap   -> graphic changes, no stale pixels
#   2. shrink swap      -> the LARGER previous footprint must be cleared
#   3. swap while moving -> old+new bounds both repaint
# Copy with picogame_game.py to CIRCUITPY. Requires the Sprite.bitmap firmware.

import time
import picogame as pg
import picogame_game
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(10, 14, 30))

big_red = shp.rect(48, 48, pg.rgb565(220, 70, 70))     # large
big_blue = shp.rect(48, 48, pg.rgb565(80, 140, 240))    # same size, different colour
small_green = shp.rect(16, 16, pg.rgb565(80, 220, 120))  # much smaller (shrink test)

# (a) Stationary sprite that cycles graphic + size in place. If the old footprint
# isn't cleared on shrink, you'll see red/blue corners left behind around the
# small green square.
swapper = pg.Sprite(big_red, 60, 90)
scene.add(swapper)

# (b) Moving sprite that ALSO swaps bitmap each step (old+new bounds repaint).
mover = pg.Sprite(small_green, 180, 60)
scene.add(mover)

print("Sprite.bitmap swap: watch for stale pixels when the big square shrinks.")
seq = [big_red, big_blue, small_green]
i = 0
mx = 180
mdir = 3
frame = 0
while True:
    if frame % 12 == 0:                       # swap the stationary one periodically
        i = (i + 1) % len(seq)
        swapper.bitmap = seq[i]

    mx += mdir                                 # move + swap the travelling one
    if mx < 10 or mx > 280:
        mdir = -mdir
    mover.move(mx, 60)
    mover.bitmap = big_blue if (frame // 4) % 2 else small_green

    scene.refresh()
    frame += 1
    time.sleep(1 / 20)
