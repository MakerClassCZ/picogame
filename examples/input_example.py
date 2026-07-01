# picogame HW test — a bring-up / debugging aid for custom hardware.
#
# Drop this on the board as code.py. It:
#   * prints to the serial console what the engine detected about the board
#     (board_id, display size, which buttons the active profile maps, audio),
#   * draws the D-pad as four squares in a cross + the A/B face buttons with X/Y
#     above them; each square lights up while its button is held,
#   * beeps on every press.
# Use it to check wiring + the button profile on a freshly built board.
#
# Works with no changes on a PicoPad (board.DISPLAY + the built-in profile). On a
# bare Pico wired like the PicoPad it builds the ST7789 itself and reads the button
# map from settings.toml (PICOGAME_BUTTONS) — see the "Supported hardware" docs.
import board
import picogame as pg
import picogame_game
import picogame_input

# --- display: use board.DISPLAY if the board has one, else build a PicoPad-clone ST7789 ---
display = getattr(board, "DISPLAY", None)
built_display = False
if display is None:
    try:
        import displayio
        from fourwire import FourWire
        from adafruit_st7789 import ST7789
        import busio
        displayio.release_displays()
        spi = busio.SPI(clock=board.GP18, MOSI=board.GP19)
        bus = FourWire(spi, command=board.GP17, chip_select=board.GP21, reset=board.GP20)
        display = ST7789(bus, width=320, height=240, rotation=0, backlight_pin=board.GP16)
        built_display = True
    except Exception as e:                       # noqa: BLE001 — bring-up aid: report and stop
        raise SystemExit("No board.DISPLAY and could not build one: %r\n"
                         "Wire a display (see the Supported hardware docs) or pass one to setup()." % e)

scene, _a, _b = picogame_game.setup(display=display, background=pg.rgb565(16, 18, 26))
W = display.width
H = display.height
btn = picogame_input.Buttons()

# --- audio (optional: needs board.AUDIO or a wired PWM speaker pin) ---
audio = None
beep = None
try:
    import picogame_audio
    audio = picogame_audio.Audio()
    beep = picogame_audio.tone(660, 45)
except Exception as e:                            # noqa: BLE001
    print("audio: unavailable (%r) — buttons will still light up silently" % e)

# --- colours ---
WHITE = pg.rgb565(240, 240, 240)
DIM = pg.rgb565(60, 64, 78)         # mapped, not pressed
HOT = pg.rgb565(80, 220, 120)       # pressed
OFF = pg.rgb565(34, 36, 46)         # this board does not wire this button
BORDER = pg.rgb565(120, 128, 150)
LABEL = pg.rgb565(220, 224, 235)

# --- the eight buttons: (logical label, mask, centre x, y) computed from W/H ---
S = max(26, H // 8)                  # square size
G = S // 4                           # gap
dcx, dcy = int(W * 0.30), int(H * 0.66)    # D-pad centre
fcx, fcy = int(W * 0.74), int(H * 0.66)    # face-button centre


def _cell(cx, cy, col, row):
    return (cx + col * (S + G) - S // 2, cy + row * (S + G) - S // 2)


BUTTONS = [
    ("^", btn.UP,    _cell(dcx, dcy, 0, -1)),
    ("v", btn.DOWN,  _cell(dcx, dcy, 0,  1)),
    ("<", btn.LEFT,  _cell(dcx, dcy, -1, 0)),
    (">", btn.RIGHT, _cell(dcx, dcy, 1,  0)),
    ("X", btn.X,     (fcx - S - G // 2, fcy - S - G // 2)),   # X/Y on top
    ("Y", btn.Y,     (fcx + G // 2,     fcy - S - G // 2)),
    ("A", btn.A,     (fcx - S - G // 2, fcy + G // 2)),       # A/B below
    ("B", btn.B,     (fcx + G // 2,     fcy + G // 2)),
]

state = 0                            # current pressed mask, read by the StripDraw callback


def draw_panel(v, vx, vy, vw, vh):
    v.fill_rect(0, 0, vw, vh, pg.rgb565(16, 18, 26))         # clear this strip
    for _label, mask, (bx, by) in BUTTONS:
        if not btn.has(mask):
            fill = OFF                                       # board doesn't wire it
        elif state & mask:
            fill = HOT                                       # held
        else:
            fill = DIM                                       # idle, mapped
        v.fill_rect(bx - vx, by - vy, S, S, fill)
        v.rect(bx - vx, by - vy, S, S, BORDER)


scene.add(pg.StripDraw(draw_panel, 0, 0, W, H, always_dirty=False))  # repaint only when input changes

# --- static text: button labels centred on each square + the detection report on top ---
import terminalio
import picogame_font


def _label_sprite(text, cx, cy, color=LABEL, scale=1.0):
    bm, _w, _h = picogame_font.render_text(pg, terminalio.FONT, text, color, None)
    spr = pg.Sprite(bm, int(cx), int(cy))
    spr.anchor = (0.5, 0.5)
    if scale != 1.0:
        spr.scale = scale
    scene.add(spr)
    return spr


for label, _mask, (bx, by) in BUTTONS:
    _label_sprite(label, bx + S / 2, by + S / 2, WHITE, 1.5)

# --- detection report (serial + on screen) ---
board_id = getattr(board, "board_id", "?")
mapped = [name for name, mask, _ in
          [("UP", btn.UP, 0), ("DOWN", btn.DOWN, 0), ("LEFT", btn.LEFT, 0), ("RIGHT", btn.RIGHT, 0),
           ("A", btn.A, 0), ("B", btn.B, 0), ("X", btn.X, 0), ("Y", btn.Y, 0)]
          if btn.has(mask)]
disp_src = "built ST7789 (PicoPad pins)" if built_display else "board.DISPLAY"
audio_src = "ok" if audio else "none"

print("=" * 40)
print("picogame HW test")
print("board_id :", board_id)
print("display  : %dx%d (%s)" % (W, H, disp_src))
print("buttons  :", " ".join(mapped) if mapped else "(none mapped!)")
print("audio    :", audio_src)
print("=" * 40)
print("Press buttons — squares light up, each press beeps.")

INFO = pg.rgb565(150, 200, 255)
_label_sprite("board: %s" % board_id, W / 2, 12, INFO)
_label_sprite("display: %dx%d  audio: %s" % (W, H, audio_src), W / 2, 28, INFO)
_label_sprite("mapped: %s" % (" ".join(mapped) if mapped else "NONE"), W / 2, 44, INFO)

# --- loop ---
import picogame_clock
clock = picogame_clock.Clock(30)
prev = -1
while True:
    state = btn.poll()            # poll() returns the full pressed bitmask (is_pressed() is a bool predicate)
    if audio and btn.just_pressed(btn.ALL):
        audio.sfx(beep)
    if state != prev:             # only repaint the panel when a button changed -> idle is ~free
        prev = state
        scene.invalidate()
    scene.refresh()
    clock.tick()
