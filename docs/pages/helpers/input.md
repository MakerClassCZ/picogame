---
title: "Input & controls"
description: "Read the D-pad and buttons with picogame_input, and add USB gamepad or keyboard control on USB-host boards — with zero game-code changes."
---

`picogame_input.Buttons` is the one input object every game uses. It reads the board's physical
buttons into a **bitmask** with edge detection, so game code never re-does the wiring:

```python
import picogame_input as pi
btn = pi.Buttons()

# each frame:
btn.poll()
if btn.is_pressed(pi.LEFT):   px -= 2
if btn.just_pressed(pi.A):    jump()
if btn.repeat(pi.DOWN):       menu_move(+1)   # PICO-8 btnp auto-repeat, good for menus
```

## One virtual controller, mapped to real hardware

The engine gives every game the **same virtual controller** — a fixed set of logical buttons — and you
**map your board's real hardware onto it**. Games always code against the logical names (`pi.A`,
`pi.LEFT`), never against pins, so the *same `code.py`* runs on a PicoPad, a breadboard Pico, a keypad
matrix, or a USB gamepad; only the mapping changes.

The logical set:

- **Baseline (every game can rely on these):** the 4-way D-pad — `UP` `DOWN` `LEFT` `RIGHT` — plus `A` and `B`.
- **Optional extras (map them if your hardware has them):** `X` `Y`, shoulders `L1` `L2` `R1` `R2`, and `START` `SELECT`.

A board maps whatever subset it physically has; absent buttons simply never fire. Query availability
with `btn.has(pi.L1)` so a game can hide a control the board lacks. The physical→logical mapping lives
in `settings.toml` (below) — one file, no reflash — resolved per source: `PICOGAME_BUTTONS` for GPIO,
`PICOGAME_MATRIX_*` for a key matrix, `PICOGAME_USBPAD` / `PICOGAME_USBKBD` for USB.

`Buttons` methods: `poll() -> mask`, `is_pressed(mask)`, `just_pressed(mask)`, `just_released(mask)`,
`has(mask)`, `repeat(button, delay=15, interval=4)`, `clear()`. For input-leniency windows (coyote
time, jump buffering) use `pi.Timer(frames)` with `.feed(cond)` / `.is_active` / `.consume()`.

## Input sources are OR'd together

```python
Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)
```

A `Buttons` object can read from **several sources at once** and ORs them into one mask, so a game
reads them all identically:

- **On-board GPIO buttons** — the default; the pin map is a *profile* resolved from `settings.toml`
  (`PICOGAME_BUTTONS`) or a board default.
- **A scanned key matrix** (`matrix=`, or the `PICOGAME_MATRIX_*` settings keys) — for keypad-style
  boards.
- **USB HID gamepad / keyboard** (`usb=`, auto-attached on USB-host builds) — see below.

Because everything ORs, **you don't branch on the source**: the same `btn.just_pressed(pi.A)` fires
whether A came from a GPIO button, a matrix cell, a USB pad, or a keyboard key.

## Map your hardware in `settings.toml`

Each source has its own mapping key. Edit `settings.toml` on the `CIRCUITPY` drive and reset — no
firmware rebuild. The [settings.toml reference](/custom-board/) lists every key and its exact format;
the common cases:

**Direct GPIO buttons** — `NAME=GPpin` tokens. Map only what you have:

```toml
# a Pico wired D-pad + A/B, plus optional X/Y
PICOGAME_BUTTONS = "UP=GP2 DOWN=GP3 LEFT=GP4 RIGHT=GP5 A=GP6 B=GP7 X=GP8 Y=GP9"
PICOGAME_PULL = "up"    # buttons to GND, pressed reads low (the default)
```

**A scanned key matrix** — give the row/column pins, then map matrix cells to logical buttons by
`NAME=row,col`. picogame scans the grid and de-bounces it via the `keypad` module:

```toml
PICOGAME_MATRIX_ROWS = "GP0 GP1 GP2 GP3"
PICOGAME_MATRIX_COLS = "GP4 GP5 GP6 GP7"
PICOGAME_MATRIX_MAP  = "UP=0,1 DOWN=2,1 LEFT=1,0 RIGHT=1,2 A=3,3 B=3,2 START=0,0 SELECT=0,3"
# PICOGAME_MATRIX_ANODES = "cols"   # flip to "rows" if the diode direction is reversed
```

**USB gamepad / keyboard** — `PICOGAME_USBPAD` / `PICOGAME_USBKBD` (see the USB sections below).

A partial map merges over the source's defaults, so you only name the buttons you're changing. Unmapped
logical buttons stay inactive (`btn.has(...)` reports them absent).

## USB gamepad (USB-host boards, e.g. Fruit Jam)

On a USB-host CircuitPython build, `Buttons()` **auto-attaches** a plugged-in USB HID gamepad — so a
pad works with **zero game changes**. On boards without USB host (PicoPad, …) the driver is simply
never loaded (no RAM cost).

- Default layout = the ubiquitous DragonRise `081f:e401` SNES-style pad.
- Remap any pad from `settings.toml` (no reflash):
  `PICOGAME_USBPAD = "A=5:0x20 B=5:0x40 X=5:0x10 Y=5:0x80 START=6:0x20 SELECT=6:0x10"`
  (`NAME=report-byte:bitmask`; a partial list merges over the defaults). Discover a new pad's report
  bytes with `tools/usbpad_probe.py`, or run the interactive `tools/usbpad_calibrate.py` — it prompts
  you to press each button and prints the ready-to-paste `PICOGAME_USBPAD` / `PICOGAME_USBPAD_ID` line.
- Turn it off with `PICOGAME_USB = 0`; pin a specific device with `PICOGAME_USBPAD_ID = "vid:pid"`.

The driver is `picogame_usbpad.UsbPad`; you rarely touch it directly — `Buttons` attaches it for you.

## USB keyboard (USB-host boards)

The keyboard twin of the gamepad — also auto-attached, also OR'd in. Works with wired keyboards and
2.4 GHz-dongle wireless ones (not Bluetooth — CircuitPython has no BT host stack).

- Default layout: **arrows + WASD** → D-pad, **Z / Space** → A, **X** → B, **C** → X, **V** → Y,
  **Q** → L1, **E** → R1, **Enter** → START, **Esc** → SELECT.
- Remap from `settings.toml`: `PICOGAME_USBKBD = "A=0x2C B=0x1B START=0x28"` (`NAME=HID-keycode`,
  hex or decimal; merges over the defaults).
- Disable the keyboard only (keep the pad) with `PICOGAME_KBD = 0`.
- Some combo dongles present a boot-keyboard interface that stays silent while keystrokes flow on a
  sibling interface. Point the driver at the live channel:
  `PICOGAME_USBKBD_EP = "2:0x83"` (`interface:IN-endpoint`). Find the value by running
  `tools/usbkbd_probe.py` as `code.py` — it prints the exact line.

The driver is `picogame_usbkbd.UsbKbd`.

## I2C gamepad (any board with I2C, incl. the PicoPad)

The third pad family: "dumb" I2C button boards — GPIO expanders (TCA9555, PCF8574, MCP23017) and the
vendor pads built on them, such as the Pimoroni QwSTPad. **No USB host needed**, so this is how a
PicoPad or a bare Pico gets an external controller. One driver plus a declarative recipe covers the
whole family — the same philosophy as the USB pad, not a library per device.

Unlike USB, it is **opt-in**: an expander has no identity register, so probing addresses could bind an
unrelated device on your bus. Name the pad in `settings.toml` and `Buttons()` ORs it in like any other
source, with no game changes:

```toml
PICOGAME_I2CPAD = "qwstpad"                  # a preset at its default address
# PICOGAME_I2CPAD = "qwstpad@0x23"           # a preset at a specific address
# PICOGAME_I2CPAD = "qwstpad;qwstpad@0x23"   # several pads = local multiplayer
# PICOGAME_I2C = "GP4,GP5"                   # SDA,SCL — bare boards only; a STEMMA/Qw-ST
#                                            #  connector needs nothing. One token names a
#                                            #  board bus instead: PICOGAME_I2C = "I2C0"
```

An unknown device is one line, no code — a **recipe** of space-separated tokens:

```toml
PICOGAME_I2CPAD = "addr=0x20 read=:1 inv=1 UP=0 DOWN=1 LEFT=2 RIGHT=3 A=4 B=5"
```

- `addr=0x21` — the I2C address.
- `read=00:2` — one poll: write register byte `00`, read 2 bytes. `read=:1` reads without a register
  (PCF8574 style).
- `init=063FF9,0206C0` — raw hex frames written once at attach (register + payload, verbatim).
- `inv=1` — buttons are active-low in the RAW read; omit it when the device already reports a press
  as 1.
- `UP=1 A=14 …` — logical button = bit index into the bytes read, little-endian
  (`byte_index * 8 + bit_in_byte`). Names are the ones `PICOGAME_BUTTONS` uses.

A poll is one short transaction, about half a millisecond at 100 kHz. A failed poll (loose cable)
holds the last state and reports everything released after eight misses, so a disconnect cannot stick
a button down. The bus is also clocked free after a soft reload, which is what otherwise leaves an
expander mid-transaction.

The driver is `picogame_i2cpad`; `Buttons` attaches it for you. Reach for it directly only to build a
pad by hand (`I2CPad`) or to enumerate pads for multiplayer (`find_pads`, below).

:::tip[Set `PICOGAME_DEBUG = 1` when input doesn't attach]
It prints `[picogame] ...` reasons to the serial console (driver missing, device not found, wrong
endpoint) instead of failing silently. Remove it once things work.
:::

## Local multiplayer

By default a `Buttons` merges every source (above). To give each player their own controller, build
**one `Buttons` per player** and bind each to its own device with `sources=`:

```python
import picogame_input as pi

pads = pi.find_pads()                  # every connected USB gamepad, in bus order
p1 = pi.Buttons(sources=pads[0:1])     # player 1 = first pad
p2 = pi.Buttons(sources=pads[1:2])     # player 2 = second pad
# or mix devices — pi.Buttons(usb=False) is a player on the on-board buttons.
```

`picogame_i2cpad.find_pads()` is the I2C twin — every pad of a preset on the bus, in address
order, and each one lights its player-number LED. A QwSTPad preset covers four addresses, so four
players work on a board with no USB host at all:

```python
import picogame_i2cpad as i2c
pads = i2c.find_pads("qwstpad")        # up to four, in address order
p1 = pi.Buttons(sources=pads[0:1])
```

Each player is independent: poll and read them separately (`p1.just_pressed(pi.A)` /
`p2.just_pressed(pi.A)`). `pi.find_pads()` returns `[]` on a board with no USB host, and
`i2c.find_pads()` returns `[]` when no pad answers on the bus. Two identical pads
come back in enumeration order — if players want them the other way round, they swap controllers (the
engine tracks no per-pad identity). See the two-player pattern above.

See the [full `settings.toml` reference](/custom-board/) for every input key and its format.
