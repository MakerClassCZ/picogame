# Desktop stand-in for CircuitPython's ``storage`` module: only what games touch on the PC.
import os


def map_file(file):
    """Sim parity for storage.map_file: the file as a tuple of read-only memoryviews, one per
    contiguous flash run on the device. The PC has no flash window, so this is a RAM copy - but
    the SHAPE is the device's, so seam code runs here too. Takes an OPEN binary file, like the
    firmware (which reads the cluster map the file already carries). PICOGAME_SIM_XIP_RUNS=N
    fakes N runs split at 512-byte boundaries. Raises OSError(EINVAL) on an empty file."""
    if not hasattr(file, "read"):
        raise TypeError("file must be of type FileIO, not %s" % type(file).__name__)
    if getattr(file, "closed", False) or "+" in getattr(file, "mode", "rb") or "r" not in getattr(file, "mode", "rb"):
        raise OSError(22, "EINVAL")              # closed, or not open for reading only
    file.seek(0)
    data = file.read()
    if not data:
        return ()
    n = int(os.environ.get("PICOGAME_SIM_XIP_RUNS", "1") or 1)
    blocks = (len(data) + 511) // 512
    n = max(1, min(n, blocks))
    bounds = [0]
    for i in range(1, n):
        bounds.append(min(len(data), (blocks * i // n) * 512))
    bounds.append(len(data))
    return tuple(memoryview(data[x:y]) for x, y in zip(bounds, bounds[1:]) if y > x)
