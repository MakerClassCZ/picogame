# picogame `settings.toml` reference

Every knob picogame reads at runtime, so a board is adapted with NO reflash. `os.getenv` returns every
value as a string, so write on/off as `1`/`0`; volumes are dB (whole numbers are the norm). A key is read the first time the relevant helper is constructed, so edits take effect on
the next reload. Pin names are resolved against `board` first (e.g. `board.GP2` → write `GP2`), then
`microcontroller.pin` (a bare `GPn`).

---

## Buttons — one pin per button

```
PICOGAME_BUTTONS = "UP=GP2 DOWN=GP3 LEFT=GP4 RIGHT=GP5 A=GP12 B=GP13 X=GP14 Y=GP15 START=GP10 SELECT=GP11"
PICOGAME_PULL = "up"     # "up" (active-low, the default — button shorts the pin to GND) or "down"
```
- Names (the button vocabulary): `UP DOWN LEFT RIGHT A B X Y L1 L2 R1 R2 START SELECT`. Map only the
  buttons your board has; the rest simply never fire (a game checks `btns.has(...)`).
- Space- or comma-separated `NAME=PIN` tokens. `PIN` is a board attribute (`GP2`) or any pin object name.
- `PICOGAME_PULL` sets the internal resistor + active level for ALL buttons: `up` = wired to GND, pressed
  reads low (default); `down` = wired to 3V3, pressed reads high.
- Discover the pins with `templates/wiring_probe.py`: it shows live which GP each button is on; you
  assemble the `PICOGAME_BUTTONS` line from those readings (it prints a skeleton to fill in).

## Buttons — a scanned ROW × COLUMN matrix (e.g. a QWERTY)

For a key matrix instead of one-pin-per-button. Map only the keys you want onto game buttons; the rest
are ignored.
```
PICOGAME_MATRIX_ROWS = "GP0 GP1 GP2 GP3"        # row pins (space/comma separated)
PICOGAME_MATRIX_COLS = "GP4 GP5 GP6 GP7"        # column pins
PICOGAME_MATRIX_MAP  = "UP=1,2 DOWN=2,2 LEFT=2,1 RIGHT=2,3 A=3,5 B=3,4 START=0,0"
                                                #  NAME=row,col   (or NAME=key_number, key=row*ncols+col)
PICOGAME_MATRIX_ANODES = "cols"                 # optional: "cols" (default) or "rows" — flip if the
                                                #  diode direction is reversed
```
Discover `(row,col)` / key numbers with `templates/matrix_probe.py` first (it prints them per press;
layouts vary).

## Buttons — a shift register (PyBadge, PyGamer)

Buttons behind a 74HC165 parallel-in shift register. **Opt-in**: clocking three unknown GPIOs is not a
read-only act, so it is never probed. A PyBadge has no other buttons — without this key none fire.
```
PICOGAME_SHIFTPAD = "pybadge"      # preset (also "pygamer")
PICOGAME_SHIFTPAD = "latch=BUTTON_LATCH clock=BUTTON_CLOCK data=BUTTON_OUT bits=8 LEFT=7 UP=6 DOWN=5 RIGHT=4 SELECT=3 START=2 A=1 B=0"
                                   # full recipe; inv=1 when the register reads 1 for a RELEASED button,
                                   #  msb=0 clocks the low bit out first
```

## Tilt — an accelerometer as a D-pad

The board's accelerometer OR'd with the real D-pad, so games steer by tilting with no change. Reads the
sensor registers directly (no driver to install). **Opt-in** — a sensor on the bus is not a request to
steer with it.
```
PICOGAME_TILTPAD = "pybadge"                # preset (also "pygamer", "lis3dh")
PICOGAME_TILTPAD = "lis3dh on=4000 off=2500" # preset + overrides: on engages, off releases (off < on;
                                            #  raw counts, ~16384 = 1 g at +-2 g). swap=1 portrait board,
                                            #  invx=1 / invy=1 flip an axis, calib=0 keep the sensor's zero
```

## USB HID gamepad

Auto-attaches on a USB-host build (Fruit Jam) when a pad is plugged into the USB-HOST port — games need
no change. Default layout = the DragonRise `081f:e401` generic pad.
```
PICOGAME_USB = 0        # set 0 to DISABLE auto-attach (default on)
PICOGAME_USBPAD = "A=5:0x40 B=5:0x20"           # remap buttons: NAME=reportByteIndex:bitmask; a PARTIAL
                                                #  list merges over the defaults (here: just swap A/B)
```
- Full default map for reference: `A=5:0x20 B=5:0x40 X=5:0x10 Y=5:0x80 L1=6:0x01 R1=6:0x02 SELECT=6:0x10 START=6:0x20`; axes are report byte 0 (X) / byte 1 (Y).
- Discover another pad's bytes with `tools/usbpad_probe.py` (shipped in this repo): it prints
  which HID report byte/bit changes per press. (The wiring probe here is GPIO/I2C only — not USB HID.)
```
PICOGAME_USBPAD_ID = "081f:e401"    # hex vid:pid. REQUIRED for any pad that is not the DragonRise
                                    #  default - without it that pad is simply not found. Matching is by VID/PID on
                                    #  purpose: usb.core exposes no device class, so a "first device"
                                    #  grab would bind a keyboard or hub (a boot keyboard's zeroed
                                    #  axis bytes decode as LEFT|UP). A custom pad needs PICOGAME_USBPAD too.
PICOGAME_USBPAD_TIMEOUT = 3         # ms per HID read; default 3, floor 1 (0 would wait forever).
                                    #  Raise it only if a pad drops inputs on a busy hub.
```

## USB HID keyboard

Also auto-attaches on a USB-host build, as one more OR'd input source next to the pad — so a keyboard
is a valid controller with no game change. Defaults: **arrows or WASD** = D-pad, **Z/Space** = A,
**X** = B, **C** = X, **V** = Y, **Q/E** = L1/R1, **Enter** = START, **Esc** = SELECT.
```
PICOGAME_KBD = 0                    # set 0 to DISABLE the keyboard source (default on)
PICOGAME_USBKBD = "A=0x2C START=0x28"   # remap: NAME=HID usage code (hex or decimal). A PARTIAL list
                                    #  merges over the defaults above.
PICOGAME_USBKBD_EP = "2:0x83"       # interface:IN-endpoint, for a dongle whose boot interface is dead.
                                    #  Deterministic override instead of an auto-detect heuristic.
PICOGAME_USBKBD_TIMEOUT = 3         # ms per HID read; default 3, floor 1.
```
- HID usage codes, not ASCII: `0x52` Up, `0x51` Down, `0x50` Left, `0x4F` Right, `0x1D` Z, `0x2C` Space,
  `0x1B` X, `0x28` Enter, `0x29` Esc. A wireless 2.4 GHz dongle counts as a keyboard.
- Both `PICOGAME_USB = 0` (pad) and `PICOGAME_KBD = 0` (keyboard) exist separately, so a board can
  keep one and drop the other.

## I2C gamepads (generic — presets + recipes)

ONE driver for the whole family of I2C button devices (GPIO expanders: TCA9555/PCF8574/MCP23017
and vendor pads built on them), same philosophy as USB pads: one driver + a declarative string,
NOT a library per device. **OPT-IN, not auto-probed** (expanders have no identity register).
```
PICOGAME_I2CPAD = "qwstpad"        # preset: Pimoroni QwSTPad (Qw/ST cable, default addr 0x21);
                                   #  D-pad + ABXY, "+" -> START, "-" -> SELECT
PICOGAME_I2CPAD = "qwstpad;qwstpad@0x23"   # several pads (";"-separated) = local multiplayer
PICOGAME_I2CPAD = "addr=0x20 read=:1 inv=1 UP=0 DOWN=1 LEFT=2 RIGHT=3 A=4 B=5"
                                   # full RECIPE — any expander pad without writing code:
                                   #  addr= I2C address | init=HEX,HEX raw one-time writes |
                                   #  read=REG:LEN per-poll read (":1" = plain read, no reg) |
                                   #  inv=1 buttons active-low in the raw read | NAME=bit map
PICOGAME_I2C = "GP4,GP5"           # bare boards only: SDA,SCL pins. Boards with a Qw/ST or
                                   #  STEMMA connector need nothing (board.STEMMA_I2C/I2C is used)
```
- `Buttons()` ORs the pad(s) in automatically — games need no changes. A listed pad that doesn't
  answer = one debug note (see `PICOGAME_DEBUG`), game runs on.
- Multiplayer: `picogame_i2cpad.find_pads("qwstpad")` → one source per detected pad for
  `Buttons(sources=[pad])`; pads with LEDs light their player number on attach.
- Needs `picogame_i2cpad.mpy` in `/lib` (part of the standard bundle).

## Display (an SPI panel built by the board / firmware)

Only for a board whose display is a `busdisplay` (ST7789 etc.). A framebuffer/DVI board (Fruit Jam)
ignores these — its orientation is fixed by the firmware (rotation 0, 16-bit).
```
PICOGAME_INVERT = 1        # 1/0 — the panel's correct resting inversion. ST7789 panels ship in BOTH
                           #  polarities; if colours look photo-negative, flip this.
PICOGAME_MADCTL = 0x60     # absolute MADCTL byte (0x36 reg: mirror + BGR order). Can't be read back, so
                           #  it's absolute, not a bit-flip. PicoPad values: 0x60 stock | 0x68 BGR panel
                           #  | 0xA0 mounted 180° | 0xA8 both. Use for mirrored / rotated / wrong-hue panels.
PICOGAME_BRIGHTNESS = 80   # backlight, integer PERCENT 0-100
PICOGAME_RGB444 = 1        # send 12-bit colour (~25% less SPI traffic) where the firmware reports support
                           #  (picogame.RGB444_SUPPORTED). A win on a slow bus (PyBadge 24 MHz) and on the
                           #  PicoPad. A game's explicit setup(rgb444=...) wins over the key. Off unless set.
```
(`PICOGAME_INVERT` also keeps the `picogame_fx` InvertFlash effect calibrated — one key fixes both.)

## Display (a framebuffer / DVI board, e.g. Fruit Jam)

These are NOT `PICOGAME_*` keys — they're CircuitPython's own display keys that the auto-constructed DVI
output reads. picogame composites into the scanout buffer, so it needs rotation 0; the libs' errors
point here:
```
CIRCUITPY_PICODVI_ENABLE = "always"     # construct the DVI display at boot ("no display found" without it)
CIRCUITPY_DISPLAY_ROTATION = 0          # picogame requires 0 (raises "picogame needs rotation 0" otherwise)
CIRCUITPY_DISPLAY_COLOR_DEPTH = 16      # 16 = RGB565 (e.g. 320x240); 8 = RGB332, the only depth at 640x480
```
`PICOGAME_INVERT`/`MADCTL`/`BRIGHTNESS` do NOT apply here (orientation/colour are fixed by this mode).

## Fast RAM on PSRAM boards (Fruit Jam) — nothing to configure

There is no key for this. Upstream CircuitPython (PR #11176, in since 10.3.0-alpha) makes the
raspberrypi `port_malloc` take **internal SRAM first** and use PSRAM only as spillover, so buffers
land in fast RAM on their own. (An older fork key, `CIRCUITPY_HEAP_SRAM_SIZE`, did this by hand and
no longer exists — setting it does nothing.)

What still matters is **allocation ORDER**, because the SRAM segment is finite:

- Allocate the **biggest surface first**. A game that builds a large atlas or Canvas after a pile of
  small objects can find SRAM already spent and get PSRAM instead — measurably slower.
- Pick the **resolution at boot**, not at runtime: a framebuffer RE-allocation (switching to 640×480
  via `open_framebuffer`) can fail because the freed old buffer cannot merge across the live heap
  segment. Set `CIRCUITPY_DISPLAY_WIDTH = 640` + `HEIGHT = 480` in settings.toml instead, and
  `open_framebuffer(640, 480)` becomes a no-op.
- Cosmetic: `gc.mem_free()` reports the current segments (~150 KB), NOT the 8 MB spillover
  capacity — that's normal.

Measured on the Fruit Jam once the allocator does this: triangle fills run **13-18× faster** than
the old PSRAM-first behaviour, and it needs no settings.toml at all.

## Audio

picogame picks the output automatically: an I2S DAC (Fruit Jam) → I2S, unless you pass an explicit pin;
otherwise the analogue path on that pin or the board's audio pin — PWM where the firmware has
`audiopwmio`, the chip's true DAC where it does not (SAMD51: PyBadge, PyGamer). A speaker amp behind
`board.SPEAKER_ENABLE` is switched on for you. `picogame_audio` and `picogame_synth` share this path.
```
# --- PWM (PicoPad, bare Pico + a buzzer/amp on a PWM pin) ---
PICOGAME_AUDIO = "GP15"        # the PWM audio pin (board attr name or bare GPn). Unset -> board.AUDIO/SPEAKER/BUZZER

# --- I2S DAC (Fruit Jam TLV320; needs adafruit_tlv320 + adafruit_bus_device in /lib, NOT bundled) ---
PICOGAME_AUDIO_OUT = "headphone"   # "headphone" (default) | "speaker" | "both"
PICOGAME_HP_VOLUME  = -10          # headphone analog trim, dB. 0 = loud/line-level (too loud for phones)
                                   #  ... -78 = silent. picogame already applies -10 (the driver's own
                                   #  default is a near-silent -30), so set this only to change it.
PICOGAME_DAC_VOLUME = -3           # main digital fader, dB. Keep <= 0 to avoid DSP clipping.
PICOGAME_SPK_VOLUME = -10          # speaker analog trim, dB (same scale as HP)

# --- diagnostics (GENERAL, not audio-specific) ---
PICOGAME_DEBUG = 1                 # print '[picogame] ...' for a real subsystem failure (audio DAC/driver,
                                   #  USB pad, ...) to serial. NOTE: picogame_synth/_sfx swallow init
                                   #  errors to run silent (this unmasks them); picogame_audio.Audio()
                                   #  RAISES instead - if a game wraps it in try/except, read the
                                   #  traceback with the wrap removed. Remove once working.
```
Safety: `0 dB` headphone = line level, too loud for earbuds — don't exceed ~`-3` for `PICOGAME_HP_VOLUME`.

---

## What is NOT settings (needs a rebuild — see `firmware.md`)

The render path is compile-time: `CIRCUITPY_PICOGAME_FRAMEBUFFER` (DVI/framebuffer vs SPI),
`CIRCUITPY_PICOGAME_FAST_DISPLAY` (DMA display backend), `CIRCUITPY_PICOGAME_RGB444` (the board
declares its panel CAN do 12-bit colour — `PICOGAME_RGB444` above is the runtime switch that uses it),
and which modules the firmware even contains.
