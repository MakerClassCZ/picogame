def play(pad):
    # Balatro-like poker: A dismisses the how-to, L/R cursor, UP select, A PLAY, A continue.
    yield from pad.tap("A", n=3, gap=8)         # dismiss how-to -> hand
    yield from pad.tap("UP", n=3, gap=5)        # select card under cursor (it lifts)
    yield from pad.tap("RIGHT", n=3, gap=4)
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("RIGHT", n=3, gap=4)
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("RIGHT", n=3, gap=4)
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("A", n=3, gap=6)         # PLAY -> chips x mult SLAM tally
    yield from pad.rest(50)                      # watch the scoring juice
    yield from pad.tap("A", n=3, gap=6)         # continue
    yield from pad.rest(10)
    # play a second hand
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("RIGHT", n=3, gap=4)
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("RIGHT", n=3, gap=4)
    yield from pad.tap("UP", n=3, gap=5)
    yield from pad.tap("A", n=3, gap=6)         # PLAY
    yield from pad.rest(40)
