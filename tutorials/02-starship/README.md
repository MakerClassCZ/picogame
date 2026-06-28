# Tutorial 2 — Starship (a top-down shooter in 8 steps)

Builds a small Asteroids-style shooter. Assumes you've done **01-bounce** (render loop,
input, sub-pixel movement, collision, HUD, particles). Here we add the things a paddle
game can't teach: rotation, vector thrust, object pools, splitting enemies, and a proper
game-state machine.

Run any step:
```
python3 sim/run.py tutorials/02-starship/stepN_name.py --hold UP,B --shot /tmp/out.png
```

---

### step 1 — `step1_ship.py` · a shaped sprite (recap)
`shp.from_mask` turns an ASCII picture into a one-colour bitmap. `anchor=(0.5, 0.5)` puts
the sprite's reference point at its centre — the right choice for something that rotates
and wraps. **You see:** a little ship in the middle. **Try it:** redraw the mask.

### step 2 — `step2_fly.py` · rotation, thrust, wrap
For a ship that spins constantly we bake the rotation into frames -- crisper and cheaper than runtime `sprite.angle`: `shp.poly_frames(size, points, N,
colour)` renders a polygon at N angles into one multi-frame bitmap, and `ship.frame =
angle` shows the right one. A `DIRS` table holds each angle's unit vector; UP accelerates
along the facing vector into the velocity, with a top-speed cap and gentle drag. `wrap()`
teleports across the edges. **You see:** a ship you fly Asteroids-style. **Try it:** change
the thrust `0.25` or the drag `0.99`.

### step 3 — `step3_shoot.py` · object pools
Creating sprites at runtime churns memory. Instead, `picogame_pool.Pool(scene, bitmap, N)`
pre-allocates N hidden sprites once; `spawn()` reveals a free one, `free()` hides it, and
`sprite.visible` *is* the alive flag. Each bullet keeps its velocity + remaining life in
`sprite.data`, its position in `fx`/`fy`. A cooldown caps the fire rate; `just_pressed(B)`
fires on a fresh press. **You see:** a stream of bullets that expire. **Try it:** change the
pool size or `fire_cooldown`.

### step 4 — `step4_rocks.py` · a second pool + waves
Reuse the pool pattern for enemies. Rocks come in 3 sizes; we keep the size in
`sprite.data` and pick the matching ring bitmap with `sprite.bitmap`. `new_wave(n)` spreads
n rocks around the screen, each drifting. **You see:** drifting rock rings. **Try it:**
change the wave count or rock speed.

### step 5 — `step5_collide.py` · circular hits + splitting
`a.near(b, r)` is a fast, no-sqrt distance test on the sprites' centres —
ideal for round things. A bullet that hits a rock frees both; a big/medium rock **splits**
into two smaller ones flying apart. A rock reaching the ship costs a life, grants brief
invulnerability (i-frames, shown by blinking `ship.visible`), and respawns. **You see:**
you can shoot rocks apart and get hit. **Try it:** change `ROCK_RADIUS` or the split velocities.

### step 6 — `step6_waves.py` · score + progression
Smaller rocks score more. A `SceneLabel` shows score + ships. When `rocks.count() == 0` the
field is clear, so we launch the next, bigger wave — the game ramps up. **You see:** a
score that climbs and waves that grow. **Try it:** change the scoring or wave growth.

### step 7 — `step7_particles.py` · explosions, exhaust, sound
One `Particles(fade=True)` system serves two effects: a burst when a rock is destroyed
(many fast, fading sparks) and a thrust flame (a couple of short sparks behind the ship
each frame while thrusting). `fade=True` dims particles as they age. `tone()` gives a fire
beep and a lower boom. **You see:** explosions and an engine trail. **Try it:** change the
explosion `count`/`life` or the beep frequencies.

### step 8 — `step8_states.py` · the state machine (capstone)
A finished game isn't one endless loop — it has **states**. We track `state`: TITLE waits
for a press, PLAY runs the game, GAMEOVER shows the final score and returns to the title.
`new_game()` resets everything; one centred `SceneLabel` shows the message for the non-play
states; death ends the run instead of silently restarting. This is what turns a mechanic
into a game. **You see:** title → play → game over → title. **Try it:** add a high score
that survives across games (see `picogame_save` for NVM persistence).

---

**Where to go next:** the editor + `picogame_scene` — design levels as data and load them,
instead of hand-coding placement. See `../README.md` and
`examples/picogame_platformer_scene.py`.
