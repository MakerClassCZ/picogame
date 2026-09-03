# Debugging first-aid — typical picogame failures and what to try FIRST

Every entry below was hit (and fixed) on real hardware. Ordered as a triage flowchart: match the
symptom, apply the first-listed fix, only then investigate deeper.

## Symptom → first move

| symptom | first move |
|---|---|
| `MemoryError` at boot / on a big allocation | You allocated a big buffer late or too big. Full-screen `Canvas(320,240)` = 150 KB → **never fits RP2040**; use half-res through a 2× Sprite, a Tilemap, or StripDraw. Allocate the BIGGEST buffer FIRST (right after imports), then the small ones — same total, no fragmentation death. `gc.collect()` before big allocs between scenes. |
| Edited a helper lib but the device ignores the change | **A stale `.mpy` EARLIER on sys.path shadows your `.py`.** The order is `['', '/', '.frozen', '/lib']` and in the SAME directory the `.py` wins (HW-measured) — so the classic trap is a bundle `.mpy` at the CIRCUITPY ROOT beating your edited `/lib/<name>.py`. Delete the stale copy or redeploy the regenerated bundle; never keep both copies on the board. |
| Drew into a bitmap/canvas buffer but the screen doesn't update | Direct buffer writes are invisible to dirty-rects. Call **`sprite.touch()`** after in-place edits (or `scene.invalidate()` for a full repaint). |
| Colors are wrong / everything looks byte-swapped | You passed a raw `0xRRGGBB` or hand-built RGB565. All colors must come from **`pg.rgb565(r, g, b)`** (display wire order). |
| Runs in the sim, `SyntaxError`/`NotImplementedError`/`AttributeError` on device | The sim is CPython; the device is MicroPython. Known gaps found the hard way: `*unpack` inside a tuple display, `x in array.array` (NotImplementedError), `math.hypot`, `random.shuffle`, `struct.iter_unpack`, and **`str.center`** (it needs an EXTRA_FEATURES build - use `picogame_ui.centred()`); other stdlib members likewise. **Gate with the firmware-matching `mpy-cross` if you have one** (catches syntax only; a missing *method* like str.center compiles fine and raises at runtime, so the real gate is a device run). Fastest way to answer "is X device-legal?" without hardware: grep the shipped games for prior art - if none of ~40 titles uses it, assume it is missing. |
| FPS fine at first, degrades over minutes | Allocation churn → GC pauses/fragmentation. Suspects: creating sprites/lists/dicts per frame (use a `Pool`; in `sprite.data` keep a number, or a dict/list pre-allocated per slot that you only MUTATE — a fresh tuple per change is churn, ~1 KB/frame at 30 entities), f-strings in the loop (`%` is 3.6× faster), text labels regrown per frame (`SceneLabel.reserve()` + set-on-change). |
| Sudden hitches every few seconds | GC. Confirm with `gc.mem_free()` deltas per frame; hunt the per-frame allocator (same suspects as above). |
| Bullets/enemies stop spawning | **Pool exhaustion** — `spawn()` returns `None` when full. Size the pool to the real max; free on despawn; the slot bit is `pool.alive`, NOT `visible` - a sprite you hid but never `free()`d still holds its slot, so audit `pool.count()` against what the game thinks is alive. |
| A menu/dialog slowly eats RAM each time it opens | You re-`scene.add()` the same UI every visit. Build once, toggle `visible`; one-shot panels call `.destroy()`. |
| Full-screen effect tanks FPS even when "nothing changes" | A full-frame `always_dirty=True` StripDraw kills dirty-rects for the whole scene. Use `always_dirty=False` + `.invalidate()` when it actually changes. |
| Game is logic-bound (profiled), not draw-bound | Move the per-frame loop into a **function**, hoist hot lookups to locals (measured −33 % on device), keep state in one object. If a ~100+-row Python loop remains hot, look for a batch C primitive (`fill_triangles`, `road_edges`+`Canvas.road`, `mode7`, `raycast`) — the Python↔C boundary costs ~9-14 µs per call, so C APIs must be fed BATCHES, never per-item calls. |
| `pg.project` / fixed-point 3D renders garbage or a black screen | Buffer format mismatch: cam/points must be packed to match the build — `array("f")` floats when `pg.FPU` is truthy, `array("i")` 16.16 ints otherwise. Mixing formats = every point lands "behind the near plane" = nothing draws. |
| 3D objects/walls flicker or vanish briefly during camera orbit | Painter's-sort tie: a big ground slab center-depth-sorted against the objects standing on it flips order at some angles. **Two-tier sort** — draw the ground (and anything provably behind: quads with `y1 ≤ 0`, the floor plane) FIRST unconditionally, then depth-sort only the objects. With the eye above the plane this is provably correct. |
| Raycaster (or any per-column Python `StripDraw` loop) is ~5 fps though "the same code" ran fast elsewhere | The `StripDraw` callback runs once **per render strip** — with `strip_h=8` a full-screen Python column loop executes 30×/frame. Fixes: a dedicated raycaster affords **big strips** (`picogame_game.setup(strip_h=40)` + `stride=3` + `rc.attach`); if big strip buffers don't fit beside your other RAM, draw into a **half-res Canvas shown through a 2× Sprite** (one loop/frame) + `sprite.touch()`. |
| A black band grows from the BOTTOM of the screen (async refresh / `pg.refresh_async` — fork-only firmware, not in the upstream build) | The core1 send races your in-place repaint: the bottom strips go out after your next frame's `canvas.clear()` but before its fills. Async needs a **double buffer** — paint the BACK canvas, flip two sprites' `visible` after render, let core1 send the FRONT. (Single-buffer async only survives when the frame slot has enough slack that `clear` starts after the ~20 ms send completes.) |
| Draw/fill phase is SLOWER on a Fruit Jam than on a PicoPad (the faster board!) | The Python heap lives in **PSRAM** on the Jam — retained-Canvas fills pay external-memory writes (~7× slower than SRAM; measured 8.7 vs 64 MB/s). Repainted-every-frame surfaces belong in **`pg.Triangles`** (fill the arrays, set `.count` — C rasterises per strip, full res, 0 retained RAM) or a StripDraw. Keep retained canvases small or static on fb boards. |
| Recurring horizontal "teeth"/shear parked in one screen region on a DVI board | The compose publishes bands out of sync with the scanout beam (worst with the dual-core split). Call **`pg.vblank()`** right before `scene.refresh()` — a compose started at vblank shows each sweep one whole frame (fits-in-two-sweeps condition; budget the ≤16.7 ms wait against your cap). |
| `pg.core1(True)` raises AttributeError | **`core1` is not in any CircuitPython release** — it is a fork-branch feature. `hasattr(pg, "core1")` before you reach for it. |
| `pg.core1(True)` returns False / dual-core gains never appear | core1 is already owned — **USB-host boards (Fruit Jam) run their USB service on core1 permanently**, and the engine refuses rather than freezing the board. The dual-core compose is for fb boards with GPIO input (no USB host). Also: any StripDraw in the scene forces the serial path (Python can't run on core1) — keep HUD text on a retained transparent Canvas repainted only on change. |
| Audio silent on device though the sim ran fine | The sim's LIVE WINDOW plays synthio through pygame.mixer (`sim/_simaudio.py`); only HEADLESS runs are silent. On device: SFX libs must be in `CIRCUITPY/lib`, volume keys in `settings.toml`; set `PICOGAME_DEBUG=1` to unmask silently-failing audio init. Tune SFX on the desktop with `tools/synth_preview.py` (renders to WAV) BEFORE deploying. |
| Sprite effect (flash/tint/dither/shadow) vanishes when another fires | On device the blit effects share ONE slot (last-set wins) — the sim models the same one-slot rule (device parity) - and remember a FALSY write clears only its own effect. Re-assert the persistent effect (e.g. dither) after a transient one (flash) ends. |
| Colors band/wobble on the real panel but look smooth in the sim | Panel truth: keep gradients 565-aligned (R/B step 8, G step 4, monotonic); dithered fills read as stipple blocks, not alpha — mute + sparsen, or use a ring. |
| `rgb444=True` shows a corrupted HUD band | The immediate-render path (reserved-band `HudBar`, `pg.render`) bypasses the 12-bit pack — known limitation; keep the HUD as in-scene StripDraw/labels when using rgb444, or stay RGB565. |
| Whole screen "flickers" when the game runs below its FPS cap | Not a bug in your code: a sub-cap frame rate beats against the panel's ~60 Hz self-scan (rolling shear). Fix the frame time until the cap holds — the flicker disappears with stable cadence. |

| A StripDraw panel/card never updates on device but is fine in the sim | `always_dirty=False` + a content change you never `invalidate()`d. The sim full-repaints, so it hides this: re-run with **`--strict-dirty`** and the layer freezes there too. |
| A StripDraw draws NOTHING (blank where the panel should be) | The callback almost certainly forgot `- vx` / `- vy`: items are stored in SCREEN coordinates, the view's local (0,0) is screen `(vx, vy)`, so draw at `self.x - vx, self.y - vy`. Drawing at raw screen coords puts the content outside the strip. |
| A scene layer inside a `setup(top=/bottom=/left=/right=)` band never appears | By design - the scene never draws in a reserved margin, and the layer is dropped in silence (the sim now warns). Paint the band with `HudBar` / `pg.render`, or move the layer into the play area. Note the band is NOT painted with `background=`; whatever paints it owns it. |
| Two runs of the same game differ (different maze/deal/waves) | `picogame_rand.Rand()` is time-seeded. Pass **`--seed N`** to repeat a run exactly - required before comparing screenshots or reproducing a balance complaint. |

| A saved best score never comes back in the sim | `sim/microcontroller.py` backs NVM with an in-memory bytearray that RESETS each run, so `picogame_save` round-trips only inside one run. Persistence itself can only be proven on hardware. |

## When you're stuck: the measurement ladder

1. **Sim first** — `sim/run.py game.py --frames 600` (crashes, obvious logic).
2. **Device parser** — firmware-matching `mpy-cross -o /dev/null game.py` (MicroPython syntax). **Only if you have one:** mpy-cross is built from a CircuitPython source tree, which the distributed repo does not carry, so from a plain clone this rung is unavailable - fall back to avoiding the known gaps by hand (the table above) plus a hardware run.
3. **Phase timing on device** — bracket suspect phases with `time.monotonic()` and print every 60
   frames (`build X | draw Y | refresh Z`); optimize the LARGEST number only. Refresh has a
   hardware floor (~24 ms full-screen SPI) — if refresh dominates, send less (dirty-rects, smaller
   viewport, `rgb444="auto"`), don't micro-optimize draw code that's already hidden under it.
4. **RAM curve** — print `gc.mem_free()` every few seconds; a downward slope = per-frame allocation.
5. Only after 1-4: read the engine reference for a cheaper building block.

**Verifying a game headless when a long route is fragile** (a first-person walker sliding along
walls, a platformer whose route depends on where you land, anything with a respawn): a scripted
`--keys` timeline is exact in TIME (frames are the game's own `clock.tick()` iterations), but the
game's STATE can still diverge - one missed jump and every later key lands in the wrong place.
Don't choreograph long routes: build an ENV-GATED debug start pose into the game
(`if os.getenv("DBG_POSE"): px, py, ang = parse(...)`) and give each `--keys` proof a 2-3 step
route from a pose next to the thing under test. Two probe builds independently invented this;
budget ~10 lines for it up front. For invisible mechanics (a meter, a graze), print one event
line per trigger under the same gate and assert on the serial log, not the screenshot.
