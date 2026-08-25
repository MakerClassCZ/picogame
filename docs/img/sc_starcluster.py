def play(pad):
    # space trader. Title splash auto-holds ~90 frames headless, then drops onto the galaxy MAP
    # (cursor already on the docked home system Vetis). DOWN selects Raron - a "!!" DANGER hop -
    # so A jumps into a cockpit pirate ambush: sweep the crosshair + fire the (overheating) gun.
    yield from pad.rest(95)                       # wait out the title splash
    yield from pad.tap("DOWN", n=3, gap=8)        # pick the risky linked system
    yield from pad.tap("A", n=3, gap=10)          # JUMP -> ambush
    for i in range(12):                           # cockpit: aim across the squad and fire
        d = "RIGHT" if i % 2 == 0 else "LEFT"
        v = "DOWN" if i % 2 == 0 else "UP"
        yield from pad.tap("A", n=4, gap=3, base=d)
        yield from pad.hold(v + "," + d, 6)
    yield from pad.rest(20)
