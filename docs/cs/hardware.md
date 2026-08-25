# Spuštění picogame na hardwaru (PicoPad / RP2040)

Hru můžeš nejprve sestavit a testovat **v prohlížeči nebo [desktopovém simulátoru](/cs/simulator/)** (`sim/`). Přechod
na **PicoPad** potom tvoří tři vratné kroky. Za stručným postupem následují podrobnosti o RAM, `.mpy`
a firmwaru, které využiješ u větší hry nebo při portování na vlastní desku.

## Rychlý postup: nasazení na PicoPad

PicoPad používá hotový firmware s `board.DISPLAY` a vestavěným profilem tlačítek. Pro běžné nasazení
proto nemusíš sestavovat vlastní firmware.

1. **Nainstaluj firmware.** Při připojení USB drž **BOOTSEL**, případně dvakrát stiskni **RESET**. Na disk
   `RPI-RP2` zkopíruj [`picopad.uf2`](../supported-hardware.md); po restartu se objeví disk `CIRCUITPY`.
   Před změnou na firmware s jiným rozložením flash data zazálohuj, protože taková změna může disk přeformátovat.
2. **Zkopíruj hru.** Na disk `CIRCUITPY` přenes `code.py`, používané moduly `picogame_*` do `lib/`
   a případné grafické nebo zvukové soubory. Jde o stejný herní kód jako v simulátoru.
3. **Spusť hru.** Ulož `code.py` nebo desku resetuj. Není potřeba další nastavení displeje ani mapování
   tlačítek.

Na jiné desce (holý Pico, PicoSystem, …) se liší zapojení a mapa tlačítek. Viz
[Podporovaný hardware](../supported-hardware.md). Všechno ostatní na této stránce je stejné.

> **Další části využiješ u větší hry nebo vlastního portu:** řeší omezenou RAM, soubory `.mpy`,
> dělení scén a build firmwaru. Pro první nasazení na PicoPad nejsou nutné.

> Limity taktování, SPI a rychlosti displeje — včetně vazby taktu jádra na SPI, limitu ST7789
> a měření vyšších taktů RP2350 — najdeš v **[Hodiny, SPI a limity displeje](../hardware-limits.md)**.

---

## 1. Rozpočet RAM

RP2040 má **264 KB** SRAM. V měřeném buildu firmwaru pro PicoPad spotřebuje firmware přibližně
72 KB staticky, takže pro Python zbývá asi **190 KB** heapu a největší souvislý blok má po startu
přibližně **130 KB**. Hodnoty se mohou změnit s verzí a konfigurací firmwaru.

| Položka | Cena |
|---|---|
| strip buffery z `picogame_game.setup()` (2 × 320×`strip_h`×2) | `strip_h=8` (výchozí s DMA) → **10 KB**, `strip_h=24` → **30 KB** |
| celoobrazovkový `Canvas(320, 240)` | **150 KB** ⚠️ více než měřený souvislý blok |
| `Canvas(320, 130)` (např. pseudo-3D silnice) | **83 KB**, samostatně OK (viz `microrace`), ale ne navíc k mnoha dalšímu |
| stavový řádek `Canvas(320, 20)` | 12,8 KB |
| Bitmap tilu/spritu | šířka×výška×snímky × (1 B PAL8 / 2 B RGB565) |

Důsledky:
- **Nealokuj celoobrazovkový Canvas na RP2040.** Pokud potřebuješ vlastní rastrovou plochu, například silnici nebo pole
  tvarů, drž ji jen tak velkou jako obsah, rozděl ji na pruhy nebo použij `Tilemap` pro velké
  rolovací plochy (1 bajt/buňka místo 2 bajtů/pixel: 320×960 šumové nebe je
  **600 KB jako Canvas, ale ~5 KB jako odstínový Tilemap**).
- Pro HUD použij `SceneLabel`, `HudBar` nebo jiný prvek, který neuchovává pixelovou plochu
  přes celou šířku, pokud ji návrh skutečně nepotřebuje.
- **`strip_h` má v současných buildech s DMA výchozí hodnotu 8** (přibližně 10 KB pro
  dva RGB565 buffery široké 320 pixelů, proti 30 KB při hodnotě 24). V měřeném buildu
  pro PicoPad byla menší hodnota také rychlejší. Porty bez DMA používají výchozí hodnotu 24,
  která snižuje počet blokujících přenosů.
- **`gc.collect()` mezi scénami/úrovněmi**, aby se buffery předchozí scény uvolnily,
  než další alokuje.
- Pokud je hra příliš velká jako jeden program, **rozděl ji** (viz §4).

`MemoryError: memory allocation failed, allocating N bytes` znamená, že se požadovaný blok nevešel.
Najdi scénu a řádek, kde chyba vzniká, a zmenši tam největší buffer, obvykle `Canvas`.

**Fragmentace, ne jen celkový volný prostor.** Dlouhá session, která alokuje a uvolňuje velké
buffery, fragmentuje heap: `gc.mem_free()` může ukazovat ~90 KB, zatímco alokace 51 KB stále
selže (žádný souvislý úsek). Pokud monolit umírá na velkém Canvasu, i když „je tam spousta volného
místa", je to právě tohle. Řešením je předalokovaná **arena** (`lib/picogame_arena.py`
+ firmwarový argument `Canvas(..., buffer=)`): vyhraď jeden velký buffer předem a rozděluj ho na části.
Obecný popis (se sondou na největší souvislý blok a síťovým příkladem)
je v **[Vejít se do paměti](../memory.md)**.

---

## 2. Zařízení a simulátor

Simulátor a firmware nabízejí stejné API hry, ale simulátor nedokáže přesně napodobit haldu,
časování přenosů, reproduktor ani efekty konkrétního panelu. Použij `picogame_game.setup()`,
aby stejný kód správně vybral SPI displej nebo framebuffer. Funkce vrací
`(scene, buffer_a, buffer_b)`: na SPI backendu buffery existují, na framebufferu mají hodnotu `None`.

`Scene.display` je dostupné v obou prostředích. Argument `fixed` u
`Scene.add(..., fixed=True)` je pouze pojmenovaný a nízkoúrovňové `pg.render()` přijímá
`scene.display`. Před vydáním hru otestuj na cílové desce, zejména po změně grafiky nebo firmwaru.

### Desky s framebufferem (Fruit Jam DVI) a barevná hloubka

Na desce, jejíž displej je RAM framebuffer místo SPI panelu — RP2350 picodvi/HSTX deska jako
**Adafruit Fruit Jam** — `picogame_game.setup()` skládá scénu přímo do scanout bufferu (jeho vrácené
buffery jsou `None`). Formát pixelu vybere podle barevné hloubky framebufferu automaticky, takže **kód
hry se nemění**; hloubku nastavíš jednou, v `settings.toml`:

- **`CIRCUITPY_DISPLAY_COLOR_DEPTH = 16`** — 16bitové RGB565 (plná barva). Obvyklá volba; na picodvi
  omezuje rozlišení (např. 320×240 zdvojené).
- **`CIRCUITPY_DISPLAY_COLOR_DEPTH = 8`** — 8bitové **RGB332**, jediná hloubka, kterou picodvi hardware
  nabízí při **640×480** (plné rozlišení Fruit Jamu). Engine každý dokončený pás kvantuje 565→332 při
  publikování, takže stále kreslíš přes `pg.rgb565(...)`; barvy se jen zredukují na 3-3-2 bity.

Pod kapotou je to `pg.Framebuffer(buffer, width, height, rgb332=True)` pro 8bitovou cestu vs.
`native_rgb565=True` pro 16bitovou (`setup()` volí za tebe). 8bitová/RGB332 cesta vyžaduje picogame
build, jehož `Framebuffer` podporuje `rgb332=` — novější engine; starší buildy vyhodí jasnou chybu
„lacks rgb332" s pokynem reflashnout.

---

## 3. Pasti při importu / kompilaci

- **Velký `.py` jako `code.py` → MemoryError při importu.** CircuitPython kompiluje zdroj `code.py`
  při startu; syntaktický strom velkého souboru krátkodobě spotřebuje mnoho RAM. **Větší moduly nasazuj
  jako `.mpy`** zkompilované verzí `mpy-cross`, která odpovídá firmwaru, a použij krátký spouštěcí `code.py`
  (`import my_scene`). `.mpy` je také menší a šetrnější k RAM.
- **Obří seznamové literály → `RuntimeError: pystack exhausted`.** Literál `array.array('H',
  [7168, ...])` tlačí tisíce prvků na VM stack (a vytvoří
  přibližně 28 KB krátkodobý seznam). Velké tilesety RGB565 **převáděj na PAL8 s `DATA =
  b'...'`**. Jediná konstanta `bytes` má poloviční velikost, nevytváří seznam a její bajtová data
  nevyžadují 16bitové zarovnání. Index palety 0 rezervuj pro průhlednost.

Kompilace modulu:
```bash
circuitpython/mpy-cross/build/mpy-cross  mymodule.py  -o  mymodule.mpy
```

---

## 4. Možnost pro velkou hru: jeden program na scénu

Pokud hra nedokáže držet všechny prostředky a kód scén současně, rozděl ji tak, aby v RAM
zůstala data jedné scény. Příklad `journey_hw` používá toto rozložení:

- **`dj_common.mpy`** — sdílené lešení + pomocníci (nastavení displeje, `new_scene`,
  `status_bar` jako Label, `play()` **bez** Canvasu kryjícího přechod, bitmap pomocníci).
  `import *` z něj.
- **`scene_<name>.mpy`** — jeden program na scénu; importuje jen prostředky, které potřebuje, takže
  v RAM žije vždy jen jedna scéna. Spouští vlastní `while True: seg(); gc.collect()`.
- **`code.py`** — jednořádkový spouštěč (`import scene_intro`); pro přepínání scén ho uprav nebo vytvoř malé tlačítkové menu.

Simulátor nebo build pro video může používat samostatný spojený vstupní soubor. Konkrétní
příklad: **`examples/journey_hw/`** (`dj_common.py` + `scene_*.py`,
plus `journey_mono.py`, varianta v jednom souboru se StripDraw, nulový pixel buffer / bez areny) vs. sim/video
monolit `examples/picogame_demo_journey.py` (se zvukem + přechodem). Viz
`examples/journey_hw/README.md`.

Rozložení na zařízení:
```text
CIRCUITPY/
  code.py                 # import scene_<name>
  scene_*.mpy             # jedna na scénu
  dj_common.mpy           # sdílení pomocníci
  <assets>.mpy            # dj_hero, dj_town, ... (jen to, co scény importují)
  lib/picogame_*.mpy      # Python pomocníci enginu
```
(Bez zapojení `picogame_audio` tato konkrétní ukázka na zařízení nepřehrává zvuk; chiptune dema je
pouze offline, zapečený do nahraného videa.)

---

## 5. Firmware musí obsahovat funkci, kterou voláš

Projevy jako `AttributeError: ... has no attribute 'X'` nebo `can't set attribute 'X'`
obvykle znamenají, že **nainstalovaný firmware je starší než kód, který X používá**. Například
starý build měl `Sprite.scale` jen pro čtení → `can't set attribute 'scale'`.

> **Pro běžné použití PicoPadu firmware nesestavuj:** nainstaluj nejnovější hotový
> [`picopad.uf2`](../supported-hardware.md) a funkce tam je. Postup buildu níže je určený jen pro port na jinou
> desku nebo práci na samotném enginu.

- Přeflashování PicoPadu: přes BOOTSEL zkopíruj nejnovější [`picopad.uf2`](../supported-hardware.md). Soubory zůstanou zachované pouze při stejném rozložení flash, proto před změnou buildu data zálohuj.
- Vlastní build pro nový port nebo vývoj enginu: viz [Build firmwaru](../firmware.md).
  (toolchain ARM GCC ≥ 14 + venv; `make BOARD=pajenicko_picopad -j$(nproc)`).
  Výstup: `circuitpython/ports/raspberrypi/build-pajenicko_picopad/firmware.uf2`.
- Ověření, že je symbol přítomen, bez flashování:
  `arm-none-eabi-nm build-.../firmware.elf | grep sprite_set_scale`.
- Instalace: vstup do bootloaderu RP2040, který se zobrazí jako disk `RPI-RP2`, a zkopíruj `firmware.uf2`.
  Souborový systém CIRCUITPY zůstane zachovaný pouze při stejném rozložení flash.

Aktuální firmware obsahuje: settery `Sprite.scale/angle/shadow`, kompletní sadu primitiv `Canvas`
(`triangle`/`ellipse`/`ring`/`fill_round_rect`/`frame3d`) a C `noise`
(`value2d`/`value1d`/`fbm2d`/`fbm1d` — implementace v pevné řádové čárce pod běžnými názvy).

---

## 6. Poznámky k výkonu

Herní páky rychlosti — smyčka ve funkci, dirty-rect-friendly pohyb, žádné alokace za snímek — najdeš
na **[Výkon](/cs/performance/)**. Poznámky zde jsou strana enginu/hardwaru.

- **Noise je v C a v pevné řádové čárce** (Q16.16): rychlý na RP2040 bez FPU; názvy jsou
  `value2d`/`value1d`/`fbm2d`/`fbm1d`.
- **Kreslení Canvasu je v C** (`fill_rect`, `frame3d`, …): Python jen vydává volání.
  Co stojí, je *buffer* Canvasu (RAM), ne kreslení.
- **`StripDraw` = okamžité vykreslování bez uchovávané pixelové plochy.** Pro *animované* plochy přes celý snímek
  (pseudo-3D silnice, gradientní nebe, procedurální pozadí) použij `pg.StripDraw(callback, …)`
  místo `Canvas`. Kreslí přímo do jednotlivých stripů a obejde se tak bez
  **150KB pixelového bufferu** celoobrazovkového `Canvas`. Překresluje se každý snímek, proto
  se hodí pro animovaný obsah, ne pro statickou grafiku. Viz [průvodce enginem](../engine.md) →
  `StripDraw` a `examples/picogame_stripdraw_example.py`. Objekt `StripDraw`, callback a herní stav
  stále používají RAM, ale nevzniká celoobrazovková plocha, která by tříštila haldu.
- Dirty regiony snižují práci u převážně statické scény; posun celé obrazovky stále překreslí
  celý výřez. Snímkovou frekvenci změř s vlastní grafikou, firmwarem a taktem SPI.

Viz také: [API enginu](../engine.md), [formát scény](../scene-format.md),
`tutorials/` (krok za krokem), `examples/`
(mezi žánrovými příklady je `microrace`, který v měřené konfiguraci používá 83KB `Canvas`).
