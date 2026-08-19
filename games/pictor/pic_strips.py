# Row-strip asset loader: a big background lives as N small files (assets/<name>_NN.bin), each a
# few KB of PAL8 rows, and each becomes its own Bitmap. Three ways to reach the pixels, best first:
#
#   1. picogame.xip_map() - the file is mapped from flash and costs NO RAM (the blitter reads it
#      through the XIP window). Needs a contiguous file, which is what the small strips are for:
#      a big file often lands in pieces on a lived-in FAT, a 5 KB one practically never does.
#   2. /rom/<name>.bin    - the ROMFS asset region, if the board carves one; also 0 RAM.
#   3. open().read()      - a plain read into RAM. Costs the strip's size, so a fragmented strip
#      (or a build without xip_map: the simulator, the web playground) still works, just heavier.
#
# `XIP` says whether route 1 exists at all, so a game can size its scene to the RAM it will need.
try:
    import picogame as _pg
    XIP = hasattr(_pg, "xip_map")
except ImportError:
    XIP = False


def _map(path):
    import picogame as pg
    return pg.xip_map(path)          # OSError: fragmented / not on internal flash / missing


def strips(pg, name, stride, height, rows, pal, transp, frames=1, root=""):
    """-> list of (top_row, Bitmap, buffer) covering rows 0..height in `rows`-row strips.
    `buffer` is the strip's pixel bytes, so a caller can slice a sub-Bitmap 0-copy."""
    out = []
    try:                                            # ROMFS region: one file, 0-copy slices
        whole = memoryview(open("/rom/" + name + ".bin", "rb"))
        for top in range(0, height, rows):
            n = min(rows, height - top)
            buf = whole[top * stride:(top + n) * stride]
            out.append((top, pg.Bitmap(buf, stride, n, format=pg.PAL8, palette=pal, frames=frames,
                                       stride=stride, transparent=transp), buf))
        return out
    except OSError:
        pass
    i = 0
    for top in range(0, height, rows):
        n = min(rows, height - top)
        path = root + "assets/" + name + "_%02d.bin" % i
        i += 1
        try:
            buf = _map(path)
        except (AttributeError, OSError):           # no xip_map, or this strip is fragmented
            with open(path, "rb") as f:
                buf = f.read()
        out.append((top, pg.Bitmap(buf, stride, n, format=pg.PAL8, palette=pal,
                                   frames=frames, stride=stride, transparent=transp), buf))
    return out


class XipSheet:
    """Frame-major PAL8 sheet mapped from flash: one Bitmap per frame over a slice of the same
    memoryview, so `use(i)` is a pointer swap - no read, no shared frame buffer, and no touch()
    (the sprite's bitmap pointer changing is dirty by itself). Same interface as
    picogame_stream.StreamSheet; raises OSError when the file cannot be mapped."""

    def __init__(self, pg, path, w, h, frames, palette, transparent):
        mv = _map(path)
        fb = w * h
        if len(mv) < fb * frames:
            raise OSError("short sheet")
        self.frames = frames
        self._bms = [pg.Bitmap(mv[i * fb:(i + 1) * fb], w, h, format=pg.PAL8, palette=palette,
                               frames=1, stride=w, transparent=transparent) for i in range(frames)]
        self.bitmap = self._bms[0]

    def use(self, i):
        self.bitmap = self._bms[i % self.frames]
        return self.bitmap

    def close(self):
        pass


def sheet(pg, path, w, h, frames, palette, transparent):
    """XipSheet when the file maps from flash, else picogame_stream.StreamSheet (one frame in RAM,
    re-read from flash on each animation step)."""
    try:
        return XipSheet(pg, path, w, h, frames, palette, transparent)
    except (AttributeError, OSError):
        import picogame_stream
        return picogame_stream.StreamSheet(pg, path, w, h, frames, palette, transparent)
