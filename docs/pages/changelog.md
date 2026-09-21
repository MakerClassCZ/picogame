---
title: What's new
description: What changed in picogame, summarised by period — helper-lib releases, firmware, the editor and playground, the simulator and the docs. Breaking changes are listed separately.
sidebar:
  label: What's new
  order: 2
---

picogame moves in small helper-lib releases (`circup update` gets you the newest) and in
firmware builds (see [Supported hardware](/supported-hardware/)). This page does not list
every release — it summarises what mattered in each period, newest first, and keeps the
changes that need action from you in one place.

## Breaking changes at a glance

Newest first. Everything else on this page is additive.

- **0.3.1 (2026-09-19)** — `picogame_game.setup(rgb444="auto")` asks `settings.toml`, not the
  firmware: it turns RGB444 on only where `PICOGAME_RGB444 = 1` is set *and* the controller can
  do it. It used to enable RGB444 wherever the firmware supported it. Support and benefit are
  not the same — RGB444 trades CPU for wire time, so it wins on a slow bus (a PyBadge at 24 MHz
  gains about 26%) and loses on a fast one (a PicoPad at 62.5 MHz). If you were relying on the
  old automatic behaviour, add the key.
- **0.3.0 (2026-09-06)** — the helper libs ship as one set: `picogame_script` needs the
  `picogame_ui` from the same release (no compatibility shim). Update the whole bundle, not
  single files. Older `*.scene.json` / `project.json` files still load; `tools/scene_build.py
  migrate` rewrites them as `game.json`.
- **0.2.1 (2026-08-31)** — `picogame_pool`: the pool owns its in-use bit, so `sprite.visible`
  only means "draw this". Code that hid a pooled sprite to free its slot must `release()` it.
- **Firmware 2026-08-23 + libs 0.1.36** — `Tilemap.tile(x, y[, value])` split into
  `get_tile(x, y)` and `set_tile(x, y, value)`. Update firmware and libs together.
- **0.1.32 (2026-08-17)** — `picogame_rand` became an alloc-free 30-bit Lehmer generator;
  the same seed now produces a different sequence than before.
- **0.1.30 (2026-08-14)** — `picogame_ray` renders natively and needs a firmware with
  `Canvas.vspans`. Older firmware: stay on 0.1.29.
- **Firmware 2026-08-27 (upstream freeze)** — module-level `pg.render()` takes its layer
  list as `layers` (`Display.render()` keeps `sprites`); `StripDraw.invalidate()` with a
  partial rectangle raises `ValueError`; `Scene`'s strip buffers default to `None`
  (framebuffer boards no longer pass two explicit `None`s).

## 2026-09-07 → 09-21 · libs 0.3.1 → 0.3.2

**picogame reaches SAMD51 handhelds.** The PyBadge builds it upstream now, over a SERCOM SPI
DMA display backend — the third port to implement the fast-display contract, after RP2 and
ESP32-S3. The helper libs those boards need arrived with it: buttons behind a shift register,
an I2C gamepad, the chip's true DAC for sound, and the accelerometer as a D-pad. Every preset
was measured on the hardware, not read off a datasheet.

- **Libs** — four new input and audio modules, each a `Buttons()` source or an output backend,
  so games need no changes to use them. `picogame_shiftpad` reads buttons on a 74HC165 (with a
  measured PyBadge preset); `picogame_i2cpad` gained the Adafruit Mini I2C Gamepad and analogue
  sticks that find their own centre at attach; `picogame_audioout` drives the chip's true DAC
  and raises the `SPEAKER_ENABLE` pin some boards gate, which is why those handhelds were
  silent; `picogame_tiltpad` turns the accelerometer into a D-pad. `picogame_game.VERSION` now
  says which bundle is on the board, and `picogame_iso` draws blocks as Sprites by default,
  keeping triangles for procedural geometry. 0.3.2 fixes the Mini I2C Gamepad's horizontal
  axis, which read mirrored on the real pad.
- **Firmware** — picogame is built in on the PyBadge (upstream #11430) and the Pimoroni
  PicoSystem (#11359). `Canvas.text` failed to link on images built without `terminalio` (the
  ja/ko/ru builds of some boards) and raises `NotImplementedError` there instead. A program
  that switched the panel to RGB444 used to leave it that way, so the REPL afterwards was drawn
  in the wrong format (#11428). Six ST7735 boards sent `0x2a` where INVOFF belongs (#11429):
  no visible effect, but wrong for anyone reading the sequence. Three size passes (#11365,
  #11371, #11379) gave tight boards room back.
- **Editor** — a UX audit in three batches: first the ways a level quietly came out broken,
  then the daily friction, then the words. Save goes straight to the board, art is painted
  without leaving the page, and `scene_build.py`'s checks run while you build instead of after.
  An eyedropper, a way to remove a level and a tile-region tool arrived; `Save` keeps the name
  of the file you opened, with `Save as…` behind a split button. One tab owns the autosave
  slot, so two open tabs can no longer overwrite each other.
- **Simulator** — the flash mapper is `storage.map_file` now, not `pg.xip_map`, matching the
  binding proposed upstream; the simulator ships a `storage` stand-in with the device's shape.
- **Docs & skill** — the board-setup skill dials display orientation with MADCTL and tests it
  through picogame, and names the two orientation keys as two phases of one job rather than two
  options to choose between.

## 2026-09-01 → 09-06 · libs 0.2.2 → 0.3.0

**One `game.json` per game, and stories in Python.** The editor now saves a single
`game.json` (every level, the assets table, sounds, zones) plus device-ready `.pal8` art
and a `story.py`; on the device `picogame_scene.Game(pg, "game.json")` streams it one level
at a time and bakes at boot — no conversion step, no per-level `.mpy`. Story scripts run
through the `picogame_story` interpreter with the `d.*` contract (`d.say`, `d.goto`,
`d.view`). `tools/scene_build.py check | art | migrate` validates, converts art and
upgrades old files.

- **Libs** — 0.2.5 is a per-frame cost pass with the API unchanged: `Buttons.poll()` is ~3×
  cheaper, `Pool.count()`/`spawn()` are O(1), `View` caches tile property tables, `Fade`,
  `Camera` and mode-7 skip idle work, synth waveform tables build on first use (touch them
  at startup, not mid-game). Teardown for launcher-style reloads: `Buttons.deinit()`,
  `Synth.deinit()`, `SceneBox.lift()`. Small UI additions: `text_width()`/centred text,
  `HudLabel.color`, `SceneMenu.set_items()`, `SceneLabel.x/.y` move the label, `fx.Flash`,
  `fx.Camera` takes the HUD band.
- **Firmware** — a `Scene`/`pg.render()` given anything but a bus display hard-faulted on
  RP2350 (Fruit Jam went dark); it is a `TypeError` now (upstream #11306). `StripDraw` and
  `Triangles` dirty rectangles are screen-space again (a scrolled scene left ghosts).
  ESP32-S3: `pg.project()` uses the Xtensa FPU inline (float is now the fast path).
- **Editor & playground** — PNG, `.pal8` and `story.py` opened on their own attach to the
  open game; the playground runs a whole game folder, drops the legacy in-browser baker and
  is refrozen with the 0.3.0 libs.
- **Simulator** — `--seed`, `--tap`, `--strict-dirty`, a reserved-band warning, an honest
  `--profile` leak verdict, and the public surface is checked against the firmware's
  signatures, not just names.
- **Docs & skill** — a truth audit corrected nine statements about changed behaviour and the
  `.mpy` shadowing explanation (it is `sys.path` order, not the extension); the game-design
  skill gained a narrative/dialogue playbook and measured audio costs.

## 2026-08-24 → 08-31 · libs 0.2.0 → 0.2.1

**The engine is in CircuitPython.** The `picogame` module was merged into
adafruit/circuitpython on 2026-08-27 (#11199); it ships in a future CircuitPython release,
and MakerClass builds carry it until then. The docs prose moved into the public
[picogame repo](https://github.com/MakerClassCZ/picogame) — pull requests welcome.

- **Libs** — 0.2.0: `picogame_scenebake` / `picogame_scene.load_json` bake a level's JSON
  on the device; `tile_has()` for tile flags; the README indexes every module. 0.2.1:
  `picogame_script` — story scripts as generators driven by a `Director` (`retarget()` on a
  map change); `View.set_tile_prop()` for runtime tile flags; `picogame_road`;
  `Raycaster.set_cell()` for worlds that change; `fx.Shake(None)` for strip-rendered games;
  `seq.Script` for self-playing demos; `shapes.masks()` and `gap=`.
- **Editor & playground** — Story panel (CodeMirror) and effects edited in modal forms with
  visual object pickers; whole-project *Try in playground* handoff; exports named by purpose
  with ASCII maps as the default; custom tile flags; shift+wheel scrolls horizontally. The
  playground stages any helper lib that drifted since the last freeze on every Run, and has
  a user-picked integer display scale (1–4×).
- **Simulator** — a verification run is fast and its leak report honest; the racing road is
  implemented; `Tilemap` drawing is fuzzed against an unculled reference; frame counts are
  taken at the game's frame boundary.
- **Games & docs** — the platformer demo everyone copies was fixed and rewritten without the
  traps; the shipped games practice what the playbook preaches; two CI docs checks that
  reported green regardless of findings were fixed.

## 2026-08-17 → 08-23 · libs 0.1.32 → 0.1.36

**Typing, one display source, and the Tilemap split.**

- **Libs** — `picogame-stubs`: type stubs for the native module (a wheel on every release)
  so VS Code / Pylance completes `pg.*`. `picogame_game.screen()` / `display()` find the
  board's display anywhere (`supervisor.runtime.display` first) — stop reading
  `board.DISPLAY` in games. `picogame_debug` is optional everywhere. `picogame_i2cpad`
  really recovers a stuck bus and accepts a bus name in `PICOGAME_I2C`. Options menus
  rebuild their rows at runtime. `FAST_DISPLAY_SUPPORTED` feature detection.
- **Firmware** — universal builds with ROMFS built in (the separate `-romfs` downloads are
  gone); rasterizer and scaled-blit fast paths; `Display` and `Framebuffer` always
  registered.
- **Editor** — Tiled import, the asset converter, autosave, multi-select, runner templates;
  save into a project folder, export levels as ASCII maps, open an exported scene back, and
  a notice when someone else wrote the file.
- **Games & tools** — *Corona* (horde survivor) and *Pictor* (a PicoLibSDK port) ship;
  *Train* and *PicoWing* get title splashes; `tools/p8music.py` bakes PICO-8 tracker music;
  the level editor and asset converter are standalone apps in the public repo.
- **Docs** — half-resolution art with power-of-two upscale; the real tilemap encodings
  (grid / rows+legend) in the scene format; scripted input timelines in the simulator.

## 2026-08-03 → 08-16 · libs 0.1.21 → 0.1.31

**Native pseudo-3D, I2C pads, tracker music, Tiled.**

- **Libs** — `picogame_ray` renders fully natively (the caster emits merged runs,
  `Canvas.vspans` paints them — about 8× faster than the Python-per-strip version on
  RP2040, flat across viewing angles). `picogame_i2cpad`: a generic I2C gamepad driver with presets and declarative
  recipes (qwstpad and friends), bus recovery after a soft reload. `picogame_music`: a
  PICO-8 tracker player on synthio (4 channels ≈ 3 ms/frame on RP2040). `picogame_iso`:
  isometric projection with a batch block builder. The scene format carries tile
  orientations (flips/rotations), sprite angles and zone/point data — what
  `tools/tiled2scene.py` and the editor export.
- **Firmware** — the 3D primitives wave: `pg.project()`, `Canvas.fill_triangles()` with
  strip-replay offsets, the `pg.Triangles` layer, `pg.vblank()`, and an experimental
  `pg.core1` fork-join on RP2.
- **Docs** — the *engine-only* page (the C module without helpers), the native raycaster
  pipeline, showcase GIFs for the three 3D techniques.

## 2026-07-27 → 08-02 · libs 0.1.17 → 0.1.20

**Two players, a games menu, mode-7 and raycasting.**

- **Libs** — local multiplayer: `Buttons(sources=[...])` per player and `find_pads()`;
  `open_framebuffer()` sets the DVI resolution from code on Fruit Jam; `picogame_launcher` —
  the games menu with FruitJamOS-compatible `metadata.json`; menu helpers, `wrap()`,
  zero-alloc `compose_into()`, polygon sub-region fills. `picogame_mode7` and `picogame_ray`
  arrive (perspective floor camera, raycaster, billboard sprites) on top of the native
  `pg.raycast` primitive.
- **Docs & site** — homepage rewritten around benefits; launcher, quickstart and performance
  pages; the pseudo-3D helper page; `llms.txt` and a downloadable agent skill for AI coding
  assistants; the **picogame-game-design** skill published in the public repo; share links
  compress the code into the URL.
- **Games & sim** — FruitJamOS-compatible metadata and icons for every game; two-player input
  in the simulator.

## 2026-07-13 → 07-26 · libs 0.1.12 → 0.1.16

**Fruit Jam.** USB HID gamepads (`picogame_usbpad`) and keyboards (`picogame_usbkbd`) as
button sources, framebuffer HUD and immediate rendering, I2S audio with a volume setting,
8-bit (RGB332) framebuffer displays, and `PICOGAME_DEBUG` diagnostics that unmask silent
failures.

- **Libs** — `ExtraFont`: fallback glyphs from small BDF subsets; keyboard-matrix buttons,
  panel variant and backlight from `settings.toml`; the font glyph cache went flat (an
  RP2040 out-of-memory fix).
- **Games** — a loop-in-function performance pass over 16 titles; the tutorials adopt the
  `State` + `main()` loop shape.
- **Site** — every gallery game plays in the browser with the real SFX clips; showcase GIFs
  from a simulator capture harness; the device-download flow; text-UI widget screenshots;
  the picogui toolkit in the playground.

## 2026-06-25 → 07-12 · libs 0.1.0 → 0.1.11 — first public releases

The helper libs became a circup-installable bundle (0.1.0, CI-built `.py` + `.mpy`), the
public repo opened under MIT (tools, simulator, examples, tutorials, games) and the docs
site went live with the playground and the level editor.

- **Libs** — `synth.Drone` for engine/siren sounds; built-in button profiles for PicoSystem,
  uGame22, uGame S3 and Thumby Color; audio pin and panel invert read from `settings.toml`
  for custom boards; an alloc-free frame loop (`Clock`/`FixedStep`, `Shake`, UI);
  `picogame_anim` animates a list of bitmaps; `picogame_arena` mark/release lifetimes;
  `picogame_cutscene` story scenes; `picogame_debug` RAM watermarks; on-device sound with
  `picogame_synth` and the signature SFX kit `picogame_sfx`.
- **Playground** — runs the WASM build of the real C engine (no Python engine variant) with
  editor handoff; native RGB565 in the browser framebuffer.
- **Games** — *Train*, *PicoRacer*, *Picatro* (a poker deckbuilder), *Bang! Bang!* (artillery
  duel); every game size-independent.
- **Tools & docs** — the custom-board bring-up kit; the ROMFS asset pipeline
  (`png2picogame --split`, `build_romfs.py`); the desktop simulator guide; a doc API lint and
  an EN/CZ structure check in the build.

## Before the releases (2025-08 → 2026-06)

Dates before June 2026 are approximate — the workspace was not under git yet.

- **2026-05/06** — API freeze (naming conventions, `tick`/`poll`/`is_*`), collision moves
  into the C engine (`Sprite.overlaps`/`near`) and `picogame_collide` retires; NVM save and
  an options menu; the ESP32-S3 board; the repo split (engine staging, libs bundle, public
  distro, docs) and the first tutorials — Bounce, Starship, Quest.
- **2026-01/02** — the declarative scene format (JSON → baked `.mpy`) and loader, the web
  level editor, the WASM playground, RP2350 boards, more games.
- **2025-11/12** — per-sprite scale/rotate/transpose/flip and the flash/tint/dither/shadow
  blit effects, `Particles`, `StripDraw` (0-RAM full-frame effects), the desktop simulator,
  the first `picogame_*` helper suite and `Canvas.text` with no glyph cache.
- **2025-09/10** — `picogame` becomes a module of its own: `Sprite` + `Bitmap`, a retained
  `Scene` with dirty-rect strip rendering, the async-DMA display path on RP2040, then
  `Tilemap` with a moving camera and `Canvas`.
- **2025-08** — the seed: the PicoPad's `stage`/`ugame` libraries cap sprites at one 16×16
  tile; a native blitter for arbitrary-size sprites is dropped in behind that API.
