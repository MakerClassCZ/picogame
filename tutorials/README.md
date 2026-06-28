# picogame tutorials — learn the engine by building games

These tutorials teach the picogame engine **one mechanic at a time**. Every step is a
complete, runnable program; the next step adds exactly one idea on top. The lesson is
the **diff** between consecutive steps — open `stepN` and `stepN+1` side by side and the
few changed lines are precisely the new concept.

You build real games, not toy snippets:

| Tutorial | Genre | What it teaches |
|----------|-------|-----------------|
| **[01-bounce](01-bounce/)** | Breakout / Arkanoid | the render loop, input, momentum (sub-pixel), wall & paddle bounces, box collision, a Tilemap brick wall, a HUD, particles + sound — and the big idea: **rectangles and sprites are the same object**, so art is a one-line swap. |
| **[02-starship](02-starship/)** | top-down space shooter | rotation via pre-baked frames, vector thrust + screen wrap, **object pools** (bullets, enemies), circular collision + splitting, escalating waves, explosions/exhaust particles, audio, and a **title → play → game-over state machine**. |
| **[03-quest](03-quest/)** | top-down RPG | a **world bigger than the screen** + a following **camera** (`set_view` with clamping), **tile-based wall collision**, a directional **walk animation**, collectible items + a fixed HUD, an **NPC + dialog**, bump **combat** (HP, i-frames), and a **quest** (objective → unlock a door → reach the goal). |

Do them **in order** — each assumes the fundamentals of the ones before it.

## How to run a step

In the desktop simulator (no hardware needed — renders headless, saves a PNG):
```
python3 sim/run.py tutorials/01-bounce/step3_ball.py --shot /tmp/out.png
```
Useful flags: `--frames N` (how long to run), `--hold RIGHT,B` (hold buttons for the
whole run, so you can test input headlessly), `--backend pygame` (a live, playable
window if you have pygame installed).

On the **PicoPad** (or any supported board): copy the step file plus the `lib/` helpers
it imports to `CIRCUITPY/` and name it `code.py` (or import it). Each file's header
comment lists what it needs.

## How each step is structured

- The **header comment** states *what you learn*, *what's new vs the previous step*, and
  the exact run command.
- Inline comments mark the **new lines** so you can see the change at a glance.
- The README in each tutorial folder walks the whole arc with the "why", and ends each
  step with a **Try it** tweak (change a number, feel the difference).

## The engine pieces you'll meet

All the helpers live in `lib/` (pure Python, work on device and in the simulator):

| Helper | Role |
|--------|------|
| `picogame_game.setup()` | take over the display, make a Scene + strip buffers |
| `picogame` (C module) | `Sprite`, `Bitmap`, `Tilemap`, `Particles`, `Canvas`, `Scene`, `collide`, `rgb565` |
| `picogame_input` | buttons → bitmask, `is_pressed` / `just_pressed` |
| `picogame_clock` | frame-rate cap + `dt`; a fixed-timestep accumulator |
| `picogame_shapes` | generate solid/round/polygon bitmaps (rectangles, balls, ships) |
| `picogame_pool` | a fixed-size sprite pool for spawners (bullets, enemies) |
| `sprite.overlaps` / `sprite.near` | zero-alloc box / circular collision, built into Sprite |
| `picogame_ui` | `SceneLabel` (in-scene HUD text), text box, menu |
| `picogame_font` | render strings to bitmaps with the bundled font |
| `picogame_audio` | beeps (`tone()`) and `.wav` playback |

## After the tutorials: stop hand-coding scenes

Once you understand the mechanics by hand, you don't have to keep hand-placing every
tile and sprite in Python. The **editor** (`editor/`) lets you paint maps, place sprites,
and flag tiles visually, then export a **scene** that the `picogame_scene` loader builds
for you — the same data runs on device and in the simulator. See
`examples/picogame_platformer_scene.py` for a full game whose level (tiles, collisions,
coins, enemies, camera) is loaded from editor data, with only the gameplay left in Python.
That's the natural next step: tutorials teach the mechanics, the editor removes the setup
boilerplate.
