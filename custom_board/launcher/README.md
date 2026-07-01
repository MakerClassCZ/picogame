# launcher — stock-firmware path

For a board with **no native `board.DISPLAY`** on a **stock / non-custom** picogame firmware
(no `board.DISPLAY` slot).

Copy to `CIRCUITPY`:
- `code.py` (this folder) — the launcher: builds the display, makes it `board.DISPLAY`, runs your game.
- `game.py` = **your game, unchanged** (or set `PICOGAME_GAME` in `settings.toml`).
- `settings.toml` — copy `../settings.toml.example`, rename (incl. `PICOGAME_GAME`).
- `/lib/` = the `picogame_*` helpers your game imports (code.py itself needs no extra lib).

Same `settings.toml` as the `firmware_boot/` path. If you can flash the custom-board firmware,
prefer that path (game stays `code.py`, no launcher).
