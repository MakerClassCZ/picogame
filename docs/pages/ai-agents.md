---
title: Build with an AI agent
description: A ready-made Claude skill and LLM-readable docs so coding agents design and build picogame games correctly.
---

picogame ships two things that make AI coding agents (like Claude Code) genuinely good at building
games for it: a **ready-made skill** that teaches the agent how to design and implement a picogame
game, and **LLM-readable documentation** it can pull in wholesale.

## The picogame game-design skill

`picogame-game-design` is an **Agent Skill** — a packaged set of instructions and references an agent
loads when you ask it to make a game. It carries:

- **Game-design fundamentals** — core loop, game feel & juice, difficulty & fairness, scope discipline,
  so the result is actually *fun*, not just running.
- **The engine, mapped** — every building block and what it costs in RAM, plus the full API reference
  (exact signatures for the native C engine **and** every helper library).
- **Genre playbooks** — Breakout, shmup, platformer, racing, first-person raycaster dungeon, and more —
  each with the core loop, controls, real tuning numbers, pitfalls and an MVP.
- **Technique recipes** — state machines, enemy AI, collision, procedural generation, pseudo-3D
  (Mode-7 & raycasting), each mapped to picogame.
- A runnable **starter game** and a **desktop-simulator** workflow, so the agent builds and checks with
  screenshots without any hardware.

### Install it

Download and unzip it into your agent's skills folder:

- **[Download the skill (.zip)](/download/picogame-game-design-skill.zip)**

For [Claude Code](https://claude.com/claude-code) that folder is `~/.claude/skills/`:

```sh
cd ~/.claude/skills
unzip ~/Downloads/picogame-game-design-skill.zip
```

Then just ask — *"make a tiny shooter for picogame"* — and the skill loads automatically.

The skill's source lives in the [public repo](https://github.com/MakerClassCZ/picogame) under `skills/`.

## LLM-readable docs (llms.txt)

For agents that read documentation directly, the whole site is available as clean markdown following
the [llms.txt](https://llmstxt.org/) convention — point your agent at these instead of scraping HTML:

- **[/llms.txt](/llms.txt)** — the index
- **[/llms-full.txt](/llms-full.txt)** — the entire documentation as one markdown file
- **[/_llms-txt/api.txt](/_llms-txt/api.txt)** — just the API (reference + engine + helpers), for writing code
- **[/_llms-txt/getting-started.txt](/_llms-txt/getting-started.txt)** — the intro, tutorials and concepts

## Editing a game.json with an agent

A level made in the [web editor](/tools/editor/) is one text file, `game.json`, that the agent
edits directly — map rows over the tileset's legend, zones and their story data, effects — next
to `story.py` (Python story scripts) and `code.py`. The rules the skill teaches:

- keep the legend's characters (append, never re-letter), so the map's diff stays a picture;
- run `python3 tools/scene_build.py check` and `fmt` before handing the file back, `art` after
  touching a PNG; never edit `.pal8` files or `build/`;
- with a folder chosen in the editor, the agent's write shows up there within two seconds; in git,
  one map row is one line, so your edits and the agent's merge cleanly.

