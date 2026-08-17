# firmware_boot — custom-board firmware path

For a board with **no native `board.DISPLAY`** running a picogame **custom-board firmware**
(pico / pico_w / pico2 / pico2_w with the `board.DISPLAY` slot).

Copy to `CIRCUITPY`:
- `boot.py` (this folder) — builds the display; runs once at boot, persists into your game.
- `settings.toml` — copy `../settings.toml.example`, rename, set your display + buttons + audio.
- `code.py` = **your game, unchanged**.
- `/lib/` = the `picogame_*` helpers your game imports (boot.py itself needs no extra lib).

**Then press RESET (or unplug/replug USB) once.** `boot.py` runs **only at power-on** — saving files
over USB soft-reloads `code.py` but does *not* re-run `boot.py`, so right after copying it your game
still sees no display and dies with `AttributeError: 'NoneType' object has no attribute 'width'`
(that is `board.DISPLAY` being `None`). One hard reset fixes it; from then on the display is there
before your code runs.

That's it — no launcher. Existing games and `stage`-based games work because `board.DISPLAY` exists
before your code runs.

**Note:** the same applies after changing a *display* key in `settings.toml` (`PICOGAME_DISPLAY`,
`PICOGAME_PINS`, `PICOGAME_SIZE`, `PICOGAME_FLIP`, `PICOGAME_INVERT`, `PICOGAME_BGR`, `PICOGAME_BAUD`):
press RESET. Button/audio keys are read by the game, so a normal reload picks those up.
