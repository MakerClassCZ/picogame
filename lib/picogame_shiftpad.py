# picogame shiftpad: buttons on a PARALLEL-IN SHIFT REGISTER (74HC165 and friends) as a picogame
# button source - the same philosophy as picogame_i2cpad and the USB pad support: one driver plus a
# declarative recipe, not a library per board.
#
# A handful of handhelds wire their buttons this way to save pins: eight switches feed one register,
# three GPIOs clock the byte out. picogame_input reads pins, a scanned matrix, I2C pads and USB pads
# - a shift register was the remaining shape, and without it a board like the Adafruit PyBadge has
# no usable input at all.
#
# OPT-IN via settings.toml (three GPIOs cannot be probed for safely - clocking an unknown device is
# not a read-only act):
#   PICOGAME_SHIFTPAD = "pybadge"        # a preset (below)
#   PICOGAME_SHIFTPAD = "latch=BUTTON_LATCH clock=BUTTON_CLOCK data=BUTTON_OUT bits=8 \
#                        LEFT=7 UP=6 DOWN=5 RIGHT=4 SELECT=3 START=2 A=1 B=0"
# `picogame_input.Buttons()` then ORs it in automatically - games need no changes.
#
# RECIPE tokens (space separated):
#   latch=NAME   clock=NAME   data=NAME   pin names looked up on `board`, then microcontroller.pin
#   bits=8       how many bits to clock out (one register = 8; chained registers = 8 per chip)
#   inv=1        the register reads 1 for a RELEASED button (pull-ups, no inverter on the board);
#                omit when a press reads 1, which is what a PyBadge does
#   msb=0        clock the LOW bit out first; default is MSB first, which is how a 74HC165
#                presents things (after the parallel load, Q7 already holds the highest input)
#   UP=6 A=1 ... logical button = bit index in the byte that comes out; names as in
#                PICOGAME_BUTTONS
#
# COST: one read is 8 GPIO clock pulses. Measured on a PyBadge (SAMD51, CircuitPython 10.3):
# 215 us, about 0.6 % of a 30 fps frame.

import os

import picogame_input as _pi

# A preset is just a parsed recipe. Bit numbering here is the value the register clocks out, so it
# matches the numbers a board's own library uses.
PRESETS = {
    # Adafruit PyBadge / PyBadge LC / PyGamer: one 74HC165, eight buttons, a press reads 1.
    # Bit values are Adafruit's own (adafruit_pybadger: LEFT=128, UP=64, DOWN=32, RIGHT=16,
    # SELECT=8, START=4, A=2, B=1).
    # msb=False is MEASURED, not assumed (PyBadge, 2026-09-19): this board clocks the button that
    # Adafruit calls bit 0 out FIRST, so reading MSB-first mirrors the whole byte - LEFT landed on
    # bit 0 and A on bit 6, exactly 7-n of where they belong. Reading LSB-first puts every button
    # back on Adafruit's own numbering.
    "pybadge": {
        "latch": "BUTTON_LATCH", "clock": "BUTTON_CLOCK", "data": "BUTTON_OUT",
        "bits": 8, "inv": False, "msb": False,
        "map": ((7, _pi.LEFT), (6, _pi.UP), (5, _pi.DOWN), (4, _pi.RIGHT),
                (3, _pi.SELECT), (2, _pi.START), (1, _pi.A), (0, _pi.B)),
    },
}
PRESETS["pygamer"] = PRESETS["pybadge"]        # same register, same order


def _pin(name):
    """A pin by name: `board` first, then a bare microcontroller pin (GP5, PA02...)."""
    import board
    p = getattr(board, name, None)
    if p is None:
        try:
            import microcontroller
            p = getattr(microcontroller.pin, name, None)
        except ImportError:
            p = None
    if p is None:
        raise ValueError("shiftpad: no pin named " + name)
    return p


def parse_recipe(text):
    """A recipe string -> recipe dict (see the header). Raises ValueError on nonsense."""
    r = {"bits": 8, "inv": False, "msb": True}
    m = []
    for tok in str(text).split():
        key, _, val = tok.partition("=")
        if key in ("latch", "clock", "data"):
            r[key] = val
        elif key == "bits":
            r["bits"] = int(val, 0)
        elif key == "inv":
            r["inv"] = val != "0"
        elif key == "msb":
            r["msb"] = val != "0"
        elif key.upper() in _pi.NAMES:
            m.append((int(val, 0), _pi.NAMES[key.upper()]))
        else:
            raise ValueError("shiftpad: unknown token " + tok)
    for need in ("latch", "clock", "data"):
        if need not in r:
            raise ValueError("shiftpad: recipe needs latch=, clock= and data=")
    if not m:
        raise ValueError("shiftpad: recipe needs at least one button")
    r["map"] = tuple(m)
    return r


class ShiftPad:
    """One shift-register pad as a picogame button source. `read()` -> logical bitmask."""

    def __init__(self, recipe):
        import digitalio
        self._r = recipe
        self._latch = digitalio.DigitalInOut(_pin(recipe["latch"]))
        self._clock = digitalio.DigitalInOut(_pin(recipe["clock"]))
        self._data = digitalio.DigitalInOut(_pin(recipe["data"]))
        self._latch.direction = digitalio.Direction.OUTPUT
        self._clock.direction = digitalio.Direction.OUTPUT
        self._data.direction = digitalio.Direction.INPUT
        self._latch.value = True                 # shift mode; a low pulse loads the inputs
        self._clock.value = False
        self.mapped = 0
        for _b, log in recipe["map"]:
            self.mapped |= log

    def raw(self):
        """The register's byte, as clocked out. Useful when working out a new board's bit map."""
        latch, clock, data = self._latch, self._clock, self._data
        latch.value = False                      # parallel load (PL is active low on a 74HC165)
        latch.value = True
        n = self._r["bits"]
        v = 0
        if self._r["msb"]:
            # After the load, the serial output already presents the highest input - so read the
            # pin FIRST and clock afterwards, or the first bit is lost.
            for _ in range(n):
                v = (v << 1) | (1 if data.value else 0)
                clock.value = True
                clock.value = False
        else:
            for i in range(n):
                if data.value:
                    v |= 1 << i
                clock.value = True
                clock.value = False
        return v

    def read(self):
        """Current logical bitmask."""
        v = self.raw()
        if self._r["inv"]:
            v = ~v
        m = 0
        for bit, log in self._r["map"]:
            if v & (1 << bit):
                m |= log
        return m

    def deinit(self):
        for p in (self._latch, self._clock, self._data):
            try:
                p.deinit()
            except Exception:
                pass


def attach(spec):
    """The pad for a PICOGAME_SHIFTPAD settings value - a preset name or a full recipe.
    Used by picogame_input.Buttons; returns a list so it reads like picogame_i2cpad.attach."""
    s = str(spec).strip()
    recipe = PRESETS.get(s.lower())
    if recipe is None:
        recipe = parse_recipe(s)
    return [ShiftPad(recipe)]
