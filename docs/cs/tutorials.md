# Tutoriály picogame — uč se tvorbou her

Tutoriály představují jednotlivé skupiny herních mechanismů postupně. Každý krok je úplný,
spustitelný program a následující krok na něm staví. Otevři si `stepN` a `stepN+1` vedle
sebe; v rozdílu uvidíš kód přidaný pro nový princip.

Výsledkem každého tutoriálu je malá dokončená hra:

| Tutoriál | Žánr | Co učí |
|----------|-------|-----------------|
| **[01-bounce](/cs/tutorials/01-bounce/)** <sub>([zdroj](../../tutorials/01-bounce/))</sub> | Breakout / Arkanoid | vykreslovací smyčka, ovládání, pohyb s desetinnou přesností, odrazy od stěn a pálky, obdélníkové kolize, cihlová zeď z `Tilemap`, HUD, částice a zvuk. Tvary i importovaná grafika používají `Bitmap` na stejném `Sprite`, takže výměna vzhledu nemění herní logiku. |
| **[02-starship](/cs/tutorials/02-starship/)** <sub>([zdroj](../../tutorials/02-starship/))</sub> | vesmírná střílečka s pohledem shora | předem připravené snímky rotace, vektorový tah, přechod přes okraj obrazovky, **fondy objektů** pro střely a nepřátele, kruhové kolize, dělení kamenů, postupné vlny, částice, zvuk a stavový automat titulní obrazovka → hra → konec hry. |
| **[03-quest](/cs/tutorials/03-quest/)** <sub>([zdroj](../../tutorials/03-quest/))</sub> | RPG s pohledem shora | **svět větší než obrazovka**, kameru sledující hráče, kolize s tily, animaci chůze, sbírání předmětů, pevný HUD, rozhovor s NPC, souboj a úkol zakončený otevřením dveří a dosažením cíle. |

Procházej je **popořadě**, protože každý navazuje na základy předchozích.

## Jak spustit krok

Každý krok můžeš spustit v prohlížeči tlačítkem **Vyzkoušet v prohlížeči**. Soubor můžeš
také spustit lokálně v desktopovém simulátoru. Ten nepotřebuje zařízení a umí uložit
výsledný snímek do PNG:
```bash
python3 sim/run.py tutorials/01-bounce/step3_ball.py --shot /tmp/out.png
```
Užitečné přepínače: `--frames N` určí délku běhu, `--hold RIGHT,B` drží vybraná tlačítka
a `--backend pygame` otevře interaktivní okno, pokud máš nainstalovaný pygame.

Na **PicoPadu** (nebo jakékoli podporované desce): zkopíruj soubor kroku plus `lib/`
helpery, které importuje, na `CIRCUITPY/` a pojmenuj jej `code.py` (nebo jej importuj).
Hlavičkový komentář každého souboru vypisuje, co potřebuje.

## Jak je strukturován každý krok

- **Hlavičkový komentář** uvádí, *co se naučíš*, *co je nové oproti předchozímu kroku* a
  přesný příkaz pro spuštění.
- Komentáře v kódu označují **nové řádky**, takže změnu snadno najdeš.
- README v každé složce vysvětluje, proč je daný krok užitečný, a navrhne malou úpravu,
  na které si můžeš jeho chování vyzkoušet.

## Části enginu, které potkáš

Všechny pomocné moduly jsou v `lib/`. Jsou napsané v Pythonu a fungují na zařízení i v simulátoru:

| Helper | Role |
|--------|------|
| `picogame_game.setup()` | vybere displej a vytvoří `Scene`; na SPI cíli také strip buffery |
| `picogame` (C modul) | `Sprite`, `Bitmap`, `Tilemap`, `Particles`, `Canvas`, `Scene`, `collide`, `rgb565` |
| `picogame_input` | tlačítka jako bitová maska, `is_pressed` / `just_pressed` |
| `picogame_clock` | omezení snímkové frekvence a `dt`; akumulátor pevného časového kroku |
| `picogame_shapes` | generuje plné/kulaté/polygonové bitmapy (obdélníky, míčky, lodě) |
| `picogame_pool` | fond spritů pevné velikosti pro střely a nepřátele |
| `sprite.overlaps` / `sprite.near` | obdélníkové a kruhové kolize zabudované ve `Sprite` |
| `picogame_ui` | `SceneLabel` (text HUD ve scéně), text box, menu |
| `picogame_font` | renderuje řetězce do bitmap pomocí přibaleného fontu |
| `picogame_audio` | pípnutí (`tone()`) a přehrávání `.wav` |

## Po tutoriálech: přejdi na editor scén

Jakmile rozumíš herním mechanismům, nemusíš každý tile a sprite umisťovat ručně v Pythonu.
**Editor** (`tools/editor/`; hostovaný na /editor/ na tomto webu) umožňuje kreslit mapu, umisťovat sprity a nastavovat vlastnosti tilů.
Vyexportovanou scénu načte `picogame_scene` a stejná data fungují na zařízení i v simulátoru.
Úplný příklad najdeš v `examples/picogame_platformer_scene.py`; Python v něm řeší herní logiku,
zatímco úroveň, kolize, mince, nepřátelé a kamera pocházejí z dat editoru.

## Další kroky po tutoriálech

Po dokončení tutoriálů můžeš pokračovat těmito směry:

- **[Herní vzory](/cs/concepts/patterns/)** + **[Úryvky](/cs/snippets/)** — znovupoužitelný
  tvar herní smyčky a objektu `State`, do kterého každá větší hra doroste, plus **kostra
  hry** připravená ke spuštění, ze které rozjedeš vlastní projekt (otevři si ji v
  [Hřišti](/cs/playground/?ex=game-skeleton)). Právě teď, když máš tři hry postavené ručně,
  je to přirozený další krok.
- **[Průvodce funkcemi](features.md)** — úkolově zaměřená prohlídka všeho, co engine umí
  (kterou kreslicí plochu zvolit, transformace spritů, kolize, HUD, zvuk a hospodaření s RAM),
  a s alternativami. Použij ji, když vybíráš vhodný nástroj.
- **Pomocné moduly** (`lib/`) — čistě pythonové moduly z tutoriálů (`picogame_pool`,
  `picogame_ui`, `picogame_clock`, `picogame_anim`, …); průvodce funkcemi u každého odkazuje
  na jeho použití.
- **[Slovníček](/cs/concepts/glossary/)** — krátké, srozumitelné definice jakéhokoli neznámého
  pojmu, například sprite, tilemapa, dirty region, AABB nebo paralaxa.
