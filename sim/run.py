#!/usr/bin/env python3
# Run a picogame game/demo on the desktop simulator.
#
#   python sim/run.py examples/picogame_arkanoid.py               # live window (needs pygame)
#   python sim/run.py examples/picogame_pacman.py --shot out.png  # headless + save a screenshot
#   python sim/run.py examples/picogame_pacman.py --backend pil   # force headless
#   python sim/run.py examples/picogame_picowing.py --profile     # cProfile + allocation report
#
# Resolves imports: sim/ provides `picogame` + the CircuitPython stubs, lib/ the
# picogame_* helpers, and the game's own dir its assets (we chdir there so relative
# asset paths like cavern.bin resolve).

import sys
import os
import argparse
import traceback


def _run_profiled(host, code, g, game_path, game_dir, root, frames):
    """Headless run under cProfile + tracemalloc, then print a STRUCTURE report.
    The sim engine is Python (C on-device), so absolute times over-weight it — read call
    counts + your game/lib functions. tracemalloc is filtered to game + lib code only."""
    import cProfile
    import pstats
    import tracemalloc
    import io
    base = os.path.basename(game_path)
    warm = min(8, max(1, frames // 3))     # snapshot after warm-up so setup allocs don't count
    snap = {}

    def hook(fr):
        if fr == warm:
            snap["t"] = tracemalloc.take_snapshot()

    host.set_frame_hook(hook)
    tracemalloc.start()
    prof = cProfile.Profile()
    prof.enable()
    try:
        exec(code, g)
    except host.SimStop:
        pass
    except Exception:
        prof.disable()
        print("[sim] EXCEPTION in %s:" % base)
        traceback.print_exc()
        sys.exit(1)
    prof.disable()
    end = host._frame

    bar = "=" * 76
    print("\n[sim] profiled %d frames: %s\n%s" % (end, base, bar))
    print("NOTE: the sim engine is PYTHON (C on the device) -> absolute TIMES over-weight engine")
    print("funcs (picogame.py blit/render). Read CALL COUNTS + your game/lib functions. Transient")
    print("per-frame allocations show as high call counts here, not in the allocation block below.")
    print(bar)
    for key, label in (("ncalls", "by CALL COUNT (transferable to device)"),
                       ("tottime", "by TIME (SIM-SKEWED — engine is Python here)")):
        buf = io.StringIO()
        pstats.Stats(prof, stream=buf).sort_stats(key).print_stats(12)
        print("\n--- cProfile %s ---\n%s" % (label, buf.getvalue().strip()))

    # tracemalloc: RETAINED growth, filtered to game + lib only (profiler/engine excluded)
    if "t" in snap:
        span = max(1, end - warm)
        filt = (tracemalloc.Filter(True, os.path.join(game_dir, "*")),
                tracemalloc.Filter(True, os.path.join(root, "lib", "*")))
        s0 = snap["t"].filter_traces(filt)
        s1 = tracemalloc.take_snapshot().filter_traces(filt)
        diff = s1.compare_to(s0, "lineno")
        grow = sum(d.size_diff for d in diff)
        print("\n--- RETAINED game/lib allocation, frames %d..%d (engine/profiler excluded) ---" % (warm, end))
        print("net growth %+d B (%.0f B/frame) — leak / per-frame-retained check (§4)" % (grow, grow / span))
        top = [d for d in diff if d.size_diff > 0][:8]
        if top:
            for d in top:
                f = d.traceback[0]
                print("   %+8d B  %s:%d" % (d.size_diff, f.filename.rsplit("/", 1)[-1], f.lineno))
        else:
            print("   none — no retained game/lib growth (clean).")
    print(bar)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--backend", choices=("pil", "pygame"), default=None,
                    help="pygame = live window, pil = headless. Default: a live window if pygame is "
                         "installed, else headless (screenshot / CI runs use pil).")
    ap.add_argument("--shot", default=None)
    ap.add_argument("--shot-at", type=int, default=None)
    ap.add_argument("--hold", default=None,
                    help="buttons held for the whole run, e.g. --hold RIGHT,B "
                         "(logical names UP/DOWN/LEFT/RIGHT/A/B/X/Y) -- for testing input")
    ap.add_argument("--profile", action="store_true",
                    help="headless run under cProfile + tracemalloc; print a perf report "
                         "(call counts, time [sim-skewed], per-frame game/lib allocation)")
    args = ap.parse_args()

    # Backend default: a human running `run.py game.py` wants to SEE it, so open a live pygame window
    # when pygame is available. A screenshot/profile run (or a box without pygame) stays headless (pil).
    if args.backend is None:
        if args.shot or args.shot_at or args.profile:
            args.backend = "pil"
        else:
            try:
                import pygame  # noqa: F401
                args.backend = "pygame"
            except ImportError:
                args.backend = "pil"
                print("[sim] pygame not installed -- running headless. `pip install pygame` for a live window.")

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    game_path = os.path.abspath(args.game)
    game_dir = os.path.dirname(game_path)

    # sim stubs first, then helpers, then the game's own dir (assets).
    sys.path.insert(0, game_dir)
    sys.path.insert(0, os.path.join(root, "lib"))
    sys.path.insert(0, here)

    import _host
    max_frames = None if (args.backend == "pygame" and not args.profile) else args.frames
    _host.configure(backend=args.backend, max_frames=max_frames,
                    shot=args.shot, shot_at=args.shot_at)
    if args.backend == "pygame":
        _host.setup_keymap()
        print("[sim] controls: arrows / WASD = move,  F / Ctrl = A,  G / Space = B,  "
              "R / Q = X,  T / E = Y,  close the window to quit")
    if args.hold:                      # hold buttons for the whole run (input testing)
        for name in args.hold.split(","):
            _host.pressed_pins.add("SW_" + name.strip().upper())

    os.chdir(game_dir)                 # so open("cavern.bin") etc. work
    src = open(game_path).read()
    code = compile(src, game_path, "exec")
    g = {"__name__": "__main__", "__file__": game_path}
    if args.profile:
        _run_profiled(_host, code, g, game_path, game_dir, root, args.frames)
        return
    try:
        exec(code, g)
    except _host.SimStop:
        print("[sim] stopped after %d frames OK: %s" % (_host._frame, os.path.basename(game_path)))
    except Exception:
        print("[sim] EXCEPTION in %s:" % os.path.basename(game_path))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
