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
try:
    from picogame_debug import note as _debug   # optional diagnostics (settings.toml PICOGAME_DEBUG=1)
except ImportError:                             # not deployed -> silent no-op, never a dependency
    def _debug(*args):
        pass

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
    """A profile pin: an actual Pin object, a board attribute name, or a bare 'GPn'/'GPIOn'
    (microcontroller). 'GPn' also resolves on boards without Pico-style aliases (e.g. the
    Fruit Jam), where microcontroller.pin names pins 'GPIOn'."""
    if not isinstance(name_or_obj, str):
        return name_or_obj
    pin = getattr(board, name_or_obj, None)
    if pin is None:
        try:
            import microcontroller
            pin = getattr(microcontroller.pin, name_or_obj, None)
            if pin is None and name_or_obj.startswith("GP") and not name_or_obj.startswith("GPIO"):
                pin = getattr(microcontroller.pin, "GPIO" + name_or_obj[2:], None)
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


def find_pads(vid=None, pid=None):
    """Enumerate all matching USB gamepads as UsbPad source objects, in bus order - for LOCAL
    MULTIPLAYER: hand pads[0] to player 1, pads[1] to player 2, each via Buttons(sources=[pad]).
    [] on a board with no USB host or no matching pad (VID/PID default = DragonRise or
    PICOGAME_USBPAD_ID). Two IDENTICAL pads come back in enumeration order; if the players want them
    swapped they just swap the controllers (no engine-side identity tracking - on an MCU you set the
    pads up once and a restart is cheap, so hot-swap isn't handled)."""
    out = []
    try:
        import usb.core
    except ImportError:
        return out                          # no USB stack (non-host board / sim)
    try:
        usb.core.find()                     # host-port probe: raises with no host -> no pads
    except Exception:
        return out
    import picogame_usbpad
    if not (vid or pid):
        vid, pid = picogame_usbpad._id_from_settings()
    try:
        for dev in usb.core.find(find_all=True, idVendor=vid, idProduct=pid):
            try:
                out.append(picogame_usbpad.UsbPad(dev=dev))
            except Exception:
                pass                        # a pad that fails to claim is skipped, not fatal
    except Exception:
        pass
    return out


class Buttons:
    # expose the constants as attributes too (btns.LEFT etc.)
    UP, DOWN, LEFT, RIGHT, A, B, X, Y = UP, DOWN, LEFT, RIGHT, A, B, X, Y
    L1, L2, R1, R2, START, SELECT, ALL = L1, L2, R1, R2, START, SELECT, ALL

    def __init__(self, profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None,
                 usb=None, sources=None):
        # LOCAL MULTIPLAYER: `sources=[src, ...]` makes this Buttons ONE player driven by exactly those
        # source objects (each `.read()`->logical mask) - NO board backend, NO USB auto-attach. Build one
        # Buttons per player: a pad player = Buttons(sources=[pad]) (see find_pads()); a board-buttons
        # player = Buttons(usb=False); a keyboard player = Buttons(sources=[picogame_usbkbd.UsbKbd()]).
        # Everything else (poll/is_pressed/just_pressed/repeat/clear/Timer) is unchanged per instance -
        # the game just reads p1.*/p2.* independently. `sources=None` = the classic all-in-one player.
        if sources is not None:
            self._sources = list(sources)
            self._hw = 0
            self._flush = False
            self._keys = None                # -> poll() takes the polling branch; empty _pairs = raw 0,
            self._pairs = []                 #    then it ORs the sources (the level-diff edge path fits)
            self._active_low = True
            self._bits = []
            self._mapped = 0
            for s in self._sources:
                self._mapped |= getattr(s, "mapped", ALL)
            self.state = self.prev = self._pressed = self._released = 0
            self._hold = [0] * _NBITS
            return
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
        # I2C gamepads first (independent of the `usb` gate): generic recipe-described pads
        # (presets like the Pimoroni QwSTPad, or any expander via one settings line). OPT-IN
        # via settings.toml because expanders have no identity to auto-probe safely. See
        # picogame_i2cpad for the keys (PICOGAME_I2CPAD, PICOGAME_I2C).
        spec = os.getenv("PICOGAME_I2CPAD")
        if spec and str(spec) != "0":
            try:
                import picogame_i2cpad
                for pad in picogame_i2cpad.attach(spec):
                    self._sources.append(pad)
                    self._mapped |= pad.mapped
            except Exception as e:
                _debug("input: I2C pad not attached ->", repr(e))
        if usb is False:
            return
        if usb is None:
            import sys
            # auto mode: never grab real host USB in the CPython sim just because PyUSB happens to be
            # installed - only a genuine CircuitPython USB-host build should auto-attach.
            if getattr(sys.implementation, "name", "") != "circuitpython":
                return
            if str(os.getenv("PICOGAME_USB", "1")) == "0":
                return
        try:
            import usb.core            # only on a USB-host build; gate BEFORE importing picogame_usbpad
        except ImportError:            # (so a non-USB board never caches the unused pad module - RP2040 RAM)
            return
        # The universal firmware ships usb.core even on boards with NO USB HOST PORT (PicoPad
        # RP2040/RP2350 - host is a Fruit Jam thing). Probe once: no host port is an EXPECTED
        # condition on those boards, so skip ALL USB silently (not even a debug note - it's not a
        # failure). Only a board with a real host port falls through to attach pad/keyboard.
        try:
            usb.core.find()           # raises "No usb host port initialized" when there's no host
        except Exception:
            return
        try:
            import picogame_usbpad
            pad = picogame_usbpad.UsbPad()
            self._sources.append(pad)
            self._mapped |= pad.mapped       # has() now reports the pad's actually-mapped buttons
        except Exception as e:
            _debug("input: USB gamepad not attached ->", repr(e))
        if str(os.getenv("PICOGAME_KBD", "1")) == "0":
            return
        try:
            # a USB HID keyboard (wired, or wireless via a 2.4 GHz dongle) is one more
            # OR'd source: arrows/WASD = D-pad, Z/Space = A, ... (see picogame_usbkbd)
            import picogame_usbkbd
            kbd = picogame_usbkbd.UsbKbd()
            self._sources.append(kbd)
            self._mapped |= kbd.mapped
        except Exception as e:
            _debug("input: USB keyboard not attached ->", repr(e))

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
            h = self._hold                   # pre-seed held bits so the loop below lands on 2, not 1 -
            i = 0                            # repeat()'s first-press edge must not fire either (a menu
            b = 1                            # opened by a held button would move its cursor one step)
            while b < (1 << _NBITS):
                if s & b:
                    h[i] = 1
                i += 1
                b <<= 1
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

    def attach(self, source):
        """OR another input source (an object with .read() -> logical mask) into this
        Buttons - e.g. a `picogame_seq.Script` for an attract-mode demo, or a late USB pad.
        The source's presses merge with the hardware's on the next poll(). NOTE: while any
        source is attached, just_pressed() reads edges from the combined LEVEL diff instead of
        the keypad event queue, so a sub-frame HUMAN tap (down and up between two polls) can be
        missed - for an attract-mode exit that only means pressing again; don't attach sources
        in a game where sub-frame taps matter."""
        if source not in self._sources:
            self._sources.append(source)

    def detach(self, source):
        """Remove a source attached with attach(). Unknown sources are ignored."""
        try:
            self._sources.remove(source)
        except ValueError:
            pass

    def is_pressed(self, mask=ALL):
        return bool(self.state & mask)

    def just_pressed(self, mask=ALL):
        """True if `mask` went down since the last poll(). The edge is STABLE for the whole frame -
        every call between two poll()s answers the same, which is what lets several systems react to
        one press. The state-machine hazard that follows: a state ENTERED this frame must not read
        the same edge, or the button that ended the game also dismisses the game-over screen before
        it is seen. Branch the states with `elif` (so only one runs per frame), or gate the new
        state on a frame counter."""
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
