# Formát scény picogame

Scéna popisuje úroveň nebo mapu jako **data**, která používá hra na zařízení, desktopový
simulátor i [webový editor](/cs/tools/editor/). Do dat patří grafické soubory, umístění
spritů, tilemapy, význam tilů, pořadí vrstev, HUD a nastavení kamery. Herní
logika, například pohyb, AI a podmínky výhry, zůstává v Pythonu.

## Postup převodu

```text
game.json  (+ hero.png ...)  ──Save v editoru / scene_build.py art──▶  hero.pal8 (grafika pro desku)
                             ──picogame_scene.Game(pg, "game.json")──▶  běží rovnou (streamem, upečeno při startu)
                             ──scene_build.py build --mpy───────────▶  build/game_bank.mpy + level_*.mpy (ship)
```

- **Zdroj = jeden JSON na hru** (`game.json`): všechny úrovně, tabulka prostředků, zvuky a
  příběhová data zón. Čitelný v diffu, editovatelný ručně, editor i `scene_build.py fmt` ho
  zapisují v jednom kanonickém tvaru. Barvy jako `[r, g, b]`, mapy jako řádky ASCII.
- **Pixely v JSON nikdy nejsou.** PNG prostředek má vedle sebe sidecar `.pal8`
  (`hero.png` → `hero.pal8`), který zapíše Save v editoru nebo `scene_build.py art`; deska ho čte
  přímo do bitmapy. Barevné tilesety a obdélníkové zástupce žádný soubor nepotřebují.
- **Deska čte game.json sama.** `picogame_scene.Game` prochází soubor po jednotlivých úrovních
  (`json.load` v CircuitPythonu vrací první úplnou hodnotu), při startu každou upeče a pekaře
  uvolní: změřeno na RP2040 40–60 ms a ~4,5 kB na úroveň, bez nástroje na hostu.
- **Ship = upečené moduly.** `scene_build.py build --mpy` zapíše `build/game_bank.mpy`, jeden
  `level_<name>.mpy` na úroveň a `code.py`, který otevře banku místo JSON; v RAM zůstává jen
  aktuální úroveň. Stejný loader, stejný herní kód.
- **Kód zůstává v Pythonu.** `code.py` je tvůj (editor ho vytvoří jednou), `story.py` drží
  příběhové skripty `def name(d)`, na které se zóna odkáže jménem. Z JSON se žádný kód negeneruje.

```bash
python3 tools/scene_build.py check          # validace game.json (id, legendy, zóny, efekty)
python3 tools/scene_build.py fmt            # kanonický text (totéž zapisuje editor)
python3 tools/scene_build.py art            # PNG -> sidecary .pal8
python3 tools/scene_build.py build --mpy    # ship: build/ s moduly .mpy
python3 tools/scene_build.py migrate old.scene.json   # v1 scéna / projekt / .pgproj -> game.json
```

Starší `*.scene.json` (jedna úroveň, prostředky uvnitř) a v1 `project.json` všechny nástroje i
deska dál čtou; `migrate` je přepíše na `game.json` a originál přesune do `legacy/`.

## Zdrojové schéma (verze 2)

```jsonc
{
  "format": "picogame-project", "version": 2,
  "name": "Quest", "icon": "icon.bmp",   // titulek a ikona pro launcher (volitelné)
  "size": [320, 240],                     // obrazovka zařízení
  "start": "world1",                      // úvodní úroveň (výchozí: první)

  "assets": {                             // jedna tabulka pro celou hru; id jsou identifikátory
    "hero":  { "type": "sprite",  "src": "hero.png", "frame": [12, 16], "frames": 6, "transparent": 0,
               "animations": { "walk": { "frames": [0,1,2,1], "fps": 8, "loop": true } } },
    "tiles": { "type": "tileset", "src": "tiles.png", "tile": [16, 16], "frames": 5,
               "legend": { ".": 0, "#": 1, "o": 2, "G": 3 },        // abeceda řádků ASCII
               "props": { "1": {"solid": true}, "2": {"coin": true}, "3": {"goal": true} } },
    "flag":  { "type": "rect", "size": [8, 16], "color": [255, 220, 60] },
    "grass": { "type": "tileset_color", "tile": [16, 16], "colors": { "1": [40, 120, 60] },
               "legend": { ".": 0, "g": 1 } }
  },
  "sounds": { "jump": { "src": "jump.wav" } },

  "levels": [
    { "name": "world1", "title": "World 1-1",   // name = identifikátor; title = pro lidi
      "background": [8, 10, 24],               // při převodu -> RGB565 ve wire order
      "worldSize": [1280, 240],                // jen když je svět větší než namalovaný obsah
      "layers": [                              // pořadí zdola nahoru
        { "kind": "tilemap", "asset": "tiles", "pos": [0, 0],
          "rows": ["....o....", "###...###"] },                 // znaky z legendy prostředku
        { "kind": "sprite", "asset": "hero", "name": "player",
          "pos": [40, 208], "anchor": [0.5, 1], "anim": "walk", "data": { "lives": 3 } },
        { "kind": "sprite", "asset": "goomba", "tag": "foes", "name": "gate_npc", "pos": [224, 208] },
        { "kind": "group", "asset": "goomba", "tag": "foes", "anchor": [0.5, 1],
          "instances": [[480, 208], [704, 208]] },
        { "kind": "tilemap", "asset": "tiles", "fg": true, "rows": ["....", "...."] },   // nad sprity
        { "kind": "particles", "name": "fx", "capacity": 64, "size": 2, "gravity": 0.5, "fade": true },
        { "kind": "hudlabel", "name": "score", "pos": [4, 4], "fg": [255,255,255], "bg": [0,0,0] }
      ],
      "camera": { "mode": "follow", "target": "player", "axis": "x", "bounds": [0, 0, 1280, 240] },
      "zones": [
        { "tag": "elder", "x": 96, "y": 160, "w": 48, "h": 48,
          "data": { "say": [{ "if": "gate_open", "lines": ["Jdi dál."] }, { "lines": ["Zatáhni za páku."] }] } },
        { "tag": "lever", "x": 200, "y": 160, "w": 40, "h": 40,
          "data": { "ask": { "lines": ["Zatáhnout za páku?"], "set": "gate_open", "done": ["Už je zataženo."] } } },
        { "tag": "exit", "x": 600, "y": 160, "w": 32, "h": 64,
          "data": { "goto": ["cave", "entry"], "if": "gate_open", "denied": ["Brána je zavřená."] } },
        { "tag": "boss", "x": 300, "y": 100, "w": 64, "h": 64, "data": { "script": "boss_fight" } }
      ],
      "points": [ { "name": "spawn", "x": 40, "y": 208 } ],
      "effects": [ { "if": "gate_open", "swap": [3, 0], "unsolid": [3], "hide": ["gate_npc"] } ],
      "music": "theme"
    },
    { "name": "cave", "background": [10, 10, 30], "layers": [ "..." ] }
  ]
}
```

Poznámky k polím:

- **assets** — typy `sprite` / `tileset` / `bitmap` (`src` PNG + `frame` nebo `tile`, `frames`,
  `transparent`), `rect`, `tileset_color`; tileset může připojit **props** pro jednotlivé tily
  (`solid`/`coin`/`goal`/`hazard`/vlastní) a sprite může deklarovat **animations**
  (`{name: {frames, fps, loop}}`). **legend** tilesetu je abeceda jeho řádků ASCII, společná pro
  všechny vrstvy, které jím malují; jen se rozšiřuje — editor ji nikdy nepřepisuje, takže diff
  mapy zůstává obrázkem a znaky, které jsi zvolil ty nebo agent, přežijí uložení.
- **levels** — `name` je identifikátor (stane se modulem `level_<name>` a klíčem pro `goto`);
  `title` je jméno pro lidi; `worldSize` se zapisuje jen tehdy, když je svět větší než namalovaný
  obsah.
- **druhy vrstev** — `tilemap` (povoleno několik; jedna může mít `fg: true`, aby kreslila přes
  sprity), `sprite` (`name`/`anchor`/`frame`/`anim`/`data`, volitelně `angle` ve stupních,
  volitelně `tag`, aby pojmenovaný sprite patřil i do skupiny), `group` (mnoho instancí jedné
  bitmapy, adresovatelných přes `tag`), `particles`, `hudlabel` (nezávislý na kameře).
- **tilemapa dvěma zaměnitelnými způsoby** — `"rows"`: jeden string na řádek nad legendou
  prostředku (výchozí; tvar, který člověk čte v diffu a agent upravuje ručně). Nebo `"grid"`:
  obdélníkové 2-D pole indexů dlaždic, jeden vnitřní seznam na řádek. Obojí se upeče do stejných
  bajtů. Hodnota v legendě může nést i orientaci, takže otočená dlaždice je prostě vlastní znak;
  znak, který v legendě chybí, se upeče jako dlaždice 0 a `check` to ohlásí.
- **orientace dlaždic** — hodnota v gridu může v bitech 8–10 nést nativní orientaci dlaždice:
  `value = tile | flipX<<8 | flipY<<9 | transpose<<10`. Baker přibalí orientační rovinu, jen když
  ji nějaká buňka používá.
- **zones** — obdélníky, na které se hra ptá (`view.in_zone`); jejich `data` jsou buď
  **příběhová data** (`say` s variantami podle flagu, `ask` se `set`/`done`/`yes`/`no`,
  `goto [úroveň, bod]` s `if`/`denied`), která interpretuje `picogame_story`, nebo
  `{"script": "jmeno"}` → `def jmeno(d)` v tvém `story.py`. **points** jsou pojmenované pozice
  (`view.point`); obojí může nést volný objekt `data`.
- **effects** — pravidla úrovně přehraná po každém načtení a po každé změně flagu: `swap` dvou
  dlaždic, `solid`/`unsolid` dlaždic, `hide`/`show` pojmenovaných spritů, vše pod `if`.
- **camera** obsahuje nastavení, které hra může použít přes `set_view`; kameru může řídit také
  vlastní logikou.
- Neznámé klíče zůstávají: editor i `fmt` je zapíší zpět, loader je ignoruje.

### Soubor `.pal8`

Ručně ho nikdy nepíšeš — vyrobí ho Save v editoru a `scene_build.py art`, čte ho
`picogame_scene.read_pal8()`. Rozvržení je tu proto, aby ho uměl vytvořit i převodník, grafická
pipeline nebo agent. Všechno je **little-endian** a soubor se popisuje sám, takže tentýž sidecar
poslouží jakékoli hře, která očekává dané rozměry snímku.

**Hlavička — 16 bajtů** (formát `struct` `<4sBBHHHHH`):

| offset | velikost | pole | hodnota |
|---|---|---|---|
| 0 | 4 | magic | `PAL8` (ASCII) |
| 4 | 1 | verze | `1` — cokoli jiného musí čtečka odmítnout |
| 5 | 1 | flags | bit 0 nastaven = **index 0 je průhledný klíč**; ostatní bity `0` |
| 6 | 2 | `fw` | šířka snímku v pixelech |
| 8 | 2 | `fh` | výška snímku v pixelech |
| 10 | 2 | `frames` | počet snímků |
| 12 | 2 | `ncol` | počet položek palety |
| 14 | 2 | rezervováno | `0` |

**Paleta** — `ncol` × `uint16` hned za hlavičkou. Barvy jsou RGB565 ve **wire pořadí**, tedy v tom
pořadí bajtů, které berou panel, framebuffer i simulátor — RGB565 hodnota s prohozenými bajty:

```python
c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)   # běžné RGB565
wire = ((c >> 8) | (c << 8)) & 0xFFFF                  # to, co jde do souboru
```

**Indexy** — `fw * frames * fh` bajtů, jeden bajt na pixel, až do konce souboru. Snímky leží
**vedle sebe v jednom pásu**, takže krok řádku je `fw * frames` a řádek `y` snímku `f` začíná na
`y * fw * frames + f * fw`. Je to totéž rozvržení, jaké bere `picogame.Bitmap(..., frames=…,
stride=…)`, a proto může loader buffer předat rovnou, bez přerovnávání.

Čtečka by měla brát špatné magic, jinou verzi než 1 i zkrácený blok indexů jako chybu — přesně to
dělá ta dodávaná.

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

### Jeden soubor a starší podoby

- `"format": "picogame-project"`, `"version": 2` — **game.json**, tvar výše: to, co editor ukládá
  a co čte `scene_build.py` i deska.
- `"format": "picogame-scene"` (v1) — jedna samostatná scéna s prostředky uvnitř; všechny nástroje
  ji dál čtou, starší volání `scene_build.py x.scene.json` ji upeče do jednoho modulu `<name>_scene`.
- v1 `project.json` — banka prostředků + `levels[]` s legendami na vrstvách; čte se a v paměti
  povýší (legendy se přesunou k prostředkům). `scene_build.py migrate` zapíše soubor v2.

### Validace

`scene_build.py check` hlásí s cestou v souboru: neexistující id prostředků, indexy dlaždic mimo
tileset, řádky různé délky, znaky chybějící v legendě, neexistující cíle `goto`, flagy testované
a nikdy nenastavené, jména `script` bez `def` ve `story.py` a `transparent` použité jako příznak
dlaždice. Deska umí méně: rozbitý JSON skončí na `game.json: level 2 (byte 1234): syntax error`,
proto validuj na hostu, než soubor zkopíruješ.

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

JSON umí přečíst i deska: `picogame_scene.Game` prochází `game.json` po jednotlivých úrovních a
každou při startu upeče do těchto n-tic (RP2040: 40–60 ms a ~4,5 kB rezidentně na úroveň, celý
třílevelový ukázkový projekt nastartuje za 0,2 s), takže ladění úrovně znamená upravit jeden
textový soubor na CIRCUITPY a stisknout reset. Upečená podoba `.mpy` zůstává formátem pro ship:
žádné parsování a v RAM jen aktuální úroveň.

## API načítání za běhu

```python
import picogame_scene as pgs, terminalio
game = pgs.Game(pg, "game.json", font=terminalio.FONT)   # při startu projde a upeče všechny úrovně
game = pgs.Game(pg, "game_bank")                          # ...nebo shipnutá banka + moduly level_*
game.levels, game.start, game.size                        # co soubor deklaruje
view = game.load(game.start)                              # View jedné úrovně
view = game.load("cave", "entry")                         # jiná úroveň, hráč na pojmenovaném bodu

view.scene                  # naplněná a seřazená picogame.Scene
view.named["player"]        # objekt Sprite
view.group("enemies")       # seznam Spritů (včetně pojmenovaných se stejným tagem)
view.tick(dt)               # posune automatické animace jednou za snímek
view.is_solid(tx, ty)       # vlastnost tilu v první hlavní mapě
view.tile_has(tx, ty, "coin")
view.tile_xy(px, py)        # pixel světa -> (tx, ty) v hlavní mapě
view.in_zone(x, y, "door")  # první zóna obsahující (x, y), nebo None
view.point("spawn")         # pojmenovaný bod (x, y), nebo None
view.play("jump")           # přehraje načtený zvuk podle id
view.camera                 # (režim, cíl, osa, hranice), které hra použije pro kameru
view.effects, view.world    # příběhová pravidla úrovně a autorská velikost světa
view.swap_tiles(a, b)       # každá buňka s dlaždicí a se změní na b (co dělá efekt)
```

Příběh: `picogame_script.Director` spouští skripty po jednom kroku za snímek a
`picogame_story.Story(d, game, story_module)` mu předává data zón a `story.py`:
`tale.enter(view, x, y)` spustí zónu při vstupu, `tale.effects(view)` přehraje pravidla,
`yield from d.goto(level, point)` požádá herní smyčku o výměnu úrovně mezi dvěma kroky. Smyčku
ukazují šablony runneru z editoru; `load()` / `load_bank()` zůstávají pro upečené slovníky SCENE.

Úplné chování a omezení načítání popisuje stránka
[Sestavování scén](/cs/helpers/building-scenes/).
