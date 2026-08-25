def play(pad):
    # run right with timed jumps + shots, then turn around and head back left
    for _ in range(6):
        yield from pad.tap("UP", n=5, gap=12, base="RIGHT")  # run right, jump
        yield from pad.tap("A", n=2, gap=8, base="RIGHT")    # shoot on the move
    for _ in range(4):
        yield from pad.tap("UP", n=5, gap=12, base="LEFT")   # turn around, run left, jump
        yield from pad.tap("A", n=2, gap=8, base="LEFT")
