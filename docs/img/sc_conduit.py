def play(pad):
    # transistor switch puzzle: A (title) -> BUILD board 1. Cursor sits on the base;
    # A toggles the gate open, hold B = POWER -> current floods VCC->LED, LED lights.
    yield from pad.tap("A", n=3, gap=8)           # title -> board B1 "OPEN THE GATE"
    yield from pad.rest(6)
    yield from pad.tap("A", n=3, gap=10)          # open the base under the cursor
    yield from pad.tap("B", n=3, gap=10)          # POWER: watch the current crawl + LED light
    yield from pad.rest(40)
    yield from pad.tap("A", n=3, gap=8)           # advance to board B2 "YOU NEED BOTH" (AND)
    yield from pad.rest(6)
    yield from pad.tap("A", n=3, gap=8)           # open first base
    yield from pad.tap("RIGHT", n=3, gap=5)       # cursor to the second base
    yield from pad.tap("A", n=3, gap=8)           # open it too
    yield from pad.tap("B", n=3, gap=10)          # POWER
    yield from pad.rest(60)                        # current floods both legs -> LED lights
