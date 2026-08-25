# picogame WIRING PROBE. Copy to CIRCUITPY as code.py, open the serial console. It (1) scans I2C for
# peripherals, then (2) shows LIVE which GPIO reads "pressed" as you push each button - so you read off
# the pin for each and build the PICOGAME_BUTTONS line. Press ONE button at a time.
#
# EDIT the config for your board: set PULL, and put every pin you use for the display / SPI / I2C /
# audio into SKIP (so the probe doesn't fight them and a driven pin doesn't look "pressed").
import time
import board
import digitalio

# ---------------- config ----------------
PULL = "up"                                    # "up" = button wired to GND, pressed reads LOW (usual);
#                                                "down" = wired to 3V3, pressed reads HIGH
CANDIDATES = ["GP%d" % i for i in range(0, 29)]   # Pico GP0..GP28; trim to your board if different
SKIP = ["GP23", "GP24", "GP25"]                # Pico internals (SMPS mode / VBUS sense / LED); ADD your
#                                                display/SPI/I2C/audio pins here too
I2C_PINS = None                                # bare board with no default I2C: set (SCL, SDA) e.g.
#                                                ("GP5", "GP4"); leave None to try board.I2C/STEMMA_I2C


def scan_i2c():
    i2c = None
    for maker in (getattr(board, "STEMMA_I2C", None), getattr(board, "I2C", None)):
        if maker is None:
            continue
        try:
            i2c = maker()
            break
        except Exception:
            i2c = None
    if i2c is None and I2C_PINS is not None:
        try:
            import busio
            i2c = busio.I2C(getattr(board, I2C_PINS[0]), getattr(board, I2C_PINS[1]))
        except Exception as e:
            print("I2C: could not open (edit I2C_PINS):", repr(e))
            return
    if i2c is None:
        print("I2C: no default bus (set I2C_PINS for a bare board)")
        return
    while not i2c.try_lock():
        pass
    try:
        found = ["0x%02x" % a for a in i2c.scan()]
    finally:
        i2c.unlock()
    print("I2C devices:", " ".join(found) if found else "(none)", " [0x18 = TLV320 audio DAC]")


def _num(name):
    try:
        return int(name[2:])            # "GP7" -> 7, for natural sort
    except ValueError:
        return 999


print("=== picogame wiring probe ===")
scan_i2c()                              # BEFORE claiming GPIO below - else the I2C pins are already
#                                         held as DigitalInOut and board.I2C()/busio would fail "in use"

pull = digitalio.Pull.DOWN if PULL == "down" else digitalio.Pull.UP
active_low = pull is digitalio.Pull.UP
ios = []
for name in CANDIDATES:
    if name in SKIP:
        continue
    pin = getattr(board, name, None)
    if pin is None:
        continue
    try:
        io = digitalio.DigitalInOut(pin)
        io.switch_to_input(pull=pull)
    except Exception:
        continue                        # pin already in use / not exposed -> skip
    ios.append((name, io))

print("watching %d pins (PULL=%s). Press ONE button at a time; note the GP that appears," % (len(ios), PULL))
print("then assemble the line by hand (skeleton below):")
print('   PICOGAME_BUTTONS = "UP=GP? DOWN=GP? LEFT=GP? RIGHT=GP? A=GP? B=GP? ..."')
print('   PICOGAME_PULL = "%s"' % PULL)

prev = None
while True:
    now = [name for name, io in ios if ((not io.value) if active_low else io.value)]
    now.sort(key=_num)
    key = tuple(now)
    if key != prev:
        print("  pressed:", " ".join(now) if now else "(none)")
        prev = key
    time.sleep(0.03)
