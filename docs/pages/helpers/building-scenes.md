---
title: "Building scenes"
description: "Guide to the picogame scene-building helpers: load baked scenes, flag tiles, bake placeholder art, and pool sprites."
---

These four modules load baked scenes, attach properties to tiles, create simple bitmap art in code, and reuse a fixed set of sprites. See [/reference/](/reference/) for the signatures.

## picogame_scene

The loader turns a baked `SCENE` dictionary into a `pg.Scene` and a set of named handles. Use it for a level produced by the editor or `scene_build.py`. The same data and loader run on hardware and in the simulator. See [/scene-format/](/scene-format/) for the input format.

`load(pg, scene, display=None, strip_h=None, font=None, bank=None)` returns a `View`. It resolves the display in the same way as `picogame_game.setup()`, constructs the scene, and adds each tilemap, sprite, group, particle system, and HUD label. On an SPI display it allocates two `width * strip_h * 2` render buffers, available as `view.bufA` and `view.bufB`. On a framebuffer target both are `None`. Pass a font such as `terminalio.FONT` if the data contains a HUD label. See [/hardware/](/hardware/) for display backends and [/memory/](/memory/) for buffer costs.

`load_bank(pg, bank)` builds shared bitmaps/sounds/anims ONCE; pass the result as `load(..., bank=...)` for each level so unchanged art is not rebuilt per level.

**Tile properties come with the scene.** Do not reach for `picogame_tiles` after loading a scene — the `View` already answers per-tile questions: `view.is_solid(tx, ty)`, and `view.tile_has(tx, ty, "name")` for any other flag. The name is whatever the editor painted, so it is not limited to the four the editor offers by default: add a `glass` flag in the editor and the game reads it as `view.tile_has(tx, ty, "glass")`. Falling back to a bitfield here means re-deriving data the loader already holds.

**`view.camera` is data, not behaviour.** The loader hands you `(mode, target, axis, x, y, w, h)` and the game applies it — nothing follows the player on its own. `axis` is `"x"`, `"y"` or `"xy"`; honour it when you call `scene.set_view()`, or a level authored to scroll vertically silently will not.

The returned `View` is your handle to everything:

- `view.scene` - the live `pg.Scene`. Call `view.scene.refresh()` each frame and `view.scene.set_view(ox, oy)` to scroll.
- `view.named[name]` - dict of name -> sprite / particles / HUD label for any layer given a `name`.
- `view.group(tag)` - list of sprites for a group layer (returns `[]` if the tag is unknown, so it is safe to iterate).
- `view.tick(dt)` - advance all auto-animated sprites; call once per frame with `dt` in seconds.
- `view.tile_xy(px, py)` - world pixel -> `(tx, ty)` cell of the primary (first) tilemap.
- `view.is_solid(tx, ty)` - shorthand for `tile_has(tx, ty, "solid")`.
- `view.tile_has(tx, ty, prop)` - True if the primary tilemap's tile at that cell has the named property (from the baked `tileprops`).
- `view.point(name)` - `(x, y)` for a named point, or None.
- `view.in_zone(x, y, tag=None)` - first zone `(tag, x, y, w, h)` containing the point (optionally filtered by tag), else None.
- `view.play(sound_id)` - play a baked sfx by id (no-op if audio/sample is missing).
- `view.tilemap` / `view.camera` / `view.zones` / `view.points` / `view.anims` - the primary tilemap object, the camera tuple, and the raw collections.

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

:::note[Gotchas]
the first tilemap layer is the primary one; `tile_xy`, `is_solid`, and `tile_has` query only that map. `view.named` contains only layers with a name. Sound loading is best-effort: a missing audio module or sample produces a `None` entry, and `play()` then does nothing.
:::

## picogame_tiles

`TileFlags` stores one metadata bitfield for each tile index, so every cell using that tile shares the same properties. Use it with a hand-built `pg.Tilemap`. A scene loaded through `picogame_scene` already exposes the higher-level `view.is_solid()` and `view.tile_has()` methods.

Eight named bits and their masks: `B_SOLID, B_HAZARD, B_LADDER, B_PLATFORM, B_WATER, B_COIN, B_EXIT, B_CUSTOM` are bit indices 0..7; `SOLID, HAZARD, LADDER, PLATFORM, WATER, COIN, EXIT, CUSTOM` are the matching `1 << bit` masks. Use the masks when building the table, the `B_*` indices when querying.

`TileFlags(flags=None, tile_px=8)` builds the table. `flags` is either a `{tile_index: bitfield}` dict or a list/bytes indexed by tile index; `tile_px` is the tile size used by the pixel helper.

- `tf.get(tile, bit=None)` - the full bitfield of a tile, or one bool flag if `bit` (a `B_*` index) is given.
- `tf.set(tile, bit, value=True)` - flag (or clear) a bit on a tile at runtime.
- `tf.at(tilemap, tx, ty, bit)` - flag `bit` of the tile at cell `(tx, ty)`.
- `tf.at_px(tilemap, px, py, bit)` - flag `bit` of the tile under MAP-LOCAL pixel `(px, py)`; the common collision probe.

```python
import picogame as pg
import picogame_tiles as tiles

TILE = 8
tf = tiles.TileFlags({1: tiles.SOLID, 2: tiles.COIN, 3: tiles.EXIT}, tile_px=TILE)

def blocked(level, tx, ty):                # level is a pg.Tilemap
    return tf.at(level, tx, ty, tiles.B_SOLID)

if tf.at_px(level, px, py, tiles.B_SOLID): # is the tile under pixel (px, py) solid?
    stop()
```

:::note[Gotchas]
`at_px` assumes the map is at screen `(0, 0)` - if it is moved, subtract the map origin from `px`/`py` yourself before calling. Tiles missing from the table read as `0` (no flags). Build with the MASK constants (`tiles.SOLID`) but query with the BIT indices (`tiles.B_SOLID`); mixing them up silently checks the wrong bit.
:::

## picogame_shapes

These functions build single-colour PAL8 `Bitmap` objects in code. They suit prototypes and geometric art such as balls, bricks, or ships. Unlike `Canvas`, they return a reusable bitmap for a `Sprite` or `Tilemap`. Palette index 0 is transparent and index 1 contains the requested colour.

- `rect(w, h, color)` - a filled `w x h` rectangle.
- `circle(d, color)` - a filled disc of diameter `d`.
- `ring(d, color, thickness=2)` - a circle outline of diameter `d`.
- `from_mask(mask, color)` - a bitmap from a list of strings; `#`, `X`, or `1` sets a pixel. Sized to the mask.
- `atlas(frames_data, w, h, color)` - pack a list of `w*h` 0/1 buffers into one horizontal multi-frame bitmap (one colour). The general "frame sheet" builder.
- `color_frames(w, h, colors)` - a multi-frame bitmap where frame `i` is a solid fill of `colors[i]`; frame 0 is already a colour. Index 0 transparent.
- `tileset_colors(w, h, colors)` - a tileset where frame 0 is EMPTY (transparent) and frame `i` is a solid fill of `colors[i-1]`. So a Tilemap reads tile value 0 as empty and 1..N as coloured tiles.
- `poly_frames(size, points, nframes, color, fill=True)` - bake `nframes` rotations of a polygon (points around centre, +y down) into a `size x size` atlas. The engine also rotates at runtime (`Sprite.angle`); baked frames trade a little RAM for a cheaper per-frame blit and pixel-stable art, so pick them for many always-rotating objects (asteroids), and `angle` for one-off or continuous rotation. Set `fill=False` for an outline.

```python
import picogame as pg
import picogame_shapes as shp

ball = shp.circle(4, pg.rgb565(255, 255, 120))
bricks = shp.tileset_colors(16, 8, [pg.rgb565(220, 70, 70),
                                    pg.rgb565(80, 140, 240)])   # value 0 empty, 1..2 coloured
ship = shp.poly_frames(16, [(0, -8), (6, 7), (0, 4), (-6, 7)], 16,
                       pg.rgb565(200, 220, 255))                 # 16 pre-rotated frames
sprite = pg.Sprite(ball, 100, 60)
```

:::note[Gotchas]
`color_frames` frame 0 is a visible colour, but `tileset_colors` frame 0 is transparent (empty) - pick the one matching how your Tilemap treats value 0. `circle` fills its bitmap edge-to-edge, so it looks flat-topped when scaled up. `poly_frames` with `nframes=1` bakes a single un-rotated frame (use it for a fixed-direction shape).
:::

## picogame_pool

`Pool` pre-allocates a fixed number of sprites for short-lived objects such as bullets, enemies, or pickups. `sprite.visible` marks an occupied slot and `sprite.data` can hold entity state. Spawning and freeing slots allocate no new sprites. See [/memory/](/memory/) for why stable allocation matters on the device.

`Pool(scene, bitmap, capacity, anchor=None, fixed=False)` pre-allocates `capacity` hidden sprites sharing `bitmap`, sets each `anchor` (if given) and `data = None`, and adds them all to `scene` (`fixed=` passes through to `scene.add`).

- `pool.items` - the underlying list of sprites; iterate it directly for zero-alloc updates.
- `pool.spawn()` - make the first free (hidden) sprite visible and return it, or None if the pool is full.
- `pool.free(s)` - hide sprite `s` (return it to the pool).
- `pool.free_all()` - hide every sprite (use on level reset).
- `pool.count()` - count of live (visible) sprites; cheap, but iterate `items` for the sprites themselves.

```python
import picogame as pg
import picogame_pool

bullets = picogame_pool.Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))

b = bullets.spawn()                        # a now-visible sprite, or None if full
if b:
    b.data = {"vx": 6}
    b.move(x, y)

for s in bullets.items:                    # zero-alloc iteration
    if not s.visible:
        continue
    s.move(s.x + s.data["vx"], s.y)
    if off_screen(s):
        bullets.free(s)
```

:::note[Gotchas]
always skip hidden slots when iterating (`if not s.visible: continue`) - `items` holds every slot, alive or not. `spawn()` returns the first free slot it finds (don't rely on any particular order), so if you `free(s)` and `spawn()` in the same step, read any state off `s.data` BEFORE freeing - the new spawn may overwrite it. A full pool returns None from `spawn()`; check for it. All sprites share one bitmap, so per-entity frame/animation must be set on each sprite after `spawn()`.
:::
