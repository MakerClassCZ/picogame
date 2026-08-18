# Fake `supervisor` for the simulator: the small slice of CircuitPython's module the engine and
# the helper libs actually use, so the sim exercises the SAME code path as the device.
#
# Why it exists: picogame_game.display()/screen() take the display from `supervisor.runtime.display`
# and nowhere else - that one source is the contract on every platform. Without this shim the sim
# would have no display at all.
#
# Deliberately NOT provided: set_next_code_file() / reload(). The sim runs one program in one
# process and cannot chain to another code file; picogame_launcher checks for those two by name
# and prints what it WOULD run instead of pretending to reboot.
import time

import board


class _Runtime:
    """`supervisor.runtime`. `display` proxies the sim's board display, so a program that sets it
    (a launcher, picogame_game.open_framebuffer) is visible to everything reading it afterwards."""

    serial_connected = True
    usb_connected = True
    run_reason = "STARTUP"

    @property
    def display(self):
        return getattr(board, "DISPLAY", None)

    @display.setter
    def display(self, value):
        board.DISPLAY = value


runtime = _Runtime()

_MASK = (1 << 29) - 1


def ticks_ms():
    """Milliseconds, wrapping at 2**29 like CircuitPython's - so picogame_clock runs its real
    wrap-safe arithmetic here instead of the CPython fallback."""
    return int(time.monotonic() * 1000) & _MASK
