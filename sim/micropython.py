# Desktop-sim shim for CircuitPython's `micropython` module, so libs that do
# `from micropython import const` (a no-op compile hint) run unchanged under CPython.
def const(x):
    return x


def native(f):
    return f


def viper(f):
    return f


def opt_level(*a):
    return 0
