# picogame DISPLAY TEST. Bare/custom SPI panel bring-up: draws colour bars + a top-left ORIGIN marker
# so you dial in the driver, SPI pins, ORIENTATION, colour order and inversion BY EYE. Copy to
# CIRCUITPY as code.py after editing the config, then edit + save to retry (no reset needed).
#
# Read it like this:
#   * bars left->right should be RED GREEN BLUE WHITE BLACK. Red and blue swapped -> flip the 0x08
#     bit of MADCTL below (0x60 <-> 0x68 on ST7789, 0x38 <-> 0x30 on ILI9341).
#   * whole screen photo-negative -> flip INVERT.
#   * the small YELLOW square must sit in the TOP-LEFT. Anywhere else -> change MADCTL.
#
# WHY MADCTL AND NOT `rotation=`
# displayio's `rotation` is a SOFTWARE transform, applied while compositing groups. It turns the
# REPL and the terminal and nothing else: picogame writes its strips straight into the panel's
# address window, so it never sees that transform. Dialling orientation with `rotation` therefore
# gives you a test pattern that looks right and a game that is still mirrored - and at 90/270 it
# also swaps width/height, which breaks picogame's clipping. MADCTL is the panel's own register,
# so it moves BOTH. This test draws through picogame for the same reason: what you see here is
# what your game gets.
#
# Once the pattern is right, carry MADCTL and INVERT over as they are - either into
# bare_pico_code.py, or as `PICOGAME_MADCTL` / `PICOGAME_INVERT` in settings.toml, which
# picogame_game.setup() applies for you.
import time

import board
import busio
import displayio

try:
    from fourwire import FourWire            # CircuitPython 9+
except ImportError:
    from displayio import FourWire            # older
from adafruit_st7789 import ST7789            # EDIT: your panel's driver

import picogame as pg                         # if this import fails, the firmware has no picogame
import picogame_clock
import picogame_game

# ---------------- config: EDIT for your wiring/panel ----------------
SCK, MOSI = board.GP18, board.GP19
TFT_CS, TFT_DC, TFT_RST = board.GP17, board.GP16, board.GP20
WIDTH, HEIGHT = 320, 240
ROWSTART, COLSTART = 0, 0                     # some panels need a pixel offset (e.g. 240x240 ST7789)
INVERT = True                                 # flip if the screen is photo-negative

# MADCTL, the panel's 0x36 register - orientation AND colour order in one absolute byte:
#   0x20 MV  row/column exchange -> landscape (you want this when WIDTH > HEIGHT)
#   0x40 MX  mirror horizontally
#   0x80 MY  mirror vertically
#   0x08     colour order; which way round is RGB depends on the panel
# Start at your panel's landscape base and add MX / MY until the yellow square is top-left:
#   ST7789  : 0x60 base | 0xA0 = 180 deg | 0x68 / 0xA8 = the same two with the other colour order
#   ILI9341 : 0x38 base | 0x78 = mirror H | 0xB8 = mirror V | 0xF8 = 180 deg
MADCTL = 0x60

displayio.release_displays()
spi = busio.SPI(SCK, MOSI)                     # clock + MOSI (a display is write-only, no MISO)
# FourWire drives the bus per-transaction, so set the baudrate HERE (a manual spi.configure is ignored)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=24_000_000)
disp = ST7789(bus, width=WIDTH, height=HEIGHT, rotation=0,          # rotation stays 0 - see above
              rowstart=ROWSTART, colstart=COLSTART)

scene, buf_a, buf_b = picogame_game.setup(display=disp, background=pg.rgb565(0, 0, 0))
W, H = disp.width, disp.height

# AFTER setup(), so this file wins over any PICOGAME_MADCTL/INVERT already in settings.toml -
# a probe that a stale settings key can silently override is worse than no probe.
bus.send(0x36, bytes([MADCTL & 0xFF]))
pg.invert(disp, INVERT)

BARS = (pg.rgb565(255, 0, 0), pg.rgb565(0, 255, 0), pg.rgb565(0, 0, 255),
        pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 0))
MARK = pg.rgb565(255, 255, 0)


def draw(view, vx, vy, vw, vh):
    bw = W // len(BARS)
    for i, colour in enumerate(BARS):
        view.fill_rect(i * bw - vx, -vy, bw, H, colour)
    view.fill_rect(-vx, -vy, 24, 24, MARK)     # origin marker: belongs in the TOP-LEFT corner


scene.add(pg.StripDraw(draw, 0, 0, W, H, always_dirty=False))

print("=== picogame display test ===")
print("%dx%d, MADCTL 0x%02X, invert %s" % (W, H, MADCTL, INVERT))
print("bars L->R = RED GREEN BLUE WHITE BLACK; yellow square must be TOP-LEFT.")
print("square misplaced -> change MADCTL | R/B swapped -> flip MADCTL bit 0x08 | negative -> INVERT")

clock = picogame_clock.Clock(30)
while True:
    scene.refresh()
    clock.tick()
