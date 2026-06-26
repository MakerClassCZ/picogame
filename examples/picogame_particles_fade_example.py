# picogame Particles fade demo: bursts that dim toward black as they age.
# Compare to picogame_particles_demo.py (no fade): here particles fade out smoothly
# instead of vanishing at full brightness. Copy with picogame_game.py +
# picogame_input.py. Requires the fade firmware.

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_rand

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(4, 4, 10))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)     # engine loop cap (was time.sleep(1/30))
rng = picogame_rand.Rand()           # seedable engine RNG (was stdlib random)

# fade=True -> each particle's colour ramps to black over its life.
sparks = pg.Particles(256, size=2, gravity=0.15, fade=True)
scene.add(sparks)

W, H = 320, 240
colors = [pg.rgb565(255, 200, 60), pg.rgb565(255, 120, 40),
          pg.rgb565(120, 200, 255), pg.rgb565(200, 255, 140)]

print("Auto-fountains + press A for a burst at a random spot. Particles fade to black.")
frame = 0
while True:
    clock.tick()                             # caps the loop to 30 FPS
    btn.poll()
    if frame % 8 == 0:                       # steady fountain from the bottom
        sparks.emit(W // 2, H - 10, 10, 4, 45, rng.choice(colors))
    if btn.just_pressed(btn.A):
        sparks.emit(rng.randint(40, W - 40), rng.randint(40, H - 40),
                    30, 5, 40, rng.choice(colors))
    sparks.tick()
    scene.refresh()
    frame += 1
