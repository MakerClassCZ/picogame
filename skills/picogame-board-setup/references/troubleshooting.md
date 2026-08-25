# picogame hardware troubleshooting

Symptom → cause → fix. **Before anything else, rule out the stale-`.mpy` footgun:** if a fix "doesn't
take", the device is almost certainly importing an old `picogame_*.mpy` in `/lib` that shadows the `.py`.
Redeploy the whole current `.mpy` bundle and DELETE every old `picogame_*.mpy` first, then retest.

---

## Display

**Colours look photo-negative (whites are black, etc.)**
Panel inversion polarity is wrong. ST7789 panels ship in both polarities. → `PICOGAME_INVERT = 1` (or
`0`) in settings.toml. On a code-built display (bare board), pass/flip the driver's `invert=` instead.

**Colours are wrong-hue / red↔blue swapped**
BGR vs RGB panel order. → `PICOGAME_MADCTL = 0x68` (the BGR variant of PicoPad's `0x60`). For a
code-built display, set the driver's `bgr=`/`colstart` accordingly.

**Subtle gradients band or hue-wobble (looks fine in the sim, wrong on the panel)**
The real ST7789 is 16-bit RGB565, not the sim's truecolour: build colours 565-aligned (R/B in steps of
8, G in steps of 4, kept monotonic) via `pg.rgb565(r,g,b)`. Dither is a stipple, not alpha — dithered
fills read as blocks on hardware; mute + sparsen them or use a ring. (This is a game-art fix, not settings.)

**Image is upside-down / mirrored / 90° off**
Orientation. On a busdisplay board: `PICOGAME_MADCTL` — `0xA0` = 180°, `0x68` = mirrored/BGR, `0xA8` =
both (PicoPad baseline `0x60`). On a code-built display: the driver's `rotation=` (0/90/180/270) and
`rowstart`/`colstart`. A framebuffer/DVI board (Fruit Jam) has no MADCTL — picogame REQUIRES rotation 0
there; set `CIRCUITPY_DISPLAY_ROTATION = 0` (it can't run at other rotations, and a rebuild won't add them).

**Framebuffer/DVI board: `no display found` or `picogame needs rotation 0` / `needs a 16-bit framebuffer`**
The DVI mode isn't set up the way picogame needs. In settings.toml: `CIRCUITPY_PICODVI_ENABLE = "always"`
(construct the display at boot), `CIRCUITPY_DISPLAY_ROTATION = 0`, `CIRCUITPY_DISPLAY_COLOR_DEPTH = 16`.

**`TypeError: expected a BusDisplay`** (usually in a HUD/label/cutscene draw)
The game handed a framebuffer board's display object (a `FramebufferDisplay`, reached through
`supervisor.runtime.display` — a DVI board like the Fruit Jam has no `board.DISPLAY` at all) straight
to `pg.render`.
Current libs normalize this centrally (picogame_ui/font/game/cutscene via `picogame_game.target`) — so
the fix is: **update to the current lib bundle**. If you're writing new immediate-render code, pass
`scene.display` (the resolved backend) or wrap with `picogame_game.target(picogame_game.display())`.

**Nothing on screen at all (bare board)**
Nothing published a display: `picogame_game` looks for `supervisor.runtime.display` (the board's
firmware sets it, or boot.py / a launcher does) and found none — the error text says so and names the
two fixes. On a DVI board that usually means `CIRCUITPY_PICODVI_ENABLE = "always"` is missing from
settings.toml (and boot.py runs only at power-on: after adding one, press RESET). On a bare board,
build the display in `code.py`, publish it with `supervisor.runtime.display = disp` and hand it to
`picogame_game.setup(display=...)` —
see `templates/bare_pico_code.py` + `templates/display_test.py` to confirm the SPI pins/driver first.

## Buttons

**No button does anything**
Wrong pull or the buttons aren't in the active profile. → Run `templates/wiring_probe.py`: confirm each
pin actually toggles, and whether pressed reads LOW (`PICOGAME_PULL = "up"`, default) or HIGH
(`"down"`). Then write the exact pins into `PICOGAME_BUTTONS`. A bare Pico has no `board_id` profile —
it falls back to the PicoPad `SW_*` names, none of which resolve on a Pico → you MUST set `PICOGAME_BUTTONS`.

**Some buttons work, others are dead or swapped**
The `PICOGAME_BUTTONS` map has the wrong pin for those names. → Re-run the probe, press the mislabeled
buttons, fix those `NAME=PIN` tokens. For a matrix, check `PICOGAME_MATRIX_ANODES` (diode direction) and
the `row,col` in `PICOGAME_MATRIX_MAP`.

**A held button repeats / sticks after a menu transition**
Call `btns.clear()` on the transition (it flushes queued events + the level accumulator). If it still
sticks, the device has a stale `picogame_input.mpy` (see the footgun at top).

**USB gamepad ignored (Fruit Jam)**
Pad must be in the USB-HOST port (not the CIRCUITPY data port). Check it's a supported layout with the
USB probe; a non-DragonRise pad needs `PICOGAME_USBPAD` remap. `PICOGAME_USB = 0` disables the pad.
Auto-attach only happens on a CircuitPython USB-host build (the sim won't grab it).

## Audio

**No sound at all, `Audio FAILED` / `Synth available = False`**
Set `PICOGAME_DEBUG = 1` (the general debug switch) and read the `[picogame] ...` reason on serial. Note
the two audio paths differ: `picogame_synth`/`_sfx`
SWALLOW init errors to run silent (this flag unmasks them), but `picogame_audio.Audio()` RAISES — if the
game wraps `Audio()` in try/except (the usual pattern), that hides the real error; read the traceback
with the wrap temporarily removed. Common causes:
- **I2S (Fruit Jam):** the `adafruit_tlv320` + `adafruit_bus_device` drivers are missing from `/lib`
  (they are NOT bundled — install from the Adafruit bundle / `circup install adafruit_tlv320`). Without
  them I2S silently falls back to PWM, and a DVI board has no PWM pin → fail.
- **Stale `picogame_audio.mpy`** (pre-I2S) shadowing the current `.py` — tell-tale error mentions
  `no PWM audio pin ... board.GP15`, a message not in current source. Redeploy the bundle.
- **PWM board:** no audio pin found → set `PICOGAME_AUDIO = "GPnn"`.

**Sound plays but is very quiet**
The TLV320 DAC's `*_output = True` defaults are deliberately near-silent (`headphone_volume` ≈ -30 dB).
→ raise `PICOGAME_HP_VOLUME` toward 0 (default now `-10`; try `-6`), and/or `PICOGAME_DAC_VOLUME`
(keep ≤ 0). Speaker: `PICOGAME_SPK_VOLUME`. (`0 dB` headphone = line level — don't exceed ~`-3`.)

**Sim is silent**
Expected — synthio is device-only, the desktop sim has no audio. Preview `picogame_synth` SFX by
rendering to WAV (`tools/synth_preview.py`), don't judge sound in the sim.

## Memory / crashes

**`MemoryError` on the device (often mid-game or during audio init)**
RP2040 has ~25-40 KB free heap (shared with synthio); fragmentation, not just totals, kills you. Prefer
0-RAM paths (StripDraw, Tilemap) over a full-screen Canvas; use a fixed `picogame_pool.Pool` instead of
per-frame sprite creation; keep the moving-object count low. Audio init failing under memory pressure
shows as silent audio (`available = False`) — free RAM before creating the Synth, or lower its
`buffer_size`. A grow-realloc on a fragmented heap (e.g. a growing label) is a classic trigger — reserve
buffers up front.

**`random.shuffle` / `random.sample` works in the sim, `AttributeError` on device**
CircuitPython's `random` has no `shuffle`/`sample`. Use Fisher-Yates via `randint`. (Game-code fix.)

**Syntax the sim accepts but the device rejects**
The CPython sim is more permissive than MicroPython (e.g. `*unpack` in a tuple display). Gate device
code with `mpy-cross`, not just the sim.
