# boot.py — build the display from settings.toml so it becomes board.DISPLAY.
# USE ONLY with a picogame "custom board" firmware (pico/pico_w/pico2/pico2_w builds that expose a
# board.DISPLAY slot). The display built here persists into code.py, so your game runs UNCHANGED as
# code.py — no launcher, no extra lib. Copy this + settings.toml to CIRCUITPY root.
#
# settings.toml:
#   PICOGAME_DISPLAY = "st7789" | "ili9341"
#   PICOGAME_PINS    = "SCK=GP18 MOSI=GP19 DC=GP17 CS=GP21 RST=GP20 BL=GP16"
#   PICOGAME_SIZE    = "320x240"      (WIDTH>HEIGHT => landscape)
#   PICOGAME_FLIP    = "" | "h" | "v" | "hv"    PICOGAME_INVERT = 0|1    PICOGAME_BGR = 0|1
#   PICOGAME_BAUD    = 24000000
# (Adding a controller = add a table in _driver() below. Pure Python, no firmware rebuild.)
import os
import board


def _flag(key):
    v = os.getenv(key)
    if v is None:
        return False
    return (v != 0) if isinstance(v, int) else v.strip().lower() not in ("", "0", "false", "no")


def _pin(name):
    if not name:
        return None
    p = getattr(board, name, None)
    if p is None:
        try:
            import microcontroller
            p = getattr(microcontroller.pin, name, None)
        except ImportError:
            p = None
    return p


def _enc(seq):
    out = bytearray()
    for cmd, data, dl in seq:
        out.append(cmd)
        out.append(len(data) | (0x80 if dl is not None else 0))
        out.extend(data)
        if dl is not None:
            out.append(dl)
    return bytes(out)


def _driver(ctrl, madctl, invert):
    if ctrl == "st7789":
        return _enc([
            (0x01, b"", 150), (0x36, bytes([madctl]), None), (0x35, b"\x00", None),
            (0xB2, b"\x0c\x0c\x00\x33\x33", None), (0x3A, b"\x05", None), (0xB7, b"\x14", None),
            (0xBB, b"\x37", None), (0xC0, b"\x2c", None), (0xC2, b"\x01", None), (0xC3, b"\x12", None),
            (0xC4, b"\x20", None), (0xD0, b"\xa4\xa1", None), (0xC6, b"\x0f", None),
            (0xE0, b"\xd0\x04\x0d\x11\x13\x2b\x3f\x54\x4c\x18\x0d\x0b\x1f\x23", None),
            (0xE1, b"\xd0\x04\x0c\x11\x13\x2c\x3f\x44\x51\x2f\x1f\x1f\x20\x23", None),
            (0x21 if invert else 0x20, b"", None), (0x11, b"", 255), (0x29, b"", 100)])
    if ctrl == "ili9341":
        return _enc([
            (0xEF, b"\x03\x80\x02", None), (0xCF, b"\x00\xC1\x30", None), (0xED, b"\x64\x03\x12\x81", None),
            (0xE8, b"\x85\x00\x78", None), (0xCB, b"\x39\x2C\x00\x34\x02", None), (0xF7, b"\x20", None),
            (0xEA, b"\x00\x00", None), (0xC0, b"\x23", None), (0xC1, b"\x10", None), (0xC5, b"\x3e\x28", None),
            (0xC7, b"\x86", None), (0x36, bytes([madctl]), None), (0x37, b"\x00", None), (0x3A, b"\x55", None),
            (0xB1, b"\x00\x18", None), (0xB6, b"\x08\xa2\x27", None), (0xF2, b"\x00", None), (0x26, b"\x01", None),
            (0xE0, b"\x0F\x31\x2B\x0C\x0E\x08\x4E\xF1\x37\x07\x10\x03\x0E\x09\x00", None),
            (0xE1, b"\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F", None),
            (0x21 if invert else 0x20, b"", None), (0x11, b"", 120), (0x29, b"", 120)])
    raise ValueError("PICOGAME_DISPLAY must be st7789 or ili9341")


def build_display():
    """Build the display from settings.toml. Returns the BusDisplay, or None if PICOGAME_DISPLAY unset."""
    ctrl = os.getenv("PICOGAME_DISPLAY")
    if not ctrl:
        return None
    pins = {}
    for tok in (os.getenv("PICOGAME_PINS") or "").replace(",", " ").split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            pins[k.strip().upper()] = v.strip()
    size = (os.getenv("PICOGAME_SIZE") or "320x240").lower().split("x")
    w, h = int(size[0]), int(size[1])
    flip = (os.getenv("PICOGAME_FLIP") or "").lower()
    baud = os.getenv("PICOGAME_BAUD")
    madctl = ((0x20 if w > h else 0) | (0x40 if "h" in flip else 0)
              | (0x80 if "v" in flip else 0) | (0x08 if _flag("PICOGAME_BGR") else 0))
    init = _driver(ctrl.strip().lower(), madctl, _flag("PICOGAME_INVERT"))
    import busio
    import displayio
    from fourwire import FourWire
    from busdisplay import BusDisplay
    displayio.release_displays()
    spi = busio.SPI(_pin(pins.get("SCK")), _pin(pins.get("MOSI")))
    bus = FourWire(spi, command=_pin(pins.get("DC")), chip_select=_pin(pins.get("CS")),
                   reset=_pin(pins.get("RST")), baudrate=int(baud) if baud else 24000000)
    return BusDisplay(bus, init, width=w, height=h, rotation=0, backlight_pin=_pin(pins.get("BL")))


try:
    build_display()                # lands in board.DISPLAY slot 0; persists into code.py
    print("boot.py: display ready")
except Exception as e:             # noqa: BLE001 - never brick boot; code.py reports the problem
    print("boot.py: display setup failed:", e)
