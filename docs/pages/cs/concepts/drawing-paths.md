---
title: Kreslicí cesty — kterou zvolit
description: Volba retained nebo immediate kreslení pro herní svět, HUD, panely a jednorázové obrazovky.
sidebar:
  order: 4
---

Kreslicí cestu vybírej podle toho, kdy se obsah mění a zda potřebuje uložené pixely:

- Retained `Scene` použij pro svět, který přetrvává mezi snímky.
- `pg.render()` použij pro jednorázovou obrazovku nebo rezervovaný pruh HUDu.
- `StripDraw` použij tam, kde můžeš pixely znovu vytvořit místo jejich uložení do Canvasu.

## Jeden kompozitor, dva výstupy

Všechny cesty používají stejný kompozitor vrstev. Na SPI cílech prochází každý dirty region po
vodorovných **pásech** a posílá je na panel. Na cílech s vlastním obrazovým výstupem, například
Fruit Jam, skládá dirty regiony přímo do framebufferu. Tam formát pixelu určuje barevná hloubka
bufferu: 16bitový framebuffer bere RGB565 přímo, u 8bitového (jediná hloubka, kterou picodvi nabízí
při 640×480) se každý dokončený pás kvantuje 565→332 při publikování — v obou případech kreslíš přes
`pg.rgb565(...)`.

Volba vrstvy určuje, kolik další pixelové paměti hra uchovává. Celoobrazovkový `StripDraw` nemá
vlastní pixelový buffer; RGB565 `Canvas` o velikosti 320×240 drží přibližně 150 KB. Případný
Výstupní framebuffer patří zobrazovací cestě a do této ceny se nepočítá.

![Jeden kompozitor vrstev napájí dva výstupy: SPI panel (dirty region prochází po vodorovných pásech) nebo scanout framebuffer (skládá se přímo jako 16bit RGB565 nebo 8bit RGB332)](/img/drawingpaths_compositor.png)

## Co spouští kreslení (dva režimy)

| Režim | Pro co | Překresluje |
|---|---|---|
| **`scene.refresh()`** — retained režim | trvalý herní svět: vrstvy přidáš, měníš a obnovuješ. Kamera (`set_view`), `fixed` vrstvy a rezervované pruhy (`top=/bottom=/left=/right=`). | dirty regions |
| **`pg.render(display, items, buffer, x0,y0,x1,y1, *, background)`** — immediate režim | jednorázové kreslení mimo scénu: HUD v rezervovaném pruhu, titulní obrazovka nebo konec úrovně. | při zavolání |

Oba režimy berou **stejné typy vrstev**: seznam pro `pg.render` může držet Sprity, `StripDraw`,
`Canvas`, `Tilemap` i `Particles`, přesně jako scéna.

## Pět typů vrstev (co kreslíš) — a jejich RAM

| Typ | RAM | Pro co |
|---|---|---|
| **Sprite** (obaluje `Bitmap`) | bitmapa: PAL8 = `w*h` (1 B/px), RGB565 = `w*h*2` | pohyblivé objekty, postavy, střely |
| **Tilemap** | `cols*rows` (1 B/buňka) + sada dlaždic | velké statické nebo posouvající se mapy |
| **Canvas** | `w*h*2` uchovaných bajtů | plocha kreslená **občas a používaná opakovaně** — statický panel, dialog |
| **StripDraw** | **0 uchovaných pixelových bajtů** (pohled na aktuální cíl vykreslování) | **dynamický celosnímkový obsah** — obloha, silnice, gradienty, HUD a text. Ve výchozím stavu překresluje každý snímek; s `always_dirty=False` a `.invalidate()` kreslí na vyžádání |
| **Particles** | pevný pool | jiskry, stopy, krátké výtrysky |

![Pět typů vrstev podle uchovávané RAM: StripDraw drží nula bajtů, Tilemap a Particles jsou levné, Sprite závisí na bitmapě a uchovávaný Canvas stojí nejvíc](/img/drawingpaths_layers.png)

### Text používá tyto vrstvy

- **`Canvas.text(x, y, s, fg, font, bg=None)`** složí glyfy v C přímo do plochy: žádná mezipaměť
  glyfů ani nová `Bitmap` či `Sprite` při každém volání. Plocha může být uchovávaný `Canvas` nebo
  pohled `StripDraw`, který míří na právě vykreslovaný pás. Jedna metoda pokrývá obojí.
- **`picogame_font.render_text(...)`** vyrastruje řetězec do PAL8 `Bitmap`, který ukážeš jako Sprite,
  vhodné pro **pohyblivý** text (plovoucí čísla poškození), kde sprite stejně chceš.

Dynamický text přes pohled `StripDraw` neuchovává bitmapu glyfů ani panelu. Kreslicí funkce ale spotřebuje
CPU pokaždé, když se oblast překreslí.

### Pseudo-3D používá tyto vrstvy taky

- **`Canvas.mode7(...)`** vyplní řádky pod horizontem **Mode-7 perspektivní podlahou** textury o
  rozměrech mocniny dvou — kresli ji do **`StripDraw` view** pro celoobrazovkovou podlahu za **0
  uchovaných bajtů** (helper `picogame_mode7.Camera` dopočítá její fixed-point argumenty z pozice kamery).
- **`picogame_ray.Raycaster`** staví first-person stěny stejně — DDA cast na sloupec, každá stěna
  `fill_rect` sloupec do `StripDraw` view.

Obojí je pseudo-3D případ „dynamického celoobrazovkového obsahu", takže žije na StripDraw (nikdy ne
150KB celoobrazovkový Canvas). Viz [Pseudo-3D](/cs/helpers/pseudo-3d/).

## Rozhodovací matice (HUD, panely, obrazovky)

| Co | Správná cesta | RAM |
|---|---|---|
| **Dynamický, tenký HUD** (skóre / životy) | `StripDraw` (+ `view.text`), přes `scene` nebo `pg.render` | **0 uchovaných pixelů** |
| **Statický, velký panel** (boční panel, titulní grafika, nápověda) | **`Canvas` nakreslený jednou** (`canvas.text`), držený jako vrstva | `w*h*2` (nakreslí se jednou a používá opakovaně) |
| **Statický panel + pár živých čísel** | statický `Canvas` na fixní část **+** malý `StripDraw` na čísla | malá |
| **Panel/dialog/menu uvnitř živé scény** (překresluje jen při změně) | **`StripDraw` na vyžádání** (`always_dirty=False`, `.invalidate()` při změně), přidaný do scény | **0 uchovaných pixelů** |
| **Jednorázová obrazovka** (titulní obrazovka / konec úrovně / konec hry) | `pg.render([stripdraw])` — procedurální pozadí + `view.text`, bez scény | **0 uchovaných pixelů** |
| **Pohyblivý text** (plovoucí čísla poškození) | `picogame_font.render_text` → Sprite | bitmapa o velikosti textu |

Past, které se vyhnout: **pás `Canvas` pro _dynamický_ HUD.** `Canvas` uchovává `w*h*2` bajtů; pás
320×16 zabere trvale 10 KB a plnovýškový boční panel mnohem víc. Dynamický HUD patří na
**`StripDraw`** bez uchovaných pixelů a při změně se znovu levně vykreslí v C. Po `Canvas` sáhni,
jen když je obsah **statický** (nakreslen jednou a znovupoužit).

Další past: **okamžitý `pg.render` přes živou retained scénu.** Scéna neví, že `render()` změnil
pixely, takže její další `refresh()` překreslí jen vlastní dirty regiony a na obrazovce nechá zbytky
překryvu. Pokud vykreslená oblast zasahuje do hracího obdélníku scény (pauza, menu, meziscéna,
banner), zavolej poté **`scene.invalidate()`** — nebo použij **`picogame_game.overlay(...)`**, což je
`pg.render` + `scene.invalidate()` v jednom volání. HUD pásy mimo hrací obdélník (`top=`/`bottom=`
rezervy) to nepotřebují: scéna se jich nikdy nedotkne.

## HUD bez uloženého bufferu panelu

`picogame_ui.HudBar` tento postup už používá: jde o `StripDraw` bez vlastního bufferu, který se při
změně vykreslí přes `pg.render`. Stejný vzor můžeš použít ručně pro HUD ve vyhrazeném pásu:

```python
scene, bufA, bufB = picogame_game.setup(background=BG, strip_h=BAR, top=BAR)
hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, BG)   # bez uchovaných pixelů
score = hud.label(FONT, 4, 3, INK, "SCORE 0")               # vrací objekt popisku
# ... při změně:
score.set("SCORE %d" % pts)
hud.draw()                                                  # znovu složí v C, bez mezipaměti
```

**Formátuj při změně, ne každý snímek.** `.set()` přeskočí překreslení nezměněného řetězce, ale
samotné formátování přes `"%"` při každém volání vytvoří nový řetězec. Formátuj v místě, kde se
hodnota *mění* (jako výše), nebo při pravidelné kontrole ve smyčce porovnej poslední zobrazenou
hodnotu: `if pts != shown_pts: shown_pts = pts; score.set("SCORE %d" % pts)`.
U plynule běžících hodnot nejdřív kvantuj na zobrazovanou jednotku (sekundy, procenta).

Nebo úplně ručně, například na titulní obrazovce bez scény a vlastních bufferů:

```python
def draw_title(view, vx, vy, vw, vh):
    view.clear(SKY)
    view.text(60 - vx, 90 - vy, "PRESS A", INK, FONT)        # místní bod = obrazovka - (vx, vy)
title = pg.StripDraw(draw_title, 0, 0, W, H)
pg.render(picogame_game.display(), [title], bufA, 0, 0, W, H, background=SKY)   # bez uchovaných pixelů
```

Místní bod `(0,0)` pohledu `view` odpovídá bodu obrazovky `(vx, vy)`. Při kreslení na souřadnice
obrazovky proto odečti `(vx, vy)`.

## Překreslení na vyžádání: panel bez bufferu uvnitř scény

`StripDraw` ve výchozím stavu překresluje **každý snímek** (`always_dirty=True`), což se hodí pro oblohu nebo silnici, které se
mění pořád. Ale vytvoř ho s **`always_dirty=False`** a překreslí se jen když zavoláš **`.invalidate()`**
(nebo ho překryje jiná změněná vrstva). Tím vznikne panel bez vlastního bufferu uvnitř scény (dialog, stavový panel
nebo menu), který se znovu nerasterizuje ani neodesílá, dokud se jeho obsah skutečně nezmění.
Pak se jednou překreslí. Jde o alternativu k retained `Canvas` bez vlastního bufferu pro obsah, který je většinou
statický, ale občas se musí aktualizovat.

```python
panel = pg.StripDraw(draw_panel, x, y, w, h, always_dirty=False)  # zahálí, dokud není invalidován
scene.add(panel, fixed=True)
# ... když se text změní:
panel.invalidate()                                                # překreslí se jednou při dalším refresh
```

Tak fungují `picogame_ui.SceneBox` a `SceneMenu`: dialog nebo menu uvnitř scény se překreslí při
`show`/`hide`/`set_line`, ne v každém snímku.

## Grafika v polovičním rozlišení + zvětšení mocninou dvou (technika na RAM)

Velkou grafiku ulož v 1/2 nebo 1/4 velikosti a zobraz ji Spritem se `scale = 2` (nebo `4`, `8`).
Bitmapa se zmenšuje **kvadraticky**, plocha na obrazovce zůstává:

| pozadí 320×240 PAL8 | RAM |
|---|---|
| uloženo 1:1 | 75,0 KB |
| uloženo v polovině, `scale = 2` | 18,8 KB |
| uloženo ve čtvrtině, `scale = 4` | **4,7 KB** |

Na RP2040 (≈ 25–40 KB volné haldy) je celoobrazovkové bitmapové pozadí v 1:1 nemožné a při 4×
pohodlné — právě tahle technika ho umožní.

Za běhu je to levné **jen při měřítkách mocnin dvou**: engine má vyhrazenou rychlou cestu pro
neprůhledné PAL8 (a RGB565) sprity se `scale` přesně 2, 4 nebo 8, změřeno ~1,5× proti obecnému
škálovanému blitu (každá zdrojová řádka se rasterizuje jednou a opakování se kopírují). Jakékoli
jiné měřítko — 3, 1,5, tweenované 0,8→1,5 — jde obecným scalerem, který je v pořádku pro malé
sprity, ale drahý pro vrstvy přes celou šířku. Průhledné sprity jdou také obecnou cestou, takže
velké škálované vrstvy drž neprůhledné.

Vzhled jsou hrubší pixely — na tomhle hardwaru je to estetika, ne kompromis (viz
[Aby to bavilo](/cs/concepts/making-it-fun/)). Takhle běží parallax v Pictoru: 640 px široké pásy
uložené v poloviční velikosti, zobrazené se `scale = 2`, úspora ~23 KB proti 1:1.

## Pravidla palce

- **Pohyblivý objekt → Sprite. Velká mapa → Tilemap. Dynamický celosnímkový obsah nebo HUD → StripDraw.
  Statický panel používaný opakovaně → Canvas.**
- Dynamický HUD nikdy nepotřebuje `Canvas`. Když jsi napsal `pg.Canvas(W, BAR, ...)` na HUD, přepni na
  `StripDraw`.
- `Canvas` se vyplatí, když je obsah statický a používá se opakovaně; buffer ušetří rasterizaci
  v každém snímku.
- Oba `scene.refresh()` i `pg.render()` berou všechny typy vrstev, takže režim vybírej podle toho, *kdy* se
  má překreslit (každý dirty refresh vs. na vyžádání), ne podle toho, co kreslíš.

## Viz také

- Bojuješ s `MemoryError`? Rozpočet, měření i arénu popisuje [Správa RAM](/cs/memory/).
- Přesné signatury `Canvas`, `StripDraw`, `pg.render` a `Sprite`: [Reference](/cs/reference/).
- Hotové widgety HUDu, dialogu a menu postavené na těchto cestách: [Text a UI](/cs/helpers/text-ui/).
- Podložení `Canvasu` znovu používanou pamětí místo nového bufferu: [Ukládání a paměť](/cs/helpers/data/) (`picogame_arena`).
