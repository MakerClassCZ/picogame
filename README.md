# picogame

**picogame** is a small 2D game engine for the **PicoPad** - a pocket handheld (320×240
screen, D-pad + a few buttons, RP2040 with little RAM) running CircuitPython. The heavy lifting -
sprites, tilemaps, a retained scene with automatic dirty-rectangle redraw, blit effects -
is a **native C module** built into the firmware; on top of it sits a set of small **Python
helper libraries** and a **desktop simulator**, so you write games in plain Python and run
them on your PC before ever touching hardware.

This repository is the **public collection**: finished games, short demos, feature examples,
step-by-step tutorials, the simulator, and the asset tools - everything you need to learn the
engine and build for it. The engine itself and the helper library live in their own repos
(see [The wider picogame project](#the-wider-picogame-project) below).

👉 **Docs, guides and an in-browser playground:** <https://picogame.makerclass.cz/>

---

## What's in this repo

| Folder | What it holds |
|---|---|
| [`games/`](games/) | complete, polished games - ready to play |
| [`demos/`](demos/) | short demos, varios game genres |
| [`examples/`](examples/) | minimal examples of the engine features |
| [`tutorials/`](tutorials/) | three guided, build-it-yourself tutorials |
| [`sim/`](sim/) | the desktop simulator (try/develop games on your PC) |
| [`tools/`](tools/) | asset converters and build helpers |

> The Python code here imports the `picogame_*` helper modules. To run anything (in the
> simulator or on device) those helpers must be available as a **`lib/`** folder - get them
> from **[picogame-libs](https://github.com/MakerClassCZ/picogame-libs)**.

---

## Quick start

Run any game or demo on the desktop simulator (needs Python 3; a live window needs `pygame`):

```bash
python sim/run.py games/picoracer/code.py --backend pygame   # live, playable window
python sim/run.py demos/picogame_snake.py                    # headless, runs ~150 frames
python sim/run.py demos/picogame_snake.py --shot shot.png    # + save a screenshot
```

**Simulator controls** (live `pygame` window):

| Keyboard | Button |
|---|---|
| Arrow keys | D-pad |
| `Z` or `Ctrl` | A |
| `X` or `Space` | B |
| `A` / `S` | X / Y |

**On the PicoPad:** copy a game's `code.py` and its assets, plus the `lib/` helpers it
imports, to the board's `CIRCUITPY` drive. Each file's header comment lists what it needs.

---

## Games

Complete features rich games - each in its own folder (`code.py` + assets):

| Game | Genre |
|---|---|
| [`picoracer`](games/picoracer/) | top-down racer - 5 laps, with ghost cars replaying your earlier laps |
| [`picotris`](games/picotris/) | falling-block puzzle in a reserved play-area well |
| [`picowing`](games/picowing/) | vertical shoot-'em-up - hold the sky against raiders |
| [`squest`](games/squest/) | Seaquest-style underwater shooter (rescue divers, watch your air) |
| [`train`](games/train/) | a logic "snake puzzle" - steer to the gate without crossing your trail, 50 levels |

## Demos

[`demos/`](demos/) has a short, focused demo for each classic arcade genre - Breakout,
Asteroids, Flappy, a maze chase, Snake, a platformer and more. Great for seeing how a whole
genre maps onto the engine in one small file.

## Examples

[`examples/`](examples/) isolates a **single engine feature** per file - Canvas, StripDraw,
Tilemap, Particles, the HUD, sprite anchors, scrolling/camera, save data, scene loading,
juice effects, and so on. Reach for these when you want to learn one specific building block.

## Tutorials

[`tutorials/`](tutorials/) teaches the engine **one mechanic at a time** - every step is a
runnable program, and the lesson is the *diff* to the next step. Three complete games:

- **[01 - Bounce](tutorials/01-bounce/)** · Breakout / Arkanoid → <https://picogame.makerclass.cz/tutorials/01-bounce/>
- **[02 - Starship](tutorials/02-starship/)** · top-down space shooter → <https://picogame.makerclass.cz/tutorials/02-starship/>
- **[03 - Quest](tutorials/03-quest/)** · top-down RPG → <https://picogame.makerclass.cz/tutorials/03-quest/>

---

## The simulator (`sim/`)

`sim/run.py` runs a game on the PC by emulating the device - it provides the `picogame`
module and the CircuitPython stubs, so the same code runs unchanged on your machine and on
the PicoPad. Useful flags:

| Flag | Effect |
|---|---|
| `--backend pygame` | a live, playable window (default `pil` is headless) |
| `--frames N` | how many frames to run (headless; default 150) |
| `--shot FILE` / `--shot-at N` | save a screenshot (at the end, or at frame N) |
| `--hold RIGHT,B` | hold buttons for the whole run (test input headlessly) |
| `--profile` | a cProfile + per-frame allocation report |

## Tools (`tools/`)

Helpers for turning art and sound into engine-ready assets:

| Script | Run it | Purpose |
|---|---|---|
| `png2picogame.py` | `python tools/png2picogame.py art.png -o art.py` | convert a PNG/BMP into an asset module - a single image, a `--frames` animation atlas, a `--tile WxH` tile sheet, or a `--map` tilemap |
| `pack_sheet.py` | `python tools/pack_sheet.py IN.py NAME --outdir DIR` | pack a big sprite sheet into a raw `.bin` streamed from flash, so the pixels don't sit in RAM |
| `scene_build.py` | `python tools/scene_build.py level.scene.json` | bake an editor scene file into a compact runtime `SCENE` module the loader reads |
| `synth_preview.py` | `python3 tools/synth_preview.py` | render `picogame_synth` sound effects to `.wav` so you can tune them by ear (the simulator is silent) |
| `build_mpy.sh` | `tools/build_mpy.sh` | precompile the Python helpers to `.mpy` bytecode (faster load, less RAM on device) |

---

## The wider picogame project

This repo is the games-and-learning side of picogame. The rest:

| Repository | What it is |
|---|---|
| **[picogame-libs](https://github.com/MakerClassCZ/picogame-libs)** | the `picogame_*` Python helper library - input, HUD/UI, clock, juice effects, sprite pools, audio, save, and more. These are the `lib/` modules every game here imports. |
| **[circuitpython](https://github.com/MakerClassCZ/circuitpython)** | the CircuitPython firmware fork that carries the **native C engine** (the `picogame` module). Build and flash this to run games on the device. |
| **[picogame-stage](https://github.com/MakerClassCZ/picogame-stage)** | a compatibility layer to run existing `ugame`/`stage` games on the picogame engine. |

And the home base - docs, feature guides, the glossary, and a playground that runs picogame
in your browser: **<https://picogame.makerclass.cz/>**


