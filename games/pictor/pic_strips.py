# Row-strip asset loader: a big background lives as N small files (assets/<name>_NN.bin), each a
# few KB of PAL8 rows, and each becomes one or more Bitmaps. Three ways to reach the pixels, best first:
#
#   1. picogame_xip     - the file is mapped from flash and costs NO RAM (the blitter reads it
#      through the XIP window). A fragmented file still maps: it comes back as one Bitmap per
#      contiguous run, and only a row that straddles a run boundary is copied.
#   2. /rom/<name>.bin  - the ROMFS asset region, if the board carves one; also 0 RAM.
#   3. open().read()    - a plain read into RAM. Costs the strip's size, so a build without
#      xip_map (the web playground, a stock firmware) still works, just heavier.
#
# `XIP` says whether route 1 exists at all, so a game can size its scene to the RAM it will need.
import picogame_xip as xip

XIP = xip.XIP


def strips(pg, name, stride, height, rows, pal, transp, frames=1, root=""):
    """-> list of (top_row, Bitmap, buffer) covering rows 0..height, in order. Each strip file is
    `rows` rows; a fragmented one yields several bands. `buffer` is the band's pixel bytes, so a
    caller can slice a sub-Bitmap 0-copy (see rows_buf for a slice that may cross bands)."""
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
        for t, bm, buf in xip.bitmaps(pg, path, stride, n, pal, stride=stride, frames=frames,
                                      transparent=transp):
            out.append((top + t, bm, buf))
    return out


def rows_buf(strip_list, stride, top, n):
    """Rows [top, top + n) of a strips() result as one buffer - 0-copy inside one band, a copy
    across bands. For a sub-Bitmap over a few rows of the art (Pictor's seam)."""
    return xip.rows_buf([(t, bm.height, buf) for t, bm, buf in strip_list], stride, top, n)


def sheet(pg, path, w, h, frames, palette, transparent):
    """Frame-major PAL8 sheet mapped from flash: one Bitmap per frame, .use(i) is a pointer swap.
    Falls back to picogame_stream.StreamSheet (one frame in RAM, re-read on each animation step)
    where mapping is impossible or would copy more than one frame."""
    return xip.sheet(pg, path, w, h, frames, palette, transparent=transparent)
