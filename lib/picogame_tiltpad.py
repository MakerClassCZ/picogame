# picogame tiltpad: the board's ACCELEROMETER as a D-pad, so a handheld with a motion sensor can
# steer by tilting. Same shape as picogame_i2cpad and picogame_shiftpad - one driver plus a
# declarative recipe, not a library per chip - and like them it is an extra Buttons SOURCE, so its
# directions are OR'ed with the real D-pad and games need no changes.
#
# Deliberately NOT built on adafruit_lis3dh: reading a few registers is a handful of lines, and a
# driver nobody has to install is the whole point of the recipe modules.
#
# OPT-IN via settings.toml (an accelerometer answering on the bus is not a request to steer with it):
#   PICOGAME_TILTPAD = "pybadge"
#   PICOGAME_TILTPAD = "lis3dh on=4000 off=2500"        # a preset plus overrides
#
# RECIPE tokens (space separated), after an optional leading preset name:
#   addr=0x19    I2C address (else the preset's candidates are probed)
#   on=4000      tilt at which a direction ENGAGES (raw counts; ~16384 = 1 g at +/-2 g)
#   off=2500     tilt at which it RELEASES. Two thresholds, because with one the direction
#                chatters on and off while the hand rests near it. off must be < on.
#   swap=1       X steers up/down and Y left/right (portrait vs landscape boards)
#   invx=1 invy=1   flip one axis
#   calib=0      do NOT zero on attach; use the sensor's own 0 as level instead
#
# ZERO POINT: by default the resting position is measured at attach, so "level" is however the
# player is holding it at boot rather than a table. Hold it the way you mean to play.

import os
import time

import picogame_input as _pi

PRESETS = {
    # ST LIS3DH: Adafruit PyBadge, PyGamer, Circuit Playground Express, many Feather wings.
    # CTRL_REG1 0x57 = 100 Hz, normal mode, all three axes. CTRL_REG4 0x88 = block data update +
    # high resolution, +/-2 g. Reads start at OUT_X_L with the auto-increment bit (0x80) set.
    "lis3dh": {
        "addrs": (0x19, 0x18),
        "whoami": (0x0F, 0x33),
        "init": (b"\x20\x57", b"\x23\x88"),
        "reg": 0xA8, "len": 6,
        # (which 16-bit word, what a NEGATIVE reading means, what a POSITIVE one means)
        "axes": ((0, _pi.LEFT, _pi.RIGHT), (1, _pi.UP, _pi.DOWN)),
        "on": 4000, "off": 2500,
        "swap": False, "invx": False, "invy": False, "calib": True,
    },
}
PRESETS["pybadge"] = PRESETS["lis3dh"]
PRESETS["pygamer"] = PRESETS["lis3dh"]


def _bus():
    """The board's own I2C. Always the shared singleton: the accelerometer sits on the same bus as
    everything else on these boards, and a private busio.I2C on those pins fails as 'in use'."""
    import board
    i2c = getattr(board, "I2C", None)
    if i2c is None:
        raise RuntimeError("tiltpad: this board has no board.I2C()")
    return i2c() if callable(i2c) else i2c


def parse_recipe(text):
    """`[preset] [token=value ...]` -> recipe dict. Raises ValueError on an unknown token."""
    parts = str(text).split()
    r = None
    if parts and "=" not in parts[0]:
        r = PRESETS.get(parts[0].lower())
        if r is None:
            raise ValueError("tiltpad: unknown preset " + parts[0])
        parts = parts[1:]
    if r is None:
        r = PRESETS["lis3dh"]
    r = dict(r)
    for tok in parts:
        key, _, val = tok.partition("=")
        if key in ("on", "off", "addr"):
            r[key] = int(val, 0)
        elif key in ("swap", "invx", "invy", "calib"):
            r[key] = val != "0"
        else:
            raise ValueError("tiltpad: unknown token " + tok)
    if r["off"] >= r["on"]:
        raise ValueError("tiltpad: off must be below on (it is the release threshold)")
    return r


class TiltPad:
    """An accelerometer as a picogame button source. `read()` -> logical bitmask."""

    def __init__(self, recipe, i2c, addr=None):
        self._r = recipe
        self._i2c = i2c
        self._buf = bytearray(recipe["len"])
        self._addr = addr if addr is not None else self._find(recipe)
        for frame in recipe["init"]:
            self._write(frame)
        time.sleep(0.02)                  # first conversion at 100 Hz
        self._zero = [0, 0]
        if recipe["calib"]:
            self._zero = self._average(8)
        self._state = 0                   # held across reads: that is what makes the hysteresis work
        self.mapped = 0
        for _w, neg, pos in recipe["axes"]:
            self.mapped |= neg | pos

    # ---- bus ----
    def _write(self, frame):
        while not self._i2c.try_lock():
            pass
        try:
            self._i2c.writeto(self._addr, frame)
        finally:
            self._i2c.unlock()

    def _read_regs(self):
        while not self._i2c.try_lock():
            pass
        try:
            self._i2c.writeto(self._addr, bytes((self._r["reg"],)))
            self._i2c.readfrom_into(self._addr, self._buf)
        finally:
            self._i2c.unlock()
        return self._buf

    def _find(self, recipe):
        who_reg, who_val = recipe["whoami"]
        for addr in recipe["addrs"]:
            try:
                while not self._i2c.try_lock():
                    pass
                try:
                    self._i2c.writeto(addr, bytes((who_reg,)))
                    b = bytearray(1)
                    self._i2c.readfrom_into(addr, b)
                finally:
                    self._i2c.unlock()
                if b[0] == who_val:
                    return addr
            except OSError:
                continue
        raise RuntimeError("tiltpad: no accelerometer answered at %s"
                           % (", ".join(hex(a) for a in recipe["addrs"])))

    # ---- readings ----
    def axes(self):
        """(x, y) as raw signed counts, zero point removed. Useful for picking thresholds."""
        b = self._read_regs()
        out = []
        for i in (0, 1):
            v = b[i * 2] | (b[i * 2 + 1] << 8)
            if v & 0x8000:
                v -= 0x10000
            out.append(v - self._zero[i])
        if self._r["swap"]:
            out[0], out[1] = out[1], out[0]
        if self._r["invx"]:
            out[0] = -out[0]
        if self._r["invy"]:
            out[1] = -out[1]
        return out

    def _average(self, n):
        acc = [0, 0]
        for _ in range(n):
            b = self._read_regs()
            for i in (0, 1):
                v = b[i * 2] | (b[i * 2 + 1] << 8)
                if v & 0x8000:
                    v -= 0x10000
                acc[i] += v
            time.sleep(0.01)
        return [a // n for a in acc]

    def read(self):
        """Current logical bitmask. A direction engages past `on` and holds until the tilt falls
        back under `off` - one threshold would chatter whenever a hand rests near it."""
        vals = self.axes()
        on, off = self._r["on"], self._r["off"]
        state = self._state
        for word, neg, pos in self._r["axes"]:
            v = vals[word]
            for bit, mag in ((neg, -v), (pos, v)):
                if state & bit:
                    if mag < off:
                        state &= ~bit
                elif mag > on:
                    state |= bit
                    state &= ~(pos if bit == neg else neg)   # never both ends of one axis
        self._state = state
        return state

    def deinit(self):
        pass


def attach(spec, i2c=None):
    """The pad for a PICOGAME_TILTPAD settings value. Used by picogame_input.Buttons; returns a
    list, so it reads like picogame_i2cpad.attach and picogame_shiftpad.attach."""
    recipe = parse_recipe(spec)
    return [TiltPad(recipe, i2c if i2c is not None else _bus(), recipe.get("addr"))]
