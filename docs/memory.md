# Managing RAM & avoiding heap fragmentation on CircuitPython

A general CircuitPython / MicroPython memory note: how to fit a long-running program in RAM —
know the budget, know what the big items cost, measure instead of guessing — and how to avoid
heap fragmentation. The technique at the end (a pre-allocated **arena**) is broadly reusable.

:::note[Applied the fix but nothing changed?]
A stale `.mpy` in the board's `/lib` **shadows** the matching `.py` at import, so a Python edit never runs — delete or rebuild it after any lib change (see [Run on hardware](hardware.md)).
:::

:::tip[MemoryError triage — start here]
A `MemoryError` mid-game almost always means **no contiguous block big enough**, not "out of RAM". Work down this list and stop at the first fix that sticks:

1. **Measure the largest _contiguous_ block, not total free** — `micropython.mem_info(1)` or the [`largest_block()` helper below](#measure-dont-guess). That's the number a big allocation has to fit into.
2. **Move HUD / text / panels off retained buffers** onto `StripDraw` (composite `Canvas.text` into a strip view) — see [Drawing paths](/concepts/drawing-paths/).
3. **Allocate big buffers once at boot; arena the churny ones** — [pre-allocated arena](#the-fix-for-churn-a-pre-allocated-arena).
4. **Pool per-frame spawns** instead of create/destroy churn — [`picogame_pool`](/helpers/building-scenes/).
5. **Freeze or stream large assets** rather than copying them onto the heap — [frozen vs file vs streaming](#where-assets-live-frozen-vs-file-in-ram-vs-streaming).
6. **`gc.collect()` at scene / level boundaries** to merge freed blocks.
7. **Still failing after a fix?** A stale `.mpy` may be **shadowing your `.py`** — see the note above.
:::

## The budget, and what eats it

The Python heap on a small board is the scarce resource, and **assets dominate it**. The
recurring costs (bytes):

| Item | Cost | Notes |
|---|---|---|
| Retained `Canvas` surface | `w * h * 2` | a 320×80 panel = 51 200 B — the classic budget killer |
| PAL8 bitmap (sprites, backgrounds) | `w * h` (+ palette) | RGB565 bitmap costs double |
| Strip buffers (from `setup()`) | `2 × width × strip_h × 2` | e.g. 320×8 ≈ 10 KB for the pair |
| Sprite pool | ~sprite object × capacity | bitmaps are shared; the pool caps the worst case |
| Text label bitmap | text area × 1–2 B/px | or 0 retained via `Canvas.text` into a StripDraw view |

Totals differ per board and firmware build — don't budget from a headline number; measure
your own build (next section). As a rule of thumb, plan your biggest surfaces first: whatever
the free heap is, one full-screen retained surface (`320*240*2` = 150 KB) will not fit on an
RP2040-class board, and a couple of large panels can eat half of it.

## Where assets live: frozen vs file-in-RAM vs streaming

A bitmap's pixels have to be *somewhere*, and on a small heap the choice decides whether the
game fits. The trap first: **CIRCUITPY is a FAT filesystem in flash, but it is NOT
memory-mapped**, so importing a big `.mpy` or reading a file **copies it to the heap**. Only
**frozen** data is read in place from flash, so "it's on flash" ≠ "it's free". Three tiers:

| Approach | Heap cost | Swap art w/o reflash? | Best for |
|---|---|---|---|
| **Frozen** (`FROZEN_MPY_DIRS`) | ~0 (read in place from flash) | no | the bulk of resident art on a tight build |
| **File → RAM** (`readinto` once) | whole sheet `w*h*frames` | yes | sheets that fit + quick art iteration |
| **Streaming** (`picogame_stream.StreamSheet`) | ~one frame | yes | a few BIG sprites/backgrounds that won't fit |

- **Frozen:** the art is a module with a `bytes` literal (`DATA = b'...'`) frozen into the
  firmware; `pg.Bitmap(DATA, ...)` references it in place. Changing the art means a reflash.
- **File → RAM:** ship a `.bin` on CIRCUITPY, `f.readinto(blob)` into ONE pre-sized
  `bytearray` at load (not `read()` — that fragments), slice the `memoryview` into Bitmaps.
- **Streaming:** `StreamSheet` keeps **one frame** in RAM; `use(i)` seeks + `readinto`s it on
  demand. A flash read per frame change — fine for a few big sprites at animation rates,
  wasteful for hundreds of tiny ones. The `.bin` must be frame-major (`tools/pack_sheet.py`).

Rule: **freeze what you always need, stream the few big things that don't fit, keep small
often-used sheets in RAM.** Mix all three in one game.

## Measure, don't guess

- `gc.mem_free()` — total free heap. Take readings after `gc.collect()`, at fixed points
  (after imports, after `setup()`, in the game loop) so runs are comparable.
- **Largest contiguous block** — what a big allocation actually needs; there's no built-in,
  binary-search it:

```python
import gc
def largest_block():
    gc.collect()
    lo, hi = 0, gc.mem_free()
    while hi - lo > 256:
        m = (lo + hi) // 2
        try:
            b = bytearray(m); del b; lo = m
        except MemoryError:
            hi = m
        gc.collect()
    return lo
```

- `import micropython; micropython.mem_info(1)` dumps the full heap map (what's live and
  where) on firmware built with the diagnostics enabled — the tool for *why* it's fragmented.

## Common optimizations (in the order to try them)

1. **Don't allocate the surface at all.** Text and HUD/panel content can composite straight
   into the render strip (`Canvas.text` into a `StripDraw` view; the `picogame_ui` widgets
   already work this way) — no retained pixel buffer, nothing on the heap to fragment. Which
   drawing path costs what, and when a retained `Canvas` *is* justified, is covered by
   [Drawing paths](/concepts/drawing-paths/).
2. **Store a full-screen background as a tilemap, not a bitmap.** A 320×240 PAL8 background is
   ~75 KB (RGB565 doubles it) — often too much on an RP2040. Cut the image into 8×8 tiles, keep
   only the *unique* tiles (a small tileset) plus a grid of indices, and draw it with a
   [`Tilemap`](engine.md) layer. Backgrounds repeat a lot, so the tileset + index grid is a
   fraction of the full bitmap. `png2picogame.py --dedup` merges identical (and rotated/mirrored)
   tiles for you; this is how the Fruit Jam MoonMiner port fits its full-screen scenes on an RP2040.
3. **Allocate big/long-lived buffers first, at boot**, and keep them; don't free and
   re-create them per level/screen.
4. **Pre-size on-demand buffers to their WIDEST content at boot.** A text label created
   short and later set to a longer string re-allocates a bigger buffer *mid-run*; on a
   fragmented heap that's a `MemoryError`. (Create HUD labels at their widest string;
   `SceneLabel.reserve(chars)` pre-sizes a banner shown only at game-over.)
5. **Object pools** for many small same-size objects (sprites, requests): reuse instead of
   alloc/free churn ([`picogame_pool`](/helpers/building-scenes/)).
6. **`recv_into` / `readinto`** (and other `*_into` APIs) read into an existing buffer
   instead of allocating a new bytes object each call.
7. **`gc.collect()` at natural boundaries** (end of a request/level) to merge adjacent free
   blocks; necessary but not sufficient (it can't move live objects). `gc.threshold(n)`
   triggers GC earlier and keeps the heap tidier.
8. **Import everything up front, not lazily mid-run** — CircuitPython relocates import-time
   "long-lived" objects to the end of the heap on the first GC, keeping the low heap
   contiguous for working allocations.

## Fragmentation: total free is not the largest block

MicroPython/CircuitPython use a **non-moving** mark-and-sweep GC: it frees unreachable
objects but **never moves live ones** (objects are referenced by raw pointers, and the
C stack is scanned conservatively, so relocating them safely isn't possible). Adjacent
free blocks are merged on `gc.collect()`, but free space split by **live** objects
stays split.

Consequence: after a program has allocated and freed many differently-sized buffers,
the heap fragments. You can have **lots of total free RAM but no single contiguous
block** big enough for the next large allocation:

```text
gc.mem_free() -> 90000      # 90 KB free...
bytearray(51200)            # ...but this raises MemoryError (no 51 KB contiguous run)
```

`gc.mem_free()` reports total free; what a big allocation needs is the **largest contiguous
free block**, which can be far smaller and which shrinks as a session fragments.

### When it bites

Any pattern that **repeatedly allocates and frees a large buffer** during one run:

- **Networking / web:** reading an HTTP response, a JSON/MQTT payload, a TLS record, an
  image download, each request grabbing (and freeing) a fresh kilobyte-scale buffer.
- **File / stream processing:** reading a file in chunks, decompressing, parsing.
- **Audio:** per-clip sample buffers.
- **Graphics:** full-/large-screen drawing surfaces (e.g. a `displayio`/`picogame`
  Canvas) created per screen/level.

A single big buffer allocated **once at boot** and kept forever is fine (it gets a
contiguous block while the heap is fresh). The problem is the **churn**.

## The fix for churn: a pre-allocated arena

Grab **one** big buffer **once, early** (when the heap is fresh and contiguous), then
hand out slices of it for the large transient buffers. Those buffers then never
alloc/free at runtime, so they can't fragment anything. Reuse the same arena bytes for
work that doesn't overlap in time.

[`lib/picogame_arena.py`](/helpers/data/) is a tiny, general implementation (it's in the picogame lib but
the `Arena` class is not game-specific):

```python
import picogame_arena
AR = picogame_arena.Arena(4096)        # 4096 bytes, grabbed up front (size = your max)

# --- networking example: reuse ONE response buffer instead of churning ---
buf = AR.alloc(4096)                   # a memoryview slice, no per-request alloc
while True:
    AR.reset()                         # reuse the same bytes each request
    n = sock.recv_into(buf)            # read straight into the arena slice
    process(buf[:n])                   # parse without allocating another big buffer
```

```python
# --- graphics example (picogame): back big Canvases with arena memory ---
AR = picogame_arena.Arena(320 * 80)    # pixels (x2 bytes); the biggest surface you need
AR.reset(); road = AR.canvas(320, 80)          # one screen's big surface
# later, a different screen (not alive at the same time) reuses the same arena:
AR.reset(); shapes = AR.canvas(320, 44); btn = AR.canvas(160, 48)
```

API: `Arena(pixels)` (allocates `pixels*2` bytes), `alloc(nbytes) -> memoryview`,
`canvas(w, h, transparent=None) -> Canvas` (needs the firmware `Canvas(..., buffer=)`
arg), `reset()` (rewind the cursor, call at the start of each non-overlapping use),
`free()`.

Key point: the arena makes the big allocation happen **once at startup** and the
**slices never touch the heap**, so a session can run indefinitely without the
"90 KB free but can't allocate 51 KB" failure.

## Why not just defragment?

A true compacting/defragmenting GC isn't feasible as an add-on: MicroPython objects
reference each other by **raw pointers** (in Python, in C modules, in bytecode), and
the GC scans the C stack **conservatively**, so it cannot safely move an object and
rewrite every reference to it. That would require a different (precise / handle-based)
object model in the VM core. The arena pattern is the practical answer: don't let the
big buffers churn in the first place.

See also the engine's `Canvas(..., buffer=)` argument (back a drawing surface with [arena
memory](/helpers/data/)) and the helper [`picogame_pool`](/helpers/building-scenes/) (object pools). Build and measure in the desktop
simulator first; optimise only once you've measured where the RAM actually goes.
