# picogame — engine capabilities reference

Ground-truth reference for an AI that designs and **builds** small 2D games with the
`picogame` engine (a CircuitPython native C module + `picogame_*` pure-Python helpers)
for the Pajenicko **PicoPad** (RP2040, 320×240 ST7789) and friends (RP2350, PicoSystem,
ESP32-S3), including the Adafruit **Fruit Jam** (RP2350) over a **DVI/HDMI framebuffer** — the display
class is either an SPI panel or a RAM framebuffer, and `setup()` handles both. This document is a
**self-contained condensation of what you need to design a game**. **For exact signatures, read
`api-reference.md`** (bundled next to this file) — the FULL API: the native C engine (`pg.Sprite`,
`Scene`, `Canvas`, `Tilemap`, `StripDraw`, `Canvas.mode7`, `pg.raycast`, …) AND the helper libs.
The C engine is a compiled native module with **no `.py` to read**, so `api-reference.md` is your
only local source for its signatures. The **helper libs** (`picogame_*.py`) you also have as source
in the distribution — current source **https://github.com/MakerClassCZ/picogame-libs** (its release
ships a bundle of compiled `.mpy` for flashing; on the board a `.mpy` in `/lib` **shadows** the
same-named `.py`, so after editing a library deploy a fresh bundle or the old version keeps running).
Exhaustive prose docs (features, hardware, tutorials) live at **https://picogame.makerclass.cz**.

Everything here is grounded in the docs/code; where something isn't certain it says so.
Colors are **always** wire-order RGB565 built with `pg.rgb565(r, g, b)` — never raw `0xRRGGBB`.

---

## 1. Mental model in 6 lines

1. **Retained `Scene` + dirty-rect:** build the scene once, then each frame *mutate* objects (`spr.x = …`) and call `scene.refresh()`; it diffs vs. last frame and repaints **only the changed regions** (up to 6 disjoint dirty rects) over SPI (nothing changed → nothing sent).
2. **Sprites** are positioned instances of a **Bitmap** (an atlas of equal-size frames; PAL8 1 B/px or RGB565 2 B/px); they carry `x/y` (24.8 fixed-point), `fx/fy` (sub-pixel float), `frame`, `flip_*`, `transpose` (90° diagonal mirror), `scale`, `angle`, `anchor`, `shadow`/`flash`/`tint`/`dither` (blit effects), and a free `data` payload.
3. **Tilemaps** are grids of tile indices into a tileset Bitmap — the cheap way to fill big/scrolling areas (1 byte/cell vs 2 bytes/pixel); only changed cells repaint.
4. **The loop:** `btn.poll()` → update game state → `scene.refresh()` → `clock.tick()` (frame-rate-independent motion via `dt`).
5. **Camera** is `scene.set_view(ox, oy)` (screen position of the scene origin); follow the player + clamp to world edges. Scrolling repaints the whole screen; `fixed=True` layers (HUD) ignore the camera.
6. **Sim-first:** build and validate on PC with `sim/run.py game.py --shot out.png` (headless), iterate on screenshots, *then* ship `.mpy` to the device.

---

## 2. The building blocks & what they COST

Everything visible is a **scene layer** added with `scene.add(item, fixed=False)` (insertion order
= bottom→top; the keyword-only `fixed=True` pins it to the screen, ignoring the camera; `add` returns the item).

| Block | What it's for | RAM cost | Pick it when / instead |
|---|---|---|---|
| **Sprite** | a moving object (player, enemy, bullet, coin, HUD text) | tiny (shares its Bitmap); the Bitmap is the cost | the basic unit; for **many identical** ones use a **Pool**, not N `Sprite()` calls |
| **Bitmap** (PAL8) | sprite/tile pixels, 1 byte/px palette index | `width*height*frames` bytes + small palette | default; 8:1 vs RGB565; index 0 = transparent by convention |
| **Bitmap** (RGB565) | full-color pixels, 2 bytes/px wire order | `width*height*frames*2` bytes | only when >255 colors needed; otherwise PAL8 |
| **Tilemap** | big grid: map, brick wall, board, terrain | `cols*rows` bytes (1 B/cell) + the tileset Bitmap | large/scrolling fields, eat-grids, destructible terrain — never a full-screen pixel buffer |
| **Canvas** | retained shape/HUD surface that changes **rarely** | `width*height*2` bytes (it holds its pixels) | a small framed gauge/panel; **NEVER** full-screen 320×240 (= **150 KB**) on RP2040 |
| **StripDraw** | anything you can **draw from state** without holding pixels: full-frame animated effects (road, gradient sky, plasma, pseudo-3D), but also **text / HUD / panels** (`picogame_ui` is built on it — `HudBar`, text boxes) | **0 bytes** — no pixel buffer | whenever you want to save RAM and drawing is cheap; `always_dirty=True` (default) repaints every frame (animation), `always_dirty=False` + `.invalidate(x,y,w,h)` repaints only the sub-rect you mark (UI-on-change, temporal rendering) |
| **Particles** | many cheap non-interactive dots (sparks, dust, explosions) | one pooled layer, ~`capacity` small entries | bursts/trails; **not** for things needing a bitmap, collision, or individual control |
| **Pseudo-3D** (`Canvas.mode7` floor, `pg.raycast` walls, `pg.road_edges`+`Canvas.road` racing road, `pg.project`+`Canvas.fill_triangles` blocky 3D, `picogame_iso` isometric) | Mode-7 floor (track, flying carpet); first-person walls (dungeon, maze); an OutRun-style road; flat-shaded perspective boxes/low-poly; iso RPG/strategy boards — combinable | **0 bytes** (StripDraw view) except blocky 3D, which draws into a half-res Canvas (~29-38 KB) shown through a 2× Sprite | drive floors/walls via `picogame_mode7`/`picogame_ray`; the road pair takes precomputed per-row tables (device-proven: picobike 15→39 fps); `pg.project` batch-projects points (fixed 16.16 on RP2040, float on FPU boards — **pack buffers per `pg.FPU`**, mixing formats renders garbage); iso needs no new C at all |
| **`render(...)`** | a one-off immediate blit outside any Scene | uses your scratch strip buffer | quick HUD draw, reserved-zone bar (`HudBar`), portable fallback path |

**The Canvas-vs-StripDraw rule:** *pick by whether you need to HOLD pixels, not by size.* Art that
**accumulates** or can't be re-derived from state (user drawing, progressive art) → **Canvas**
(holds pixels, ~0 CPU while unchanged). Anything you can **redraw from state** → **StripDraw** at
0 RAM: per-frame animation (`always_dirty=True`), or UI/HUD repainted only on change
(`always_dirty=False` + `.invalidate()`). A full-screen pseudo-3D road is **150 KB as a Canvas** vs
**0 B as a StripDraw**.

Both surfaces share the **C draw primitives** (fast, in-engine): `pixel/line/rect/fill_rect/circle/
fill_circle/ellipse/fill_ellipse/triangle/fill_triangle/round_rect/fill_round_rect/ring/frame3d/blit`
and **`text(x, y, str, fg, font)`** — text rendered in C into any surface. Because a StripDraw callback's
`view` IS a Canvas onto the live strip, `view.text(...)` gives **0-RAM screen/HUD text** (no glyph
cache, no per-label Bitmap) — the basis of `HudBar`. Use it for custom HUDs and text baked into a
full-frame effect.

`scene.refresh() -> [x1,y1,x2,y2] | None` returns the dirty rect (reused list) or `None`
when nothing changed. First refresh repaints the whole screen. `scene.invalidate()` forces
a full repaint next frame (level change). It tracks up to **6 disjoint dirty rects** — each gets its
own tight SPI window (CASET/RASET clamped to the rect, both axes), so several separated moving
objects stay cheap; only beyond ~6 scattered changes do they merge toward a fuller redraw.

---

## 3. Helper libraries (`lib/picogame_*.py`, pure Python — copy/ship the ones a game imports)

> **This table is the SINGLE SOURCE OF TRUTH for the helper API.** Module names, method names and
> signatures live here only; everywhere else (SKILL.md, techniques.md, genre-patterns.md) names the
> module and points back here rather than restating a signature — so a rename is a one-place edit.
> `tools/check_skill_api.py` greps the skill's `picogame_*` identifiers against `lib/` and fails on a
> mismatch (run it after any lib rename).

| Module | What it gives you | Reach for it when |
|---|---|---|
| `picogame_game` | `setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0, rgb444=False) -> (scene, bufA, bufB)` — one-call display takeover + Scene + 2 strip buffers. `strip_h=None` → the board default `pg.STRIP_H` (**8** on fast/DMA boards, 24 portable); `rgb444=True`/`"auto"` = 12-bit colour (~25% less SPI where the panel supports it). Also `overlay(scene, display, items, buffer, x0,y0,x1,y1, *, background=0)` = `pg.render`+`scene.invalidate()` — draw a pause/menu OVER a live scene with no stale fragments. **Framebuffer/DVI board (Fruit Jam): `setup()` returns `(scene, None, None)`** (no strip buffers; `pg.render` ignores its buffer arg there, and HUD helpers accept a bare `board.DISPLAY` — they normalize it). `open_framebuffer(width, height, color_depth=None)` **before** `setup()` lets a game pick its own DVI resolution in code (e.g. 320×240 for speed, or 640×480 which needs PSRAM); a no-op on fixed SPI panels | every game's boot; `top/bottom/left/right` reserve a HUD border the scene won't touch |
| `picogame_input` | `Buttons(..., usb=None)`: `.poll()`, `.is_pressed/.just_pressed/.just_released(mask)`, `.has(mask)`, `.repeat()`, `.clear()` (flush input on a state/menu transition); masks `UP DOWN LEFT RIGHT A B X Y L1 L2 R1 R2 START SELECT ALL`; **backend auto** = CP `keypad` (HW debounce, no missed taps) else digitalio, **or a scanned ROW×COL matrix** (`settings.toml PICOGAME_MATRIX_ROWS/COLS/MAP`); per-board map via `board_id` profile or `PICOGAME_BUTTONS`. **Auto-attaches a USB HID gamepad AND a USB HID keyboard** as extra OR'd sources on USB-host boards (Fruit Jam) — games get pad/keyboard input with ZERO code change (`picogame_usbpad` / `picogame_usbkbd`, wired or 2.4 GHz dongle; not Bluetooth); `usb=False` off / `usb=True` force; remap via `PICOGAME_USBPAD`. Local multiplayer = one `Buttons` per player via `Buttons(sources=[…])` + `find_pads()` | all button input — portable across boards, incl. a USB gamepad/keyboard |
| `picogame_clock` | `Clock(fps, max_dt=0.1).tick()->dt` (frame cap + dt); `FixedStep(step_fps, max_steps=5).steps()` | `Clock` for smooth/arcade, `FixedStep` for deterministic physics (jumps, stacking) |
| `picogame_shapes` | generate single-color PAL8 bitmaps: `rect/circle/ring/from_mask/atlas/color_frames/tileset_colors/poly_frames` | stop hand-rolling pixel buffers; `tileset_colors` for solid-tile sheets; `poly_frames` to bake rotation frames |
| `picogame_pool` | `Pool(scene, bitmap, capacity, anchor=None, fixed=False)`: `.spawn()->sprite|None`, `.free(s)`, `.free_all()`, `.count()`, `.items` | many of the **same** bitmap (bullets, sparks, pipes) — pre-allocate, never alloc per frame |
| `Sprite.overlaps` / `Sprite.near` | zero-alloc collision built into Sprite: `a.overlaps(b, inset=0)` (AABB; `b` = sprite/point/rect; `inset=N` shrinks the caller's box by N px = the **generous smaller-than-sprite hitbox** §1.4 wants), `a.near(b, r)` (circular, no sqrt) | collision without temp rects, anchor/scale aware |
| `picogame_math` | `clamp/mid/lerp/inv_lerp/remap/sgn/approach/wrap`, turn-trig `sin_t/cos_t/atan2_t`, vectors `length/distance/normalize/angle_rad/from_angle_rad` | game math — scalars, angles (turns), 2D vectors |
| `picogame_anim` | `FrameAnim(sprite, frames, fps=8, loop=True).tick(dt)`; `AnimatedSprite(sprite, {name:(frames,fps,loop)}).play(name).tick(dt)` | time-based / named-state animation (walk/idle/jump) |
| `picogame_ui` | text/box/menu in two render contexts (see the **UI widgets** box below): scene-layer `SceneLabel`/`SceneBox`/`SceneMenu`, immediate `Label`/`TextBox`/`Menu`, plus `HudBar` (reserved-strip) + `GridCursor` (grid logic); `LINE_H=12` | HUD/dialog/menu-driven games (RPG, strategy) |
| `picogame_font` | `render_text(pg, font, text, fg, bg=None)->(bmp,w,h)`, `render_text_pal(...)`, `Label(pg, font, x, y, fg, bg)` — renders any `fontio` font (e.g. `terminalio.FONT`) to a Bitmap | text with no font assets; `bg=None` → transparent |
| `picogame_audio` | WAV/PWM: `Audio(pin=None, voices=4, sample_rate=22050, channels=1, bits=16)` (needs `voices>=2`), `.load/.sfx/.music/.stop/.deinit`; `tone(freq, ms)` **builds** a RawSample you play via `.sfx(tone(...))`. Output auto-picked (see `picogame_audioout`) | recorded SFX / music; **each sample is resident RAM** |
| `picogame_audioout` | `make_output(sample_rate=22050, pin=None)` — the shared output factory `Audio` **and** `Synth` route through: explicit `pin`→PWM, else `board.I2S_BCLK`+TLV320→**I2S** (Fruit Jam; needs `adafruit_tlv320` in `/lib`, silent fallback if absent), else PWM on `board.AUDIO/SPEAKER/BUZZER` or `PICOGAME_AUDIO` | rarely called directly — it's why games need NO board-specific audio code; volume via `settings.toml PICOGAME_HP_VOLUME/DAC_VOLUME/SPK_VOLUME` (dB), output `PICOGAME_AUDIO_OUT=headphone\|speaker\|both`; `PICOGAME_DEBUG=1` prints the real failure reason |
| `picogame_synth` | synthio SFX/MIDI: `Synth()`, `note(...)`, `sfx(n, priority=0, window=0)` (priority classes + protected windows so hit-spam can't erase a boss boom), `sfx_seq(events)`, `Drone` (held engine/siren note fed per frame), `square(duty)` pulse timbres, `set_levels/mute`, `load_midi(...)`; ~0 RAM. **Imports + runs on ANY build** (audio-less/sim degrade to silent no-ops) and `Synth()` **self-guards a failed init** (tight heap / claimed pin) → check module `AVAILABLE` / instance `.available`, **no `try/except` needed** | a big bank of chiptune SFX or sequenced music |
| `picogame_sfx` | `Kit(synth)`: a hardware-tuned signature SFX set built once — `.blip/.coin/.powerup/.zap` (your fire) `/.pew` (enemy) `/.jump/.hit(rotate=True)/.hurt/.boom/.explosion` + `.tick()` per frame; priority classes (hit-spam won't erase a boom); safe no-op on audio-less builds | the **default** SFX set — reach for this before hand-rolling `synth` notes |
| `picogame_save` | `Save(key, schema, *, offset=0)`: `.load()->dict`, `.save(dict)`, `.reset()` — NVM-backed (survives reboot + FS wipe) | high scores / progress / settings; per-game `key`; write on game-over, not per frame |
| `picogame_fx` | `Shake(scene).add(amt)/.tick(camx,camy)`; `Fade(scene,w,h,x=0,y=0,color,cell)` dither fade/dim/flash `.out()/.into()/.dim()/.pulse()/.tick()`; `Tween(v).to(t).tick()`; `Camera(scene, w, h, lerp=0.18, world_w=0, world_h=0).follow(x,y).apply()` (**pass `world_w`/`world_h` by keyword** — positional args after `h` set `lerp` and break the follow); `Sky`, `Scanlines`, `InvertFlash` | JUICE: screenshake, scene transitions / menu dim, value easing, smooth follow camera (composes with Shake), gradient sky, CRT scanlines, full-screen invert flash |
| `picogame_rand` | `Rand(seed)`: `below/randint/random/chance/choice/shuffle/weighted`; `Bag(items,rng).next()` (7-bag anti-streak) | seeded/deterministic randomness — replays, daily seeds, fair spawns/pieces |
| `picogame_input.Timer` | `Timer(frames)`: `.feed(cond)`, `.is_active`, `.consume()`, `.charge()` | input leniency — **coyote time** & **jump buffering** (fair platformers) |
| `picogame_stream` | `StreamSheet(pg, path, w, h, frames, palette, transparent=None)`: `.use(i)` seeks+`readinto`s one frame | a few **big** sprites too large to hold resident; ~one frame of RAM |
| `picogame_arena` | `Arena(pixels)`: `.alloc(nbytes)->memoryview`, `.canvas(w,h)`, `.reset()`, `.free()`, `.mark()/.release(m)` (nested LIFO lifetimes) | dodge heap fragmentation — grab one big buffer up front, slice it (needs firmware `Canvas(buffer=)`) |
| `picogame_debug` | `dbg.ram(tag)` (gc.collect + `free/alloc` print on device, tracemalloc on the sim; a **no-op until `dbg.enabled=True`**, never crashes the game); `Watch(scene)` = a corner `FPS/FREE` overlay, alloc-free between changes | hunt `MemoryError` / measure RAM — use instead of a hand-rolled `gc.mem_free` dance |
| `picogame_scene` | `load(pg, scene, …)->View`; `View`: `.is_solid/.tile_has/.point/.group/.in_zone/.tile_xy/.play/.tick` | data-driven levels baked from the web editor (SCENE_FORMAT.md) |
| `picogame_mode7` | `Camera(fov=0.66).draw(canvas, texture, x, y, angle, horizon, height, y_off=0)` — drives the C `Canvas.mode7` floor from a camera pose (pos in world/tile units, heading rad, `height`=camera height); texture dims must be pow2, one world unit = one tile | a **Mode-7 perspective floor / ground plane** (racer track, flying floor) into a 0-RAM StripDraw view — the fast pseudo-3D path |
| `picogame_iso` | `IsoView(ox, oy, tw, th)`: `.to_screen(gx,gy,h=0)`, `.depth(gx,gy,h=0)` (painter's key), `.screen_to_grid(sx,sy)` (picking), `.cube_faces(gx,gy,h)` (3 visible faces of a block), `.emit_blocks(cells, tv, tc)` — the **alloc-free batch builder**: writes flat-shaded cube triangles for many blocks straight into int16/uint16 arrays for ONE `Canvas.fill_triangles()` call (device: 3.9× faster than looping `cube_faces`) | **isometric** boards — iso RPG / strategy / builder / puzzle. Integer add/shift only, no divide. The idiomatic pattern is a STATIC board rendered once + a few moving unit sprites (dirty-rect) → locked 30 fps on RP2040; `emit_blocks` covers boards that must rebuild per frame (~20 fps at 8×8) |
| `picogame_ray` | `Raycaster(world, wall_colors, sky, floor, fov=0.66, stride=2)`: `.cast(px,py,ang,sw,sh)` (once/frame, drives the native `pg.raycast`), `.draw(view,…)` (StripDraw callback), `.solid(x,y)` (wall test), `.attach(stripdraw)` (temporal repaint), `.project_sprite(sx,sy,margin=0.2)` → `(screen_x, size, depth)` or `None` (billboard enemies, depth-tested), `.zbuf` (Q16 wall distance per column) | first-person **walls/corridors** (dungeon, maze). The per-column DDA is the **native C `pg.raycast`** (integer 16.16) → **~22-30 fps** full-screen RP2040. Two Python levers on top: `.attach(sd)` on an `always_dirty=False` StripDraw repaints only the changed column band and skips the cast entirely when the camera pose is unchanged (a standing/grid-step dungeon is ~30 fps); `stride` (1 sharpest, 3 balanced, 6 fastest) trades wall sharpness for speed. Raise `strip_h` too. Use `mode7` instead if you only need a floor |
| `picogame_seq` | `wait(n)`, `over(n,fn)`, `move_over(spr,x,y,n)` generators; `Seq(gen)`: `.start(gen)`, `.tick()->done`, `.done` | timed/sequenced logic as coroutines — cutscenes, "do X over N frames", staged AI; compose with `yield from` |
| `picogame_tiles` | `TileFlags(flags, tile_px=8)`: `.get(tile,bit=None)`, `.set(tile,bit,value=True)`, `.at(tm,tx,ty,bit)`, `.at_px(tm,px,py,bit)`. `B_SOLID/B_HAZARD/B_LADDER/…`=bit INDICES (for get/set/at/at_px); `SOLID/HAZARD/…`=masks (only for the `{tile:flags}` table) | gameplay properties per tile (solid/hazard/ladder) without a parallel map |
| `picogame_palette` | mutate a PAL8 palette in place: cycle / swap / brightness-fade — ZERO extra art | water/lava shimmer, day-night, hit-tint, fade — many effects from a few array writes |
| `picogame_bitfont` | `render_text(...)` with a tiny built-in bitmap font (no `fontio` dependency) | small fixed HUD text when you don't want to pull `terminalio`/`fontio` |
| `picogame_cutscene` | `palette(pg, rgb)`; `show(pg, display, buffer, path, pal=None, w, h, scale=None, …)` / `play(..., btn, ..., caption=, auto_hold=)` — strip-streams a FULLSCREEN image from a flash FILE band-by-band (~0 RAM); PAL8 or RGB565; `scale=None` auto-derives an integer upscale (160×120 art → 2× on 320×240 = quarter the flash) + optional caption bar + wait-A | title/intro/ending art AND narrative story scenes (bake with tools/bake_cutscene.py — shared palette across a game's scene set) |
| `picogame_options` | `OptionsMenu(scene, pg, font, x, y, w, rows, fg, bg, …)`: rows of kind choice/stepper/toggle/action; `.show()/.tick(btn)->key|CANCEL|None/.value(key)` | a **game** menu with a value per row — shop, recruit, build/upgrade. Don't take it as the default for *settings*, though: tuning parameters (difficulty, effect strength) belong in named constants at the top of the game file — on CircuitPython the player edits them right in the code, so a settings screen is unnecessary. **Provisional** — built on `ui.SceneBox`, kept outside the core `ui` widgets |
| `picogame.value2d/fbm2d` (native) | coherent value-noise + fBm — `value2d/value1d/fbm2d/fbm1d` directly on the `picogame` module | organic variation (terrain, sky) — not gameplay randomness |

### UI widgets — SCENE-LAYER vs IMMEDIATE (pick by render context, NOT by content)

The same content (a label, a text box, a menu) comes in **two render contexts**, and choosing the
wrong one is the #1 UI bug (the widget either flickers or gets clobbered and vanishes):

| Content | **Scene-layer** (`Scene*`) | **Immediate** | When |
|---|---|---|---|
| one line of text | `SceneLabel` | `picogame_font.Label` | label |
| multi-line box | `SceneBox` | `TextBox` | dialog / status / message |
| cursor menu | `SceneMenu` (`show/hide`, `tick→idx`) | `Menu` (`tick→idx`, `draw`) | choice list |

**THE RULE:** is `scene.refresh()` still running under your UI (a live/scrolling/animated scene — an
RPG world, a battle with idle anims/particles)?
- **YES → use the `Scene*` widget.** It's a `fixed` (camera-independent) scene layer that
  `scene.refresh()` paints as part of the frame: one present, no flicker, never clobbered.
- **NO (a fully STATIC screen you draw entirely with `pg.render` — title, pause, settings, or a
  turn screen with no scene.refresh) → use the immediate widget** (`Label`/`TextBox`/`Menu`, drawn
  with `pg.render`). Drawing an immediate widget OVER a live scene is the trap: the scene/fast
  Display pushes its strips over it and erases it (an immediate `Menu` "only appears when you press
  a key"). To draw an immediate widget OVER a live scene ON PURPOSE (pause/menu banner), use
  `picogame_game.overlay(...)` — it wraps `pg.render` + `scene.invalidate()` so the next refresh
  repaints the covered area cleanly. Conversely a `Scene*` widget needs a scene to live in.

Naming: a `Scene*` class is the scene-layer twin of the same-named immediate one (`SceneMenu`↔`Menu`,
`SceneBox`↔`TextBox`, `SceneLabel`↔`Label`). Also: `HudBar` = a strip in a `Scene(top=/bottom=)`
reserved border (0 RAM, `draw()` on change; update a text field with the `label(...)` handle's `.set(text)`); `GridCursor` = grid-cursor LOGIC only (`tick→(tx,ty)`),
you draw the grid + highlight yourself (e.g. tint Tilemap cells for move/attack reach). `SceneMenu`/`Menu`
share the same navigation (paging, wrap, `A`=select→index, `B`=`ui.CANCEL`, `None` while navigating).
Menus assume a non-empty `items` list.

### Naming conventions (the whole API obeys these)

When you write or read engine code, expect these rules; they hold across every module:

- **Per-frame advance = `tick()`.** Rendering = `refresh()` (retained scene) or `draw()` (immediate).
  Input sampling = `poll()`. (So: `btn.poll()`, `fade.tick()`, `menu.tick(btn)`, `anim.tick(dt)`,
  `scene.refresh()`, `clock.tick()`.)
- **Boolean predicates read `is_*`** (`is_pressed`, `is_active`, `is_done`, `is_playing`, `is_solid`,
  `is_within`); tile-property query is `tile_has(tx,ty,prop)`. Edge events keep the `just_` prefix
  (`just_pressed`, `just_released`).
- **Geometry order `x, y, w, h`** (and `x0,y0,x1,y1` for segments). `Fade` is the one deliberate
  exception: `Fade(scene, w, h, x=0, y=0, …)` — full-screen is the default, x/y is an optional offset.
- **Cell/tile coords `tx, ty`**; pixel coords `x, y`; tilemap dims `cols, rows`; pixel dims `w, h`.
- **Color goes last** (`color`); text colors `fg, bg`.
- **Pool size = `capacity`; per-call burst = `count`** (`Particles.emit(x,y,count,…)`,
  `Pool(scene,bm,capacity)`, `pool.count()` = alive count).
- **No-event sentinel = `None`; explicit cancel = `ui.CANCEL`.** `Menu/SceneMenu.tick → idx | None |
  CANCEL`; `GridCursor.tick → (tx,ty) | None | CANCEL`. (Guard before comparing: `if pick is not
  None and pick >= 0`.)
- **`render_text(...) → (bmp, w, h)`** is a tuple (not a bare Bitmap) — hence `render_text`, not
  `*_bitmap`. Optional constructor args are keyword-only.
- Animation: `frames` = count, `fps` = rate, `speed` = per-tick motion.

---

## 4. Core idioms (tiny sketches)

**The game loop**
```python
import picogame as pg, picogame_game, picogame_input, picogame_clock
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(16, 18, 32))
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(60)
dt = 1 / 60                                          # seed BEFORE the loop (first frame uses it)
while True:
    btn.poll()
    if btn.is_pressed(btn.LEFT):  hero.fx -= 120 * dt   # scale by dt for FPS-independence
    if btn.just_pressed(btn.A): fire()
    scene.refresh()                                  # repaints only what moved
    dt = clock.tick()                                # caps FPS, returns real dt (s)
```

**Camera-follow with clamping** (world bigger than screen; keep entities in world coords)
```python
ox = int(max(W - WORLD_W, min(0, W // 2 - hero.x)))   # follow + clamp to world edges
oy = int(max(H - WORLD_H, min(0, H // 2 - hero.y)))
scene.set_view(ox, oy)                                # changing view repaints the whole screen
```

**A Pool spawner** (pre-allocate; `visible` IS the alive flag; `data` holds per-entity state)
```python
import picogame_pool
bullets = picogame_pool.Pool(scene, bullet_bm, 12, anchor=(0.5, 0.5))
b = bullets.spawn()                       # first free sprite, made visible (None if full)
if b: b.move(x, y); b.data = -6           # data = per-entity state: keep it a NUMBER or tuple
for b in bullets.items:                   # zero-alloc iteration  (a string-key dict here is the
    if not b.visible: continue            #  exact anti-pattern the hot-loop guide bans: slower
    b.fy += b.data                        #  + typo-prone; pack multiple fields into a tuple)
    if b.fy < -8: bullets.free(b)         # hide to recycle — never del/create per frame
```

**Runtime rotation / scale** (about the anchor; `1.0`/`0` = fast blit path)
```python
spr.anchor = (0.5, 0.5)                   # pivot at center
spr.scale = 1.6                           # float; integer scales stay crisp, fractional ok (a pulse)
spr.angle = 30                            # degrees; nearest-neighbour, shimmers a little
spr.transpose = True                      # diagonal mirror; + flip_x/flip_y reaches all 8 orientations
```
Use runtime `angle`/`scale` for a **few** sprites or smooth/arbitrary values; **pre-bake
frames** (`shapes.poly_frames` or art) for many or always-rotating sprites and just step `frame`.
For a **crisp quarter-turn** (no shimmer, stays on the fast blit path) use `transpose` + a flip instead
of `angle`: 90° CW = `transpose + flip_y`, 270° CW = `transpose + flip_x` (the footprint swaps w/h).

**Per-sprite blit effects** (cheap juice, no extra bitmaps; one at a time — last set wins):
```python
spr.shadow = True                 # opaque pixels darken the destination (drop shadow / dim)
spr.flash  = pg.rgb565(255,255,255)  # opaque pixels drawn SOLID in this colour -> hit-flash (flat); 0/False = off
spr.tint   = pg.rgb565(255,160,60)   # MULTIPLY the sprite by this colour (keeps shading); 0/False = off
spr.dither = 8                    # Bayer translucency 0..16 (8 ~= 50% see-through); ghosts/fog/fade
```
`flash` is the cheap **hit-flash** (pulse 1–3 frames on impact) — a flat solid-colour silhouette.
`tint` **multiplies** ("colour the source, keep its shading"), so it can only *darken*: tinting a
white/grey sprite gives that colour, but tinting a *coloured* sprite (e.g. a green ship) only muddies
it. **To recolour a coloured sprite BRIGHTLY while keeping its shading, don't tint — rebuild the PAL8
Bitmap with a new `palette` array** (a warm raider from a green one, team colours, day/night) — full
control, no per-pixel cost; or mutate the palette live via `picogame_palette`. `dither` is **fake
transparency** without alpha (fading enemies, ghosts, fog). Animating `dither` repaints automatically;
animating the flash/tint *colour* while it stays on needs `touch()`.

**`sprite.touch()` after mutating a bitmap in place** — *the dirty-rect won't notice
pixels you change directly in a Bitmap's backing buffer.* If you write into a Bitmap's
`data` (or a `StreamSheet`/arena buffer) without changing the sprite's `x/y/frame/bitmap`,
the scene sees no change and skips it. After an in-place pixel edit, mark the sprite dirty.
> `Sprite.touch()` **is** in the engine (it bumps an internal `seq` the
> dirty-rect snapshot compares). It's the correct escape hatch after raw in-place edits — e.g.
> `StreamSheet.use(i)` returns the shared buffer's bitmap, so you call `sprite.touch()` after.
> Always-tracked alternatives if you'd rather not: swap `.bitmap`, step `.frame`, or `scene.invalidate()`.

**StripDraw callback for a full-frame effect** (0 bytes; view-local `(0,0)` == screen `(vx,vy)`)
```python
def road(view, vx, vy, vw, vh):          # view = a Canvas onto the live strip, clipped to the rect
    for ly in range(vh):
        view.fill_rect(0, ly, vw, 1, shade(vy + ly))   # one C primitive per scanline (keep it light)
scene.add(pg.StripDraw(road, 0, 0, 320, 240))          # in a SCROLLING scene, add it fixed: add(sd, fixed=True)
```

**Tilemap as a board you read/write** (eat-grids, destructible terrain, puzzle wells)
```python
tm = pg.Tilemap(tileset, MAP_W, MAP_H)
if tm.tile(tx, ty) == PELLET:            # read (out-of-range reads 0)
    tm.tile(tx, ty, 0)                   # write empty -> single-cell dirty-rect repaint
solid = tm.tile(tx, ty) == WALL          # tile-grid collision = a plain lookup
tm.tile(tx, ty, ROCK, flip_x=True, transpose=True)   # per-cell orientation: all 8 from one tile
tm.fill(0)                               # clear the whole map
```
Per-cell `flip_x`/`flip_y`/`transpose` (a lazily-allocated plane — 0 RAM unless used) get all 8
orientations from ONE tile, pairing with `png2picogame.py --dedup` to shrink the tileset.

---

## 5. RAM budget & the #1 gotcha

RP2040 has **264 KB** SRAM; firmware uses ~72 KB static, leaving **~138–190 KB** Python heap
(treat **~138 KB** as the planning number for the supported RP2040 build — the real figure moves with firmware/build options, so measure YOUR target build with `gc.mem_free()` at boot). RP2350 (Fruit Jam) has **~520 KB** heap — there a
full-screen Canvas (150 KB) *is* affordable. But **RP2040 stays the primary target** (nothing ships
RP2350-only) unless the user explicitly asks otherwise (then build to the RP2350/Fruit Jam budget and
use it fully): design to the RP2040 budget and treat the RP2350 headroom as slack, not a licence. **Assets
dominate** the budget. Concrete costs:

| Thing | Cost |
|---|---|
| `setup()` strip buffers (2 × 320×`strip_h`×2) | default `pg.STRIP_H`: **8** on fast/DMA boards → **~10 KB** (also *faster* — smaller strips overlap DMA better); 24 portable → **30 KB** |
| full-screen `Canvas(320, 240)` | **150 KB** ⚠️ basically the whole RP2040 heap — never do this |
| `Canvas(320, 130)` (pseudo-3D road) | **83 KB** — OK alone, not on top of much else |
| `Canvas(320, 20)` status bar | **~13 KB** — burns RAM for static text; use a `SceneLabel`/`HudBar` instead |
| a Bitmap | `width*height*frames` × (1 B PAL8 / 2 B RGB565) |
| a 320×960 noise sky | **600 KB as a Canvas** vs **~5 KB as a shade Tilemap** |

The **#1 gotcha**: never allocate a big full-frame Canvas. For animated full-frame content use
**StripDraw** (0 B); for big scrolling fields use a **Tilemap** (1 B/cell). Other rules:

- **Ship `.mpy`, not big `.py`.** CircuitPython compiles `code.py` at boot; a large source file's
  parse tree is a RAM spike → `MemoryError` on import. Use a tiny `code.py` launcher (`import my_scene`)
  and precompile with `mpy-cross` **matching the firmware's mpy/CP version** (see FIRMWARE.md; a mismatched `.mpy` won't import).
- **Big data as `bytes`, not an `array` literal.** A huge `array.array('H', [7168, …])` literal →
  `RuntimeError: pystack exhausted` and a ~28 KB transient list. Bake tilesets as PAL8 `DATA = b'…'`.
- **`gc.collect()` between scenes/levels** so the previous scene's buffers free before the next allocates.
- **`strip_h` already defaults small on fast/DMA boards** (`pg.STRIP_H`=8 → ~10 KB); only *raise* it (portable boards) if a scene needs it — don't drop it below the board default, that's both leaner and faster already.
- **`StreamSheet`** streams a big sprite sheet from flash, holding ~one frame in RAM.
- **The arena pattern** (`picogame_arena`): `gc.mem_free()` is *total* free, **not** the largest
  contiguous block — a long session that churns big buffers fragments the heap (90 KB free, 51 KB
  alloc still fails). Grab one big buffer once at boot and hand out slices (`AR.canvas(w,h)`); the
  slices never touch the heap, so they can't fragment. Needs the firmware `Canvas(..., buffer=)` arg.
- **Frozen art** (`FROZEN_MPY_DIRS`) is zero-copy from flash (~0 heap) — CIRCUITPY is FAT flash but
  **not** memory-mapped, so importing a `.mpy` or reading a file **copies it to the heap**. Three
  asset tiers: **frozen** (~0 heap, reflash to change), **file→RAM** via one `readinto` (whole sheet
  resident, swappable), **streaming** (`StreamSheet`, ~one frame). Mix all three.
- ~50 moving sprites ≈ 25 FPS on RP2040; a static background + localized motion → 100+ FPS.

### Measured hot-loop style guide (RP2040 @125 MHz, measured on device)

For per-frame code only — elsewhere write for clarity. All measured on real hardware, not guessed. The **#1 CPU
cost on-device is name lookup** (`mp_map_lookup` is the single hottest interpreter function).

- **Locals beat globals ~2×; hoist hot lookups.** Local read ~0.56 µs, global ~1.13 µs, and a C-object
  attr (`sprite.visible`) ~6.3 µs (worse than a Python inst-attr!). So: **put the per-frame loop in a
  function** (SKILL §1.6 — measured −33 % logic), and bind repeated globals + hot C-attrs to locals once
  (`poll = btn.poll`, `px = spr.x`). `const()` reads are FREE (compile-time) — use for same-module tunables.
- **Clamp with `if/elif`, not `min(max(v,a),b)`** — the builtin form is **~5× slower** (2 builtin
  lookups + 2 calls). (`picogame_math.clamp/lerp` calls also cost ~2× their inline form — convenience API,
  not for per-frame loops.)
- **Math:** `x*x` not `x**2` (2.7×); `math.sqrt(d)` not `d**0.5` (2.2×, `**` goes through generic pow).
  **`int(float)` is the hidden killer** (~16 µs — call + convert) — avoid in row loops (fixed-point
  accumulator instead). Floats themselves are fine: **no allocation** (inline floats on this port) and
  only ~1.4× int — it's the `int()` conversions + name lookups that cost, not float math. `//`/`%` by a
  power of two ≈ a shift (~12 % — don't uglify code for it).
- **`"%d" %` formatting is ~3.6× faster than f-strings / `.format`** (identical on MicroPython — f-strings
  compile to `.format`); a `%.2f` float format is ~0.3-0.4 ms/call → format-on-change, never per-frame.
- **Containers:** `list[i]` beats `array('h')[i]` for speed (arrays only save RAM); `if lst:` is 3× faster
  than `if len(lst) > 0`; `return a, b` (tuple) is fine — out-params aren't faster; avoid `divmod` in hot code.
- **Pools:** scanning usually-empty pools for `visible` is real money (~0.3-0.5 ms/f); keep a `live` count
  and guard `if pool.live:` before iterating.
- **Python↔C boundary tax is ~9-14 µs/call**, so a C helper only pays when the Python work it replaces
  costs much more — **scalar C helpers are pointless; batch** (one array-filling call per frame, not per
  element). `math.sin` bound ≈ 9.9 µs (the RP2040 ROM float-trig is nearly free — the CALL is the cost).
- **`picogame_rand.Rand` is mpz-bound (~247 µs/call)** on this 31-bit-small-int VM — fine at spawn/event
  rate (its real usage), never per-pixel. That cost is the deliberate price of independent seeded
  streams — don't replace it with a global random for speed.

---

## 6. Asset pipeline

A host-side converter emits modules whose colors are **already in wire order**.

**PNG/BMP → `tools/png2picogame.py`** (needs Pillow; auto-picks PAL8 or RGB565):
```bash
python3 tools/png2picogame.py hero.png  -o hero.py  --frames 6            # sprite / h-atlas
python3 tools/png2picogame.py tiles.bmp -o tiles.py --tile 16x16 --transparent-index 15  # tile sheet -> h-atlas
python3 tools/png2picogame.py level.bmp -o level.py --map                 # palette indices ARE tile indices -> Tilemap data
```
Options: `--format auto|pal8|rgb565`, `--frames N`, `--tile WxH`, `--map`, `--transparent-index N`.
PAL8 reserves **index 0 = transparent** (pixels with alpha < 128 → 0). RGB565 mode uses a magenta
color key `(248,0,248)` by default. On device:
```python
import hero, tiles, level
spr = pg.Sprite(hero.bitmap(pg), 40, 120)
tm  = pg.Tilemap(tiles.bitmap(pg), level.WIDTH, level.HEIGHT); level.fill(tm)
```

Emits `DATA` (bytes), `PAL` (array 'H'), `W` (frame width), `H`, `FRAMES`, `STRIDE`, `TRANSP`,
and `bitmap(pg) -> pg.Bitmap`. Frame `i` is columns `i*W .. (i+1)*W`.

**AI art (PixelLab.ai) → PNG → bake with the converter above.** Generate cohesive, optionally animated
pixel-art via the REST API (`https://api.pixellab.ai/v1`, Bearer key — the workspace key is in memory,
not here; full spec at `/v1/openapi.json`). Endpoints: `generate-image-pixflux` (text→sprite),
`generate-image-bitforge` (+ `style_image` for style transfer), `animate-with-text`
(`reference_image`+`action`+`n_frames` → frames), `rotate`, `balance`.
- **Size floors:** pixflux/static **≥ 32×32**; `animate-with-text` **≥ 64×64**, and its `reference_image`
  MUST equal the output size. So **generate big, downscale to device size** (worked: enemies 24 px, boss
  32 px, towers 16 px on a 16 px-tile board).
- **Cohesion lever = `color_image`:** pass a tiny swatch PNG of your shared palette on EVERY call → one
  palette across the whole roster (the cheapest consistency enforcer). **Variants/tiers = recolor the
  palette, never regenerate** (also sidesteps cross-asset drift).
- **Animation:** `animate-with-text` returns ~4 frames for **1 generation** (cheap); use
  `view="high top-down"` for top-down games and bump `image_guidance_scale` (~2.2) so frames stay close
  to the base, then **pick the best 2 frames** (the 2-frame device budget). Animations drift from the
  base — a clear base + high guidance + few frames mitigate it.
- **Prompt explicitly:** "pixel art, top-down view from directly above, <silhouette>, dark body, single
  glowing accent, centered". Vague top-down prompts get misread (a "top-down eel" came back as a stick).
  First-try reliability ~60–70 %; budget 1–3 tries/asset (`usage.generations` = per-call cost; `balance`
  shows USD only — trial credits are tracked separately).
- **Bake:** pre-process in PIL — pick the 2 frames, trim to the alpha bbox (UNION across both frames so
  they stay registered), aspect-fit + pad to a square device size, assemble a horizontal atlas — then
  `tools/png2picogame.py atlas.png -o art.py --frames 2` (emits PAL8 **in wire order**, index 0 transparent).
- **GOTCHA — if you hand-roll a baker** (prefer the converter, which is correct): `pg.rgb565`
  **byte-SWAPS** to wire order (`((c>>8)|(c<<8))`). Build the palette by calling `pg.rgb565(r,g,b)` at
  load (store RGB triplets in the module), NOT a hand-computed 565 int — otherwise every colour is scrambled.
- **Tiles:** PixelLab doesn't produce seamless tiles — use engine solid-colour tiles
  (`shapes.tileset_colors`) for the board, AI art only for sprites/decor.
- Worked example: the SALVO "Abyssal Bloom" roster (4 animated creatures + 3 towers + reef, one abyss palette).

Other tools: `tools/pack_sheet.py` (frame-major `.bin` for `StreamSheet`), `tools/scene_build.py`
(bake declarative scenes), `tools/bake_cutscene.py` (full-screen images for `picogame_cutscene`),
`tools/synth_preview.py` (render SFX to WAV for listening). **Format facts:** PAL8 = 1 byte/px, RGB565 =
2 bytes/px; transparent is index 0 (PAL8) or a wire color (RGB565); always build colors with `rgb565()`.

---

## 7. Sim-first workflow

The simulator (`sim/`, pure-Python `picogame.py` + CircuitPython stubs) has unlimited RAM and a
forgiving API — it's the fastest way to iterate. Build on PC, validate with screenshots, deploy last.

```bash
python sim/run.py game.py                                   # default 150 frames, headless PIL
python sim/run.py game.py --shot out.png                    # save final frame to a PNG
python sim/run.py game.py --frames 300 --shot-at 120 --shot mid.png   # grab frame 120
python sim/run.py game.py --hold RIGHT,B --shot out.png      # hold buttons (input testing)
python sim/run.py game.py --backend pygame                  # live interactive window
```
CLI: `game` (positional), `--frames N` (default 150), `--backend pil|pygame`, `--shot PATH`,
`--shot-at N`, `--hold NAME,NAME` (logical `UP/DOWN/LEFT/RIGHT/A/B/X/Y`), `--profile` (per-frame
timing). Env `PICOGAME_SIM_SIZE=WxH` sets the screen size (e.g. `240x240` for a PicoSystem, `320x240`
default) — smoke a game at BOTH sizes, since games must read `board.DISPLAY.width/height`, not hardcode.
The **headless
screenshot loop is HOW you iterate**: render N frames, dump a PNG, eyeball it, fix, repeat —
no hardware in the loop. Only after it looks right do you ship `.mpy` to the device (and then
re-check the device-only gotchas in §9).

---

## 8. Example catalog (technique → study these)

The shipped games ARE the worked references. Public repo: **https://github.com/MakerClassCZ/picogame**
— `demos/` are single-file games (`demos/picogame_snake.py`), bigger titles are per-game folders
`games/<name>/code.py`, `tutorials/` holds step-by-step teaching games, and `examples/` small
*feature* demos (`*_example.py`, one feature per file). Run via `sim/run.py demos/<name>.py` or
`sim/run.py games/<name>/code.py`. The table maps technique → where to study it:

| Technique | Study |
|---|---|
| **Tilemap world + follow camera** (`set_view`) | `demos/picogame_platformer.py` (platformer: gravity, tile collision, fixed HUD) · `demos/picogame_quest.py` (top-down RPG: AABB-vs-solid-tile, NPC dialog, turn-based battle) · `games/picoracer` (racer: Tilemap track, runtime `sprite.angle` car, best-lap ghost) |
| **Projectile/enemy pools + collision** | `games/squest` (per-sprite state in `sprite.data`, explosion Particles, HUD gauge) · `games/picowing` (vertical shmup: autofire, hit chains, bomb) · `demos/picogame_flappy.py` (the smallest pool demo — endless obstacles sharing one bitmap) |
| **Rotation: runtime vs pre-baked** | `games/picoracer` (runtime `sprite.angle`) vs `demos/picogame_asteroids.py` (`shapes.poly_frames` frames + screen wrap + `near` circular hits) |
| **Grid as the game board** | `demos/picogame_pacman.py` (eat-grid, grid-locked movement + turn queue, 4-ghost AI) · `demos/picogame_maze.py` (procedural maze + fog-of-war) · `games/picotris` (well = Tilemap, dirty-rect cell repaints) · `games/train` (whole board is ONE Tilemap, no sprites) |
| **Juice: Particles / flash / shake** | `demos/picogame_starfall.py` (a complete tiny arcade game — the case study in SKILL.md) · `demos/picogame_missile.py` (particle-heavy blasts) · `demos/picogame_arkanoid.py` (Breakout: bricks + collide + Particles + font HUD) |
| **Menus / text / UI** | `games/picatro` (Balatro-style card deckbuilder: cards as 0-RAM StripDraw, scoring tally) · `demos/picogame_quest.py` (TextBox dialog, battle menu with HP/MP bars) |
| **Turn-based / hot-seat** | `games/bangbang` (artillery duel: destructible terrain, 1P vs AI or two players pass-and-play) |

---

## 9. Gotchas & footguns

> **Debugging first-aid lives in `references/debugging.md`** — typical picogame bugs (byte order,
> stale `.mpy`, `touch()`, pool exhaustion, sim-vs-device gaps) and what to try first when FPS
> drops, the sim crashes, or the heap fragments.

- **RED FLAGS — measure BEFORE building further** (each alone is fine; stacked they sink RP2040):
  camera scroll (full-screen recomposite) **+** >12-16 moving sprites **+** a full-frame
  `always_dirty` StripDraw effect **+** particles — pick the frame budget FIRST and bench the
  combination in the sim + on device (see §7). The engine's own measured walls: full-screen SPI
  refresh has a hard ~24 ms floor (~18.5 ms with `rgb444="auto"` on ST7789), and per-frame Python
  row/entity loops dominate long before the C engine does.
- **`sprite.frame` is forgiving (modulo-wraps).** An out-of-range frame index wraps at render
  (`frame % frame_count`), it does NOT raise. So `spr.frame += 1` cycles an animation safely with no
  manual `% n`. (Defined behaviour -- don't write code that depends on it raising.)
- **Dirty-rect in-place-mutation trap.** Writing pixels directly into a Bitmap buffer (or an
  arena/`StreamSheet` buffer) without changing `x/y/frame/bitmap` leaves the scene blind to it.
  Call **`sprite.touch()`** after an in-place edit (it bumps the dirty-rect `seq`), or use a
  tracked path — swap `.bitmap`, step `.frame`, `StreamSheet.use(i)` then `touch()` — or
  `scene.invalidate()` for a full repaint.
- **Transient UI: build ONCE, toggle `visible` — never re-`add()` per visit.** A repeated
  `scene.add(...)` for a menu/dialog that comes and goes accumulates layers forever (an unbounded
  leak: two real Wyrmfall bugs — a village recruit menu re-added every rest ate the heap). The
  pattern: construct the widgets once (module/game init), keep references, show/hide with
  `visible = False/True`, and only rebuild when the whole scene is rebuilt. `Scene.remove(obj)` is in
  the engine unconditionally, and the UI widgets build on it: a **one-shot** panel calls
  `SceneLabel/SceneBox/SceneMenu.destroy()` when dismissed (teardown so GC reclaims it); **recurring** UI
  is build-once + `set("")`/`hide()`/`show()`. `SceneLabel.reserve(chars)` pre-allocates the text buffer
  up front, dodging a later grow-realloc on a fragmented heap.
- **Never pass raw `0xRRGGBB` (or naïve RGB565).** All colors are display **wire byte order** —
  build them with `pg.rgb565(r, g, b)`; raw ints render wrong (byte-swapped/wrong layout).
- **RP2040 RAM ceilings.** No full-screen `Canvas` (150 KB); HUD = `SceneLabel`/`HudBar`, not a
  full-width Canvas bar (~13 KB for nothing); `Canvas(320,130)` ~83 KB only stands alone;
  `gc.collect()` between scenes; split big games one-program-per-scene.
- **Big `.py` → `MemoryError` on import.** Ship `.mpy` + a tiny launcher; huge `array` literals →
  `pystack exhausted` (use `bytes`).
- **Reading pixels from the screen for collision doesn't work.** Classic destructible bunkers
  (Invaders) are done in other engines by reading/erasing framebuffer pixels — picogame is retained,
  there's no readable composited frame.
  Substitute **tile/Canvas erosion** (carve cells/pixels in a Tilemap or Canvas + `touch()`) and
  collide against that data, not the screen. (See `techniques.md`.)
- **You don't need fixed-point in game logic.** Write plain floats (`sprite.fx/fy` are sub-pixel) —
  readable, and not the bottleneck. The engine already uses integer fixed-point in its own C hot
  paths (rotate/scale, mode7, raycast) because the M0+ has no FPU — you don't hand-roll it.
- **Sim accepts what the device rejects.** The C `Scene` binding exposes `.display` (getter),
  `.add_all(items)` and `.view` (current offset), so those work on both — but `picogame_game.setup`
  still hides the display takeover and is the path to use. `scene.add(item, fixed=True)` uses the
  keyword-only `fixed` flag on both sim and device. The general rule below still holds: raw scene
  code that leaned on sim-only conveniences can crash on device.
- **Native (C) methods take POSITIONAL args only — keyword args are a sim-only luxury.** The sim's
  Python methods accept kwargs, but firmware C bindings often don't: `parts.emit(x, y, count, speed,
  life, color)` works on both, while `parts.emit(x, y, count, color=FIRE)` raises `TypeError: function
  doesn't take keyword arguments` **only on device**. Call native *methods* positionally ALWAYS — even
  when you're only writing/testing in the sim. (Exception:
  args declared kw-only in the binding — e.g. the `Particles(cap, size=…, gravity=…, fade=…)`,
  `Canvas(…, transparent=…, buffer=…)`, `scene.add(item, fixed=True)` constructors/flags — DO require
  keywords on both. So: constructor kw-only = keyword; everything else native = positional.)
- **The firmware must contain the feature.** `AttributeError`/`can't set attribute` usually means
  the flashed firmware predates the API you call (e.g. old build had `Sprite.scale` read-only).
  Verify without flashing: `arm-none-eabi-nm build-…/firmware.elf | grep sprite_set_scale`. In-game,
  probe `getattr(pg, "API_LEVEL", 0)` (the engine exposes `pg.API_LEVEL`, an int, currently **1**) as
  the sanctioned capability check; the `nm`/elf grep is the offline fallback.
- **Anchor + rotation/scale interplay.** `scale`/`angle` pivot about the `anchor` (fractions of the
  bitmap, e.g. `(0.5,0.5)` center, `(0.5,1.0)` bottom-center); `x/y` then refer to that pivot, so a
  centered sprite grows/spins in place. `collide.*` only works cleanly when both sprites share the same
  anchor (the offset cancels). `scale=1.0, angle=0` is the fast blit path — leave them there when idle.
- **Camera repaints everything.** `set_view` changes repaint the whole screen (no dirty-rect win
  while scrolling). StripDraw is screen-space → add it `fixed=True` in a scrolling scene or it smears.
- **`fast=` rarely matters.** The DMA `Display` only beats portable `bus.send` when a repaint spans
  multiple strips (full-frame / heavy blit, ~5–30%); for normal dirty-rect games it's ~0%. Leave
  `fast=True`; it self-downgrades to portable where no backend exists.
- **Noise ≠ randomness.** `value2d/fbm2d` are smooth and correlated (terrain/sky); use a PRNG for
  spawns/drops. On device noise is the fast fixed-point C impl.
- **Audio is opt-in / silent by default.** The sim is silent, but **no import guard is needed** —
  `picogame_synth`/`picogame_sfx` import and run everywhere, degrading to silent no-ops (`Synth()`
  self-guards a failed init; branch on `.available`). `picogame_audio.Audio()`, by contrast, *raises*
  if it can't open an output. Each `picogame_audio.load()` sample stays resident in RAM. Preview synth
  SFX with `tools/synth_preview.py` (the sim can't play them).
- **Don't churn objects.** Never create/free sprites or big buffers per frame — pre-allocate (Pool,
  arena); the GC is non-moving, so churn fragments the heap.
