def play(pad):
    # snake puzzle. Title splash auto-holds ~90 frames headless; then the loco auto-moves
    # (~1 tile / ~14 frames) and arrows set its heading. Loco starts at (1,5) facing RIGHT;
    # item bands sit on rows 2/5/8. Sweep row 5 then row 8, growing the train (no 180 turns).
    yield from pad.rest(95)                # wait out the title splash
    yield from pad.hold("RIGHT", 150)      # run E along row 5, eating its items (train grows)
    yield from pad.hold("DOWN", 42)        # drop to the row-8 band
    yield from pad.hold("LEFT", 120)       # sweep W along row 8
    yield from pad.hold("UP", 24)
