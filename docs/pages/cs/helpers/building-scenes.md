---
title: "Sestavování scén"
description: "Načítání scén, vlastnosti dlaždic, jednoduchá grafika vytvářená v kódu a opakované použití spritů."
---

Tyto čtyři moduly načítají připravené scény, přiřazují vlastnosti dlaždicím, vytvářejí jednoduché bitmapy v kódu a opakovaně používají pevný počet spritů. Signatury najdeš v [/cs/reference/](/cs/reference/).

## picogame_scene

Loader převede připravený slovník `SCENE` na `pg.Scene` a sadu pojmenovaných objektů. Použij ho pro úroveň vytvořenou editorem nebo nástrojem `scene_build.py`. Stejná data i loader fungují na hardwaru a v simulátoru. Vstupní formát popisuje [/cs/scene-format/](/cs/scene-format/).

`load(pg, scene, display=None, strip_h=None, font=None, bank=None)` vrátí objekt `View`. Displej vybere stejně jako `picogame_game.setup()`, vytvoří scénu a přidá všechny tilemapy, sprity, skupiny, částice a popisky HUD. Pro SPI displej alokuje dva vykreslovací buffery o velikosti `width * strip_h * 2`, dostupné jako `view.bufA` a `view.bufB`. Na framebufferu mají oba hodnotu `None`. Pokud data obsahují popisek HUD, předej font, například `terminalio.FONT`. Zobrazovací backendy popisuje [/cs/hardware/](/cs/hardware/) a náklady bufferů [/cs/memory/](/cs/memory/).

`load_bank(pg, bank)` vytvoří sdílené bitmapy, zvuky a animace. Výsledek předej jako `load(..., bank=...)` při načtení každé úrovně, aby se společné prostředky nevytvářely znovu.

**Vlastnosti dlaždic přicházejí se scénou.** Po načtení scény nesahej po `picogame_tiles` — `View` na dotazy k jednotlivým dlaždicím odpovídá sám: `view.is_solid(tx, ty)` a `view.tile_has(tx, ty, "název")` pro libovolný další příznak. Název je ten, který jsi namaloval v editoru, takže nejsi omezený na čtyři výchozí: přidej v editoru příznak `glass` a hra ho přečte jako `view.tile_has(tx, ty, "glass")`. Sáhnout tu po bitovém poli znamená znovu odvozovat data, která loader už má.

**`view.camera` jsou data, ne chování.** Loader ti podá `(mode, target, axis, x, y, w, h)` a hra to aplikuje — nic hráče samo nesleduje. `axis` je `"x"`, `"y"` nebo `"xy"`; respektuj ho při volání `scene.set_view()`, jinak level navržený na svislé rolování tiše rolovat nebude.

Vrácený `View` zpřístupňuje obsah scény:

- `view.scene` - vytvořený `pg.Scene`. V každém snímku zavolej `view.scene.refresh()`; pohled posuneš přes `view.scene.set_view(ox, oy)`.
- `view.named[name]` - slovník názvů na sprity, částice a popisky HUD.
- `view.group(tag)` - seznam spritů ze skupinové vrstvy. Pro neznámý tag vrátí `[]`.
- `view.tick(dt)` - posune všechny automatické animace o `dt` sekund. Volej jednou za snímek.
- `view.tile_xy(px, py)` - světové pixely -> buňka `(tx, ty)` primárního (prvního) tilemapu.
- `view.is_solid(tx, ty)` - zkratka pro `tile_has(tx, ty, "solid")`.
- `view.tile_has(tx, ty, prop)` - True, pokud má dlaždice primárního tilemapu v dané buňce pojmenovanou vlastnost (z připraveného `tileprops`).
- `view.set_tile_prop(tile, prop, on=True)` - přepne příznak TYPU dlaždice za běhu: všechny buňky s touto dlaždicí změní význam naráz (páka zprůchodní všechny mřížové dlaždice, led roztaje). Jednu buňku naopak změníš výměnou dlaždice přes nativní `tilemap.set_tile`. Změny platí do dalšího `load()` - načtení úrovně významy dlaždic resetuje, i při sdíleném banku.
- `view.point(name)` - `(x, y)` pojmenovaného bodu, nebo None.
- `view.in_zone(x, y, tag=None)` - první zóna `(tag, x, y, w, h)` obsahující daný bod (volitelně filtrovaná podle tagu), jinak None.
- `view.play(sound_id)` - přehraje připravený zvuk podle ID. Pokud zvuk nebo zvukový výstup chybí, nic neudělá.
- `view.tilemap` / `view.camera` / `view.zones` / `view.points` / `view.anims` - primární tilemapa, nastavení kamery a zdrojové kolekce.

```python
import board, terminalio
import picogame as pg
import picogame_scene as pgs
import world1_scene

view = pgs.load(pg, world1_scene.SCENE, font=terminalio.FONT)
player = view.named["player"]
enemies = view.group("enemies")
while True:
    view.tick(1 / 30)                      # advance auto-animations
    tx, ty = view.tile_xy(player.x, player.y)
    if not view.is_solid(tx, ty):
        player.move(player.x + 2, player.y)
    view.scene.refresh()
```

:::note[Pozor]
první tilemapa ve scéně je primární; `tile_xy`, `is_solid` a `tile_has` se dotazují pouze na ni. `view.named` obsahuje jen pojmenované vrstvy. Načítání zvuků je volitelné: při chybějícím modulu nebo souboru bude příslušná položka `None` a `play()` nic neudělá.
:::

## picogame_tiles

`TileFlags` ukládá jedno bitové pole vlastností pro každý index dlaždice. Všechny buňky se stejnou dlaždicí proto sdílejí stejné vlastnosti. Použij ho s ručně vytvořenou `pg.Tilemap`. Scéna načtená přes `picogame_scene` už nabízí metody `view.is_solid()` a `view.tile_has()`.

Osm pojmenovaných bitů a jejich masek: `B_SOLID, B_HAZARD, B_LADDER, B_PLATFORM, B_WATER, B_COIN, B_EXIT, B_CUSTOM` jsou bitové indexy 0..7; `SOLID, HAZARD, LADDER, PLATFORM, WATER, COIN, EXIT, CUSTOM` jsou odpovídající masky `1 << bit`. Při sestavování tabulky používej masky, při dotazování `B_*` indexy.

`TileFlags(flags=None, tile_px=8)` vytvoří tabulku. `flags` je slovník `{tile_index: bitfield}` nebo sekvence typu `list` či `bytes` indexovaná číslem dlaždice. `tile_px` určuje velikost dlaždice pro dotazy v pixelech.

- `tf.get(tile, bit=None)` - celý bitfield dlaždice, nebo jeden bool flag, pokud zadáš `bit` (index `B_*`).
- `tf.set(tile, bit, value=True)` - nastav (nebo smaž) bit na dlaždici za běhu.
- `tf.at(tilemap, tx, ty, bit)` - flag `bit` dlaždice v buňce `(tx, ty)`.
- `tf.at_px(tilemap, px, py, bit)` - flag `bit` dlaždice pod MAP-LOCAL pixelem `(px, py)`; běžná kolizní sonda.

```python
import picogame as pg
import picogame_tiles as tiles

TILE = 8
tf = tiles.TileFlags({1: tiles.SOLID, 2: tiles.COIN, 3: tiles.EXIT}, tile_px=TILE)

def blocked(level, tx, ty):                # level je pg.Tilemap
    return tf.at(level, tx, ty, tiles.B_SOLID)

if tf.at_px(level, px, py, tiles.B_SOLID): # je dlaždice pod pixelem (px, py) pevná?
    stop()
```

:::note[Pozor]
`at_px` předpokládá, že mapa je na souřadnicích `(0, 0)` - pokud je posunutá, odečti před voláním počátek mapy od `px`/`py` sám. Dlaždice chybějící v tabulce se čtou jako `0` (žádné flagy). Sestavuj pomocí MASK konstant (`tiles.SOLID`), ale dotazuj se pomocí BIT indexů (`tiles.B_SOLID`); záměna tiše kontroluje nesprávný bit.
:::

## picogame_shapes

Tyto funkce vytvářejí jednobarevné bitmapy PAL8 přímo v kódu. Hodí se pro prototypy a geometrickou grafiku, například míče, cihly nebo lodě. Na rozdíl od `Canvas` vracejí znovu použitelný `Bitmap` pro `Sprite` nebo `Tilemap`. Index palety 0 je průhledný a index 1 obsahuje požadovanou barvu.

- `rect(w, h, color)` - vyplněný obdélník `w x h`.
- `circle(d, color)` - vyplněný disk průměru `d`.
- `ring(d, color, thickness=2)` - obrys kružnice průměru `d`.
- `from_mask(mask, color)` - bitmapa z listu stringů; `#`, `X` nebo `1` nastaví pixel. Velikost odpovídá masce.
- `atlas(frames_data, w, h, color)` - zabalí list `w*h` bufferů 0/1 do jedné horizontální víceframové bitmapy (jedna barva). Obecný builder "frame sheetu".
- `color_frames(w, h, colors)` - víceframová bitmapa, kde frame `i` je plná výplň `colors[i]`; frame 0 je už barevný. Index 0 je průhledný.
- `tileset_colors(w, h, colors)` - tileset, kde frame 0 je PRÁZDNÝ (průhledný) a frame `i` je plná výplň `colors[i-1]`. Tilemap tak čte hodnotu dlaždice 0 jako prázdnou a 1..N jako barevné dlaždice.
- `poly_frames(size, points, nframes, color, fill=True)` - upeče `nframes` rotací polygonu (body kolem středu, +y dolů) do atlasu `size x size`. Engine rotuje i za běhu (`Sprite.angle`); upečené framy vymění trochu RAM za levnější blit na frame a pixelově stabilní grafiku, takže je vyber pro mnoho stále rotujících objektů (asteroidy) a `angle` pro jednorázovou nebo plynulou rotaci. Nastav `fill=False` pro obrys.

```python
import picogame as pg
import picogame_shapes as shp

ball = shp.circle(4, pg.rgb565(255, 255, 120))
bricks = shp.tileset_colors(16, 8, [pg.rgb565(220, 70, 70),
                                    pg.rgb565(80, 140, 240)])   # 0 je prázdná, 1..2 barevné
ship = shp.poly_frames(16, [(0, -8), (6, 7), (0, 4), (-6, 7)], 16,
                       pg.rgb565(200, 220, 255))                 # 16 pre-rotated frames
sprite = pg.Sprite(ball, 100, 60)
```

:::note[Pozor]
frame 0 v `color_frames` je viditelná barva, ale v `tileset_colors` je frame 0 průhledný (prázdný) - vyber ten, který odpovídá tomu, jak tvůj Tilemap zachází s hodnotou 0. `circle` vyplňuje bitmapu od okraje k okraji, takže při zvětšení vypadá jako by měla ploché hrany. `poly_frames` s `nframes=1` upeče jediný neotočený frame (použij pro tvar s pevným směrem).
:::

## picogame_pool

`Pool` předem vytvoří pevný počet spritů pro krátce žijící objekty, například střely, nepřátele nebo bonusy. Viditelný sprite označuje obsazenou pozici a `sprite.data` může nést stav entity. Přidání a uvolnění objektu nevytváří nový sprite. Proč na zařízení záleží na stabilních alokacích, popisuje [/cs/memory/](/cs/memory/).

`Pool(scene, bitmap, capacity, anchor=None, fixed=False)` předalokuje `capacity` skrytých spritů sdílejících `bitmap`, nastaví každému `anchor` (pokud je zadán) a `data = None` a přidá je všechny do `scene` (`fixed=` se předává přímo do `scene.add`).

- `pool.items` - podkladový seznam spritů. Přímá iterace nevytváří další kolekci.
- `pool.spawn()` - udělá první volný (skrytý) sprite viditelným a vrátí ho, nebo None, pokud je pool plný. Slot se vrací ve svém **výchozím vzhledu** - blit efekt (`flash`/`tint`/`dither`/`shadow`), `scale`/`angle`, `frame` a flipy se obnoví na to, jak sprity vypadaly při prvním `spawn()` - takže záblesk po zásahu ani zvětšení při smrti neprosákne do dalšího života. Nastavení hned po vytvoření (`for e in enemies.items: e.flip_y = True`) tedy zůstává; na tobě je jen `.data` a pozice.
- `pool.baseline()` - znovu sejme výchozí vzhled, když sprity přenastavíš později ve hře (větší balvany ve třetím levelu).
- `pool.free(s)` - skryje sprite `s` (vrátí ho do poolu).
- `pool.free_all()` - skryje všechny sprity (použij při resetu levelu).
- `pool.count()` - počet živých (viditelných) spritů; levné, ale pro samotné sprity iteruj `items`.

```python
import picogame as pg
import picogame_pool

bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))

b = bullets.spawn()                        # zobrazený sprite, nebo None při plném fondu
if b:
    b.data = {"vx": 6}
    b.move(x, y)

for s in bullets.items:                    # iterace bez alokací
    if not s.visible:
        continue
    s.move(s.x + s.data["vx"], s.y)
    if off_screen(s):
        bullets.free(s)
```

:::note[Pozor]
při iteraci vždy přeskakuj skryté sloty (`if not s.visible: continue`) - `items` obsahuje každý slot, živý i mrtvý. `spawn()` vrací první volný slot, který najde (nespoléhej na žádné konkrétní pořadí), takže pokud ve stejném kroku zavoláš `free(s)` a `spawn()`, přečti si stav z `s.data` PŘED uvolněním - nový spawn ho může přepsat. Plný pool vrátí z `spawn()` None; zkontroluj to. Všechny sprity sdílejí jednu bitmapu, takže frame/animaci pro každou entitu musíš nastavit na každém spritu po `spawn()`.
:::
