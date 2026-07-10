#!/usr/bin/env python3
"""Convert a PNG/BMP into a picogame asset module.

Modes:
  (default)   single image / horizontal animation atlas (--frames N)
  --tile WxH  treat the image as a grid of W x H tiles (row-major) and repack
              them into a horizontal atlas Bitmap (use for vertical/grid tile
              sheets like ugame's 16x256 banks). Output FRAMES = number of tiles.
  --map       the image's palette indices ARE tile indices: emit a tilemap data
              module (WIDTH, HEIGHT, DATA bytes) for picogame.Tilemap.

Colors are emitted in ST7789 wire byte order (matches picogame.rgb565()).
"""

import argparse
import struct
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow required: pip install Pillow")


def rgb565_wire(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


try:                                    # Pillow >= 9.1 enum; fall back to the old constants
    _DITHER_FS = Image.Dither.FLOYDSTEINBERG
    _DITHER_NONE = Image.Dither.NONE
except AttributeError:                  # pragma: no cover
    _DITHER_FS = Image.FLOYDSTEINBERG
    _DITHER_NONE = Image.NONE
_ADAPTIVE = getattr(getattr(Image, "Palette", Image), "ADAPTIVE", 1)


def convert_pal8(img, dither=False, max_colors=255):
    """img: RGBA. Returns (palette_wire_list, data_bytes). Index 0 = transparent.

    With `dither` (or when there are more than `max_colors` distinct colours) the image is
    quantized to `max_colors` colours; `dither` adds Floyd-Steinberg error diffusion, which
    hides banding in gradients (skies, lighting) on the small palette. A low `max_colors`
    (e.g. 16-32) + `dither` gives a deliberate retro look."""
    w, h = img.size
    px = img.load()
    palette = [(0, 0, 0)]
    data = bytearray(w * h)
    opaque = set()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a >= 128:
                opaque.add((r, g, b))
    if not dither and len(opaque) <= max_colors:
        idx = {}
        for c in sorted(opaque):
            idx[c] = len(palette)
            palette.append(c)
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                data[y * w + x] = 0 if a < 128 else idx[(r, g, b)]
    else:
        rgb = img.convert("RGB")
        if dither:
            # quantize() only dithers when given a palette image, so build an adaptive
            # palette first, then map onto it with Floyd-Steinberg error diffusion.
            pal_img = rgb.convert("P", palette=_ADAPTIVE, colors=max_colors)
            q = rgb.quantize(palette=pal_img, dither=_DITHER_FS)
        else:
            q = rgb.quantize(colors=max_colors, dither=_DITHER_NONE)
        pal = q.getpalette()
        ncol = min(max_colors, len(pal) // 3)
        for i in range(ncol):
            palette.append((pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]))
        qpx = q.load()
        for y in range(h):
            for x in range(w):
                _, _, _, a = px[x, y]
                data[y * w + x] = 0 if a < 128 else (qpx[x, y] + 1)
    return [rgb565_wire(*c) for c in palette], bytes(data)


def convert_rgb565(img, key=(248, 0, 248)):
    w, h = img.size
    px = img.load()
    out = bytearray(w * h * 2)
    key_wire = rgb565_wire(*key)
    has_transp = False
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                v = key_wire
                has_transp = True
            else:
                v = rgb565_wire(r, g, b)
            struct.pack_into("<H", out, (y * w + x) * 2, v)
    return bytes(out), (key_wire if has_transp else None)


def repack_tiles(img, tw, th):
    """Reorder an image's tiles (row-major grid) into a single horizontal row."""
    w, h = img.size
    cols, rows = w // tw, h // th
    ntiles = cols * rows
    out = Image.new("RGBA", (tw * ntiles, th))
    for t in range(ntiles):
        sx, sy = (t % cols) * tw, (t // cols) * th
        out.paste(img.crop((sx, sy, sx + tw, sy + th)), (t * tw, 0))
    return out, ntiles


def _orient_bytes(tile, tw, th, transpose, fx, fy):
    """Render `tile` with (transpose, fx, fy) using the SAME formula as the engine blit, so the
    converter's orientation codes match what the firmware draws. Returns the result's bytes."""
    src = tile.load()
    dw, dh = (th, tw) if transpose else (tw, th)
    out = Image.new("RGBA", (dw, dh))
    op = out.load()
    for ly in range(dh):
        for lx in range(dw):
            su = ly if transpose else lx          # -> source X
            sv = lx if transpose else ly          # -> source Y
            if fx:
                su = tw - 1 - su
            if fy:
                sv = th - 1 - sv
            op[lx, ly] = src[su, sv]
    return out.tobytes()


def dedup_tiles(atlas, tw, ntiles):
    """Fold tiles that are identical UP TO ORIENTATION (all 8: 4 rotations x mirror) into a smaller
    atlas -> less tileset RAM (CircuitPython holds the Bitmap in the scarce heap, unlike a native
    flash-resident const). Returns (new_atlas, remap, n_unique); remap[i] = (unique_idx, flip_x,
    flip_y, transpose) -- rewrite a tilemap with: new = REMAP[old]; tm.tile(x, y, *new). Rotations
    are only folded for SQUARE tiles (transpose swaps w/h)."""
    th = atlas.height
    combos = [(0, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1)]
    if tw == th:                                   # square -> add the transpose (rotation) variants
        combos += [(1, 0, 0), (1, 1, 0), (1, 0, 1), (1, 1, 1)]
    variant = {}                                   # rendered bytes -> (unique_idx, fx, fy, transpose)
    remap = []
    uniques = []
    for t in range(ntiles):
        tile = atlas.crop((t * tw, 0, t * tw + tw, th))
        key = tile.tobytes()
        if key in variant:
            remap.append(variant[key])
        else:
            ui = len(uniques)
            uniques.append(t)
            remap.append((ui, 0, 0, 0))
            for (tr, fx, fy) in combos:            # register every orientation of this new unique
                variant.setdefault(_orient_bytes(tile, tw, th, tr, fx, fy), (ui, fx, fy, tr))
    new = Image.new("RGBA", (tw * len(uniques), th))
    for ui, ot in enumerate(uniques):
        new.paste(atlas.crop((ot * tw, 0, ot * tw + tw, th)), (ui * tw, 0))
    return new, remap, len(uniques)


def rle_encode(data, w, h):
    """Per-row run-length encode an index buffer: runs of (count 1..255, value).
    Row-independent so a C decoder can stream one scanline at a time."""
    out = bytearray()
    for y in range(h):
        row = y * w
        x = 0
        while x < w:
            v = data[row + x]
            run = 1
            while x + run < w and run < 255 and data[row + x + run] == v:
                run += 1
            out.append(run)
            out.append(v)
            x += run
    return bytes(out)


def write_module(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines))


def emit_map(args):
    img = Image.open(args.input)
    if img.mode != "P":
        img = img.convert("P")
    w, h = img.size
    px = img.load()
    data = bytes(px[x, y] for y in range(h) for x in range(w))
    write_module(args.output, [
        "# picogame tilemap data from %s" % (args.name or args.input),
        "WIDTH = %d" % w,
        "HEIGHT = %d" % h,
        "DATA = %s" % repr(data),
        "",
        "",
        "def fill(tilemap):",
        "    i = 0",
        "    for ty in range(HEIGHT):",
        "        for tx in range(WIDTH):",
        "            tilemap.tile(tx, ty, DATA[i]); i += 1",
        "",
    ])
    print("wrote %s: tilemap %dx%d (%d tiles)" % (args.output, w, h, w * h))


def main():
    ap = argparse.ArgumentParser(description="PNG/BMP -> picogame asset module")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--format", choices=("auto", "pal8", "rgb565"), default="auto")
    ap.add_argument("--frames", type=int, default=1)
    ap.add_argument("--tile", default=None, help="WxH: repack a tile grid into an atlas")
    ap.add_argument("--map", action="store_true", help="emit tilemap indices, not pixels")
    ap.add_argument("--transparent-index", type=int, default=None,
                    help="palette index treated as transparent (for P-mode sheets)")
    ap.add_argument("--rle", action="store_true",
                    help="RLE-compress a single-frame PAL8 image (big backgrounds: far less "
                         "flash/.mpy; the module inflates to a Bitmap on load)")
    ap.add_argument("--dither", action="store_true",
                    help="Floyd-Steinberg dither when reducing to PAL8 (hides gradient banding); "
                         "implies --format pal8")
    ap.add_argument("--colors", type=int, default=255,
                    help="max PAL8 palette colours 1..255 (default 255). Low + --dither = retro look")
    ap.add_argument("--dedup", action="store_true",
                    help="with --tile: fold identical tiles -> smaller tileset (less RAM); emits a "
                         "REMAP table to rewrite your tilemap (new = REMAP[old])")
    ap.add_argument("--split", action="store_true",
                    help="emit pic_X.py (metadata+palette+loader) AND X.bin (raw pixels) instead "
                         "of inlining DATA: the .bin goes into a ROMFS asset image "
                         "(tools/build_romfs.py) and loads 0-copy from XIP flash on boards with "
                         "an asset region; everywhere else the loader falls back to reading the "
                         "sibling .bin (device FAT / desktop sim)")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()
    args.colors = max(1, min(255, args.colors))

    if args.map:
        emit_map(args)
        return

    img = Image.open(args.input).convert("RGBA")

    # Map a source palette index to transparency (alpha=0) before any repack.
    if args.transparent_index is not None:
        src = Image.open(args.input)
        if src.mode != "P":
            sys.exit("--transparent-index needs a paletted (P) image")
        spx = src.load()
        ipx = img.load()
        w0, h0 = img.size
        for y in range(h0):
            for x in range(w0):
                if spx[x, y] == args.transparent_index:
                    r, g, b, _ = ipx[x, y]
                    ipx[x, y] = (r, g, b, 0)

    remap = None
    if args.tile:
        tw, th = (int(v) for v in args.tile.lower().split("x"))
        img, frames = repack_tiles(img, tw, th)
        if args.dedup:
            before = frames
            img, remap, frames = dedup_tiles(img, tw, frames)
            print("dedup: %d -> %d tiles (%.0f%% saved)" % (
                before, frames, 100.0 * (before - frames) / before if before else 0))
    else:
        frames = args.frames

    w, h = img.size
    if frames < 1 or w % frames != 0:
        sys.exit("frames must be >=1 and divide width (%d)" % w)
    frame_w = w // frames
    stride = w

    fmt = args.format
    if args.dither or args.colors < 255:
        fmt = "pal8"                    # dithering / colour-reduction only makes sense for PAL8
    if fmt == "auto":
        opaque = {img.getpixel((x, y))[:3]
                  for y in range(h) for x in range(w) if img.getpixel((x, y))[3] >= 128}
        fmt = "pal8" if len(opaque) <= 256 else "rgb565"

    palette_bytes = b""
    needs_array = False
    if fmt == "pal8":
        palette_wire, data = convert_pal8(img, dither=args.dither, max_colors=args.colors)
        fmt_const, transparent = 1, 0
        palette_bytes = b"".join(struct.pack("<H", v) for v in palette_wire)
        # emit a uint16 array (NOT raw bytes): correct both for the C engine's buffer
        # protocol AND for indexed access in pure-Python (the simulator).
        palette_repr = "array.array('H', %r)" % (palette_wire,)
        needs_array = True
    else:
        data, transparent = convert_rgb565(img)
        fmt_const, palette_repr = 0, "None"

    if args.rle:
        if fmt != "pal8" or frames != 1:
            sys.exit("--rle needs a single-frame PAL8 image")
        rle = rle_encode(data, w, h)
        write_module(args.output, [
            "import array",
            "# picogame RLE asset from %s (%dx%d, inflates to a PAL8 Bitmap on load)" % (
                args.name or args.input, w, h),
            "WIDTH = %d" % w,
            "HEIGHT = %d" % h,
            "TRANSPARENT = %s" % (str(transparent) if transparent is not None else "None"),
            "PALETTE = %s" % palette_repr,
            "RLE = %s" % repr(rle),
            "",
            "",
            "def bitmap(pg):",
            "    data = bytearray(WIDTH * HEIGHT)",
            "    rle = RLE; i = 0; p = 0; n = len(rle)",
            "    while p < n:",
            "        c = rle[p]; v = rle[p + 1]; p += 2",
            "        for _ in range(c):",
            "            data[i] = v; i += 1",
            "    return pg.Bitmap(data, WIDTH, HEIGHT, format=1, palette=PALETTE,",
            "                     frames=1, stride=WIDTH, transparent=TRANSPARENT)",
            "",
        ])
        raw = w * h
        print("wrote %s: RLE %dx%d, %d B (raw %d B, %.0f%% of raw)" % (
            args.output, w, h, len(rle), raw, 100.0 * len(rle) / raw))
        return

    if args.split:
        if args.rle:
            sys.exit("--split and --rle are exclusive (RLE inlines its data)")
        import os
        base = os.path.splitext(os.path.basename(args.output))[0]
        bin_name = (base[4:] if base.startswith("pic_") else base) + ".bin"
        bin_path = os.path.join(os.path.dirname(args.output) or ".", bin_name)
        with open(bin_path, "wb") as bf:
            bf.write(data)
        write_module(args.output, ([
            "import array"] if needs_array else []) + [
            "# picogame SPLIT asset from %s (%s, frame %dx%d, frames %d): pixels live in %s," % (
                args.name or args.input, fmt, frame_w, h, frames, bin_name),
            "# packed into the ROMFS asset image by tools/build_romfs.py. Only the palette (~%d B)" % (
                len(palette_bytes) or 2),
            "# stays in RAM; on a board with an asset region the pixels blit 0-copy from XIP flash.",
            "WIDTH = %d" % frame_w,
            "HEIGHT = %d" % h,
            "FRAMES = %d" % frames,
            "STRIDE = %d" % stride,
            "FORMAT = %d  # 0=RGB565, 1=PAL8" % fmt_const,
            "TRANSPARENT = %s" % (str(transparent) if transparent is not None else "None"),
            "PALETTE = %s" % palette_repr,
            "BIN = %r" % bin_name,
        ] + (["REMAP = %r  # per old tile: (idx, flip_x, flip_y, transpose); tm.tile(x, y, *REMAP[old])"
              % (remap,)] if remap is not None else []) + [
            "",
            "",
            "def data(root=\"\"):",
            "    \"\"\"The raw pixels: a memoryview into XIP flash when the ROMFS asset region is",
            "    mounted (0-copy; slicing stays 0-copy - build sub-Bitmaps from slices freely),",
            "    else the sibling .bin at `root` read into RAM (device FAT / desktop sim).\"\"\"",
            "    try:",
            "        return memoryview(open(\"/rom/\" + BIN, \"rb\"))",
            "    except OSError:",
            "        with open(root + BIN, \"rb\") as f:",
            "            return f.read()",
            "",
            "",
            "def bitmap(pg, root=\"\"):",
            "    return pg.Bitmap(data(root), WIDTH, HEIGHT, format=FORMAT, palette=PALETTE,",
            "                     frames=FRAMES, stride=STRIDE, transparent=TRANSPARENT)",
            "",
        ])
        print("wrote %s + %s: %s %dx%d x%d frames, pixels %d B split out%s" % (
            args.output, bin_path, fmt, frame_w, h, frames, len(data),
            ", palette %d B stays in .py" % len(palette_bytes) if fmt == "pal8" else ""))
        return

    write_module(args.output, ([
        "import array"] if needs_array else []) + [
        "# picogame asset from %s (%s, frame %dx%d, frames %d)" % (
            args.name or args.input, fmt, frame_w, h, frames),
        "WIDTH = %d" % frame_w,
        "HEIGHT = %d" % h,
        "FRAMES = %d" % frames,
        "STRIDE = %d" % stride,
        "FORMAT = %d  # 0=RGB565, 1=PAL8" % fmt_const,
        "TRANSPARENT = %s" % (str(transparent) if transparent is not None else "None"),
        "PALETTE = %s" % palette_repr,
        "DATA = %s" % repr(data),
    ] + (["REMAP = %r  # per old tile: (idx, flip_x, flip_y, transpose); tm.tile(x, y, *REMAP[old])"
          % (remap,)] if remap is not None else []) + [
        "",
        "",
        "def bitmap(pg):",
        "    return pg.Bitmap(DATA, WIDTH, HEIGHT, format=FORMAT, palette=PALETTE,",
        "                     frames=FRAMES, stride=STRIDE, transparent=TRANSPARENT)",
        "",
    ])
    print("wrote %s: %s %dx%d x%d frames, data %d B%s" % (
        args.output, fmt, frame_w, h, frames, len(data),
        ", palette %d B" % len(palette_bytes) if fmt == "pal8" else ""))


if __name__ == "__main__":
    main()
