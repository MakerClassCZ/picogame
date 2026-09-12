# picogame_xip: draw assets straight from flash even when the FAT drive fragmented them.
#
# `pg.xip_map(path)` hands back one read-only memoryview per contiguous run of the file, in file
# order (a 1-tuple = the file is contiguous). Every boundary between two views is a cluster
# boundary, a multiple of 512 bytes into the file. A Bitmap wants ONE buffer, so this module
# cuts an image into row bands that each live inside one run, and copies only the rows that
# straddle a boundary. The RULE: never spend more RAM on seams than reading the whole thing
# would; over that budget, or where mapping is impossible (the simulator, the web playground,
# a stock firmware, an SD card), fall back to a plain read with the same result shape.
#
#   import picogame_xip as xip
#   for top, bm, buf in xip.bitmaps(pg, "assets/level.bin", 320, 240, pal, transparent=0):
#       sprites.append(pg.Sprite(bm, 0, top))       # row bands, 0-copy wherever they can be
#   sheet = xip.sheet(pg, "hero.bin", 32, 32, frames=8, pal=pal)   # frame-major sprite sheet
#   sheet.use(3); spr.bitmap = sheet.bitmap
#   tiles = pg.Bitmap(xip.one("tiles.bin"), 128, 128, format=pg.PAL8, palette=pal)
#
# Measured on a PicoPad (2026-09): splitting a straddling row into two part-width Bitmaps costs
# nothing in RAM and +6.6% blit time; copying that one row costs its bytes and +4.9%.

try:
    import picogame as _pg
    XIP = hasattr(_pg, "xip_map")
    MAX_RUNS = getattr(_pg, "XIP_MAX_RUNS", 1)
except ImportError:                     # desktop without the sim on the path
    _pg = None
    XIP = False
    MAX_RUNS = 1


def views(path):
    """The file's flash runs as a tuple of read-only memoryviews, in file order - or None when
    it cannot be mapped here (no xip_map, not internal flash, missing, empty, > MAX_RUNS runs).
    None means "read it instead", never an error the caller has to interpret."""
    if not XIP:
        return None
    try:
        return _pg.xip_map(path)
    except OSError:
        return None


def _read(path, offset, n):
    with open(path, "rb") as f:
        if offset:
            f.seek(offset)
        return f.read(n)


def _split(runs, offset, row_bytes, nrows):
    """Row-major cover of rows [0, nrows), each row `row_bytes` long, starting `offset` bytes into
    the concatenation of `runs`. Yields (top_row, n_rows, buf, copied): buf is a 0-copy slice of one
    run for a band of rows that fits inside it, or a bytearray copy for the ONE row that straddles a
    run boundary (a row wider than a run can straddle several: the copy gathers from all of them).
    Pieces are in order and cover the range exactly."""
    ends = []                           # cumulative end offset of each run
    total = 0
    for r in runs:
        total += len(r)
        ends.append(total)
    if offset + row_bytes * nrows > total:
        raise OSError("short file")
    row = 0
    pos = offset
    ri = 0
    while row < nrows:
        while pos >= ends[ri]:          # advance to the run that holds `pos`
            ri += 1
        run_start = ends[ri] - len(runs[ri])
        room = ends[ri] - pos           # bytes left in this run from pos
        fit = room // row_bytes         # whole rows that fit before the boundary
        if fit:
            n = fit if fit < nrows - row else nrows - row
            lo = pos - run_start
            yield row, n, runs[ri][lo:lo + n * row_bytes], False
            row += n
            pos += n * row_bytes
            continue
        buf = bytearray(row_bytes)      # one straddling row: gather it across the boundary(ies)
        got = 0
        rj = ri
        p = pos
        while got < row_bytes:
            rs = ends[rj] - len(runs[rj])
            take = ends[rj] - p
            if take > row_bytes - got:
                take = row_bytes - got
            buf[got:got + take] = runs[rj][p - rs:p - rs + take]
            got += take
            p += take
            if got < row_bytes:
                rj += 1
        yield row, 1, buf, True
        row += 1
        pos += row_bytes


def rows(path, row_bytes, nrows, offset=0, max_ram=None):
    """-> list of (top_row, n_rows, buf) covering rows [0, nrows) of the row-major image that starts
    `offset` bytes into `path`. buf is a 0-copy flash view, or a bytearray copy of the one row that
    straddles a run boundary. Seam copies never exceed `max_ram` (default: the size of a plain read);
    over budget or unmappable -> a single RAM piece of the same shape."""
    if max_ram is None:
        max_ram = row_bytes * nrows
    runs = views(path)
    if runs is not None:
        out = []
        ram = 0
        for top, n, buf, copied in _split(runs, offset, row_bytes, nrows):
            if copied:
                ram += len(buf)
                if ram > max_ram:
                    out = None
                    break
            out.append((top, n, buf))
        if out is not None:
            return out
    return [(0, nrows, _read(path, offset, row_bytes * nrows))]


def rows_buf(pieces, row_bytes, top, n):
    """Rows [top, top + n) of a rows()/bitmaps() result as one buffer: 0-copy when they lie inside
    one piece, a copy when they cross a piece boundary."""
    for ptop, pn, buf in pieces:
        if top >= ptop and top + n <= ptop + pn:
            lo = (top - ptop) * row_bytes
            return buf[lo:lo + n * row_bytes]
    out = bytearray(n * row_bytes)
    got = 0
    for ptop, pn, buf in pieces:
        lo = max(top, ptop)
        hi = min(top + n, ptop + pn)
        if lo < hi:
            src = buf[(lo - ptop) * row_bytes:(hi - ptop) * row_bytes]
            out[got:got + len(src)] = src
            got += len(src)
    return out


def bitmaps(pg, path, width, height, pal, stride=None, frames=1, transparent=None, fmt=None,
            offset=0, max_ram=None):
    """-> list of (top_row, Bitmap, buf): the image as row-band Bitmaps, a drop-in for the strip
    lists games build by hand. `stride` defaults to width * frames (a horizontal frame atlas)."""
    if fmt is None:
        fmt = pg.PAL8
    if stride is None:
        stride = width * frames
    bpp = 2 if fmt == pg.RGB565 else 1
    if bpp == 2 and offset & 1:
        raise ValueError("RGB565 needs an even offset")
    out = []
    for top, n, buf in rows(path, stride * bpp, height, offset, max_ram):
        out.append((top, pg.Bitmap(buf, width, n, format=fmt, palette=pal, frames=frames,
                                   stride=stride, transparent=transparent), buf))
    return out


def one(path, offset=0, size=None):
    """One buffer for an asset that must be a single Bitmap (a Tilemap tileset, a mode-7 texture,
    a .pal8 atlas): a 0-copy flash view when the bytes lie in one run, a RAM copy otherwise."""
    runs = views(path)
    if runs is not None:
        pos = 0
        for r in runs:
            if offset >= pos and (size is None or offset + size <= pos + len(r)):
                lo = offset - pos
                return r[lo:] if size is None else r[lo:lo + size]
            pos += len(r)
    if size is None:
        with open(path, "rb") as f:
            f.seek(offset)
            return f.read()
    return _read(path, offset, size)


class _Sheet:
    """Frame-major sheet: one Bitmap per frame, .use(i) is a pointer swap."""

    def __init__(self, bms):
        self._bms = bms
        self.frames = len(bms)
        self.bitmap = bms[0]

    def use(self, i):
        self.bitmap = self._bms[i % self.frames]
        return self.bitmap

    def close(self):
        pass


def sheet(pg, path, w, h, frames, pal, transparent=None, offset=0, max_ram=None):
    """Frame-major PAL8 sprite sheet from flash, with the picogame_stream.StreamSheet interface
    (.frames / .bitmap / .use(i) / .close()). A frame inside one run is a 0-copy Bitmap; a frame
    across a boundary is copied. Copies never exceed `max_ram` (default: ONE frame, what StreamSheet
    would cost) - over that, or unmappable, this returns a StreamSheet instead."""
    fb = w * h
    if max_ram is None:
        max_ram = fb
    runs = views(path)
    if runs is not None:
        try:
            bms = []
            ram = 0
            for top, n, buf, copied in _split(runs, offset, fb, frames):
                if copied:
                    ram += fb
                    if ram > max_ram:
                        raise MemoryError
                for k in range(n):
                    bms.append(pg.Bitmap(buf[k * fb:(k + 1) * fb], w, h, format=pg.PAL8,
                                         palette=pal, frames=1, stride=w, transparent=transparent))
            return _Sheet(bms)
        except (MemoryError, OSError):
            pass
    import picogame_stream
    return picogame_stream.StreamSheet(pg, path, w, h, frames, pal, transparent=transparent)
