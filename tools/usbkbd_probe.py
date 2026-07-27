# USB KEYBOARD probe (Fruit Jam). Copy as CIRCUITPY/code.py, open the serial
# console and press keys. Walks the whole chain and reports where it breaks:
#   1) enumerate USB devices (VID/PID + strings)
#   2) adafruit_usb_host_descriptors present? boot-keyboard endpoint found?
#   3) raw read loop on the found endpoint - prints every report change
#   4) the actual picogame_usbkbd driver - prints the decoded logical mask
# Send the whole serial log back.
import time

import usb.core

print("=== picogame USB keyboard probe ===")

try:
    import adafruit_usb_host_descriptors as ahd
    print("adafruit_usb_host_descriptors: OK")
except ImportError:
    ahd = None
    print("adafruit_usb_host_descriptors: MISSING (combo dongles will not be found; "
          "circup install adafruit_usb_host_descriptors)")

print("\n-- devices on the bus --")
found = []
for d in usb.core.find(find_all=True):
    try:
        names = "%s / %s" % (d.manufacturer, d.product)
    except Exception:
        names = "(strings unreadable)"
    print("  %04x:%04x  %s" % (d.idVendor, d.idProduct, names))
    ep = None
    if ahd is not None:
        try:
            iface, ep = ahd.find_boot_keyboard_endpoint(d)
            print("     boot-keyboard endpoint: iface=%s ep=%s"
                  % (iface, hex(ep) if ep else ep))
            if ep:
                globals()["KIFACE"] = iface
        except Exception as e:
            print("     descriptor walk failed: %r" % e)
    if ep:
        found.append((d, ep))

if not found:
    print("\nNo boot-keyboard endpoint found.")
    if ahd is None:
        print("-> install adafruit_usb_host_descriptors into /lib first")
    print("-> trying fallback: first NON-gamepad device, endpoint 0x81")
    for d in usb.core.find(find_all=True):
        if (d.idVendor, d.idProduct) != (0x081F, 0xE401):
            found.append((d, 0x81))
            break

if not found:
    raise SystemExit("no usable device - is the dongle in the HOST port?")

dev, ep = found[0]
KIFACE = globals().get("KIFACE", 1)     # interface from step 2 (combo dongle: keyboard != iface 0)

print("\n-- config descriptor --")
KBD_CANDS = []                          # (iface, IN ep) of every keyboard-proto interface
try:
    cfg = bytearray(256)
    n = dev.ctrl_transfer(0x80, 6, 0x0200, 0, cfg, timeout=200)   # GET_DESCRIPTOR: CONFIG
    i = 0
    cur_if = cur_proto = None
    while i + 1 < n:
        ln, dt = cfg[i], cfg[i + 1]
        if ln == 0:
            break
        d = cfg[i:i + ln]
        if dt == 4:
            print("  iface %d alt %d: class %02x sub %02x proto %02x (%d EPs)"
                  % (d[2], d[3], d[5], d[6], d[7], d[4]))
            cur_if = d[2]
            cur_proto = d[7] if d[5] == 3 else None
        elif dt == 5:
            print("     ep 0x%02x attr %02x maxpkt %d interval %d"
                  % (d[2], d[3], d[4] | (d[5] << 8), d[6]))
            if cur_proto == 1 and d[2] & 0x80:
                KBD_CANDS.append((cur_if, d[2]))
        i += ln
except Exception as e:
    print("  GET_DESCRIPTOR: %r" % e)

for i in (KIFACE, 0):
    try:
        if dev.is_kernel_driver_active(i):
            dev.detach_kernel_driver(i)
            print("   (kernel driver detached from iface %d)" % i)
    except Exception as e:
        print("   detach iface %d: %r" % (i, e))
dev.set_configuration()


def _phase(tag, secs=10):
    buf = bytearray(16)                   # 16 B: catches report-ID formats too
    last = None
    ok = to = err = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < secs:
        try:
            n = dev.read(ep, buf, timeout=3)
            ok += 1
            b = bytes(buf[:n])
            if b != last:
                print("   %7.3f  report(%dB) %s" % (time.monotonic() - t0, n, b.hex()))
                last = b
        except usb.core.USBTimeoutError:
            to += 1
        except Exception as e:
            err += 1
            if err <= 3:
                print("   %7.3f  ERR %r" % (time.monotonic() - t0, e))
            time.sleep(0.2)
        time.sleep(0.01)
    print(">>> %s: ok=%d timeouts=%d errs=%d" % (tag, ok, to, err))
    return ok


CANDS = tuple(KBD_CANDS) or ((1, 0x82), (2, 0x83))   # from the descriptor; fallback = Rapoo pair
LIVE = {}                               # (iface, ep) -> delivered report count
for kif, kep in CANDS:
    for i in (kif,):
        try:
            if dev.is_kernel_driver_active(i):
                dev.detach_kernel_driver(i)
                print("   (kernel driver detached from iface %d)" % i)
        except Exception as e:
            print("   detach iface %d: %r" % (i, e))
    ep = kep
    print("\n-- iface %d ep 0x%02x: report protocol (8 s, press keys) --" % (kif, kep))
    LIVE[(kif, kep)] = LIVE.get((kif, kep), 0) + (_phase("iface%d/plain" % kif, 8) or 0)
    try:
        dev.ctrl_transfer(0x21, 0x0B, 0, kif, None, timeout=50)
        print("   SET_PROTOCOL boot OK (iface %d)" % kif)
    except Exception as e:
        print("   SET_PROTOCOL: %r" % e)
    print("-- iface %d ep 0x%02x: boot protocol (8 s, press keys) --" % (kif, kep))
    LIVE[(kif, kep)] = (LIVE.get((kif, kep), 0) or 0) + (_phase("iface%d/boot" % kif, 8) or 0)

print("\n-- D) stdin test (10 s, press keys on the TESTED keyboard) --")
print("   (if bytes show up here, the supervisor STILL consumes the keyboard")
print("    and detach_kernel_driver did not really release it)")
try:
    import supervisor as _sup
    import sys as _sys
    got = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 10:
        n = _sup.runtime.serial_bytes_available
        if n:
            data = _sys.stdin.read(n)
            got += len(data)
            print("   %7.3f  stdin: %r" % (time.monotonic() - t0, data))
        time.sleep(0.02)
    print(">>> D: stdin bytes total %d %s"
          % (got, "(supervisor KEEPS the keyboard!)" if got else "(stdin quiet - detach worked)"))
except Exception as e:
    print("   stdin test failed: %r" % e)

print("\n-- RECOMMENDATION --")
_best = None
for _k in LIVE:
    if _best is None or LIVE[_k] > LIVE[_best]:
        _best = _k
if _best is not None and LIVE[_best] > 0:
    if _best == CANDS[0] and len(CANDS) > 1:
        print("   the keyboard talks on the default interface - nothing to configure")
    else:
        print("   add this line to CIRCUITPY/settings.toml:")
        print('   PICOGAME_USBKBD_EP = "%d:0x%02x"' % _best)
else:
    print("   no endpoint delivered a report - is the keyboard on/paired?")

print("\n-- picogame_usbkbd driver (30 s, press keys) --")
try:
    import picogame_usbkbd
    print("   VERSION:", picogame_usbkbd.VERSION)
    k = picogame_usbkbd.UsbKbd()
    print("   attach OK, mapped mask: 0x%04x" % k.mapped)
    last_m = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < 30:
        m = k.read()
        if m != last_m:
            print("%7.3f  mask 0x%04x" % (time.monotonic() - t0, m))
            last_m = m
        time.sleep(0.03)
except Exception as e:
    print("   DRIVER FAIL: %r" % e)
print("=== end ===")
