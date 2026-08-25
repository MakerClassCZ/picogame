def play(pad):
    # glide left/right across the sky, one SHORT A burst per leg then a long, calm glide
    # (long A holds overheat the gun; wide legs so the ship glides, not darts)
    for i in range(9):
        d = "LEFT" if i % 2 == 0 else "RIGHT"
        yield from pad.tap("A", n=4, gap=2, base=d)   # brief burst as the leg starts
        yield from pad.hold(d, 20)                    # long, calm glide in that direction
