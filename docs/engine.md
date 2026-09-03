# picogame — 2D game engine for PicoPad (CircuitPython)

`picogame` is a retained-mode 2D game engine built as a CircuitPython C module.
It targets the Pajenicko PicoPad (RP2040, 320×240 ST7789) and similar boards. It is
a more complete successor to `_stage`: arbitrary-size sprites, a retained `Scene`
with dirty-region rendering, tilemaps, particles, drawing surfaces, and an optional
asynchronous DMA display backend.

- **Reference target:** the PicoPad firmware and SPI path are tested on hardware. Other targets
  have individual status notes in [Supported hardware](supported-hardware.md).
- **Performance:** on an SPI display, `Scene` transfers up to six changed regions separately.
  Localized motion can therefore cost less than a full repaint; scattered changes and camera
  movement can still approach a full-screen update.

---

## Contents
1. [Where this page fits](#where-this-page-fits)
2. [Quick start](#quick-start)
3. [API reference](#api-reference)
4. [Asset pipeline](#asset-pipeline)
5. [Engine costs & constraints](#engine-costs--constraints)
6. [Under the hood](#under-the-hood)
7. [Building the firmware](#building-the-firmware)
8. [Examples](#examples)

---

## Where this page fits

This is the **deep guide to the native `picogame` C module**: exact behaviour, contracts and
costs of the engine types. It assumes you know what you're looking for.

- New here? [Your first game](/start/first-game/), then [How picogame works](/concepts/how-it-works/).
- "Which layer/surface do I use?" → [Drawing paths](/concepts/drawing-paths/); task index in [FEATURES.md](features.md).
- Bare signatures of everything → [REFERENCE.md](reference.md).
- The pure-Python `picogame_*` helpers (input, timing, audio, UI, pools, save…) have their own
  guides under *Helpers* — this page covers the C module only. (Helpers keep the `picogame_*`
  file prefix, **not** a `picogame/` package: that name is the C module and can't be shadowed.)

**Two contracts everything relies on:** colours are always the display's **wire byte order** —
build them with `pg.rgb565(r, g, b)`; a naïve `0xRRGGBB` or host-endian RGB565 renders wrong
colours. Coordinates are top-left origin; render-call rectangles are **half-open**
(`x0,y0` inclusive to `x1,y1` exclusive), while `collide()` hitboxes are **inclusive**
(different domains: pixels vs hitboxes).

---

## Quick start

```python
import time, array
import board
import picogame as pg
import picogame_game

BG = pg.rgb565(20, 24, 40)
scene, _, _ = picogame_game.setup(background=BG)
W, H = picogame_game.screen()   # read the screen size from the board

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

## API reference

### Module `picogame`

| Name | Description |
|---|---|
| `RGB565` | format constant (16-bit color, wire order) |
| `PAL8` | format constant (8-bit palette index) |
| `rgb565(r, g, b) -> int` | build a wire-order RGB565 color from 8-bit components |
| `collide(x1, y1, x2, y2, ax1, ay1, ax2, ay2) -> bool` | AABB box↔box overlap; inclusive bounds, so boxes collide when they touch (pass sprite boxes as `(x, y, x+w, y+h)`; fires on contact). `collide` is inclusive, unlike render's half-open pixel ranges (different domains: hitboxes vs pixels) |
| `collide(x1, y1, x2, y2, px, py) -> bool` | box↔point (6 args) |
| `render(display, layers, buffer, x0, y0, x1, y1, *, background=0)` | immediate draw of a layer list (any scene-layer kind) to a compatible display target |
| `value2d(x, y, *, seed=0) -> float` | smooth 2-D value noise, 0..1 (fast C) |
| `value1d(x, *, seed=0) -> float` | smooth 1-D value noise, 0..1 |
| `fbm2d(x, y, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` | fractal (fBm) 2-D noise, 0..1 — terrain/clouds/caves |
| `fbm1d(x, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` | fractal (fBm) 1-D noise, 0..1 |

Noise is **fixed-point** (Q16.16) under the hood, fast on the RP2040 (no FPU) and meant for one-shot
terrain/cloud gen, not per-frame. There are no separate `_fx` exports; `value2d`/`value1d`/`fbm2d`/`fbm1d`
are the canonical functions, called directly on the `picogame` module (`pg.value2d`, `pg.fbm2d`, …);
the simulator provides a matching Python implementation.

### Conditional / build-flag API

Presence depends on the firmware build. Do NOT feature-test the TYPES with `hasattr` — a build without the backend still exposes `Display`/`Framebuffer` as stubs whose constructor raises, so `hasattr` is always True. Test the module booleans instead: `pg.FAST_DISPLAY_SUPPORTED` and `pg.FRAMEBUFFER_SUPPORTED`:

| Name | Present when | Purpose |
|---|---|---|
| `Display` | `pg.FAST_DISPLAY_SUPPORTED` (RP2/ESP builds) | async-DMA render backend; on other builds the type exists but constructing it raises (pass the plain busdisplay to `Scene` instead) |
| `Framebuffer` | `pg.FRAMEBUFFER_SUPPORTED` (scanout-buffer platforms, e.g. the WASM playground) | RAM render target instead of a panel; the type itself exists everywhere |
| `RGB444_SUPPORTED` | always (bool) | whether this board's panel can drive 12-bit RGB444 |
| `STRIP_H` | always (int) | the board's default render-strip height (`picogame_game.setup` uses it) |
| `API_LEVEL` | newer firmware (use `getattr(pg, "API_LEVEL", 0)`) | engine API generation, for up-front version checks |

### `Bitmap(data, width, height, *, format=RGB565, palette=None, frames=1, stride=0, transparent=None)`
An image atlas of one or more equal-size frames, **any** width/height.
- `data` — readable buffer: `PAL8` = 1 byte/pixel index; `RGB565` = 2 bytes/pixel (LE wire).
- `palette` — for `PAL8`, a buffer of wire-order RGB565 entries (e.g. `array("H", [...])`).
- `frames` — animation frames laid out **horizontally**; frame `f` is at column `f*width`.
- `stride` — atlas width in pixels (default `width*frames`).
- `transparent` — palette index (`PAL8`) or wire color (`RGB565`) to skip; `None` = opaque.
- Read-only properties: `width`, `height`, `frames`, `format`, `stride`, `palette` (the PAL8 palette buffer or `None`), `transparent` (the transparent value or `None`).

### `Sprite(bitmap, x=0, y=0, *, frame=0, visible=True, flip_x=False, flip_y=False)`
A positioned, animatable instance of a `Bitmap`.
- Properties: `x`, `y` (integer pixel; setter also accepts a float), `fx`, `fy`
  (sub-pixel float position), `frame`, `visible`, `flip_x`, `flip_y`, `transpose`,
  `data`, `bitmap`, `scale`, `angle`, `shadow`, `flash`, `tint`, `dither`.
- `move(x, y)` — set position (accepts int or float).
- `overlaps(other, inset=0) -> bool` / `near(other, r) -> bool` — native collision
  tests (anchor/scale/rotation aware, zero-allocation). `overlaps` is an inclusive
  AABB box test (`other` = a `Sprite`, an `(x, y)` point, or an `(x1, y1, x2, y2)`
  rect); `inset` shrinks **this** sprite's box by N px for a fairer hitbox. `near`
  is a circular test (centres within `r`, no sqrt; `other` = `Sprite` or point).
- `scale` — uniform draw scale (float, nearest-neighbour). `1.0` = native (fast 1:1
  path); `2.0` = double size; fractional allowed (e.g. a coin pulsing `1.0..1.3`, a
  powerup growing). Scales about the `anchor`.
- `angle` — rotation in **degrees** about the anchor (float). `0` = none (fast path);
  any other value uses the affine (inverse-mapped) blit. Integer scales stay crisp;
  rotation shimmers slightly (pixel-art trade-off). `scale` + `angle` compose.
- `shadow` — when `True`, the sprite's opaque pixels **darken** the destination
  instead of drawing their color (drop shadows: an offset silhouette below the
  sprite; or a dim/vignette overlay). Combine with `scale`/`angle` freely.
- Blit effects `flash`, `tint`, `dither` — cheap per-pixel recolour/translucency,
  one at a time (setting one clears the others; `0` = off), no extra art or RAM.
  `flash = WHITE` paints opaque pixels a flat colour (a 1–3-frame hit blink);
  `tint = RED` multiplies the colour, **keeping** shading (lighting/damage/freeze;
  it can only darken); `dither = 0..16` is a Bayer stipple (ghost/fog/fade, no
  alpha; animate the level to fade in/out).
- `transpose` — when `True`, swaps the X/Y axes (a diagonal mirror); combined with
  `flip_x`/`flip_y` it gives all **8** orientations as a crisp fast-path blit
  (scale 1, angle 0). The footprint swaps width/height.
- `bitmap` — read/write the source `Bitmap`. Assigning a new one swaps graphics
  at runtime and may change size (powerups, resizable HUD bars, text labels); the
  scene repaints both the old and new bounds on the next `refresh`.
- `touch()` — mark the sprite dirty after an **in-place** `bitmap`/palette edit (e.g. a `picogame_palette` recolour), so the change repaints on the next `refresh`.
- `anchor` — pivot as `(fx, fy)` fractions of the bitmap size: `(0, 0)` top-left
  (default), `(0.5, 0.5)` center, `(0.5, 1.0)` bottom-center. `x`/`y` then refer to
  this point, so growing/shrinking via a `bitmap` swap stays aligned around the
  pivot. The dirty-rect tracks the resulting top-left.
- Use `fx`/`fy` for smooth physics
  (`ball.fx += 2.4`) instead of a parallel Python float + `int(round())`; `x`/`y`
  return the floored pixel for tile/collision math. Dirty-rect triggers only when
  the pixel changes (sub-pixel jitter under 1 px is free).
- `data` — an arbitrary user payload (any object) for per-sprite game state, so
  you don't need a parallel wrapper class: `hero.data = {"vy": 0, "dead": False}`.

### `Display(busdisplay, *, rgb444=False)`
Fast async-DMA backend wrapping an existing `busdisplay.BusDisplay` (e.g.
`board.DISPLAY`). Reuses its SPI bus, pins, window commands and dimensions.
- `rgb444=True` drives the panel in 12-bit RGB444 instead of 16-bit RGB565:
  ~25 % less SPI traffic (3 bytes per 2 pixels) at the cost of colour depth.
- `render(sprites, buffer_a, buffer_b, x0, y0, x1, y1, *, background=0)` — draw a
  sprite list into the region with double-buffered DMA.
- `picogame.invert(display, on)` — toggle the panel's hardware colour inversion. Changes the panel's inversion state without sending pixel data, so a brief invert makes a full-screen negative flash (a 1-bit "hit" look) with no buffer and no redraw. Wrapped by `picogame_fx.InvertFlash`.

### `Scene(display, buffer_a, buffer_b, *, background=0, top=0, bottom=0, left=0, right=0)`
Retained-mode scene with dirty-rectangle rendering. `display` is a `picogame.Display`
(the fast backend) **or** a plain `busdisplay.BusDisplay` (the portable path).
- `add(item, *, fixed=False) -> item` — add a `Sprite`/`Tilemap`/`Particles`/`Canvas`/`StripDraw`
  and return it (so `spr = scene.add(Sprite(...))` works). Insertion
  order is **bottom-to-top**. `fixed=True` (keyword-only) pins the item to the screen (ignores the
  view offset); use it for HUD / score / dialog that must stay put while the world
  scrolls via `set_view`.
  (add tilemap backgrounds first, sprites after, foreground tilemaps last).
- `add_all(items)` — add several items at once (same bottom-to-top order).
- `refresh() -> [x1, y1, x2, y2] | None` — diff vs. the previous frame and repaint
  only the changed region; returns the bounding dirty rect as a REUSED list (read it
  immediately - the next call overwrites it), or `None` if nothing changed.
  The first refresh repaints the whole screen (covers leftover console pixels).
- `invalidate()` — force a full-screen repaint on the next refresh (e.g. on level change).
- `set_view(ox, oy)` — view offset = screen position of the scene origin. Set a
  constant offset to centre a small game (e.g. a 128×128 game on 320×240); update
  it each frame to scroll a larger world (scrolling repaints the whole screen).
  Sprites/tilemaps then live in plain scene coordinates regardless of placement.
- `view` — read-only `(ox, oy)` current view offset.
- `display` — read-only: the render backend this scene draws through (the `pg.Display`
  wrapper where enabled, else the plain busdisplay). `pg.render()`/`pg.invert()` accept
  either form, so `pg.render(scene.display, ...)` always works.

### `Tilemap(tileset, cols, rows)`
A grid of tile indices into `tileset` (a `Bitmap` whose frames are the tiles).
- `get_tile(tx, ty) -> int` — read a tile.
- `set_tile(tx, ty, value, *, flip_x=False, flip_y=False, transpose=False)` — write one (marks dirty); the orientation flags are keyword-only.
- `move(x, y)` — move the whole map (pixel position of tile 0,0).
- `fill(value)` — set every tile.
- Out-of-range `get_tile()` reads as `0` and `set_tile()` ignores the write (no exception).
- Read-only properties: `x`, `y`, `cols`, `rows`.
- **Index 0 is a tile like any other** (frame 0 of the tileset) — there is no implicit empty tile. A cell whose index is `>= tileset.frames` draws nothing, so an out-of-range value (e.g. `255`) is the "empty" cell; a see-through tile is a frame that uses the tileset's `transparent` colour. Indices are bytes (`value & 0xff`).

**Breaking change:** these two replaced `tile(tx, ty[, value])` (firmware after 2026-08-23) — old
code raises `AttributeError`. The **firmware** is what must be new enough.

### `Canvas(width, height, *, transparent=None, buffer=None)`
A RAM drawing surface composited as a Scene layer — the general home for shapes.
Add it to a `Scene`; draw into it; only redrawn areas repaint. Colors are wire-order.
Pass an existing `buffer` (a `width*height*2`-byte writable buffer) to back the
surface with your own RAM instead of letting the Canvas allocate one.
- Primitives (all take wire colors): `clear(color)`, `pixel(x, y, color)`,
  `fill_rect(x,y,w,h,color)`, `rect(x,y,w,h,color)`, `line(x0,y0,x1,y1,color)`,
  `circle(cx,cy,r,color)`, `fill_circle(cx,cy,r,color)`, `ring(cx,cy,r,thickness,color)`,
  `triangle(x0,y0,x1,y1,x2,y2,color)`, `fill_triangle(...)`,
  `ellipse(cx,cy,rx,ry,color)`, `fill_ellipse(...)`, `fill_round_rect(x,y,w,h,r,color)`,
  `frame3d(x,y,w,h,light,dark)` (bevelled box: light top/left, dark bottom/right),
  `text(x, y, s, fg, font, bg=None)` (composite font glyphs in C; `bg=None` =
  transparent, and also works in a `StripDraw` view without a retained text bitmap),
  `move(x, y)`.
- `blit(bitmap, x, y, frame=0, flip_x=False, flip_y=False)` — stamp a bitmap frame into the surface (honours its transparent key): the retained way to bake an icon/portrait/rendered text into a panel.
- Read-only properties: `x`, `y`, `width`, `height`.
- `transparent` (a wire color) lets the surface be a shaped overlay (HUD bar,
  gauge, vector art) over other layers. Costs `width*height*2` bytes of RAM, so
  size it to what you need (e.g. a 320×16 status bar = ~10 KB).
- **RAM warning:** a full-screen `Canvas(320, 240)` is **150 KB**, too big for the
  RP2040 (~190 KB heap, ~130 KB contiguous). Keep Canvases small, or use a `Tilemap` for large scrolling
  fields. See [the hardware notes](hardware.md). For a *full-frame animated* surface, consider
  `StripDraw` below; it does not retain a pixel surface.

### `StripDraw(callback, x=0, y=0, width=0, height=0, *, always_dirty=True)`
An **immediate-mode** draw layer with **no pixel buffer at all**. Added to a `Scene`
like any layer, but instead of retaining pixels it calls your `callback` once per
render strip that overlaps its rect:

```python
def draw(view, vx, vy, vw, vh):
    # `view` is a Canvas pointing straight at the live strip. Its local (0,0) is screen
    # pixel (vx, vy). CAREFUL: (vw, vh) is the RENDER REGION's size, not the layer's -
    # the rect only limits which strips (rows) fire the callback, NOT the width you can
    # paint. So `view.clear()` / a full-view fill on a narrow layer paints the whole
    # screen width; draw your own rectangle with fill_rect(0, ly, MY_W, 1, ...) instead.
    for ly in range(vh):
        Y = vy + ly                                  # screen row
        view.fill_rect(0, ly, vw, 1, sky_or_road(Y))

scene.add(pg.StripDraw(draw, 0, 0, 320, 240))
```

- **RAM:** the layer retains no `width*height*2` pixel surface. A full-screen pseudo-3D
  road therefore avoids the **150 KB** pixel buffer required by a full-screen `Canvas`;
  the `StripDraw` object, callback, and game state still use memory.
- With the default `always_dirty=True` its rect is **repainted every frame** (no
  dirty-rect skip), so use it for *animated* content: pseudo-3D roads, gradient
  skies, raycasters, plasma, procedural backgrounds, or shapes that change each
  frame. For *static* art that mostly sits still, a `Canvas` is cheaper CPU (it
  repaints only when changed); pick by motion, not by size.
- `always_dirty=False` makes it an **on-demand** layer: it repaints only when you
  call `.invalidate()` (otherwise the dirty-rect skips it, like a Canvas), a
  buffer-less in-scene panel with no retained pixel surface that repaints only on change. This
  is how `picogame_ui.SceneBox`/`SceneMenu` draw their panels.
- **Keep the inner loop light:** the callback issues C primitives, so a handful of
  `fill_rect`/`hline`-style calls per strip is cheap; avoid heavy per-pixel Python.
- Read/write properties `x`, `y`, `width`, `height` move or resize the layer at runtime;
  after shrinking it, call `scene.invalidate()` so the vacated area repaints.
- Drawn in **screen space** (it ignores the camera/view offset). In a **scrolling** scene
  (one that calls `set_view`) add it **fixed** (`scene.add(sd, fixed=True)`) so its dirty rect
  matches where it draws; in a static-camera scene it doesn't matter. Inside the callback,
  map a screen point to the strip via `(screen_x - vx, screen_y - vy)`. Composites over lower
  layers and under higher ones, like any layer. See `examples/picogame_stripdraw_example.py`, and
  `examples/journey_hw/journey_mono.py` (racer road, intro shapes, RPG dialog box).

### `Particles(capacity, *, size=1, gravity=0.0, fade=False)`
A pooled particle layer (many small moving dots) drawn as a single Scene layer,
far cheaper than one `Sprite` per particle. Add it to a `Scene`. With `fade=True`
each particle dims toward black over its life (sparks/embers/smoke look).
- `emit(x, y, count, speed=1, life=30, color=0xFFFF)` — spawn `count` particles at
  (x, y) with random velocity up to `speed` px/tick, living `life` ticks, in a
  wire-order color (use `picogame.rgb565`).
- `tick()` — advance one step (move, gravity, ageing); call once per frame.
- `clear()` — remove all particles.
- Positions are sub-pixel (fixed-point); the layer repaints only where particles
  are (and were), so they leave no trails. v1 draws solid `size`×`size` dots.

---

## Asset pipeline

`tools/png2picogame.py` (host-side, needs Pillow) converts PNG/BMP into importable
asset modules whose colors are already in wire order.

```bash
# A sprite / horizontal animation atlas (auto picks PAL8 or RGB565):
python3 tools/png2picogame.py hero.png -o hero.py --frames 6

# A vertical / grid tile sheet -> horizontal atlas Bitmap (16x16 tiles):
python3 tools/png2picogame.py tiles.bmp -o tiles.py --tile 16x16 --transparent-index 15

# A tilemap (image palette indices ARE tile indices) -> Tilemap data module:
python3 tools/png2picogame.py level.bmp -o level.py --map
```

On the device:
```python
import hero, tiles, level
spr = pg.Sprite(hero.bitmap(pg), 40, 120)
tileset = tiles.bitmap(pg)
tm = pg.Tilemap(tileset, level.WIDTH, level.HEIGHT)
level.fill(tm)          # load the map data
```

Options: `--format auto|pal8|rgb565`, `--frames N`, `--tile WxH`, `--map`,
`--transparent-index N` (treat a P-mode palette index as transparent), `--rle` (RLE-compress a
single-frame PAL8 background).

Size-saving options (PAL8):
- `--dither` (+ `--colors N`, default 255): Floyd–Steinberg dither when reducing to PAL8; hides
  gradient banding (skies, lighting). A low `--colors` (e.g. 16–32) + `--dither` = a retro look.
- `--dedup` (with `--tile WxH`) — fold tiles that are identical **up to orientation** (all 8: 4
  rotations × mirror) into a smaller tileset → less tileset RAM. Emits a `REMAP` table; rebuild your
  map with `v, fx, fy, tp = REMAP[old_index]; tm.set_tile(x, y, v, flip_x=fx, flip_y=fy, transpose=tp)`
  (it carries the per-tile flip/transpose; the orientation flags are keyword-only). Typical
  hand-drawn levels are 40–70 % duplicate. Pairs with the Tilemap per-cell orientation.

---

## Engine costs & constraints

> For deployment, read [Run on hardware](hardware.md) (`.mpy`, firmware, and device testing)
> and [Fit it in RAM](memory.md) (costs and measurement).

- **Plan retained surfaces against the measured heap.** A full-screen `Canvas(320,240)` is
  150 KB and exceeds the largest contiguous block in the current RP2040 PicoPad build. Keep
  Canvases small, use a `Tilemap` for big fields and a
  `StripDraw` for animated full-frame content. Costs and the decision matrix:
  [Drawing paths](/concepts/drawing-paths/) + [MEMORY.md](memory.md).
- **Dirty-region rendering reduces SPI traffic for localized motion.** A full-screen repaint
  still pays both composition and transfer costs; which dominates depends on the scene,
  firmware, and SPI clock.
- **Up to six dirty regions:** overlapping changes are combined first. If more than six
  regions remain, `Scene` merges the pair that adds the least extra area until six are left.
  Localized motion stays cheap; changes scattered across the screen can still approach a full
  redraw. `refresh()` returns their bounding union for diagnostics, although the renderer
  processes the regions separately.
- **Native types (`Sprite`, `Bitmap`, …) can't hold custom attributes** - use `sprite.data`
  for per-entity state.
- **PAL8 uses half the pixel storage of RGB565** (1 B/px vs 2). For larger assets, also
  consider frozen data, ROMFS, or streaming; see
  [Where assets live](memory.md).

---

## Under the hood

How a `refresh()` or `render()` reaches the output:

- **SPI targets render in horizontal strips.** The engine reuses one or two small buffers;
  for each strip it clears the background, composites overlapping layers, and sends the result.
- **Framebuffer targets composite into the scanout buffer.** They do not allocate the SPI
  strip buffers. A large dirty region still means more pixels to composite, but there is no
  SPI transfer step.
- **Fast SPI path (`pg.Display`)**: two strip buffers + asynchronous DMA - the CPU composites
  the next strip while the previous one is still on the SPI bus. **Portable path** (plain
  busdisplay): one buffer and blocking `bus.send`.
- **Strip height** comes from the buffer size you allocate (`buffer_len / (width*2)`).
  Smaller strips give finer CPU/transfer overlap on the DMA path; larger strips mean fewer
  blocking sends on the portable path - which is why the board default `STRIP_H` differs
  (8 with DMA, 24 without).
- **Dirty tracking** diffs each layer against a per-item snapshot (position, frame, scale,
  angle, effects, a `seq` bumped by `touch()`); Canvas/Tilemap/Particles accumulate their own
  dirty rects internally and hand them over on refresh.
- **Rotation/scaling** is a fixed-point inverse-mapped blit (no floats in the hot path); the
  per-sprite transform (bbox + inverse-map steps) is cached and recomputed only when
  angle/scale/bitmap/anchor change.

---

## Building the firmware

The engine is a native module inside a CircuitPython fork; building it is its own guide -
see **[The firmware build](firmware.md)** (toolchain, board configs, flags). Prebuilt
firmware for supported boards: [Supported hardware](supported-hardware.md).

---

## Examples

In the project root (copy to `CIRCUITPY/code.py`):

| File | Shows |
|---|---|
| `examples/picogame_scene_example.py` | retained Scene + dirty-rect (static field + movers) |
| `examples/picogame_hud_example.py` | HUD text via the bundled font (`picogame_font.py`) |
| `examples/picogame_tilemap_example.py` | tilemap background + sprite over it |
| `examples/picogame_scroll_example.py` | camera/scrolling: a bigger world with the view following the player (`scene.set_view`) |
| `examples/picogame_particles_example.py` | particle layer bursts with gravity (`pg.Particles`; see also `picogame_particles_fade_example.py`) |
| `examples/picogame_stripdraw_example.py` | 0-RAM full-frame drawing via `StripDraw` |
| `examples/picogame_canvas_example.py` | retained Canvas panel |
| `demos/picogame_arkanoid.py` | a full Breakout/Arkanoid game: Tilemap bricks + sprites + collide + particles + HUD |
| `games/squest/code.py` | a Seaquest-style shooter: pooled sprites via `sprite.data`, projectiles + collide + particles, O2 HUD gauge, tone audio |
### Project layout

```text
lib/        engine Python helpers (picogame_*)  -> copy needed ones to CIRCUITPY/lib/
examples/   games, demos, per-game assets       -> a game becomes code.py at the root
tools/      asset converters (png2picogame, ...)
```

Deploying a game to the device (helpers, `.mpy`, assets) is covered by
[Run on hardware](hardware.md).
