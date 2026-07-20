# picogame input: a board's buttons -> a bitmask + edge detection, so games don't redo the wiring.
# Backend is chosen automatically per board: the CircuitPython `keypad` module (hardware debounce +
# an event queue -> no missed taps) where present, else digitalio polling. Same API either way.
#
# Games use LOGICAL button names; the physical pin map is a *profile*, resolved (highest wins):
#   1. an explicit profile passed to Buttons(profile=...)
#   2. settings.toml on CIRCUITPY - `PICOGAME_BUTTONS = "UP=GP2 DOWN=GP3 A=GP12 ..."` (no reflash;
#      this is how a bare/custom Pico with your own wiring remaps everything), `PICOGAME_PULL="up"`
#   3. a built-in profile selected by `board.board_id` (PicoPad etc. -> zero config)
#   4. fallback to PICOPAD
# Absent buttons (a board without shoulders) simply never fire; query with `btns.has(btns.L1)`.
#
#   btns = picogame_input.Buttons()                      # auto profile by board
#   while True:
#       btns.poll()
#       if btns.is_pressed(btns.LEFT): ...
#       if btns.just_pressed(btns.A): ...                 # rising edge
#
# A profile is a sequence of (pin, bit): `pin` is a board attribute NAME (looked up on `board`, or
# resolved via microcontroller.pin for a bare "GPn") or an actual pin object. Missing pins skipped.

import board
import os

import digitalio
from micropython import const

# Logical buttons - a SUPERSET; a board maps the subset it has.
UP, DOWN, LEFT, RIGHT, A, B, X, Y = (1 << i for i in range(8))
L1, L2, R1, R2, START, SELECT = (1 << i for i in range(8, 14))
_NBITS = const(14)
# NOT const(): the Buttons class body below re-exports `ALL` as a class attribute (the
# `L1, ..., ALL = L1, ..., ALL` line), and assigning to a const-declared name is a compile error
# under mpy-cross ("can't assign to expression") - even though CPython/the sim tolerate it.
ALL = (1 << _NBITS) - 1

# name -> mask, for parsing the settings.toml PICOGAME_BUTTONS string
NAMES = {"UP": UP, "DOWN": DOWN, "LEFT": LEFT, "RIGHT": RIGHT, "A": A, "B": B, "X": X, "Y": Y,
         "L1": L1, "L2": L2, "R1": R1, "R2": R2, "START": START, "SELECT": SELECT}

# Built-in per-board profiles (active-low + a pull). A profile is a sequence of
# (board-attribute-name, button-bit): the name is looked up on `board` (or microcontroller.pin
# for a bare 'GPn') -- so each entry below doubles as a worked example of the format you'd pass
# as Buttons(profile=...) or write into settings.toml on a board we don't list yet.
PICOPAD = (                                   # PicoPad: face buttons on board.SW_*
    ("SW_UP", UP), ("SW_DOWN", DOWN), ("SW_LEFT", LEFT), ("SW_RIGHT", RIGHT),
    ("SW_A", A), ("SW_B", B), ("SW_X", X), ("SW_Y", Y),
)
# uGame-style boards (Radomir Dopieralski): D-pad + face buttons O / X / Z.
# Logical A = the primary-action "O" button; B = "X"; the third "Z" -> logical X.
UGAME = (
    ("BUTTON_UP", UP), ("BUTTON_DOWN", DOWN), ("BUTTON_LEFT", LEFT), ("BUTTON_RIGHT", RIGHT),
    ("BUTTON_O", A), ("BUTTON_X", B), ("BUTTON_Z", X),
)
THUMBY_COLOR = (                              # D-pad + A/B + two bumpers (->X/Y) + menu (->START)
    ("BUTTON_UP", UP), ("BUTTON_DOWN", DOWN), ("BUTTON_LEFT", LEFT), ("BUTTON_RIGHT", RIGHT),
    ("BUTTON_A", A), ("BUTTON_B", B),
    ("BUTTON_BUMPER_LEFT", X), ("BUTTON_BUMPER_RIGHT", Y), ("BUTTON_MENU", START),
)
PROFILES = {                                  # add new boards here, keyed by board.board_id
    "pajenicko_picopad_game": PICOPAD,
    "pimoroni_picosystem": PICOPAD,           # exposes the same board.SW_* names as the PicoPad
    "ugame22": UGAME,
    "deshipu_ugame_s3": UGAME,
    "tinycircuits_thumby_color": THUMBY_COLOR,
    # VIDI X (vidi_x): the D-pad is an analog ladder -- board.BTN_L_R / BTN_UP_DOWN are one ADC pin
    # per axis, which the digital (pin -> button) model can't decode -> no built-in profile.
}


def _resolve_pin(name_or_obj):
    """A profile pin: an actual Pin object, a board attribute name, or a bare 'GPn' (microcontroller)."""
    if not isinstance(name_or_obj, str):
        return name_or_obj
    pin = getattr(board, name_or_obj, None)
    if pin is None:
        try:
            import microcontroller
            pin = getattr(microcontroller.pin, name_or_obj, None)
        except ImportError:
            pin = None
    return pin


def _profile_from_settings():
    """Build a profile from settings.toml `PICOGAME_BUTTONS = "UP=GP2 A=GP12 ..."`, or None if unset."""
    s = os.getenv("PICOGAME_BUTTONS")
    if not s:
        return None
    prof = []
    for tok in s.replace(",", " ").split():
        if "=" in tok:
            nm, pin = tok.split("=", 1)
            m = NAMES.get(nm.strip().upper())
            if m:
                prof.append((pin.strip(), m))
    return prof or None


def _matrix_from_settings():
    """Build a matrix config from settings.toml, or None if unset. Three keys (values are strings,
    which is all CircuitPython's os.getenv returns):
        PICOGAME_MATRIX_ROWS = "GP0 GP1 GP2 GP3"      # row pins (space/comma separated)
        PICOGAME_MATRIX_COLS = "GP4 GP5 GP6 GP7"      # column pins
        PICOGAME_MATRIX_MAP  = "UP=1,2 DOWN=2,2 LEFT=2,1 RIGHT=2,3 A=3,5 B=3,4 START=0,0"
                                                      # NAME=row,col  (or NAME=key_number); space-separated
        PICOGAME_MATRIX_ANODES = "cols"               # optional: "cols" (default) or "rows" (diode dir)
    Only the listed keys map to game buttons; every other key on the QWERTY is ignored."""
    rows = os.getenv("PICOGAME_MATRIX_ROWS")
    cols = os.getenv("PICOGAME_MATRIX_COLS")
    mp = os.getenv("PICOGAME_MATRIX_MAP")
    if not (rows and cols and mp):
        return None
    keymap = {}
    for tok in mp.split():                            # space-separated; comma is the row,col inside a token
        if "=" not in tok:
            continue
        nm, key = tok.split("=", 1)
        bit = NAMES.get(nm.strip().upper())
        if not bit:
            continue
        key = key.strip()
        try:                                          # skip malformed key specs, like _profile_from_settings
            if "," in key:
                r, c = key.split(",", 1)
                keymap[(int(r), int(c))] = bit
            else:
                keymap[int(key)] = bit
        except ValueError:
            continue
    if not keymap:
        return None
    anodes = (os.getenv("PICOGAME_MATRIX_ANODES") or "cols").strip().lower()
    return {"rows": rows.replace(",", " ").split(), "cols": cols.replace(",", " ").split(),
            "map": keymap, "cols_to_anodes": anodes != "rows"}


class Buttons:
    # expose the constants as attributes too (btns.LEFT etc.)
    UP, DOWN, LEFT, RIGHT, A, B, X, Y = UP, DOWN, LEFT, RIGHT, A, B, X, Y
    L1, L2, R1, R2, START, SELECT, ALL = L1, L2, R1, R2, START, SELECT, ALL

    def __init__(self, profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None,
                 usb=None):
        # `matrix` = drive a scanned ROW x COLUMN key matrix (e.g. a QWERTY) instead of one-pin-per-
        # button; map only the keys you want onto game buttons, the rest are ignored. Pass:
        #   matrix={"rows": [pin/name, ...], "cols": [pin/name, ...],
        #           "map": {key_number OR (row,col): BIT or "UP"/"A"/..., ...},
        #           "cols_to_anodes": True}         # optional; flip if the diode direction is reversed
        # key_number = row*len(cols)+col. Everything above (is_pressed/just_pressed/repeat, all games)
        # is unchanged - a mapped key IS that game button. (Discover key_numbers with a keypad.KeyMatrix
        # scan sketch first; layouts vary.) See NAMES for the button vocabulary. Can also be set
        # entirely from settings.toml (PICOGAME_MATRIX_ROWS/COLS/MAP) - see _matrix_from_settings.
        # Extra button SOURCES (each an object with .read() -> logical bitmask; Buttons ORs them into
        # self.state every poll). A USB HID gamepad is auto-attached here on USB-host boards; see
        # _attach_usb / picogame_usbpad. self._hw holds the keypad backend's own level accumulator so
        # source bits never corrupt it.
        self._sources = []
        self._hw = 0
        self._flush = False
        if matrix is None:
            matrix = _matrix_from_settings()
        if matrix is not None:
            self._init_matrix(matrix, debounce_s)
            self._attach_usb(usb)
            return
        # Backend is chosen automatically: the CircuitPython `keypad` module (hardware debounce +
        # background scan + an event queue, so quick taps are never missed) where available, else
        # raw digitalio polling. `debounce_s` is the keypad debounce/scan window in seconds (its
        # `interval`); raise it for a noisy switch, lower it for snappier response. The polling path
        # is UNDEBOUNCED - per-frame sampling already filters bounce shorter than a frame (a
        # mechanical switch settles in <1 frame at 30-60 fps); for a noisy switch on a keypad-less
        # build, wrap pins in the separate `adafruit_debouncer` upstream. prefer_keypad=False forces
        # polling.
        if profile is None:                              # resolve: settings.toml -> board_id -> PicoPad
            profile = _profile_from_settings() or PROFILES.get(getattr(board, "board_id", None), PICOPAD)
        if pull is None:
            p = os.getenv("PICOGAME_PULL")
            pull = digitalio.Pull.DOWN if (p and p.lower() == "down") else digitalio.Pull.UP
        pins = []
        self._bits = []
        self._mapped = 0                                 # which buttons this board actually wires
        for pin_or_name, bit in profile:
            pin = _resolve_pin(pin_or_name)
            if pin is None:
                continue
            pins.append(pin)
            self._bits.append(bit)
            self._mapped |= bit
        self.state = 0
        self.prev = 0
        self._pressed = 0
        self._released = 0
        self._hold = [0] * _NBITS                         # per-button held-frame counts (for repeat)
        self._keys = None
        if prefer_keypad:
            try:
                import keypad
                self._keys = keypad.Keys(pins, value_when_pressed=(pull is digitalio.Pull.DOWN),
                                         pull=True, interval=debounce_s)
                self._ev = keypad.Event()                 # reused (no per-event alloc)
            except (ImportError, ValueError):
                self._keys = None
        if self._keys is None:                            # digitalio polling backend
            self._active_low = pull is not digitalio.Pull.DOWN
            self._ios = []
            for pin in pins:
                io = digitalio.DigitalInOut(pin)
                io.switch_to_input(pull=pull)
                self._ios.append(io)
            self._pairs = list(zip(self._ios, self._bits))  # pre-zipped (no per-frame zip alloc)
        self._attach_usb(usb)

    def _attach_usb(self, usb):
        """Try to attach a USB HID gamepad as an extra source, unless disabled. `usb=False` off;
        `usb=None` (default) = auto (attach only on a CircuitPython USB-host build, unless settings.toml
        sets PICOGAME_USB=0); `usb=True` = force (also on the CPython sim, for deliberate testing - still
        no-ops if no pad/driver). Silent on every failure (no usb.core, no pad plugged in, driver not
        copied) so games run unchanged on any board."""
        if usb is False:
            return
        if usb is None:
            import sys
            # auto mode: never grab real host USB in the CPython sim just because PyUSB happens to be
            # installed - only a genuine CircuitPython USB-host build should auto-attach.
            if getattr(sys.implementation, "name", "") != "circuitpython":
                return
            if os.getenv("PICOGAME_USB", "1") == "0":
                return
        try:
            import usb.core            # only on a USB-host build; gate BEFORE importing picogame_usbpad
        except ImportError:            # (so a non-USB board never caches the unused pad module - RP2040 RAM)
            return
        try:
            import picogame_usbpad
            pad = picogame_usbpad.UsbPad()
            self._sources.append(pad)
            self._mapped |= pad.mapped       # has() now reports the pad's actually-mapped buttons
        except Exception as e:
            import picogame_debug
            picogame_debug.note("input: USB gamepad not attached ->", repr(e))

    def _init_matrix(self, m, debounce_s):
        """Row x column matrix backend (keypad.KeyMatrix). Same Event queue as keypad.Keys, so poll()
        and everything above are unchanged; self._bits is indexed by key_number (0 = unmapped)."""
        import keypad
        self.state = 0
        self.prev = 0
        self._pressed = 0
        self._released = 0
        self._hold = [0] * _NBITS
        rows = [_resolve_pin(p) for p in m["rows"]]
        cols = [_resolve_pin(p) for p in m["cols"]]
        if not rows or not cols or None in rows or None in cols:      # clear error, not a late KeyMatrix fault
            raise ValueError("picogame matrix: empty or unresolved row/column pins")
        ncols = len(cols)
        n = len(rows) * ncols
        self._bits = [0] * n                             # index = key_number; 0 = unmapped -> ignored
        self._mapped = 0
        for k, v in m["map"].items():
            if isinstance(k, int):
                kn = k
            elif 0 <= k[0] < len(rows) and 0 <= k[1] < ncols:         # validate row/col per-axis (no aliasing)
                kn = k[0] * ncols + k[1]
            else:
                continue                                 # out-of-range (row, col) -> skip, don't alias
            if 0 <= kn < n:
                bit = v if isinstance(v, int) else NAMES[v]
                self._bits[kn] = bit
                self._mapped |= bit
        self._keys = keypad.KeyMatrix(rows, cols,
                                      columns_to_anodes=m.get("cols_to_anodes", True),
                                      interval=debounce_s)
        self._ev = keypad.Event()

    def poll(self):
        """Sample all buttons once; returns the current pressed bitmask."""
        self.prev = self.state
        if self._keys is not None:                       # --- keypad backend: drain the event queue ---
            self._pressed = 0
            self._released = 0
            q = self._keys.events
            ev = self._ev
            while q.get_into(ev):
                bit = self._bits[ev.key_number]
                if ev.pressed:
                    self._hw |= bit
                    self._pressed |= bit
                else:
                    self._hw &= ~bit
                    self._released |= bit
        else:                                            # --- digitalio polling backend (raw) ---
            raw = 0
            active_low = self._active_low
            for io, bit in self._pairs:
                if ((not io.value) if active_low else io.value):
                    raw |= bit
            self._hw = raw
        # merge extra sources (USB gamepad, ...) - each holds its own mask, Buttons is the OR
        s = self._hw
        for src in self._sources:
            s |= src.read()
        self.state = s
        if self._flush:                      # first poll after clear(): consume this frame's edges so a
            self.prev = self.state           # button HELD across the transition doesn't read as a fresh
            self._pressed = self._released = 0   # press (matters for USB sources, which keep holding it)
            self._flush = False
        # track held-frame counts (for repeat())
        h = self._hold
        s = self.state
        i = 0
        b = 1
        limit = 1 << _NBITS
        while b < limit:
            h[i] = h[i] + 1 if (s & b) else 0
            i += 1
            b <<= 1
        return self.state

    def is_pressed(self, mask=ALL):
        return bool(self.state & mask)

    def just_pressed(self, mask=ALL):
        # With extra sources (USB pad) attached: edges come from the COMBINED level diff only. A source
        # and the keypad can hold the SAME logical bit, so mixing in the keypad's own queue edge would
        # falsely fire a press/release the other source doesn't agree with (e.g. a release while the pad
        # still holds it). No sources: use the keypad queue (catches sub-frame taps the diff would miss),
        # else the polling level diff.
        if self._sources:
            edge = self.state & ~self.prev
        elif self._keys is not None:
            edge = self._pressed
        else:
            edge = self.state & ~self.prev
        return bool(edge & mask)

    def just_released(self, mask=ALL):
        if self._sources:
            edge = ~self.state & self.prev
        elif self._keys is not None:
            edge = self._released
        else:
            edge = ~self.state & self.prev
        return bool(edge & mask)

    def has(self, mask=ALL):
        """True if the active profile actually maps (this board physically has) the given button(s).
        Lets a game adapt its controls/UI to boards without shoulders, START/SELECT, etc."""
        return bool(self._mapped & mask)

    def repeat(self, button, delay=15, interval=4):
        """Auto-repeat for a SINGLE button: True the frame it's pressed, then every `interval`
        frames once it's been held `delay` frames. Great for menu / grid movement."""
        b = button; i = 0           # bit index of the mask (int.bit_length isn't in MicroPython-WASM)
        while b > 1:
            b >>= 1; i += 1
        c = self._hold[i]
        if c == 1:
            return True
        return c > delay and (c - delay) % interval == 0

    def clear(self):
        """Reset state + flush pending input (call on scene/menu transitions)."""
        if self._keys is not None:
            self._keys.events.clear()
        # _hw is the keypad/polling level accumulator (separate from state since sources were added) -
        # zero it too, or a held key's level would OR straight back into state on the next poll.
        self.state = self.prev = self._pressed = self._released = self._hw = 0
        self._flush = True                   # suppress edges on the next poll (a still-held source
        #                                      button must not re-fire as a fresh press after clear)
        for i in range(_NBITS):
            self._hold[i] = 0


class Timer:
    """A decaying frame timer for INPUT LENIENCY - the small forgiveness windows that make
    action games feel fair (see the difficulty / game-feel research): coyote time and jump
    buffering. Call once per frame.

    Coyote time (let the player jump a few frames after walking off a ledge):
        coyote = Timer(6)
        coyote.feed(on_ground)            # refresh while grounded, else decay
        if want_jump and coyote.is_active: jump()

    Jump buffer (honour a jump pressed just before landing):
        jbuf = Timer(5)
        jbuf.feed(buttons.just_pressed(buttons.A))
        if on_ground and jbuf.consume(): jump()   # consume() = use it once
    """

    def __init__(self, frames):
        self.frames = frames
        self.t = 0

    def feed(self, condition):
        """Recharge to full when `condition` is true, else count down one frame."""
        if condition:
            self.t = self.frames
        elif self.t > 0:
            self.t -= 1
        return self.t > 0

    def charge(self):
        self.t = self.frames

    @property
    def is_active(self):
        return self.t > 0

    def consume(self):
        """True once if currently active, then clears it (a buffered press fires once)."""
        if self.t > 0:
            self.t = 0
            return True
        return False
