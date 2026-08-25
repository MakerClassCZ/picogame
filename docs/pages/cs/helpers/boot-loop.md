---
title: "Spuštění a herní smyčka"
description: "Nastavení displeje, časování herní smyčky a čtení tlačítek pomocí picogame_game, picogame_clock a picogame_input."
---

Tyto tři moduly nastaví displej, časují herní smyčku a čtou tlačítka. Typický `code.py` jednou zavolá `picogame_game.setup()`, vytvoří `Buttons()` a `Clock()` a potom opakuje čtyři kroky: načíst vstup, změnit stav hry, překreslit scénu a posunout hodiny. Signatury najdeš v [/cs/reference/](/cs/reference/).

## picogame_game

Funkci `setup()` zavolej jednou před vytvořením herních objektů. Vybere zobrazovací cestu, podle potřeby zastaví samostatné obnovování přes `displayio` a vrátí novou scénu s potřebnou pamětí.

- `setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0, rgb444=False)` - vrátí `(scene, buffer_a, buffer_b)`. Pro SPI displej vypne automatické obnovování, vyčistí `root_group` a alokuje dva vykreslovací pásy přes celou šířku. Na framebufferu, například Fruit Jam DVI nebo v prohlížečovém playgroundu, scéna skládá obraz přímo do framebufferu a oba vrácené buffery jsou `None`. Scéna si případné pásy drží sama. Pokud používáš pouze `scene.refresh()`, můžeš je ignorovat: `scene, _, _ = picogame_game.setup(...)`.
  - `display` - explicitně zadaný displej. Pokud ho vynecháš, funkce vezme `supervisor.runtime.display` (primární displej desky).
  - `strip_h` - výška vykreslovacího pásu na SPI cestě. Výchozí hodnotu určuje `picogame.STRIP_H` z firmwaru desky. Dva buffery zaberou `2 * width * strip_h * 2` bajtů, tedy přibližně 10 KiB při 320×8 nebo 30 KiB při 320×24. Na měřené RP2040 DMA cestě menší pás také zlepšil překrytí vykreslování s přenosem; bez DMA větší pás omezuje počet blokujících přenosů. Hodnotu můžeš změnit při volání nebo při sestavení firmwaru přes `-DPICOGAME_STRIP_H=N`. Framebuffer ji nepoužívá. Podrobnosti najdeš v [/cs/memory/](/cs/memory/).
  - `background` - barva pozadí ve formátu RGB565. Vytvoř ji pomocí `pg.rgb565(r, g, b)`.
  - `top` / `bottom` / `left` / `right` - okraj v pixelech, do kterého scéna nebude kreslit. Hodí se pro samostatně vykreslený HUD nebo boční panel.
  - `fast` - pro SPI displej vybere při hodnotě `True` třídu `pg.Display`, pokud je dostupná. `False` použije přenositelnou cestu přes busdisplay. Když rychlá cesta chybí, funkce přepne automaticky.
  - `rgb444` - hodnota `True` vyžádá 12bitové barvy na kompatibilní rychlé SPI cestě. Hodnota `"auto"` je zapne pouze na desce, která podporu oznámí. Framebuffer toto nastavení nepoužívá. Viz [/cs/hardware/](/cs/hardware/).

```python
import picogame as pg
import picogame_game

BG = pg.rgb565(20, 24, 30)
scene, buffer_a, buffer_b = picogame_game.setup(background=BG, strip_h=16, top=12)
# scene je pg.Scene; přidej sprity a překresluj ji každý snímek
# jednoduchá hra, která nikdy nekreslí v immediate módu, může buffery vynechat: scene, _, _ = ...
scene.add(sprite)
scene.refresh()
```

:::note[Pozor]
scénu drž po celou dobu hry. Na SPI cestě vlastní oba vykreslovací buffery; framebufferová cesta je nevytváří. Okraj rezervovaný přes `top`/`bottom`/`left`/`right` scéna nemaže ani nekreslí, proto ho vykresli samostatně. Data scény popisuje [/cs/scene-format/](/cs/scene-format/) a rozdíly mezi displeji [/cs/hardware/](/cs/hardware/).
:::

## picogame_clock

`Clock` omezí smyčku na cílové FPS a vrátí uplynulý čas jako `dt`, takže pohyb nemusí záviset na snímkové frekvenci. `FixedStep` spouští herní logiku ve stejně dlouhých krocích, když potřebuješ opakovatelnou fyziku nebo kolize.

`Clock`:

- `Clock(fps=30, max_dt=0.1)` - omezí smyčku na `fps` (použij `0` pro bez omezení) a ořízne vrácené `dt` na maximálně `max_dt` sekund, takže pauza nebo zaseknutí nemůže vyrobit obří `dt`, které teleportuje vše.
- `tick()` - čeká do hranice snímku a pak vrátí reálné `dt` v sekundách od posledního `tick()`. Kotví se na ideální rozvrh, takže malé překročení se nesmí akumulovat do driftu; pokud jsi přetáhl rozpočet, ukotvuje se na reálný čas a `dt` zůstane přesné. Volej jednou za snímek.
- `tick_async()` - asynchronní varianta, která během čekání předá řízení jiným úlohám `asyncio`. Vyžaduje dostupnou knihovnu `asyncio`, jinak vyvolá `RuntimeError`. Samotné vykreslování zůstává blokující, takže asynchronní běh pomáhá pouze během čekání na další snímek.
- `set_fps(fps)` - změn cílové FPS za běhu (např. menu na 30, akce na 60). `0` odstraní omezení.

`FixedStep`:

- `FixedStep(step_fps=60, max_steps=5)` - pevný časový krok `1/step_fps` sekund. Za jeden snímek spustí nejvýše `max_steps` kroků logiky; pokud vykreslování nestíhá, starší nahromaděné kroky zahodí.
- `step_count()` - vrátí počet pevných kroků pro tento snímek (`0..max_steps`). Iteruj `for _ in range(step_count())` a používej konstantní `self.dt`; tato forma nic nealokuje, vhodné pro horké smyčky.
- `dt` - konstantní délka kroku v sekundách. Předej ji svému updatu.
- `steps()` - generátorová forma, která pro každý krok yielduje `self.dt`. Pohodlné, ale při každém volání alokuje generátor; v hlavní smyčce raději použij `step_count()`.

```python
import picogame_clock

clock = picogame_clock.Clock(30)        # omezení na 30 FPS
while True:
    dt = clock.tick()                   # počká na hranici snímku, vrátí reálné dt
    player.x += player.vx * dt          # pohyb nezávislý na snímkové frekvenci
    scene.refresh()
```

:::note[Pozor]
`tick()` volej jednou za snímek na konci smyčky. Když vrácenou hodnotu ignoruješ, omezení FPS dál funguje, ale pohyb nebude využívat skutečný uplynulý čas. `tick_async()` pomůže jen tehdy, když během čekání běží jiné úlohy; vykreslení samo stále blokuje.
:::

## picogame_input

`Buttons` mapuje fyzická tlačítka na logickou bitovou masku a rozlišuje stisk, uvolnění i automatické opakování. Pokud je dostupný modul `keypad`, používá skenování na pozadí a frontu událostí; jinak čte piny přes `digitalio`. Třída `Timer` vytváří krátká časová okna pro toleranci pozdního nebo předčasného stisku, například coyote time a předregistraci skoku.

Logická tlačítka jsou dostupná jako konstanty modulu i atributy instance: `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `B`, `X`, `Y`, `L1`, `L2`, `R1`, `R2`, `START`, `SELECT` a `ALL`. PicoPad mapuje osm předních tlačítek. Tlačítka, která daná deska nemá, se nikdy neaktivují. Masky můžeš spojit operátorem OR: `btn.A | btn.B`.

`Buttons`:

- `Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)` - vytvoří čtečku. Pokud `profile=None`, mapu pinů určí v tomto pořadí: `PICOGAME_BUTTONS` ze `settings.toml`, vestavěný profil podle `board.board_id` a nakonec profil `PICOPAD`. Explicitně předaný `profile` má přednost před všemi. `pull` je standardně `Pull.UP`, případně hodnota `PICOGAME_PULL` ze `settings.toml`. `debounce_s` určuje interval skenování modulu `keypad`; `prefer_keypad=False` vynutí přímé čtení pinů. `matrix=` přidá skenovanou klávesovou matici a `usb=` USB HID zdroje — viz níže.
  - **Víc zdrojů vstupu:** `Buttons` ORuje několik zdrojů do jedné masky — GPIO tlačítka desky, skenovanou klávesovou matici (`matrix=`, nebo klíče `PICOGAME_MATRIX_*`) a USB gamepady/klávesnice na deskách s USB hostem (`usb=`, připojené automaticky). Hra je čte všechny bez změny kódu. Kompletní průvodce: [Vstup a ovládání](/cs/helpers/input/).
- `poll()` - načte tlačítka a vrátí aktuální masku stisknutých. Volej jednou za snímek před dotazy na stav. Zpracuje frontu událostí `keypad` nebo přímo přečte piny a aktualizuje dobu držení pro `repeat()`.
- `is_pressed(mask=ALL)` - `True` pokud je aktuálně stisknuto jakékoli tlačítko v `mask` (úroveň).
- `just_pressed(mask=ALL)` - `True` na vzestupné hraně (snímek, kdy tlačítko šlo dolů). Na keypad backendu pochází z fronty událostí, takže stisk kratší než jeden snímek se stále zaregistruje.
- `just_released(mask=ALL)` - `True` na sestupné hraně (snímek, kdy tlačítko šlo nahoru).
- `has(mask=ALL)` - `True`, pokud aktivní profil mapuje některé tlačítko z `mask`. Umožní přizpůsobit ovládání a rozhraní deskám bez ramenních tlačítek nebo bez START/SELECT.
- `repeat(button, delay=15, interval=4)` - auto-repeat pro JEDNO tlačítko: `True` ve snímku, kdy je stisknuto, pak každých `interval` snímků po přidržení `delay` snímků. Ideální pro pohyb v menu a mřížce.
- `clear()` - vynuluje stav a zahodí čekající události. Volej při přechodu mezi scénami nebo nabídkami, aby se přidržené tlačítko nepřeneslo do další obrazovky.

`Timer`:

- `Timer(frames)` - čítač, který ubývá jeden snímek po druhém po dobu `frames` snímků.
- `feed(condition)` - dobije na plnou hodnotu pokud je `condition` pravdivá, jinak odečte jeden snímek; vrátí, zda je stále aktivní. Použij pro coyote time (`feed(on_ground)`).
- `charge()` - vynutí čítač na plnou hodnotu.
- `is_active` (vlastnost) - `True`, dokud je čítač nad nulou.
- `consume()` - pokud je čítač aktivní, jednou vrátí `True` a vynuluje ho. Předregistrovaný stisk se tak použije nejvýše jednou.

```python
import picogame_input

btn = picogame_input.Buttons()          # profil automaticky podle desky
while True:
    btn.poll()
    dx = btn.is_pressed(btn.RIGHT) - btn.is_pressed(btn.LEFT)   # -1, 0 nebo +1
    if btn.just_pressed(btn.A):          # vzestupná hrana: spustí se jednou za stisk
        jump()
    scene.refresh()
```

Coyote time a jump buffering, přímo z příkladu platformovky:

```python
coyote = picogame_input.Timer(5)        # ještě pár snímků po sejití z hrany dovol skok
jbuf = picogame_input.Timer(6)          # uznej skok stisknutý těsně před dopadem
# každý snímek:
coyote.feed(on_ground)
jbuf.feed(btn.just_pressed(btn.A))
if coyote.is_active and jbuf.consume():
    jump()
```

:::note[Pozor]
`poll()` volej jednou za snímek před dotazy, jinak `is_pressed()` a `just_pressed()` vrátí starý stav. `repeat()` přijímá jediné tlačítko, ne spojenou masku. Cesta přes `digitalio` neodstraňuje zákmit kontaktů; u problematického spínače bez modulu `keypad` přidej samostatné ošetření vstupu. USB pad/klávesnici a maticový vstup popisuje [Vstup a ovládání](/cs/helpers/input/), remap klíče (`PICOGAME_BUTTONS`/`PICOGAME_MATRIX_*`/USB) [reference settings.toml](/cs/custom-board/).
:::
