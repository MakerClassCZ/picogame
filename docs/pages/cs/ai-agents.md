---
title: Stavěj s AI agentem
description: Hotové skilly pro Claude a dokumentace čitelná pro LLM, aby kódovací agenti správně stavěli picogame hry a rozcházeli desky.
---

picogame nabízí dva hotové **skilly** pro AI kódovací agenty (třeba Claude Code) — jeden hry navrhuje
a staví, druhý rozchodí picogame na tvé desce — a **dokumentaci čitelnou pro LLM**, kterou si agent
může natáhnout celou.

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

## Skill pro rozchození desky

`picogame-board-setup` řeší hardwarovou stranu: holý nebo vlastní Raspberry Pi Pico, vlastní tlačítka,
displej nebo reproduktor, nebo podporovanou desku, na které něco nevypadá či nezní správně. Nese:

- **Nastavení v `settings.toml`** — tlačítka (každé na svém pinu, nebo skenovaná matice), barvy a
  orientace displeje, audio výstup a hlasitost, USB gamepady. Bez nového flashe.
- **Zjištění zapojení** — `code.py`, který při stisku ukáže, na kterém GPIO tlačítko je, a projede I2C,
  plus test displeje, takže se zapojení přečte z desky místo hádání.
- **Řešení problémů** — příznak → příčina → oprava pro špatné barvy, otočený obraz, mrtvá tlačítka,
  žádný nebo tichý zvuk a běžné tracebacky.
- **Přestavění firmwaru** — build flagy `CIRCUITPY_PICOGAME_*` pro změny, které nastavení neudělá.

Instaluje se stejně:

- **[Stáhnout skill (.zip)](/download/picogame-board-setup-skill.zip)**

```sh
cd ~/.claude/skills
unzip ~/Downloads/picogame-board-setup-skill.zip
```

Pak se zeptej — *„na holém Picu mi nefungují tlačítka"* nebo *„displej má špatné barvy"*.

## Dokumentace čitelná pro LLM (llms.txt)

Pro agenty, kteří čtou dokumentaci přímo, je celý web dostupný jako čistý markdown podle konvence
[llms.txt](https://llmstxt.org/) — nasměruj agenta sem místo scrapování HTML:

- **[/llms.txt](/llms.txt)** — index
- **[/llms-full.txt](/llms-full.txt)** — celá dokumentace jako jeden markdown soubor
- **[/_llms-txt/api.txt](/_llms-txt/api.txt)** — jen API (reference + engine + helpery), na psaní kódu
- **[/_llms-txt/getting-started.txt](/_llms-txt/getting-started.txt)** — úvod, tutoriály a koncepty

## Úprava game.json s agentem

Úroveň z [webového editoru](/cs/tools/editor/) je jeden textový soubor, `game.json`, který agent
upravuje přímo — řádky mapy nad legendou tilesetu, zóny a jejich příběhová data, efekty — vedle
`story.py` (příběhové skripty v Pythonu) a `code.py`. Pravidla, která skill učí:

- zachovej znaky legendy (přidávej, nikdy nepřepisuj), aby diff mapy zůstal obrázkem;
- před předáním souboru pusť `python3 tools/scene_build.py check` a `fmt`, po změně PNG `art`;
  nikdy neupravuj soubory `.pal8` ani `build/`;
- se zvolenou složkou v editoru se agentův zápis objeví do dvou sekund; v gitu je jeden řádek mapy
  jeden řádek souboru, takže se tvoje a agentovy úpravy slijí bez konfliktu.

