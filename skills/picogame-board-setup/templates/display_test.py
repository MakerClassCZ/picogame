# picogame DISPLAY TEST. Bare/custom SPI panel bring-up: draws colour bars + a top-left ORIGIN marker
# so you dial in the driver, SPI pins, rotation, colour order and inversion BY EYE. Copy to CIRCUITPY
# as code.py after editing the config. Read it like this:
#   * bars left->right should be RED GREEN BLUE WHITE BLACK. If red<->blue swap -> set BGR = True.
#   * whole screen photo-negative -> flip INVERT.
#   * the small YELLOW square must sit in the TOP-LEFT. If it's elsewhere -> change ROTATION (0/90/180/270).
# Once correct, mirror ROTATION/INVERT/BGR into your bare_pico_code.py (or PICOGAME_MADCTL/PICOGAME_INVERT
# for a firmware-built display). Needs your panel's driver in /lib (here adafruit_st7789).
import board
import busio
import displayio
import time

try:
    from fourwire import FourWire            # CircuitPython 9+
except ImportError:
    from displayio import FourWire            # older
import vectorio
from adafruit_st7789 import ST7789            # EDIT: your panel's driver

# ---------------- config: EDIT for your wiring/panel ----------------
SCK, MOSI = board.GP18, board.GP19
TFT_CS, TFT_DC, TFT_RST = board.GP17, board.GP16, board.GP20
WIDTH, HEIGHT = 320, 240
ROTATION = 0                                  # 0 / 90 / 180 / 270 until the yellow square is top-left
INVERT = True                                 # flip if the screen is photo-negative
BGR = True                                    # ST7789 driver default; set False if the R and B bars swap
ROWSTART, COLSTART = 0, 0                      # some panels need a pixel offset (e.g. 240x240 ST7789)

displayio.release_displays()
spi = busio.SPI(SCK, MOSI)                     # clock + MOSI (a display is write-only, no MISO)
# FourWire drives the bus per-transaction, so set the baudrate HERE (a manual spi.configure is ignored)
bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=24_000_000)
disp = ST7789(bus, width=WIDTH, height=HEIGHT, rotation=ROTATION, invert=INVERT,
              rowstart=ROWSTART, colstart=COLSTART, bgr=BGR)

pal = displayio.Palette(6)
pal[0] = 0xFF0000       # red
pal[1] = 0x00FF00       # green
pal[2] = 0x0000FF       # blue
pal[3] = 0xFFFFFF       # white
pal[4] = 0x000000       # black
pal[5] = 0xFFFF00       # yellow (origin marker)

grp = displayio.Group()
nbars = 5
bw = disp.width // nbars
for i in range(nbars):
    grp.append(vectorio.Rectangle(pixel_shader=pal, width=bw, height=disp.height, x=i * bw, y=0,
                                  color_index=i))
grp.append(vectorio.Rectangle(pixel_shader=pal, width=24, height=24, x=0, y=0, color_index=5))
disp.root_group = grp

print("=== picogame display test ===")
print("bars L->R = RED GREEN BLUE WHITE BLACK; yellow square must be TOP-LEFT.")
print("R/B swapped -> BGR=True | negative -> flip INVERT | square not top-left -> change ROTATION.")
while True:
    time.sleep(1)
