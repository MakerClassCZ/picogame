# picogame_arena: a pre-allocated buffer arena to dodge heap fragmentation.
#
# MicroPython's GC is non-moving (it never compacts), so a long-running program that
# repeatedly allocates and frees BIG buffers (e.g. full-width Canvas surfaces) ends up
# with a fragmented heap: plenty of total free RAM, but no single contiguous block big
# enough for the next large alloc -> MemoryError even though `gc.mem_free()` looks fine.
#
# The fix is to grab ONE big buffer ONCE, early (when the heap is fresh and contiguous),
# and hand out slices of it for large surfaces. Those surfaces then never alloc/free at
# runtime, so they can't fragment anything. Scenes that don't run at the same time can
# reuse the same arena bytes (call reset() at the start of each).
#
#   import picogame_arena
#   AR = picogame_arena.Arena(320 * 88)            # capacity in PIXELS (x2 bytes), grab early
#   ...
#   AR.reset(); road = AR.canvas(320, 88)          # racer: one big surface
#   ...
#   AR.reset(); shapes = AR.canvas(320, 44); btn = AR.canvas(160, 48)   # intro: two from one arena
#
# NESTED lifetimes (mark/release) - the Doom "zone tag" idea (Z_FreeTags) as a LIFO stack:
# grab whole-RUN buffers first, then mark() on entering a MODE (battle/boss/menu) and release(m)
# on leaving it - freeing everything alloc'd since the mark while KEEPING everything before it.
# reset() is just release(0). Unlike reset()'s all-or-nothing, this lets persistent run-level
# buffers survive while a transient mode reuses the space above them:
#
#   AR = picogame_arena.Arena(320 * 120)
#   hud = AR.canvas(320, 24)          # RUN-lifetime: lives the whole game
#   m = AR.mark()                     # <- remember the fill point
#   arena_bg = AR.canvas(320, 96)     #    MODE-lifetime: only during the battle
#   ...battle...
#   AR.release(m)                     # frees arena_bg, hud survives; space above m is free again
#
# Marks are LIFO (release in reverse order of mark) - enough for nested game modes, and it only
# reclaims arena BUFFERS; Python object graphs (Sprites/Scenes) are still GC'd by dropping refs
# + gc.collect() (see the Wyrmfall world_free/world_build pattern - the object-graph half).
#
# Needs the firmware Canvas `buffer=` argument (the sim ignores it and allocates its own).
# See HARDWARE.md for why this matters on the RP2040 (~138 KB heap).

import picogame as pg


class Arena:
    def __init__(self, pixels):
        self.buf = bytearray(pixels * 2)           # one allocation, kept for the whole run
        self.mv = memoryview(self.buf)
        self.used = 0

    def reset(self):
        """Free all slices handed out so far (call at the start of each scene that
        reuses the arena). Any Canvas from a previous reset() must no longer be drawn."""
        self.used = 0

    def mark(self):
        """Save the current fill point for a later release() - the start of a nested lifetime
        (a MODE/SCENE). Returns an opaque handle (the offset). Marks are LIFO: release them in
        reverse order. See the module header for the Doom-zone nesting pattern."""
        return self.used

    def release(self, m):
        """Rewind to a saved mark(): frees every slice handed out since that mark, keeping
        everything before it. Any Canvas/slice alloc'd after `m` must no longer be drawn/used.
        `reset()` == `release(0)`."""
        self.used = m

    def alloc(self, nbytes, align=1):
        """A `memoryview` slice of `nbytes` from the arena (generic, not just Canvas):
        reuse it as a network/file read buffer, a parse scratch buffer, an audio block,
        a display strip, etc. - anything where a big buffer would otherwise churn the heap.

        `align` (bytes) rounds the slice's START up to a multiple of `align` - use it when
        YOU need it: `align=2` for RGB565 / 16-bit data (so an odd-sized PAL8 alloc before it
        can't leave the next slice on an odd offset), `align=4` for word access. Default 1 =
        packed (fine for PAL8 / byte data, no waste). The arena buffer is GC-aligned, so an
        aligned offset gives an aligned slice. The slice is valid until the next reset()."""
        if align > 1:
            self.used = (self.used + align - 1) // align * align
        if self.used + nbytes > len(self.buf):
            raise MemoryError("picogame_arena: arena full (need %d more bytes)" % nbytes)
        sl = self.mv[self.used:self.used + nbytes]
        self.used += nbytes
        return sl

    def canvas(self, w, h, transparent=None):
        """A Canvas backed by the next slice of the arena (no heap alloc for the buffer);
        16-bit (RGB565) aligned automatically."""
        return pg.Canvas(w, h, transparent=transparent, buffer=self.alloc(w * h * 2, align=2))

    def free(self):
        return len(self.buf) - self.used
