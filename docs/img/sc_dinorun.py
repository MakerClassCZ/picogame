def play(pad):
    # endless runner: jump on a steady rhythm (open-loop). Long enough for a ~6-7 s clip;
    # capped by --frames so it never ends on GAME OVER.
    yield from pad.rest(6)
    for _ in range(22):
        yield from pad.tap("UP", n=2, gap=8)   # jump ~every 10 frames; overlapping air time keeps
                                               # the dino hopping continuously (double-jumps clear rocks)
