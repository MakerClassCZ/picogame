# Debugging first-aid — typical picogame failures and what to try FIRST

Every entry below was hit (and fixed) on real hardware. Ordered as a triage flowchart: match the
symptom, apply the first-listed fix, only then investigate deeper.

## Symptom → first move

| symptom | first move |
|---|---|
| `MemoryError` at boot / on a big allocation | You allocated a big buffer late or too big. Full-screen `Canvas(320,240)` = 150 KB → **never fits RP2040**; use half-res through a 2× Sprite, a Tilemap, or StripDraw. Allocate the BIGGEST buffer FIRST (right after imports), then the small ones — same total, no fragmentation death. `gc.collect()` before big allocs between scenes. |
| Edited a helper lib but the device ignores the change | **Stale `.mpy` shadows your `.py`** in `CIRCUITPY/lib` — a stale compiled copy (`<name>.mpy`) wins over the edited `<name>.py` at import. Delete the old `.mpy` (or redeploy the whole regenerated bundle). |
| Drew into a bitmap/canvas buffer but the screen doesn't update | Direct buffer writes are invisible to dirty-rects. Call **`sprite.touch()`** after in-place edits (or `scene.invalidate()` for a full repaint). |
| Colors are wrong / everything looks byte-swapped | You passed a raw `0xRRGGBB` or hand-built RGB565. All colors must come from **`pg.rgb565(r, g, b)`** (display wire order). |
| Runs in the sim, `SyntaxError`/`NotImplementedError`/`AttributeError` on device | The sim is CPython; the device is MicroPython. Known gaps: `*unpack` inside a tuple display, `x in array.array` (NotImplementedError), `math.hypot`/`random.shuffle`/other stdlib members missing. **Gate with the firmware-matching `mpy-cross`** (catches syntax; runtime gaps need a device run). |
| FPS fine at first, degrades over minutes | Allocation churn → GC pauses/fragmentation. Suspects: creating sprites/lists/dicts per frame (use a `Pool` + scalars/tuples in `sprite.data`), f-strings in the loop (`%` is 3.6× faster), text labels regrown per frame (`SceneLabel.reserve()` + set-on-change). |
| Sudden hitches every few seconds | GC. Confirm with `gc.mem_free()` deltas per frame; hunt the per-frame allocator (same suspects as above). |
| Bullets/enemies stop spawning | **Pool exhaustion** — `spawn()` returns `None` when full. Size the pool to the real max; free on despawn; check you aren't leaking `visible=True` corpses. |
| A menu/dialog slowly eats RAM each time it opens | You re-`scene.add()` the same UI every visit. Build once, toggle `visible`; one-shot panels call `.destroy()`. |
| Full-screen effect tanks FPS even when "nothing changes" | A full-frame `always_dirty=True` StripDraw kills dirty-rects for the whole scene. Use `always_dirty=False` + `.invalidate()` when it actually changes. |
| Game is logic-bound (profiled), not draw-bound | Move the per-frame loop into a **function**, hoist hot lookups to locals (measured −33 % on device), keep state in one object. If a ~100+-row Python loop remains hot, look for a batch C primitive (`fill_triangles`, `road_edges`+`Canvas.road`, `mode7`, `raycast`) — the Python↔C boundary costs ~9-14 µs per call, so C APIs must be fed BATCHES, never per-item calls. |
| `pg.project` / fixed-point 3D renders garbage or a black screen | Buffer format mismatch: cam/points must be packed to match the build — `array("f")` floats when `pg.FPU` is truthy, `array("i")` 16.16 ints otherwise. Mixing formats = every point lands "behind the near plane" = nothing draws. |
| Audio silent on device though the sim ran fine | The sim has no audio backend at all — silence there is normal. On device: SFX libs must be in `CIRCUITPY/lib`, volume keys in `settings.toml`; set `PICOGAME_DEBUG=1` to unmask silently-failing audio init. Tune SFX on the desktop with `tools/synth_preview.py` (renders to WAV) BEFORE deploying. |
| Sprite effect (flash/tint/dither/shadow) vanishes when another fires | On device the blit effects share ONE slot (last-set wins) — the sim treats them as independent. Re-assert the persistent effect (e.g. dither) after a transient one (flash) ends. |
| Colors band/wobble on the real panel but look smooth in the sim | Panel truth: keep gradients 565-aligned (R/B step 8, G step 4, monotonic); dithered fills read as stipple blocks, not alpha — mute + sparsen, or use a ring. |
| `rgb444=True` shows a corrupted HUD band | The immediate-render path (reserved-band `HudBar`, `pg.render`) bypasses the 12-bit pack — known limitation; keep the HUD as in-scene StripDraw/labels when using rgb444, or stay RGB565. |
| Whole screen "flickers" when the game runs below its FPS cap | Not a bug in your code: a sub-cap frame rate beats against the panel's ~60 Hz self-scan (rolling shear). Fix the frame time until the cap holds — the flicker disappears with stable cadence. |

## When you're stuck: the measurement ladder

1. **Sim first** — `sim/run.py game.py --frames 600` (crashes, obvious logic).
2. **Device parser** — firmware-matching `mpy-cross -o /dev/null game.py` (MicroPython syntax).
3. **Phase timing on device** — bracket suspect phases with `time.monotonic()` and print every 60
   frames (`build X | draw Y | refresh Z`); optimize the LARGEST number only. Refresh has a
   hardware floor (~24 ms full-screen SPI) — if refresh dominates, send less (dirty-rects, smaller
   viewport, `rgb444="auto"`), don't micro-optimize draw code that's already hidden under it.
4. **RAM curve** — print `gc.mem_free()` every few seconds; a downward slope = per-frame allocation.
5. Only after 1-4: read the engine reference for a cheaper building block.
