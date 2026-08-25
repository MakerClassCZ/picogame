---
title: Performance — keep your game fast
description: A practical checklist for a steady frame rate on picogame — the game loop in a function, dirty-rect-friendly motion, zero-RAM layers, and no per-frame allocation.
sidebar:
  label: Performance
  order: 7
---

picogame games run at a steady **30 FPS** when each frame fits in about **33 ms**. Most small games
get there without effort — the rendering runs in native C, and the engine repaints only what moved.
When a game does start to stutter, the fixes below are the ones that actually move the needle, in
rough order of payoff. Every number here is measured on an RP2040.

## 1. Put the game loop in a function

This is the single biggest lever. In MicroPython, reading a **module-level global is a dictionary
lookup** every time — and on the device that lookup is literally the hottest thing the interpreter
does. Names inside a **function are locals**, which are far cheaper. So wrap your loop in a function
and call it:

```python
def main():
    x = W // 2                 # locals — fast
    while True:
        buttons.poll()
        if buttons.is_pressed(pi.RIGHT):
            x += 2
        ball.x = x
        scene.refresh()
        clock.tick()

main()
```

Measured on one real game, moving the loop into a function cut its Python time from **~12 ms to
~8 ms per frame (−33 %)** — enough to turn a game that missed the cap into a solid 30 FPS.

## 2. Hoist lookups out of the hot loop

Same idea, one level down. If you touch `self.player.x` or `sprite.move` many times a frame, read it
into a local once:

```python
def main():
    px = ball.x                # cache the attribute
    poll = buttons.poll        # cache the bound method
    while True:
        poll()
        px += vx
        ball.x = px
        ...
```

Repeated `obj.attr` and `obj.method()` each cost a lookup; a local costs almost nothing.

## 3. Move few things

picogame is **retained, dirty-rect** rendering: it redraws only the rectangles that changed, and on
an SPI panel it only sends those pixels. A **static background with a small moving foreground** is the
sweet spot. A change that touches most of the screen costs a full frame no matter what — so keep the
moving-object count modest and let the background sit still. See [Drawing paths](/concepts/drawing-paths/).

## 4. Prefer zero-RAM layers

- **StripDraw** draws full-screen effects (a road, a gradient sky, a scanline HUD) with **no pixel
  buffer** — zero extra RAM and nothing to keep in sync.
- **Tilemap** is **one byte per cell**, so a big scrolling world is cheap.
- Reach for a retained **Canvas** only for a small panel that rarely changes — a full-screen Canvas is
  a large buffer you usually don't need. See [Fit it in RAM](/memory/).
- **Batch your StripDraw painting.** The callback runs once per render strip (dozens of times a
  frame), so a Python loop of small `fill_rect` calls inside it multiplies by strips-per-frame —
  measured to make a raycaster 8× slower. Precompute the shapes once per *change* into uint16 arrays
  and hand the whole batch to C with **one call per strip**: `view.vspans(...)` for vertical spans
  (wall columns, gradients, bars) or `view.fill_triangles(...)` for triangles.

## 5. Don't allocate every frame

Creating objects in the loop feeds the garbage collector, and a `gc.collect()` can cost tens of
milliseconds — a visible hitch. So:

- Spawn bullets, enemies and pickups from a fixed [`picogame_pool.Pool`](/helpers/data/), never
  `Sprite(...)` per frame.
- Reuse objects and buffers instead of rebuilding them; update a label's text, don't recreate it.
- Avoid building throwaway lists, tuples or strings inside the loop.

## 6. Ship `.mpy`, not big `.py`

Pre-compile your game with `mpy-cross` (or let the packs do it). Compiled bytecode starts faster and
avoids the heap churn of compiling a large source file on the device — which can itself `MemoryError`.
See [Run on hardware](/hardware/).

## Measure, don't guess

Some "obvious" tweaks do nothing — bumping the dirty-rectangle limit, for instance, was measured to
make no difference, because a well-built scene isn't rect-bound. Before optimising, find out where the
time actually goes:

- In the **[desktop simulator](/simulator/)**, `python3 sim/run.py yourgame.py --profile` prints per-
  function call counts and per-frame allocation.
- On hardware, watch the frame time with an FPS readout (`picogame_debug`) and change one thing at a
  time.

Optimise the loop that the profile says is hot — not the one you guessed.
