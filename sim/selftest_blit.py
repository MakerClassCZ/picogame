#!/usr/bin/env python3
"""The blitter's fast path must be indistinguishable from the general one.

_blit has an inlined path for the common case (1:1, no flips, no per-pixel effect, PAL8) that skips
two Python calls per pixel -- worth ~2.5x on a tilemap frame. It is a duplicate of the general loop,
so it can drift from it silently: the failure mode is wrong pixels in a verification screenshot,
which is the one thing the simulator exists to be trusted about.

So: fuzz both against each other over randomized bitmaps, positions (fully on, partly off and fully
off screen), clip rects, flips, scales, palettes, transparency and all four effects. Compares the
whole framebuffer after every blit.

    python3 sim/selftest_blit.py [trials]
"""
import array
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _host
import picogame as pg

TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 4000


def _case(rng):
    """One randomized blit: (bitmap, args) -- built from rng so both runs see the same case."""
    sw, sh = rng.randint(1, 24), rng.randint(1, 24)
    frames = rng.randint(1, 4)
    stride = sw * frames
    npal = rng.randint(1, 6)
    data = bytearray(rng.randrange(0, npal) for _ in range(stride * sh))
    pal = array.array("H", [rng.randrange(0, 65536) for _ in range(npal)])
    bm = pg.Bitmap(data, sw, sh, format=pg.PAL8, palette=pal, frames=frames,
                   stride=stride, transparent=rng.choice([None, 0, 1]))
    W, H = _host.W, _host.H
    eff = rng.random()
    return bm, dict(
        dx0=rng.randint(-sw - 2, W + 2), dy0=rng.randint(-sh - 2, H + 2),
        frame=rng.randrange(frames), flip_x=rng.random() < 0.25, flip_y=rng.random() < 0.25,
        clip=(rng.randint(0, 40), rng.randint(0, 40),
              rng.randint(W - 40, W), rng.randint(H - 40, H)),
        scale=rng.choice([1.0, 1.0, 1.0, 2.0, 0.5]),
        shadow=eff < 0.08,
        flash=rng.randrange(1, 65536) if 0.08 <= eff < 0.16 else None,
        dither=rng.randint(1, 15) if 0.16 <= eff < 0.24 else 0,
        tint=rng.randrange(1, 65536) if 0.24 <= eff < 0.30 else None,
    )


def main():
    _host.configure(backend="pil", max_frames=1)
    fb = _host.fb
    bad = 0
    fast_cases = 0
    for trial in range(TRIALS):
        outputs = []
        for use_fast in (True, False):
            pg._FAST_BLIT = use_fast
            rng = random.Random(trial)            # same case both times
            bm, a = _case(rng)
            for i in range(len(fb)):
                fb[i] = 0
            pg._blit(bm, a["dx0"], a["dy0"], a["frame"], a["flip_x"], a["flip_y"], a["clip"],
                     a["scale"], a["shadow"], a["flash"], a["dither"], a["tint"], False)
            outputs.append(list(fb))
        if outputs[0] != outputs[1]:
            bad += 1
            if bad <= 3:
                diff = [i for i in range(len(fb)) if outputs[0][i] != outputs[1][i]]
                print("MISMATCH trial %d: %d pixels differ, first at %d" % (trial, len(diff), diff[0]))
        else:
            # did this case actually exercise the fast path? (otherwise the trial proves nothing)
            if (a["scale"] == 1.0 and not a["flip_x"] and not a["flip_y"] and not a["shadow"]
                    and not a["flash"] and not a["dither"] and a["tint"] is None):
                fast_cases += 1
    pg._FAST_BLIT = True
    print("selftest_blit: %d trials, %d exercised the fast path, %d mismatches"
          % (TRIALS, fast_cases, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
