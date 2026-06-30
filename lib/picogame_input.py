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


class Buttons:
    # expose the constants as attributes too (btns.LEFT etc.)
    UP, DOWN, LEFT, RIGHT, A, B, X, Y = UP, DOWN, LEFT, RIGHT, A, B, X, Y
    L1, L2, R1, R2, START, SELECT, ALL = L1, L2, R1, R2, START, SELECT, ALL

    def __init__(self, profile=None, pull=None, prefer_keypad=True, debounce_s=0.02):
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
                    self.state |= bit
                    self._pressed |= bit
                else:
                    self.state &= ~bit
                    self._released |= bit
        else:                                            # --- digitalio polling backend (raw) ---
            raw = 0
            active_low = self._active_low
            for io, bit in self._pairs:
                if ((not io.value) if active_low else io.value):
                    raw |= bit
            self.state = raw
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
        # keypad backend reports edges from the event queue (catches sub-frame taps); the polling
        # backend diffs held state across frames.
        edge = self._pressed if self._keys is not None else (self.state & ~self.prev)
        return bool(edge & mask)

    def just_released(self, mask=ALL):
        edge = self._released if self._keys is not None else (~self.state & self.prev)
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
        self.state = self.prev = self._pressed = self._released = 0
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
