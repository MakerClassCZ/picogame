# picogame — quick reference

A one-page cheat sheet of the engine's everyday API: the native `picogame` C module
and the pure-Python `picogame_*` helper libraries in `lib/`. Signatures show parameter
names and defaults; `*` marks keyword-only arguments. Colours are wire-order RGB565 ints
(build them with `rgb565`). For longer explanations see the [engine guide](engine.md).

**See also:** [Fit it in RAM](memory.md) · [Drawing paths](/concepts/drawing-paths/) · [Performance](/performance/) · [Run on hardware](hardware.md) · [Coming from another engine](/concepts/coming-from/).

---

## Native module: `picogame` (`import picogame as pg`)

### Constants & colour
- `RGB565`, `PAL8` — bitmap pixel formats.
- `API_LEVEL` — `int`; engine API generation, bumped when the Python-visible surface grows. Libraries check `getattr(pg, "API_LEVEL", 0) >= N` to diagnose a too-old firmware up front instead of failing later on a missing attribute.
- `RGB444_SUPPORTED` — `bool`; whether this board's panel can drive 12-bit RGB444 (lets one game opt into `Display(rgb444=True)` only where it works).
- `FPU` — `bool`; `True` when the 3D math primitives (`pg.project`) run the hardware-float path (RP2350, ESP32-S3), `False` on the RP2040 (16.16 fixed-point). Pack `project` buffers to match: `array("f")` when `pg.FPU` else `array("i")` with values `int(v * 65536)`.
- `rgb565(r, g, b) -> int` — wire-order colour from 8-bit channels.
- `collide(x1, y1, x2, y2, ax1, ay1, ax2, ay2) -> bool` — AABB overlap (8 args = box vs box) or point-in-box (6 args: `collide(x1, y1, x2, y2, px, py)`). Inclusive AABB, so boxes collide when they touch (pass sprite boxes as `(x, y, x+w, y+h)`; fires on contact).

### `Bitmap(data, width, height, *, format=RGB565, palette=None, frames=1, stride=0, transparent=None)`
An image atlas of equal-size frames (any size). `data` is a buffer; `palette` (array of wire colours) is required for `PAL8`. `transparent` = the index/colour skipped when blitting.
- Read-only props: `width`, `height`, `frames`, `format`, [`stride`](/concepts/glossary/) (pixels per source row; leave `0` for tightly-packed data, set it only for a sub-window of a larger image), `palette` (the PAL8 palette buffer or `None`), `transparent` (the transparent value or `None`).

### `Sprite(bitmap, x=0, y=0, *, frame=0, visible=True, flip_x=False, flip_y=False)`
A positioned, animatable instance of a Bitmap.
- Position/anim props: `x`, `y` (int px) · `fx`, `fy` (float sub-pixel) · `frame` · `visible` · `flip_x`, `flip_y` · `bitmap` (swap) · `data` (your payload).
- Transform props (nearest-neighbour, about the anchor):
  - `scale` — float draw scale; `1.0` = native (fast path), `2.0` = double size, fractional allowed (e.g. a pulse).
  - `angle` — rotation in degrees; `0` = none (fast path). Combines with `scale`.
  - `transpose` — bool; swaps X/Y axes. On its own that is a **diagonal mirror**, not a rotation; combine with a flip for a crisp, shimmer-free quarter-turn. With `flip_x`/`flip_y` it reaches all 8 orientations. Fast path only (scale 1, angle 0); footprint swaps w/h. Recipes (screen y-down): **90° CW** = `transpose+flip_y` · **180°** = `flip_x+flip_y` · **270° CW** = `transpose+flip_x`.
  - `anchor` = `(fx, fy)` — pivot as fractions of the bitmap (0..1): `(0.5, 0.5)` = centre, `(0.5, 1.0)` = bottom-centre. `x`/`y` and rotation are about this point.
- Blit-effect props (one at a time; setting one clears the others; cheap, no extra bitmaps):
  - `shadow` — bool; opaque pixels darken the destination (drop-shadow / dim overlay).
  - `flash` — wire-RGB565 colour (or `0`/`None` = off); opaque pixels drawn as that flat colour (hit-flash). Pulse 1–3 frames.
  - `tint` — wire-RGB565 colour (or `0` = off); opaque pixels *multiplied* by it, colouring the sprite while **keeping its shading** (damage-red, freeze-blue, glow).
  - `dither` — `0` (opaque) .. `16` (invisible); Bayer-stipple translucency, no alpha (ghosts, fog, fade-in/out).
- `move(x, y)` — set position. · `touch()` — mark dirty after an in-place bitmap/palette edit.
- `overlaps(other, inset=0) -> bool` · `near(other, r) -> bool` — native collision tests (see **Sprite collision** below).

### `Display(busdisplay, *, rgb444=False)`
Fast DMA backend wrapping a board's `busdisplay` (FourWire SPI). Pass to `Scene`. `rgb444=True` drives the panel in 12-bit RGB444 (~25% less SPI traffic) on panels that support it; gate with `RGB444_SUPPORTED`.

### `Scene(display, buffer_a, buffer_b, *, background=0, top=0, bottom=0, left=0, right=0)`
Retained-mode scene with dirty-rectangle rendering; `buffer_a/b` are strip buffers.
- `add(item, *, fixed=False) -> item` — add a Sprite/Tilemap/Particles/Canvas/StripDraw (insertion order = bottom→top) and return it (so `spr = scene.add(Sprite(...))` works). `fixed=True` (keyword-only) pins it to the screen (ignores the camera) for HUD/dialog.
- `add_all(items)` — add several (bottom→top).
- `remove(item)` — unlink a previously added item (no ghost — next refresh repaints over it, like `invalidate()`); the item survives and can be `add()`ed again. `ValueError` if not in the scene.
- `set_view(ox, oy)` — camera offset (screen position of the scene origin); changing it repaints all.
- `view` — read-only `(ox, oy)` camera offset.
- `invalidate()` — force a full repaint next refresh.
- `refresh() -> list | None` — diff & repaint changed regions; returns the dirty rect `[x1,y1,x2,y2]` (reused) or None.

### `Tilemap(tileset, cols, rows)`
A grid of tile indices into a tileset Bitmap (each frame = one tile); a Scene layer.
- `get_tile(tx, ty) -> int` — read a tile. · `set_tile(tx, ty, value, *, flip_x=False, flip_y=False, transpose=False)` — write one (with optional keyword-only per-cell orientation: `flip_x`/`flip_y`/`transpose` give all 8 orientations of a tile; pair with a deduplicated tileset, see `png2picogame.py --dedup`). Out-of-range ignored. The orientation plane is allocated lazily (RAM only if a map uses it).
- `fill(value)` — set every tile (clears orientation).
- `move(x, y)` — position the map.
- Read-only props: `x`, `y`, `cols`, `rows`.
**Breaking change:** replaced `tile(tx, ty[, value])` (firmware after 2026-08-23); old code raises
`AttributeError`. The firmware is what must be new enough.

### `Particles(capacity, *, size=1, gravity=0.0, fade=False)`
A pooled particle layer (small moving dots) drawn as one Scene layer.
- `emit(x, y, count, speed=1, life=30, color=0xFFFF)` — burst `count` dots, random velocity ≤ `speed` px/tick, living `life` ticks.
- `tick()` — advance one step (move, gravity, ageing). Call each frame.
- `clear()` — remove all.

### `Canvas(width, height, *, transparent=None, buffer=None)`
A RAM RGB565 drawing surface composited as a Scene layer (`width*height*2` bytes). `transparent` makes it a shaped overlay; `buffer` backs it with external memory (e.g. an arena slice). For *animated full-frame* surfaces prefer `StripDraw` (no buffer).
- `clear(color)` · `pixel(x, y, color)` · `fill_rect(x, y, w, h, color)` · `rect(x, y, w, h, color)`
- `line(x0, y0, x1, y1, color)` · `circle(cx, cy, r, color)` · `fill_circle(cx, cy, r, color)` · `ring(cx, cy, r, thickness, color)`
- `triangle(x0,y0, x1,y1, x2,y2, color)` · `fill_triangle(...)` · `ellipse(cx, cy, rx, ry, color)` · `fill_ellipse(...)`
- `fill_round_rect(x, y, w, h, r, color)` · `frame3d(x, y, w, h, light, dark)` (beveled box) · `move(x, y)`
- `blit(bitmap, x, y, frame=0, flip_x=False, flip_y=False)` — stamp a bitmap frame into the surface (honours its transparent key; the retained way to bake an icon/portrait/rendered text into a panel).
- `text(x, y, s, fg, font, bg=None)` — composite a string in C, rasterizing each glyph of `font` (a `fontio.BuiltinFont`) on the fly. **The built-in `terminalio.FONT` is a fixed 6×12 cell**, so a string is `len(s) * 6` px wide and centring is `(W - len(s) * 6) // 2` (both fonts here are fixed-width: `picogame_bitfont` is 8×8). At 6 px/char a 320 px screen holds 53 characters and a 240 px one holds 40 — budget text against the smaller. Details: no Python glyph cache and no per-call Bitmap/Sprite. `bg=None` → transparent glyph background. ASCII/built-in font only. Works on a Canvas or a `StripDraw` view; the latter does not retain a separate text surface.
- `mode7(texture, horizon, y_off, z, rx0, ry0, rsx, rsy, cam_x, cam_y)` — fill the rows below `horizon` with a **Mode-7 perspective floor** of `texture` (power-of-2 dims; one world unit = one tile). 10 fixed-point (16.16) args — you normally let `picogame_mode7.Camera` compute them from a camera pose. Draws into a Canvas or a 0-RAM `StripDraw` view (pass `y_off` = the strip top).
- `vspans(x0s, x1s, tops, bots, colors, n, x_off=0, y_off=0)` — fill `n` **vertical colour spans** in one call: span *i* covers `x0s[i]..x1s[i]` × `tops[i]..bots[i]` (both exclusive) in `colors[i]`; all five are uint16 arrays. The batch primitive for column renderers — `picogame_ray` paints its merged wall runs with one call per strip (`x_off=-vx, y_off=-vy` replay, off-band spans rejected with two compares), which made its per-strip cost independent of the run count (measured: a full-screen stride-1 raycast frame 203–275 ms → ~27 ms (~36 fps)).
- `fill_triangles(verts, colors, n, x_off=0, y_off=0)` — fill `n` triangles in **one call**: `verts` = int16 `x0,y0,x1,y1,x2,y2` per triangle, `colors` = wire-RGB565 uint16 per triangle. Same rasteriser as `fill_triangle`, but the whole batch crosses the Python/C boundary once — the win for many small triangles (blocky 3D, low-poly, isometric), where the ~10 µs per-call overhead otherwise dominates. `x_off`/`y_off` translate every vertex before clipping: pass `y_off=-vy` in a `StripDraw` callback to **replay one screen-space batch into each render strip** (off-band triangles are rejected with three compares) — full-res 3D with no retained canvas at all, the preferred path on framebuffer boards. Companion of `pg.project` and `picogame_iso.emit_blocks`.
- `road(ri0, tab, rl, rr, d05_q8, d07_q8, colors)` — draw one **OutRun-style racing-road strip** from precomputed tables: the whole per-scanline loop (sky/road/rumble/dash colour picks) in one call. `ri0` = road-table row at this surface's row 0 (negative = sky rows); `tab` = int16 rows of `{edge_w, dash_hw, wb05_q8, wb07_q8, flags}`; `rl`/`rr` = int16 per-row edges from `pg.road_edges`; `d05/d07` = Q8 scroll phases; `colors` = 6× uint16 `{sky, road_a, road_b, rumble_a, rumble_b, dash}`. Designed as a `StripDraw` callback body (0-RAM road).
- Read-only props: `x`, `y`, `width`, `height`.

### `StripDraw(callback, x=0, y=0, width=0, height=0, *, always_dirty=True)`
Immediate-mode layer with **no pixel buffer**: each refresh it calls `callback(view, vx, vy, vw, vh)` once per render strip inside its rect. `view` is a Canvas pointing at the live strip (use Canvas primitives, incl. `view.text`); view-local `(0,0)` = screen `(vx, vy)`. In a scrolling scene add it `fixed`.
- `always_dirty=True` (default) repaints every frame → for animated/scanline content (pseudo-3D, gradients). `always_dirty=False` repaints only when invalidated or overlapped by another change → for static/on-change panels (it still renders once on first refresh).
- `invalidate()` — mark it dirty so the next refresh repaints it (the way to update an `always_dirty=False` panel when its content changes).

### `Triangles(verts, colors)`
A retained **screen-space triangle batch** the compositor rasterises **entirely in C** per render strip (cheap band reject + the Canvas rasteriser) — no pixel buffer AND no Python per strip. `verts` = int16 array (`x0,y0,x1,y1,x2,y2` per triangle), `colors` = uint16 wire-RGB565 per triangle — both **caller-owned** (fill them in place each frame). This is **the 3D-scene layer**: `pg.project` into the arrays, painter's-order the faces, set `count`, `scene.refresh()`. Because no Python runs during compose, it stays composable by the core1 band split — unlike a `StripDraw` callback.
- `count` — how many triangles draw next refresh (clamped to the buffer capacity); **assigning marks the layer dirty** for a full repaint (set it every frame in a live 3D scene).
- Measured (roadhop lab): replaces the `fill_triangles`-in-StripDraw replay with ~30 % less refresh time at 320×240 and unlocks the dual-core compose (640×480 at a locked 20 fps on an RP2350 with a free second core).
- Read/write props: `x`, `y`, `width`, `height` — move or resize the layer (after shrinking, call `scene.invalidate()`) · `always_dirty`.

### Low-level draw functions
Most games never call these (`picogame_game.setup` + `Scene` use them internally), but they are exposed for hand-built render loops.
- `render(display, sprites, buffer, x0, y0, x1, y1, *, background=0)` — render a sprite list into the region `[x0,x1) × [y0,y1)` and push it to `display`. `buffer` is a reusable strip buffer (≥ region-width × 2 bytes). **Mixing with a retained scene:** the scene doesn't know `render()` changed the pixels — if the region overlaps the scene's play rect, call `scene.invalidate()` after (or use `picogame_game.overlay`, which does both); HUD bands outside the play rect don't need it.
- `invert(display, on)` — toggle the panel's hardware colour inversion. Changes the panel's inversion state without sending pixel data, so a brief invert makes a full-screen negative flash (a 1-bit "hit" look) with no redraw. See `picogame_fx.InvertFlash`.
- `project(cam, pts, n, out_sx, out_sy)` — **batch perspective projection** of `n` 3D points to screen in C. `cam` = 15 camera params `(ex,ey,ez, rx,rz, ux,uy,uz, fx,fy,fz, focal, cx0, cy0, near)`, `pts` = `n×3` world coords, `out_sx`/`out_sy` = int16 screen coords (a point behind the near plane gets the sentinel `-32768` — skip its faces). Buffer format follows `pg.FPU` (float32 on FPU boards, 16.16 int32 on the RP2040 — a format mismatch culls everything = black screen). One call per frame + `Canvas.fill_triangles` = real flat-shaded polygon 3D (Elite-class): project your vertices, painter's-sort faces, fill. ~0.7 ms/480 pts on an RP2350, ~2.2 ms on an RP2040.
- `road_edges(rl, rr, hw, n, cx0, dist, cfg)` — one racing-road frame's **curve accumulator + integer edge tables** in a single call (the OutRun-genre `compute_road` loop). `rl`/`rr` = int16 outputs for `Canvas.road`, `hw` = int32 Q16 per-row half-widths, `cx0` = Q16 screen centre (incl. lateral offset), `dist` = integer world distance, `cfg` = int32[7] **curve** config (`f1,f2` Q20 frequencies, `a1k,a2k` Q16 amp×gain, world step, curve step, row offset) — there is NO hill term: `road_edges` emits horizontal edges only, and hills come from moving the horizon you pass as `Canvas.road`'s `ri0`. Pairs with `Canvas.road` for a 0-RAM 30 fps road on the RP2040.
- `vblank()` — (DVI boards, RP2350) block until the scanout's next vertical blanking (≤ ~16.7 ms). Starting a full-frame compose right after vblank keeps the publish front consistently behind the beam, so each sweep shows one **whole** frame — removes single-buffer tearing while the compose fits within two sweeps. Costs the wait: budget it against your FPS cap.
- `core1(on) -> bool` — (RP2 boards) route splittable engine kernels (`Canvas.mode7` rows, the framebuffer compose bands) through the second core. Returns the **resulting** state: `False` when core1 is unavailable — e.g. a **USB-host board (Fruit Jam) runs its USB service on core1 permanently**, so the engine refuses rather than stomping it. Dual-core compose measured ~1.75× on an RP2350 with a free core1.
- **`core1` is NOT in a CircuitPython release.** It lives on the fork's `picogame-core1` branch and has not gone upstream, so `pg.core1` raises `AttributeError` on any firmware you download from circuitpython.org. Guard it with `hasattr(pg, "core1")` and treat the dual-core path as an optimisation you may not have.

### Procedural noise (coherent value noise, 0..1)
- `value2d(x, y, *, seed=0) -> float` · `value1d(x, *, seed=0) -> float`
- `fbm2d(x, y, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` · `fbm1d(x, *, octaves=4, seed=0, lacunarity=2.0, gain=0.5) -> float` — fractal (summed octaves).

---

## Helper libraries (`lib/picogame_*.py`, pure Python)

### `picogame_game` — one-call boot
- `setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0, rgb444=False) -> (scene, buffer_a, buffer_b)` — take over the display, build a Scene + two strip buffers. `top/bottom/left/right` reserve fixed HUD margins; `rgb444=True` opts into 12-bit colour on a supporting SPI panel, and `rgb444="auto"` enables it only where the board reports `picogame.RGB444_SUPPORTED`.
- `overlay(scene, display, items, buffer, x0, y0, x1, y1, *, background=0)` — immediate-draw `items` over a live scene (pause / menu / cutscene / banner) = `pg.render` + `scene.invalidate()`, so the next `refresh()` repaints the full frame instead of leaving overlay fragments.
- `screen() -> (width, height)` — the screen size, from whichever display the board provides. Lay every game out from this instead of hardcoding 320×240.
- `display()` — that same display object (for `pg.render`, `picogame_fx.InvertFlash`, …). Both read `supervisor.runtime.display` — the board's primary display, which CircuitPython picks right after board init and which a `boot.py`, a launcher or `open_framebuffer()` publishes with `supervisor.runtime.display = disp`. That is the one way a display reaches a game, so the same file runs on a PicoPad, a Fruit Jam, a bare Pico, in the simulator and in the browser playground (the last two ship a small `supervisor` shim).
- `open_framebuffer(width, height, color_depth=None) -> display` — set the resolution from inside a game on a framebuffer board (Fruit Jam DVI), e.g. `open_framebuffer(640, 480)`; a no-op that returns the current display on a fixed SPI panel. Pass the result to `setup(display=…)`.
- `resolve_display(display=None) -> (display, is_framebuffer)` — normalise a display/framebuffer handle (used by the HUD / immediate-render helpers).

### `picogame_clock` — frame pacing
- `Clock(fps=30, max_dt=0.1)` · `.set_fps(fps)` · `.tick() -> dt` (sleep to frame, return seconds) · `.tick_async()` (the same, for `asyncio` loops).
- `FixedStep(step_fps=60, max_steps=5)` · `.steps()` — generator yielding a constant dt per fixed step · `.step_count()`.

### `picogame_input` — buttons
- Masks: `UP DOWN LEFT RIGHT A B X Y L1 L2 R1 R2 START SELECT ALL` (a superset; each board maps the subset it has); profile `PICOPAD`.
- `Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)` · `.poll() -> mask` · `.is_pressed(mask=ALL)` · `.just_pressed(mask=ALL)` · `.just_released(mask=ALL)` · `.has(mask=ALL)` (is the mask present in the profile) · `.repeat(button, delay=15, interval=4)` — PICO-8 `btnp` auto-repeat (menus / grid move) · `.clear()` (drop held state) · `.attach(source)` / `.detach(source)` — OR another input source in/out at runtime (a `picogame_seq.Script` attract demo, a late USB pad).
  - `matrix=` — a scanned key-matrix source (also configured board-wide via the `PICOGAME_MATRIX_*` settings keys); `usb=` — one or more extra button **sources** (USB pad/keyboard, below). `Buttons` ORs every source together, so a game reads them all with no code change.
- `Timer(frames)` — input-leniency window (coyote time / jump buffering): `.feed(condition)` (recharge while true, else decay) · `.charge()` · `.is_active` · `.consume()` (true once, then clears).

### `picogame_usbpad` — USB HID gamepad source (USB-host boards, e.g. Fruit Jam)
- `UsbPad(buttons=None)` — a button **source** for `Buttons(usb=…)` (auto-attached by default on a USB-host build). Reads a USB HID gamepad and ORs it into the button mask, so a plugged-in pad works with **zero game code changes**. Needs a USB-host CircuitPython build (`usb.core`); a no-op on boards without it.
- Default map = the ubiquitous DragonRise `081f:e401` SNES-style pad; remap per pad from `settings.toml` (`PICOGAME_USBPAD`, no reflash — see [Custom board](custom-board.md)). Discover a new pad's report bytes with `tools/usbpad_probe.py`.
- `.mapped` — mask of buttons this pad can report; `VERSION`, `MAPPED` module constants.

### `picogame_usbkbd` — USB HID keyboard source (USB-host boards)
- `UsbKbd(keys=None)` — the keyboard twin of `UsbPad`, a `Buttons(usb=…)` source. Found by its boot-keyboard HID interface (no fixed VID/PID); works with wired and 2.4 GHz-dongle keyboards (not Bluetooth).
- Default map: arrows + WASD → D-pad, Z/Space → A, X → B, C → X, V → Y, Q → L1, E → R1, Enter → START, Esc → SELECT. Remap from `settings.toml` (`PICOGAME_USBKBD`, `NAME=HID-keycode`). For a combo dongle whose real keystrokes flow on a sibling interface, point it at the right channel with `PICOGAME_USBKBD_EP = "iface:endpoint"` (find it with `tools/usbkbd_probe.py`).

### `picogame_font` — text bitmaps (external font module)
Which text path to use (`Canvas.text` vs a rendered Bitmap vs a StripDraw view — and what each costs): see the decision matrix in [Drawing paths](/concepts/drawing-paths/).
- `render_text(pg, font, text, fg, bg=None) -> (bitmap, w, h)` — render a string to a PAL8 Bitmap (`bg=None` → transparent).
- `render_text_pal(pg, font, text, fg, bg=None) -> (bitmap, w, h, palette)` — same, plus the palette array; mutate `palette[1]` to recolour the text in place (no rebuild).
- `Label(pg, font, x, y, fg, bg)` · `.move(x, y)` · `.set(text) -> changed` · `.draw(display, buffer)`.

### `picogame_bitfont` — built-in font (no font module needed, fixed 8×8 cell: `GLYPH_W`/`GLYPH_H`)
- `render_text(pg, text, fg=None, outline=None, mid=None, bg=None) -> (bitmap, w, h)` — render with the bundled bitmap font; optional `outline`/`mid` give a cheap 2-tone outlined look.

### `picogame_ui` — HUD & menu widgets (`LINE_H = 12`)
- `SceneLabel(scene, pg, font, x, y, fg, bg)` · `.set(text)` · `.reserve(chars)` · `.destroy()` — camera-independent text label (a fixed Scene layer). `reserve(chars)` switches it to a FIXED-width buffer built once: `set()` then composes glyphs in place — zero allocation per update, and the label cannot grow-realloc on a fragmented heap. There is no `.move()` and no width metric, so CENTRE a changing value by reserving the widest string and padding with spaces (the font cell is fixed-width, 6 px/char). destroy() detaches a ONE-SHOT label so GC reclaims it (recurring HUD: build once + set/hide instead).
- `SceneBox(scene, pg, font, x, y, w, h, fg, bg, nlines=3, key=None, border=None)` · `.show(lines)` · `.hide()` · `.set_line(i, text)` · `.destroy()` — a multi-line in-scene panel (dialog/log); destroy() = one-shot teardown (needs firmware with `Scene.remove`).
- `HudBar(pg, display, buffer, x, y, w, h, bg)` · `.add(sprite)` (an icon Sprite) · `.label(font, x, y, fg, text=" ")` → a text handle; update it with `handle.set(text)` · `.draw()` (repaint the bar, call on HUD changes) — a fixed bar that composites sprites + labels (0 retained RAM).
- `TextBox(pg, font, x, y, w, h, fg, bg, maxlines=6)` · `.draw(display, buffer, lines, force=False)`.
- `Menu(pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None, paged=True)` · `.tick(btn)` → index ≥0 on A, `CANCEL` (= -2) on B, `None` while navigating · `.draw(display, buffer, force=False)`.
- `SceneMenu(scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None, border=None, paged=True)` · `.show(sel=0)` · `.hide()` · `.tick(btn)` → index ≥0 on A, `CANCEL` (= -2) on B, `None` while navigating — the same menu as an in-scene layer.
- `GridCursor(cols, rows, tx=0, ty=0, wrap=False)` · `.index` · `.tick(btn) -> (tx, ty) | None | ui.CANCEL` — D-pad cursor over a grid (inventory / board). `tick` moves on held D-pad (auto-repeat) and returns the selected cell on A, `ui.CANCEL` on B, else `None`; guard with `if pick is not None and pick is not ui.CANCEL:` (the tuple does not support `>= 0`).

### `picogame_options` — settings menu
- `OptionsMenu(scene, pg, font, x, y, w, rows, fg, bg, title=None, border=None)` · `.value(key)` · `.show(sel=0)` · `.hide()` · `.tick(btn)` — an in-scene options screen of toggles/choices.

### `picogame_shapes` — single-colour bitmap generators
- `rect(w, h, color)` · `circle(d, color)` · `ring(d, color, thickness=2)`
- `from_mask(mask, color)` — Bitmap from a **list of strings**, one per row (`'#'`, `'X'` or `'1'` = set); sized to the mask. Passing a single string is not an error — each CHARACTER becomes a row, so you get a 1-pixel-wide sprite and no exception.
- `masks(mask_list, color)` — **multi-frame `from_mask`**: a list of string masks → one horizontal atlas Bitmap (frame *i* = `mask_list[i]`), sized to the largest. The step between `from_mask` (single frame) and `atlas` (raw 0/1 buffers, which nothing else produces) — animated or multi-state mask art needed it and every game re-derived the same ten lines.
- `atlas(frames_data, w, h, color)` — pack w×h buffers into a multi-frame Bitmap.
- `color_frames(w, h, colors)` — frame i = solid `colors[i]`.
- `tileset_colors(w, h, colors, gap=0)` — tileset: frame 0 empty, frames 1..N coloured; `gap=N` carves an N-px transparent right+bottom edge into each tile, so touching same-colour tiles read as individual tiles (brick walls show mortar, not stripes).
- `poly_frames(size, points, nframes, color, fill=True)` — bake `nframes` rotations of a polygon.

### `picogame_pool` — reusable sprite pool
- `Pool(scene, bitmap, capacity, anchor=None, fixed=False)` · `.spawn() -> sprite | None` · `.free(s)` · `.free_all()` · `.count() -> int`. (`.items` = all sprites.)
- **`visible` means only "draw this"** — the pool keeps its own in-use bit (`.alive`, one byte per slot), so blinking a pooled sprite through `.visible` is safe: its slot stays taken. `spawn()` shows the sprite it hands out and `free()` hides it again, so `if not s.visible: continue` stays a correct liveness guard. While a sprite is blinked off that guard skips it, so it doesn't move for those frames — guard on `pool.alive[i]` instead if that matters.

### Sprite collision (native methods)
Collision lives on the `Sprite` itself: zero-alloc, anchor/scale/rotation aware (no separate module).
- `Sprite.overlaps(other, inset=0) -> bool` — inclusive AABB box overlap (touch = hit). `other` = another `Sprite`, a point `(x, y)`, or a rect `(x1, y1, x2, y2)` (trigger zone / screen-cull). `inset` shrinks THIS sprite's box by N px per side for a fair hitbox.
- `Sprite.near(other, r) -> bool` — circular: this sprite's centre within `r` px of `other`'s centre (squared distance, no sqrt). `other` = a `Sprite` or a point `(x, y)`.
- Raw primitive (any coords, no sprite): `pg.collide(x1, y1, x2, y2, ax1, ay1[, ax2, ay2])` — 8 args box-vs-box, 6 args box-vs-point.
- Tile-grid collision (walls/terrain): probe `picogame_tiles` flags (`at_px(tm, x, y, SOLID)`), not AABB.

### `picogame_math` — numeric helpers, vectors & turn-based trig
- `clamp(v, lo, hi)` · `mid(a, b, c)` · `lerp(a, b, t)` · `inv_lerp(a, b, v)` · `remap(v, a, b, c, d)` · `sgn(x)` · `approach(v, target, step)` · `wrap(v, lo, hi)`.
- `sin_t(turns)` · `cos_t(turns)` · `atan2_t(dy, dx) -> turns` — angles as 0..1 turns (standard, not PICO-8's inverted sin).
- `length(dx, dy)` · `distance(x1, y1, x2, y2)` · `normalize(dx, dy)` · `angle_rad(dx, dy)` (radians) · `from_angle_rad(a, mag=1.0)` — vector helpers.

### `picogame_tiles` — per-tile metadata flags (PICO-8 `fget`/`fset`)
- Bits/masks: `B_SOLID B_HAZARD B_LADDER …` (indices) and `SOLID HAZARD LADDER …` (masks).
- `TileFlags(flags=None, tile_px=8)` — `flags` = `{tile_index: bitfield}` or a list. `.get(tile, bit=None)` · `.set(tile, bit, value=True)` · `.at(tilemap, tx, ty, bit)` · `.at_px(tilemap, px, py, bit)` (collision one-liner). Keyed by tile index (shared by all cells using it).

### `picogame_script` — story scripts as generators (Director)
- `Director(pg, scene, buttons, font, box=None, nlines=3, fg=0xFFFF, bg=0x0000)` — runs ONE story script at a time over a live scene; `box` = the dialog panel rect (default: a bottom strip sized from `screen()`).
- `.on(name, genfunc)` (register) · `.start(script)` (a name or a generator) · `.active` · `.tick() -> bool` — call once per frame **after** `buttons.poll()`; returns True while a script runs, INCLUDING its final step (so the A press that dismissed the last dialog cannot fall through into the same frame's game input).
- Waiting primitives (use with `yield from` inside a script): `.text(lines)` (dialog page, A advances) · `.ask(lines) -> sets .answer` (A/B choice) · `.wait(frames)` · `.fade_out(speed)` / `.fade_in(speed)`.
- Story flags: `.ev(name)` / `.ev_set(name)`, kept in `.events` (a set — persist it via your save schema). `.retarget(scene)` re-points the Director after a map change.

### `picogame_seq` — generator-driven sequences (coroutine pattern)
- `wait(frames)` · `over(frames, fn)` (fn(t), t 0..1) · `move_over(sprite, x, y, frames)` — all are generators; compose with `yield from`.
- `Seq(gen=None)` · `.start(gen)` · `.tick() -> done` — advance one step per frame (cutscenes, "do X over N frames").
- `Script(play, loop=False)` — **scripted input: a game that plays itself.** `play(s)` is a generator pressing Buttons masks over frames (`yield from s.tap(B.A)` · `s.hold(B.RIGHT | B.UP, n)` · `s.rest(n)`; `tap(..., base=mask)` keeps `base` held throughout). It is a Buttons *source*: `btn.attach(script)`, then `script.tick()` each frame **before** `btn.poll()` — the demo runs through the game's own input path (`just_pressed`/`repeat` all fire), on device and in the sim alike. Attract mode: attach on an idle title, `loop=True` to run forever, and hand the controls back on a human press — `if btn.state & ~script.mask: btn.detach(script); script.stop()`. The same script doubles as a scripted verification run.

### `picogame_anim` — frame animation over time
- `FrameAnim(sprite, frames, *, fps=8, loop=True)` · `.configure(frames, fps=8, loop=True)` · `.reset()` · `.tick(dt)`.
- `AnimatedSprite(sprite, anims)` · `.play(name)` · `.tick(dt)`.

### `picogame_fx` — juice & raster effects
- `Shake(scene, max_offset=6, decay=0.03, seed=0x9E37)` · `.add(amount)` (0.6 hit, 0.15 bump) · `.tick(cam_x=0, cam_y=0)` — trauma screen shake composed on top of the camera. `scene=None` = offset-only mode for strip-rendered games (road/raycaster/mode-7, which `set_view` never moves): tick() just updates `.ox`/`.oy` and you spend them in your renderer's params — `road.tick(dist, lateral + sh.ox)`, a jittered horizon.
- `Fade(scene, width, height, x=0, y=0, color=0, cell=8)` · `.to(target, speed=2.0)` · `.out()/.into()/.set(level)/.dim(level=8)/.clear()/.pulse(level=12, speed=2.0)` · `.is_done` · `.tick() -> done` — dither fade / dim / flash, full-screen or a region. Uses `StripDraw` without a retained pixel surface.
- `Tween(value=0.0, speed=0.2)` · `.to(target, speed=None)` · `.set(value)` · `.tick() -> value` · `.is_done` — ease a scalar (UI/pop-ups).
- `Camera(scene, w, h, lerp=0.18, world_w=0, world_h=0)` · `.follow(tx, ty, snap=False)` · `.offset() -> (ox,oy)` · `.apply()` — smoothed follow + world clamp (compose with `Shake` via `shake.tick(*cam.offset())`).
- `Sky(scene, x, y, w, h, top, bottom)` — vertical gradient with a `2*h`-byte colour table. · `Scanlines(scene, x, y, w, h, step=2, dark=0)` — CRT overlay retaining one `w`-byte PAL8 row and its palette.
- `InvertFlash(display, frames=3, normal=None)` · `.pulse(frames=None)` · `.tick()` — hardware-invert hit flash for a supported SPI panel. It does not redraw the scene and is not a framebuffer effect.

### `picogame_palette` — Game-Boy palette tricks on PAL8 art (call `sprite.touch()` after)
- `cycle(palette, lo, hi, step=1)` — rotate entries (animated water/lava/portals; ~0 extra art).
- `swap(dst_palette, src_palette)` — recolour a shared bitmap (GBC-style; cheaper than a 2nd bitmap).
- `fade(palette, base, t, target=0, skip=None)` — lerp toward a colour (smooth brightness fade; `base` = `snapshot()` of the original).
- `snapshot(palette)` / `restore(palette, base)`.

### `picogame_rand` — seedable RNG
- `Rand(seed=None)` (deterministic xorshift; `None` = time-seeded) · `.below(n)` · `.randint(a, b)` · `.random()` · `.chance(p)` · `.choice(seq)` · `.shuffle(lst)` · `.weighted(weights) -> index` · `.seed(s)`.
- `Bag(items, rng)` · `.next()` — shuffle-bag (7-bag) anti-streak randomizer.

### `picogame_save` — NVM persistence
- `Save(key, schema, *, offset=0)` — `schema` = an ordered dict of `name -> (struct format char, default)`; worked example → [/helpers/data/](/helpers/data/). · `.defaults()` · `.load() -> dict` · `.save(values)` · `.reset()`. Survives reboot/filesystem wipe.

### `picogame_audioout` — one output device for any board
- `make_output(sample_rate=22050, pin=None)` — returns this board's audio output, chosen automatically: an I2S DAC (Fruit Jam TLV320) when the board has `I2S_BCLK`, else a PWM output on `pin` (or the board default). Used by both `picogame_audio` and `picogame_synth`, so a game needs no board-specific audio code. Raises `RuntimeError` if no output exists.
- The TLV320's output select + the three volume trims are set from `settings.toml` (`PICOGAME_AUDIO_OUT`, `PICOGAME_DAC_VOLUME`, `PICOGAME_HP_VOLUME`, `PICOGAME_SPK_VOLUME` — see [Custom board](custom-board.md)); the driver's defaults are deliberately quiet, so raise them toward 0 dB. `PICOGAME_DEBUG = 1` prints why a DAC failed to init.

### `picogame_audio` — sample playback (PWM or I2S DAC)
- `Audio(pin=None, voices=4, sample_rate=22050, channels=1, bits=16, signed=True)` · `.load(path)` · `.play(sample, *, voice=None, loop=False, volume=1.0)` · `.sfx(sample, volume=1.0)` · `.music(sample, loop=True, volume=1.0)` · `.stop(voice=None)` · `.stop_music()` · `.deinit()` · `.is_playing`.
- `tone(frequency=440, ms=120, sample_rate=22050, volume=0.6)` — square-wave beep sample.

### `picogame_synth` — synthio music & SFX
- Waveforms: `sine()` · `saw()` · `triangle()` · `square()` · `noise()`.
- `note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08, amplitude=0.6, bend=None, cutoff=None)` — build a reusable instrument note (`midi` 60 = middle C; `cutoff` = low-pass Hz).
- `pitch_bend(semitones, ms, waveform=None, once=True)` — an LFO for a note's `bend` (slide / laser zap).
- `Synth(pin=None, sample_rate=22050, buffer_size=2048, music_level=0.4, sfx_level=0.7)` · `.sfx(n)` · `.press(n)` · `.release(n)` · `.music(midi_track)` · `.stop_music()` · `.set_levels(music=None, sfx=None)` · `.mute(on)` · `.available` — self-guarding init: on audio-less firmware **or** a failed init (tight heap, claimed pin) the instance runs as silent no-ops instead of raising; no try/except needed in games.
- `Drone(synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12)` · `.start()` · `.set(frequency, amplitude=None)` · `.stop()` — a continuously-held note (engine/siren/drone): press once, then feed `set(freq, amp)` each frame so synthio tracks the live pitch/amplitude.
- `load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240)` — load a MIDI file into a playable track.

### `picogame_sfx` — signature SFX kit (over `picogame_synth`)
- `Kit(synth)` — build a ready-made, hardware-tuned SFX set once from a live `Synth` (silent no-op without audio). Fire by event: `.blip()` · `.coin()` · `.powerup()` · `.zap()` (your fire) · `.pew()` (enemy fire) · `.jump()` · `.hit(rotate=True)` (brightness rotates on rapid fire) · `.hurt()` · `.boom()` · `.explosion()`. Call `.tick()` once per frame — drives the coin/powerup arpeggios and the priority + protected-window arbitration through the single SFX voice. Volume via the `Synth`: `.set_levels()` / `.mute()`.

### `picogame_cutscene` — full-screen image / story-scene player
- `palette(pg, rgb)` — build the wire palette once (from a bake_cutscene.py palette module, RGB triplets, or wire ints).
- `show(pg, display, buffer, path, pal=None, w=320, h=240, scale=None, band=24, bg=0)` — stream an image in row bands. The source band uses `w*band` bytes for PAL8 or `w*band*2` for RGB565, in addition to any render buffer passed in. `scale=None` derives an integer upscale from the display.
- `play(pg, display, buffer, btn, path, pal=None, ..., caption=None, caption_lines=None, auto_hold=0, clock=None)` — show it, overlay an optional caption bar, and wait for A/B (or auto-advance after `auto_hold` ticks).

### `picogame_stream` — stream sprite frames from flash
- `StreamSheet(pg, path, w, h, frames, palette, transparent=None)` · `.use(i)` (select a frame, loaded on demand) · `.close()` — keep big sheets on flash instead of RAM.

### `picogame_arena` — anti-fragmentation buffer
- `Arena(pixels)` · `.alloc(nbytes, align=1) -> memoryview` · `.canvas(w, h, transparent=None) -> Canvas` · `.reset()` · `.mark() -> m` / `.release(m)` (nested LIFO lifetimes: mark on entering a mode, release on leaving — run-level buffers survive) · `.free() -> int`. Grab one big buffer up front, hand out slices.

### `picogame_debug` — RAM watermarks + FPS overlay (testing aid)
- `enabled` — module flag (default False: calls ship as no-ops; flip True while testing).
- `ram(tag)` — gc.collect() + print `[RAM] <tag>: free N alloc M` at a transition (boot/battle/menu) — the on-device leak/fit diagnostic.
- `Watch(scene, clock=None, every=30, x=2, y=2)` · `.step()` each frame · `.hide()/.show()` · `.remove()` — a corner `FPS 30 FREE 31k` overlay (one live text bitmap, re-rendered only on change). Pass your `Clock` as `clock=` for a true FPS reading; `every`/`x`/`y` are keyword args.

### `picogame_scene` — declarative level loader
- `load(pg, scene, display=None, strip_h=None, font=None, bank=None) -> View` — build a scene from a baked SCENE dict.
- `load_bank(pg, bank)` — build a shared asset bank once (reuse across levels).
- `View`: `.tile_xy(px, py)` · `.group(tag)` · `.point(name)` · `.in_zone(x, y, tag=None)` · `.is_solid(tx, ty)` · `.tile_has(tx, ty, prop)` · `.play(sound_id)` · `.tick(dt)`. · `.set_tile_prop(tile, prop, on=True)` — flip a flag for a TILE TYPE at runtime: every cell holding that tile changes meaning at once (a lever makes all gate tiles walkable, ice melts). Complements the native `Tilemap.set_tile`, which swaps ONE cell; tables are copied per `load()`, so changes never leak into other levels sharing a bank.
- `load_json(pg, path, display=None, strip_h=None, font=None, bank=None, release=True) -> View` — bake a level's scene JSON on the device and load it, skipping `scene_build.py`. For ITERATING on a level; ship the pre-baked module. Colour-tileset levels only.

### `picogame_scenebake` — on-device scene baker
- `bake(scene) -> SCENE` — turn an editor scene JSON (already parsed) into the runtime SCENE dict, byte-identical to `tools/scene_build.py`. PNG-backed assets raise `NotImplementedError` (median-cut quantization stays on the desktop).
- Prefer `picogame_scene.load_json()`: it holds the JSON text and the parse tree as locals, which is what keeps the ~17 kB peak transient. Bake EARLY, while the heap is still contiguous.
- Costs ~3.6 kB while imported; `load_json(..., release=True)` drops it after the last level.

### `picogame_mode7` — Mode-7 perspective floor
- `Camera(fov=0.66)` · `.draw(canvas, texture, x, y, angle, horizon, height, y_off=0)` — drive the C `Canvas.mode7` floor from a friendly camera pose (position in world/tile units, heading in radians, `height` = how high the camera sits). `texture` dims must be powers of two, one world unit = one tile. Draw into a 0-RAM `StripDraw` view. See [/helpers/pseudo-3d/](/helpers/pseudo-3d/).

### `picogame_road` — the OutRun scanline road
- `Road(pg, width, height, horizon, colors, *, half_width=0.47, hw_min=6.0, depth=600.0, curves=((16384, 90.0), (4096, 30.0)), world_step=6, curve_step=2, hill_amp=0, edge_frac=0.12, dash_frac=0.07, dash_min_hw=7.0, band=20.0, dash_band=14.0)` · `.tick(dist, lateral_px=0)` (once/frame; positive lateral = the car moved right, the road shifts left) · `.draw(view, vy)` (StripDraw callback body) · `.set_grade(g)` (hills: −1..+1 moves the horizon; needs `hill_amp`) · `.horizon_now` (this frame's effective horizon = horizon + hill pitch — the y overlays and roadside sprites anchor to) · `.curve_at(dist)` (signed curvature −1..+1 for centrifugal pull / AI — the same two-sine model the C runs, zero-alloc) · `.row_of(z)` / `.half_of(row)` / `.edges_of(row)` (place and scale sprites ON the road — the rows are linear, so scale by `half_of`, not `F/(F+z)`) — drives the native `pg.road_edges` + `Canvas.road` pair from human units: curve `periods` in world units (rounded up to powers of two so the int32 phase wrap stays continuous — see the [calling contract](/helpers/pseudo-3d/)), `swing` in px of lateral bend, colors as a dict of six `pg.rgb565` values. Builds every fixed-point table once; `tick()` allocates nothing. See [/helpers/pseudo-3d/](/helpers/pseudo-3d/).

### `picogame_iso` — isometric projection
- `IsoView(ox, oy, tw, th)` (`tw`/`th` = tile half-width/half-height; 2:1 diamond → `th = tw//2`) · `.to_screen(gx, gy, h=0)` · `.depth(gx, gy, h=0)` (back-to-front painter's key) · `.screen_to_grid(sx, sy)` · `.cube_faces(gx, gy, height_px)` (top/right/left faces of a raised block) · `.emit_blocks(cells, tv, tc)` (alloc-free batch: writes flat-shaded cube triangles for many blocks straight into int16/uint16 buffers for ONE `Canvas.fill_triangles` call; returns the triangle count) — the **cheapest pseudo-3D there is**: integer add/shift only, no divide, no C dependency, which is why it runs well on the RP2040. Unlocks iso RPG / strategy / tactics / builder. Static boards: render once + dirty-rect the movers (30 fps); `emit_blocks` is for rebuild-every-frame scenes (~2× faster than a Python `cube_faces` loop). See [/helpers/pseudo-3d/](/helpers/pseudo-3d/).

### `picogame_ray` — first-person raycaster
- `Raycaster(world, wall_colors, sky, floor, fov=0.66, stride=2)` · `.cast(px, py, ang, sw, sh)` (once/frame) · `.draw(view, vx, vy, vw, vh)` (StripDraw callback; **row 0 is the top of the VIEW, not the screen** — a layer starting below y=0, e.g. under a reserved HUD band, must pass `vy - band`) · `.solid(x, y)` (wall test) · `.set_cell(x, y, v)` (change ONE world cell at runtime — a door opening, a wall dropping; v = wall type 0-9, 0 = empty; keeps the caster grid, `solid()` and `.map` consistent and re-casts even for a standing camera. For events, not animation — each call forces one full re-cast) · `.attach(sd)` (temporal repaint) · `.project_sprite(sx, sy)` (billboard) — fully native render: the `pg.raycast` caster (integer 16.16 C on device, Python in the sim) also emits the RLE-merged wall runs, painted with one `Canvas.vspans` batch per strip into a 0-RAM `StripDraw` view (~36 fps uncapped at stride 1 full-screen on RP2040, flat across view angles). `stride` = perf/quality knob; `attach(sd)` + `always_dirty=False` repaints only the changed column band (still/slow ~30 fps). See [/helpers/pseudo-3d/](/helpers/pseudo-3d/).
