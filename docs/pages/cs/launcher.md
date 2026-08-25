---
title: Herní menu (launcher)
description: Launcher je menu, do kterého picogame naběhne — hru vybereš D-padem. Jak hry hledá, jak se ovládá a jak přidat vlastní.
sidebar:
  label: Herní menu
  order: 6
---

Launcher je **herní menu** picogame — oficiální, a nepovinná, cesta, jak mít na jedné desce víc her a
přepínat mezi nimi. Nakopíruj hry na disk a launcher je vypíše; jednu vybereš D-padem a hraješ,
restartem se vrátíš.

Je volitelný: [quick-start balíčky](/cs/start/quickstart/) do launcheru naběhnou (jejich kořenový
`code.py` ho spustí), ale deska, jejíž `code.py` je jedna hra, spustí rovnou tu hru — bez menu.
Launcher použij, když chceš na téže desce víc her.

![Launcher picogame: vlevo seznam her, vpravo náhled s ikonou a údaji vybrané hry.](/img/launcher.png)

## Ovládání

- **NAHORU / DOLŮ** — pohyb v seznamu.
- **A** — spustit zvýrazněnou hru.
- **RESET** (tlačítko reset na desce) — návrat z hry do launcheru.

## Jak hledá hry

Ve výchozím stavu launcher prohledá složky `demos/`, `games/` a `apps/` na disku — chybějící se prostě
přeskočí. Každá hra je **složka** se vstupním `code.py` a zkompilovaným `.mpy`:

```
games/
  picotris/
    code.py           # 2řádkový stub, který hru naimportuje
    picotris.mpy      # zkompilovaná hra
    metadata.json     # title, icon, ...  (volitelné)
    icon.bmp          # ikona do menu      (volitelné)
```

Složka s `code.py`, ale bez metadat se v menu objeví taky — launcher použije jméno složky a písmenkovou
náhradní ikonu.

Vlastní bootovací `code.py` může prohledat jinou sadu složek — stačí je předat:
`picogame_launcher.run(roots=("mojehry", "demos"))`.

## Přidání vlastní hry

1. Zkompiluj hru do `.mpy` (`mpy-cross tvojehra.py`), nebo vlož `.py` a nech ji zkompilovat na desce.
2. Vytvoř složku v `apps/` — tam patří tvoje vlastní hry, vedle přibalených `games/` a `demos/` —
   třeba `apps/tvojehra/`, se stub `code.py`, který ji naimportuje:
   ```python
   import tvojehra
   ```
3. Volitelně přidej vedle `metadata.json`, ať v menu vypadá dobře, plus malou `icon.bmp` (48pixelová
   BMP funguje dobře):
   ```json
   {
     "title": "Tvoje hra",
     "author": "Ty",
     "category": "arcade",
     "players": 1,
     "desc": "Jeden řádek o hře.",
     "icon": "icon.bmp"
   }
   ```
4. Restartuj desku — hra se objeví v menu.

## Dva způsoby, jak hru popsat

Složka může nést malý manifest, aby v menu vypadala dobře. Fungují dva formáty:

- **`metadata.json`** — jednoduchý a **kompatibilní s FruitJamOS** (`title` + `icon`, plus volitelně
  `author`, `category`, `players`, `desc`, `entry`). Jedna hra na složku — to používá příklad výše,
  takže stejná složka se objeví v obou menu.
- **`picogame.json`** — bohatší forma. Buď plochý objekt (`title`, `entry`, `icon`, …) pro jednu hru,
  nebo seznam **`"apps"`**, který z jedné složky nabídne **víc her** — hodí se pro kolekci nebo hru s
  variantami:
  ```json
  {
    "apps": [
      { "title": "Hra A", "entry": "a.py", "icon": "a.bmp" },
      { "title": "Hra B", "entry": "b.py", "icon": "b.bmp" }
    ]
  }
  ```
  Každá položka má vlastní `entry`, `title` a `icon` (a volitelně `author`/`category`/`players`/`desc`).
  `picogame.json` se čte dřív než `metadata.json`.
