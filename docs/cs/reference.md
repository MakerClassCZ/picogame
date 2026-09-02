# picogame — rychlá reference

Jednostránkový tahák všeho, co engine nabízí: nativní C modul `picogame`
a pomocné knihovny `picogame_*` v čistém Pythonu ve složce `lib/`. Signatury ukazují názvy parametrů
a výchozí hodnoty; `*` označuje argumenty zadávané pouze jménem. Barvy jsou celá čísla RGB565
ve wire order; vytvářej je pomocí `rgb565()`. Podrobnosti najdeš v [průvodci enginem](../engine.md).

**Viz také:** [Vejít se do paměti](memory.md) · [Kreslicí cesty](/cs/concepts/drawing-paths/) · [Výkon](/cs/performance/) · [Spuštění na zařízení](hardware.md) · [Přicházíš z jiného enginu](/cs/concepts/coming-from/).

---

## Nativní modul: `picogame` (`import picogame as pg`)

### Konstanty a barva
- `RGB565`, `PAL8` — pixelové formáty bitmapy.
- `API_LEVEL` — `int`; generace API enginu, zvyšuje se, když roste plocha viditelná z Pythonu. Knihovny kontrolují `getattr(pg, "API_LEVEL", 0) >= N`, aby příliš starý firmware odhalily rovnou, místo pozdějšího pádu na chybějícím atributu.
- `RGB444_SUPPORTED` — `bool`; jestli panel této desky umí 12bitový RGB444 (umožní hře zapnout `Display(rgb444=True)` jen tam, kde to funguje).
- `FPU` — `bool`; `True`, když 3D matematické primitivy (`pg.project`) běží hardwarovou float cestou (RP2350, ESP32-S3), `False` na RP2040 (16.16 fixed-point). Buffery pro `project` packuj podle toho: `array("f")` když `pg.FPU`, jinak `array("i")` s hodnotami `int(v * 65536)`.
- `rgb565(r, g, b) -> int` — barva z 8bitových kanálů ve wire order.
- `collide(x1, y1, x2, y2, ax1, ay1, ax2, ay2) -> bool` — překryv dvou AABB s osmi argumenty nebo bod v obdélníku se šesti argumenty. Hranice jsou včetně dotyku. Obdélník spritu předej jako `(x, y, x+w, y+h)`.

### `Bitmap(data, width, height, *, format=RGB565, palette=None, frames=1, stride=0, transparent=None)`
Obrazový atlas stejně velkých snímků libovolné velikosti. `data` je buffer; `palette` je pro `PAL8` povinné pole barev ve wire order. `transparent` určuje index nebo barvu, která se při vykreslení přeskočí.
- Vlastnosti jen pro čtení: `width`, `height`, `frames`, `format`, [`stride`](/cs/concepts/glossary/) (pixelů na řádek zdroje; nech `0` pro těsně zabalená data, nastav jen pro podokno většího obrázku), `palette` (buffer palety PAL8 nebo `None`) a `transparent` (průhledná hodnota nebo `None`).

### `Sprite(bitmap, x=0, y=0, *, frame=0, visible=True, flip_x=False, flip_y=False)`
Umístěná, animovatelná instance Bitmap.
- Vlastnosti pozice a animace: `x`, `y` (celé pixely) · `fx`, `fy` (desetinná poloha) · `frame` · `visible` · `flip_x`, `flip_y` · `bitmap` (výměna) · `data` (uživatelská data).
  **Nikdy nemíchej obojí na téže ose.** Je to JEDNA uložená hodnota: zápis do `x` ji PŘEPÍŠE a zahodí desetinný zbytek, takže klasické „sčítej v `fx`, ořízni přes `x`" pomalý pohyb úplně zastaví (drift 0,4 px/frame ořez nikdy nepřežije). Ořezávej taky přes `fx`/`fy`. Na zařízení to platí stejně — firmware drží 24.8 fixed point a jeho setter `x` ji přepíše identicky, takže simulátor tady nelže.
- Transformace (metoda nejbližšího souseda, kolem kotevního bodu):
  - `scale` — float měřítko vykreslení; `1.0` = nativní (rychlá cesta), `2.0` = dvojnásobná velikost, zlomky povoleny (např. pulz).
  - `angle` — rotace ve stupních; `0` = žádná (rychlá cesta). Kombinuje se se `scale`.
  - `transpose` — bool; prohodí osy X/Y. Samotné znamená zrcadlení přes diagonálu, ne rotaci. Pro rotaci o čtvrtotáčku ho spoj s flipem. S `flip_x` a `flip_y` vytvoří všech 8 orientací. Funguje na rychlé cestě se scale 1 a angle 0; vykreslený obdélník prohodí w/h. Na obrazovce s osou y dolů: **90° CW** = `transpose+flip_y` · **180°** = `flip_x+flip_y` · **270° CW** = `transpose+flip_x`.
  - `anchor` = `(fx, fy)` — kotevní bod jako zlomky bitmapy (0..1): `(0.5, 0.5)` = střed, `(0.5, 1.0)` = dole uprostřed. `x`/`y` a rotace se vztahují k tomuto bodu.
- Efekty vykreslení (vždy jen jeden; PRAVDIVÝ zápis do kteréhokoli zruší ostatní tři, ale NEPRAVDIVÝ zápis (`spr.flash = 0`) zruší JEN svůj vlastní efekt - `spr.dither = 0` tedy nevypne aktivní flash, vypínej ten, který jsi zapnul; bez dalších bitmap):
  - `shadow` — bool; neprůhledné pixely ztmaví cíl, například pro vržený stín nebo tmavý překryv.
  - `flash` — barva RGB565 ve wire order (nebo `0`/`None` = vypnuto); neprůhledné pixely vykreslí touto plnou barvou. Záblesk trvá obvykle 1–3 snímky.
  - `tint` — barva RGB565 ve wire order (nebo `0` = vypnuto); vynásobí jí neprůhledné pixely, takže sprite obarví a **zachová jeho stínování**.
  - `dither` — `0` (neprůhledné) .. `16` (neviditelné); Bayer-stipple průsvitnost, bez alfy (duchové, mlha, fade-in/out).
- `move(x, y)` — nastaví pozici. · `touch()` — označí dirty po in-place úpravě bitmapy/palette.
- `overlaps(other, inset=0) -> bool` · `near(other, r) -> bool` — nativní kolizní testy (viz **Kolize spritů** níže).

### `Display(busdisplay, *, rgb444=False)`
Rychlý backend s DMA, který obaluje `busdisplay` desky s FourWire SPI. Předej ji do `Scene`. `rgb444=True` řídí kompatibilní panel ve 12bitovém RGB444 a sníží počet přenášených bitů na pixel o 25 %. Podporu ověř přes `RGB444_SUPPORTED`.

### `Scene(display, buffer_a, buffer_b, *, background=0, top=0, bottom=0, left=0, right=0)`
Retained scéna s vykreslováním podle dirty regions. Na SPI backendu jsou `buffer_a` a `buffer_b` strip buffery; s `pg.Framebuffer` mohou mít hodnotu `None`.
- `add(item, *, fixed=False) -> item` — přidá Sprite/Tilemap/Particles/Canvas/StripDraw (pořadí vkládání = zdola→nahoru) a vrátí ho (takže `spr = scene.add(Sprite(...))` funguje). `fixed=True` (jen keyword) ho připne k obrazovce (ignoruje kameru) pro HUD/dialog.
- `add_all(items)` — přidá několik (zdola→nahoru).
- `remove(item)` — odpojí dříve přidaný objekt; odebrání vynutí PLNÉ překreslení při příštím refresh (bez „duchů"). `Scene.invalidate()` nebere ŽÁDNÉ argumenty — pod-obdélníková forma patří `StripDraw.invalidate(x, y, w, h)` (všechny čtyři pozičně, nebo nic); objekt samotný zůstává a lze ho později znovu `add()`ovat. `ValueError`, pokud ve scéně není.
- `set_view(ox, oy)` — offset kamery (pozice počátku scény na obrazovce); jeho změna překreslí vše.
- `view` — dvojice `(ox, oy)` s aktuálním posunem kamery, jen pro čtení.
- `invalidate()` — vynutí překreslení celé obrazovky při dalším `refresh()`.
- `refresh() -> list | None` — porovná a překreslí dirty regiony; vrací dirty rect `[x1,y1,x2,y2]` (znovupoužitý) nebo None. **Simulátor dirty-rect nemá**: překresluje vše a vrací celý play rect — nebo `None`, když je hotový frame pixelově shodný s minulým (parita s firmwarem kvůli idiomu `if scene.refresh():`). VELIKOST toho rectu tedy v simu nic neměří, ale jeho pravdivostní hodnota ano.

### `Tilemap(tileset, cols, rows)`
Mřížka indexů do bitmapy tilesetu, kde každý snímek představuje jeden tile; vrstva `Scene`.
- `get_tile(tx, ty) -> int` — přečte tile. · `set_tile(tx, ty, value, *, flip_x=False, flip_y=False, transpose=False)` — zapíše ho. Pojmenované argumenty `flip_x`/`flip_y`/`transpose` nabízejí všech osm orientací buňky; použij je s deduplikovaným tilesetem z `png2picogame.py --dedup`. Čtení mimo rozsah vrátí 0 a zápis se ignoruje. Pole orientace se alokuje až při prvním použití.
- `fill(value)` — nastaví každý tile (vymaže orientaci).
- `move(x, y)` — umístí mapu.
- Vlastnosti jen pro čtení: `x`, `y`, `cols`, `rows`.
**Nekompatibilní změna:** nahradily `tile(tx, ty[, value])` (firmware po 23. 8. 2026); starý kód
spadne na `AttributeError`. Dost nový musí být firmware.

### `Particles(capacity, *, size=1, gravity=0.0, fade=False)`
`gravity` je px/tick² přičítané k vy každý tick, ořezané na **-128..127.99**; ZÁPORNÁ gravitace je legální a částice pak STOUPAJÍ (jiskry, bubliny). Pozice částic jsou ve **světových** souřadnicích - `scene.set_view` s nimi hýbe jako s každou jinou vrstvou.
Sdružená částicová vrstva (malé pohyblivé tečky) vykreslená jako jedna vrstva Scene.
- `emit(x, y, count, speed=1, life=30, color=0xFFFF)` — výbuch `count` teček, náhodná rychlost ≤ `speed` px/tick, žijících `life` ticků.
- `tick()` — posune o jeden krok pohyb, gravitaci a stárnutí. Volej jednou za snímek.
- `clear()` — odstraní vše.

### `Canvas(width, height, *, transparent=None, buffer=None)`
Kreslicí plocha RGB565 skládaná jako vrstva scény (`width*height*2` bajtů). `transparent` z ní udělá tvarovaný překryv; `buffer` ji podloží externí pamětí, například částí arény. Pro animované plochy přes celý snímek zvaž `StripDraw`, který nedrží vlastní pixelovou plochu.
- `clear(color)` · `pixel(x, y, color)` · `fill_rect(x, y, w, h, color)` · `rect(x, y, w, h, color)`
- `line(x0, y0, x1, y1, color)` · `circle(cx, cy, r, color)` · `fill_circle(cx, cy, r, color)` · `ring(cx, cy, r, thickness, color)`
- `triangle(x0,y0, x1,y1, x2,y2, color)` · `fill_triangle(...)` · `ellipse(cx, cy, rx, ry, color)` · `fill_ellipse(...)`
- `fill_round_rect(x, y, w, h, r, color)` · `frame3d(x, y, w, h, light, dark)` (zkosený box) · `move(x, y)`
- `blit(bitmap, x, y, frame=0, flip_x=False, flip_y=False)` — vykreslí snímek bitmapy do plochy a respektuje její průhledný klíč; retained způsob, jak do panelu zapéct ikonu, portrét nebo text.
- `text(x, y, s, fg, font, bg=None)` — složí řetězec v C a znaky fontu typu `fontio.BuiltinFont` rasterizuje za běhu. Nevytváří další bitmapu ani sprite textu. `bg=None` znamená průhledné pozadí znaku. Funguje na `Canvas` i na pohledu `StripDraw`; cílový `Canvas` však stále vlastní svou pixelovou plochu. **Vestavěný `terminalio.FONT` má pevnou buňku 6×12**, takže řetězec je `len(s) * 6` px široký a vycentruješ ho jako `(W - len(s) * 6) // 2` (oba zdejší fonty jsou fixed-width: `picogame_bitfont` má 8×8). Při 6 px/znak se na 320px displej vejde 53 znaků a na 240px jen 40 — počítej text podle toho menšího.
- `mode7(texture, horizon, y_off, z, rx0, ry0, rsx, rsy, cam_x, cam_y)` — vyplní řádky pod `horizon` **Mode-7 perspektivní podlahou** (`texture` je Bitmap, `horizon`/`y_off` jsou pixelové řádky, zbylých 7 argumentů je 16.16 fixed-point)** textury (rozměry mocniny dvou; jedna světová jednotka = jedna dlaždice). 10 fixed-point (16.16) argumentů — normálně je necháš dopočítat `picogame_mode7.Camera` z pozice kamery. Kreslí do `Canvas` nebo 0-RAM `StripDraw` view (předej `y_off` = horní okraj stripu).
- `vspans(x0s, x1s, tops, bots, colors, n, x_off=0, y_off=0)` — vyplní `n` **svislých barevných spanů** jedním voláním: span *i* pokrývá `x0s[i]..x1s[i]` × `tops[i]..bots[i]` (obojí exkluzivně) barvou `colors[i]`; všech pět jsou uint16 pole. Dávkový primitiv pro sloupcové renderery — `picogame_ray` maluje své sloučené runy stěn jedním voláním na strip (`x_off=-vx, y_off=-vy` replay, spany mimo pás se odmítnou dvěma porovnáními), čímž jeho per-strip cena přestala záviset na počtu runů (změřeno: full-screen stride-1 raycast snímek 203–275 ms → ~27 ms (~36 fps)).
- `fill_triangles(verts, colors, n, x_off=0, y_off=0)` — vyplní `n` trojúhelníků **jedním voláním**: `verts` = int16 `x0,y0,x1,y1,x2,y2` na trojúhelník, `colors` = wire-RGB565 uint16 na trojúhelník. Stejný rasterizér jako `fill_triangle`, ale celá dávka překročí hranici Python/C jen jednou — výhra pro mnoho malých trojúhelníků (blocky 3D, low-poly, izometrie), kde jinak dominuje ~10 µs režie na volání. `x_off`/`y_off` posunou každý vrchol před clippingem: předej `y_off=-vy` ve `StripDraw` callbacku a **přehraj jednu screen-space dávku do každého render stripu** (trojúhelníky mimo pás se odmítnou třemi porovnáními) — full-res 3D úplně bez retained canvasu, preferovaná cesta na framebuffer deskách. Partner `pg.project` a `picogame_iso.emit_blocks`.
- `road(ri0, tab, rl, rr, d05_q8, d07_q8, colors)` — vykreslí jeden strip **závodní silnice ve stylu OutRun** z předpočítaných tabulek: celá per-scanline smyčka (výběr barev nebe/silnice/krajnice/čáry) v jednom volání. `ri0` = řádek road-tabulky na řádku 0 této plochy (záporný = řádky nebe); `tab` = int16 řádky `{edge_w, dash_hw, wb05_q8, wb07_q8, flags}`; `rl`/`rr` = int16 okraje z `pg.road_edges`; `d05/d07` = Q8 fáze scrollu; `colors` = 6× uint16 `{sky, road_a, road_b, rumble_a, rumble_b, dash}`. Navrženo jako tělo `StripDraw` callbacku (0-RAM silnice).
- Vlastnosti jen pro čtení: `x`, `y`, `width`, `height`.

### `StripDraw(callback, x=0, y=0, width=0, height=0, *, always_dirty=True)`
Immediate vrstva bez vlastní pixelové plochy. Při `refresh()` volá `callback(view, vx, vy, vw, vh)` pro části svého obdélníku, které backend právě skládá. `view` je pohled typu `Canvas` do aktuální cílové oblasti; použij jeho kreslicí primitiva včetně `view.text()`. Místní `(0,0)` odpovídá obrazovkovému `(vx, vy)`. Je VŽDY v obrazovkových souřadnicích, takže `fixed=True` u ní nic nedělá — v posouvané scéně se ani neposouvá, ani nerozmazává.
- `always_dirty=True` (výchozí) překresluje každý snímek, proto se hodí pro animovaný obsah a efekty po řádcích. `always_dirty=False` překresluje jen po invalidaci nebo když ho překryje jiná změna, proto se hodí pro panely měněné na vyžádání. Při prvním `refresh()` se vykreslí vždy.
- `invalidate()` — označí ho jako dirty, aby ho příští refresh překreslil (způsob, jak aktualizovat panel s `always_dirty=False`, když se změní jeho obsah).
- JEDINÁ vlastnost je `count` — kolik trojúhelníků příští refresh kreslí (přiřazení označí vrstvu dirty). Typ nemá x/y/width/height/always_dirty.

### `Triangles(verts, colors)`
Retained **screen-space dávka trojúhelníků**, kterou kompozitor rasterizuje **celou v C** per render strip (levný band reject + Canvas rasterizér) — žádný pixel buffer A žádný Python per strip. `verts` = int16 pole (`x0,y0,x1,y1,x2,y2` na trojúhelník), `colors` = uint16 wire-RGB565 na trojúhelník — obojí **vlastní volající** (plníš je in-place každý snímek). Tohle je **vrstva pro 3D scény**: `pg.project` do polí, painter's pořadí stěn, nastav `count`, `scene.refresh()`. Protože při kompozici neběží žádný Python, zůstává skládatelná core1 band splitem — na rozdíl od `StripDraw` callbacku.
- `count` — kolik trojúhelníků se příští refresh kreslí (oříznuto kapacitou bufferů); **přiřazení označí vrstvu dirty** pro plné překreslení (v živé 3D scéně ho nastav každý snímek).
- Změřeno (roadhop lab): nahrazuje `fill_triangles`-v-StripDraw replay s ~30 % kratším refreshem na 320×240 a odemyká dvoujádrovou kompozici (640×480 na zamčených 20 fps na RP2350 s volným druhým jádrem).

### Nízkoúrovňové kreslicí funkce
Většina her je nikdy nevolá (interně je používá `picogame_game.setup` + `Scene`), ale jsou dostupné pro ručně psané render smyčky.
- `render(display, layers, buffer, x0, y0, x1, y1, *, background=0)` — vykreslí seznam vrstev (libovolný druh scénické vrstvy) do oblasti `[x0,x1) × [y0,y1)`. Na SPI backendu je `buffer` znovu použitelný strip buffer, na framebufferovém backendu může být `None`. Scéna neví, že okamžité `render()` změnilo pixely. Pokud oblast zasahuje do jejího herního obdélníku, potom zavolej `scene.invalidate()` nebo použij `picogame_game.overlay()`.
- `invert(display, on)` — přepne hardwarovou inverzi kompatibilního SPI panelu bez posílání pixelových dat. Framebufferové výstupy tuto funkci nepodporují. Viz `picogame_fx.InvertFlash`.
- `project(cam, pts, n, out_sx, out_sy)` — **dávková perspektivní projekce** `n` 3D bodů na obrazovku v C. `cam` = 15 parametrů kamery `(ex,ey,ez, rx,rz, ux,uy,uz, fx,fy,fz, focal, cx0, cy0, near)`, `pts` = `n×3` světové souřadnice, `out_sx`/`out_sy` = int16 obrazovkové souřadnice (bod za near rovinou dostane sentinel `-32768` — jeho stěny přeskoč). Formát bufferů se řídí `pg.FPU` (float32 na FPU deskách, 16.16 int32 na RP2040 — nesoulad formátu cullne všechno = černá obrazovka). Jedno volání za snímek + `Canvas.fill_triangles` = skutečné flat-shaded polygonové 3D (třída Elite): promítni vrcholy, painter's sort stěn, vyplň. ~0,7 ms/480 bodů na RP2350, ~2,2 ms na RP2040.
- `road_edges(rl, rr, hw, n, cx0, dist, cfg)` — **akumulátor zatáček + celočíselné tabulky okrajů** jednoho snímku závodní silnice v jediném volání (smyčka `compute_road` OutRun žánru). `rl`/`rr` = int16 výstupy pro `Canvas.road`, `hw` = int32 Q16 poloviční šířky per řádek, `cx0` = Q16 střed obrazovky (vč. laterálního posunu), `dist` = celočíselná světová vzdálenost, `cfg` = int32[7] konfigurace **zatáček** (`f1,f2` Q20 frekvence, `a1k,a2k` Q16 amplituda×zisk, světový krok, krok zatáčky, posun řádku) — kopce v ní NEJSOU: `road_edges` počítá jen vodorovné okraje a kopce vznikají posouváním horizontu, který předáváš jako `ri0` do `Canvas.road`. Páruje se s `Canvas.road` na 0-RAM silnici ve 30 fps na RP2040.
- `vblank(framebuffer)` — (DVI desky, RP2350) předej `picodvi.Framebuffer`, ze kterého displej scanoutuje; blokuje do jeho dalšího vertikálního zatmění (≤ ~16,7 ms). Kompozice odstartovaná hned po vblanku drží publikační frontu konzistentně za paprskem, takže každý sweep zobrazí jeden **celý** snímek — odstraňuje single-buffer tearing, dokud se kompozice vejde do dvou sweepů. Stojí to čekání: počítej s ním proti FPS capu.
- `core1(on) -> bool` — (RP2 desky) pošle dělitelné kernely enginu (`Canvas.mode7` řádky, pásy fb kompozice) přes druhé jádro. Vrací **výsledný** stav: `False`, když core1 není k dispozici — např. **USB-host deska (Fruit Jam) na něm trvale provozuje USB servis**, takže engine odmítne místo jeho přepsání. Dvoujádrová kompozice změřena ~1,75× na RP2350 s volným core1.
- **`core1` NENÍ v žádném releasu CircuitPythonu.** Žije na větvi `picogame-core1` v našem forku a do upstreamu zatím nešel, takže `pg.core1` na firmwaru staženém z circuitpython.org vyhodí `AttributeError`. Ošetři to přes `hasattr(pg, "core1")` a ber dvoujádrovou cestu jako optimalizaci, kterou možná nemáš.

### Procedurální šum (koherentní value noise, 0..1)
- `value2d(x, y, *, seed=0) -> float` · `value1d(x, *, seed=0) -> float`
- `fbm2d(x, y, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` · `fbm1d(x, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` — fraktální (součet oktáv).

---

## Pomocné knihovny (`lib/picogame_*.py`, čistý Python)

### `picogame_game` — spuštění jedním voláním
- `setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0, rgb444=False) -> (scene, buffer_a, buffer_b)` — vybere backend a vytvoří scénu. Na SPI backendu vrátí dva strip buffery, na framebufferu dvakrát `None`. `top/bottom/left/right` rezervují okraje HUD; `rgb444=True` zapne 12bitové barvy na podporovaném SPI panelu a `rgb444="auto"` se řídí `RGB444_SUPPORTED`.
- `overlay(scene, display, items, buffer, x0, y0, x1, y1, *, background=0)` — okamžité vykreslení `items` přes živou scénu (pauza / menu / cutscéna / banner) = `pg.render` + `scene.invalidate()`, takže další `refresh()` překreslí celý snímek místo ponechání zbytků overlaye.
- `screen() -> (width, height)` — rozměry obrazovky z displeje, který deska poskytuje. Rozvrhni podle nich hru místo natvrdo psaných 320×240.
- `display()` — tentýž objekt displeje (pro `pg.render`, `picogame_fx.InvertFlash`, …). Obojí čte `supervisor.runtime.display` — primární displej desky, který CircuitPython vybere hned po inicializaci a který zveřejní `boot.py`, spouštěč nebo `open_framebuffer()` přes `supervisor.runtime.display = disp`. Je to jediná cesta, kterou se displej ke hře dostane, takže stejný soubor běží na PicoPadu, Fruit Jamu, holém Picu, v simulátoru i ve hřišti v prohlížeči (poslední dva mají malý shim `supervisor`).
- `open_framebuffer(width, height, color_depth=None) -> display` — nastaví rozlišení z kódu hry na framebufferové desce (Fruit Jam DVI), např. `open_framebuffer(640, 480)`; na pevném SPI panelu je to no-op vracející aktuální displej. Výsledek předej do `setup(display=…)`.
- `resolve_display(display=None) -> (display, is_framebuffer)` — sjednotí handle displeje/framebufferu (používají HUD / helpery okamžitého renderu).

### `picogame_clock` — časování snímků
- `Clock(fps=30, max_dt=0.1)` · `.set_fps(fps)` · `.tick() -> dt` (počká do dalšího snímku a vrátí sekundy) · `.tick_async()` (totéž pro smyčku `asyncio`).
- `FixedStep(step_fps=60, max_steps=5)` · `.steps()` — generátor vracející konstantní dt na fixní krok · `.step_count()`.

### `picogame_input` — tlačítka
- Masky: `UP DOWN LEFT RIGHT A B X Y L1 L2 R1 R2 START SELECT ALL` (superset; každá deska mapuje jen tu podmnožinu, kterou má); profil `PICOPAD`.
- `Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)` · `.poll() -> mask` · `.is_pressed(mask=ALL)` · `.just_pressed(mask=ALL)` · `.just_released(mask=ALL)` · `.has(mask=ALL)` (je maska v profilu) · `.repeat(button, delay=15, interval=4)` — PICO-8 `btnp` auto-repeat (menu / pohyb v mřížce) · `.clear()` (zahodí držený stav) · `.attach(source)` / `.detach(source)` — za běhu při-OR-uje/odebere další vstupní zdroj (attract demo přes `picogame_seq.Script`, pozdě připojený USB pad).
  - `matrix=` — zdroj skenované klávesové matice (nastavitelný i přes klíče `PICOGAME_MATRIX_*`); `usb=` — jeden či více dalších **zdrojů** tlačítek (USB pad/klávesnice, níže). `Buttons` všechny zdroje ORuje dohromady, takže hra je čte bez jediné změny kódu.
- `Timer(frames)` — okno vstupní tolerance (coyote time / jump buffering): `.feed(condition)` (dobíjí, dokud je true, jinak slábne) · `.charge()` · `.is_active` · `.consume()` (true jednou, pak se vymaže).

### `picogame_usbpad` — USB HID gamepad jako zdroj (desky s USB hostem, např. Fruit Jam)
- `UsbPad(buttons=None)` — zdroj tlačítek pro `Buttons(usb=…)` (na buildu s USB hostem se připojí sám). Čte USB HID gamepad a ORuje ho do masky, takže připojený pad funguje **bez jakékoli změny kódu hry**. Vyžaduje CircuitPython build s USB hostem (`usb.core`); na deskách bez něj se nezavádí.
- Výchozí mapování = běžný DragonRise `081f:e401` (SNES-style pad); přemapuj kterýkoli pad ze `settings.toml` (`PICOGAME_USBPAD`, bez reflashe — viz [Vlastní deska](custom-board.md)). Report byty nového padu zjistíš pomocí `tools/usbpad_probe.py`.
- `.mapped` — maska tlačítek, která pad umí hlásit; modulové konstanty `VERSION`, `MAPPED`.

### `picogame_usbkbd` — USB HID klávesnice jako zdroj (desky s USB hostem)
- `UsbKbd(keys=None)` — dvojče `UsbPad`, zdroj pro `Buttons(usb=…)`. Nalezena podle boot-keyboard HID rozhraní (bez pevného VID/PID); funguje s drátovými i 2,4GHz dongle klávesnicemi (ne Bluetooth).
- Výchozí mapování: šipky + WASD → D-pad, Z/mezerník → A, X → B, C → X, V → Y, Q → L1, E → R1, Enter → START, Esc → SELECT. Přemapuj ze `settings.toml` (`PICOGAME_USBKBD`, `NAME=HID-keycode`). U combo donglu, jehož skutečné klávesy jdou po sourozeneckém rozhraní, nasměruj driver klíčem `PICOGAME_USBKBD_EP = "iface:endpoint"` (najdeš přes `tools/usbkbd_probe.py`).

### `picogame_font` — textové bitmapy (externí modul fontu)
Kterou textovou cestu použít (`Canvas.text` vs vyrenderovaná Bitmap vs StripDraw view — a co která stojí): viz rozhodovací matice v [Drawing paths](/cs/concepts/drawing-paths/).
- `render_text(pg, font, text, fg, bg=None) -> (bitmap, w, h)` — vykreslí řetězec do PAL8 Bitmap (`bg=None` → průhledné).
- `render_text_pal(pg, font, text, fg, bg=None) -> (bitmap, w, h, palette)` — totéž, plus pole palety; změnou `palette[1]` přebarvíš text bez přestavby bitmapy.
- `Label(pg, font, x, y, fg, bg)` · `.move(x, y)` · `.set(text) -> changed` · `.draw(display, buffer)`.

### `picogame_bitfont` — vestavěný font (bez modulu fontu, pevná buňka 8×8: `GLYPH_W`/`GLYPH_H`)
- `render_text(pg, text, fg=None, outline=None, mid=None, bg=None) -> (bitmap, w, h)` — vykreslí přibaleným bitmapovým fontem; volitelné `outline`/`mid` dají levný 2tónový obrysový vzhled.

### `picogame_ui` — HUD a menu widgety (`LINE_H = 12`)
- `SceneLabel(scene, pg, font, x, y, fg, bg=None, scale=1, fixed=True)` · `.set(text)` · `.reserve(chars)` · `.show(on)` · `.color(fg)` · `.destroy()` — textový popisek nezávislý na kameře (fixní vrstva scény). `reserve(chars)` ho přepne na buffer PEVNÉ šířky postavený jednou: `set()` pak skládá znaky na místě — žádný růst ani přestavba Bitmapy/palety (skládání nechá ~0,5-1,5 KB krátkodobého slice-odpadu na ZMĚNĚNÝ update (změřeno: RP2040 ~0,6 KB, ESP32-S3 ~1,4 KB), uvolní ho nejbližší GC — aktualizuj při změně, ne každý frame) a popisek nemůže růst-realokovat na fragmentované haldě. Přiřazením `.x` / `.y` ho PŘESUNEŠ (scéna překreslí starý i nový rect); metriku šířky nemá, takže měnící se hodnotu CENTRUJ rezervací nejširšího řetězce a paddingem mezerami (font má pevnou buňku, 6 px/znak — `ui.text_width` / `ui.centred`). `scale=2` zdvojnásobí glyfy (na titulní banner není potřeba druhý sprite); `show(False)` ho SKRYJE - tak se rezervovaný popisek maže, protože `set(" ")` přemaluje CELOU rezervovanou šířku barvou `bg` (viditelný pruh). `color()` přebarví bez přestavby. destroy() odpojí JEDNORÁZOVÝ popisek, aby ho GC uvolnil (opakovaný HUD: postav jednou + set/hide).
- `SceneBox(scene, pg, font, x, y, w, h, fg, bg, nlines=3, key=None, border=None)` · `.show(lines)` · `.hide()` · `.set_line(i, text)` — víceřádkový panel ve scéně (dialog/log) · `.destroy()` = jednorázový úklid (vyžaduje firmware se `Scene.remove`).
- `HudBar(pg, display, buffer, x, y, w, h, bg)` · `.add(sprite)` (ikona Sprite) · `.label(font, x, y, fg, text=" ")` → objekt popisku, který aktualizuješ přes `handle.set(text)` · `.draw()` — okamžitě skládaný pruh bez pixelové plochy velikosti panelu; volej při změně HUD.
- `TextBox(pg, font, x, y, w, h, fg, bg, maxlines=6)` · `.draw(display, buffer, lines, force=False)`.
- `Menu(pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None, paged=True)` · `.tick(btn)` → index ≥0 na A, `CANCEL` (= -2) na B, `None` během navigace · `.draw(display, buffer, force=False)`.
- `SceneMenu(scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None, border=None, paged=True)` · `.show(sel=0)` · `.hide()` · `.set_items(items, sel=0)` (vymění položky a změní velikost BEZ nové vrstvy scény) · `.tick(btn)` → index ≥0 na A, `CANCEL` (= -2) na B, `None` během navigace — totéž menu jako vrstva ve scéně.
- `GridCursor(cols, rows, tx=0, ty=0, wrap=False, delay=15, interval=4)` · `.index` · `.tick(btn) -> (tx, ty) | None | ui.CANCEL` — `delay`/`interval` ladí opakování při držení směru (framy do prvního opakování / mezi opakováními) — kurzor na D-padu po mřížce (inventář / herní deska). `tick` se hýbe drženým D-padem (auto-repeat) a vrací vybranou buňku na A, `ui.CANCEL` na B, jinak `None`; hlídej přes `if pick is not None and pick is not ui.CANCEL:` (tuple neumí `>= 0`).

### `picogame_options` — menu nastavení
- `OptionsMenu(scene, pg, font, x, y, w, rows, fg, bg, title=None, border=None, visible=True)` · `.value(key)` · `.show(sel=0)` · `.hide()` · `.set_rows(rows, sel=0)` · `.tick(btn)` — **jeho `tick()` vrací KLÍČ řádku, zatímco `SceneMenu`/`Menu` vrací INDEX** (jediný rozdíl, který kousne při přechodu z jednoho na druhý) — obrazovka nastavení (přepínače/volby) ve scéně.

### `picogame_shapes` — generátory jednobarevných bitmap
- `rect(w, h, color)` · `circle(d, color)` · `ring(d, color, thickness=2)`
- `from_mask(mask, color)` — Bitmap ze **seznamu řetězců**, jeden na řádek (`'#'`, `'X'` nebo `'1'` = nastaveno); rozměr podle masky. `color` může být i **slovník {znak: barva}** - pak má každý znak vlastní položku palety (neuvedené znaky, třeba `.` nebo mezera, zůstanou průhledné), takže JEDNA maska nese tělo + obrys + odlesk: `from_mask(["  ##  ", " #oo# ", "#o..o#"], {"#": OBRYS, "o": TELO, ".": ODLESK})`. Tím dostaneš identitu tvarem I barvou, kterou žádá designový standard, bez ručního stavění PAL8 atlasu. Předat jeden řetězec není chyba — každý ZNAK se stane řádkem, takže dostaneš sprite široký 1 pixel a žádnou výjimku.
- `masks(mask_list, color)` — **vícesnímkový `from_mask`**: seznam maskových stringů → jedna horizontální atlas Bitmapa (snímek *i* = `mask_list[i]`), rozměr podle největší masky. Chybějící krok mezi `from_mask` (jeden snímek) a `atlas` (syrové 0/1 buffery, které nic jiného nevyrábí) — animované nebo vícestavové maskové art ho potřebovalo a každá hra si ho odvozovala znovu. Plochý seznam řetězců (= jedna maska) vyhodí `TypeError` místo tichých 1px snímků.
- `atlas(frames_data, w, h, color)` — zabalí buffery w×h do vícesnímkové bitmapy.
- `color_frames(w, h, colors)` — snímek `i` vyplní barvou `colors[i]`.
- `tileset_colors(w, h, colors, gap=0)` — tileset: snímek 0 je prázdný, snímky 1..N obarvené; `gap=N` vyřízne do každé dlaždice N-px průhledný pravý+spodní okraj, takže sousedící stejnobarevné dlaždice zůstanou rozlišitelné (cihlová zeď má spáry, ne pruhy).
- `poly_frames(size, points, nframes, color, fill=True)` — předem vygeneruje `nframes` rotací polygonu.

### `picogame_pool` — znovupoužitelný pool spritů
- `Pool(scene, bitmap, capacity, anchor=None, fixed=False)` · `.spawn() -> sprite | None` · `.free(s)` · `.free_all()` · `.count() -> int`. (`.items` = všechny sprite.)
- **`visible` znamená jen „kresli"** — pool si drží vlastní bit obsazenosti (`.alive`, bajt na slot), takže blikat pooled spritem přes `.visible` je bezpečné: jeho slot zůstane obsazený. `spawn()` vydaný sprite rozsvítí a `free()` ho zase skryje, takže `if not s.visible: continue` zůstává správná hlídka života. Dokud sprite bliká zhasnutý, hlídka ho přeskočí a ten snímek se nehýbe — když to vadí, hlídej místo toho `pool.alive[i]`.

### Kolize spritů (nativní metody)
Kolize je přímo na `Sprite`: bez alokace, anchor/scale/rotace aware (žádný samostatný modul).
- `Sprite.overlaps(other, inset=0) -> bool` — inkluzivní AABB překryv (dotek = zásah). `other` = další `Sprite`, bod `(x, y)`, nebo rect `(x1, y1, x2, y2)` (trigger zóna / culling). `inset` zmenší box TOHOTO spritu o N px na každé straně pro férový hitbox.
- `Sprite.near(other, r) -> bool` — kruhové: střed tohoto spritu do `r` px od středu `other` (kvadrát vzdálenosti, bez sqrt). `other` = `Sprite` nebo bod `(x, y)`.
- Syrový primitiv (libovolné souřadnice, bez spritu): `pg.collide(x1, y1, x2, y2, ax1, ay1[, ax2, ay2])` — 8 arg box-box, 6 arg box-bod.
- Kolize s mřížkou tilů, například zdi a terén: dotazuj se přes `picogame_tiles` (`at_px(tm, x, y, SOLID)`), ne přes AABB každého tilu.

### `picogame_math` — numerické helpery, vektory a trigonometrie v otáčkách
- `clamp(v, lo, hi)` · `mid(a, b, c)` · `lerp(a, b, t)` · `inv_lerp(a, b, v)` · `remap(v, a, b, c, d)` · `sgn(x)` · `approach(v, target, step)` · `wrap(v, lo, hi)`.
- `sin_t(turns)` · `cos_t(turns)` · `atan2_t(dy, dx) -> turns` — úhly jako 0..1 otáčky (standardní, ne PICO-8 invertovaný sin).
- `length(dx, dy)` · `distance(x1, y1, x2, y2)` · `normalize(dx, dy)` · `angle_rad(dx, dy)` (radiány) · `from_angle_rad(a, mag=1.0)` — vektorové helpery.

### `picogame_tiles` — příznaky jednotlivých tilů (PICO-8 `fget`/`fset`)
- Bity/masky: `B_SOLID B_HAZARD B_LADDER …` (indexy) a `SOLID HAZARD LADDER …` (masky).
- `TileFlags(flags=None, tile_px=8)` — `flags` = `{tile_index: bitfield}` nebo seznam. `.get(tile, bit=None)` · `.set(tile, bit, value=True)` · `.at(tilemap, tx, ty, bit)` · `.at_px(tilemap, px, py, bit)` (kolize jedním řádkem). Klíčováno tile indexem (sdíleno všemi buňkami, které ho používají).

### `picogame_script` — příběhové skripty jako generátory (Director)
- `Director(pg, scene, buttons, font, box=None, nlines=3, fg=0xFFFF, bg=0x0000)` — pouští JEDEN příběhový skript nad živou scénou; `box` = obdélník dialogového panelu (výchozí: spodní pruh dle `screen()`).
- `.on(name, genfunc)` (registrace) · `.start(script)` (jméno nebo generátor) · `.active` · `.tick() -> bool` — volej jednou za snímek **po** `buttons.poll()`; vrací True dokud skript běží VČETNĚ posledního kroku (stisk A, který zavřel poslední dialog, tak nepropadne do vstupu hry v témže snímku).
- Čekací primitivy (uvnitř skriptu přes `yield from`): `.text(lines)` (stránka dialogu, A posouvá) · `.ask(lines) -> nastaví .answer` (volba A/B) · `.wait(frames)` · `.fade_out(speed)` / `.fade_in(speed)`.
- Příběhové vlajky: `.ev(name)` / `.ev_set(name)` v `.events` (set — persistuj přes své save schéma). `.retarget(scene)` přepojí Directora po změně mapy.

### `picogame_seq` — sekvence řízené generátory (coroutine vzor)
- `wait(frames)` · `over(frames, fn)` (fn(t), t 0..1) · `move_over(sprite, x, y, frames)` — vše jsou generátory; skládej je přes `yield from`.
- `Seq(gen=None)` · `.start(gen)` · `.tick() -> done` — posune o jeden krok za snímek (meziscény, „udělej X za N snímků“).
- `Script(play, loop=False)` — **skriptovaný vstup: hra, která hraje sama.** `play(s)` je generátor mačkající masky Buttons po snímcích (`yield from s.tap(B.A)` · `s.hold(B.RIGHT | B.UP, n)` · `s.rest(n)`; `tap(..., base=maska)` drží `base` po celou dobu). Je to *zdroj* pro Buttons: `btn.attach(script)` a pak `script.tick()` každý snímek **před** `btn.poll()` — demo běží vlastní vstupní cestou hry (`just_pressed`/`repeat` normálně fungují), na zařízení i v simu. Attract mód: attach na nečinné titulce, `loop=True` pro věčné přehrávání, a při lidském stisku vrátit ovládání — `if btn.state & ~script.mask: btn.detach(script); script.stop()`. Stejný skript poslouží i jako skriptovaný ověřovací běh.

### `picogame_anim` — animace snímků v čase
- `FrameAnim(sprite, frames, *, fps=8, loop=True)` · `.configure(frames, fps=8, loop=True)` · `.reset()` · `.tick(dt)`.
- `AnimatedSprite(sprite, anims)` · `.play(name)` · `.tick(dt)`.

### `picogame_fx` — herní odezva a rastrové efekty
- `Shake(scene, max_offset=6, decay=0.03, seed=0x9E37)` · `.add(amount)` (0.6 malý kopanec, 0.8 zásah, 1.0 velký; pod ~0.5 je posun při `max_offset=6` sub-pixelový, tedy neviditelný) · `.tick(cam_x=0, cam_y=0)` — trauma screen shake složený nad kamerou. `scene=None` = režim jen-offset pro strip renderery (road/raycaster/mode-7, kterými `set_view` nehne): tick() jen aktualizuje `.ox`/`.oy` a ty je utratíš v parametrech svého rendereru — `road.tick(dist, lateral + sh.ox)`, roztřesený horizont.
- `Fade(scene, width, height, x=0, y=0, color=0, cell=8)` · `.to(target, speed=2.0)` · `.out()/.into()/.set(level)/.dim(level=8)/.clear()/.pulse(level=12, speed=2.0)` · `.is_done` · `.tick() -> done` — rastrový přechod, ztmavení nebo záblesk přes celou obrazovku či vybranou oblast. `StripDraw` nedrží vlastní pixelovou plochu.
- `Tween(value=0.0, speed=0.2)` · `.to(target, speed=None)` · `.set(value)` · `.tick() -> value` · `.is_done` — vyhladí skalár (UI/pop-upy).
- `Camera(scene, w, h, lerp=0.18, world_w=0, world_h=0, top=0, bottom=0, left=0, right=0)` · `.follow(tx, ty, snap=False)` · `.offset() -> (ox,oy)` · `.apply()` — vyhlazené sledování s omezením na svět; se `Shake` ho spoj přes `shake.tick(*cam.offset())`. `w`/`h` = obrazovka; vyhrazený pruh pro HUD patří do `top`/`bottom`/`left`/`right` (stejný pruh jako v `setup()`), kamera pak centruje a omezuje pohled ve viditelné části.
- `Sky(scene, x, y, w, h, top, bottom)` — svislý gradient s tabulkou `2*h` bajtů. · `Scanlines(scene, x, y, w, h, step=2, dark=0)` — CRT překryv s jedním řádkem PAL8 o velikosti `w` bajtů.
- `InvertFlash(display, frames=3, normal=None)` · `.pulse(frames=None)` · `.tick()` — záblesk pomocí hardwarové inverze podporovaného SPI panelu; nevykresluje scénu a není určený pro framebuffer.

### `picogame_palette` — změny palety PAL8 (potom zavolej `sprite.touch()`)
- `cycle(palette, lo, hi, step=1)` — rotuje položky (animovaná voda/láva/portály; ~0 grafiky navíc).
- `swap(dst_palette, src_palette)` — přebarví sdílenou bitmapu (GBC styl; levnější než 2. bitmapa).
- `fade(palette, base, t, target=0, skip=None)` — lerp k barvě (hladké stmívání jasu; `base` = `snapshot()` originálu).
- `snapshot(palette)` / `restore(palette, base)`.

### `picogame_rand` — seedovatelný RNG
- `Rand(seed=None)` (deterministický kombinovaný 30bitový Lehmer PRNG; `None` = seed z času) · `.below(n)` · `.randint(a, b)` · `.random()` · `.chance(p)` · `.choice(seq)` · `.shuffle(lst)` · `.weighted(weights) -> index` · `.seed(s)`.
- `Bag(items, rng)` · `.next()` — shuffle-bag (7-bag) anti-streak randomizér.

### `picogame_save` — NVM perzistence
- `Save(key, schema, *, offset=0)` — `schema` = uspořádaný dict `jméno -> (formátový znak struct, výchozí)`; ukázka → [/helpers/data/](/helpers/data/). · `.defaults()` · `.load() -> dict` · `.save(values)` · `.reset()`. Přežije restart/smazání souborového systému.

### `picogame_audioout` — jeden výstup pro libovolnou desku
- `make_output(sample_rate=22050, pin=None)` — vrátí audio výstup desky, vybraný automaticky: I2S DAC (Fruit Jam TLV320), když má deska `I2S_BCLK`, jinak PWM výstup na `pin` (nebo výchozím pinu desky). Používá ho `picogame_audio` i `picogame_synth`, takže hra nepotřebuje žádný kód specifický pro desku. Vyhodí `RuntimeError`, pokud výstup neexistuje.
- Výběr výstupu TLV320 a tři hlasitostní trimy se nastavují ze `settings.toml` (`PICOGAME_AUDIO_OUT`, `PICOGAME_DAC_VOLUME`, `PICOGAME_HP_VOLUME`, `PICOGAME_SPK_VOLUME` — viz [Vlastní deska](custom-board.md)); výchozí hodnoty driveru jsou schválně tiché, tak je zvedni k 0 dB. `PICOGAME_DEBUG = 1` vypíše, proč DAC selhal.

### `picogame_audio` — přehrávání samplů (PWM nebo I2S DAC)
- `Audio(pin=None, voices=4, sample_rate=22050, channels=1, bits=16, signed=True)` · `.load(path)` · `.play(sample, *, voice=None, loop=False, volume=1.0)` · `.sfx(sample, volume=1.0)` · `.music(sample, loop=True, volume=1.0)` · `.stop(voice=None)` · `.stop_music()` · `.deinit()` · `.is_playing`.
- `tone(frequency=440, ms=120, sample_rate=22050, volume=0.6)` — sample pípnutí obdélníkovou vlnou.

### `picogame_synth` — synthio hudba a SFX
- Vlny: `sine()` · `saw()` · `triangle()` · `square()` · `noise()`.
- `note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08, amplitude=0.6, bend=None, cutoff=None)` — sestaví znovupoužitelnou notu nástroje (`midi` 60 = střední C; `cutoff` = dolní propust v Hz).
- `pitch_bend(semitones, ms, waveform=None, once=True)` — LFO pro `bend` noty (sklouznutí / laserový zvuk).
- `Synth(pin=None, sample_rate=22050, buffer_size=2048, music_level=0.4, sfx_level=0.7)` · `.sfx(n)` · `.press(n)` · `.release(n)` · `.music(midi_track)` · `.stop_music()` · `.set_levels(music=None, sfx=None)` · `.mute(on)` · `.available` — init se hlídá sám: na firmwaru bez audia **nebo** při selhání initu (těsný heap, obsazený pin) instance běží jako tiché no-opy místo výjimky; hra žádný try/except nepotřebuje.
- `Drone(synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12)` · `.start()` · `.set(frequency, amplitude=None)` · `.stop()` — souvisle držená nota pro motor nebo sirénu. Jednou zavolej `.start()`, potom v každém snímku měň výšku a amplitudu přes `.set()`.
- `load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240)` — načte MIDI soubor do přehratelné stopy.

### `picogame_sfx` — signature SFX sada (nad `picogame_synth`)
- `Kit(synth)` — jednou sestaví sadu efektů pro připojený `Synth`; bez dostupného audia zůstane tichá. Metody podle události: `.blip()` · `.coin()` · `.powerup()` · `.zap()` · `.pew()` · `.jump()` · `.hit(rotate=True)` · `.hurt()` · `.boom()` · `.explosion()`. `.tick()` volej jednou za snímek kvůli arpeggiím a prioritě jediného hlasu SFX. Hlasitost nastav přes `Synth.set_levels()` nebo `Synth.mute()`.

### `picogame_cutscene` — přehrávač celoobrazovkových obrázků / story scén
- `palette(pg, rgb)` — jednou vytvoř paletu ve wire order z modulu palety od `bake_cutscene.py`, trojic RGB nebo hotových číselných hodnot.
- `show(pg, display, buffer, path, pal=None, w=320, h=240, scale=None, band=24, bg=0)` — načítá obrázek po stripech. Dočasný zdrojový strip zabere `w*band` bajtů v PAL8 nebo `w*band*2` bajtů v RGB565 nad rámec vykreslovacího bufferu. `scale=None` odvodí celočíselné zvětšení z displeje.
- `play(pg, display, buffer, btn, path, pal=None, ..., caption=None, caption_lines=None, auto_hold=0, clock=None)` — zobrazí, překryje volitelný titulkový pruh a čeká na A/B (nebo auto-pokračuje po `auto_hold` ticích).

### `picogame_stream` — postupné načítání snímků spritu z flash
- `StreamSheet(pg, path, w, h, frames, palette, transparent=None)` · `.use(i)` (vybere snímek načtený na vyžádání) · `.close()` — velké atlasy zůstávají ve flash místo v RAM.

### `picogame_arena` — předalokovaná paměť proti fragmentaci
- `Arena(pixels)` · `.alloc(nbytes, align=1) -> memoryview` · `.canvas(w, h, transparent=None) -> Canvas` · `.reset()` · `.free() -> int`. Předem vyhraď jeden velký buffer a rozděluj ho na části. `.mark() -> m` / `.release(m)` podporují vnořené životnosti LIFO.

### `picogame_debug` — RAM watermarky + FPS overlay (testovací pomůcka)
- `enabled` — modulový flag (default False: volání jsou no-op; zapni True při testování).
- `ram(tag)` — gc.collect() + tisk `[RAM] <tag>: free N alloc M` na přechodu (boot/bitva/menu) — on-device diagnostika leaků/fitu.
- `Watch(scene, clock=None, every=30, x=2, y=2)` · `.step()` každý frame · `.hide()/.show()` · `.remove()` — rohový overlay `FPS 30 FREE 31k` (jedna živá text bitmapa, re-render jen při změně). Předej svůj `Clock` jako `clock=` pro skutečné FPS; `every`/`x`/`y` jsou keyword argumenty.

### `picogame_scene` — deklarativní loader levelů
- `load(pg, scene, display=None, strip_h=None, font=None, bank=None) -> View` — vytvoří scénu z připraveného slovníku `SCENE`; na SPI backendu má `View` dva strip buffery, na framebufferu jsou `view.bufA` a `view.bufB` rovny `None`.
- `load_bank(pg, bank)` — postaví sdílenou asset banku jednou (znovupoužitelnou napříč levely).
- `View`: `.tile_xy(px, py)` · `.group(tag)` · `.point(name)` · `.in_zone(x, y, tag=None)` · `.is_solid(tx, ty)` · `.tile_has(tx, ty, prop)` · `.play(sound_id)` · `.tick(dt)`. · `.set_tile_prop(tile, prop, on=True)` — přepni příznak TYPU dlaždice za běhu: každá buňka s tou dlaždicí změní význam najednou (páka zprůchodní všechny brány, led roztaje). Doplňuje nativní `Tilemap.set_tile`, který mění JEDNU buňku; tabulky se kopírují per `load()`, takže změny neprosáknou do jiných úrovní sdílejících bank.
- `load_json(pg, path, display=None, strip_h=None, font=None, bank=None, release=True) -> View` — zapeče scene JSON levelu přímo na desce a načte ho, bez kroku přes `scene_build.py`. Na ITERACI levelu; hotovou hru posílej se zapečeným modulem. Jen barevné tilesety.

### `picogame_scenebake` — baker scén na desce
- `bake(scene) -> SCENE` — z (už naparsovaného) scene JSONu editoru udělá runtime SCENE dict, byte-identicky s `tools/scene_build.py`. Assety z PNG vyhodí `NotImplementedError` (median-cut kvantizace zůstává na desktopu).
- Radši `picogame_scene.load_json()`: drží text JSONu i parse strom jako lokály, což je přesně to, co dělá tu ~17 kB špičku přechodnou. Bakuj BRZO, dokud je heap souvislý.
- Zabírá ~3,6 kB, dokud je importovaný; `load_json(..., release=True)` ho po posledním levelu zahodí.

### `picogame_mode7` — Mode-7 perspektivní podlaha
- `Camera(fov=0.66)` · `.draw(canvas, texture, x, y, angle, horizon, height, y_off=0)` — řídí C podlahu `Canvas.mode7` z přívětivé pozice kamery (pozice ve světových/dlaždicových jednotkách, směr v radiánech, `height` = výška kamery). Rozměry `texture` musí být mocniny dvou, jedna světová jednotka = jedna dlaždice. Kresli do 0-RAM `StripDraw` view. Viz [/cs/helpers/pseudo-3d/](/cs/helpers/pseudo-3d/).

### `picogame_road` — OutRun scanline silnice
- `Road(pg, width, height, horizon, colors, *, half_width=0.47, hw_min=6.0, depth=600.0, curves=((16384, 90.0), (4096, 30.0)), world_step=6, curve_step=2, hill_amp=0, edge_frac=0.12, dash_frac=0.07, dash_min_hw=7.0, band=20.0, dash_band=14.0)` · `.tick(dist, lateral_px=0)` (1×/snímek; kladné lateral = auto jelo doprava, silnice se posune doleva) · `.draw(view, vy)` (tělo StripDraw callbacku) · `.set_grade(g)` (kopce: −1..+1 posouvá horizont; chce `hill_amp`) · `.horizon_now` (this frame's effective horizon = horizon + hill pitch — the y overlays and roadside sprites anchor to) · `.curve_at(dist)` (znaménková křivost −1..+1 pro odstředivou sílu / AI — stejný dvousinový model, který běží v C, bez alokace) · `.row_of(z)` / `.half_of(row)` / `.edges_of(row)` (umístění a škálování spritů NA silnici — řádky jsou lineární, škáluj přes `half_of`, ne `F/(F+z)`) — řídí nativní pár `pg.road_edges` + `Canvas.road` z lidských jednotek: `periody` zatáček ve světových jednotkách (zaokrouhlené nahoru na mocniny dvou, aby int32 fázový wrap zůstal spojitý — viz [smlouvu volání](/helpers/pseudo-3d/)), `swing` v px bočního ohnutí, barvy jako dict šesti hodnot `pg.rgb565`. Všechny fixed-point tabulky staví jednou; `tick()` nealokuje. Viz [/helpers/pseudo-3d/](/helpers/pseudo-3d/).

### `picogame_iso` — izometrická projekce
- `IsoView(ox, oy, tw, th)` (`tw`/`th` = poloviční šířka/výška dlaždice; 2:1 diamant → `th = tw//2`) · `.to_screen(gx, gy, h=0)` · `.depth(gx, gy, h=0)` (painter's klíč zezadu dopředu) · `.screen_to_grid(sx, sy)` · `.cube_faces(gx, gy, height_px)` (horní/pravá/levá stěna vyvýšeného bloku) · `.emit_blocks(cells, tv, tc)` (alloc-free dávka: zapíše flat-shaded trojúhelníky kostek mnoha bloků přímo do int16/uint16 bufferů pro JEDNO volání `Canvas.fill_triangles`; vrací počet trojúhelníků) — **nejlevnější pseudo-3D vůbec**: jen celočíselné sčítání a shifty, žádné dělení, žádná závislost na C, proto běží dobře i na RP2040. Odemyká iso RPG / strategie / taktiky / buildery. Statické desky: vykresli jednou + dirty-rect jen pohyblivé (30 fps); `emit_blocks` je pro scény přestavované každý snímek (~2× rychlejší než Python smyčka přes `cube_faces`). Viz [/cs/helpers/pseudo-3d/](/cs/helpers/pseudo-3d/).

### `picogame_ray` — first-person raycaster
- `Raycaster(world, wall_colors, sky, floor, fov=0.66, stride=2)` · `.cast(px, py, ang, sw, sh)` (jednou/snímek) · `.draw(view, vx, vy, vw, vh)` (StripDraw callback; **řádek 0 je horní okraj VÝHLEDU, ne obrazovky** — vrstva začínající pod y=0, např. pod rezervovaným HUD pruhem, musí předat `vy - pruh`) · `.solid(x, y)` (test stěny) · `.set_cell(x, y, v)` (změň JEDNU buňku světa za běhu — otevření dveří, pád zdi; v = typ zdi 0–9, 0 = prázdno; drží mřížku casteru, `solid()` i `.map` v souladu a přecastuje i stojící kameru. Pro události, ne animaci — každé volání vynutí jeden plný re-cast) · `.attach(sd)` (temporální repaint) · `.project_sprite(sx, sy)` (billboard) — plně nativní render: caster `pg.raycast` (integer 16.16 C na zařízení, Python v simu) rovnou emituje RLE-sloučené runy stěn, malované jednou dávkou `Canvas.vspans` na strip do 0-RAM `StripDraw` view (~36 fps uncapped při stride 1 přes celou obrazovku na RP2040, ploché napříč úhly pohledu). `stride` = knoflík výkon/kvalita; `attach(sd)` + `always_dirty=False` překreslí jen změněný pás sloupců (stání/pomalu ~30 fps). Viz [/cs/helpers/pseudo-3d/](/cs/helpers/pseudo-3d/).
