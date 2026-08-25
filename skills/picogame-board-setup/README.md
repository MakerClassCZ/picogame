# picogame-board-setup

A skill that brings picogame up on a specific board and fixes hardware config — for people running the
engine on a bare/custom Raspberry Pi Pico (or tweaking a supported board).

It covers:
- **settings.toml** — buttons (per-pin or a scanned matrix), display (invert / MADCTL / brightness),
  audio (PWM pin, or I2S DAC output + volume), USB gamepad. No reflash.
- **Wiring detection** — generates a `code.py` that live-scans GPIO for button presses and scans I2C,
  plus a parametric SPI display test, so you read the wiring off the device instead of guessing.
- **Troubleshooting** — symptom → cause → fix for the usual failures (wrong colours/orientation, dead
  buttons, silent or too-quiet audio, common tracebacks).
- **Firmware rebuild** — the `CIRCUITPY_PICOGAME_*` compile-time flags, when each matters, and how to
  build (for changes settings can't make).

Start at `SKILL.md`. Templates in `templates/`, deep references in `references/`.
