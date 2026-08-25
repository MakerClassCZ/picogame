def play(pad):
    # B begins the 120-frame countdown; hold gas through it, then drive with brief steering corrections
    yield from pad.tap("B", n=3, gap=3)
    yield from pad.hold("B", 130)                    # sit on the gas through the countdown + get rolling
    for _ in range(10):
        yield from pad.hold("B", 16)                 # straight
        yield from pad.hold("B,RIGHT", 5)            # short correction (never a long turn)
        yield from pad.hold("B", 16)
        yield from pad.hold("B,LEFT", 5)
