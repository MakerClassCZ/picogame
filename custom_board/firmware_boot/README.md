# firmware_boot — custom-board firmware path

For a board with **no native `board.DISPLAY`** running a picogame **custom-board firmware**
(pico / pico_w / pico2 / pico2_w with the `board.DISPLAY` slot).

Copy to `CIRCUITPY`:
- `boot.py` (this folder) — builds the display; runs once at boot, persists into your game.
- `settings.toml` — copy `../settings.toml.example`, rename, set your display + buttons + audio.
- `code.py` = **your game, unchanged**.
- `/lib/` = the `picogame_*` helpers your game imports (boot.py itself needs no extra lib).

That's it — no launcher. Existing games and `stage`-based games work because `board.DISPLAY` exists
before your code runs.

**Note:** after changing a display setting in `settings.toml`, press RESET (or re-plug USB) — `boot.py` builds the display only at power-on, so a soft reload keeps the old one. Button/audio changes are picked up by a normal reload.
