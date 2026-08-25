def play(pad):
    # Tetris: L/R move (just_pressed), A rotate, DOWN soft-drop. Pieces auto-fall.
    # place a few pieces to different sides so the well fills visibly.
    for i in range(7):
        yield from pad.tap("A", n=2, gap=3)          # rotate
        side = "LEFT" if i % 2 == 0 else "RIGHT"
        yield from pad.tap(side, n=2, gap=3)
        yield from pad.tap(side, n=2, gap=3)
        yield from pad.hold("DOWN", 12)              # soft-drop + lock
        yield from pad.rest(5)
