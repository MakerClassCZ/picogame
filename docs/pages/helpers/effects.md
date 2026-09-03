---
title: "Effects & feedback"
description: "Screen shake, fades, tweens, cameras, raster effects, particles, and PAL8 palette changes."
---

These effects add visual feedback and movement without full-screen surfaces. Their memory costs differ: `Fade` draws through a `StripDraw` callback, `Sky` keeps a colour lookup table, `Scanlines` keeps one bitmap row, and palette helpers modify existing PAL8 palettes. See [/reference/](/reference/) for the signatures.

Reaching for feedback on a game event? This table routes you to the right effect; the sections below have the details.

| Event | Reach for |
|---|---|
| Small hit / took damage | sprite `flash` (1-3 frames) + a small `Shake` (`add(0.6)`) |
| Enemy killed / big impact | `Particles` burst + a bigger `Shake` (`add(0.8)`-`add(1.0)`) + [hit-stop](#hit-stop-frame-freeze) |
| Pickup / score pop | a `Tween` pop (the blip is on the [audio page](/helpers/audio/)) |
| Screen / scene change | `Fade` |
| Menu / UI motion | `Tween` |

## picogame_fx

Create these helpers for a `Scene` and update the time-based ones once per game frame. `Shake` and `InvertFlash` emphasize an impact, `Fade` handles transitions, `Tween` smooths a changing value, `Camera` follows the world, and `Sky` or `Scanlines` draw raster-style backgrounds and overlays.

`import picogame_fx as fx`

### `fx.Shake` - decaying screen shake

![Screen shake - a kick that decays](/img/fx_shake.gif)

`Shake` stores an intensity called trauma. Calling `add()` raises it; each `tick()` applies a random offset and reduces the stored value. Pass the normal camera offset to `tick()` so both effects use one `scene.set_view()` call.

- `Shake(scene, max_offset=6, decay=0.03, seed=0x9E37)` - `max_offset` is the peak pixel offset (about 6 suits 320x240; over 10 hides the action). `decay` is trauma lost per frame (about 0.03 reads as a "kick", not a "rumble").
- `.add(amount)` - add trauma in the 0..1 range, clamped to 1.0. Use 0.6 for a small kick, 0.8 for a hit or explosion, 1.0 for a big impact. Trauma is squared before use, so small events barely shake and big ones slam - and below about 0.5 the offset is under one pixel at `max_offset=6` (0.4 gives 0.96 px), so such a shake is invisible and only costs the full repaints.
- `.tick(cam_x=0, cam_y=0)` - adds a decaying random offset on top of `(cam_x, cam_y)` and calls `scene.set_view` with the sum. Returns `True` while still shaking. Pass your camera offset here so shake and a moving camera don't both call `set_view` and stomp each other.

```python
import picogame_fx as fx

shaker = fx.Shake(scene, max_offset=6)
# ...on impact:
shaker.add(0.8)
# ...every frame (no camera, so feed 0,0):
shaker.tick(0, 0)
```

:::note[Gotchas]
`Shake` owns `scene.set_view` while it runs - if you also move a camera by hand, feed that offset into `tick(cam_x, cam_y)` rather than calling `set_view` separately. See [/hardware/](/hardware/) for the screen size you are tuning `max_offset` against.
:::

### Hit-stop (frame freeze)

Freeze-framing on a big impact is a common juice technique, but there is **no engine primitive** for it - you skip N logic / `scene.refresh()` ticks yourself. Hold a `freeze` counter and, while it is positive, decrement and `continue` the loop (still calling `clock.tick()` so timing stays steady).

```python
freeze = 0
# ...on a big impact:
freeze = 4
# ...at the top of the game loop:
if freeze > 0:
    freeze -= 1
    clock.tick()
    continue
```

### `fx.Fade` - dither screen fade / dim / flash

![A dither fade to black and back](/img/fx_fade.gif)

A `StripDraw` overlay stipples a colour over a rectangle with ordered Bayer dithering. It keeps no pixel surface. At level 0 its drawing rectangle collapses to 0×0, so it adds no region to repaint.

- `Fade(scene, width, height, x=0, y=0, color=0, cell=8)` - covers the rect `(x, y, width, height)`; defaults cover the whole screen. A sub-rect dims just that area (a panel behind a dialog, a sidebar). `color=0` is black; `cell` is the dither block size. Added to the scene `fixed=True` so it ignores the camera.
- `.set(level)` - jump instantly to `level` (0 = clear .. 16 = solid). Use 16 to start opaque before a fade-in.
- `.to(target, speed=2.0)` - head toward `target` at `speed` levels per frame. Returns `self`.
- `.out(speed=2.0)` / `.into(speed=2.0)` - shortcuts for `to(16)` (to opaque) and `to(0)` (to clear).
- `.dim(level=8)` - jump to a partial hold, e.g. a 50% dim behind a menu. `.clear()` jumps to 0.
- `.pulse(level=12, speed=2.0)` - ramp up to `level` then automatically back to 0; the smooth full-screen flash. Keep `level` under 16 so it stays a see-through dither, never a solid wall.
- `.tick()` - step `level` toward `target` by `speed`. Returns `True` when the target is reached.
- `.is_done` (property) - `True` when `level == target`.

```python
import picogame_fx as fx

fader = fx.Fade(scene, W, H)
# ...trigger a fade to black:
fader.out(speed=2)
# ...each frame, fade back in once we hit black:
if fading and fader.tick():
    fader.into(speed=2)
```

:::note[Gotchas]
`level` runs from 0 to 16, not 0 to 255 or 0.0 to 1.0. A white `Fade` pulse works on every render backend. `InvertFlash` below avoids repainting but only works with a supported panel controller.
:::

### `fx.Tween` - ease a scalar toward a target

![A value easing toward its target](/img/fx_tween.gif)

A per-frame exponential ease-out for a single value: UI slides, pop-up scales, a number that should "catch up" smoothly. No keyframes or schedule.

- `Tween(value=0.0, speed=0.2)` - `speed` is the fraction of the remaining gap closed each frame (0..1).
- `.to(target, speed=None)` - set a new target (and optionally a new speed). Returns `self`.
- `.set(value)` - snap value and target to `value` immediately.
- `.tick()` - move value a `speed` fraction toward target and return the new value. Snaps exactly when within 0.01.
- `.is_done` (property) - `True` once value equals target.

```python
import picogame_fx as fx

y = fx.Tween(0)
y.to(100)               # slide a panel down to y=100
# ...each frame:
panel.y = int(y.tick())
```

:::note[Gotchas]
ease-out only, so it never overshoots or bounces. `tick()` returns the value - read its return rather than `.value` if you want the freshly-stepped number.
:::

### `fx.Camera` - smoothed follow camera

![The camera following across a wider world](/img/fx_camera.gif)

Tracks a world point and produces the scene view offset, centred and optionally clamped to a world size. Use it when the level is bigger than the screen.

- `Camera(scene, w, h, lerp=0.18, world_w=0, world_h=0, top=0, bottom=0, left=0, right=0)` - `w`/`h` are the screen size; `lerp` is the follow smoothing per frame; `world_w`/`world_h` (if non-zero) clamp so the view never shows past the world edge; `top`/`bottom`/`left`/`right` are a reserved HUD band (the same numbers you gave `setup()` or `Scene`), so the camera centres and clamps inside the visible part of the screen instead of under the HUD.
- `.follow(tx, ty, snap=False)` - move the camera centre toward `(tx, ty)` by `lerp`, or jump there with `snap=True`. Returns `self`, so you can chain.
- `.apply(shake=None)` - compute the offset and call `scene.set_view` directly. Allocation-free; returns `None`. Pass a `Shake` (`cam.apply(shaker)`) and the shake offset rides on top of the camera in the same call - one `set_view`, no tuple.
- `.offset()` - compute and return the offset as an `(ox, oy)` tuple (allocates a tuple per call - fine for setup or a test, not for the frame loop). After `apply()`/`offset()` the ints are also readable as `.ox`/`.oy`.

```python
import picogame_fx as fx

cam = fx.Camera(scene, W, H, world_w=bounds_w, world_h=bounds_h, top=BAR)   # same band as setup(top=BAR)
# ...each frame:
cam.follow(player.x, player.y).apply()
```

:::note[Gotchas]
`apply()` and `Shake.tick()` both call `scene.set_view`, so don't run both blind - the second overwrites the first. To combine, call `cam.follow(...).apply(shaker)`: the shake stacks on the camera and the view is set once. See [/scene-format/](/scene-format/) for what `set_view` does to the view.

With a HUD band, pass it as `top=`/`bottom=`/… - not by padding `h`. `Camera(scene, W, H + BAR, ...)` recentres correctly but clamps against the padded height, so `BAR` pixels of the world at each edge can never scroll into view. The simulator warns when the camera's band differs from the scene's.
:::

### `fx.Sky` - vertical gradient background

A per-scanline gradient drawn through `StripDraw`. It retains a lookup table of `h` wire-order colours, or `2 * h` bytes, and redraws the requested rows when its region is repainted. Add it before the gameplay layers.

- `Sky(scene, x, y, w, h, top, bottom)` - fills the rect, lerping each scanline from the `top` wire-RGB565 colour to `bottom`. Added `fixed=True`. Change `.top`/`.bottom` over time for a day-night cycle.

```python
import picogame as pg
import picogame_fx as fx

sky = fx.Sky(scene, 0, 0, W, HORIZON,
             pg.rgb565(60, 120, 240), pg.rgb565(200, 230, 255))
```

:::note[Gotchas]
it issues one `fill_rect` per visible scanline. Its CPU cost grows with the height of the repainted region.
:::

### `fx.Scanlines` - CRT scanline overlay

Darkens every Nth row for a CRT or LCD-grid look. It retains one PAL8 row of `w` bytes plus a two-entry palette, then blits that row through `StripDraw`. Add it after gameplay layers so it remains visible.

- `Scanlines(scene, x, y, w, h, step=2, dark=pg.rgb565(0, 0, 0))` - `step=2` darkens every other line; `dark` is the overlay colour. Precomputes a 1px dither row and blits it once per darkened line (one blit instead of a per-pixel loop).

```python
import picogame_fx as fx

scanlines = fx.Scanlines(scene, 0, 0, W, H)   # add LAST, on top of everything
```

:::note[Gotchas]
order matters - add it after every gameplay layer or it gets painted over.
:::

### `fx.InvertFlash` - controller inversion flash

![Full-screen colour-inversion flash (sim-emulated)](/img/fx_invertflash.gif)

Flips a compatible SPI panel to its negative for a few frames using controller colour inversion (`pg.invert`). It does not repaint the scene or allocate a pixel buffer. Use it with ST7789/ST7735-class controllers; it is not available on framebuffer outputs such as Fruit Jam DVI. The simulator emulates the effect.

- `InvertFlash(display, frames=3, normal=None)` - `display` is the board's display, e.g. `picogame_game.display()`; `frames` is the flash length. `normal` is the panel's resting invert state. The PicoPad sends INVON in its init, so its resting state is `normal=None` (the default); pass `normal=False` only for a panel whose init does not invert.
- `.pulse(frames=None)` - flip away from the resting state now (optionally for a custom frame count).
- `.tick()` - count down and restore the resting state when the flash ends. Returns `True` while flashing. Call it after `scene.refresh()` so the INVON/INVOFF is the frame's last bus op.

```python
import board
import picogame_fx as fx

flash = fx.InvertFlash(picogame_game.display(), frames=6)
# ...on hit:
flash.pulse()
# ...after scene.refresh():
flash.tick()
```

:::note[Gotchas]
the resting inversion state must match the panel initialization. On PicoPad, leave `normal=None` so the helper uses the configured default. Do not construct this effect for a framebuffer display. See [/hardware/](/hardware/) for controllers that support INVON/INVOFF.
:::

**Seizure safety:** for any full-screen flasher (`InvertFlash`, `Fade.pulse`, rapid sprite flash), avoid sustained flashing above ~3 Hz (at least 10 frames apart at 30 fps); keep full-screen inverts to 1-3 frames, one-shot.

## picogame.Particles

![A particle burst expanding and fading](/img/fx_particles.gif)

`pg.Particles` is a core engine layer for sparks, explosions, pickup bursts, and dust. It pre-allocates a fixed-capacity pool and does not create new particle objects during `emit()` or `tick()`.

- `pg.Particles(capacity, *, size=1, gravity=0.0, fade=False)` - a pool of up to `capacity` dots, each `size` px. `gravity` pulls them down per tick (0 = free drift); `fade=True` dims a dot as it ages. `size`/`gravity`/`fade` are keyword-only (pass them by name).
- `.emit(x, y, count, speed=1, life=30, color=0xFFFF)` - burst `count` dots from `(x, y)` with random velocity up to `speed` px/tick, each living `life` ticks.
- `.tick()` - age and move the live dots; call once per frame.

```python
import picogame as pg

ps = pg.Particles(180, size=2, gravity=0.0, fade=True)
scene.add(ps)                                        # add once, like any layer
# ...on a hit / kill / pickup:
ps.emit(x, y, 16, 4, 24, pg.rgb565(255, 210, 120))   # 16 sparks, speed 4, 24-tick life
# ...every frame:
ps.tick()
```

:::note[Gotchas]
emits past `capacity` are dropped, so size the pool for your busiest moment (a big burst plus lingering sparks). `fade=True` + a short `life` reads as a spark; `gravity > 0` + a longer `life` reads as debris falling. Keep the live-dot count modest on RP2040.
:::

## picogame_palette

![Palette cycling - a reserved colour band flows](/img/fx_palette.gif)

PAL8 art can change colour without duplicating its pixel indices. `cycle` rotates a range of palette entries, `swap` copies another palette, and `fade` interpolates entries toward a target. Palette entries are wire-order RGB565 integers returned by `pg.rgb565()`.

`import picogame_palette as palette`

- `snapshot(palette)` - return an `array('H')` copy of a palette. Save the original once, before any fading or cycling, so you can fade relative to it or `restore` it.
- `restore(palette, base)` - copy `base` back into `palette` in place.
- `cycle(palette, lo, hi, step=1)` - rotate entries `[lo..hi]` inclusive by `step` (wraps), in place with no allocation, so it is safe to call every frame. Reserve a run of indices for flowing colours, paint your art with them, and they animate.
- `swap(dst_palette, src_palette)` - copy one palette over another (up to the shorter length). GBC-style recolour: keep one PAL8 bitmap and hand it a different palette per variant. Cheaper than a second bitmap.
- `fade(palette, base, t, target=0, skip=None)` - lerp every entry of `palette` from the saved `base` toward the `target` wire colour by `t` (0.0 = base .. 1.0 = target). `target=0` (black) fades out; a white target fades to white. `skip` leaves one index untouched (e.g. a transparent index).

```python
import picogame_palette as palette

# ...each frame, flow a reserved band of water colours:
palette.cycle(water_bmp.palette, 1, 6)
water.touch()                       # tell the renderer the palette changed
```

:::caution[One blit slot on device]
A sprite's `flash`, `tint`, `dither`, and `shadow` effects share **one** blit slot on hardware — setting one clears the others (last-set-wins). The desktop simulator does **not** reproduce this; it shows them as independent. Combine them by sequencing frame-by-frame or using a separate effect layer; always confirm on hardware.
:::

Recolour a sprite **brighter / to a new hue** — what `sprite.tint` can't do (multiply only darkens).
Keep one PAL8 bitmap and give it a warm palette (e.g. a green enemy → a hot amber "elite"):

```python
import array, picogame_palette as palette

WARM = array.array("H", [0, pg.rgb565(150, 40, 30), pg.rgb565(255, 130, 45),
                         pg.rgb565(120, 45, 25), pg.rgb565(255, 215, 130),
                         pg.rgb565(235, 90, 45), pg.rgb565(255, 245, 190)])  # one entry per index
palette.swap(enemy.bitmap.palette, WARM)   # copy WARM into the bitmap's palette, in place
enemy.touch()                              # the renderer won't notice a palette change on its own
# Per-variant instead of in-place? Build a 2nd `pg.Bitmap(DATA, ..., palette=WARM)` and assign it to
# the sprite's `.bitmap` — see examples/picogame_picowing.py, which recolours the Kenney enemy this way.
```

:::note[Gotchas]
the dirty-rect renderer reads the palette at blit time but does not notice a palette change on its own. After any `cycle`/`swap`/`fade`/`restore`, call `sprite.touch()` on the sprites using that bitmap (or `scene.invalidate()` / repaint the tilemap region) or nothing visibly changes. The cost is a repaint of the affected sprites that frame, so cycle a small band (a strip of water), not the whole screen. See [/memory/](/memory/) for why this beats holding a second recoloured bitmap.
:::
