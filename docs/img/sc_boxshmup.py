def play(pad):
    # 1-bit horizontal shmup: A clears the title, then D-pad flies + A fires cannons.
    yield from pad.tap("A", n=3, gap=8)              # title -> play
    for i in range(9):
        v = "UP" if i % 2 == 0 else "DOWN"
        yield from pad.tap("A", n=5, gap=2, base="RIGHT")     # slide right, fire
        yield from pad.hold(v + ",RIGHT", 8)
        yield from pad.tap("A", n=5, gap=2, base="LEFT")      # weave left, fire
        yield from pad.hold(v + ",LEFT", 8)
