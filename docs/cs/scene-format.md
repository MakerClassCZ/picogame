# Formát scény picogame

Scéna popisuje úroveň nebo mapu jako **data**, která používá hra na zařízení, desktopový
simulátor i [webový editor](/cs/tools/editor/). Do dat patří grafické soubory, umístění
spritů, tilemapy, význam tilů, pořadí vrstev, HUD a nastavení kamery. Herní
logika, například pohyb, AI a podmínky výhry, zůstává v Pythonu.

## Postup převodu

```text
*.scene.json  ──tools/scene_build.py──▶  <name>_scene.py  ──mpy-cross──▶  <name>_scene.mpy
(úprava v editoru nebo ručně)            (převedený modul)                (kopie do CIRCUITPY)
```

- **Zdrojový JSON** (`*.scene.json`) může upravovat člověk i editor. Barvy zapisuje jako
  `[r, g, b]` a mapy jako mřížky.
- **Převedený modul Pythonu** (`SCENE = {...}`) obsahuje barvy RGB565 ve wire order,
  mřížku tilů jako `bytes` s jedním bajtem na buňku a grafiku převedenou na atlasy PAL8.
  Pro zařízení jej zkompiluj do `.mpy`.
- **Stejné načítání na obou cílech:** `picogame_scene.load(pg, SCENE, ...)` sestaví
  `pg.Scene` přes veřejné API picogame. Použití popisuje stránka
  [Sestavování scén](/cs/helpers/building-scenes/).

Zapečení:

```bash
python3 tools/scene_build.py examples/levels/world1.scene.json
# -> examples/levels/world1_scene.py   (atribut modulu SCENE)
tools/build_mpy.sh                     # případně přelož modul pro zařízení přes mpy-cross
```

## Zdrojové schéma (verze 2)

```jsonc
{
  "format": "picogame-scene", "version": 2,
  "size": [320, 240],
  "background": [8, 10, 24],            // při převodu -> RGB565 ve wire order

  "assets": {                            // sdílená banka, položky se odkazují přes id
    "hero":  { "type": "sprite",  "src": "hero.png", "frames": 6, "transparent": 0,
               "animations": { "walk": { "frames": [0,1,2,1], "fps": 8, "loop": true } } },
    "tiles": { "type": "tileset", "src": "tiles.png", "tile": [16, 16], "frames": 5,
               "props": { "1": {"solid": true}, "2": {"coin": true}, "3": {"goal": true} } },
    "flag":  { "type": "rect", "size": [8, 16], "color": [255, 220, 60] }
  },
  "sounds": { "jump": { "src": "jump.wav" } },

  "layers": [                            // pořadí zdola nahoru
    { "kind": "tilemap", "asset": "tiles", "cols": 80, "rows": 15, "pos": [0, 0],
      "grid": [[0,0,1,1,0], [1,1,1,1,1]] },   // nebo "rows" + "legend", viz níže
    { "kind": "sprite", "asset": "hero", "name": "player",
      "pos": [40, 208], "anchor": [0.5, 1.0], "anim": "walk", "data": { "lives": 3 } },
    { "kind": "group", "asset": "goomba", "anchor": [0.5, 1.0],
      "instances": [[224, 208], [480, 208], [704, 208]], "tag": "enemies" },
    { "kind": "tilemap", "asset": "tiles", "fg": true, "cols": 80, "rows": 15,
      "legend": { ".": 0, "#": 1, "o": 2 },       // fg: true kreslí nad sprity
      "rows": ["....o....", "###...###"] },
    { "kind": "particles", "capacity": 64, "size": 2, "gravity": 0.5, "fade": true,
      "name": "fx" },
    { "kind": "hudlabel", "name": "score", "pos": [4, 4],
      "fg": [255,255,255], "bg": [0,0,0] }   // bez vlivu kamery (fixed je odvozené)
  ],

  "zones":  [ { "tag": "door", "x": 300, "y": 180, "w": 20, "h": 40 } ],
  "points": [ { "name": "spawn", "x": 40, "y": 208 } ],
  "camera": { "mode": "follow", "target": "player", "axis": "x",
              "bounds": [0, 0, 1280, 240] },
  "music": "theme",
  "meta": { "editor": { "grid": 16, "name": "World 1-1" } }   // runtime tuto část ignoruje
}
```

Poznámky k polím:

- **assets** — typy `sprite` / `tileset` / `bitmap` (`src` PNG + `frames`, `tile`,
  `transparent`), `rect`, `tileset_color`; tileset může připojit **props** pro jednotlivé
  tily (`solid`/`coin`/`goal`/`hazard`/vlastní) a sprite může deklarovat **animations**
  (`{name: {frames, fps, loop}}`).
- **druhy vrstev** — `tilemap` (povoleno několik; jedna může mít `fg: true`, aby kreslila
  přes sprity), `sprite` (`name`/`anchor`/`frame`/`anim`/`data`, volitelně `angle` ve
  stupních — nastaví nativní `sprite.angle`), `group` (mnoho instancí jedné bitmapy,
  adresovatelných přes `tag`), `particles`, `hudlabel` (nezávislý na kameře).
  Jakákoli vrstva může nastavit `"fixed": true`.
- **grid tilemapy dvěma zaměnitelnými způsoby** — `"grid"`: obdélníkové 2-D pole indexů
  dlaždic, **jeden vnitřní seznam na ŘÁDEK** (`grid[y][x]`, takže `len(grid)` je `rows` a
  `len(grid[0])` je `cols`; délky řádků musí odpovídat deklarovaným `cols`/`rows`). Nebo
  `"legend"` + `"rows"`: mapa `{znak: index dlaždice}` a jeden string na řádek — tatáž mapa jako
  ASCII obrázek. Baker bere obojí a vyrobí identický výstup, takže volíš podle toho, kdo to
  edituje: `grid` pro editor, `rows` pro cokoli, co člověk čte v diffu nebo agent upravuje ručně
  (zeď je viditelně sloupec `#` a „o tři dlaždice vlevo" je vidět, ne popsané). Editor umí obojí —
  v `Export ▾` je zaškrtávátko **ASCII map**. Hodnota v legendě může nést i orientaci, takže
  otočená dlaždice je prostě vlastní znak; znak, který v legendě chybí, se zapeče jako dlaždice 0
  a baker to ohlásí jako chybu.
- **orientace dlaždic** — hodnota v gridu tilemapy může v bitech 8–10 nést nativní
  orientaci dlaždice: `value = tile | flipX<<8 | flipY<<9 | transpose<<10` (všech
  8 orientací — 4 rotace × zrcadlení). Obyčejné hodnoty zůstávají obyčejné; baker
  přibalí orientační rovinu, jen když ji nějaká buňka používá.
- **zones / points** — pojmenované obdélníky a pozice, na které se hra ptá za běhu
  (`view.in_zone`, `view.point`). Obojí může nést volný objekt `data` (např. importované
  Tiled custom properties): u zóny je pak v tuple na indexu 5, data pointu čteš
  z `view.pdata[name]`.
- **camera** obsahuje nastavení, které hra může použít přes `set_view`; kameru může řídit
  také vlastní logikou.
- **meta** je volný prostor pro editor; načítání za běhu neznámé klíče ignoruje.

### Import map z Tiled

`tools/tiled2scene.py` převede JSON mapu (`.tmj`) z editoru [Tiled](https://www.mapeditor.org/)
do tohoto formátu: dlaždicové vrstvy (flip/rotate bity se stanou nativními orientacemi),
tile objekty → sprity (rotace → `angle`, custom properties → `data`), obdélníky → zóny,
pointy → pointy a bool vlastnosti dlaždic (`solid`/`coin`/…) → props tilesetu. Tilesety se
přebalí do horizontálních strip PNG vedle výstupu. Nepodporované věci z Tiled (animované
dlaždice, sub-tile kolize, image vrstvy, opacity/tint/parallax, polygonové objekty) tool
vypíše, nikdy tiše nezahodí:

```
python3 tools/tiled2scene.py map.tmj --follow player
python3 tools/scene_build.py map_scene.json
```

### Dvě podoby nejvyšší úrovně

- `"format": "picogame-scene"` — jedna samostatná scéna s grafikou uvnitř → převedená do jednoho
  modulu `<name>_scene`.
- `"format": "picogame-project"` — **banka** sdílených prostředků + `levels[]` → převedeno do jednoho modulu
  `_bank` plus jednoho modulu `_level` na úroveň; načti přes
  `bank = picogame_scene.load_bank(pg, BANK)` a pak `load(..., bank=bank)`, takže se sdílená
  grafika nestaví znovu pro každou úroveň.

### Validace

Při neznámém typu prostředku nebo vrstvy skončí převod s `ValueError`, která označí
problematickou položku. Chybějící nebo vadný soubor PNG vyvolá původní chybu převodníku.
Načítání toleruje neznámé klíče na nejvyšší úrovni, ale n-tice vrstev používají pevné pozice.
Modul vytvořený novější verzí `scene_build.py` proto může vyžadovat odpovídající verzi
`picogame_scene`.

## Převedený modul pro zařízení

```python
# world1_scene.py  (potom -> world1_scene.mpy)
SCENE = {
  "bg": 0x2001,                          # RGB565 už ve wire order
  "assets": {
    "hero":  ("pal8", "a1b2...", 12, 16, 6, 0, (0x0000, 0xF80F, ...)),  # data(hex),w,h,snímky,průhlednost,paleta
    "tiles": ("pal8", "00ff...", 16, 16, 5, None, (...)),
  },
  "tileprops": { "tiles": { "solid": b"\x00\x01\x00\x00\x00",
                            "coin":  b"\x00\x00\x01\x00\x00" } },  # indexováno hodnotou tilu
  "anims":  { "hero": { "walk": ((0, 1, 2, 1), 8, True) } },
  "layers": [
    ("tilemap", "tiles", 80, 15, 0, 0, b"\x01\x01..."),               # cols,rows,ox,oy,grid bytes
    ("sprite", "hero", "player", 40, 208, 128, 256, 0, {"lives": 3}),   # kotevní bod v 1/256
    ("group", "goomba", "enemies", 128, 256, ((224,208), (480,208))),
    ("particles", "fx", 64, 2, 0.5, True),
    ("hudlabel", "score", 4, 4, 0xFFFF, 0x0000),
  ],
  "camera": ("follow", "player", "x", 0, 0, 1280, 240),
}
```

Vrstvy a prostředky jsou n-tice místo slovníků, aby modul `.mpy` zůstal malý; načítání je
rozbaluje podle pozice. Mřížka a tabulky vlastností tilů jsou `bytes`, každá v jedné
alokaci. Pixelová data jsou hexadecimální řetězec dekódovaný přes `bytes.fromhex(...)`.

Přímé načítání JSON na zařízení by pro mřížku vytvořilo seznam samostatných Python čísel
(v měřené verzi přibližně 28 B na číslo): mapa 28×18 spotřebuje asi 14 KB jen za tento seznam,
navíc k textu JSON. Stejná mřížka jako
`bytes` literál v `.mpy` má ~500 B a jednu alokaci.

## API načítání za běhu

```python
import picogame_scene as pgs, terminalio
view = pgs.load(pg, world1_scene.SCENE, font=terminalio.FONT)
view.scene                  # naplněná a seřazená picogame.Scene
view.named["player"]        # objekt Sprite
view.group("enemies")       # list of Sprites
view.tick(dt)               # posune automatické animace jednou za snímek
view.is_solid(tx, ty)       # vlastnost tilu v první hlavní mapě
view.tile_has(tx, ty, "coin")
view.tile_xy(px, py)        # pixel světa -> (tx, ty) v hlavní mapě
view.in_zone(x, y, "door")  # first zone containing (x, y), or None
view.point("spawn")         # named point (x, y), or None
view.play("jump")           # play a loaded sound by id
view.camera                 # (režim, cíl, osa, hranice), které hra použije pro kameru
```

Úplné chování a omezení načítání popisuje stránka
[Sestavování scén](/cs/helpers/building-scenes/).
