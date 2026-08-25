# picogame on a BARE / CUSTOM board (nothing published a display): build the SPI display in code,
# publish it, hand it to picogame_game.setup(display=...) - a normal picogame scene. Buttons come from
# settings.toml (PICOGAME_BUTTONS / PICOGAME_PULL) via picogame_input.Buttons() - no board code.
# Copy to CIRCUITPY as code.py after editing the display config (use display_test.py to find it first).
import board
import busio
import displayio

try:
    from fourwire import FourWire            # CircuitPython 9+
except ImportError:
    from displayio import FourWire
from adafruit_st7789 import ST7789            # EDIT: your panel's driver

import picogame as pg
import picogame_game
import picogame_input
import picogame_clock
import picogame_shapes as shp

# ---------------- display config: EDIT (values dialed in with display_test.py) ----------------
SCK, MOSI = board.GP18, board.GP19
TFT_CS, TFT_DC, TFT_RST = board.GP17, board.GP16, board.GP20
WIDTH, HEIGHT = 320, 240
ROTATION, INVERT, BGR = 0, True, True         # BGR=True = ST7789 driver default (see display_test.py)
ROWSTART, COLSTART = 0, 0

displayio.release_displays()
_spi = busio.SPI(SCK, MOSI)                    # FourWire sets the baudrate per-transaction (below)
_bus = FourWire(_spi, command=TFT_DC, chip_select=TFT_CS, reset=TFT_RST, baudrate=24_000_000)
disp = ST7789(_bus, width=WIDTH, height=HEIGHT, rotation=ROTATION, invert=INVERT,
              rowstart=ROWSTART, colstart=COLSTART, bgr=BGR)

# Publish it as the board's display, so picogame_game.screen()/display() (and any library that
# asks for the screen) find it without being passed the handle.
try:
    import supervisor
    supervisor.runtime.display = disp
except (ImportError, AttributeError):
    pass

# --- picogame scene on our hand-built display ---
scene, bufA, bufB = picogame_game.setup(display=disp, background=pg.rgb565(10, 12, 20))
W, H = disp.width, disp.height                # size-independent: read from the display, never hardcode
btn = picogame_input.Buttons()                # reads PICOGAME_BUTTONS/PULL from settings.toml
clock = picogame_clock.Clock(30)

# a player box (generated shape - no art needed to prove the loop)
spr = pg.Sprite(shp.rect(16, 16, pg.rgb565(240, 80, 60)), W // 2 - 8, H // 2 - 8)
scene.add(spr)

print("bare-board picogame up: %dx%d. D-pad moves the box; wire buttons via PICOGAME_BUTTONS." % (W, H))
while True:
    btn.poll()
    if btn.is_pressed(btn.LEFT):
        spr.x = max(0, spr.x - 3)
    if btn.is_pressed(btn.RIGHT):
        spr.x = min(W - 16, spr.x + 3)
    if btn.is_pressed(btn.UP):
        spr.y = max(0, spr.y - 3)
    if btn.is_pressed(btn.DOWN):
        spr.y = min(H - 16, spr.y + 3)
    scene.refresh()
    clock.tick()
