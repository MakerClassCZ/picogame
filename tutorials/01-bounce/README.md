# Tutorial 1 — Bounce (a Breakout/Arkanoid in 9 steps)

We build a complete brick-breaker, one mechanic per step. Each `stepN_*.py` runs on its
own. Run any of them with:
```
python3 sim/run.py tutorials/01-bounce/stepN_name.py --shot /tmp/out.png
```
(add `--hold RIGHT` etc. to hold a button, or `--backend pygame` to play it live.)

The point of the last step is a punchline: **we built the whole game out of coloured
rectangles, and turning it into "real" graphics is a one-line bitmap swap.** Art is
independent of mechanics — which is also why the editor can re-skin a game without
touching its code.

---

### step 1 — `step1_hello.py` · the render loop
picogame is **retained-mode**: you `scene.add()` objects once, then each frame you change
their state and call `scene.refresh()` — the engine redraws. A "paddle" is a `Sprite`
whose bitmap is a solid rectangle from `shp.rect(w, h, colour)`. `picogame_game.setup()`
does the display boilerplate; `picogame_clock.Clock(40)` caps the loop to 40 FPS.
**You see:** a grey bar near the bottom. **Try it:** change the rectangle's size/colour.

### step 2 — `step2_move.py` · input
`picogame_input.Buttons()` samples the buttons each `poll()`. `is_pressed(RIGHT) -
is_pressed(LEFT)` is a tidy −1/0/+1 axis; we move the paddle and clamp it inside the screen.
**You see:** the paddle slides with LEFT/RIGHT. **Try it:** change `SPEED`.

### step 3 — `step3_ball.py` · momentum (sub-pixel)
A `Sprite` stores its position as fixed-point, exposed as `sprite.fx`/`sprite.fy`
(floats). Add a velocity to `fx`/`fy` each frame and the ball drifts smoothly — even at
speeds under 1 px/frame, which integer coordinates can't express. `sprite.x`/`.y` are the
rounded pixels the engine draws at. **You see:** the ball flies off-screen (we fix that
next). **Try it:** change `velocity_x, velocity_y`.

### step 4 — `step4_walls.py` · reflection
A bounce is just flipping the velocity component heading into a wall and pinning the ball
to the edge so it can't tunnel out. Left/right flip `velocity_x`, the top flips `velocity_y`. The bottom
stays open — falling past it is a "miss". **You see:** the ball bounces around three
walls forever. **Try it:** make the top open too and watch it escape.

### step 5 — `step5_paddle.py` · box collision + feel
`pg.collide(ax1,ay1,ax2,ay2, bx1,by1,bx2,by2)` is a fast AABB overlap test. On a paddle
hit (only while moving down) we send the ball up and nudge `velocity_x` by *where* on the paddle
it landed, so you can aim. Falling past the bottom costs a life and re-serves. **You
see:** a real volley you can keep alive. **Try it:** change the `0.06` steering factor.

### step 6 — `step6_bricks.py` · the Tilemap
A `Tilemap` is a grid backed by one tileset bitmap, 1 byte per cell — far cheaper than a
sprite per brick. `shp.tileset_colors(w, h, [colours])` builds a sheet where value 0 is
empty and 1..N are colours. Map the ball's pixel to a tile (`tile_x = pixel_x // BW`), read it, and
set it to 0 to clear it. Clear the wall → rebuild. **You see:** a 10×6 wall you break.
**Try it:** change `ROWS` or the brick colours.

### step 7 — `step7_hud.py` · text / status bar
`picogame_ui.SceneLabel` renders text into the scene as a **fixed** layer (drawn by
`refresh()`, and camera-independent — handy once the world scrolls). It uses the bundled
`terminalio.FONT`, so no font asset. `label.set(...)` re-renders only when the text
changes. **You see:** `SCORE / LIVES` across the top. **Try it:** add the brick count.

### step 8 — `step8_particles.py` · juice (particles + sound)
`pg.Particles` is a cheap burst system: `emit(x, y, count, speed, life, colour)` then
`tick()` each frame. We burst in the brick's colour on every break. `picogame_audio.tone()`
makes a beep with no `.wav` — a blip per hit. (Audio is wrapped in `try/except`, so it's
silent but safe where there's no audio output, like the simulator.) **You see:** coloured
sparks + (on hardware) a blip. **Try it:** change the particle `count`/`gravity`.

### step 9 — `step9_sprites.py` · rectangles → sprites
The payoff. We change **only the two bitmaps**: the ball becomes a round disc
(`shp.circle`) and the paddle gets a multi-colour bitmap with a highlight. Diff this file
against step 8 — the entire game loop is byte-for-byte identical. A `Sprite` doesn't care
whether its bitmap is a rectangle, a generated shape, or a PNG you imported in the editor.
**You see:** the same game, now with a round ball and a shaded paddle. **Try it:** load a
real PNG via the editor → scene pipeline (see `../README.md`) and assign it as the bitmap.

---

**Where to go next:** 02-starship (pools, rotation, shooting, state machine), or jump to
the editor + `picogame_scene` to build levels as data instead of by hand.
