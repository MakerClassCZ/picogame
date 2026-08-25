def play(pad):
    # bioluminescent tower defense. Title splash auto-holds ~90 frames headless; then
    # PLAN: D-pad move cursor, A build, X cycle type, Y release wave. Cursor starts on (6,4).
    yield from pad.rest(95)                       # wait out the title splash
    yield from pad.tap("A", n=3, gap=6)           # build a Sentinel at the start cell
    for _ in range(3):
        yield from pad.tap("RIGHT", n=2, gap=3)   # move cursor along the build row
    yield from pad.tap("A", n=3, gap=6)           # build another
    for _ in range(3):
        yield from pad.tap("LEFT", n=2, gap=3)
    yield from pad.tap("DOWN", n=2, gap=3)
    yield from pad.tap("DOWN", n=2, gap=3)
    yield from pad.tap("A", n=3, gap=6)           # a third, second row
    yield from pad.tap("Y", n=3, gap=6)           # RELEASE the wave
    yield from pad.rest(220)                       # sentinels auto-fire on the incoming bloom
