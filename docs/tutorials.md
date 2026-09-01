# picogame tutorials — learn the engine by building games

These tutorials introduce the picogame engine **one group of mechanics at a time**. Every
step is a complete, runnable program, and the next step builds on it. Compare `stepN` and
`stepN+1` side by side to see the code added for the new concept.

Each tutorial ends with a small completed game:

| Tutorial | Genre | What it teaches |
|----------|-------|-----------------|
| **[01-bounce](/tutorials/01-bounce/)** <sub>([source](../tutorials/01-bounce/))</sub> | Breakout / Arkanoid | the render loop, input, sub-pixel movement, wall and paddle bounces, box collision, a `Tilemap` brick wall, a HUD, particles, and sound. Placeholder shapes and imported art both use a `Bitmap` on the same `Sprite`, so replacing the artwork does not change the game logic. |
| **[02-starship](/tutorials/02-starship/)** <sub>([source](../tutorials/02-starship/))</sub> | top-down space shooter | rotation via pre-baked frames, vector thrust + screen wrap, **object pools** (bullets, enemies), circular collision + splitting, escalating waves, explosions/exhaust particles, audio, and a **title → play → game-over state machine**. |
| **[03-quest](/tutorials/03-quest/)** <sub>([source](../tutorials/03-quest/))</sub> | top-down RPG | a **world bigger than the screen** + a following **camera** (`set_view` with clamping), **tile-based wall collision**, a directional **walk animation**, collectible items + a fixed HUD, an **NPC + dialog**, bump **combat** (HP, i-frames), and a **quest** (objective → unlock a door → reach the goal). |

Do them **in order**: each assumes the fundamentals of the ones before it.

## How to run a step

You can run each step in the browser with the **Try it** button. To run a step file locally,
use the desktop simulator (no hardware needed; it can render
headless, saves a PNG):
```bash
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
- The README in each tutorial folder explains why each addition is useful and ends each
  step with a small **Try it** change.

## The engine pieces you'll meet

All the helpers live in `lib/` (pure Python, work on device and in the simulator):

| Helper | Role |
|--------|------|
| `picogame_game.setup()` | resolve the display and create a Scene; on SPI targets, also create render strips |
| `picogame` (C module) | `Sprite`, `Bitmap`, `Tilemap`, `Particles`, `Canvas`, `Scene`, `collide`, `rgb565` |
| `picogame_input` | buttons → bitmask, `is_pressed` / `just_pressed` |
| `picogame_clock` | frame-rate cap + `dt`; a fixed-timestep accumulator |
| `picogame_shapes` | generate solid/round/polygon bitmaps (rectangles, balls, ships) |
| `picogame_pool` | a fixed-size sprite pool for spawners (bullets, enemies) |
| `sprite.overlaps` / `sprite.near` | zero-alloc box / circular collision, built into Sprite |
| `picogame_ui` | `SceneLabel` (in-scene HUD text), text box, menu |
| `picogame_font` | render strings to bitmaps with the bundled font |
| `picogame_audio` | beeps (`tone()`) and `.wav` playback |

## After the tutorials: move to the scene editor

Once you understand the mechanics, the **editor** (`tools/editor/`; hosted at /editor/ on this site) can replace hand-placing every
tile and sprite in Python. It lets you paint maps, place sprites, and assign tile properties,
then export a **scene** that the `picogame_scene` loader builds. The same data runs on device and in the simulator. See
`examples/picogame_platformer_scene.py` for a full game whose level (tiles, collisions,
coins, enemies, camera) is loaded from editor data, with only the gameplay left in Python.
The tutorials teach the mechanics; the editor moves level layout into data.

## Next steps after the tutorials

After the tutorials, continue with:

- **[Game patterns](/concepts/patterns/)** + **[Snippets](/snippets/)** — the reusable
  game-loop + `State` shape every bigger game grows into, plus a ready-to-run **game
  skeleton** to start your own project from (open it in the
  [Playground](/playground/?ex=game-skeleton)). This is the natural next step now that
  you've built three games by hand.
- **[Feature guide](features.md)** — the task-oriented tour of everything the engine can do
  (which drawing surface to pick, sprite transforms, collision, HUDs, audio, RAM budgeting),
  with alternatives for each. Use it when choosing a tool for a task.
- **The helpers** (`lib/`) — the pure-Python modules you met above (`picogame_pool`,
  `picogame_ui`, `picogame_clock`, `picogame_anim`, …); the feature guide links each to its use.
- **[Glossary](/concepts/glossary/)** — short, plain-language definitions of any unfamiliar
  term such as sprite, tilemap, dirty region, AABB, or parallax.
