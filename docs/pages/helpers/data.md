---
title: "Saving & memory"
description: "Persist scores and settings to NVM, dodge heap fragmentation with a pre-allocated arena, and stream big sprite sheets from flash."
---

These helpers persist small values, reserve reusable memory, and stream animation frames from flash. See [/reference/](/reference/) for the signatures and [/memory/](/memory/) for the memory model behind the last two modules.

## picogame_save

This structured key-value store uses `microcontroller.nvm`, a reserved flash region writable from `code.py`. Use it for a high score, unlocked level, or settings that must survive power loss. The region is 4 KiB on the supported RP2040 builds; the class checks the actual available length when it is constructed.

NVM is a single region shared by every program on the device, so each game passes its own `key`. The key is hashed into the header and checked on load - if another game or stale data wrote the slot, `load()` returns your defaults instead of misreading foreign bytes.

You describe your data as a schema: an ordered dict of `name -> (struct format char, default)`. Common chars: `"B"` 0-255, `"H"` 0-65535, `"I"` 0 to 2^32-1; lowercase `b`/`h`/`i` are signed.

- `Save(key, schema, *, offset=0)` - create a store. `key` is your game's name (str or bytes). `offset` is keyword-only; bump it only if two coexisting games must use different NVM regions. Raises `RuntimeError` if NVM is unavailable, or `ValueError` if the schema does not fit NVM.
- `load()` - return a dict of the stored values, or a fresh copy of the defaults if the slot is blank, corrupt, or written by a different game (key mismatch). Never raises on bad data.
- `save(values)` - persist a dict. Missing keys fall back to their schema default. Writes a checksum so a later `load()` can detect corruption.
- `reset()` - write the defaults back under this game's key.
- `defaults()` - a fresh dict of just the default values, no NVM read.

```python
import picogame_save

# persist the best lap time (seconds) across reboots
store = picogame_save.Save("ghostrace", {"best_t": ("H", 0)})
best_t = store.load()["best_t"]              # 0 = no record yet

# ...later, on a new best run:
if best_t == 0 or secs < best_t:
    best_t = secs
    store.save({"best_t": best_t})           # survives power-off
```

:::note[Gotchas]
every `save()` erases and rewrites a flash sector, so flash wears out if you call it every frame - save only on meaningful events (game over, new high score, settings change). Keep the schema small; the whole blob (header + fields + checksum) must fit in NVM.
:::

## picogame_arena

A buffer arena reserves one contiguous block early and hands out slices of it later. Use it when several scenes or modes need large `Canvas` buffers at different times. MicroPython's garbage collector does not compact the heap, so repeatedly creating and discarding large buffers can leave enough free memory in total but no sufficiently large contiguous block.

- `Arena(pixels)` - allocate the arena. Size is in pixels; it reserves `pixels * 2` bytes (RGB565). Do this early, before the heap fragments.
- `canvas(w, h, transparent=None)` - a `pg.Canvas` backed by the next slice (no per-canvas heap alloc); 16-bit aligned automatically. Returns the `Canvas`.
- `alloc(nbytes, align=1)` - a generic `memoryview` slice of `nbytes`: reuse it as a file/network read buffer, parse scratch, audio block, etc. `align` rounds the slice start up (use `align=2` for 16-bit data, `align=4` for word access). Raises `MemoryError` if the arena is full. Valid until the next `reset()`.
- `mark()` - return the current allocation offset. Keep it when entering a temporary mode or scene.
- `release(mark)` - rewind the arena to a previous mark and make every later slice available again. Marks should be released in reverse order. Objects backed by released slices must no longer be used.
- `reset()` - free all slices handed out so far. Call at the start of each scene that reuses the arena. Any `Canvas` from before the reset must no longer be drawn.
- `free()` - bytes still available in the arena.

```python
import picogame_arena

# one arena for the big canvases, grabbed once while the heap is contiguous;
# scenes that never run at the same time share the bytes (reset each).
ARENA = picogame_arena.Arena(320 * 80)       # 320x80 px = 51 200 bytes

def big_canvas(w, h, transparent=None, first=False):
    if first:
        ARENA.reset()                        # reuse the arena for this scene
    return ARENA.canvas(w, h, transparent=transparent)
```

:::note[Gotchas]
this needs a firmware `Canvas` with the `buffer=` argument. The simulator currently allocates its own canvas storage, so the anti-fragmentation benefit applies on [hardware](/hardware/). After `reset()` or `release()`, do not use objects backed by the reclaimed slices; new allocations may overwrite their data.
:::

## picogame_stream

`StreamSheet` keeps one PAL8 animation frame in RAM and reads the requested frame from a file on flash. A 64x100 sheet with 11 frames therefore needs a 6,400-byte pixel buffer instead of 70,400 bytes for all frame pixels. The file must be frame-major, with each frame's `w*h` bytes contiguous. Create it with `tools/pack_sheet.py`.

- `StreamSheet(pg, path, w, h, frames, palette, transparent=None)` - open `path`, allocate one frame buffer, build a `pg.Bitmap` (PAL8) over it, and load frame 0. `palette` is the color table for the PAL8 data.
- `.bitmap` - the single `pg.Bitmap` whose pixels get overwritten in place. Build your `pg.Sprite` from this.
- `use(i)` - load frame `i` (wrapped modulo `frames`) into the shared buffer and return the bitmap. Cached: re-reads from flash only when `i` actually changes.
- `close()` - close the underlying file.

```python
import picogame_stream

sheet = picogame_stream.StreamSheet(pg, "jill.bin", 64, 100, 11, PAL, transparent=0)
player = pg.Sprite(sheet.bitmap, x, y)
# ...each frame the animation advances:
sheet.use(frame_index)        # stream that frame into the shared buffer
player.touch()                # tell the scene to repaint it (pixels changed in place)
```

:::note[Gotchas]
always call `sprite.touch()` after `use()`. The method overwrites bitmap pixels in place, which does not change a property tracked by the dirty-region renderer. Without `touch()`, a stationary sprite may keep showing its previous frame. The simulator repaints the full scene, so this mistake can appear only on hardware. See [/scene-format/](/scene-format/) for dirty-region repainting.
:::
