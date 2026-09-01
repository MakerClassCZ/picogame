# picogame — 2D herní engine pro PicoPad (CircuitPython)

`picogame` je 2D herní engine s uchovávanou scénou, napsaný jako C modul pro CircuitPython.
Referenčním cílem je Pajenicko PicoPad (RP2040, 320×240 ST7789), podporované jsou i další
desky. Oproti `_stage` nabízí sprity různých velikostí, `Scene` s dirty regiony, tilemapy,
částice, kreslicí plochy a volitelný backend s asynchronním DMA.

- **Referenční cíl:** firmware PicoPadu a SPI backend jsou testované na zařízení. Stav dalších
  cílů uvádí stránka [Podporovaný hardware](../supported-hardware.md).
- **Výkon:** na SPI displeji přenáší `Scene` samostatně až šest dirty regionů. Pohyb
  soustředěný na malé ploše proto může být levnější než celý snímek; změny rozeseté po obrazovce
  a pohyb kamery se mohou blížit překreslení celé obrazovky.

---

## Obsah
1. [Kam tahle stránka patří](#kam-tahle-stránka-patří)
2. [Rychlý start](#rychlý-start)
3. [Přehled API](#přehled-api)
4. [Příprava grafiky a map](#příprava-grafiky-a-map)
5. [Náklady a omezení enginu](#náklady-a-omezení-enginu)
6. [Pod kapotou](#pod-kapotou)
7. [Build firmwaru](#build-firmwaru)
8. [Příklady](#příklady)

---

## Kam tahle stránka patří

Tohle je **hloubkový průvodce nativním C modulem `picogame`**: přesné chování, kontrakty
a náklady typů enginu. Předpokládá, že víš, co hledáš.

- Jsi tu poprvé? [Tvoje první hra](/cs/start/first-game/), pak [Jak picogame funguje](/cs/concepts/how-it-works/).
- „Kterou vrstvu/plochu použít?" → [Kreslicí cesty](/cs/concepts/drawing-paths/); rejstřík podle úkolů ve [FEATURES.md](../features.md).
- Holé signatury všeho → [REFERENCE.md](../reference.md).
- Čistě-Python helpery `picogame_*` (vstup, časování, audio, UI, pooly, ukládání…) mají vlastní
  průvodce v sekci *Helpery* — tahle stránka pokrývá jen C modul. (Helpery si drží prefix
  souborů `picogame_*`, **nikoli** balíček `picogame/`: to jméno patří C modulu a nelze ho zastínit.)

**Dva kontrakty, na kterých stojí všechno:** barvy jsou vždy ve **wire order** —
skládej je přes `pg.rgb565(r, g, b)`; naivní `0xRRGGBB` nebo host-endian RGB565 vykreslí špatné
barvy. Souřadnice mají počátek vlevo nahoře; obdélníky render volání jsou **půlotevřené**
(`x0,y0` včetně až `x1,y1` vyjma), zatímco hitboxy `collide()` jsou **inkluzivní**
(jiné domény: pixely vs hitboxy).

---

## Rychlý start

```python
import time, array
import board
import picogame as pg
import picogame_game

BG = pg.rgb565(20, 24, 40)
scene, _, _ = picogame_game.setup(background=BG)
W, H = picogame_game.screen()   # rozměry obrazovky z desky

# Simple 16×16 paletted sprite (index 0 is transparent)
pal = array.array("H", [pg.rgb565(0, 0, 0), pg.rgb565(230, 80, 80)])
data = bytearray(16 * 16)
for y in range(16):
    for x in range(16):
        if 3 <= x < 13 and 3 <= y < 13:
            data[y * 16 + x] = 1
hero_bmp = pg.Bitmap(data, 16, 16, format=pg.PAL8, palette=pal, transparent=0)

hero = pg.Sprite(hero_bmp, 150, 110)
scene.add(hero)

while True:
    hero.x = (hero.x + 1) % (W - 16)
    scene.refresh()
    time.sleep(1 / 60)
```

---

## Přehled API

### Modul `picogame`

| Název | Popis |
|---|---|
| `RGB565` | konstanta formátu (16bitová barva ve wire order) |
| `PAL8` | konstanta formátu (8bitový index do palette) |
| `rgb565(r, g, b) -> int` | vytvoří z 8bitových složek barvu RGB565 ve wire order |
| `collide(x1, y1, x2, y2, ax1, ay1, ax2, ay2) -> bool` | překryv AABB box↔box; inkluzivní hranice, takže boxy kolidují při doteku (boxy spritu předávej jako `(x, y, x+w, y+h)`; spustí se při kontaktu). `collide` je inkluzivní, na rozdíl od půlotevřených pixelových rozsahů u render (jiné domény: hitboxy vs pixely) |
| `collide(x1, y1, x2, y2, px, py) -> bool` | box↔bod (6 argumentů) |
| `render(display, sprites, buffer, x0, y0, x1, y1, *, background=0)` | okamžité vykreslení seznamu spritů do kompatibilního zobrazovacího cíle |
| `value2d(x, y, *, seed=0) -> float` | hladký 2-D value noise, 0..1 (rychlé C) |
| `value1d(x, *, seed=0) -> float` | hladký 1-D value noise, 0..1 |
| `fbm2d(x, y, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` | fraktální (fBm) 2-D noise, 0..1 — terén/mraky/jeskyně |
| `fbm1d(x, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` | fraktální (fBm) 1-D noise, 0..1 |

Šum se interně počítá s **pevnou řádovou čárkou** (Q16.16), což je rychlé na RP2040 bez FPU.
Je určený pro jednorázové generování terénu nebo mraků, ne pro každý snímek. Samostatné exporty `_fx`
neexistují; `value2d`/`value1d`/`fbm2d`/`fbm1d` jsou kanonické funkce, volané přímo na modulu
`picogame` (`pg.value2d`, `pg.fbm2d`, …); simulátor poskytuje odpovídající implementaci v Pythonu.

### API závislé na buildu

Přítomnost závisí na buildu firmwaru. NEOVĚŘUJ přes `hasattr` na TYPECH — build bez backendu je stále vystavuje jako stuby, jejichž konstruktor vyhodí výjimku, takže `hasattr` je vždy True. Testuj modulové booleany: `pg.FAST_DISPLAY_SUPPORTED` a `pg.FRAMEBUFFER_SUPPORTED`:

| Název | Přítomné když | Účel |
|---|---|---|
| `Display` | `pg.FAST_DISPLAY_SUPPORTED` (buildy RP2/ESP) | backend s asynchronním DMA; na přenositelných portech chybí (místo ní předej `Scene` běžný busdisplay) |
| `Framebuffer` | `pg.FRAMEBUFFER_SUPPORTED` (platformy s výstupním framebufferem, např. WASM playground) | cíl vykreslování v RAM místo panelu |
| `RGB444_SUPPORTED` | vždy (bool) | zda panel této desky umí 12bitové RGB444 |
| `STRIP_H` | vždy (int) | výchozí výška stripu desky (používá ji `picogame_game.setup`) |
| `API_LEVEL` | novější firmware (použij `getattr(pg, "API_LEVEL", 0)`) | generace API enginu, pro verzní kontroly předem |

### `Bitmap(data, width, height, *, format=RGB565, palette=None, frames=1, stride=0, transparent=None)`
Obrazový atlas jednoho či více stejně velkých snímků, **libovolné** šířky a výšky.
- `data` — čitelný buffer: `PAL8` = 1 bajt na index pixelu; `RGB565` = 2 bajty na pixel ve wire order.
- `palette` — pro `PAL8` buffer barev RGB565 ve wire order (např. `array("H", [...])`).
- `frames` — snímky animace uspořádané **vodorovně**; snímek `f` začíná ve sloupci `f*width`.
- `stride` — šířka atlasu v pixelech (výchozí `width*frames`).
- `transparent` — index palety (`PAL8`) nebo barva (`RGB565`) ve wire order, která se přeskočí; `None` = neprůhledné.
- Vlastnosti jen pro čtení: `width`, `height`, `frames`, `format`, `stride`, `palette` (buffer palety PAL8 nebo `None`) a `transparent` (průhledná hodnota nebo `None`).

### `Sprite(bitmap, x=0, y=0, *, frame=0, visible=True, flip_x=False, flip_y=False)`
Umístěná, animovatelná instance `Bitmap`.
- Vlastnosti: `x`, `y` (celočíselný pixel; setter přijímá i float), `fx`, `fy`
  (sub-pixelová float pozice), `frame`, `visible`, `flip_x`, `flip_y`, `transpose`,
  `data`, `bitmap`, `scale`, `angle`, `shadow`, `flash`, `tint`, `dither`.
- `move(x, y)` — nastaví pozici (přijímá int nebo float).
- `overlaps(other, inset=0) -> bool` / `near(other, r) -> bool` — nativní testy
  kolizí (zohledňují anchor/scale/rotaci, bez alokací). `overlaps` je inkluzivní
  test AABB boxu (`other` = `Sprite`, bod `(x, y)`, nebo rect `(x1, y1, x2, y2)`);
  `inset` zmenší box **tohoto** spritu o N px pro férovější hitbox. `near` je
  kruhový test (středy do `r`, bez sqrt; `other` = `Sprite` nebo bod).
- `scale` — rovnoměrné měřítko vykreslení (float, nearest-neighbour). `1.0` = nativní (rychlá cesta 1:1);
  `2.0` = dvojnásobná velikost; zlomky povoleny (např. mince pulzující `1.0..1.3`, rostoucí
  powerup). Škáluje kolem `anchor`.
- `angle` — rotace ve **stupních** kolem anchoru (float). `0` = žádná (rychlá cesta);
  jakákoli jiná hodnota použije afinní (inverzně mapovaný) blit. Celočíselná měřítka zůstávají ostrá;
  rotace lehce „šumí“ (kompromis pixel-art grafiky). `scale` + `angle` se skládají.
- `shadow` — když je `True`, neprůhledné pixely sprite cíl **ztmaví**
  místo vykreslení své barvy (vržené stíny: posunutá silueta pod
  sprite; nebo ztmavující/vignette overlay). Lze libovolně kombinovat se `scale`/`angle`.
- Blit efekty `flash`, `tint`, `dither` — levné per-pixel přebarvení/průhlednost,
  vždy jeden naráz (nastavení jednoho ostatní zruší; `0` = vyp), žádná grafika ani
  RAM navíc. `flash = WHITE` obarví neprůhledné pixely plochou barvou (1–3framové
  bliknutí při zásahu); `tint = RED` barvu násobí a **zachovává** stínování
  (osvětlení/zranění/zmrazení; umí jen ztmavit); `dither = 0..16` je Bayer stipple
  (duch/mlha/rozplynutí, žádná alpha; animuj úroveň pro rozplynutí dovnitř/ven).
- `transpose` — když je `True`, prohodí osy X/Y (diagonální zrcadlení); ve spojení
  s `flip_x`/`flip_y` dává všech **8** orientací jako ostrý blit po rychlé cestě
  (scale 1, angle 0). Prohodí se šířka/výška obrysu.
- `bitmap` — čtení/zápis zdrojového `Bitmap`. Přiřazení nového vymění grafiku
  za běhu a může změnit velikost (powerupy, měnitelné HUD pruhy, textové popisky);
  scéna při dalším `refresh` překreslí jak staré, tak nové hranice.
- `touch()` — označí sprite jako dirty po **in-place** úpravě `bitmap`/palety (např. přebarvení přes `picogame_palette`), aby se změna při dalším `refresh` překreslila.
- `anchor` — pivot jako `(fx, fy)` zlomky velikosti bitmapy: `(0, 0)` vlevo nahoře
  (výchozí), `(0.5, 0.5)` střed, `(0.5, 1.0)` dole uprostřed. `x`/`y` pak odkazují na
  tento bod, takže růst/zmenšování přes výměnu `bitmap` zůstává zarovnáno kolem
  pivotu. Dirty-rect sleduje výsledný levý horní roh.
- Pro hladkou fyziku použij `fx`/`fy`
  (`ball.fx += 2.4`) místo paralelního Python floatu + `int(round())`; `x`/`y`
  vracejí zaokrouhlený pixel dolů pro výpočty s tile/kolizemi. Dirty-rect se spustí jen tehdy,
  když se změní pixel (sub-pixelové chvění pod 1 px je zdarma).
- `data` — libovolný objekt s herním stavem daného spritu. Není proto potřeba souběžná obalová
  třída: `hero.data = {"vy": 0, "dead": False}`.

### `Display(busdisplay, *, rgb444=False)`
Rychlý backend s asynchronním DMA, který obaluje existující `busdisplay.BusDisplay` (např.
`board.DISPLAY`). Znovu využívá jeho SPI sběrnici, piny, příkazy okna a rozměry.
- `rgb444=True` řídí panel ve 12bitovém RGB444 místo 16bitového RGB565:
  ~25 % méně provozu na SPI (3 bajty na 2 pixely) za cenu barevné hloubky.
- `render(sprites, buffer_a, buffer_b, x0, y0, x1, y1, *, background=0)` — vykreslí
  seznam sprite do oblasti pomocí DMA s dvojitým bufferem.
- `picogame.invert(display, on)` — přepne hardwarovou inverzi barev panelu. Mění stav inverze panelu bez posílání pixelových dat, takže krátká inverze vytvoří celoobrazovkový negativ (efekt „zásahu") bez bufferu a bez překreslení. Obaleno v `picogame_fx.InvertFlash`.

### `Scene(display, buffer_a, buffer_b, *, background=0, top=0, bottom=0, left=0, right=0)`
Scéna v retained mode s vykreslováním pomocí dirty regionů. `display` je
`picogame.Display` (rychlý backend) **nebo** běžný `busdisplay.BusDisplay`
(přenositelný backend).
- `add(item, *, fixed=False) -> item` — přidá `Sprite`/`Tilemap`/`Particles`/`Canvas`/`StripDraw`
  a vrátí přidanou položku, takže `spr = scene.add(Sprite(...))` funguje. Pořadí
  vkládání je **zdola nahoru**. `fixed=True` (lze zadat jen jménem) připne položku k obrazovce (ignoruje
  view offset); použij pro HUD / skóre / dialog, které musí zůstat na místě, zatímco se svět
  posouvá přes `set_view`.
  (nejprve přidej pozadí tilemap, pak sprite, popředí tilemap nakonec).
- `add_all(items)` — přidá několik položek najednou (stejné pořadí zdola nahoru).
- `refresh() -> [x1, y1, x2, y2] | None` — porovná stav s předchozím snímkem a překreslí
  jen dirty region; vrací ohraničující dirty rect jako ZNOVUPOUŽÍVANÝ list (přečti
  ho hned — další volání ho přepíše), nebo `None`, pokud se nic nezměnilo.
  První refresh překreslí celou obrazovku (pokryje zbylé pixely z konzole).
- `invalidate()` — vynutí překreslení celé obrazovky při dalším refresh (např. při změně levelu).
- `set_view(ox, oy)` — view offset = pozice počátku scény na obrazovce. Nastav konstantní
  offset pro vycentrování malé hry (např. hra 128×128 na 320×240); aktualizuj ho
  každý snímek pro posouvání většího světa (posouvání překresluje celou obrazovku).
  Sprite/tilemapy pak žijí v běžných souřadnicích scény bez ohledu na umístění.
- `view` — dvojice `(ox, oy)` s aktuálním posunem kamery, jen pro čtení.
- `display` — backend, přes který scéna kreslí, jen pro čtení (obal `pg.Display`,
  kde je zapnutý, jinak prostý busdisplay). `pg.render()`/`pg.invert()` přijímají obě formy,
  takže `pg.render(scene.display, ...)` funguje vždy.

### `Tilemap(tileset, cols, rows)`
Mřížka indexů tilů do `tileset`, tedy bitmapy, jejíž snímky představují jednotlivé tily.
- `get_tile(tx, ty) -> int` — přečte tile.
- `set_tile(tx, ty, value, *, flip_x=False, flip_y=False, transpose=False)` — zapíše ho (a označí jako změněný); příznaky orientace lze zadat jen jménem.
- `move(x, y)` — posune celou mapu; určí pixelovou pozici tilu 0,0.
- `fill(value)` — nastaví všechny tily.
- Čtení `get_tile()` mimo rozsah vrací `0` a `set_tile()` zápis ignoruje (bez výjimky).
- Vlastnosti jen pro čtení: `x`, `y`, `cols`, `rows`.

**Nekompatibilní změna:** tyhle dvě nahradily `tile(tx, ty[, value])` (firmware po 23. 8. 2026) —
starý kód spadne na `AttributeError`. Dost nový musí být **firmware**.

### `Canvas(width, height, *, transparent=None, buffer=None)`
RAM kreslicí plocha skládaná jako vrstva Scene — obecný domov pro tvary.
Přidej ji do `Scene` a kresli do ní; znovu se odešlou jen dirty regiony. Barvy mají wire order.
Předáním existujícího `buffer` (zapisovatelný buffer o `width*height*2` bajtech)
podložíš plochu vlastní RAM, místo aby si ji Canvas alokoval sám.
- Primitiva (všechna berou barvy ve wire order): `clear(color)`, `pixel(x, y, color)`,
  `fill_rect(x,y,w,h,color)`, `rect(x,y,w,h,color)`, `line(x0,y0,x1,y1,color)`,
  `circle(cx,cy,r,color)`, `fill_circle(cx,cy,r,color)`, `ring(cx,cy,r,thickness,color)`,
  `triangle(x0,y0,x1,y1,x2,y2,color)`, `fill_triangle(...)`,
  `ellipse(cx,cy,rx,ry,color)`, `fill_ellipse(...)`, `fill_round_rect(x,y,w,h,r,color)`,
  `frame3d(x,y,w,h,light,dark)` (zkosený box: světlo nahoře/vlevo, tma dole/vpravo),
  `text(x, y, s, fg, font, bg=None)` (složí glyfy fontu v C; `bg=None` = průhledné,
  funguje i v pohledu `StripDraw` bez uchovávání samostatné bitmapy textu),
  `move(x, y)`.
- `blit(bitmap, x, y, frame=0, flip_x=False, flip_y=False)` — vykreslí snímek bitmapy do plochy a respektuje její průhledný klíč. Jde o retained způsob, jak do panelu zapéct ikonu, portrét nebo text.
- Vlastnosti jen pro čtení: `x`, `y`, `width`, `height`.
- `transparent` (barva ve wire order) umožňuje použít plochu jako tvarovaný překryv (HUD,
  ukazatel, vektorová grafika) nad ostatními vrstvami. Stojí `width*height*2` bajtů RAM, takže
  ji nadimenzuj na to, co potřebuješ (např. stavový pruh 320×16 = ~10 KB).
- **Upozornění na RAM:** `Canvas(320, 240)` přes celou obrazovku má **150 KB**, příliš velké pro
  RP2040 (~190 KB heap, ~130 KB souvislých). Udržuj Canvasy malé, nebo použij `Tilemap` pro velká posouvaná
  pole. Viz [poznámky k hardwaru](../hardware.md). Pro *animovanou plochu přes celý snímek* zvaž `StripDraw`
  níže; neuchovává vlastní pixelovou plochu.

### `StripDraw(callback, x=0, y=0, width=0, height=0, *, always_dirty=True)`
Kreslicí vrstva v **immediate-mode** **zcela bez pixelového bufferu**. Přidává se do `Scene`
jako jakákoli vrstva, ale místo uchovávání pixelů volá kreslicí funkci jednou pro každý
strip, který se překrývá s jejím obdélníkem:

```python
def draw(view, vx, vy, vw, vh):
    # `view` je Canvas nad právě vykreslovaným stripem. Jeho místní bod (0, 0) odpovídá
    # pixelu obrazovky (vx, vy). POZOR: (vw, vh) je velikost CELÉ kreslené oblasti, ne
    # vrstvy - obdélník vrstvy omezuje jen to, které stripy (řádky) callback zavolají,
    # NE šířku, do které smíš kreslit. `view.clear()` nebo výplň přes celý view proto
    # u úzké vrstvy přemaluje celou šířku obrazovky; kresli vlastní obdélník přes
    # fill_rect(0, ly, MOJE_S, 1, ...).
    for ly in range(vh):
        Y = vy + ly                                  # řádek obrazovky
        view.fill_rect(0, ly, vw, 1, sky_or_road(Y))

scene.add(pg.StripDraw(draw, 0, 0, 320, 240))
```

- **RAM:** vrstva neuchovává pixelovou plochu o velikosti `width*height*2`. Pseudo-3D silnice
  přes celou obrazovku se proto obejde bez **150 KB** pixelového bufferu, který by potřeboval
  celoobrazovkový `Canvas`. Objekt `StripDraw`, callback a herní stav však paměť používají.
- S výchozím `always_dirty=True` se jeho obdélník **překresluje každý snímek** (žádné
  přeskočení přes dirty-rect), takže ho použij pro *animovaný* obsah: pseudo-3D
  silnice, gradientní oblohy, raycastery, plazmu, procedurální pozadí, nebo tvary,
  které se mění každý snímek. Pro *statickou* grafiku, která většinou stojí, je `Canvas`
  levnější na CPU (překresluje se jen při změně); vybírej podle pohybu, ne podle velikosti.
- `always_dirty=False` z něj udělá vrstvu **na vyžádání**: překreslí se jen když
  zavoláš `.invalidate()` (jinak ji dirty-rect přeskočí jako Canvas), panel ve
  scéně bez vlastní pixelové plochy, který se překresluje jen při změně.
  Takto kreslí své panely `picogame_ui.SceneBox`/`SceneMenu`.
- **Udržuj vnitřní smyčku lehkou:** kreslicí funkce volá primitiva v C, takže několik volání
  `fill_rect` nebo `hline` na strip je levných. Vyhni se náročnému Pythonu pro každý pixel.
- Read/write vlastnosti `x`, `y`, `width`, `height` přesunou nebo změní velikost vrstvy za běhu;
  po zmenšení zavolej `scene.invalidate()`, aby se uvolněná oblast překreslila.
- Kreslí se v **prostoru obrazovky** (ignoruje offset kamery/view). Ve **posouvané** scéně
  (která volá `set_view`) ho přidej jako **fixed** (`scene.add(sd, fixed=True)`), aby jeho dirty rect
  odpovídal tomu, kam kreslí; ve scéně se statickou kamerou na tom nezáleží. Uvnitř callbacku
  převeď bod obrazovky na souřadnice stripu pomocí `(screen_x - vx, screen_y - vy)`. Skládá se nad nižší
  vrstvy a pod vyšší, jako každá vrstva. Viz `examples/picogame_stripdraw_example.py` a
  `examples/journey_hw/journey_mono.py` (silnice závodu, intro tvary, dialogový box RPG).

### `Particles(capacity, *, size=1, gravity=0.0, fade=False)`
Sdružená částicová vrstva (mnoho malých pohyblivých teček) vykreslená jako jedna vrstva Scene,
mnohem levnější než jeden `Sprite` na částici. Přidej ji do `Scene`. S `fade=True`
každá částice během svého života stmívá k černé (vzhled jisker/uhlíků/kouře).
- `emit(x, y, count, speed=1, life=30, color=0xFFFF)` — vytvoří `count` částic na
  (x, y) s náhodnou rychlostí až `speed` px/tick, žijících `life` ticků, ve
  barvě ve wire order (použij `picogame.rgb565`).
- `tick()` — posune o jeden krok (pohyb, gravitace, stárnutí); volej jednou za snímek.
- `clear()` — odstraní všechny částice.
- Pozice jsou sub-pixelové (fixed-point); vrstva překresluje jen tam, kde částice
  jsou (a byly), takže nezanechávají stopy. v1 kreslí plné tečky `size`×`size`.

---

## Příprava grafiky a map

`tools/png2picogame.py` (na straně hostitele, potřebuje Pillow) převádí PNG/BMP na importovatelné
moduly s grafikou a mapami, jejichž barvy už mají správné wire order.

```bash
# Sprite nebo vodorovný atlas animace (formát PAL8/RGB565 se zvolí automaticky):
python3 tools/png2picogame.py hero.png -o hero.py --frames 6

# Svislý či mřížkový tileset -> vodorovný atlas Bitmap (tily 16x16):
python3 tools/png2picogame.py tiles.bmp -o tiles.py --tile 16x16 --transparent-index 15

# Tilemap (indexy palety obrázku jsou indexy tilů) -> datový modul:
python3 tools/png2picogame.py level.bmp -o level.py --map
```

Na zařízení:
```python
import hero, tiles, level
spr = pg.Sprite(hero.bitmap(pg), 40, 120)
tileset = tiles.bitmap(pg)
tm = pg.Tilemap(tileset, level.WIDTH, level.HEIGHT)
level.fill(tm)          # načte data mapy
```

Volby: `--format auto|pal8|rgb565`, `--frames N`, `--tile WxH`, `--map`,
`--transparent-index N` (považuje index palette v režimu P za průhledný), `--rle` (RLE-komprese
jednosnímkové pozadí PAL8).

Volby šetřící velikost (PAL8):
- `--dither` (+ `--colors N`, výchozí 255): Floyd–Steinberg dither při redukci na PAL8; skrývá
  pruhování gradientů (oblohy, osvětlení). Nízké `--colors` (např. 16–32) + `--dither` = retro vzhled.
- `--dedup` (s `--tile WxH`) — sloučí tily, které jsou identické **až na orientaci** (všech 8: 4
  rotace × zrcadlení) do menšího tilesetu → méně RAM tilesetu. Vydá tabulku `REMAP`; přestav svou
  mapu pomocí `v, fx, fy, tp = REMAP[old_index]; tm.set_tile(x, y, v, flip_x=fx, flip_y=fy, transpose=tp)`
  (nese otočení a zrcadlení každého tilu; příznaky orientace lze zadat jen jménem). Typické
  ručně kreslené úrovně mají 40–70 % duplicit. Funguje spolu s orientací jednotlivých buněk `Tilemap`.

---

## Náklady a omezení enginu

> Pro nasazení si přečti [Spuštění na hardwaru](../hardware.md) (`.mpy`, firmware a testování
> na zařízení) a [Vejít se do paměti](../memory.md) (náklady a měření).

- **Uchovávané plochy plánuj podle změřené haldy.** Celoobrazovkový `Canvas(320,240)` má
  150 KB a přesahuje největší souvislý blok současného buildu pro RP2040 PicoPad.
  Drž plochy `Canvas` malé, pro velká pole použij `Tilemap` a pro
  animovaný celoobrazovkový obsah `StripDraw`. Náklady a rozhodovací matice:
  [Kreslicí cesty](/cs/concepts/drawing-paths/) + [MEMORY.md](../memory.md).
- **Dirty regiony snižují provoz na SPI při soustředěném pohybu.** Překreslení celé obrazovky
  stále platí cenu za skládání i přenos; dominantní část závisí na scéně, firmwaru a taktu SPI.
- **Až šest dirty regionů:** překrývající se změny se nejprve spojí. Pokud jich zbývá více
  než šest, `Scene` postupně slučuje dvojici s nejmenším nárůstem plochy. Pohyb na malé ploše
  tak zůstává levný, ale změny rozeseté po obrazovce se mohou blížit úplnému překreslení.
  `refresh()` vrací pro diagnostiku jejich společný ohraničující obdélník, vykreslovač však
  jednotlivé regiony zpracuje samostatně.
- **Nativní typy (`Sprite`, `Bitmap`, …) nemohou nést vlastní atributy** — pro stav objektu
  použij `sprite.data`.
- **PAL8 používá polovinu prostoru RGB565** (1 B/px proti 2). U větší grafiky zvaž také
  zmrazená data, ROMFS nebo postupné čtení; viz
  [Kde je uložená grafika](../memory.md).

---

## Pod kapotou

Jak se `refresh()` nebo `render()` dostane na výstup:

- **SPI cíle se vykreslují po vodorovných stripech.** Engine používá jeden nebo dva malé
  buffery. Pro každý strip vyčistí pozadí, složí překrývající se vrstvy a výsledek odešle.
- **Framebufferové cíle skládají obraz do výstupního framebufferu.** SPI řádkové buffery
  nealokují. Větší dirty region stále znamená více pixelů ke složení, ale bez přenosu přes SPI.
- **Rychlý SPI backend (`pg.Display`)** používá dva buffery a asynchronní DMA. CPU skládá
  další strip, zatímco předchozí je ještě na SPI sběrnici. **Přenositelný backend** přes běžný
  `busdisplay` používá jeden buffer a blokující `bus.send`.
- **Výška stripu** plyne z velikosti alokovaného bufferu (`buffer_len / (width*2)`).
  Menší stripy umožňují jemnější překryv CPU a přenosu na DMA backendu; větší stripy znamenají méně
  blokujících odeslání na přenositelném backendu. Proto se výchozí `STRIP_H` desky liší
  (8 s DMA, 24 bez).
- **Sledování změn** porovnává každou vrstvu s uloženým stavem položky: pozicí, snímkem,
  měřítkem, úhlem, efekty a hodnotou `seq` zvýšenou přes `touch()`. `Canvas`, `Tilemap` a
  `Particles` shromažďují vlastní dirty regiony a předají je při `refresh()`.
- **Rotace a škálování** používají inverzní mapování s pevnou řádovou čárkou. Transformace
  spritu se přepočítá jen při změně úhlu, měřítka, bitmapy nebo kotevního bodu.

---

## Build firmwaru

Engine je nativní modul uvnitř forku CircuitPythonu; jeho build popisuje samostatný
průvodce **[Build firmwaru](../firmware.md)** (nástroje, konfigurace desek a volby). Hotový
firmware pro podporované desky: [Podporovaný hardware](../supported-hardware.md).

---

## Příklady

V kořeni projektu (zkopíruj do `CIRCUITPY/code.py`):

| Soubor | Co ukazuje |
|---|---|
| `examples/picogame_scene_example.py` | retained Scene + dirty-rect (statické pole + pohyblivé objekty) |
| `examples/picogame_hud_example.py` | HUD text přes přibalený font (`picogame_font.py`) |
| `examples/picogame_tilemap_example.py` | tilemap pozadí + sprite nad ním |
| `examples/picogame_scroll_example.py` | kamera a posouvání: větší svět s pohledem sledujícím hráče (`scene.set_view`) |
| `examples/picogame_particles_example.py` | částicové výbuchy s gravitací (`pg.Particles`; viz i `picogame_particles_fade_example.py`) |
| `examples/picogame_stripdraw_example.py` | 0-RAM celoplošné kreslení přes `StripDraw` |
| `examples/picogame_canvas_example.py` | retained Canvas panel |
| `demos/picogame_arkanoid.py` | kompletní hra Breakout/Arkanoid: Tilemap cihly + sprite + collide + částice + HUD |
| `games/squest/code.py` | střílečka ve stylu Seaquest: stav spritů v `sprite.data`, projektily, `collide`, částice, ukazatel kyslíku v HUD a tónový zvuk |
### Struktura projektu

```text
lib/        pomocné moduly enginu (picogame_*)  -> potřebné zkopíruj do CIRCUITPY/lib/
examples/   hry, dema a jejich soubory          -> vybraná hra bude code.py v kořeni
tools/      převodníky grafiky a dat (png2picogame, ...)
```

Nasazení hry na zařízení (pomocné moduly, `.mpy` a grafika) pokrývá
[Spuštění na hardwaru](../hardware.md).
