def play(pad):
    # A clears the title, then roam a slow loop so the torch light sweeps the arena; dash each lap
    yield from pad.tap("A", n=3, gap=4)
    for _ in range(3):
        yield from pad.hold("RIGHT", 16)
        yield from pad.hold("DOWN", 16)
        yield from pad.tap("X", n=2, gap=6, base="DOWN")   # dash
        yield from pad.hold("LEFT", 16)
        yield from pad.tap("A", n=2, gap=2)                # confirm any level-up popup
        yield from pad.hold("UP", 16)
