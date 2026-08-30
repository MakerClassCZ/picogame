#!/usr/bin/env python3
"""Drift-guard for the picogame-game-design skill (review issue #3: single source of truth).

The skill's prose names engine helpers; the libs are generated and get renamed, so the prose drifts
(e.g. picogame_geom -> picogame_collide, .update() -> .tick(), .pressed -> .is_pressed). This greps
every `picogame_*` module token in the skill against the real `lib/picogame_*.py`, and bans a list of
RETIRED tokens that renames/the API freeze removed. Run it after any lib rename; exit 1 on a mismatch.

    python tools/check_skill_api.py
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # picogame-dev
REPOS = os.path.dirname(ROOT)                                        # repos/ (multi-repo layout)


def _first(cands, needle):
    for c in cands:
        if os.path.exists(os.path.join(c, needle)):
            return c
    return cands[0]


# The check must evaluate WHAT SHIPS, not whatever the maintainer's workspace happens to contain.
# The dev tree carries ~59 extra game modules, so a skill citing one of them (`picogame_cavern`,
# `picogame_boxshmup`, ...) passed here and failed for every public user - the check was weaker for
# us than for the people it protects. So: resolve ONE public root and allow only that.
PUB = _first([os.path.join(REPOS, "picogame"), ROOT], "lib/picogame_input.py")

SKILL = _first([os.path.join(ROOT, "skills/picogame-game-design"),
                os.path.join(PUB, "skills/picogame-game-design")], "SKILL.md")
LIB = os.path.join(PUB, "lib")
SIM = _first([os.path.join(PUB, "sim"),
              os.path.join(REPOS, "picogame-final/sim")], "run.py")

_GAME_ROOTS = [LIB, os.path.join(PUB, "demos"), os.path.join(PUB, "examples"),
               os.path.join(PUB, "games"), os.path.join(PUB, "tutorials")]
real = {os.path.basename(p)[:-3]
        for d in _GAME_ROOTS
        for p in glob.glob(os.path.join(d, "**", "picogame_*.py"), recursive=True)}
real.add("picogame")  # the native C module

# Retired tokens that must never reappear in the skill (renames + frozen API). Each: (regex, why).
BANNED = [
    (r"\bpicogame_geom\b", "renamed -> picogame_collide (now removed)"),
    (r"\bpicogame_collide\b", "removed -> use sprite.overlaps(b) / sprite.near(b, r)"),
    (r"\bpicogame_vec\b", "merged into picogame_math"),
    (r"\bpicogame_keypad\b", "merged into picogame_input (auto backend)"),
    (r"\bpicogame_noise\b", "dropped (noise is native picogame.value2d/fbm2d)"),
    (r"\bseq\.add\b", "Seq has no add(); use Seq(gen)/.start(gen)"),
    (r"\bseq\.update\b", "Seq advances via .tick()"),
    (r"Shake\([^)]*\)\.update", "Shake advances via .tick()"),
    (r"(?<![\w.])\.pressed\b", "predicate is .is_pressed"),
    (r"\.open\((?!ed)", "menus show/hide, not open/close"),
]

errors = []
files = sorted(glob.glob(os.path.join(SKILL, "**", "*.md"), recursive=True) +
               glob.glob(os.path.join(SKILL, "**", "*.py"), recursive=True))
mod_re = re.compile(r"\bpicogame_[a-z0-9_]+")
for f in files:
    rel = os.path.relpath(f, ROOT)
    lines = open(f).read().splitlines()
    for ln, line in enumerate(lines, 1):
        for m in mod_re.findall(line):
            if m not in real:
                errors.append("%s:%d unknown module `%s` (no lib/%s.py)" % (rel, ln, m, m))
        for pat, why in BANNED:
            if re.search(pat, line):
                errors.append("%s:%d retired token /%s/ (%s): %s" % (rel, ln, pat, why, line.strip()[:70]))

# Grep catches renamed MODULES but not renamed METHODS (e.g. hud.redraw() vs .draw()). The template
# is what the workflow tells the agent to start from, so actually RUN it in the sim: a crashing
# starter would otherwise pass the grep and poison every game the agent builds from it.
starter = os.path.join(SKILL, "templates", "starter_game.py")
run_py = os.path.join(SIM, "run.py")
if os.path.exists(starter) and os.path.exists(run_py):
    r = subprocess.run([sys.executable, run_py, starter, "--frames", "30"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        tail = r.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
        errors.append("templates/starter_game.py FAILS in the sim:\n    " + "\n    ".join(tail))
    else:
        print("starter_game.py runs clean in the sim (30 frames)")
else:
    print("note: skipped starter_game sim-run (starter or sim not found)")

def check_reference_coverage():
    """The skill's api-reference must document every symbol the public docs/reference.md does.

    They are two hand-maintained copies of one API. The skill copy carries extra detail (argument
    ranges), so they are not byte-identical and a plain diff would cry wolf -- but it must never
    fall BEHIND, because an agent only knows what its own copy lists. It silently drifted 13 symbols
    behind (pg.project, Canvas.vspans, core1, vblank, the whole Triangles/iso/scenebake sections)
    while both files looked fine on their own.
    """
    import re as _re
    ref = None
    cand = os.path.join(PUB, "docs", "reference.md")
    if os.path.exists(cand):
        ref = cand
    skill_ref = os.path.join(SKILL, "references", "api-reference.md")
    if ref is None or not os.path.exists(skill_ref):
        return []                       # nothing to compare against in this checkout
    def syms(p):
        out = set()
        for line in open(p, encoding="utf-8"):
            m = _re.match(r"^-\s+`([A-Za-z_][\w.]*)[`(]", line)
            if m:
                out.add(m.group(1))
        return out
    behind = sorted(syms(ref) - syms(skill_ref))
    if behind:
        return ["skill api-reference is behind docs/reference.md, missing: " + ", ".join(behind)]
    return []


errors.extend(check_reference_coverage())

if errors:
    print("SKILL API DRIFT (%d):" % len(errors))
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("skill API OK: every picogame_* ref resolves (%d known lib+example modules), no retired tokens"
      % (len(real) - 1))
