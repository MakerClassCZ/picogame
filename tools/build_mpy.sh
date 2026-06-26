#!/usr/bin/env bash
# Precompile the picogame Python helpers (lib/*.py) to .mpy bytecode.
#
# .mpy files import faster and use less RAM on device (no on-board source parse) --
# the single biggest win for the helper LIBRARY, since the heavy per-pixel work is
# already in the C engine and the Python helpers have little hot-path left to tune.
#
# mpy-cross MUST match the CircuitPython version on the board (mpy ABI changes
# between releases). We build it from the same source tree.
#
#   tools/build_mpy.sh           # -> lib/*.mpy  (copy these to CIRCUITPY/lib instead of .py)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CP="$ROOT/circuitpython"
MPYCROSS="$CP/mpy-cross/build/mpy-cross"

if [ ! -x "$MPYCROSS" ]; then
    echo "building mpy-cross (matches this CircuitPython tree)..."
    make -C "$CP/mpy-cross" -j"$(nproc)"
fi

mkdir -p "$ROOT/lib/mpy"
for f in "$ROOT"/lib/picogame_*.py; do
    name="$(basename "$f" .py)"
    "$MPYCROSS" -s "$name.py" -o "$ROOT/lib/mpy/$name.mpy" "$f"   # -s: embed clean basename, not the abs build path
    echo "  $name.mpy"
done
echo "done -> lib/mpy/  (deploy these to CIRCUITPY/lib/)"
