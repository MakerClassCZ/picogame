# picogame persistence helper: a tiny structured store backed by
# microcontroller.nvm - a reserved flash region (4 KB on RP2040) writable
# straight from code.py. Unlike the CIRCUITPY filesystem (read-only from code
# unless boot.py remounts it, and then the USB host can't write), NVM needs no
# boot.py and no remount, and it survives a reboot AND a filesystem wipe.
# No firmware change (CIRCUITPY_NVM is on by default for rp2040).
#
# NVM is a SINGLE shared region across every program on the device, so each game
# must pass its own `key`. The key is stored in the header and verified on load:
# if another game (or stale data) wrote the slot, the key won't match and load()
# safely returns this game's defaults instead of misreading foreign bytes.
#
#   save = picogame_save.Save("arkanoid", {"hiscore": ("I", 0), "level": ("B", 1)})
#   data = save.load()              # -> defaults unless OUR key + checksum match
#   data["hiscore"] = 1200
#   save.save(data)                 # persists; survives power-off
#
# Schema: an ordered dict of name -> (struct format char, default). Common chars:
#   "B" 0..255, "H" 0..65535, "I" 0..2^32-1, "b/h/i" signed. Header is
#   2-byte magic + 1-byte version + 4-byte key hash + fields + 1-byte checksum;
#   the whole thing must fit NVM. Games that must coexist use distinct `offset`s.
#
# FLASH WEAR: each save() erases+writes a flash sector. Save on meaningful events
# (game over, new highscore, settings change), NOT every frame.

import microcontroller
import struct

from micropython import const

_NVM = microcontroller.nvm
_MAGIC = b"PG"            # format marker
_VERSION = const(1)


def _key_hash(key):
    """FNV-1a 32-bit of the game key (str or bytes) -> 4 stored bytes."""
    if isinstance(key, str):
        key = key.encode("utf-8")
    h = 0x811C9DC5
    for x in key:
        h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
    return h


class Save:
    def __init__(self, key, schema, *, offset=0):
        if _NVM is None:
            raise RuntimeError("NVM not available on this build")
        self.schema = schema
        self.offset = offset
        self._names = list(schema.keys())
        self._keyhash = _key_hash(key)
        self._fmt = "<" + "".join(c for (c, _d) in schema.values())
        self._head = len(_MAGIC) + 1 + 4                  # magic + version + key hash
        self._size = self._head + struct.calcsize(self._fmt) + 1   # + checksum byte
        if offset + self._size > len(_NVM):
            raise ValueError("save data (%d B) does not fit in NVM (%d B)"
                             % (self._size, len(_NVM)))

    def _checksum(self, b):
        s = 0
        for x in b:
            s = (s + x) & 0xFF
        return s

    def defaults(self):
        """A fresh dict of the schema's default values."""
        return {n: d for n, (_c, d) in self.schema.items()}

    def _header(self):
        return _MAGIC + bytes([_VERSION]) + struct.pack("<I", self._keyhash)

    def load(self):
        """Return the stored values, or defaults if the slot is blank, corrupt,
        or belongs to a different game (key mismatch)."""
        raw = _NVM[self.offset:self.offset + self._size]
        body = raw[:-1]
        if bytes(body[:self._head]) != self._header() or self._checksum(body) != raw[-1]:
            return self.defaults()
        vals = struct.unpack(self._fmt, body[self._head:])
        return dict(zip(self._names, vals))

    def save(self, values):
        """Persist a dict of values (missing keys fall back to defaults)."""
        ordered = [values.get(n, self.schema[n][1]) for n in self._names]
        body = self._header() + struct.pack(self._fmt, *ordered)
        blob = body + bytes([self._checksum(body)])
        _NVM[self.offset:self.offset + len(blob)] = blob

    def reset(self):
        """Write the defaults back to NVM (under this game's key)."""
        self.save(self.defaults())
