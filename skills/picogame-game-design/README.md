# picogame-game-design (Claude skill)

An AI **skill** for designing and building games with the [picogame](../../) engine. It pairs
**game-design theory** (what makes a small game fun) with **deep, accurate engine knowledge** and a
**sim-first build loop**, so an AI assistant can take a one-line idea ("make a tiny shooter") and
turn it into a well-designed game that actually runs — the way the project's own examples were made.

## What's inside

- **`SKILL.md`** — the self-contained **design guide**: the design fundamentals (core loop, game
  feel/juice with numbers, difficulty & fairness, the "one more go", game-state flow, audio,
  handheld readability, scope, assets), the workflow, the quality bar, and worked examples. Claude
  loads this when the task is about designing/building a picogame game — it can design a good game
  from this file alone.
- **`references/`** — pulled only when a step needs them:
  - `engine-capabilities.md` — the **deep engine reference** (blocks & costs, helpers, idioms, RAM
    budget, asset pipeline, sim loop, footguns).
  - `genre-patterns.md` — **genre playbooks** (per-genre recipes, controls, tuning, MVP).
  - `techniques.md` — **cross-genre technique recipes** mapped to picogame (state machines, AI,
    parallax, collision, procedural gen, palette/raster effects, level authoring, ghosts).
- **`templates/`** — `starter_game.py` (a runnable skeleton) and `design-brief.md` (fill before coding).

## Install (make it loadable by Claude Code)

Symlink (or copy) the skill into your skills dir so Claude can discover it:

```sh
ln -s "$PWD/repos/picogame/skills/picogame-game-design" ~/.claude/skills/picogame-game-design
# or project-level: ln -s ... .claude/skills/picogame-game-design
```

Then run Claude from the project root (so `sim/run.py`, `examples/`, and the `lib/` helpers
resolve). Ask for a game and the skill drives the design + build.

## Proven

The skill's own method was used to design and build **`examples/picogame_starfall.py`**
(a catch-the-gems / dodge-the-bombs arcade game) end to end, validated in the simulator.
