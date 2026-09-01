#!/usr/bin/env python3
# Run a picogame game/demo on the desktop simulator.
#
#   python sim/run.py examples/picogame_arkanoid.py               # live window (needs pygame)
#   python sim/run.py examples/picogame_pacman.py --shot out.png  # headless + save a screenshot
#   python sim/run.py examples/picogame_pacman.py --backend pil   # force headless
#   python sim/run.py examples/picogame_picowing.py --profile     # cProfile + allocation report
#   python sim/run.py my_game.py --keys "20:RIGHT,40:X:2" --shot-at 45 --shot out.png
#
# Resolves imports: sim/ provides `picogame` + the CircuitPython stubs, lib/ the
# picogame_* helpers, and the game's own dir its assets (we chdir there so relative
# asset paths like cavern.bin resolve).

import sys
import os
import argparse
import traceback

# The sim's display rests NON-inverted (unlike the PicoPad panel, which sends INVON at init). Tell
# picogame_fx so InvertFlash flips to the negative on pulse() and restores to NORMAL - otherwise it
# "restores" to inverted and the whole sim stays stuck in negative after the first flash. setdefault
# so an explicit PICOGAME_INVERT (e.g. to emulate an inverted panel) still wins.
os.environ.setdefault("PICOGAME_INVERT", "0")


def _button_pin(name):
    """Logical button name -> pin name. A full pin (SW2_LEFT for player 2) passes through."""
    n = name.strip().upper()
    return n if n.startswith("SW") else "SW_" + n


def _parse_keys(spec):
    """Parse a --keys timeline into {frame: [(pin, down), ...]}.

    `20:X` presses X at frame 20 and holds it, `25:-X` releases it, `40:X:2` taps it for 2
    frames (= press at 40, release at 42). A tap of 1-2 frames is what `just_pressed` needs;
    holding is what `is_pressed` needs.
    """
    events = {}
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) not in (2, 3):
            raise SystemExit("[sim] --keys: expected FRAME:BUTTON[:HELD_FRAMES], got %r" % item)
        try:
            frame = int(parts[0])
            held = int(parts[2]) if len(parts) == 3 else None
        except ValueError:
            raise SystemExit("[sim] --keys: frame and HELD_FRAMES must be integers, got %r" % item)
        name = parts[1].strip().upper()
        down = not name.startswith("-")
        pin = _button_pin(name.lstrip("-"))
        events.setdefault(frame, []).append((pin, down))
        if held is not None:
            if not down:
                raise SystemExit("[sim] --keys: HELD_FRAMES makes no sense on a release, got %r" % item)
            events.setdefault(frame + held, []).append((pin, False))
    # A bare FRAME:BTN with no later release/tap is HELD to the end of the run. That is valid
    # (it is how you hold a direction), but when the intent was a TAP the run is silently
    # edge-dead: just_pressed fires once at the press and never again, and every later "press"
    # in the tester's head does nothing. Warn - a probe lost 40 minutes to four such runs.
    open_holds = {}
    for frame in sorted(events):
        for pin, down in events[frame]:
            if down:
                open_holds[pin] = frame
            else:
                open_holds.pop(pin, None)
    for pin, frame in sorted(open_holds.items()):
        print("[sim] --keys note: %s pressed at frame %d is HELD to the end "
              "(use %d:%s:2 for a tap)" % (pin, frame, frame, pin.replace("SW_", "")))
    return events


def _keys_applier(host, events):
    """Return fn(frame) that applies the timeline's presses/releases for `frame`."""
    def apply(frame):
        for pin, down in events.get(frame, ()):
            if down:
                host.pressed_pins.add(pin)
            else:
                host.pressed_pins.discard(pin)
    return apply


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
    mid = warm + max(1, (frames - warm) // 2)   # a second one halfway, to tell a one-off from a leak
    snap = {}

    prev = host._frame_hook            # keep a --keys timeline running under --profile

    def hook(fr):
        if prev is not None:
            prev(fr)
        if fr == warm:
            snap["t"] = tracemalloc.take_snapshot()
        if fr == mid:
            snap["mid"] = tracemalloc.take_snapshot()

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
        # The inclusive game filter is a DIRECTORY glob, so a game sitting in the repo root pulls
        # in sim/ and everything else beside it -- the report then blames the simulator, and its
        # own profiler printer, for a leak in your game. Exclude the sim explicitly: the header
        # promises the engine is excluded, so it has to be.
        sim_dir = os.path.dirname(os.path.abspath(__file__))
        filt = (tracemalloc.Filter(True, os.path.join(game_dir, "*")),
                tracemalloc.Filter(True, os.path.join(root, "lib", "*")),
                tracemalloc.Filter(False, os.path.join(sim_dir, "*")))
        s0 = snap["t"].filter_traces(filt)
        s1 = tracemalloc.take_snapshot().filter_traces(filt)
        diff = s1.compare_to(s0, "lineno")
        grow = sum(d.size_diff for d in diff)
        print("\n--- RETAINED game/lib allocation, frames %d..%d (engine/profiler excluded) ---" % (warm, end))
        # A per-frame RATE is the wrong shape for a one-off cost: a fixed 3 kB of lazy setup reads as
        # 4 B/frame over 600 frames and 1 B/frame over 2400, and the quality bar calls growth a
        # blocker - so people chase a phantom. Split the run in half instead: a real leak keeps
        # allocating at the same pace, a warm-up allocation does not.
        half = None
        if "mid" in snap:
            sm = snap["mid"].filter_traces(filt)
            first = sum(d.size_diff for d in sm.compare_to(s0, "lineno"))
            second = sum(d.size_diff for d in s1.compare_to(sm, "lineno"))
            half = (first, second)
        print("net growth %+d B over %d frames" % (grow, span))
        if half:
            first, second = half
            # The halves alone are noisy: CPython frame objects and a GC pass make one half
            # negative, and `second > first * 0.5` then reads a few hundred bytes of churn as a
            # LEAK (probe agents saw the same unmodified game flip verdict at 300 / 400 / 800
            # frames). A leak has to show up in the NET first - only then is the shape worth
            # reading.
            if grow <= 1024:
                verdict = "clean — net retained growth is negligible for the whole run"
            elif second > max(64, first * 0.5):
                verdict = "LEAK — still allocating in the second half"
            else:
                verdict = "one-off — the second half is flat, this is warm-up, not a leak"
            print("  first half %+d B, second half %+d B  ->  %s" % (first, second, verdict))
        top = [d for d in diff if d.size_diff > 0][:8]
        if top:
            for d in top:
                f = d.traceback[0]
                print("   %+8d B  %s:%d" % (d.size_diff, f.filename.rsplit("/", 1)[-1], f.lineno))
        else:
            print("   none — no retained game/lib growth (clean).")
    print(bar)


def _install_virtual_clock():
    """Make picogame_clock believe time passes only when the game sleeps.

    Clock already has an uncapped mode, but it measures REAL elapsed time -- in a headless loop that
    is a fraction of a millisecond, so a dt-scaled game crawls (and `x / dt` can divide by zero). What
    a verification run wants is the opposite: skip the wait, keep the timeline. So we replace the
    module's clock source with a counter and its sleep with an advance of that counter. Real work
    costs zero virtual milliseconds, so Clock finds itself exactly one interval ahead of each
    boundary, "sleeps" that interval, and hands the game a dt of exactly 1/fps every frame.

    Patched at module level (`_ms` / `_sleep` are bound there, which is what makes this a two-line
    seam). Anything reading the wall clock directly is untouched -- that is the honest limit here.
    """
    import picogame_clock
    now = [picogame_clock._ms()]
    picogame_clock._ms = lambda: now[0]
    picogame_clock._sleep = lambda seconds: now.__setitem__(
        0, (now[0] + int(seconds * 1000 + 0.5)) & picogame_clock._MASK)


def _uses_clock(game_path):
    """Does this game (or any sibling module it imports, recursively) use picogame_clock?

    Decided BEFORE the game runs, because the two frame counters must not switch mid-run: a
    game's setup presents would otherwise consume the first scripted key events.
    """
    import ast
    gdir = os.path.dirname(os.path.abspath(game_path))
    seen, todo = set(), [game_path]
    while todo:
        f = todo.pop()
        try:
            tree = ast.parse(open(f).read())
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n == "picogame_clock":
                    return True
                sib = os.path.join(gdir, n + ".py")
                if n not in seen and os.path.isfile(sib):
                    seen.add(n)
                    todo.append(sib)
    return False


def _install_frame_boundary(host):
    """Count frames at the GAME's loop boundary (`clock.tick()`), not at each present.

    A present is not a frame: a draw-on-change HUD (`HudBar.draw`, an immediate label) pushes a
    SECOND present on the frames where it repaints, so a present-counted timeline drifts by a
    content-dependent amount - `--keys 105:A` firing at game frame 96, and a route that survives
    one death falling apart after the next. `clock.tick()` is the one call every shipped title
    makes exactly once per iteration, so it is the honest boundary. A game with no Clock keeps
    the old present counting (nothing else marks its frames).
    """
    import picogame_clock
    _orig = picogame_clock.Clock.tick

    def tick(self, *a, **k):
        dt = _orig(self, *a, **k)
        host.tick_boundary()
        return dt

    picogame_clock.Clock.tick = tick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--frames", type=int, default=150,
                    help="stop after N GAME frames - one per `clock.tick()`, i.e. the game's own loop iteration, however many times it presented inside it (a draw-on-change HUD is free). A game with no picogame_clock falls back to counting presents.")
    ap.add_argument("--backend", choices=("pil", "pygame"), default=None,
                    help="pygame = live window, pil = headless. Default: a live window if pygame is "
                         "installed, else headless (screenshot / CI runs use pil).")
    ap.add_argument("--shot", default=None)
    ap.add_argument("--shot-at", type=int, default=None,
                    help="screenshot after this GAME frame - counted from the very first "
                         "clock.tick(), so TITLE and menu frames count too: if the game "
                         "sits on a title until A, add those frames to the play-frame you "
                         "want. Default: the last frame.")
    ap.add_argument("--hold", default=None,
                    help="buttons held for the whole run, e.g. --hold RIGHT,B "
                         "(logical names UP/DOWN/LEFT/RIGHT/A/B/X/Y) -- for testing input")
    ap.add_argument("--keys", default=None,
                    help="scripted input timeline, FRAME:BUTTON[:HELD_FRAMES] items separated by "
                         "commas: --keys \"20:RIGHT,40:X:2,60:-RIGHT\" walks right from frame 20, "
                         "taps X for 2 frames at 40 (a tap is what just_pressed needs) and lets go "
                         "at 60. FRAME is a GAME frame (the same counter as --frames: one per "
                         "clock.tick()), so the button is down when the game polls input on that "
                         "frame no matter how often it presents (a draw-on-change HUD is free). "
                         "Headless only (a live window reads the keyboard).")
    ap.add_argument("--tap", default=None,
                    help="repeat a tap for the whole run: --tap A:30 taps A for 2 frames every 30. "
                         "A soak needs this: --hold A presses ONCE and never releases, so a game "
                         "whose restart is just_pressed(A) spends the soak on its game-over screen. "
                         "Several: --tap A:30,LEFT:12 (BUTTON:PERIOD[:HELD_FRAMES]).")
    ap.add_argument("--seed", type=int, default=None,
                    help="fix the RNG so a run REPEATS: seeds picogame_rand's default seed and "
                         "CPython's random. Without it every run deals a different game, so two "
                         "screenshots can't be compared and a difficulty complaint can't be "
                         "reproduced.")
    ap.add_argument("--strict-dirty", action="store_true",
                    help="honour each always_dirty=False StripDraw's dirty bit instead of "
                         "repainting everything: a layer you forgot to invalidate() after a "
                         "content change then STOPS UPDATING here, the way it does on device "
                         "(the sim has no dirty-rect otherwise, so that bug is invisible).")
    ap.add_argument("--fast", action="store_true",
                    help="headless: run the frame loop at full speed by giving picogame_clock a "
                         "VIRTUAL clock -- the frame sleep is skipped but dt still reads the nominal "
                         "1/fps, so dt-scaled movement behaves exactly as it does at the real rate "
                         "(and becomes deterministic: no machine-load jitter between runs). Turns a "
                         "3600-frame soak from two minutes of wall clock into however long the "
                         "compute takes. A game that reads time.monotonic() itself is NOT faked.")
    ap.add_argument("--profile", action="store_true",
                    help="headless run under cProfile + tracemalloc; print a perf report "
                         "(call counts, time [sim-skewed], per-frame game/lib allocation)")
    args = ap.parse_args()

    # Backend default: a human running `run.py game.py` wants to SEE it, so open a live pygame window
    # when pygame is available. A screenshot/profile run (or a box without pygame) stays headless (pil).
    if args.backend is None:
        if args.shot or args.shot_at or args.profile or args.keys or args.fast:
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
    import picogame as _pgmod
    _pgmod._set_strict_dirty(args.strict_dirty)
    if args.seed is not None:
        import random as _random
        import picogame_rand as _prand
        _prand._default_seed = lambda: args.seed    # Rand() with no seed -> this one
        _random.seed(args.seed)                     # ... and the stdlib RNG some games use
    _host.set_tick_mode(_uses_clock(game_path))   # decided statically, see _uses_clock
    _install_frame_boundary(_host)
    if args.fast:
        if args.backend == "pygame":
            print("[sim] --fast is ignored with a live window (a window has to run in real time).")
        else:
            _install_virtual_clock()

    if args.hold:                      # hold buttons for the whole run (input testing)
        for name in args.hold.split(","):
            _host.pressed_pins.add(_button_pin(name))
    if args.tap:                       # periodic taps for the whole run (soak restarts)
        if args.backend == "pygame":
            print("[sim] --tap is ignored with a live window (it reads the real keyboard).")
        else:
            taps = []
            for item in args.tap.split(","):
                parts = item.split(":")
                if len(parts) < 2:
                    raise SystemExit("[sim] --tap: expected BUTTON:PERIOD[:HELD], got %r" % item)
                pin = _button_pin(parts[0])
                period = int(parts[1])
                held = int(parts[2]) if len(parts) > 2 else 2
                if period < 1 or held < 1 or held >= period:
                    raise SystemExit("[sim] --tap: need 1 <= HELD < PERIOD, got %r" % item)
                taps.append((pin, period, held))

            def apply_taps(fr, _taps=taps):
                for pin, period, held in _taps:
                    phase = fr % period
                    if phase == 0:
                        _host.pressed_pins.add(pin)
                    elif phase == held:
                        _host.pressed_pins.discard(pin)

            prev = _host._frame_hook
            _host.set_frame_hook(lambda fr: (apply_taps(fr + 1), prev and prev(fr)))
    if args.keys:                      # scripted timeline: press/release at given frames
        if args.backend == "pygame":
            print("[sim] --keys is ignored with a live window (it reads the real keyboard).")
        else:
            apply_keys = _keys_applier(_host, _parse_keys(args.keys))
            # The hook runs after frame N is presented, i.e. just before the game polls input for
            # N+1 -- so schedule N+1 there and apply frames 0/1 up front. A game therefore SEES the
            # button down on the frame the timeline names.
            apply_keys(0)
            apply_keys(1)
            _host.set_frame_hook(lambda fr: apply_keys(fr + 1))

    os.chdir(game_dir)                 # so open("cavern.bin") etc. work
    src = open(game_path).read()
    code = compile(src, game_path, "exec")
    g = {"__name__": "__main__", "__file__": game_path}
    if args.profile:
        if args.frames > 600:
            print("[sim] --profile traces every allocation: expect ~10x the wall time of a plain "
                  "run (900 frames ~ 2 min). Profile a few hundred frames; soak WITHOUT --profile.")
        _run_profiled(_host, code, g, game_path, game_dir, root, args.frames)
        return
    try:
        exec(code, g)
    except _host.SimStop:
        print("[sim] stopped after %d frames OK: %s" % (_host._frame, os.path.basename(game_path)))
        for n in _host.take_notes():
            print("[sim] WARNING: %s" % n)
    except Exception:
        print("[sim] EXCEPTION in %s:" % os.path.basename(game_path))
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
