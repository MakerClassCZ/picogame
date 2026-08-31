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
    bad += tilemap_trials(pg, _host)
    return 1 if bad else 0



# --------------------------------------------------------------------------------------------
# Tilemap._draw has its own fast path: it culls the tile loop to what the clip rect can reach.
# That is a SECOND place a drawing shortcut can drop pixels, and the first version of it did -
# a TRANSPOSED tile on a non-square tileset draws tw x th swapped, so it reaches outside the cell
# the cull bounds were derived from. selftest above covers _blit and would never have seen it.
def _tilemap_case(rng, pg, _host, transposed):
    """A tilemap with a deliberately non-square tileset, optionally carrying orientation bits."""
    import array
    tw, th = 16, 8                       # non-square on purpose: transpose then changes the footprint
    frames = 3
    stride = tw * frames
    data = bytearray(rng.randrange(1, frames) for _ in range(stride * th))
    pal = array.array("H", [0] + [rng.randrange(1, 65536) for _ in range(frames)])
    ts = pg.Bitmap(data, tw, th, format=pg.PAL8, palette=pal, frames=frames,
                   stride=stride, transparent=0)
    cols, rows = 30, 12
    tm = pg.Tilemap(ts, cols, rows)
    for ty in range(rows):
        for tx in range(cols):
            tm.set_tile(tx, ty, rng.randrange(frames))
    if transposed:
        for ty in range(rows):
            for tx in range(cols):
                if rng.random() < 0.3:
                    tm.set_tile(tx, ty, rng.randrange(frames), transpose=True)
    return tm


def tilemap_trials(pg, _host, trials=200):
    """Culled vs unculled must paint the same pixels, transposed tiles included."""
    import random
    fb = _host.fb
    W, H = _host.W, _host.H
    orig = pg.Tilemap._draw
    bad = 0
    for t in range(trials):
        frames = []
        for cull in (True, False):
            rng = random.Random(t)
            tm = _tilemap_case(rng, pg, _host, transposed=(t % 2 == 0))
            tm._ox, tm._oy = rng.randint(-20, 20), rng.randint(-20, 20)
            vx, vy = rng.randint(-200, 20), rng.randint(-60, 20)
            for i in range(len(fb)):
                fb[i] = 0
            if cull:
                orig(tm, vx, vy, (0, 0, W, H))
            else:
                _draw_every_tile(tm, vx, vy, (0, 0, W, H), pg)
            frames.append(list(fb))
        if frames[0] != frames[1]:
            bad += 1
            if bad <= 3:
                d = [i for i in range(len(fb)) if frames[0][i] != frames[1][i]]
                print("TILEMAP MISMATCH trial %d: %d px differ, first at (%d,%d)"
                      % (t, len(d), d[0] % W, d[0] // W))
    print("selftest_blit: %d tilemap trials, %d mismatches" % (trials, bad))
    return bad


def _draw_every_tile(tm, vx, vy, clip, pg):
    """Reference: no culling at all — walk the whole map."""
    ts = tm._tileset
    tw, th = ts.width, ts.height
    for ty in range(tm._map_h):
        for tx in range(tm._map_w):
            off = ty * tm._map_w + tx
            v = tm._grid[off]
            if v >= ts.frames:
                continue
            o = tm._orient[off] if tm._orient is not None else 0
            pg._blit(ts, tm._ox + tx * tw + vx, tm._oy + ty * th + vy, v,
                     bool(o & 1), bool(o & 2), clip, 1.0, False, None, 0, None, bool(o & 4))

if __name__ == "__main__":
    sys.exit(main())
