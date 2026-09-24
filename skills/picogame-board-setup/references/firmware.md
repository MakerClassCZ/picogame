# Rebuilding picogame firmware (flag changes)

Rebuild ONLY to change a compile-time flag that `settings.toml` can't touch — whether picogame is in
the firmware at all, and its render path. Everything else (buttons, display orientation, audio, gamepad) is settings; try those first.
This needs the CircuitPython build environment (ARM GCC ≥ 14, submodules) — heavier than a settings edit.

## The `CIRCUITPY_PICOGAME_*` flags

| Flag | Default | Change it when |
|---|---|---|
| `CIRCUITPY_PICOGAME` | `0` | master switch — the whole engine module. On in stock CircuitPython for PicoPad, PicoSystem, Fruit Jam, Pico, Pico W and PyBadge; any other board needs `1`. |
| `CIRCUITPY_PICOGAME_FRAMEBUFFER` | `0` | the board scans out of a RAM framebuffer (DVI/HSTX, e.g. Fruit Jam) instead of an SPI bus display. picogame then composites into it. |
| `CIRCUITPY_PICOGAME_FAST_DISPLAY` | `0` | a DMA-driven display backend (`pg.Display`) for SPI panels; the raspberrypi, espressif and atmel-samd ports have one. `0` uses the portable `bus.send` path. |
| `CIRCUITPY_PICOGAME_RGB444` | `0` | the board declares its panel supports 12-bit colour (`picogame.RGB444_SUPPORTED`). Using it is a runtime choice: `PICOGAME_RGB444` in settings.toml or `setup(rgb444=...)`. |
| `CIRCUITPY_PICOGAME_FPU` | *unset* | float path for the 3D math (`pg.project`). **Leave it alone** — unset means the engine derives it from the architecture (hardware FPU → float32, RP2040 → 16.16 fixed). Set 0/1 only to override that on purpose. |

A framebuffer board sets `FRAMEBUFFER=1`; an SPI board on a port with a backend sets `FAST_DISPLAY=1`.

**Not a build flag:** the strip-buffer height is the C define `PICOGAME_STRIP_H` (default **8** with
FAST_DISPLAY, **24** without), settable only in a board's `mpconfigboard.h`/CFLAGS — but you almost
never rebuild for it: `picogame_game.setup(strip_h=N)` tunes it per game at runtime.

## Build

picogame is part of CircuitPython (`github.com/adafruit/circuitpython`). You need a checkout **with
submodules**, then build the board with the flags on the make line (or in its `mpconfigboard.mk`):
```
cd ports/raspberrypi
make BOARD=raspberry_pi_pico2 CIRCUITPY_PICOGAME=1 CIRCUITPY_PICOGAME_FAST_DISPLAY=1 -j$(nproc)   # SPI panel
make BOARD=<dvi_board> CIRCUITPY_PICOGAME=1 CIRCUITPY_PICOGAME_FRAMEBUFFER=1 -j$(nproc)          # DVI board
```
Output is `firmware.uf2` under the board's `build-*/` dir; flash by copying it to the RPI-RP2 / board
bootloader drive.

## Gotchas

- **Toolchain:** ARM GCC ≥ 14 — the tree hard-`#error`s on an older one (Ubuntu 24.04's packaged 13.2
  included), so install the Arm GNU toolchain and put it first on `PATH`.
- **Submodules matter:** a checkout without them fails mid-build; from the CircuitPython checkout
  (not this repo) run `python tools/ci_fetch_deps.py raspberrypi` first. A shallow clone can also fail version
  generation ("Cannot determine version") — build with `CP_VERSION=<the tag you cloned>` if it does.
- **Command-line flags don't invalidate an incremental build** — give a changed-flags build its own
  `BUILD=build-<name>` dir, or `make clean` first, or the flag change is silently ignored.
- **Flash is tight and the API is stabilized** — these flags flip existing code paths; they don't add
  features. Don't remove modules to save flash (a near-full universal build that fits is fine).
- **RAM is the binding constraint** (RP2040 ≈ 25-40 KB free, shared with synthio) — a framebuffer costs
  RAM; `RGB444`/`FAST_DISPLAY` are the FPS levers on SPI boards.

## When you actually need a NEW board definition

Out of scope for this skill (heavier): if the board isn't in CircuitPython at all, it needs a
`ports/raspberrypi/boards/<board>/` with `pins.c` + `mpconfigboard.{h,mk}` (and, for a display,
`board.c` constructing it into `board.DISPLAY`). For most bare Picos you DON'T need this — build the
display in `code.py` (`templates/bare_pico_code.py`) and configure buttons in `settings.toml`.
