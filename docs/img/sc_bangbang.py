def play(pad):
    # turn-based artillery. X starts DEMO mode (AI vs AI) so the duel plays itself:
    # barrels swing to aim, shells arc across, terrain craters + explosion shake.
    yield from pad.tap("X", n=3, gap=6)
    yield from pad.rest(600)
