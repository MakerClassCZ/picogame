#!/usr/bin/env python3
# /helpers/text-ui/ illustration: the two bundled picogame_font.ExtraFont glyph sets — Czech
# diacritics (picogame_cz.bdf) and game symbols (picogame_symbols.bdf). Renders each glyph's ACTUAL
# BDF bitmap (cut from the same Terminus build terminalio.FONT comes from) scaled up on a chip, with
# its U+XXXX label, in two labeled rows. Output: extrafont_glyphs.png.
#   python3 gen_extrafont.py
import os
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "picogame-libs", "fonts")
OUT = os.path.join(os.path.dirname(__file__), "extrafont_symbols.png")


def parse_bdf(path):
    """Return [(codepoint, [row_ints], w, h)] for each glyph, MSB-first byte rows."""
    glyphs = []
    cp = w = h = None
    rows = None
    reading = False
    with open(path) as f:
        for line in f:
            if line.startswith("ENCODING"):
                cp = int(line.split()[1])
            elif line.startswith("BBX"):
                _, w, h, _, _ = line.split()
                w, h = int(w), int(h)
            elif line.startswith("BITMAP"):
                rows, reading = [], True
            elif line.startswith("ENDCHAR"):
                glyphs.append((cp, rows, w, h)); reading = False
            elif reading:
                rows.append(int(line.strip(), 16))
    return glyphs


# theme
BG = (18, 20, 32)
CHIP = (30, 34, 54)
FG = (232, 234, 245)
LABEL = (150, 158, 185)
TITLE = (240, 232, 200)

SCALE = 4          # glyph pixel size
COLS = 13          # glyphs per row
CELL_W, CELL_H = 44, 62
PAD = 16
try:
    lab_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
    ttl_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
except Exception:
    lab_font = ttl_font = ImageFont.load_default()


def draw_glyph(dr, gx, gy, rows, w, h):
    for ry, bits in enumerate(rows):
        for cx in range(w):
            if bits & (1 << (7 - cx)):        # MSB-first within the byte
                x0 = gx + cx * SCALE
                y0 = gy + ry * SCALE
                dr.rectangle([x0, y0, x0 + SCALE - 1, y0 + SCALE - 1], fill=FG)


def layout(sets):
    # height: per set = title + N rows of cells
    total_rows = 0
    for _, glyphs in sets:
        total_rows += -(-len(glyphs) // COLS)
    width = PAD * 2 + COLS * CELL_W
    height = PAD
    for _, glyphs in sets:
        r = -(-len(glyphs) // COLS)
        height += 30 + r * CELL_H + 10
    img = Image.new("RGB", (width, height), BG)
    dr = ImageDraw.Draw(img)
    y = PAD
    for title, glyphs in sets:
        dr.text((PAD, y), title, font=ttl_font, fill=TITLE)
        y += 30
        for i, (cp, rows, w, h) in enumerate(glyphs):
            col = i % COLS
            row = i // COLS
            cx = PAD + col * CELL_W
            cy = y + row * CELL_H
            dr.rectangle([cx, cy, cx + CELL_W - 6, cy + CELL_H - 20], fill=CHIP)
            # centre the glyph in the chip
            gw, gh = w * SCALE, h * SCALE
            gx = cx + ((CELL_W - 6) - gw) // 2
            gy = cy + ((CELL_H - 20) - gh) // 2
            draw_glyph(dr, gx, gy, rows, w, h)
            dr.text((cx + 2, cy + CELL_H - 18), "U+%04X" % cp, font=lab_font, fill=LABEL)
        y += (-(-len(glyphs) // COLS)) * CELL_H + 10
    return img


sets = [
    ("Game symbols  —  picogame_symbols.bdf", parse_bdf(os.path.join(FONTS, "picogame_symbols.bdf"))),
]
img = layout(sets)
img.save(OUT)
print("wrote", OUT, img.size)
