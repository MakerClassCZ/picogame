# picogame DISPLAY TEST - bare/custom SPI panel bring-up.
#
# It CYCLES the four orientations itself, four seconds each, and writes on the panel which one you
# are looking at. You do not edit-and-reload to find the value: you watch, and you note the label
# of the frame that reads correctly. Copy to CIRCUITPY as code.py after setting the wiring below.
#
# WHAT TO LOOK FOR, in this order:
#   1. TEXT READS LEFT TO RIGHT and is not mirrored  -> horizontal is right
#   2. the word TOP-LEFT sits in the top-left corner -> vertical is right
#   3. bars read RED GREEN BLUE WHITE BLACK          -> colour order is right (else flip COLOUR_BIT)
#   4. nothing looks like a photo negative           -> else flip INVERT
#
# WHAT TO DO WITH THE ANSWER - the panel shows both forms:
#   PICOGAME_FLIP  = "hv"   <- put THIS in settings.toml. It is read by the boot.py / launcher that
#                              builds your display, so the panel is right from power-on: the REPL, a
#                              traceback and every game get it, and no game code changes. Set once
#                              per box and forget it.
#   PICOGAME_MADCTL = 0xF8  <- the same thing as a raw register byte, applied later by
#                              picogame_game.setup(). Handy WHILE experimenting, because
#                              settings.toml is re-read on every reload. Delete it once FLIP is
#                              set - MADCTL is absolute and silently overrides FLIP.
#
# WHY NOT displayio's `rotation=`: it is a software transform applied when compositing groups, so it
# turns the REPL and leaves picogame alone - picogame writes strips straight into the panel's address
# window. It gives you a correct-looking terminal over a mirrored game, and at 90/270 it swaps
# width/height while the panel keeps its own, which breaks picogame's clipping. Orientation on an SPI
# panel lives in ONE place: the panel's MADCTL register. This test only ever writes that.
import time

import board
import busio
import displayio
import terminalio

try:
    from fourwire import FourWire            # CircuitPython 9+
except ImportError:
    from displayio import FourWire            # older
from adafruit_st7789 import ST7789            # EDIT: your panel's driver

import picogame as pg                         # if THIS import fails, the firmware has no picogame
import picogame_clock
import picogame_game

# ---------------- config: EDIT for your wiring/panel ----------------
SCK, MOSI = board.GP18, board.GP19
TFT_CS, TFT_DC, TFT_RST = board.GP17, board.GP16, board.GP20
WIDTH, HEIGHT = 320, 240
ROWSTART, COLSTART = 0, 0                     # some panels need a pixel offset (e.g. 240x240 ST7789)
INVERT = True                                 # photo-negative? flip this
COLOUR_BIT = 0x08                             # red and blue swapped? use 0x00 instead
# --------------------------------------------------------------------

MV = 0x20 if WIDTH > HEIGHT else 0x00         # row/column exchange = landscape
MX, MY = 0x40, 0x80                           # mirror horizontally / vertically
BASE = MV | COLOUR_BIT
CANDIDATES = (("", BASE), ("h", BASE | MX), ("v", BASE | MY), ("hv", BASE | MX | MY))
HOLD_S = 4                                     # seconds per orientation

displayio.release_displays()
spi = busio.SPI(SCK, MOSI)                     # clock + MOSI (a display is write-only, no MISO)
# FourWire drives the bus per-transaction, so set the baudrate HERE (a manual spi.configure is ignored)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=24_000_000)
disp = ST7789(bus, width=WIDTH, height=HEIGHT, rotation=0,     # rotation stays 0 - see the header
              rowstart=ROWSTART, colstart=COLSTART)

scene, buf_a, buf_b = picogame_game.setup(display=disp, background=pg.rgb565(0, 0, 0))
W, H = disp.width, disp.height
pg.invert(disp, INVERT)

INK = pg.rgb565(255, 255, 255)
DIM = pg.rgb565(120, 130, 150)
MARK = pg.rgb565(255, 255, 0)
CORNER = pg.rgb565(255, 0, 255)
BLACK = pg.rgb565(0, 0, 0)
BARS = ((pg.rgb565(255, 0, 0), "RED"), (pg.rgb565(0, 255, 0), "GREEN"),
        (pg.rgb565(0, 0, 255), "BLUE"), (pg.rgb565(255, 255, 255), "WHITE"),
        (BLACK, "BLACK"))
FW, FH = terminalio.FONT.get_bounding_box()[:2]
BAR_H = min(FH + 8, H // 5)                    # the bars stay a band, even on a short panel
LINE = FH + 4
now = [0]                                      # index into CANDIDATES


def draw(view, vx, vy, vw, vh):
    ox, oy = -vx, -vy                          # view (0,0) is the strip corner; this is screen (0,0)
    flip, madctl = CANDIDATES[now[0]]

    view.fill_rect(ox, oy, FH, FH, MARK)                            # the origin block...
    view.text(ox + FH + 4, oy + 2, "TOP-LEFT", MARK, terminalio.FONT)    # ...and which corner it is
    view.fill_rect(ox + W - 8, oy + H - BAR_H - 8, 8, 8, CORNER)    # a second, different mark

    # Kept short on purpose: a 240px panel fits 40 characters, and Canvas.text CLIPS rather than
    # wraps - a line that runs off the edge just vanishes, which on a bring-up tool reads as a
    # broken display. Lines are dropped from the bottom if the panel is too short for them.
    lines = (("text reads L to R", DIM),
             ('FLIP = "%s"' % flip, INK),
             ("MADCTL = 0x%02X" % madctl, INK),
             ("put FLIP in settings.toml", DIM),
             ("%d of %d, %ds each" % (now[0] + 1, len(CANDIDATES), HOLD_S), DIM))
    y = oy + FH + 10
    for text, colour in lines:
        if y + FH > oy + H - BAR_H - 10:       # would collide with the colour bars: stop
            break
        view.text(ox + FH + 4, y, text, colour, terminalio.FONT)
        y += LINE

    bw = W // len(BARS)                        # colour bars along the bottom, each one named
    for k, (colour, name) in enumerate(BARS):
        view.fill_rect(ox + k * bw, oy + H - BAR_H, bw, BAR_H, colour)
        if bw >= (len(name) + 1) * FW:         # only label a bar the name actually fits in
            view.text(ox + k * bw + 3, oy + H - BAR_H + 4, name,
                      BLACK if name == "WHITE" else INK, terminalio.FONT)


layer = pg.StripDraw(draw, 0, 0, W, H, always_dirty=False)
scene.add(layer)

print("=== picogame display test ===")
print("%dx%d panel. Cycling %d orientations, %ds each." % (W, H, len(CANDIDATES), HOLD_S))
print("Watch for: text left-to-right, TOP-LEFT in the top-left corner,")
print("bars RED GREEN BLUE WHITE BLACK, no photo-negative.")
print("Note the FLIP shown on the frame that reads correctly, then put it in settings.toml.")

clock = picogame_clock.Clock(30)
bus.send(0x36, bytes([CANDIDATES[0][1]]))
switch_at = time.monotonic() + HOLD_S
while True:
    if time.monotonic() >= switch_at:
        now[0] = (now[0] + 1) % len(CANDIDATES)
        flip, madctl = CANDIDATES[now[0]]
        bus.send(0x36, bytes([madctl]))        # the panel's own register: moves EVERYTHING on screen
        layer.invalidate()                     # the labels changed too
        print('  showing PICOGAME_FLIP = "%s"   (PICOGAME_MADCTL = 0x%02X)' % (flip, madctl))
        switch_at = time.monotonic() + HOLD_S
    scene.refresh()
    clock.tick()
