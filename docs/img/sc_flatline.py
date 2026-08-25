def play(pad):
    # PCB fault-finder: D-pad moves the probe between test points, A measures a node
    # (reads HIGH/LOW/FLOAT into the HUD), then Y = ACCUSE a part + confirm how it failed.
    for _ in range(3):
        yield from pad.tap("A", n=2, gap=6)      # measure the node under the probe
        yield from pad.tap("RIGHT", n=2, gap=6)  # step to the next pad
    yield from pad.tap("DOWN", n=2, gap=6)
    yield from pad.tap("A", n=2, gap=6)
    yield from pad.tap("LEFT", n=2, gap=6)
    yield from pad.tap("A", n=2, gap=6)
    yield from pad.tap("Y", n=3, gap=8)          # switch to ACCUSE
    yield from pad.tap("RIGHT", n=2, gap=6)      # move the accuse cursor onto a part
    yield from pad.tap("A", n=3, gap=8)          # pick it
    yield from pad.tap("DOWN", n=2, gap=6)       # cycle the failure mode
    yield from pad.tap("A", n=3, gap=8)          # confirm -> reveal
    yield from pad.rest(24)
    # next board: probe another handful of nodes
    for _ in range(4):
        yield from pad.tap("A", n=2, gap=6)
        yield from pad.tap("RIGHT", n=2, gap=6)
    yield from pad.tap("DOWN", n=2, gap=6)
    yield from pad.tap("A", n=2, gap=6)
    yield from pad.rest(20)
