# picogame scene format

A scene describes a level or map as **data** shared by the device game, desktop simulator,
and [web editor](/tools/editor/). It can contain assets, sprite placement, tilemaps, tile
properties, layer order, HUD elements, and camera settings. Game logic such as movement, AI,
and win conditions stays in Python.

## The pipeline

```text
game.json  (+ hero.png ...)  ──editor Save / scene_build.py art──▶  hero.pal8 (device art)
                             ──picogame_scene.Game(pg, "game.json")──▶  runs as is (streamed, baked at boot)
                             ──scene_build.py build --mpy───────────▶  build/game_bank.mpy + level_*.mpy (ship)
```

- **Authoring = one JSON per game** (`game.json`): every level, the assets table, sounds, the
  story data of the zones. Diff-able, hand-editable, written by the editor and by
  `scene_build.py fmt` in one canonical text form. Colours as `[r, g, b]`, maps as ASCII rows.
- **Pixels never live in the JSON.** A PNG asset is served from a `.pal8` sidecar next to it
  (`hero.png` → `hero.pal8`), written by the editor's Save or by `scene_build.py art`; the device
  reads it straight into the bitmap. Colour tilesets and rect placeholders need no file.
- **The device reads game.json itself.** `picogame_scene.Game` streams the file one level at a
  time (CircuitPython's `json.load` returns the first complete value), bakes every level at boot
  and releases the baker: measured on an RP2040, 40–60 ms and ~4.5 kB per level, no host tool.
- **Ship = baked modules.** `scene_build.py build --mpy` writes `build/game_bank.mpy` plus one
  `level_<name>.mpy` per level and a `code.py` that opens the bank instead of the JSON; only the
  current level stays resident. Same loader, same game code.
- **Code stays Python.** `code.py` is yours (the editor scaffolds it once); `story.py` holds
  `def name(d)` story scripts a zone can name. Nothing is generated from the JSON into code.

```bash
python3 tools/scene_build.py check          # validate game.json (ids, legends, zones, effects)
python3 tools/scene_build.py fmt            # canonical text (what the editor writes too)
python3 tools/scene_build.py art            # PNG -> .pal8 sidecars
python3 tools/scene_build.py build --mpy    # ship: build/ with the .mpy modules
python3 tools/scene_build.py migrate old.scene.json   # v1 scene / project / .pgproj -> game.json
```

The older `*.scene.json` (one level, assets inline) and v1 `project.json` are still read by every
tool and by the device; `migrate` rewrites them as `game.json` and moves the original to `legacy/`.

## Authoring schema (version 2 — the implemented set)

```jsonc
{
  "format": "picogame-project", "version": 2,
  "name": "Quest", "icon": "icon.bmp",   // launcher title + icon (optional)
  "size": [320, 240],                     // the device screen
  "start": "world1",                      // level to begin in (default: the first)

  "assets": {                             // one table for the whole game; ids are identifiers
    "hero":  { "type": "sprite",  "src": "hero.png", "frame": [12, 16], "frames": 6, "transparent": 0,
               "animations": { "walk": { "frames": [0,1,2,1], "fps": 8, "loop": true } } },
    "tiles": { "type": "tileset", "src": "tiles.png", "tile": [16, 16], "frames": 5,
               "legend": { ".": 0, "#": 1, "o": 2, "G": 3 },        // the ASCII rows' alphabet
               "props": { "1": {"solid": true}, "2": {"coin": true}, "3": {"goal": true} } },
    "flag":  { "type": "rect", "size": [8, 16], "color": [255, 220, 60] },
    "grass": { "type": "tileset_color", "tile": [16, 16], "colors": { "1": [40, 120, 60] },
               "legend": { ".": 0, "g": 1 } }
  },
  "sounds": { "jump": { "src": "jump.wav" } },

  "levels": [
    { "name": "world1", "title": "World 1-1",   // name = identifier; title = for people
      "background": [8, 10, 24],               // -> wire rgb565 at bake time
      "worldSize": [1280, 240],                // only when larger than the painted content
      "layers": [                              // ordered bottom -> top
        { "kind": "tilemap", "asset": "tiles", "pos": [0, 0],
          "rows": ["....o....", "###...###"] },                 // chars from the asset's legend
        { "kind": "sprite", "asset": "hero", "name": "player",
          "pos": [40, 208], "anchor": [0.5, 1], "anim": "walk", "data": { "lives": 3 } },
        { "kind": "sprite", "asset": "goomba", "tag": "foes", "name": "gate_npc", "pos": [224, 208] },
        { "kind": "group", "asset": "goomba", "tag": "foes", "anchor": [0.5, 1],
          "instances": [[480, 208], [704, 208]] },
        { "kind": "tilemap", "asset": "tiles", "fg": true, "rows": ["....", "...."] },   // over sprites
        { "kind": "particles", "name": "fx", "capacity": 64, "size": 2, "gravity": 0.5, "fade": true },
        { "kind": "hudlabel", "name": "score", "pos": [4, 4], "fg": [255,255,255], "bg": [0,0,0] }
      ],
      "camera": { "mode": "follow", "target": "player", "axis": "x", "bounds": [0, 0, 1280, 240] },
      "zones": [
        { "tag": "elder", "x": 96, "y": 160, "w": 48, "h": 48,
          "data": { "say": [{ "if": "gate_open", "lines": ["Go on."] }, { "lines": ["Pull the lever."] }] } },
        { "tag": "lever", "x": 200, "y": 160, "w": 40, "h": 40,
          "data": { "ask": { "lines": ["Pull the lever?"], "set": "gate_open", "done": ["Already pulled."] } } },
        { "tag": "exit", "x": 600, "y": 160, "w": 32, "h": 64,
          "data": { "goto": ["cave", "entry"], "if": "gate_open", "denied": ["The gate is shut."] } },
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

Field notes:

- **assets** — kinds `sprite` / `tileset` / `bitmap` (`src` PNG + `frame` or `tile`, `frames`,
  `transparent`), `rect`, `tileset_color`; a tileset may attach per-tile **props**
  (`solid`/`coin`/`goal`/`hazard`/your own) and a sprite may declare **animations**
  (`{name: {frames, fps, loop}}`). The **legend** of a tileset is the alphabet its ASCII rows use,
  shared by every layer painted with it; it is append-only — the editor never re-letters it, so a
  map's diff stays a picture and the characters you or an agent chose survive a Save.
- **levels** — `name` is an identifier (it becomes the `level_<name>` module and the key `goto`
  targets use); `title` is the human name; `worldSize` is written only when the world is larger
  than the painted content.
- **layer kinds** — `tilemap` (several allowed; one may be `fg: true` to draw over sprites),
  `sprite` (`name`/`anchor`/`frame`/`anim`/`data`, optional `angle` in degrees, optional `tag` so a
  named single sprite still belongs to a group), `group` (many instances of one bitmap, addressable
  by `tag`), `particles`, `hudlabel` (camera-independent).
- **the tilemap, two interchangeable ways** — `"rows"`: one string per row over the asset's legend
  (the default, the form a person reads in a diff and an agent edits by hand). Or `"grid"`: a
  rectangular 2-D array of tile indices, one inner list per row. Both bake to identical bytes. A
  legend value may carry an orientation, so an oriented tile is simply its own character; a
  character missing from the legend bakes as tile 0 and `check` reports it.
- **tile orientations** — a grid value may carry the native per-tile orientation in bits 8–10:
  `value = tile | flipX<<8 | flipY<<9 | transpose<<10`. The baker emits the orientation plane only
  when a cell uses it.
- **zones** — rectangles the game queries (`view.in_zone`); their `data` is either **story data**
  (`say` variants picked by flag, `ask` with `set`/`done`/`yes`/`no`, `goto [level, point]` with
  `if`/`denied`) interpreted by `picogame_story`, or `{"script": "name"}` → `def name(d)` in your
  `story.py`. **points** are named positions (`view.point`); both may carry free-form `data`.
- **effects** — per-level rules replayed after every load and every flag change:
  `swap` two tiles, make tiles `solid`/`unsolid`, `hide`/`show` named sprites, all under `if`.
- **camera** is advisory data the game applies via `set_view`; games can drive the camera
  themselves.
- Unknown keys are kept: the editor and `fmt` write them back, the loader ignores them.

### The `.pal8` file

You never write one by hand — the editor's Save and `scene_build.py art` produce them, and
`picogame_scene.read_pal8()` reads them. The layout is here so a converter, an art pipeline or an
agent can emit one directly. Everything is **little-endian**, and the file is self-describing, so the
same sidecar serves any game that expects those frame dimensions.

**Header — 16 bytes** (`struct` format `<4sBBHHHHH`):

| offset | size | field | value |
|---|---|---|---|
| 0 | 4 | magic | `PAL8` (ASCII) |
| 4 | 1 | version | `1` — a reader must reject anything else |
| 5 | 1 | flags | bit 0 set = **index 0 is the transparent key**; all other bits `0` |
| 6 | 2 | `fw` | frame width in pixels |
| 8 | 2 | `fh` | frame height in pixels |
| 10 | 2 | `frames` | number of frames |
| 12 | 2 | `ncol` | palette entries |
| 14 | 2 | reserved | `0` |

**Palette** — `ncol` × `uint16`, immediately after the header. The colours are **wire-order** RGB565,
the byte order the panel, the framebuffer and the simulator all take, i.e. an RGB565 value with its
two bytes swapped:

```python
c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)   # plain RGB565
wire = ((c >> 8) | (c << 8)) & 0xFFFF                  # what goes in the file
```

**Indices** — `fw * frames * fh` bytes, one byte per pixel, to the end of the file. Frames sit **side
by side in one strip**, so the row stride is `fw * frames` and row `y` of frame `f` starts at
`y * fw * frames + f * fw`. That is the same layout `picogame.Bitmap(..., frames=…, stride=…)` takes,
which is why the loader can hand the buffer over without rearranging it.

A reader should treat a wrong magic, a version other than 1, or a short index block as an error —
that is what the shipped one does.

### Importing Tiled maps

`tools/tiled2scene.py` converts a [Tiled](https://www.mapeditor.org/) JSON map (`.tmj`) into
this format: tile layers (flip/rotate bits become native tile orientations), tile objects →
sprites (rotation → `angle`, custom properties → `data`), rectangles → zones, points →
points, and bool per-tile properties (`solid`/`coin`/…) → tileset props. Tilesets are
repacked into horizontal-strip PNGs next to the output. Unsupported Tiled features
(animated tiles, sub-tile collision shapes, image layers, opacity/tint/parallax, polygon
objects) are reported, never silently dropped:

```
python3 tools/tiled2scene.py map.tmj --follow player
python3 tools/scene_build.py map_scene.json
```

### One file, and the older shapes

- `"format": "picogame-project"`, `"version": 2` — **game.json**, the shape above: what the
  editor saves, what `scene_build.py` and the device read.
- `"format": "picogame-scene"` (v1) — one self-contained scene, assets inline; still read by
  every tool, baked to one `<name>_scene` module by the legacy call `scene_build.py x.scene.json`.
- v1 `project.json` — an assets bank + `levels[]` with legends on the layers; read and upgraded
  in memory (legends move into the assets). `scene_build.py migrate` writes the v2 file.

### Validation

`scene_build.py check` reports, with a path into the file: dangling asset ids, tile indices past
the tileset, rows of different lengths, characters missing from a legend, `goto` targets that do
not exist, flags that are tested but never set, `script` names with no `def` in `story.py`, and
`transparent` used as a tile flag. The device gives less: a broken JSON stops at
`game.json: level 2 (byte 1234): syntax error` — validate on the host before you copy.

## Baked runtime module (what the device imports)

```python
# world1_scene.py  (then -> world1_scene.mpy)
SCENE = {
  "bg": 0x2001,                          # pre-converted wire rgb565
  "assets": {
    "hero":  ("pal8", "a1b2...", 12, 16, 6, 0, (0x0000, 0xF80F, ...)),  # data(hex),w,h,frames,transp,palette
    "tiles": ("pal8", "00ff...", 16, 16, 5, None, (...)),
  },
  "tileprops": { "tiles": { "solid": b"\x00\x01\x00\x00\x00",
                            "coin":  b"\x00\x00\x01\x00\x00" } },  # indexed by tile value
  "anims":  { "hero": { "walk": ((0, 1, 2, 1), 8, True) } },
  "layers": [
    ("tilemap", "tiles", 80, 15, 0, 0, b"\x01\x01..."),               # cols,rows,ox,oy,grid bytes
    ("sprite", "hero", "player", 40, 208, 128, 256, 0, {"lives": 3}),   # anchor in 1/256
    ("group", "goomba", "enemies", 128, 256, ((224,208), (480,208))),
    ("particles", "fx", 64, 2, 0.5, True),
    ("hudlabel", "score", 4, 4, 0xFFFF, 0x0000),
  ],
  "camera": ("follow", "player", "x", 0, 0, 1280, 240),
}
```

Layers and assets are tuples (not dicts) to keep the `.mpy` small and parse-free; the loader
unpacks positionally. The grid and tile-prop tables are `bytes` (one allocation each); asset
pixel data is a hex string the loader decodes with `bytes.fromhex(...)`.

The JSON is also readable on the device: `picogame_scene.Game` streams `game.json` one level at a
time and bakes each into these tuples at boot (RP2040: 40–60 ms and ~4.5 kB resident per level,
the whole 3-level demo project boots in 0.2 s), so iterating on a level means editing one text
file on CIRCUITPY and pressing reset. The baked `.mpy` form stays the ship format: no parse at
all, and only the current level in RAM.

## Runtime loader API

```python
import picogame_scene as pgs, terminalio
game = pgs.Game(pg, "game.json", font=terminalio.FONT)   # streams + bakes every level at boot
game = pgs.Game(pg, "game_bank")                          # ...or the shipped bank + level_* modules
game.levels, game.start, game.size                        # what the file declares
view = game.load(game.start)                              # a View for one level
view = game.load("cave", "entry")                         # another level, player at a named point

view.scene                  # the picogame.Scene (already populated + layered)
view.named["player"]        # the Sprite
view.group("enemies")       # list of Sprites (tagged singles included)
view.tick(dt)               # advance auto-animated sprites (once per frame)
view.is_solid(tx, ty)       # tile-property query (primary/first tilemap)
view.tile_has(tx, ty, "coin")
view.tile_xy(px, py)        # world pixel -> (tx, ty) on the primary tilemap
view.in_zone(x, y, "door")  # first zone containing (x, y), or None
view.point("spawn")         # named point (x, y), or None
view.play("jump")           # play a loaded sound by id
view.camera                 # (mode, target, axis, bounds) for the game to apply
view.effects, view.world    # the level's story rules and authored world size
view.swap_tiles(a, b)       # every cell of tile a becomes b (what an effect does)
```

Story: `picogame_script.Director` runs scripts one step per frame and
`picogame_story.Story(d, game, story_module)` feeds it the zones' data and `story.py`:
`tale.enter(view, x, y)` starts a zone on entry, `tale.effects(view)` replays the rules,
`yield from d.goto(level, point)` asks the game loop to swap levels between two steps. The editor's
runner templates show the loop; `load()` / `load_bank()` remain for baked SCENE dicts.

See [Building scenes](/helpers/building-scenes/) for the complete loader behaviour and limits.
