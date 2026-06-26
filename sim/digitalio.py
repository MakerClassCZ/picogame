# Fake `digitalio`: a button reads as active-low from the host's pressed-pin set.
import _host
class Pull:
    UP = "UP"; DOWN = "DOWN"
class Direction:
    INPUT = "INPUT"; OUTPUT = "OUTPUT"
class DigitalInOut:
    def __init__(self, pin):
        self._pin = pin
    def switch_to_input(self, pull=None):
        pass
    def deinit(self):
        pass
    @property
    def value(self):
        return self._pin not in _host.pressed_pins   # active-low: pressed -> False
