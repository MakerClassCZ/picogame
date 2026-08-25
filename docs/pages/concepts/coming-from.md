---
title: Coming from another engine
description: Map what you already know from Pygame, displayio, PICO-8 or Arcade onto picogame — and see what the engine does and doesn't do.
sidebar:
  order: 2
---

Use the table below to map concepts from Pygame, `displayio`, PICO-8, or Arcade onto picogame.
If you know `displayio`, continue with the [term-by-term bridge](#coming-from-displayio).
See [How picogame works](/concepts/how-it-works/) for the underlying model and the
[API reference](/reference/) for signatures.

## Concept map

| You want… | Pygame | displayio (CircuitPython) | PICO-8 | **picogame** |
|---|---|---|---|---|
| An image | `Surface` | `Bitmap` + `Palette` | sprite sheet | `pg.Bitmap(data, w, h, …)` (PAL8 or RGB565, multi-frame atlas) |
| A movable object | `sprite.Sprite` | `TileGrid` | `spr()` | `pg.Sprite(bitmap, x, y)` (anchor, flip, frame, **scale**, **angle**) |
| The scene/world | `Group`/manual | `Group` | the screen | `pg.Scene(...)` — retained, dirty-rect |
| Draw it | `screen.blit()` | add to `Group` | `spr()`/`map()` | `scene.add(obj)` once; then `scene.refresh()` per frame |
| A tiled level | your own | `TileGrid`+`Bitmap` | `map()` | `pg.Tilemap(tiles, cols, rows)` — `tile(x, y, value)` |
| A scrolling camera | manual offset | `Group.x/y` | `camera()` | `scene.set_view(ox, oy)` (world bigger than screen) |
| The main loop | `while`, `flip()` | `while`, `refresh()` | `_update()`/`_draw()` | `while: buttons.poll(); …; scene.refresh(); clock.tick()` |
| Input | `pygame.event` | `keypad`/pins | `btn()` | `picogame_input.Buttons` → `is_pressed()` / `just_pressed()` (`poll()` for the bitmask) |
| Sound | `mixer` | `audiocore`/`audiopwmio` | `sfx()`/`music()` | `picogame_audio` (`tone()`, `.wav`) |
| Collision | `Rect.colliderect` | manual | manual | `pg.collide(...)` / `a.overlaps(b)` / `a.near(b, r)` (zero-alloc, off sprites) |
| Text | `font.render` | `label` | `print()` | `picogame_ui` HUD / `picogame_font` → Bitmap |
| Many bullets/enemies | sprite groups | manual | manual | `picogame_pool.Pool` (fixed pool, no per-frame alloc) |
| Transforms | `transform.rotate` | limited | `spr` flips | `sprite.scale` (float) + `sprite.angle` (deg), nearest-neighbour |

## Coming from displayio

If you've used CircuitPython's `displayio`, you already know most of picogame; it's the same world
with games-shaped names and the redraw bookkeeping done for you:

| In `displayio` you used… | In picogame it's… |
|---|---|
| `displayio.TileGrid` — a positioned bitmap | a **[Sprite](/concepts/glossary/)** — but it also flips, scales, rotates and animates |
| `displayio.Group` — a stack of things | a **[Scene](/concepts/glossary/)** — holds [layers](/concepts/glossary/), painted in order |
| `while True: display.refresh()` | the **[game loop](/concepts/glossary/)**: read input → update → `scene.refresh()` → wait |
| `bitmap` + `palette` + RGB565 | the same — but build colours with `pg.rgb565(r, g, b)` ([wire-order](/concepts/glossary/)), never a raw `0xRRGGBB` |
| managing redraws by hand | nothing — picogame is **[retained mode](/concepts/glossary/)**: you change objects, it repaints only what moved |

The main shift is that you describe the scene instead of driving each display update yourself.

## The main difference: retained mode and dirty regions

Many 2D engines are **immediate mode**: every frame you clear the screen and redraw everything.
picogame is **retained mode**: you build a `Scene` of objects once, then each frame you *mutate*
them and call `scene.refresh()`. The engine figures out which rectangles changed and **redraws only
those**. On SPI displays, only those pixels are sent to the panel. Framebuffer targets such as
Fruit Jam repaint the same regions in scanout memory. In both cases, the scene tracks the changes.

One consequence: moving or swapping a sprite is tracked automatically, but an **in-place** pixel
edit needs a `sprite.touch()` to register (see [effects](/helpers/effects/)).

## What picogame can do

- **Arbitrary-size sprites** with anchors, flips, multi-frame animation atlases.
- **Runtime scale and rotation** per sprite (nearest-neighbour affine, no FPU needed), about an anchor.
- **Tilemaps** you read and write at runtime (use them as game boards, not just backgrounds).
- A **moving camera** (`set_view`) over a world larger than the screen, with fixed (HUD) layers.
- **Particles**, a drawing **Canvas** (retained shapes), and **StripDraw** (full-frame effects without a retained pixel buffer).
- **Audio** (PWM tones + `.wav`), **NVM save** for high scores/settings, a bundled **font** + HUD helpers.
- A **desktop simulator**: the same game code runs on your PC (headless screenshots or a live window), so you build and debug without hardware.

## Design within the limits

- **RAM depends on the board and firmware.** Large pixel buffers and sprite sheets dominate the
  budget. Tile large worlds, stream large sheets, and use StripDraw when you do not need retained
  pixels. See [Fit it in RAM](/memory/) for measured budgets and alternatives.
- **One display, no GPU.** No shaders, no alpha blending. Transparency is a single transparent
  index/colour; for a darken effect there's a `shadow` mode. Transforms are nearest-neighbour (crisp at
  integer scales, shimmery at fractional).
- **Paletted art.** PAL8 is 1 byte/pixel (cheap); RGB565 is 2 bytes/pixel. Build colours with
  `rgb565(r, g, b)`, never raw `0xRRGGBB`.
- **Few buttons.** D-pad + A/B (and sometimes X/Y). Design controls accordingly.
- **Ship `.mpy`, not big `.py`.** Compiling a large source file on-device can `MemoryError`; pre-compile
  to `.mpy`. See [Run on hardware](/hardware/).

## Start here

1. Read [How picogame works](/concepts/how-it-works/) for the loop and dirty-region model.
2. Copy the [first game](/start/first-game/) and run it in your browser or the [desktop simulator](/simulator/) to feel the API.
3. Keep the [API cheat sheet](/reference/) and [feature guide](/features/) open while you build.
4. Adapt patterns from the [examples](/examples/) to your genre.
