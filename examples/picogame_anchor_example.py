# picogame Sprite.anchor demo: two sprites pulse in size (via Sprite.scale).
# LEFT keeps the default top-left anchor -> it grows down-right from a fixed corner.
# RIGHT uses anchor=(0.5, 0.5) -> it grows symmetrically around a fixed centre.
# Proves the anchor keeps x/y meaning a chosen pivot even as the sprite scales.
# Copy with picogame_game.py, picogame_shapes.py, picogame_clock.py. Requires the anchor firmware.

import picogame as pg
import picogame_game
import picogame_shapes as shapes
import picogame_clock

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(12, 14, 28))

# One small square per side; Sprite.scale resizes it around its anchor pivot.
left = pg.Sprite(shapes.rect(28, 28, pg.rgb565(230, 110, 90)), 90, 120)   # default anchor (0,0) = top-left
right = pg.Sprite(shapes.rect(28, 28, pg.rgb565(110, 200, 230)), 230, 120)
right.anchor = (0.5, 0.5)                        # centre pivot
scene.add_all([left, right])

# Small dot markers at each pivot so you can see the anchor point stay put.
# The dots are themselves centre-anchored so they sit EXACTLY on the pivot
# (a default top-left dot would look ~half-its-size off).
dot_bmp = shapes.rect(4, 4, pg.rgb565(255, 255, 0))
for dx, dy in ((90, 120), (230, 120)):
    m = pg.Sprite(dot_bmp, dx, dy)
    m.anchor = (0.5, 0.5)
    scene.add(m)


def tri(t):                                      # triangle wave 0..1, period 2s
    p = (t * 0.5) % 1.0
    return 2.0 * p if p < 0.5 else 2.0 * (1.0 - p)


print("Left = top-left anchor (grows from corner). Right = centre anchor (grows around dot).")
clock = picogame_clock.Clock(30)
t = 0.0
while True:
    t += clock.tick()
    s = 0.5 + 1.5 * tri(t)                        # pulse ~0.5x..2.0x (scale is float, 1.0=1x)
    left.scale = s
    right.scale = s
    scene.refresh()
