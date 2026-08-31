def play(pad):
    # Picotris now boots to a TITLE screen: A starts. Then: L/R move (hold = DAS auto-shift),
    # A rotate, DOWN soft-drop (lock delay keeps the piece adjustable for ~0.5 s on the ground).
    yield from pad.rest(6)
    yield from pad.tap("A", n=2, gap=6)              # leave the title
    for i in range(7):
        yield from pad.tap("A", n=2, gap=3)          # rotate
        side = "LEFT" if i % 2 == 0 else "RIGHT"
        yield from pad.hold(side, 14)                # DAS: hold walks the piece over
        yield from pad.rest(3)
        yield from pad.hold("DOWN", 16)              # soft-drop; lock delay then locks it
        yield from pad.rest(8)
