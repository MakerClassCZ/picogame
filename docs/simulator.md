# Desktop simulator

The web [Playground](/playground/) lets you try picogame in a browser. The **desktop simulator**
runs the same game-facing API on your PC and is better suited to local files, converted PNG assets,
headless screenshots, and scripted command-line runs.

It ships inside the repo (`sim/`). Clone [picogame](https://github.com/MakerClassCZ/picogame) and you
have everything: the simulator, the games, and the `picogame_*` helpers.

```sh
git clone https://github.com/MakerClassCZ/picogame
cd picogame
```

## Install

Headless mode (render frames, save a screenshot, no window) works out of the box. For a live,
interactive window, install pygame:

```sh
pip install pygame
```

:::tip[If it doesn't work]
- `pip` not found? Use `python3 -m pip install pygame` instead.
- Run every command from the cloned `picogame` folder, the one that holds `sim/` and `lib/`.
- Without pygame, use `--shot out.png` to run headlessly and save the final frame.
:::

## Run a game

Play it in a window (the default when pygame is installed; it prints the controls on start):

```sh
python3 sim/run.py demos/picogame_flappy.py
```

Render a few frames headlessly and save a screenshot (handy for docs, tests, and CI):

```sh
python3 sim/run.py demos/picogame_flappy.py --frames 80 --shot shot.png
```

### Options

| Flag | What it does |
|---|---|
| `--backend pygame` / `pil` | force a live window / headless. Default: a window if pygame is installed, else headless (a `--shot` or `--profile` run stays headless). |
| `--frames N` | run N frames, then stop (default 150) |
| `--shot FILE` | save a PNG of the final frame |
| `--shot-at N` | save that PNG at frame N instead of at the end |
| `--hold RIGHT,A` | hold these buttons for the whole run, so you can drive it with no keyboard |
| `--profile` | print per-phase timing |

In the live window: arrows or **WASD** move; `F` (or `Ctrl`) = A, `G` (or `Space`) = B, `R`/`Q` = X, `T`/`E` = Y.

## Web or desktop?

Both expose the same game-facing API, so the same game code runs in either. Under the hood they differ (the browser runs the native C engine compiled to WASM; the desktop simulator is a Python reference implementation), so timing, RAM behaviour, audio and panel effects are approximations - verify those on the device.

| | Web Playground | Desktop simulator |
|---|---|---|
| Setup | none, runs in the browser | clone the repo (plus pygame for a window) |
| Best for | trying an idea, sharing a link, first steps | asset files, headless screenshots, CLI automation, local iteration |
| Assets | code-generated shapes | your own PNGs and converted art |

Once a game runs well, copy it to the board and test its timing, controls, audio, and memory use.
See [Run on hardware](hardware.md).
