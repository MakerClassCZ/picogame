# picogame_usbpad: read a USB HID gamepad on a USB-host board (e.g. Adafruit Fruit Jam) and expose it
# as an extra button SOURCE for picogame_input.Buttons. Buttons ORs every source together, so a game
# gets gamepad input with ZERO code changes - `Buttons()` just also reads the pad when one is plugged
# into the USB-HOST port. Needs a USB-host CircuitPython build (the `usb.core` module); on boards
# without it (PicoPad etc.) this driver simply never attaches. No firmware changes required.
#
# Default layout = DragonRise 081f:e401 "USB gamepad" (the ubiquitous cheap SNES-style pad):
#   byte0 = X axis (00=LEFT, 7f=center, ff=RIGHT), byte1 = Y axis (00=UP, ff=DOWN),
#   byte5 high nibble = X/A/B/Y, byte6 = L1/R1/SELECT/START.
# Other pads / personal preference: remap BUTTON bits from settings.toml (no reflash) -
#   PICOGAME_USBPAD = "A=5:0x40 B=5:0x20"                    # e.g. just swap A/B, keep the rest
#   PICOGAME_USBPAD = "A=5:0x20 B=5:0x40 X=5:0x10 Y=5:0x80 L1=6:0x01 R1=6:0x02 SELECT=6:0x10 START=6:0x20"
# (NAME=byteindex:bitmask; a partial list MERGES over the defaults - only the named buttons change;
# axes stay byte0/byte1.) Discover a new pad's bits with the probe in
# tools/ (prints the report bytes that change on each press). A wholly different report layout can be
# passed to UsbPad(buttons=..., axes=...) in code.
import os

VERSION = "2026-07-23j"   # deploy sanity: print(picogame_usbpad.VERSION) in the REPL

from picogame_input import (UP, DOWN, LEFT, RIGHT, A, B, X, Y,
                            L1, L2, R1, R2, START, SELECT, NAMES)

# axis thresholds on a 0..255 centered-at-0x7f axis: below LO = low direction, above HI = high
_LO = 0x40
_HI = 0xC0

# default DragonRise 081f:e401 button map: (report byte index, bitmask, logical button)
_DEFAULT_BTN = (
    (5, 0x20, A), (5, 0x40, B), (5, 0x10, X), (5, 0x80, Y),
    (6, 0x01, L1), (6, 0x02, R1), (6, 0x10, SELECT), (6, 0x20, START),
)
# default axes: (report byte index, logical-when-low, logical-when-high)
_DEFAULT_AXES = ((0, LEFT, RIGHT), (1, UP, DOWN))

# union of everything the DEFAULT map can report (Buttons.has() uses the per-instance `mapped` mask,
# which also covers custom remaps that add L2/R2 - see UsbPad.mapped)
MAPPED = UP | DOWN | LEFT | RIGHT | A | B | X | Y | L1 | R1 | SELECT | START

_DR_VID = 0x081F   # DragonRise Inc. - the generic "USB gamepad" (the SNES-style pad this maps by default)
_DR_PID = 0xE401


def _buttons_from_settings():
    """Parse PICOGAME_USBPAD = 'A=5:0x20 B=5:0x40 ...' -> button map, or None if unset/empty."""
    s = os.getenv("PICOGAME_USBPAD")
    if not s:
        return None
    out = []
    for tok in s.replace(",", " ").split():
        if "=" not in tok:
            continue
        nm, spec = tok.split("=", 1)
        bit = NAMES.get(nm.strip().upper())
        if bit is None or ":" not in spec:
            continue
        bi, mask = spec.split(":", 1)
        try:
            out.append((int(bi), int(mask, 0), bit))
        except ValueError:
            continue
    return out or None


def _merged_buttons():
    """Default button map with any settings.toml PICOGAME_USBPAD entries merged over it: a named
    logical button takes its bit from settings, every other button keeps the default."""
    override = _buttons_from_settings()
    if not override:
        return _DEFAULT_BTN
    overridden = 0
    for _bi, _mask, log in override:
        overridden |= log
    merged = [e for e in _DEFAULT_BTN if not (e[2] & overridden)]
    merged.extend(override)
    return tuple(merged)


def _id_from_settings():
    """settings.toml `PICOGAME_USBPAD_ID = "081f:e401"` (hex vid:pid) for a non-DragonRise pad, else the
    DragonRise default. We match by VID/PID, NEVER "first enumerated device": CircuitPython's usb.core
    exposes no device class, so a blind grab would happily bind a keyboard/hub/mouse (a boot keyboard's
    zeroed axis bytes decode as LEFT|UP). A truly custom pad also needs its byte map via PICOGAME_USBPAD."""
    s = os.getenv("PICOGAME_USBPAD_ID")
    if s and ":" in s:
        try:
            a, b = s.split(":", 1)
            return int(a, 16), int(b, 16)
        except ValueError:
            pass
    return _DR_VID, _DR_PID


class UsbPad:
    """One USB HID gamepad as a picogame button source. `read()` -> current logical bitmask.

    Construction raises (no usb.core / no pad / claim failed) so the caller can fall back; once built,
    `read()` never raises - it holds the last state on a stale read and releases all on unplug."""

    # timeout_ms bounds how long read() waits for the pad's interrupt
    # report. DEFAULT 3 (HW-tuned, 2026-07-23): fetching even an ALREADY
    # PENDING report takes ~1-2 ms on a low-speed pad behind the hub
    # (transactions schedule on 1 ms USB frame boundaries), so a 1 ms
    # timeout aborts mid-transfer and DROPS reports - imperceptible when
    # polling at 90+ Hz (the next poll retries ~10 ms later) but visibly
    # laggy at a 30 fps cap (each loss is a 33 ms hole; measured: to=1 at
    # ~90 Hz still timed out 60% of polls, to=8 at 30 Hz timed out none).
    # 3 ms clears the fetch latency with margin (2 ms already tested OK on
    # HW; 3 adds headroom) at a ~1-2 fps cost to the uncapped ceiling vs
    # 1 ms. PICOGAME_USBPAD_TIMEOUT overrides.
    # (Never use 0: libusb semantics make 0 = wait forever.)
    def __init__(self, dev=None, vid=None, pid=None, ep=0x81, report_len=8,
                 buttons=None, axes=_DEFAULT_AXES, timeout_ms=None):
        import usb.core
        self._timeout_exc = usb.core.USBTimeoutError
        if dev is None:
            if not (vid or pid):
                vid, pid = _id_from_settings()   # DragonRise default, or PICOGAME_USBPAD_ID
            dev = usb.core.find(idVendor=vid, idProduct=pid)   # match by VID/PID, never "first device"
        if dev is None:
            raise ValueError("picogame_usbpad: no matching USB gamepad (VID/PID) found")
        self._vid = vid                                 # for re-attach after a bus drop
        self._pid = pid
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except Exception:
            pass                                        # not all backends implement this - fine
        dev.set_configuration()
        self._dev = dev
        self._ep = ep
        self._buf = bytearray(report_len)
        self._buttons = buttons if buttons is not None else _merged_buttons()
        self._axes = axes
        if timeout_ms is None:                          # settings.toml override, else 1
            try:
                import os
                timeout_ms = int(os.getenv("PICOGAME_USBPAD_TIMEOUT") or "3")
            except (ValueError, ImportError):
                timeout_ms = 3
        self._to = max(1, timeout_ms)                   # never 0: libusb 0 = wait forever
        self._no_raise = True                           # probe raise_on_timeout= on first read()
        self._errs = 0                                  # consecutive hard USB errors (re-attach gate)
        self._mask = 0
        self._quiet = 0                                 # consecutive quiet polls (stale-mask healer)
        self._resync_ok = True                          # healer enabled until GET_REPORT fails once
        m = 0                                           # per-instance mapped mask (covers custom remaps
        for _bi, _mask, log in self._buttons:           # that add L2/R2, unlike the module MAPPED const)
            m |= log
        for _bi, lo, hi in self._axes:
            m |= lo | hi
        self.mapped = m

    def read(self):
        """Non-blocking-ish: fetch the latest HID report (waits up to timeout_ms) and return the
        current logical bitmask. On a timeout (no fresh report) holds the last mask; on any other
        USB error (pad unplugged) releases everything (returns 0).

        Newer firmware exposes read(..., raise_on_timeout=False) -> 0 (our upstream
        CircuitPython addition): an empty poll then allocates NOTHING, where the
        exception path costs an exception object per poll (~1-1.5 KB/s at 30 fps,
        measured). Feature-detected once; older firmware falls back to the
        exception path transparently."""
        if self._no_raise:
            try:
                n = self._dev.read(self._ep, self._buf, timeout=self._to,
                                   raise_on_timeout=False)
            except TypeError:                           # old firmware: kwarg unknown
                self._no_raise = False
                return self._mask                       # plain path from next frame on
            except Exception:
                return self._hard_error()
            if n == 0:
                return self._held()                     # no new report -> hold (self-healing) state
        else:
            try:
                n = self._dev.read(self._ep, self._buf, timeout=self._to)
            except self._timeout_exc:
                return self._held()                     # no new report -> hold (self-healing) state
            except Exception:
                return self._hard_error()
        self._quiet = 0
        self._errs = 0
        return self._parse(n)

    def _hard_error(self):
        """A non-timeout USB error: the pad stalled, dropped off the bus or
        re-enumerated (observed on HW as a pad going silently dead mid-game -
        the old handle never recovers by itself). Release all buttons, and
        after ~1 s of consecutive failures try a full re-attach: find the
        device again by VID/PID, reconfigure, drain the junk reports a fresh
        enumeration emits (zeroed axes = phantom LEFT|UP)."""
        self._mask = 0
        self._errs += 1
        if self._errs >= 30 and self._vid:              # ~1 s at a 30 fps poll
            self._errs = 0
            try:
                import usb.core
                dev = usb.core.find(idVendor=self._vid, idProduct=self._pid)
                if dev is not None:
                    try:
                        if dev.is_kernel_driver_active(0):
                            dev.detach_kernel_driver(0)
                    except Exception:
                        pass
                    dev.set_configuration()
                    self._dev = dev
                    for _ in range(8):                  # drain enumeration junk
                        try:
                            if not self._dev.read(self._ep, self._buf, timeout=2):
                                break
                        except Exception:
                            break
                    import picogame_debug
                    picogame_debug.note("usbpad: re-attached after bus drop")
            except Exception:
                pass
        return 0

    def _held(self):
        """Held state during quiet polls - with a STALE-MASK HEALER. This pad
        class reports on CHANGE, and a timed-out interrupt read ABORTS its
        transfer; an abort racing the pad's change-report can eat it. A lost
        RELEASE then wedges the held mask at "pressed" forever (observed on
        HW: a crash prompt that never reacts because A/LEFT are stuck on).
        After ~8 consecutive quiet polls with a non-zero mask, fetch ground
        truth synchronously via a HID GET_REPORT control transfer (control
        transfers complete, they cannot be abort-raced) and re-parse. Pads
        that stall GET_REPORT get the healer disabled on first failure."""
        if self._mask:
            self._quiet += 1
            if self._quiet >= 8 and self._resync_ok:
                self._quiet = 0
                try:
                    # bmRequestType 0xA1 = device-to-host|class|interface,
                    # bRequest 0x01 = GET_REPORT, wValue 0x0100 = Input report 0
                    n = self._dev.ctrl_transfer(0xA1, 0x01, 0x0100, 0,
                                                self._buf, timeout=20)
                    if n:
                        return self._parse(n)
                except Exception:
                    self._resync_ok = False             # unsupported -> never retry
        return self._mask

    def _parse(self, n):
        r = self._buf
        m = 0
        for bi, bit, log in self._buttons:              # 0 <= bi < n guards a bad byte index from a
            if 0 <= bi < n and (r[bi] & bit):           # malformed settings remap (else r[-99] would
                m |= log                                 # raise here, outside the USB-read try)
        for bi, lo, hi in self._axes:
            if 0 <= bi < n:
                v = r[bi]
                if v < _LO:
                    m |= lo
                elif v > _HI:
                    m |= hi
        self._mask = m
        return m
