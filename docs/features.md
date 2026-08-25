# picogame — what to use for what

One page, one job: you know what you want to build — this index says **which piece to use**
and links the page that explains it. (New to the engine? Read
[How picogame works](/concepts/how-it-works/) first.)

## Drawing & the screen

RAM at a glance: a retained full-screen `Canvas` ≈ 150 KB; `StripDraw` / `Tilemap` ≈ 0 — full costs in [Drawing paths](/concepts/drawing-paths/).

| I want to… | Use | Details |
|---|---|---|
| show a moving object (player, enemy, bullet) | `Sprite` | [Reference](reference.md) |
| draw a map / big scrolling world | `Tilemap` (1 B per cell) | [Drawing paths](/concepts/drawing-paths/) |
| draw an animated full-screen effect cheaply (sky, road, gradient) | `StripDraw` (no retained buffer) | [Drawing paths](/concepts/drawing-paths/) |
| a panel that changes rarely (framed box, gauge) | `Canvas` (retained `w*h*2` B) | [Drawing paths](/concepts/drawing-paths/) |
| a status bar / HUD / dialog / menu | `picogame_ui` widgets — pick by the decision matrix | [Drawing paths](/concepts/drawing-paths/) · [Text & UI](/helpers/text-ui/) |
| rotate / scale a sprite at runtime | `Sprite.scale` / `Sprite.angle`; bake frames for many always-rotating objects | [Building scenes](/helpers/building-scenes/) |
| recolour / flash / ghost a sprite without extra bitmaps | blit effects `flash` / `tint` / `dither` / `shadow` (one at a time) | [Reference](reference.md) |
| a crisp 90° turn without shimmer | `transpose` + flips (all 8 orientations) | [Reference](reference.md) |
| follow the player with a camera | `scene.set_view(ox, oy)` + `fixed=True` HUD layers | [Game patterns](/concepts/patterns/) |
| screen shake / fade / smooth camera | `picogame_fx` | [Effects & juice](/helpers/effects/) |
| animated water/lava, palette cycling | `picogame_palette` | [Effects & juice](/helpers/effects/) |
| lots of small sparks / debris | `Particles` | [Reference](reference.md) |
| terrain / sky that varies naturally | C noise: `value2d` / `fbm2d` | [Reference](reference.md) |
| a pseudo-3D floor or first-person walls | `Canvas.mode7` (floor, via `picogame_mode7`) / `picogame_ray` (walls) — both into a `StripDraw` | [Pseudo-3D](/helpers/pseudo-3d/) |
| real flat-shaded polygon 3D (blocky worlds, low-poly) | `pg.project` (batch projection, float/fixed per `pg.FPU`) + `pg.Triangles` (C-composited batch layer; `Canvas.fill_triangles` on the canvas path) | [Pseudo-3D](/helpers/pseudo-3d/) · [Reference](reference.md) |
| an isometric board (RPG / tactics / builder) | `picogame_iso.IsoView` (integer-only projection + painter's key + `emit_blocks` batch) | [Pseudo-3D](/helpers/pseudo-3d/) |
| an OutRun-style racing road at 30 fps | `pg.road_edges` + `Canvas.road` (per-scanline loop in C, into a `StripDraw`) | [Reference](reference.md) |

## Gameplay

| I want to… | Use | Details |
|---|---|---|
| detect hits | `a.overlaps(b)` (box), `a.near(b, r)` (circle), `picogame_tiles` (grid probe) | [Math & collision](/helpers/math/) |
| fire lots of bullets / spawn enemies | `picogame_pool.Pool` — reuse frequently created sprites | [Snippets](/snippets/) |
| animate a sprite (walk/idle/explode) | `sprite.frame` by hand, or `picogame_anim` time-based | [Animation](/helpers/animation/) |
| cutscene / title image with no frame buffer | `picogame_cutscene` (streams from flash) | [Animation](/helpers/animation/) |
| read the buttons through one API | `picogame_input.Buttons` | [Input & controls](/helpers/input/) |
| play with a USB gamepad or keyboard (USB-host boards, e.g. Fruit Jam) | `picogame_usbpad` / `picogame_usbkbd` (auto-attached via `Buttons`) | [Input & controls](/helpers/input/) |
| give each player their own controller (local multiplayer) | one `Buttons(sources=[pad])` per player + `find_pads()` | [Input & controls](/helpers/input/#local-multiplayer) |
| coyote time / jump buffering | `picogame_input.Timer` | [Boot & game loop](/helpers/boot-loop/) · [Snippets](/snippets/) |
| frame-rate-independent motion | `picogame_clock.Clock` (dt) / `FixedStep` (deterministic) | [Boot & game loop](/helpers/boot-loop/) |
| seeded / deterministic random, fair spawns | `picogame_rand` | [Math & collision](/helpers/math/) |
| play sounds (samples vs synth vs MIDI) | `picogame_audio` (WAV) / `picogame_synth` (synthio) | [Audio & music](/helpers/audio/) |
| a ready-made signature SFX set (no note-tuning) | `picogame_sfx` (`Kit` over `picogame_synth`) | [Audio & music](/helpers/audio/#picogame_sfx) |
| save a high score (to *display* a score on screen, see [Text & UI](/helpers/text-ui/)) | `picogame_save` (NVM) | [Saving & memory](/helpers/data/) |
| author many levels | the declarative scene format + editor; hand-code small ones | [Scene format](scene-format.md) · [Building scenes](/helpers/building-scenes/) |
| pause / menu over a live scene | `picogame_game.overlay()` | [Snippets](/snippets/) |

## Fitting the device

| I want to… | Use | Details |
|---|---|---|
| make it fit in RAM | budget → measure → optimize | [Fit it in RAM](memory.md) |
| keep a steady frame rate | game loop in a function, dirty-rect-friendly motion, 0-RAM layers | [Performance](/performance/) |
| store big art / many frames | frozen vs file→RAM vs streaming (`picogame_stream`) | [Fit it in RAM](memory.md) |
| shrink a tileset | `png2picogame.py --dedup` (merges rotated/mirrored tiles) | [Engine guide](engine.md) |
| understand fast DMA vs portable rendering | `pg.Display` backend vs plain busdisplay | [Engine guide](engine.md) |
| run at 640×480 over HDMI (Fruit Jam) | `CIRCUITPY_DISPLAY_COLOR_DEPTH = 8` (RGB332, auto-handled by `setup()`) | [Run on hardware](hardware.md) |
| run on a board I wired myself | prebuilt generic firmware + `settings.toml` (`PICOGAME_BUTTONS`, display, matrix, USB keys) | [Custom board](custom-board.md) |
| deploy to the device / troubleshoot | `.mpy`, lib bundle, serial console | [Run on hardware](hardware.md) |

Every row's *Details* page carries the behaviour, the costs and the gotchas — this page
deliberately repeats none of it.
