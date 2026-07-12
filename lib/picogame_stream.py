# picogame_stream: play a big sprite sheet straight from a file on flash, holding only
# ONE frame in RAM instead of the whole sheet.
#
# CircuitPython keeps the CIRCUITPY filesystem in flash, but a FAT file is NOT mapped into
# the CPU address space (only frozen/XIP data is), so importing the sheet as a .mpy copies
# all of it to the heap. StreamSheet instead opens the file once and, each time you ask for
# a frame, seeks to it and `readinto()`s a single-frame buffer (no allocation per frame).
# The sheet must be FRAME-MAJOR (each frame's w*h bytes contiguous) - use tools/pack_sheet.py.
#
#   import picogame_stream
#   sheet = picogame_stream.StreamSheet(pg, "jill.bin", 64, 100, 11, PAL, transparent=0)
#   spr = pg.Sprite(sheet.bitmap, x, y)
#   ...
#   sheet.use(frame_index)        # overwrite the buffer with that frame
#   spr.touch()                   # tell the scene to repaint it (the pixels changed in place)
#
# IMPORTANT: call `spr.touch()` after use(). use() overwrites ONE bitmap buffer in place; the
# scene's dirty-rect engine repaints a sprite only when a TRACKED property changes (position,
# frame idx, scale, angle, bitmap object) - an in-place pixel change is invisible to it, so
# without touch() a frame change with no movement (a jump apex, walking into a wall) leaves a
# stale/torn sprite. `Sprite.touch()` needs firmware with the touch() method (picogame engine
# 2026-06+). On the simulator touch() is a no-op (the sim repaints fully).


class StreamSheet:
    def __init__(self, pg, path, w, h, frames, palette, transparent=None):
        if frames <= 0:
            raise ValueError("frames must be > 0")
        self.f = open(path, "rb")
        try:
            self.frame_bytes = w * h
            self.buf = bytearray(self.frame_bytes)     # the only RAM the sheet costs (one frame)
            self.frames = frames
            self.bitmap = pg.Bitmap(self.buf, w, h, format=pg.PAL8, palette=palette,
                                    frames=1, stride=w, transparent=transparent)
            self._cur = -1
            self.use(0)
        except Exception:
            self.f.close()                             # don't leak the file if setup fails
            raise

    def use(self, i):
        """Load frame `i` into the shared buffer (cached: re-reads only when it changes) and
        return the bitmap. After this, call `sprite.touch()` so the scene repaints the sprite
        (the bitmap's pixels changed in place; that isn't otherwise detected as dirty).
        A short read (truncated file / bad frame index past EOF) raises instead of caching a
        half-old/half-new frame as if it succeeded."""
        i %= self.frames
        if i != self._cur:
            self.f.seek(i * self.frame_bytes)
            n = self.f.readinto(self.buf)
            if n != self.frame_bytes:                  # incomplete -> do NOT mark it cached
                self._cur = -1
                raise OSError("StreamSheet: short read for frame %d (%d/%d bytes)"
                              % (i, n or 0, self.frame_bytes))
            self._cur = i
        return self.bitmap

    def close(self):
        self.f.close()
