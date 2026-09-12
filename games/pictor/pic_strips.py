# Row-strip asset loader: a big background lives as N small files (assets/<name>_NN.bin), each a
# few KB of PAL8 rows, and each becomes one or more Bitmaps. Reach the pixels the cheapest way:
#
#   1. picogame.xip_map() maps the file from flash at 0 RAM. It returns one memoryview per
#      contiguous flash run. We cut the strip into row bands: rows that sit whole inside a run
#      blit straight from flash (0 copy); only a row split across a run boundary is copied (one
#      row, a few hundred bytes). So fragmentation costs ~one row per seam, not the whole strip -
#      which matters on a lived-in Linux/vfat drive, where a strip is often broken into 2-3 runs.
#   2. /rom/<name>.bin - the ROMFS asset region, if the board carves one; also 0 RAM.
#   3. open().read() - a plain read into RAM (the simulator, the playground, a stock firmware).

try:
    import picogame as _pg
    XIP = hasattr(_pg, "xip_map")
except ImportError:
    XIP = False


def _load(pg, path, stride, nrows, pal, transp, frames):
    """One strip file -> [(top, Bitmap, buf)] bands covering rows 0..nrows in order. A band of
    whole rows inside one flash run is 0-copy; a row straddling a run boundary is copied (1 row).
    No mapping here (sim, playground, stock fw) -> the whole file read into RAM, one band."""
    runs = None
    if XIP:
        try:
            runs = _pg.xip_map(path)
        except OSError:
            runs = None
    if runs is None:
        with open(path, "rb") as f:
            runs = (memoryview(f.read()),)

    def band(buf, top, n):
        return (top, pg.Bitmap(buf, stride, n, format=pg.PAL8, palette=pal, frames=frames,
                               stride=stride, transparent=transp), buf)

    out = []
    row = 0
    ri = 0
    pos = 0                                          # byte offset inside runs[ri]
    while row < nrows:
        r = runs[ri]
        fit = (len(r) - pos) // stride               # whole rows left in this run
        if fit:
            n = min(fit, nrows - row)
            out.append(band(r[pos:pos + n * stride], row, n))
            row += n
            pos += n * stride
            if pos >= len(r):
                ri += 1
                pos = 0
        else:                                        # this row straddles a run boundary: copy it
            buf = bytearray(stride)
            got = 0
            while got < stride:
                r = runs[ri]
                take = min(len(r) - pos, stride - got)
                buf[got:got + take] = r[pos:pos + take]
                got += take
                pos += take
                if pos >= len(r):
                    ri += 1
                    pos = 0
            out.append(band(buf, row, 1))
            row += 1
    return out


def strips(pg, name, stride, height, rows, pal, transp, frames=1, root=""):
    """-> list of (top_row, Bitmap, buffer) covering rows 0..height. Each strip file is `rows`
    rows; a fragmented one may yield several bands. `buffer` is the band's pixel bytes."""
    out = []
    try:                                                # ROMFS region: one file, 0-copy slices
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
        for t, bm, buf in _load(pg, path, stride, n, pal, transp, frames):
            out.append((top + t, bm, buf))
    return out


def rows_buf(strip_list, stride, top, n):
    """Rows [top, top + n) of a strips() result as one buffer: 0-copy when they lie inside one
    band, a copy when they span bands (for a sub-Bitmap over a few rows of the art)."""
    for t, bm, buf in strip_list:
        if top >= t and top + n <= t + bm.height:
            lo = (top - t) * stride
            return buf[lo:lo + n * stride]
    out = bytearray(n * stride)
    got = 0
    for t, bm, buf in strip_list:
        lo = max(top, t)
        hi = min(top + n, t + bm.height)
        if lo < hi:
            src = buf[(lo - t) * stride:(hi - t) * stride]
            out[got:got + len(src)] = src
            got += len(src)
    return out


class _XipSheet:
    """Frame-major sheet mapped from flash: one Bitmap per frame, .use(i) is a pointer swap."""

    def __init__(self, bms):
        self._bms = bms
        self.frames = len(bms)
        self.bitmap = bms[0]

    def use(self, i):
        self.bitmap = self._bms[i % self.frames]
        return self.bitmap

    def close(self):
        pass


def sheet(pg, path, w, h, frames, palette, transparent):
    """Frame-major PAL8 sheet from flash: one Bitmap per frame (0 copy) when every flash run is a
    whole number of frames. Otherwise falls back to picogame_stream.StreamSheet (one frame in RAM,
    re-read on each animation step)."""
    fb = w * h
    if XIP:
        try:
            runs = _pg.xip_map(path)
            if not any(len(r) % fb for r in runs):      # every run is whole frames
                bms = []
                for r in runs:
                    for k in range(len(r) // fb):
                        bms.append(pg.Bitmap(r[k * fb:(k + 1) * fb], w, h, format=pg.PAL8,
                                             palette=palette, frames=1, stride=w,
                                             transparent=transparent))
                return _XipSheet(bms)
        except OSError:
            pass
    import picogame_stream
    return picogame_stream.StreamSheet(pg, path, w, h, frames, palette, transparent=transparent)
