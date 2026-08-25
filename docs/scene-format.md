# picogame scene format

A scene describes a level or map as **data** shared by the device game, desktop simulator,
and [web editor](/tools/editor/). It can contain assets, sprite placement, tilemaps, tile
properties, layer order, HUD elements, and camera settings. Game logic such as movement, AI,
and win conditions stays in Python.

## The pipeline

```text
*.scene.json  ──tools/scene_build.py──▶  <name>_scene.py  ──mpy-cross──▶  <name>_scene.mpy
(authoring: editor or hand)              (baked runtime module)           (ship to CIRCUITPY)
```

- **Authoring = JSON** (`*.scene.json`): diff-able, round-trippable by the editor or a human.
  Colours as `[r, g, b]`, maps as grids.
- **Runtime = a baked Python module** (`SCENE = {...}`): colours pre-converted to wire RGB565,
  the tilemap grid a `bytes` literal (1 byte/tile, one allocation), art pre-converted to PAL8
  atlases. Import cost stays small; ship it as `.mpy`.
- **One loader for both targets:** `picogame_scene.load(pg, SCENE, ...)` builds the live
  `pg.Scene` using only public engine API, so the same file runs on hardware and in the
  simulator. Loader usage guide: [Building scenes](/helpers/building-scenes/).

Bake:

```bash
python3 tools/scene_build.py examples/levels/world1.scene.json
# -> examples/levels/world1_scene.py   (module attribute SCENE)
tools/build_mpy.sh                     # or mpy-cross the module for the device
```

## Authoring schema (version 2 — the implemented set)

```jsonc
{
  "format": "picogame-scene", "version": 2,
  "size": [320, 240],
  "background": [8, 10, 24],            // -> wire rgb565 at bake time

  "assets": {                            // shared bank, referenced by id
    "hero":  { "type": "sprite",  "src": "hero.png", "frames": 6, "transparent": 0,
               "animations": { "walk": { "frames": [0,1,2,1], "fps": 8, "loop": true } } },
    "tiles": { "type": "tileset", "src": "tiles.png", "tile": [16, 16], "frames": 5,
               "props": { "1": {"solid": true}, "2": {"coin": true}, "3": {"goal": true} } },
    "flag":  { "type": "rect", "size": [8, 16], "color": [255, 220, 60] }
  },
  "sounds": { "jump": { "src": "jump.wav" } },

  "layers": [                            // ordered bottom -> top
    { "kind": "tilemap", "asset": "tiles", "cols": 80, "rows": 15, "pos": [0, 0],
      "grid": [[0,0,1,1,0], [1,1,1,1,1]] },   // or "rows" + "legend", see below
    { "kind": "sprite", "asset": "hero", "name": "player",
      "pos": [40, 208], "anchor": [0.5, 1.0], "anim": "walk", "data": { "lives": 3 } },
    { "kind": "group", "asset": "goomba", "anchor": [0.5, 1.0],
      "instances": [[224, 208], [480, 208], [704, 208]], "tag": "enemies" },
    { "kind": "tilemap", "asset": "tiles", "fg": true, "cols": 80, "rows": 15,
      "legend": { ".": 0, "#": 1, "o": 2 },       // fg: true draws OVER the sprites
      "rows": ["....o....", "###...###"] },
    { "kind": "particles", "capacity": 64, "size": 2, "gravity": 0.5, "fade": true,
      "name": "fx" },
    { "kind": "hudlabel", "name": "score", "pos": [4, 4],
      "fg": [255,255,255], "bg": [0,0,0] }   // camera-independent (fixed implied)
  ],

  "zones":  [ { "tag": "door", "x": 300, "y": 180, "w": 20, "h": 40 } ],
  "points": [ { "name": "spawn", "x": 40, "y": 208 } ],
  "camera": { "mode": "follow", "target": "player", "axis": "x",
              "bounds": [0, 0, 1280, 240] },
  "music": "theme",
  "meta": { "editor": { "grid": 16, "name": "World 1-1" } }   // ignored by the runtime
}
```

Field notes:

- **assets** — kinds `sprite` / `tileset` / `bitmap` (`src` PNG + `frames`, `tile`,
  `transparent`), `rect`, `tileset_color`; a tileset may attach per-tile **props**
  (`solid`/`coin`/`goal`/`hazard`/your own) and a sprite may declare **animations**
  (`{name: {frames, fps, loop}}`).
- **layer kinds** — `tilemap` (several allowed; one may be `fg: true` to draw over sprites),
  `sprite` (`name`/`anchor`/`frame`/`anim`/`data`, optional `angle` in degrees — applied to
  the native `sprite.angle`), `group` (many instances of one bitmap, addressable by `tag`),
  `particles`, `hudlabel` (camera-independent). Any layer may set `"fixed": true`.
- **the tilemap grid, two interchangeable ways** — `"grid"`: a rectangular 2-D array of tile
  indices (what the editor exports; row lengths and the declared `cols`/`rows` must agree).
  Or `"legend"` + `"rows"`: a `{char: tile index}` map plus one string per row — the same map as
  an ASCII picture. The baker accepts either and produces identical output, so pick by who edits
  it: `grid` for the editor, `rows` for anything a human reads in a diff or an agent edits by hand
  (a wall is visibly a column of `#`, and "three tiles too far left" is visible instead of
  described). The editor writes either — `Export ▾` has an **ASCII map** checkbox. A legend value
  may carry an orientation, so an oriented tile is simply its own character; a character missing
  from the legend bakes as tile 0 and is reported as an error.
- **tile orientations** — a tilemap grid value may carry the native per-tile orientation in
  bits 8–10: `value = tile | flipX<<8 | flipY<<9 | transpose<<10` (all 8 orientations —
  4 rotations × mirror — at zero RAM cost beyond a lazily-baked per-cell plane). Plain
  values stay plain; the baker emits the orientation plane only when a cell uses it.
- **zones / points** — named rectangles and positions the game queries at runtime
  (`view.in_zone`, `view.point`). Both may attach a free-form `data` object (e.g. imported
  Tiled custom properties): a zone tuple then carries it at index 5, point data is read
  from `view.pdata[name]`.
- **camera** is advisory data the game applies via `set_view`; games can drive the camera
  themselves.
- **meta** is free for the editor; the runtime loader ignores unknown keys (forward-compat).

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

### Two top-level shapes

- `"format": "picogame-scene"` — one self-contained scene (assets inline) → baked to one
  `<name>_scene` module.
- `"format": "picogame-project"` — an assets **bank** + `levels[]` → baked to one `_bank`
  module plus one `_level` module per level; load with
  `bank = picogame_scene.load_bank(pg, BANK)` then `load(..., bank=bank)` so shared art isn't
  rebuilt per level.

### Validation

The baker fails fast with a `ValueError` naming the offender on an unknown asset type or an
unknown layer kind; asset conversion errors (missing file, bad PNG) surface as the underlying
exception with the file in the message. The loader tolerates unknown *top-level* keys (so an
older firmware can load a newer scene's data it doesn't use), but layer tuples are positional —
a module baked by a newer `scene_build.py` needs the matching `picogame_scene` version.

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

Why not JSON on the device? `json.load` of a tilemap builds a Python list of boxed ints
(~28 B each): a 28×18 map ≈ 14 KB for the list alone, plus the JSON text. The same grid as a
`bytes` literal in a `.mpy` is ~500 B and one allocation.

## Runtime loader API

```python
import picogame_scene as pgs, terminalio
view = pgs.load(pg, world1_scene.SCENE, font=terminalio.FONT)
view.scene                  # the picogame.Scene (already populated + layered)
view.named["player"]        # the Sprite
view.group("enemies")       # list of Sprites
view.tick(dt)               # advance auto-animated sprites (once per frame)
view.is_solid(tx, ty)       # tile-property query (primary/first tilemap)
view.tile_has(tx, ty, "coin")
view.tile_xy(px, py)        # world pixel -> (tx, ty) on the primary tilemap
view.in_zone(x, y, "door")  # first zone containing (x, y), or None
view.point("spawn")         # named point (x, y), or None
view.play("jump")           # play a loaded sound by id
view.camera                 # (mode, target, axis, bounds) for the game to apply
```

See [Building scenes](/helpers/building-scenes/) for the complete loader behaviour and limits.
