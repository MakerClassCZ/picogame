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

Each player is independent: poll and read them separately (`p1.just_pressed(pi.A)` /
`p2.just_pressed(pi.A)`). `find_pads()` returns `[]` on a board with no USB host. Two identical pads
come back in enumeration order — if players want them the other way round, they swap controllers (the
engine tracks no per-pad identity). See the two-player pattern above.

See the [full `settings.toml` reference](/custom-board/) for every input key and its format.
