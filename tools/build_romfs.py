#!/usr/bin/env python3
"""Pack game asset files (the .bin halves of png2picogame --split, or any files) into a
ROMFS image for the picogame asset region, with a hard SIZE GUARD against the region.

  build_romfs.py gnd.bin m2.bin -o assets-mygame.romfs                # pack files
  build_romfs.py assets_dir/ -o assets-mygame.romfs                  # or a whole dir
  build_romfs.py ... --region-kb 64                                  # guard (default 64)
  build_romfs.py ... --uf2 [--uf2-offset 0x10181000]                 # + factory UF2

Deploy on device: copy the .romfs onto CIRCUITPY (or the SD card) and run
`picogame.romfs_program("/assets-mygame.romfs")` - done, `/rom` mounts. The optional
--uf2 output is the FACTORY path (BOOTSEL drag straight to the region offset); note the
UF2 route has NO on-device size check, which is why the guard here is mandatory and why
a too-big image is refused before anything is written.

The ROMFS writer is the pure-python VfsRomWriter from CircuitPython/MicroPython
(tests/extmod/vfs_rom.py, MIT), vendored so this tool is dependency-free.
"""

import argparse
import os
import struct
import sys


# ---- VfsRomWriter (vendored from circuitpython tests/extmod/vfs_rom.py, MIT) ----
class VfsRomWriter:
    ROMFS_HEADER = b"\xd2\xcd\x31"

    ROMFS_RECORD_KIND_UNUSED = 0
    ROMFS_RECORD_KIND_PADDING = 1
    ROMFS_RECORD_KIND_DATA_VERBATIM = 2
    ROMFS_RECORD_KIND_DATA_POINTER = 3
    ROMFS_RECORD_KIND_DIRECTORY = 4
    ROMFS_RECORD_KIND_FILE = 5

    def __init__(self):
        self._dir_stack = [(None, bytearray())]

    def _encode_uint(self, value):
        encoded = [value & 0x7F]
        value >>= 7
        while value != 0:
            encoded.insert(0, 0x80 | (value & 0x7F))
            value >>= 7
        return bytes(encoded)

    def _pack(self, kind, payload):
        return self._encode_uint(kind) + self._encode_uint(len(payload)) + payload

    def _extend(self, data):
        buf = self._dir_stack[-1][1]
        buf.extend(data)
        return len(buf)

    def finalise(self):
        _, data = self._dir_stack.pop()
        encoded_kind = VfsRomWriter.ROMFS_HEADER
        encoded_len = self._encode_uint(len(data))
        if (len(encoded_kind) + len(encoded_len) + len(data)) % 2 == 1:
            encoded_len = b"\x80" + encoded_len
        data = encoded_kind + encoded_len + data
        return data

    def opendir(self, dirname):
        self._dir_stack.append((dirname, bytearray()))

    def closedir(self):
        dirname, dirdata = self._dir_stack.pop()
        dirdata = self._encode_uint(len(dirname)) + bytes(dirname, "ascii") + dirdata
        self._extend(self._pack(VfsRomWriter.ROMFS_RECORD_KIND_DIRECTORY, dirdata))

    def mkfile(self, filename, filedata, extra_payload=b""):
        filename = bytes(filename, "ascii")
        payload = self._encode_uint(len(filename))
        payload += filename
        payload += extra_payload
        payload += self._pack(VfsRomWriter.ROMFS_RECORD_KIND_DATA_VERBATIM, filedata)
        self._dir_stack[-1][1].extend(
            self._pack(VfsRomWriter.ROMFS_RECORD_KIND_FILE, payload))
# ---- end vendored writer ----


UF2_MAGIC0 = 0x0A324655
UF2_MAGIC1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY = 0x00002000
RP2040_FAMILY = 0xE48BFF56


def write_uf2(data, path, base_addr, family=RP2040_FAMILY):
    """Wrap raw bytes as a UF2 targeting `base_addr` (256 B payload per 512 B block)."""
    blocks = (len(data) + 255) // 256
    with open(path, "wb") as f:
        for i in range(blocks):
            chunk = data[i * 256:(i + 1) * 256]
            chunk += b"\x00" * (256 - len(chunk))
            hdr = struct.pack("<8I", UF2_MAGIC0, UF2_MAGIC1, UF2_FLAG_FAMILY,
                              base_addr + i * 256, 256, i, blocks, family)
            f.write(hdr + chunk + b"\x00" * (512 - 32 - 256 - 4)
                    + struct.pack("<I", UF2_MAGIC_END))
    return blocks


def main():
    ap = argparse.ArgumentParser(description="pack asset files -> picogame ROMFS image")
    ap.add_argument("inputs", nargs="+", help="files and/or directories to pack")
    ap.add_argument("-o", "--output", required=True, help="output .romfs image")
    ap.add_argument("--region-kb", type=int, default=64,
                    help="asset region size the image must fit (board's "
                         "CIRCUITPY_PICOGAME_ROMFS_KB; default 64)")
    ap.add_argument("--uf2", action="store_true",
                    help="also emit <output>.uf2 for factory BOOTSEL flashing")
    ap.add_argument("--uf2-offset", type=lambda v: int(v, 0), default=0x10181000,
                    help="UF2 target bus address (default 0x10181000 = "
                         "0x10000000 + 1536K firmware + 4K NVM)")
    args = ap.parse_args()

    files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            for n in sorted(os.listdir(inp)):
                p = os.path.join(inp, n)
                if os.path.isfile(p):
                    files.append((n, p))
        else:
            files.append((os.path.basename(inp), inp))
    if not files:
        sys.exit("nothing to pack")

    wr = VfsRomWriter()
    total = 0
    for name, path in files:
        with open(path, "rb") as f:
            data = f.read()
        wr.mkfile(name, data)
        total += len(data)
        print("  + %-24s %7d B" % (name, len(data)))
    img = wr.finalise()

    limit = args.region_kb * 1024
    if len(img) > limit:
        sys.exit("ERROR: image is %d B but the region holds %d B (%d KB) - it would "
                 "overflow into the FAT drive. Trim assets or build a bigger-region "
                 "firmware flavor." % (len(img), limit, args.region_kb))

    with open(args.output, "wb") as f:
        f.write(img)
    # sidecar manifest (input names + sha1): lets tools/sync.py flag a STALE image when a
    # .bin changes after packing (content-based, matching the sync.py philosophy)
    import hashlib
    with open(args.output + ".manifest", "w") as mf:
        for name, path in files:
            with open(path, "rb") as f:
                mf.write("%s %s\n" % (hashlib.sha1(f.read()).hexdigest(), name))
    print("wrote %s: %d files, %d B payload -> %d B image (%.0f%% of the %d KB region)" % (
        args.output, len(files), total, len(img), 100.0 * len(img) / limit, args.region_kb))

    if args.uf2:
        uf2_path = args.output + ".uf2"
        n = write_uf2(img, uf2_path, args.uf2_offset)
        print("wrote %s: %d UF2 blocks @ 0x%08x (factory path - prefer "
              "picogame.romfs_program() for normal deploys)" % (uf2_path, n, args.uf2_offset))


if __name__ == "__main__":
    main()
