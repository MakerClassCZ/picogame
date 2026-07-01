# Running picogame on a custom board / bare Pico

Games use `board.DISPLAY`. How you get one depends on your board — **three paths, pick one:**

1. **Your board already has `board.DISPLAY`** (PicoPad, PicoSystem, µGame, Thumby, VIDI X, …)
   → nothing to do. Copy your game as `code.py` + the `lib/` it needs. Done.

2. **No `board.DISPLAY`, and you flashed a picogame *custom-board* firmware** (our pico / pico_w /
   pico2 / pico2_w builds, which expose a `board.DISPLAY` slot) → use **[`firmware_boot/`](firmware_boot/)**.
   A `boot.py` builds the display from `settings.toml`; your game runs **unchanged as `code.py`**.
   The pleasant path.

3. **No `board.DISPLAY`, stock/other firmware** → use **[`launcher/`](launcher/)**. A `code.py`
   launcher builds the display and runs your game (as `game.py`). A little more setup.

**Use ONE folder** — `firmware_boot/` *or* `launcher/`, never both. Both read the **same `settings.toml`** (display, buttons, audio). Each file is self-contained
(display driver inline) — you only copy the one file + your game + the `picogame_*` helpers your game
imports in `/lib`. Add a new display controller by editing the `_driver()` table in the file (Python, no rebuild).
