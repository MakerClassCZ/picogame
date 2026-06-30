# picogame_cutscene: show a FULLSCREEN image with ~0 RAM, by strip-streaming it from a flash FILE.
#
# A 320x240 frame is 150 KB (RGB565) / 75 KB (PAL8) - too big for the ~138 KB heap, and a .mpy const
# would just COPY to the heap (a FAT file is not XIP-mapped). So the image stays on flash as a raw
# ROW-MAJOR file and we read it one ~24-row BAND at a time into a small reused buffer, blitting each
# band straight to the display. Only the strip buffer (one band) is ever in RAM. The LCD then holds
# the image, so a static cutscene costs nothing after the one render.
#
# Bake a raw file with `tools/bake_image.py` (PNG -> wire-order RGB565 rows, or PAL8 + a palette):
#   import picogame_cutscene as cut, board
#   cut.play(pg, board.DISPLAY, bufA, btn, "intro.dat")          # render + wait for A/B  (RGB565)
#   cut.play(pg, board.DISPLAY, bufA, btn, "map.dat", palette=PAL)  # PAL8 (1 B/px file + palette)
#
# `band` MUST divide the height (240 % 24 == 0). `buffer` is your strip buffer (>= w*band*2 bytes).


def show(pg, display, buffer, path, w=320, h=240, band=24, palette=None):
    """Render the image at `path` to the display, streaming it band-by-band (no full-frame RAM)."""
    fmt = pg.PAL8 if palette is not None else pg.RGB565
    bpp = 1 if palette is not None else 2
    rowbuf = bytearray(w * band * bpp)
    bmp = pg.Bitmap(rowbuf, w, band, format=fmt, palette=palette, frames=1, stride=w)
    spr = pg.Sprite(bmp, 0, 0)
    with open(path, "rb") as f:
        y = 0
        while y < h:
            r = f.readinto(rowbuf)                       # next band of rows
            if not r:
                break
            if r < len(rowbuf):                          # short final read -> clear the stale tail
                for i in range(r, len(rowbuf)):
                    rowbuf[i] = 0
            spr.move(0, y)
            spr.touch()                                # pixels changed in place -> force the blit
            pg.render(display, [spr], buffer, 0, y, w, y + band, background=0)
            y += band


def play(pg, display, buffer, btn, path, w=320, h=240, band=24, palette=None):
    """show() the image, then block (polling `btn`) until A or B is pressed. Returns when dismissed."""
    show(pg, display, buffer, path, w, h, band, palette)
    while True:
        btn.poll()
        if btn.just_pressed(btn.A) or btn.just_pressed(btn.B):
            return
