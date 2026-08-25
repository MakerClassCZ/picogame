---
name: picogame-board-setup
description: >-
  Bring picogame up on a specific board and fix hardware config. Use when the user is running picogame
  on a bare/custom Raspberry Pi Pico (or any board), wiring their own buttons/display/audio, editing
  settings.toml (PICOGAME_BUTTONS / MATRIX / INVERT / MADCTL / AUDIO / USBPAD ...), asking which GPIO a
  button or peripheral is wired to, rebuilding the firmware with different CIRCUITPY_PICOGAME_* flags,
  or hitting a hardware symptom (wrong display colours/orientation, dead buttons, no or too-quiet sound).
---

# picogame board setup

Get picogame running on THIS hardware. The engine is one build; a board is adapted almost entirely by
**settings.toml** (no reflash) plus, for a bare/custom board, a few lines of display code. Firmware is
rebuilt only to change compile-time **flags**. The recurring job is a **bring-up**: discover the wiring,
write the config, dial in the display/audio, verify.

**Golden rule — measure, don't guess.** The device can't be introspected from your machine; you find
the wiring by running a probe on it and reading the serial console. Generate the probe, have the user
run it, read the result, THEN write config. Never invent pin numbers.

**Two footguns to state up front (they waste whole sessions):**
- **A stale `.mpy` in `/lib` shadows the `.py`.** After ANY lib change, redeploy the whole current
  `.mpy` bundle and delete old `picogame_*.mpy`. A symptom whose fix "isn't taking" is almost always this.
- **settings.toml has no floats** — every value is an integer or a string. Write `PICOGAME_HP_VOLUME = -10`,
  never `-10.0`.

---

## Step 0 — identify the situation

Ask (or infer) which path you're on; they share Steps 2-4 but differ at Step 1:

- **A. Supported board, tweak only** (PicoPad etc.): the display and buttons already work; you're only
  adjusting a symptom (colours, volume, a remap). Skip to Step 3 (or straight to `references/troubleshooting.md`).
- **B. Bare / custom board** (a plain Pico + your own buttons + an SPI display): nothing is wired for
  picogame yet. Do the full Step 1 → 2.
- **C. Needs a rebuild**: the change is a compile-time flag (framebuffer/DVI, DMA fast display, RGB444,
  ROMFS assets), not settings. Do Step 4.

**Completion:** you've named the path (A/B/C) and what hardware is attached.

## Step 1 — detect the wiring (bare/custom board)

**Prerequisite — the board must already run picogame CircuitPython.** A bare Pico out of the box runs
nothing, and the probe + every template `import board` / `picogame_*`. First: flash the published
picogame firmware for the chip (`raspberry_pi_pico` / `pico_w` / `pico2` / `pico2_w` — the RP2350 `pico2`
has far more RAM), then copy to `CIRCUITPY/lib/` the current `picogame-libs/mpy/` bundle (delete any old
`picogame_*.mpy` first) AND the panel's display driver (e.g. `adafruit_st7789`, not frozen into the
build). Only then does the probe run.

Generate a probe `code.py` from `templates/wiring_probe.py` (buttons + I2C) and, for a display,
`templates/display_test.py`. Tailor the candidate pin list to the user's board, then have them run it
and paste the serial output. Read it to produce:
- the **button map** — press each button, note the GPIO that reads pressed → a `PICOGAME_BUTTONS` line;
- the **I2C addresses** present (e.g. `0x18` = TLV320 audio DAC, a display/sensor);
- a **working display** — `display_test.py` draws colour bars + orientation markers so the user dials in
  driver, SPI pins, rotation, colour order and inversion by eye.

**Completion:** you hold the concrete pin→button map, the I2C address list, and display parameters that
render correctly — all read back from the device, not assumed.

## Step 2 — write the config

Translate Step 1's findings into `settings.toml` (and, on a bare board, a display built in `code.py`).
The full key reference — every `PICOGAME_*` key, its value format, and worked examples — is
**`references/settings.md`**; pull it and copy the exact syntax. Cover only what the board needs:
buttons (one-pin-per-button `PICOGAME_BUTTONS`, or a scanned `PICOGAME_MATRIX_*` keypad), display
(`PICOGAME_INVERT` / `PICOGAME_MADCTL` / `PICOGAME_BRIGHTNESS`, or the code-built display for a bare
board), audio (`PICOGAME_AUDIO` PWM pin, or I2S `PICOGAME_AUDIO_OUT` + `_VOLUME`), USB gamepad.

**Completion:** `settings.toml` (and any display `code.py`) written, with each value traceable to a
Step 1 reading; nothing hardcoded that should be read from `picogame_game.screen()`.

## Step 3 — verify

Run a shipped game or the launcher on the device. Watch the serial console for a traceback and the
screen/sound for the symptom. If something is off, go to **`references/troubleshooting.md`** — it's a
symptom → cause → fix table for the usual failures (wrong colours/orientation, dead or wrong buttons,
silent or too-quiet audio, "expected a BusDisplay", MemoryError). Re-verify after each change.

**Completion:** a game runs, input responds, the display reads correctly, and audio is audible — all
confirmed on hardware, not inferred.

## Step 4 — rebuild firmware (only for a flag change)

Settings can't change a compile-time flag. When the board needs a different render path (DVI/framebuffer
vs SPI, DMA fast display, RGB444, ROMFS file assets), rebuild per **`references/firmware.md`** (which
flag does what, the build command, the toolchain/RAM gotchas). This is heavier and needs the build
environment; confirm the user wants it before starting.

**Completion:** the rebuilt `.uf2` is flashed and the flag-dependent behaviour is confirmed on device.

---

## References & templates (pull only what a step needs)

| File | Pull it for |
|---|---|
| `references/settings.md` | every `settings.toml` key: buttons, matrix keypad, display, audio, USB gamepad — value formats + examples |
| `references/troubleshooting.md` | symptom → cause → fix: display colours/orientation, buttons, audio silent/quiet, common tracebacks |
| `references/firmware.md` | the `CIRCUITPY_PICOGAME_*` build flags, when to change each, build command, gotchas |
| `templates/wiring_probe.py` | a `code.py` that live-scans GPIO for button presses + scans I2C — produces the button map + addresses |
| `templates/matrix_probe.py` | a `code.py` for a ROW×COLUMN key matrix — prints key_number + (row,col) per press for `PICOGAME_MATRIX_MAP` |
| `templates/display_test.py` | a parametric SPI-display bring-up that draws colour/orientation test patterns to dial in the display |
| `templates/settings.toml` | an annotated starting `settings.toml` |
| `templates/bare_pico_code.py` | build an SPI display in `code.py` and hand it to `picogame_game.setup(display=...)` on a board with no `board.DISPLAY` |
