---
title: Stavěj s AI agentem
description: Hotový skill pro Claude a dokumentace čitelná pro LLM, aby kódovací agenti navrhovali a stavěli picogame hry správně.
---

picogame nabízí dvě věci, díky kterým jsou AI kódovací agenti (třeba Claude Code) v tvorbě her pro něj
opravdu dobří: **hotový skill**, který agenta naučí picogame hru navrhnout a naimplementovat, a
**dokumentaci čitelnou pro LLM**, kterou si může natáhnout celou.

## Skill pro herní design v picogame

`picogame-game-design` je **Agent Skill** — zabalená sada instrukcí a referencí, kterou si agent načte,
když ho požádáš o hru. Nese:

- **Základy herního designu** — core loop, game feel a juice, obtížnost a férovost, kázeň ve scope, aby
  výsledek byl *zábavný*, ne jen že „běží".
- **Namapovaný engine** — každý stavební blok a jeho cena v RAM, plus kompletní API referenci (přesné
  signatury nativního C enginu **i** všech pomocných knihoven).
- **Žánrové playbooky** — Breakout, shmup, plošinovka, závody, first-person raycaster dungeon a další —
  každý s core loopem, ovládáním, reálnými ladicími čísly, nástrahami a MVP.
- **Recepty technik** — stavové automaty, AI nepřátel, kolize, procedurální generování, pseudo-3D
  (Mode-7 a raycasting), každý namapovaný na picogame.
- Spustitelnou **startovací hru** a workflow **desktopového simulátoru**, takže agent staví a ověřuje
  screenshoty bez jakéhokoli hardwaru.

### Instalace

Stáhni a rozbal do složky skillů svého agenta:

- **[Stáhnout skill (.zip)](/download/picogame-game-design-skill.zip)**

U [Claude Code](https://claude.com/claude-code) je to `~/.claude/skills/`:

```sh
cd ~/.claude/skills
unzip ~/Downloads/picogame-game-design-skill.zip
```

Pak stačí říct — *„udělej malou střílečku pro picogame"* — a skill se načte automaticky.

Zdroj skillu žije ve [veřejném repu](https://github.com/MakerClassCZ/picogame) ve složce `skills/`.

## Dokumentace čitelná pro LLM (llms.txt)

Pro agenty, kteří čtou dokumentaci přímo, je celý web dostupný jako čistý markdown podle konvence
[llms.txt](https://llmstxt.org/) — nasměruj agenta sem místo scrapování HTML:

- **[/llms.txt](/llms.txt)** — index
- **[/llms-full.txt](/llms-full.txt)** — celá dokumentace jako jeden markdown soubor
- **[/_llms-txt/api.txt](/_llms-txt/api.txt)** — jen API (reference + engine + helpery), na psaní kódu
- **[/_llms-txt/getting-started.txt](/_llms-txt/getting-started.txt)** — úvod, tutoriály a koncepty
