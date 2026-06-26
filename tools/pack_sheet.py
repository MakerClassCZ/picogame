#!/usr/bin/env python3
# Pack a pic_*.py sheet asset (from tools/picolib_img.py) into a raw FRAME-MAJOR .bin for
# streaming from flash (lib/picogame_stream.StreamSheet) instead of holding it in RAM.
# Also writes a slim companion module (palette + dims + a stream() helper) so the big pixel
# DATA leaves the .py and lives on disk as <name>.bin.
#
# Usage:
#   python tools/pack_sheet.py IN.py NAME --outdir DIR
#     IN.py    a module exposing DATA, W, H, FRAMES, STRIDE, PAL, TRANSP
#     NAME     base name -> DIR/NAME.bin + DIR/pic_NAME.py
#
# The source sheet is stored at `STRIDE` (whole-sheet width); we re-lay it out so each
# frame's W*H bytes are contiguous -> streaming a frame is a single seek + readinto.

import argparse
import importlib.util


def load(path):
    spec = importlib.util.spec_from_file_location("_sheet", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("name")
    ap.add_argument("--outdir", default=".")
    a = ap.parse_args()

    m = load(a.inp)
    W, H, F, ST = m.W, m.H, m.FRAMES, m.STRIDE
    data = m.DATA

    out = bytearray(W * H * F)                       # frame-major: frame 0, then frame 1, ...
    for fi in range(F):
        for y in range(H):
            src = y * ST + fi * W
            dst = fi * W * H + y * W
            out[dst:dst + W] = data[src:src + W]

    bin_path = "%s/%s.bin" % (a.outdir, a.name)
    with open(bin_path, "wb") as f:
        f.write(out)

    mod_path = "%s/pic_%s.py" % (a.outdir, a.name)
    with open(mod_path, "w") as f:
        f.write("# Streaming asset for %s: the pixel data lives in %s.bin (read from flash\n"
                % (a.name, a.name))
        f.write("# one frame at a time -- only %d B in RAM, not %d B). tools/pack_sheet.py.\n"
                % (W * H, W * H * F))
        f.write("import array\nimport picogame_stream\n\n")
        f.write("W = %d\nH = %d\nFRAMES = %d\nTRANSP = %s\nBIN = %r\n" % (W, H, F, m.TRANSP, a.name + ".bin"))
        f.write("PAL = array.array('H', %r)\n\n" % list(m.PAL))
        f.write("def stream(pg, path=BIN):\n")
        f.write("    return picogame_stream.StreamSheet(pg, path, W, H, FRAMES, PAL, TRANSP)\n")

    print("wrote %s (%d B, %d frames) + %s  (RAM/frame = %d B)"
          % (bin_path, len(out), F, mod_path, W * H))


if __name__ == "__main__":
    main()
