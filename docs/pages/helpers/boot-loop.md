---
title: "Boot & game loop"
description: "Guide to picogame_game, picogame_clock and picogame_input: take over the display, pace the frame, and read the buttons."
---

These three modules set up the display, pace the game loop, and read buttons. A typical `code.py` calls `picogame_game.setup()` once, creates `Buttons()` and `Clock()`, then repeats four steps: poll input, update state, refresh the scene, and tick the clock. See [/reference/](/reference/) for the signatures.

## picogame_game

Call `setup()` once before creating the game objects. It resolves the display backend, stops `displayio` from refreshing independently where applicable, and returns a new `Scene` with the memory it needs.

- `setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0, rgb444=False)` - returns `(scene, buffer_a, buffer_b)`. On an SPI display it disables automatic refresh, clears `root_group`, and allocates two full-width render strips. On a framebuffer target such as Fruit Jam DVI or the browser playground, the scene composites into the framebuffer and both returned buffers are `None`. The `Scene` keeps any allocated strip buffers alive. A game that only calls `scene.refresh()` can ignore the returned buffers: `scene, _, _ = picogame_game.setup(...)`.
  - `display` - explicit display object. If omitted, setup takes `supervisor.runtime.display` (the board's primary display).
  - `strip_h` - height of each render strip on the SPI path. It defaults to the board's compiled `picogame.STRIP_H` value. The two buffers occupy `2 * width * strip_h * 2` bytes: about 10 KiB at 320×8 or 30 KiB at 320×24. On the measured RP2040 DMA path, a smaller strip also improved overlap between rendering and transfer; without DMA, larger strips reduce the number of blocking transfers. Override the value per call or at firmware build time with `-DPICOGAME_STRIP_H=N`. Framebuffer targets ignore it. See [/memory/](/memory/) for the trade-off.
  - `background` - fill colour behind the scene, an RGB565 int. Build one with `pg.rgb565(r, g, b)`.
  - `top` / `bottom` / `left` / `right` - reserve a border (px) the scene won't render into, so it paints only the inner play rect. You draw that border yourself (a HUD bar, side panels) once, and it is never recomputed per frame.
  - `fast` - on an SPI display, `True` selects `pg.Display` when available; `False` uses the portable busdisplay renderer. Setup falls back automatically when the fast backend is absent.
  - `rgb444` - `True` requests 12-bit colour on a compatible fast SPI backend. Use `"auto"` to enable it only when the board reports support. Framebuffer targets ignore this setting. See [/hardware/](/hardware/).

```python
import picogame as pg
import picogame_game

BG = pg.rgb565(20, 24, 30)
scene, buffer_a, buffer_b = picogame_game.setup(background=BG, strip_h=16, top=12)
# scene is a pg.Scene; add sprites and refresh it each frame
# a simple game that never draws in immediate mode can skip the buffers: scene, _, _ = ...
scene.add(sprite)
scene.refresh()
```

:::note[Gotchas]
keep `scene` alive for the life of the game. On the SPI path it owns the two render buffers; the framebuffer path does not create them. A border reserved with `top`/`bottom`/`left`/`right` is not painted by the scene, so draw it separately. See [/scene-format/](/scene-format/) for scene data and [/hardware/](/hardware/) for display notes.
:::

## picogame_clock

`Clock` caps the loop to a target FPS and returns elapsed time as `dt`, so movement can be independent of frame rate. `FixedStep` runs game logic in equal time steps when physics or collision must be reproducible.

`Clock`:

- `Clock(fps=30, max_dt=0.1)` - cap the loop to `fps` (use `0` for uncapped) and clamp the returned `dt` to at most `max_dt` seconds, so a pause or stall can't produce a giant `dt` that teleports everything.
- `tick()` - sleeps until the frame boundary, then returns the real `dt` in seconds since the last `tick()`. Anchors to the ideal schedule so a small oversleep can't accumulate into drift; if you ran over budget it anchors to real time instead, keeping `dt` accurate. Call once per frame.
- `tick_async()` - awaitable variant that yields to other `asyncio` tasks during the idle wait instead of blocking. Needs the `asyncio` library available (raises `RuntimeError` otherwise). Note rendering itself is blocking, so async only helps in the cap-sleep gap.
- `set_fps(fps)` - change the target FPS on the fly (e.g. menus at 30, action at 60). `0` uncaps.

`FixedStep`:

- `FixedStep(step_fps=60, max_steps=5)` - fixed timestep of `1/step_fps` seconds, running at most `max_steps` logic steps per frame (the cap avoids a "spiral of death" when rendering can't keep up - backlog is dropped).
- `step_count()` - returns how many fixed steps to run this frame (`0..max_steps`). Loop `for _ in range(step_count())` and use the constant `self.dt`; this form allocates nothing, good for hot loops.
- `dt` - the constant step duration in seconds. Pass it to your update.
- `steps()` - generator form yielding `self.dt` per step. Convenient, but allocates a generator each call; prefer `step_count()` in the main loop.

```python
import picogame_clock

clock = picogame_clock.Clock(30)        # cap to 30 FPS
while True:
    dt = clock.tick()                   # sleeps to the frame boundary, returns real dt
    player.x += player.vx * dt          # frame-rate independent movement
    scene.refresh()
```

:::note[Gotchas]
call `tick()` exactly once per frame, at the bottom of the loop. If you ignore the return value you still get the FPS cap, but lose frame-rate independence - fine for a fixed-feel grid game, not for smooth motion. `tick_async()` only buys you anything if rendering can overlap other tasks; the render call still blocks.
:::

## picogame_input

`Buttons` maps physical buttons to a logical bitmask with pressed and released edges plus auto-repeat. It uses CircuitPython's background-scanned `keypad` event queue when available and falls back to `digitalio` polling. The `Timer` class provides frame-based windows for coyote time and jump buffering.

Logical buttons are exposed both as module constants and as attributes on the instance: `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `B`, `X`, `Y`, `L1`, `L2`, `R1`, `R2`, `START`, `SELECT`, plus `ALL`. The PicoPad maps the eight face buttons; absent buttons (no shoulders) simply never fire. They are bit flags, so you can OR them: `btn.A | btn.B`.

`Buttons`:

- `Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)` - build the reader. With `profile=None` the pin map is resolved highest-wins: an explicit `profile`, then `settings.toml` `PICOGAME_BUTTONS = "UP=GP2 A=GP12 ..."` (remap a custom Pico with no reflash), then a built-in profile by `board.board_id`, then the `PICOPAD` fallback. `pull` defaults to `Pull.UP` (or `PICOGAME_PULL` in `settings.toml`). `debounce_s` is the keypad scan window; `prefer_keypad=False` forces polling. `matrix=` adds a scanned key matrix and `usb=` adds USB HID sources — see below.
  - **More than one input source:** `Buttons` ORs several sources into one mask — on-board GPIO buttons, a scanned key matrix (`matrix=`, or the `PICOGAME_MATRIX_*` keys), and USB gamepads/keyboards on USB-host boards (`usb=`, auto-attached). A game reads them all with no code change. Full guide: [Input & controls](/helpers/input/).
- `poll()` - sample all buttons once and return the current pressed bitmask. Call once per frame, before any query. Drains the keypad event queue (catching sub-frame taps) or reads the pins directly, and updates held-frame counts for `repeat()`.
- `is_pressed(mask=ALL)` - `True` if any button in `mask` is currently down (level).
- `just_pressed(mask=ALL)` - `True` on the rising edge (the frame a button went down). On the keypad backend this comes from the event queue, so a tap shorter than a frame still registers.
- `just_released(mask=ALL)` - `True` on the falling edge (the frame a button came up).
- `has(mask=ALL)` - `True` if this board physically wires the given button(s). Use it to adapt controls/UI to boards without shoulders or START/SELECT.
- `repeat(button, delay=15, interval=4)` - auto-repeat for a SINGLE button: `True` the frame it's pressed, then every `interval` frames once held `delay` frames. Ideal for menu and grid movement.
- `clear()` - reset state and flush pending input. Call on scene or menu transitions so a held button doesn't leak across.

`Timer`:

- `Timer(frames)` - a counter that decays one frame at a time over `frames` frames.
- `feed(condition)` - recharge to full when `condition` is true, else count down one frame; returns whether still active. Use for coyote time (`feed(on_ground)`).
- `charge()` - force the timer to full.
- `is_active` (property) - `True` while the counter is above zero.
- `consume()` - `True` once if active, then clears it, so a buffered press fires exactly once (jump buffering).

```python
import picogame_input

btn = picogame_input.Buttons()          # auto profile by board
while True:
    btn.poll()
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)   # -1, 0 or +1
    if btn.just_pressed(btn.A):          # rising edge: fire once per tap
        jump()
    scene.refresh()
```

Coyote time and jump buffering, straight from the platformer example:

```python
coyote = picogame_input.Timer(5)        # still jump a few frames after a ledge
jbuf = picogame_input.Timer(6)          # honour a jump pressed just before landing
# each frame:
coyote.feed(on_ground)
jbuf.feed(btn.just_pressed(btn.A))
if coyote.is_active and jbuf.consume():
    jump()
```

:::note[Gotchas]
always `poll()` once per frame before querying, or `is_pressed` / `just_pressed` read stale state. `repeat()` takes a single button, not an OR-mask. The `digitalio` polling backend is undebounced (per-frame sampling already filters sub-frame bounce); for a noisy switch on a keypad-less build, debounce upstream. See [Input & controls](/helpers/input/) for USB pad/keyboard and matrix input, and [the settings.toml reference](/custom-board/) for the `PICOGAME_BUTTONS`/`PICOGAME_MATRIX_*`/USB remap keys.
:::
