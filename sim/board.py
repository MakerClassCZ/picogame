# Fake `board` for the simulator: a display object the engine wraps + button pins.
import _host
class _Display:
    width = _host.W            # follows PICOGAME_SIM_SIZE (e.g. 240x240 for PicoSystem)
    height = _host.H
    auto_refresh = True
    root_group = None
DISPLAY = _Display()
# Pins are just identifiers; digitalio compares them against the host key state.
SW_UP = "SW_UP"; SW_DOWN = "SW_DOWN"; SW_LEFT = "SW_LEFT"; SW_RIGHT = "SW_RIGHT"
SW_A = "SW_A"; SW_B = "SW_B"; SW_X = "SW_X"; SW_Y = "SW_Y"
AUDIO = "AUDIO"
