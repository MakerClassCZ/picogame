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
# player-2 pins (SIM ONLY): let a local-multiplayer demo drive a second player from a second key
# cluster (IJKL + P) on the one desktop keyboard. Real boards don't have these - a game maps them
# only when no USB pad is present, and _resolve_pin skips a missing board pin on hardware.
SW2_UP = "SW2_UP"; SW2_DOWN = "SW2_DOWN"; SW2_LEFT = "SW2_LEFT"; SW2_RIGHT = "SW2_RIGHT"; SW2_A = "SW2_A"
