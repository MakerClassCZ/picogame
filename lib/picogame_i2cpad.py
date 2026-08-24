# picogame i2cpad: GENERIC I2C gamepads/button boards as picogame button sources — one driver
# + a declarative recipe, the same philosophy as the USB gamepad support (one driver + a remap
# string, not a library per device).
#
# Covers the whole family of "dumb" I2C button devices (GPIO expanders: TCA9555, PCF8574,
# MCP23017, and vendor pads built on them, e.g. the Pimoroni QwSTPad). A device is described by
# a RECIPE: a few raw init writes, one register read per poll, and a NAME=bit map. Known pads
# ship as named PRESETS; anything else is one settings.toml line, no code.
#
# OPT-IN via settings.toml (expanders have no identity register, so auto-probing I2C addresses
# could bind an unrelated device — unlike USB HID, which self-describes):
#   PICOGAME_I2CPAD = "qwstpad"           # a preset, default address
#   PICOGAME_I2CPAD = "qwstpad@0x23"      # a preset at a specific address
#   PICOGAME_I2CPAD = "qwstpad;qwstpad@0x23"   # several pads = local multiplayer
#   PICOGAME_I2CPAD = "addr=0x20 read=:1 inv=1 UP=0 DOWN=1 LEFT=2 RIGHT=3 A=4 B=5"
#                                         # full recipe (here: a PCF8574 with 6 buttons)
#   PICOGAME_I2C = "GP4,GP5"              # bare boards only: SDA,SCL pins. Boards with a
#                                         #  STEMMA/Qw-ST connector need nothing.
# `picogame_input.Buttons()` then ORs the pad(s) in automatically — games need no changes.
#
# RECIPE tokens (space separated):
#   addr=0x21          I2C address
#   init=063FF9,0206C0 raw hex frames written once at attach (register + payload bytes verbatim)
#   read=00:2          per poll: write register byte 00, read 2 bytes ("read=:1" = plain read,
#                      no register — PCF8574 style)
#   inv=1              buttons are active-low in the RAW read (pressed bit = 0); omit when the
#                      device already reports pressed as 1 (qwstpad inverts in its polarity regs)
#   UP=1 A=14 ...      logical button = bit index into the read bytes (little-endian:
#                      bit = byte_index*8 + bit_in_byte); names as in PICOGAME_BUTTONS
#
# MULTIPLAYER: find_pads("qwstpad") -> one source per pad found on the preset's addresses,
# ready for Buttons(sources=[pad]) per player; each pad lights its player-number LED (presets
# with LEDs only). One poll = one short I2C transaction (~0.5 ms at 100 kHz); a failed poll
# (loose cable) holds the last state and reports all-released after 8 misses.

import os

import picogame_input as _pi

# preset = a parsed recipe dict; "addrs" lists the addresses find_pads() scans, "led" is an
# optional (register, (bit1..bit4), inverted) player-LED spec.
PRESETS = {
    # Pimoroni QwSTPad: TCA9555. Config regs make button pins inputs with inverted polarity
    # (pressed reads 1) and LED pins outputs; init frames are reg + 16-bit LE value verbatim.
    "qwstpad": {
        "addr": 0x21,
        "addrs": (0x21, 0x23, 0x25, 0x27),
        "init": (b"\x06\x3f\xf9", b"\x04\x3f\xf8", b"\x02\xc0\x06"),
        "rreg": b"\x00",
        "rlen": 2,
        "inv": False,
        "map": ((1, _pi.UP), (4, _pi.DOWN), (2, _pi.LEFT), (3, _pi.RIGHT),
                (14, _pi.A), (12, _pi.B), (15, _pi.X), (13, _pi.Y),
                (11, _pi.START), (5, _pi.SELECT)),
        # (output register, player-LED bits, inverted logic, register value after init)
        "led": (0x02, (6, 7, 9, 10), True, 0x06C0),
    },
}


def _unstick(scl, sda):
    """Classic I2C bus recovery: clock SCL up to 9 times so a slave stuck mid-transaction
    (holding SDA low - e.g. after a soft reload interrupted a read) releases the bus.
    Expander pads otherwise keep the bus dead until a power cycle: every transaction in the
    next program times out with OSError(116) even though the device is fine."""
    import time
    import digitalio
    s = digitalio.DigitalInOut(scl)
    d = digitalio.DigitalInOut(sda)
    try:
        d.switch_to_input(pull=digitalio.Pull.UP)
        s.switch_to_output(value=True, drive_mode=digitalio.DriveMode.OPEN_DRAIN)
        for _ in range(9):
            if d.value:                              # SDA released - bus is free
                break
            s.value = False
            time.sleep(0.00002)
            s.value = True
            time.sleep(0.00002)
        # STOP condition (SDA low->high while SCL high) so the slave state machine resets
        d.switch_to_output(value=False, drive_mode=digitalio.DriveMode.OPEN_DRAIN)
        time.sleep(0.00002)
        d.value = True
        time.sleep(0.00002)
    finally:
        s.deinit()
        d.deinit()


def _try_unstick(scl, sda):
    """Bus recovery, but only when the pins are free to claim - pins already held in
    THIS vm mean the bus object is alive (not stuck), so recovery is moot."""
    try:
        _unstick(scl, sda)
    except Exception:
        pass


def _bus():
    """The I2C bus: PICOGAME_I2C="SDA,SCL" pins on a bare board, else the board's own
    bus. The 9-clock soft-reload recovery runs in both paths (keyless via board.SDA/SCL
    when the board names them) - the key exists for bare boards / non-standard wiring
    only. Explicit pins that ARE the board's own bus (e.g. Fruit Jam SDA/SCL) route to
    the shared board.I2C() singleton - audio and friends already live on it, and a
    private busio.I2C on the same pins would fail with 'I2C peripheral in use'.

    A single token names a board BUS instead of pins: PICOGAME_I2C="I2C0" ->
    board.I2C0() (or the object itself when it isn't callable). This is the form for
    ports whose busio can't be built from pins (zephyr-cp: I2C comes from the device
    tree, the buses surface as board.I2C0/I2C1 factories)."""
    import board
    spec = os.getenv("PICOGAME_I2C")
    if spec:
        parts = [p.strip() for p in str(spec).replace(",", " ").split() if p.strip()]
        if len(parts) == 1:
            bus = getattr(board, parts[0], None)
            if bus is None:
                raise ValueError("PICOGAME_I2C bus %r not found on this board" % parts[0])
            return bus() if callable(bus) else bus
        sda_name, scl_name = parts
        sda = _pi._resolve_pin(sda_name)
        scl = _pi._resolve_pin(scl_name)
        if sda is None or scl is None:
            raise ValueError("PICOGAME_I2C pin %r not found on this board (try the"
                             " 'GPIOn' name)" % (sda_name if sda is None else scl_name))
        if getattr(board, "SDA", None) is sda and getattr(board, "SCL", None) is scl \
                and hasattr(board, "I2C"):
            _try_unstick(scl, sda)          # effective only before the singleton exists
            return board.I2C()
        _try_unstick(scl, sda)
        import busio
        return busio.I2C(scl, sda)
    # No key: the board's own bus. CP convention puts board.I2C() on board.SDA/SCL,
    # so when those names exist the soft-reload bus recovery works here too - the key
    # is only needed for bare boards / non-standard wiring.
    scl = getattr(board, "SCL", None)
    sda = getattr(board, "SDA", None)
    if scl is not None and sda is not None:
        _try_unstick(scl, sda)
    if hasattr(board, "STEMMA_I2C"):
        return board.STEMMA_I2C()
    return board.I2C()


def parse_recipe(text):
    """A recipe string -> recipe dict (see the header). Raises ValueError on nonsense."""
    r = {"init": (), "rreg": None, "rlen": 1, "inv": False, "addrs": None, "led": None}
    m = []
    for tok in str(text).split():
        key, _, val = tok.partition("=")
        if key == "addr":
            r["addr"] = int(val, 0)
        elif key == "init":
            r["init"] = tuple(bytes.fromhex(f) for f in val.split(","))
        elif key == "read":
            reg, _, n = val.partition(":")
            r["rreg"] = bytes.fromhex(reg) if reg else None
            r["rlen"] = int(n)
        elif key == "inv":
            r["inv"] = val != "0"
        elif key.upper() in _pi.NAMES:
            m.append((int(val, 0), _pi.NAMES[key.upper()]))
        else:
            raise ValueError("i2cpad: unknown token " + tok)
    if "addr" not in r or not m:
        raise ValueError("i2cpad: recipe needs addr= and at least one button")
    r["map"] = tuple(m)
    return r


class I2CPad:
    """One recipe-described I2C pad as a picogame button source. `read()` -> logical bitmask."""

    def __init__(self, recipe, i2c=None, address=None):
        self._i2c = i2c if i2c is not None else _bus()
        self._addr = address if address is not None else recipe["addr"]
        self._r = recipe
        self._rbuf = bytearray(recipe["rlen"])
        self._mask = 0
        self._misses = 0
        self.mapped = 0
        for _b, log in recipe["map"]:
            self.mapped |= log
        self._led_shadow = None
        for frame in recipe["init"]:                 # OSError here = no device at the address
            self._raw_write(frame)
        self._locked_read()                          # presence check even for init-less recipes

    def _raw_write(self, frame):
        while not self._i2c.try_lock():
            pass
        try:
            self._i2c.writeto(self._addr, frame)
        finally:
            self._i2c.unlock()

    def _locked_read(self):
        """One raw poll into self._rbuf; raises OSError when the device doesn't answer."""
        while not self._i2c.try_lock():
            pass
        try:
            if self._r["rreg"] is not None:
                self._i2c.writeto_then_readfrom(self._addr, self._r["rreg"], self._rbuf)
            else:
                self._i2c.readfrom_into(self._addr, self._rbuf)
        finally:
            self._i2c.unlock()

    def read(self):
        """Current logical bitmask. Holds the last state over a failed poll (loose cable);
        reports all-released after 8 consecutive misses so a disconnect can't stick a button."""
        try:
            self._locked_read()
        except OSError:
            self._misses += 1
            if self._misses >= 8:
                self._mask = 0
            return self._mask
        self._misses = 0
        state = 0
        for i in range(len(self._rbuf)):
            state |= self._rbuf[i] << (8 * i)
        if self._r["inv"]:
            state = ~state
        m = 0
        for bit, log in self._r["map"]:
            if state & (1 << bit):
                m |= log
        self._mask = m
        return m

    def led(self, n, on):
        """Player LED n (1-4) on/off — presets with a `led` spec only, no-op otherwise."""
        spec = self._r.get("led")
        if not spec:
            return
        reg, bits, inverted, initial = spec
        if self._led_shadow is None:
            self._led_shadow = initial
        bit = 1 << bits[n - 1]
        lit = not on if inverted else on
        self._led_shadow = (self._led_shadow | bit) if lit else (self._led_shadow & ~bit)
        self._raw_write(bytes((reg, self._led_shadow & 0xFF, (self._led_shadow >> 8) & 0xFF)))


def _spec_recipe(segment):
    """One spec segment -> (recipe, address): a preset name, preset@0xNN, or a full recipe."""
    s = segment.strip()
    name, _, at = s.partition("@")
    preset = PRESETS.get(name.strip().lower())
    if preset is not None:
        return preset, (int(at, 0) if at else preset["addr"])
    r = parse_recipe(s)
    return r, r["addr"]


def _recover(i2c):
    """Last-resort bus recovery when a pad times out: an expander interrupted mid-read (a soft
    reload during a poll is enough) holds SDA low and every later transaction returns ETIMEDOUT,
    even though a bare address scan still ACKs. _try_unstick can only clock it free while the
    pins are UNCLAIMED, so the live bus has to be deinit'd first - CircuitPython rebuilds the
    board singleton on the next board.I2C()/STEMMA_I2C() call. Returns the usable bus (the old
    one if recovery was not possible), so the caller can simply retry."""
    import board
    scl = getattr(board, "SCL", None)
    sda = getattr(board, "SDA", None)
    if scl is None or sda is None:
        return i2c
    try:
        i2c.deinit()                                 # frees the pins; assert_pin_free needs this
    except Exception:
        return i2c
    _try_unstick(scl, sda)
    try:
        return _bus()
    except Exception:
        return i2c


def attach(spec, i2c=None):
    """Pads for the PICOGAME_I2CPAD settings value — ";"-separated segments, one pad each.
    Used by picogame_input.Buttons; raises if a listed pad doesn't answer."""
    import time
    if i2c is None:
        i2c = _bus()
    pads = []
    for seg in str(spec).split(";"):
        recipe, addr = _spec_recipe(seg)
        for attempt in range(3):                     # a retry also clocks a sluggish bus free
            try:
                pad = I2CPad(recipe, i2c, addr)
                break
            except OSError:
                if attempt == 2:
                    raise
                if attempt == 1:                     # plain retries did not help: unstick the bus
                    i2c = _recover(i2c)
                time.sleep(0.01)
        try:
            pad.led(len(pads) + 1, True)
        except OSError:
            pass
        pads.append(pad)
    return pads


def find_pads(preset="qwstpad", i2c=None):
    """All pads of a preset on the bus, in address order — one source per player."""
    recipe = PRESETS[preset]
    if i2c is None:
        i2c = _bus()
    pads = []
    for addr in recipe.get("addrs") or (recipe["addr"],):
        try:
            pad = I2CPad(recipe, i2c, addr)
        except OSError:
            continue
        try:
            pad.led(len(pads) + 1, True)
        except OSError:
            pass
        pads.append(pad)
    return pads
