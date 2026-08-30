# Running picogame on hardware (PicoPad / RP2040)

You can build and test in the browser or the [desktop simulator](simulator.md) before copying
the game to a device. The simulator does not reproduce the device's RAM limits, timing, controls,
or audio, so verify those on the board. On a PicoPad, deployment takes three steps.

## Quick start: deploy to a PicoPad

The PicoPad has a prebuilt firmware with `board.DISPLAY` and a button profile. You do not need
to build firmware for normal deployment.

1. **Flash the firmware once.** Hold **BOOTSEL** while plugging in USB (or double-tap **RESET**) → an
   `RPI-RP2` drive appears → drag [`picopad.uf2`](supported-hardware.md) onto it → it reboots as a
   `CIRCUITPY` drive. You only do this once, and it's reversible: your files on `CIRCUITPY` survive a same-layout reflash (a firmware that moves the flash layout - e.g. adds or resizes the ROMFS asset region - reformats the drive; back up first).
2. **Copy your game.** Drag your `code.py` onto the `CIRCUITPY` drive, plus the `lib/` helper modules it
   imports (the `picogame_*` files) and any assets. It's the same game code you ran in the sim.
3. **Start the game.** Save `code.py` or reset the board. No additional display or button setup is needed.

On another board (a bare Pico, PicoSystem, …) the wiring and button map differ. See
[Supported hardware](supported-hardware.md). Everything else on this page is the same.

> The rest of this page covers RAM limits, `.mpy`, splitting large programs, and porting to a
> board without prebuilt firmware. You can skip it for a first PicoPad deployment.

> Clock / SPI / display-speed limits (how the core clock drives the display SPI, the ST7789
> ceiling, overclocking the RP2350, how to test) live in **[Clocks, SPI &amp; display limits](hardware-limits.md)**.

---

## 1. The RAM budget

RP2040 has **264 KB** SRAM. In the measured PicoPad firmware build, static allocations use
about 72 KB, leaving roughly **190 KB** of Python heap and an initial largest contiguous block
of about **130 KB**. These figures change with the firmware version and configuration.

| Thing | Cost |
|---|---|
| `picogame_game.setup()` strip buffers (2 × 320×`strip_h`×2) | `strip_h=8` (DMA default) → **10 KB**, `strip_h=24` → **30 KB** |
| full-screen `Canvas(320, 240)` | **150 KB** ⚠️ larger than the measured contiguous block |
| `Canvas(320, 130)` (e.g. a pseudo-3D road) | **83 KB**, OK alone (see `microrace`), but not on top of much else |
| `Canvas(320, 20)` status bar | 12.8 KB |
| a tile/sprite Bitmap | width×height×frames × (1 B PAL8 / 2 B RGB565) |

Consequences:
- **Avoid a full-screen Canvas on the measured RP2040 build.** If you need a custom raster (road, shape
  field), keep it as small as the content (band it), or use a `Tilemap` for large
  scrolling areas (1 byte/cell instead of 2 bytes/pixel: a 320×960 noise sky is
  **600 KB as a Canvas but ~5 KB as a shade Tilemap**).
- For a HUD, use `SceneLabel`, `HudBar`, or another helper that does not retain a full-width
  pixel surface unless the design needs one.
- **`strip_h` defaults to 8 on current DMA builds** (about 10 KB for two 320-pixel-wide
  RGB565 buffers, compared with 30 KB at 24). The measured PicoPad build was also faster at
  the smaller value. Non-DMA ports default to 24 to reduce the number of blocking transfers.
- **`gc.collect()` between scenes/levels** so the previous scene's buffers are freed
  before the next allocates.
- If a game is too big as one program, **split it** (see §4).

`MemoryError: memory allocation failed, allocating N bytes` = you're over budget;
note which scene/line and shrink the biggest buffer there (usually a Canvas).

**Fragmentation, not just total free.** A long session that allocates and frees big
buffers fragments the heap: `gc.mem_free()` can read ~90 KB while a 51 KB allocation
still fails (no contiguous run). If a monolith dies on a big Canvas even though "there's
plenty free", that's this. The fix is a pre-allocated **arena** (`lib/picogame_arena.py`
+ the firmware `Canvas(..., buffer=)` arg): grab one big buffer up front and slice it.
The general writeup (with the largest-contiguous-block probe and a networking example)
is **[Fit it in RAM](memory.md)**.

---

## 2. Device and simulator

The simulator and firmware expose the same game-facing API, but the simulator cannot model the
device's heap, transfer timing, speaker, or panel-specific effects exactly. Use
`picogame_game.setup()` so the same code selects an SPI display or framebuffer correctly. It
returns `(scene, buffer_a, buffer_b)`; the buffers exist on the SPI path and are `None` on the
framebuffer path.

`Scene.display` is available in both environments. `Scene.add(..., fixed=True)` uses a
keyword-only `fixed` argument, and low-level `pg.render()` accepts `scene.display`. Test on the
target board before release, especially after changing assets or firmware.

### Framebuffer boards (Fruit Jam DVI) and colour depth

On a board whose display is a RAM framebuffer rather than an SPI panel — an RP2350 picodvi/HSTX
board like the **Adafruit Fruit Jam** — `picogame_game.setup()` composites into the scanout buffer
directly (its returned buffers are `None`). It picks the pixel format from the framebuffer's colour
depth automatically, so **your game code is unchanged**; you only set the depth once, in
`settings.toml`:

- **`CIRCUITPY_DISPLAY_COLOR_DEPTH = 16`** — 16-bit RGB565 (full colour). The usual choice; on
  picodvi it caps the resolution (e.g. 320×240 doubled).
- **`CIRCUITPY_DISPLAY_COLOR_DEPTH = 8`** — 8-bit **RGB332**, the only depth the picodvi hardware
  offers at **640×480** (Fruit Jam full resolution). The engine quantizes each finished band 565→332
  as it publishes it, so you still author in `pg.rgb565(...)`; colours are just reduced to 3-3-2 bits.

Under the hood this is `pg.Framebuffer(buffer, width, height, rgb332=True)` for the 8-bit path vs
`native_rgb565=True` for 16-bit (`setup()` chooses for you). The 8-bit/RGB332 path needs a picogame
build whose `Framebuffer` supports `rgb332=` — a recent engine; older builds raise a clear
"lacks rgb332" error telling you to reflash.

---

## 3. Import-time / compile-time traps

- **Big `.py` as `code.py` → MemoryError on import.** CircuitPython compiles `code.py`
  source at boot, so a large parse tree causes a temporary RAM spike. Deploy larger modules
  as `.mpy`, compiled with an `mpy-cross` version compatible with the target firmware, and
  use a small `code.py` launcher (`import my_scene`).
- **Huge list literals → `RuntimeError: pystack exhausted`.** A `array.array('H',
  [7168, ...])` literal pushes thousands of elements onto the VM stack (and builds a
  ~28 KB transient list). For big RGB565 tilesets, **bake them as PAL8 with `DATA =
  b'...'`** (a single `bytes` constant: half the size, no list, and byte-data is
  alignment-safe on Cortex-M0+). Reserve palette index 0 = transparent.

Compile a module:
```bash
circuitpython/mpy-cross/build/mpy-cross  mymodule.py  -o  mymodule.mpy
```

---

## 4. Option for a large game: one program per scene

If a game cannot hold all assets and scene code at once, split it so only one scene's data is
live. The `journey_hw` example uses this layout:

- **`dj_common.mpy`** — shared scaffolding + helpers (display setup, `new_scene`,
  `status_bar` as a Label, `play()` with **no** wipe-cover Canvas, bitmap helpers).
  `import *` from it.
- **`scene_<name>.mpy`** — one program per scene; imports only the assets it needs, so
  only one scene's RAM is live at a time. Runs its own `while True: seg(); gc.collect()`.
- **`code.py`** — a one-line launcher (`import scene_intro`); edit/rename to switch
  scenes, or build a small button menu.

The simulator or video build may use a separate combined entry point. Concrete example:
**`examples/journey_hw/`** (`dj_common.py` + `scene_*.py`,
plus `journey_mono.py`, a StripDraw single-file variant, zero pixel buffer / no arena) vs. the sim/video
monolith `examples/picogame_demo_journey.py` (with sound + wipe). See
`examples/journey_hw/README.md`.

On-device layout:
```text
CIRCUITPY/
  code.py                 # import scene_<name>
  scene_*.mpy             # one per scene
  dj_common.mpy           # shared helpers
  <assets>.mpy            # dj_hero, dj_town, ... (only what the scenes import)
  lib/picogame_*.mpy      # engine Python helpers
```
(No sound on device unless you wire up `picogame_audio`; the demo's chiptune is
offline-only, baked into the recorded video.)

---

## 5. The firmware must contain the feature you call

Symptoms like `AttributeError: ... has no attribute 'X'` or `can't set attribute 'X'`
usually mean the **flashed firmware is older than the code that uses X**. E.g. an old
build had `Sprite.scale` as read-only → `can't set attribute 'scale'`.

> **On a PicoPad you don't build firmware**: just reflash the latest prebuilt
> [`picopad.uf2`](supported-hardware.md) and the feature is there. The build steps below are only for
> porting to another board or working on the engine itself.

- Reflash (PicoPad): drop the latest [`picopad.uf2`](supported-hardware.md) over BOOTSEL; your files survive it as long as the firmware keeps the same flash layout (see the backup note above).
- Build (porting / engine dev): see [the engine guide](engine.md) §"Building the firmware"
  (ARM GCC ≥ 14 toolchain + venv; `make BOARD=pajenicko_picopad -j$(nproc)`).
  Output: `circuitpython/ports/raspberrypi/build-pajenicko_picopad/firmware.uf2`.
- Verify a symbol is present without flashing:
  `arm-none-eabi-nm build-.../firmware.elf | grep sprite_set_scale`.
- Flash: enter the RP2040 bootloader (RPI-RP2 drive), copy `firmware.uf2`. The
  CIRCUITPY filesystem (your `.mpy` files) is preserved across a same-layout firmware flash.

Current firmware has: `Sprite.scale/angle/shadow` setters, the full `Canvas` primitive
set (`triangle`/`ellipse`/`ring`/`fill_round_rect`/`frame3d`), and C `noise`
(`value2d`/`value1d`/`fbm2d`/`fbm1d` - fixed-point implementations under the plain names).

---

## 6. Performance notes

For the game-side speed levers — the loop in a function, dirty-rect-friendly motion, avoiding
per-frame allocation — see **[Performance](/performance/)**. The notes here are the engine/hardware side.

- **Noise is C, and fixed-point** (Q16.16): fast on the FPU-less RP2040; the names are
  `value2d`/`value1d`/`fbm2d`/`fbm1d`.
- **Canvas drawing is C** (`fill_rect`, `frame3d`, …): Python only issues the calls.
  What costs is the Canvas *buffer* (RAM), not the drawing.
- **`StripDraw` = immediate mode without a retained pixel surface.** For full-frame *animated* surfaces
  (pseudo-3D road, gradient sky, procedural background) use `pg.StripDraw(callback, …)`
  instead of a Canvas. It draws into each render strip and avoids the **150 KB pixel buffer**
  of a full-screen Canvas. It repaints every frame, so use it for animated content rather than
  static art. See [the engine guide](engine.md) → `StripDraw` and
  `examples/picogame_stripdraw_example.py`. The `StripDraw` object, callback, and game state still
  use RAM, but there is no full-screen surface to fragment the heap.
- Dirty-region rendering reduces work in a mostly static scene; full-screen scrolling still
  repaints the whole view. Measure the frame rate with your artwork, firmware, and SPI clock.

See also: [engine API](engine.md), [scene format](scene-format.md),
`tutorials/` (step-by-step), `examples/`
(genre examples include `microrace`, which uses an 83 KB Canvas in its measured configuration).
