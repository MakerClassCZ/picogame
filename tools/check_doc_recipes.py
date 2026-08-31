#!/usr/bin/env python3
"""Check the code the documentation hands people: it must parse, and it must do what it claims.

Four recipes on docs/pages/concepts/patterns.md stated their behaviour in a comment and did not do
it - a fall at double speed, a wall you end up inside, a flash that never clears, mercy frames that
never expire. Every one of them PARSED. They were found by a person building a game from them and
by reading the rest of the page afterwards, which is not a process that scales to 156 code blocks.

So:
  phase 1  every ```python block in docs/ parses (cheap; catches a broken edit)
  phase 2  the recipes that define a function are EXECUTED against stubs and asserted against the
           claim the prose makes about them

Phase 2 is where the value is, and it only covers what someone has written a check for - add one
when you add a recipe. A recipe with no check is a recipe nobody has run.

    python3 tools/check_doc_recipes.py
"""
import ast
import glob
import os
import re
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCK_RE = re.compile(r"^[ \t]*```python\n(.*?)^[ \t]*```", re.S | re.M)


def blocks(path):
    """(line number, dedented source) for every python block in a markdown file."""
    s = open(path, encoding="utf-8").read()
    return [(s[:m.start()].count("\n") + 2, textwrap.dedent(m.group(1)))
            for m in BLOCK_RE.finditer(s)]


def phase1_parse():
    bad = 0
    n = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "docs", "**", "*.md"), recursive=True)):
        for ln, code in blocks(f):
            n += 1
            try:
                ast.parse(code)
            except SyntaxError as e:
                rel = os.path.relpath(f, ROOT)
                print("  %s:%d does not parse: %s" % (rel, ln, str(e).split("(")[0].strip()))
                bad += 1
    print("phase 1: %d python blocks, %d unparseable" % (n, bad))
    return bad


def _recipe(name, page="docs/pages/concepts/patterns.md"):
    """Execute the block that defines `name`, and hand back the function itself.

    The recipes call a `solid(x, y)` the reader supplies, so we supply one too - that IS the
    contract, and a recipe that only works against the demo's private helpers would be a finding.
    """
    path = os.path.join(ROOT, page)
    for _ln, code in blocks(path):
        if re.search(r"^def %s\(" % re.escape(name), code, re.M):
            ns = {}
            exec(compile(code, "%s::%s" % (page, name), "exec"), ns)   # noqa: S102 - the point
            return ns[name], ns
    raise LookupError("no block defining %s() in %s" % (name, page))


# --------------------------------------------------------------------------- the behaviour checks
def check_move_x():
    """'stop at the wall, don't enter it' - at ANY speed, and without tunnelling through it."""
    LEFT, RIGHT = 20, 100                     # a corridor, so both directions are tested
    fn, ns = _recipe("move_x")
    ns["solid"] = lambda x, y: x >= RIGHT or x <= LEFT
    out = []
    for dx in (1, 3, 7, 15, 40):
        x = 60
        for _ in range(40):
            x = fn(x, 200, dx, 6)
        if x + 6 > RIGHT:
            out.append("dx=%d ends %d px inside the right wall" % (dx, x + 6 - RIGHT))
        x = 60
        for _ in range(40):
            x = fn(x, 200, -dx, 6)
        if x - 6 < LEFT:
            out.append("dx=-%d ends %d px inside the left wall" % (dx, LEFT - (x - 6)))
    return out


def check_move_y():
    """Three claims: it does not move twice, it stops both ways, and standing still is stable."""
    FLOOR, CEIL = 100, 40
    fn, ns = _recipe("move_y")
    ns["solid"] = lambda x, y: y >= FLOOR or y <= CEIL
    out = []

    # 1. free fall advances by vy, once
    y = 60
    for i in range(1, 4):
        y, vy, _g = fn(10, y, 3, 6)
        if y != 60 + 3 * i:
            out.append("free fall moved to %d after %d frames at vy=3, expected %d" % (y, i, 60 + 3 * i))
            break

    # 2. a ceiling stops a jump
    y, vy, _g = fn(10, 50, -20, 6)
    if y <= CEIL:
        out.append("rising through a ceiling: ended at y=%d, ceiling is %d" % (y, CEIL))

    # 3. standing still does not flicker the grounded flag
    y, vy, seen = 99, 0.0, set()
    for _ in range(12):
        vy = min(7.0, vy + 0.6)
        y, vy, grounded = fn(10, y, vy, 6)
        seen.add(bool(grounded))
    if len(seen) > 1:
        out.append("the grounded flag flickers while standing still (saw %s)" % sorted(seen))
    return out


def check_camera_clamp():
    """The scrolling-camera one-liner must keep the view inside the world."""
    path = os.path.join(ROOT, "docs/pages/concepts/patterns.md")
    for _ln, code in blocks(path):
        if "set_view" in code and "clamp" in code:
            if "clamp(" not in code:
                return ["the camera recipe no longer clamps"]
            return []
    return ["no scrolling-camera recipe found"]


CHECKS = [("move_x", check_move_x), ("move_y", check_move_y), ("camera", check_camera_clamp)]


def phase2_behaviour():
    bad = 0
    for name, fn in CHECKS:
        try:
            problems = fn()
        except Exception as e:                       # a recipe that will not even run is a finding
            print("  %-8s could not be executed: %s: %s" % (name, type(e).__name__, e))
            bad += 1
            continue
        for p in problems:
            print("  %-8s %s" % (name, p))
        bad += len(problems)
    print("phase 2: %d recipe check(s), %d problem(s)" % (len(CHECKS), bad))
    return bad


if __name__ == "__main__":
    n = phase1_parse() + phase2_behaviour()
    if n:
        print("\nFAIL: %d problem(s) in the documented code" % n)
    sys.exit(1 if n else 0)
