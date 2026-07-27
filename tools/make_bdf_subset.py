#!/usr/bin/env python3
"""Extract a glyph subset from a charcell BDF font (Terminus-style) into a
small standalone BDF - the asset format picogame_font.ExtraFont loads.

The source of truth for the shipped subsets is CircuitPython's own
tools/fonts/ter-u12n.bdf (the exact font terminalio.FONT is built from, so
subset glyphs blend seamlessly with builtin text).

Usage:
  make_bdf_subset.py SRC.bdf OUT.bdf --chars "áčď×°..."
  make_bdf_subset.py SRC.bdf OUT.bdf --codes 0xE1 0x10D ...

Glyph blocks are copied verbatim (only the CHARS count is rewritten), so the
output stays a valid BDF for any reader. Missing codepoints are reported and
skipped.
"""
import argparse
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--chars", default="", help="literal characters to keep")
    ap.add_argument("--codes", nargs="*", default=[],
                    help="codepoints to keep (0x.. or decimal)")
    ap.add_argument("--mirror", nargs="*", default=[],
                    help="SRC:DST pairs - append a horizontally mirrored copy "
                         "of glyph SRC under codepoint DST (for symbols the "
                         "font lacks, e.g. 0x21BB:0x21BA makes a CCW arrow)")
    args = ap.parse_args()

    want = [ord(c) for c in args.chars]
    want += [int(c, 0) for c in args.codes]
    want = sorted(set(want))
    if not want:
        sys.exit("nothing to extract (--chars/--codes)")

    src = open(args.src, encoding="ascii", errors="replace").read()
    header = src[:src.index("STARTCHAR")]
    blocks = {}
    for m in re.finditer(r"STARTCHAR .*?\nENDCHAR\n", src, re.S):
        enc = int(re.search(r"^ENCODING (-?\d+)$", m.group(0), re.M).group(1))
        blocks[enc] = m.group(0)

    keep = []
    missing = []
    for cp in want:
        if cp in blocks:
            keep.append(blocks[cp])
        else:
            missing.append(cp)
    if missing:
        print("MISSING (skipped): %s" % " ".join("U+%04X %r" % (c, chr(c))
                                                 for c in missing))

    for spec in args.mirror:
        a, b = spec.split(":")
        src_cp, dst_cp = int(a, 0), int(b, 0)
        if src_cp not in blocks:
            sys.exit("--mirror: U+%04X not in the source font" % src_cp)
        block = blocks[src_cp]
        w = int(re.search(r"^BBX (\d+)", block, re.M).group(1))
        out_lines = []
        in_bitmap = False
        for line in block.splitlines():
            if line.startswith("STARTCHAR"):
                line = "STARTCHAR mirrored_%04X" % src_cp
            elif line.startswith("ENCODING"):
                line = "ENCODING %d" % dst_cp
            elif line.startswith("BITMAP"):
                in_bitmap = True
            elif line.startswith("ENDCHAR"):
                in_bitmap = False
            elif in_bitmap:
                v = int(line, 16)
                m = 0
                for x in range(w):           # reverse the top w bits
                    m |= ((v >> (7 - x)) & 1) << (7 - (w - 1 - x))
                line = "%02X" % m
            out_lines.append(line)
        keep.append("\n".join(out_lines) + "\n")
        print("mirrored U+%04X -> U+%04X" % (src_cp, dst_cp))

    header = re.sub(r"^CHARS \d+$", "CHARS %d" % len(keep), header, flags=re.M)
    with open(args.out, "w", encoding="ascii") as f:
        f.write(header)
        f.writelines(keep)
        f.write("ENDFONT\n")
    print("%s: %d glyphs (%s)" % (args.out, len(keep),
                                  "".join(chr(c) for c in want if c in blocks)))


if __name__ == "__main__":
    main()
