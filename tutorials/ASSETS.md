# Real art in the tutorials (and your own)

Each tutorial ships a **`bonus_art.py`** — the finished capstone game re-skinned with
real, free **CC0** pixel art. They prove the engine's core idea: **art is orthogonal to
code.** Diff a `bonus_art.py` against its `step8`/`step9` and almost nothing changed but
the bitmaps.

| Tutorial | bonus uses | from (CC0) |
|----------|-----------|------------|
| 01-bounce | brick wall = a CC0 brick texture **recoloured** into the 4 row colours (ball/paddle stay generated) | Kenney **Tiny Dungeon** |
| 02-starship | ship (pre-rotated 16 frames) + laser bullet | Kenney **Pixel Shmup** |
| 03-quest | tileset (floor/lava/barrel/brick/door/chest) + hero + slime + coin | Kenney **Tiny Dungeon** |

Run one:
```
python3 sim/run.py tutorials/03-quest/bonus_art.py --shot /tmp/out.png
```

## The pipeline: any PNG → a picogame sprite

`tools/png2picogame.py` turns a PNG into a tiny Python module exposing `bitmap(pg)`:
```
python3 tools/png2picogame.py hero.png -o hero_art.py --frames 8
```
then in a game:
```python
import hero_art
hero = pg.Sprite(hero_art.bitmap(pg), x, y)        # drop-in replacement for any shp.*()
```
Options:
- `--frames N` — the PNG is a **horizontal strip** of N equal-width frames (left→right).
- `--tile WxH` — the PNG is a **grid** of W×H tiles; repacks them into a horizontal atlas
  (use for grid sheets; output frame count = number of tiles).
- format is auto (PAL8 if ≤256 colours, else RGB565); transparency comes from the PNG's
  **alpha** (alpha ≥128 = opaque); colours are emitted in ST7789 wire order.

## Layout rules (so it just works)
- **Horizontal strip**, equal-width frames. (Grids: use `--tile WxH`, or in Aseprite export
  `Sheet Type: Horizontal`, Trim OFF.)
- **Transparency = the alpha channel** (one on/off key, no blending). Hard pixel edges; avoid
  soft/anti-aliased alpha — it quantises badly.
- **Tilesets:** the engine draws tile value `v` as frame `v`, so make **frame 0 empty/
  transparent** and put your tiles at 1, 2, 3… (that's how `bonus_art` maps map values to
  real tiles).
- **Rotation:** for constant spin, bake rotations into frames (crisper + cheaper than runtime `sprite.angle`). The Starship ship is the
  Kenney sprite rotated into 16 frames offline (see how `tools/`-side scripts build the strip),
  then `ship.frame = angle`.

## Using your own Aseprite art
`File → Export Sprite Sheet → Sheet Type: Horizontal`, **Trim OFF**, Padding 0 → that's
exactly the strip `png2picogame` wants. Design in **Indexed** mode with a small palette (or
RGBA with a transparent background). Animation **Frame Tags** can drive frame ranges.

## Where to get more (free)
- **kenney.nl** — everything CC0, no attribution. (We used Pixel Shmup + Tiny Dungeon.)
- Recolouring CC0 art is allowed and often the quickest fix: the Bounce bricks are one grey
  Tiny Dungeon tile multiplied into 4 colours — texture of real art, palette you want.
- **itch.io** (CC0 filter), **OpenGameArt** (filter CC0). Avoid CC-BY-SA / GPL art.
- See the project memory note "picogame art sources" for the full rundown.

## Licensing / credits
All bundled art is **CC0** (public domain, no attribution required). The source PNGs we used
live in `assets/kenney/` with `assets/kenney/CREDITS.txt`. Even for CC0 it's good manners to
keep a credits note when you publish a game.
