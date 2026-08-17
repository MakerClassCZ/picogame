# Fake `microcontroller`: NVM as an in-memory bytearray (resets each run).
nvm = bytearray(4096)


class _PinNS:
    """Permissive pin namespace: any GPIOn resolves (the sim never drives real pins;
    picogame_input._resolve_pin needs the lookup to succeed like on a device)."""

    def __getattr__(self, name):
        if name.startswith("GPIO") and name[4:].isdigit():
            return "SIM_" + name
        raise AttributeError(name)


pin = _PinNS()
