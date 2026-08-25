def play(pad):
    # dives straight in (start screen waits A), then dive below the surface and hunt in laps
    yield from pad.tap("A", n=3, gap=4)              # A begins play
    yield from pad.hold("DOWN", 16)                  # dive well below the surface
    for _ in range(2):
        for _ in range(3):
            yield from pad.tap("B", n=3, gap=7, base="RIGHT")   # swim right, fire one torpedo
        yield from pad.hold("UP,RIGHT", 8)           # weave up
        yield from pad.tap("B", n=3, gap=7, base="RIGHT")
        yield from pad.hold("DOWN,RIGHT", 8)         # weave down
        yield from pad.tap("B", n=3, gap=7, base="RIGHT")
        yield from pad.hold("LEFT", 18)              # turn back before the wall
        yield from pad.tap("B", n=3, gap=7, base="LEFT")
        yield from pad.hold("UP,LEFT", 8)
        yield from pad.tap("B", n=3, gap=7, base="LEFT")
        yield from pad.hold("RIGHT", 16)             # swing back out for the next lap
