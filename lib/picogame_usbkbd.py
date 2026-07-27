# picogame_usbkbd: read a USB HID keyboard on a USB-host board (e.g. Adafruit Fruit Jam) and expose
# it as an extra button SOURCE for picogame_input.Buttons - the keyboard twin of picogame_usbpad.
# Buttons ORs every source together, so a game gets keyboard input with ZERO code changes.
#
# Works with wired keyboards AND wireless ones that use a 2.4 GHz USB dongle (the dongle presents a
# standard HID keyboard; Bluetooth keyboards do NOT work - CircuitPython has no BT host stack).
# The keyboard is found by its BOOT-KEYBOARD interface descriptor (keyboards have no fixed VID/PID):
# the config descriptor is walked for class-3/protocol-1 interfaces (adafruit_usb_host_descriptors,
# when present, only orders the preference). Some combo dongles advertise a boot-keyboard interface
# that never delivers a report while the real keystrokes flow on a SIBLING keyboard interface
# (e.g. a Rapoo 2.4G receiver: iface 1 silent, iface 2 live). For those, point the driver at the
# right channel from settings.toml - deterministic, no auto-detection:
#   PICOGAME_USBKBD_EP = "2:0x83"                      # "interface:IN endpoint"
# (run tools/usbkbd_probe.py as code.py to find the value - it prints this exact line.)
# CircuitPython's own terminal may hold the keyboard for the REPL - the kernel driver is
# detached, so while a game runs the keyboard belongs to the game.
#
# Default layout (boot report: byte0 = modifiers, bytes 2..7 = up to 6 pressed keycodes):
#   arrows + WASD -> D-pad,  Z / Space -> A,  X -> B,  C -> X,  V -> Y,
#   Q -> L1,  E -> R1,  Enter -> START,  Esc -> SELECT
# Remap from settings.toml (no reflash), same grammar as the gamepad:
#   PICOGAME_USBKBD = "A=0x2C B=0x1B START=0x28"      # NAME=HID keycode (hex or decimal)
# (a partial list MERGES over the defaults - only the named buttons change; one keycode per
# button in the override, the defaults may alias several keycodes to one logical button.)
import os

VERSION = "2026-07-23g"   # deploy sanity: print(picogame_usbkbd.VERSION) in the REPL

from picogame_input import (UP, DOWN, LEFT, RIGHT, A, B, X, Y,
                            L1, R1, START, SELECT, NAMES)

# default map: HID keycode -> logical button (aliases allowed: WASD + arrows)
_DEFAULT_KEYS = (
    (0x52, UP), (0x1A, UP),          # Up arrow, W
    (0x51, DOWN), (0x16, DOWN),      # Down arrow, S
    (0x50, LEFT), (0x04, LEFT),      # Left arrow, A
    (0x4F, RIGHT), (0x07, RIGHT),    # Right arrow, D
    (0x1D, A), (0x2C, A),            # Z, Space
    (0x1B, B),                       # X
    (0x06, X),                       # C
    (0x19, Y),                       # V
    (0x14, L1), (0x08, R1),          # Q, E
    (0x28, START),                   # Enter
    (0x29, SELECT),                  # Esc
)


def _keys_from_settings():
    """PICOGAME_USBKBD = 'A=0x2C START=0x28 ...' -> overrides merged over the defaults."""
    s = os.getenv("PICOGAME_USBKBD")
    if not s:
        return _DEFAULT_KEYS
    override = []
    for tok in s.replace(",", " ").split():
        if "=" not in tok:
            continue
        nm, code = tok.split("=", 1)
        bit = NAMES.get(nm.strip().upper())
        try:
            code = int(code, 0)
        except ValueError:
            continue
        if bit is not None:
            override.append((code, bit))
    if not override:
        return _DEFAULT_KEYS
    overridden = 0
    ovcodes = []
    for c, log in override:
        overridden |= log
        ovcodes.append(c)
    merged = [e for e in _DEFAULT_KEYS
              if not (e[1] & overridden) and e[0] not in ovcodes]
    merged.extend(override)
    return tuple(merged)


def _kbd_candidates(dev):
    """All keyboard-capable (interface, IN endpoint) pairs of a device, read from its raw
    config descriptor: HID class 03, boot-interface protocol 01 = keyboard. The pair the
    descriptor helpers would pick goes FIRST - but on some combo dongles that official boot
    interface is a DEAD channel and the real keystrokes flow on a sibling keyboard interface
    (seen on a Rapoo 2.4G receiver: iface 1/ep 0x82 silent, iface 2/ep 0x83 live), which is
    the fix is the PICOGAME_USBKBD_EP setting (see the module header)."""
    cands = []
    try:
        cfg = bytearray(256)
        n = dev.ctrl_transfer(0x80, 6, 0x0200, 0, cfg, timeout=200)
        i = 0
        iface = None
        proto = None
        while i + 1 < n:
            ln, dt = cfg[i], cfg[i + 1]
            if ln == 0:
                break
            if dt == 4:                          # INTERFACE
                iface = cfg[i + 2]
                proto = cfg[i + 7] if cfg[i + 5] == 3 else None   # class 3 = HID
            elif dt == 5 and proto == 1:         # ENDPOINT on a keyboard interface
                ep = cfg[i + 2]
                if ep & 0x80:                    # IN
                    cands.append((iface, ep))
            i += ln
    except Exception:
        pass
    try:
        import adafruit_usb_host_descriptors as ahd
        iface, ep = ahd.find_boot_keyboard_endpoint(dev)
        if iface is not None and ep is not None:
            pref = (iface, ep)
            if pref in cands:
                cands.remove(pref)
            cands.insert(0, pref)
    except Exception:
        pass
    return cands


def _find_keyboard():
    """First device on the bus with any keyboard-protocol interface -> (device, candidates).
    A plain single-interface keyboard legitimately yields [(0, 0x81)] from the walk."""
    import usb.core
    for dev in usb.core.find(find_all=True):
        try:
            cands = _kbd_candidates(dev)
            if cands:
                return dev, cands
        except Exception:
            continue
    return None, None


def _pick(cands):
    """settings.toml PICOGAME_USBKBD_EP = "iface:ep" (e.g. "2:0x83") wins; otherwise the
    descriptor-preferred candidate. Deterministic - a dongle whose boot interface is dead
    gets the one-line setting, not an auto-detection heuristic."""
    ov = os.getenv("PICOGAME_USBKBD_EP")
    if ov and ":" in ov:
        try:
            i, e = ov.split(":", 1)
            i, e = int(i, 0), int(e, 0)
            if 0 <= i <= 255 and (e & 0x80) and e <= 0xFF:   # interface + IN endpoint
                return i, e
        except ValueError:
            pass
    return cands[0]


def _claim_detach(dev, iface):
    try:
        if dev.is_kernel_driver_active(iface):
            dev.detach_kernel_driver(iface)
    except Exception:
        pass


def _claim(dev, iface):
    """Take the keyboard interface over from CircuitPython's own terminal: the supervisor's
    built-in host-keyboard support claims the KEYBOARD interface (not 0!) and consumes its
    reports for the REPL - until it is detached, our reads never see a byte. Then force the
    8-byte BOOT protocol (combo dongles default to report protocol; SET_PROTOCOL(0) is the
    HID class request bmRequestType 0x21, bRequest 0x0B)."""
    for i in (iface, 0):
        _claim_detach(dev, i)
    dev.set_configuration()
    _boot_protocol(dev, iface)


def _boot_protocol(dev, iface):
    try:
        dev.ctrl_transfer(0x21, 0x0B, 0, iface, None, timeout=50)   # SET_PROTOCOL: boot
    except Exception:
        pass                                # report-protocol keyboards still send 8-byte-alike


class UsbKbd:
    """One USB HID boot keyboard as a picogame button source. `read()` -> current logical
    bitmask. Construction raises when no keyboard is present (the caller falls back);
    once built, read() never raises - it holds the last state on a quiet poll and
    releases everything on a hard USB error, re-attaching after ~1 s of failures."""

    def __init__(self, dev=None, iface=None, ep=None, keys=None, timeout_ms=None):
        auto = dev is None
        if auto:
            dev, cands = _find_keyboard()
            if dev is not None:
                iface, ep = _pick(cands)
                for i, _e in cands:              # detach every candidate iface (the
                    _claim_detach(dev, i)        # supervisor may hold any of them)
                _claim_detach(dev, iface)        # override may point outside cands
                _claim_detach(dev, 0)            # + iface 0 (a combo dongle's mouse) - a
                dev.set_configuration()          # held iface makes set_configuration fail
                _boot_protocol(dev, iface)
        if dev is None:
            raise ValueError("picogame_usbkbd: no boot keyboard found")
        if not auto:                         # explicit device: claim it like UsbPad does
            _claim(dev, iface if iface is not None else 0)
        self._dev = dev
        self._iface = iface if iface is not None else 0
        self._ep = ep if ep is not None else 0x81
        self._vid = getattr(dev, "idVendor", None)
        self._pid = getattr(dev, "idProduct", None)
        self._buf = bytearray(8)
        self._keys = keys if keys is not None else _keys_from_settings()
        if timeout_ms is None:
            try:
                timeout_ms = int(os.getenv("PICOGAME_USBKBD_TIMEOUT") or "3")
            except ValueError:
                timeout_ms = 3
        self._to = max(1, timeout_ms)
        self._mask = 0
        self._errs = 0
        self._no_raise = True                   # probe raise_on_timeout= on first read()
        m = 0
        for _c, log in self._keys:
            m |= log
        self.mapped = m

    def read(self):
        if self._no_raise:
            try:
                n = self._dev.read(self._ep, self._buf, timeout=self._to,
                                   raise_on_timeout=False)
            except TypeError:                   # old firmware: kwarg unknown
                self._no_raise = False
                return self._mask
            except Exception:
                return self._hard_error()
            if n == 0:
                return self._mask               # no new report -> hold last state
        else:
            try:
                n = self._dev.read(self._ep, self._buf, timeout=self._to)
            except Exception as e:
                if type(e).__name__ == "USBTimeoutError":
                    return self._mask
                return self._hard_error()
        self._errs = 0
        return self._parse(n)

    def _parse(self, n):
        r = self._buf
        if n > 2 and r[2] == 1:                 # error rollover (>6 keys / ghosting):
            return self._mask                   # state unknown -> HOLD, don't release
        m = 0
        # boot report: bytes 2..7 hold up to 6 concurrently pressed keycodes
        for i in range(2, min(n, 8)):
            c = r[i]
            if c <= 3:                          # 0 = none, 1-3 = HID error codes
                continue
            for code, log in self._keys:
                if code == c:
                    m |= log
        self._mask = m
        return m

    def _hard_error(self):
        """Keyboard stalled / dropped off the bus (wireless dongles also disappear when
        their batteries die): release all keys and retry a full re-attach after ~1 s."""
        self._mask = 0
        self._errs += 1
        if self._errs >= 30:
            self._errs = 0
            try:
                dev, cands = _find_keyboard()
                if dev is not None:
                    iface, ep = _pick(cands)
                    for i, _e in cands:
                        _claim_detach(dev, i)
                    _claim_detach(dev, iface)
                    _claim_detach(dev, 0)
                    dev.set_configuration()
                    _boot_protocol(dev, iface)
                    self._dev = dev
                    self._iface = iface
                    self._ep = ep
                    import picogame_debug
                    picogame_debug.note("usbkbd: re-attached after bus drop")
            except Exception:
                pass
        return 0
