# Fruit Jam USB gamepad PROBE. Plug the gamepad into the USB-HOST port (the horizontal USB-A on the
# Fruit Jam, NOT the CIRCUITPY data port). Watch the serial console: it lists every USB device, then
# prints the HID report bytes ONLY WHEN THEY CHANGE, marking which byte moved. Press each button /
# wiggle each stick one at a time and note the byte + value -> that is the mapping we build the driver
# from. Send the whole serial log back.
#
# Optional (better endpoint auto-detect): install `adafruit_usb_host_descriptors` in CIRCUITPY/lib
# (circup install adafruit_usb_host_descriptors). Without it the probe falls back to endpoint 0x81.
import time
import usb.core

print("=== Fruit Jam USB gamepad probe ===")

# --- make sure the host port has 5V (auto on Fruit Jam; force it if the pin is still free) ---
try:
    import board
    import digitalio
    _pwr = digitalio.DigitalInOut(board.USB_HOST_5V_POWER)
    _pwr.switch_to_output(value=True)
    print("USB_HOST_5V_POWER forced high")
except Exception as e:
    print("5V power: already managed / n/a ->", repr(e))

# --- make sure the USB host port is running (auto on Fruit Jam; construct it if not) ---
try:
    import usb_host
    import board
    try:
        usb_host.Port(board.USB_HOST_DATA_PLUS, board.USB_HOST_DATA_MINUS)
        print("usb_host.Port started")
    except Exception as e:
        print("usb_host.Port: already running or n/a ->", repr(e))
except Exception as e:
    print("usb_host import:", repr(e))

# --- enumerate everything so we see the pad's VID/PID + strings ---
dev = None
print("--- USB devices ---")
for d in usb.core.find(find_all=True):
    try:
        mfg = d.manufacturer
    except Exception:
        mfg = "?"
    try:
        prod = d.product
    except Exception:
        prod = "?"
    print("  VID=%04x PID=%04x  %s  %s" % (d.idVendor, d.idProduct, mfg, prod))
    if dev is None:
        dev = d          # take the first device; if you have a hub, set VID/PID by hand below
if dev is None:
    print("NO USB device found - is the pad in the HOST port and powered? (5V jumper)")
    while True:
        time.sleep(1)

# To force a specific pad instead of "first found", uncomment + fill in from the list above:
# dev = usb.core.find(idVendor=0x0000, idProduct=0x0000)

print("--- using VID=%04x PID=%04x ---" % (dev.idVendor, dev.idProduct))

# --- claim it away from any built-in driver + configure ---
try:
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
        print("detached kernel driver on interface 0")
except Exception as e:
    print("detach_kernel_driver:", repr(e))
try:
    dev.set_configuration()
    print("set_configuration OK")
except Exception as e:
    print("set_configuration:", repr(e))

# --- find the interrupt-IN endpoint + report length (via descriptors if available, else 0x81/64) ---
ep_addr = 0x81
report_len = 8          # DragonRise 081f:e401 sends 8-byte reports; a bigger buffer concatenates them
try:
    import adafruit_usb_host_descriptors as ud
    cfg = ud.get_configuration_descriptor(dev, 0)
    i = 0
    while i < len(cfg):
        blen = cfg[i]
        btype = cfg[i + 1]
        if btype == 0x05:                      # ENDPOINT descriptor
            addr = cfg[i + 2]
            attr = cfg[i + 3]
            mps = cfg[i + 4] | (cfg[i + 5] << 8)
            if (addr & 0x80) and (attr & 0x03) == 0x03:   # IN + interrupt
                ep_addr = addr
                report_len = mps
                print("found interrupt-IN endpoint 0x%02x, max packet %d" % (ep_addr, report_len))
                break
        i += blen if blen else 1
    else:
        print("no interrupt-IN endpoint in descriptor; using 0x81/64")
except ImportError:
    print("adafruit_usb_host_descriptors not installed; assuming endpoint 0x81, 64 bytes")
except Exception as e:
    print("descriptor parse failed (%r); assuming 0x81/64" % e)

if report_len < 1 or report_len > 64:
    report_len = 64

# --- read loop: print the report only when it changes, flag the byte(s) that moved ---
print("--- reading endpoint 0x%02x (%d bytes). Press buttons / move sticks now ---" % (ep_addr, report_len))
buf = bytearray(report_len)
prev = None
while True:
    try:
        n = dev.read(ep_addr, buf, timeout=200)
    except usb.core.USBTimeoutError:
        continue                               # no new report this window
    except Exception as e:
        print("read error:", repr(e))
        time.sleep(0.5)
        continue
    cur = bytes(buf[:n])
    if cur != prev:
        # hex dump + which byte indexes differ from the previous report
        hexs = " ".join("%02x" % b for b in cur)
        if prev is None:
            diff = "(first report, len=%d)" % n
        else:
            changed = [str(k) for k in range(min(len(cur), len(prev))) if cur[k] != prev[k]]
            diff = "changed byte#: " + (",".join(changed) if changed else "(len change)")
        print("%s   %s" % (hexs, diff))
        prev = cur
