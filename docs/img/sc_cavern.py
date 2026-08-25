def play(pad):
    # Bubble-Bobble-style cave platformer: LEFT/RIGHT run, UP jump (grounded), B fire orb.
    for _ in range(5):
        yield from pad.tap("B", n=2, gap=4, base="RIGHT")   # run right, blow an orb
        yield from pad.hold("RIGHT", 10)
        yield from pad.tap("UP", n=4, gap=4, base="RIGHT")  # hop right
        yield from pad.hold("RIGHT", 6)
        yield from pad.tap("B", n=2, gap=4, base="LEFT")    # turn, fire left
        yield from pad.hold("LEFT", 10)
        yield from pad.tap("UP", n=4, gap=4, base="LEFT")   # hop left
        yield from pad.hold("LEFT", 6)
