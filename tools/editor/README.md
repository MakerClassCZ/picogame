# picogame level editor

<!-- ARCHIVED / INTERNAL — not a published page. The live editor doc is the hand-authored
     site/src/content/docs/tools/editor.mdx (its prose was folded in there once); build-content.py
     only keeps a LINKMAP redirect from this file to /tools/editor/. The text below (incl. the
     feature roadmap) is stale — do NOT copy it back into the site; edit editor.mdx instead. -->

A zero-install, zero-dependency **web editor** for picogame scenes/levels. Import real
sprite/tileset PNGs, paint tilemaps (with per-tile solid/coin/goal/hazard flags), place
sprites, HUD labels, zones, spawn points and particle layers, set up a follow-camera, and
export the `scene.json` that `tools/scene_build.py` bakes for the device/simulator.

It is **viewport-first**: the canvas is a window onto a world that can be far larger than
one handheld screen, so authoring **scrolling levels (bigger than one screen) is native**.

## Start here
Open the editor and use the **Demos** menu (top bar) to load a ready-made level:

- **Sample (one screen)** — a compact one-screen platformer showing every feature.
- **Scrolling platformer (bounded)** — a 960×240 world (~3 screens wide), follow-camera on
  **axis x** with bounds = the finite world, so the camera **clamps** at the left/right
  ends. The "level with definite ends" pattern.
- **Open world (bigger both ways)** — a 640×480 quest map (bigger than the screen in both
  dimensions), follow-camera on **axis xy**, so you free-roam in x *and* y.

The two scrolling demos are the fastest way to **learn the big-map workflow**: load one,
then inspect its **Map size** (Paint panel) and **Camera** (Select, nothing selected) to
see exactly how a scrolling level is built. The first-run getting-started card offers the
same demos; press **?** any time for the shortcut cheatsheet.

## World size vs. device screen (the key distinction)
Two sizes matter, and the editor shows them as a pair in the **Level** panel (Select tool,
nothing selected):

- **World size** — how big the **whole level** is, in **pixels**. This is the headline
  "how big is my level" knob and the single source of truth for the world extent: it drives
  the camera bounds, **Fit**, the minimap, and the size of new tilemap layers. A live
  readout shows "≈ N × M screens".
- **Device screen** — one handheld view (320×240 by default), drawn as the dashed **white
  box** on the canvas. Build a World size bigger than one screen to get a level that scrolls.

## Make a level that scrolls (the whole point)
1. In the **Level** panel (Select tool, nothing selected), set **World size** bigger than
   one screen — type `world w×h` and **Apply world size**, or use a preset: **1 screen**,
   **3× wide** (a scrolling platformer), **2×2 screens** (an open world). The editor offers
   to grow/crop your tilemap layers to fill the new world.
2. Pick the **Paint** tool and a tileset (import a PNG or add a colour tileset); a new layer
   already fills the whole world. Paint your ground/platforms across it. **Pan** (Space-drag,
   middle-drag, or the Pan tool) and the **minimap** (top-right) to move around; **Fit**
   frames the whole world, **100%** returns to 1:1.
3. Place a sprite and name it `player` (Select tool → *name* field).
4. In **Select** set **Camera → follow → player**. Leave bounds on *auto* (= the whole
   World size) or uncheck it to drag an explicit orange **camera-bounds** frame.
5. **Export → scene.json**, keep the PNGs beside it, and bake.

Changing World size (or a layer's own size) pads with empty tiles on grow, and crops with a
**confirm** if painted tiles would be lost. Everything is undoable.

The per-layer **Layer size** control (Paint panel) is the advanced knob — a single layer can
be smaller than the world or offset within it (parallax). **World size** is the headline.

## Tools
| Tool | Key | Does |
|------|-----|------|
| Select | 1 / V | Pick + move objects (drag). Click a stacked spot again to cycle. Edit tile flags/colour. |
| Paint | 2 / B | Paint the active tilemap layer. Drag = brush, **Shift-drag = rectangle**, **Alt-click = flood fill**. |
| Place | 3 / P | Drop the chosen sprite on the map. |
| HUD | 4 | Camera-fixed text label (e.g. a score). Also manages **particle layers**. |
| Zone | 5 | Drag a trigger rectangle, then tag it. |
| Point | 6 | Drop a named point (e.g. `spawn`). |
| Pan | H / Space | Pan the view (or hold Space in any tool; middle-drag also pans). |

**Navigation:** wheel scrolls, **Shift+wheel** scrolls horizontally, **Ctrl/⌘+wheel** zooms to the cursor, `+`/`−` zoom, `F`
fits. Arrows nudge the selection (Shift = ×10), or pan the camera when nothing is selected.

**Editing:** `Ctrl+Z`/`Ctrl+Y` undo/redo (everywhere), `Ctrl+C`/`V`/`D` copy/paste/
duplicate, `Delete` removes the selection, `Esc` deselects. No blocking `prompt()`/
`alert()` — inputs are inline panel fields and feedback is non-blocking toasts.

## Tile flags
A flag gives a tile a **meaning the game reads** — it does not change how it looks. The
loader builds fast lookup tables so the game asks the meaning instead of hardcoding numbers:

| flag | the game reads it as | typical use |
|------|----------------------|-------------|
| solid | `view.is_solid(tx, ty)` | walls / floor that block movement |
| coin | `view.tile_has(tx, ty, "coin")` | collectible removed on pickup |
| goal | `view.tile_has(tx, ty, "goal")` | level exit / win tile |
| hazard | `view.tile_has(tx, ty, "hazard")` | lava / spikes that hurt |

Toggle **Show flag badges on map** (Paint panel) to see coloured corner badges.

## Bake & run
Keep the imported/exported PNGs next to the downloaded `scene.json`, then:
```sh
python3 tools/scene_build.py my.scene.json        # -> my_scene.py (SCENE = {...})
python3 sim/run.py <a consumer that imports my_scene>   # preview in the simulator
tools/build_mpy.sh                                # optional: my_scene.mpy for the device
```
Load it with `picogame_scene.load(pg, my_scene.SCENE, font=...)`.

## Architecture (vanilla JS, no build step)
Small single-responsibility files attached to a shared `window.PG*` namespace:

- `core.js` — **pure, DOM-free** model + exporters + save/load + migrations +
  `resizeTilemap`/`levelBounds`. The single source of the on-disk formats. Node-testable.
- `viewport.js` — `Viewport`: `screenToWorld` / `applyTransform` / `pan` / `zoomAt` /
  `fit`. The one place world↔screen mapping lives.
- `history.js` — undo/redo snapshot stack (the project is plain JSON).
- `render.js` — world-space canvas rendering + overlays (one-screen guide box, grid,
  camera-bounds frame, world extent).
- `minimap.js` — birds-eye of the whole world + click/drag-to-jump.
- `app.js` — DOM shell: state, contextual right panel, a **tool dispatch table**
  (`onDown/onMove/onUp` per tool), keyboard, toasts, overlays, file/top-bar actions.

### Tests
`node test.js` covers the export shape (scene + project), the project round-trip,
migrations (flat→levels, single `tilemap`→`tilemaps[]`), `resizeTilemap` grow/crop, and a
sample round-trip. The full export→bake→load path is validated end-to-end in the simulator.

## Data contract (do not drift)
The exported JSON is consumed **unchanged** by `tools/scene_build.py` (see
`../SCENE_FORMAT.md`). Project files (`*.pgproj.json`) load old shapes via the migrations
in `core.js`. Both are load-bearing — real games depend on them.

## Serving standalone
The Sample button and Load use `fetch`, which browsers block on `file://`:
```sh
cd editor && python3 -m http.server 8753     # then open http://localhost:8753/
```
