// picogame editor -- interactive shell over the DOM-free model (core.js). VIEWPORT-FIRST:
// the canvas is a window onto a world that can be far larger than one screen. All pointer
// handling goes through vp.screenToWorld / render.js draws through vp.applyTransform, so
// authoring bigger-than-screen maps is native (pan/zoom/minimap/one-screen guide box).
//
// Design for a first-time user: labelled+tooltipped tools, a getting-started overlay, an
// always-available shortcut cheatsheet, non-blocking toasts (no prompt/alert), undo
// everywhere, and an obvious "Map size" affordance so making a level scroll is discoverable.
//
// Files: core.js (model/exporters/save-load), viewport.js, history.js, render.js,
// minimap.js. Tools are a dispatch table (onDown/onMove/onUp per tool) so adding one is local.
"use strict";
// Wrapped in an IIFE so all top-level const/let are FUNCTION-scoped, not global. The Astro embed
// (SceneEditor.astro) re-loads app.js on every open to re-init against the freshly-built DOM; without
// this wrapper the second load re-declares these globals -> "Identifier 'E' has already been declared"
// SyntaxError, which aborts app.js so the freshly-built buttons never get their handlers.
(function () {
const E = PGEditor, VP = PGViewport, HIST = PGHistory, R = PGRender, MM = PGMinimap;

// ---------------------------------------------------------------- DOM handles
const $ = function (id) { return document.getElementById(id); };
const canvas = $("canvas");
const ctx = canvas.getContext("2d");
const panel = $("panel");
const minimap = $("minimap");
const mmCtx = minimap ? minimap.getContext("2d") : null;

// ---------------------------------------------------------------- state
const FLAGS = R.FLAGS, FLAG_COLOR = R.FLAG_COLOR;
const TOOLS = ["select", "paint", "place", "hud", "zone", "point", "pan"];
const TOOL_META = {
  select: { key: "1", icon: "⤡", label: "Select", tip: "Select / move objects (V or 1). Click stacked items again to cycle; Shift-click = multi-select." },
  paint:  { key: "2", icon: "▦", label: "Paint",  tip: "Paint tiles (B or 2). Drag to paint; Shift-drag = rectangle; hold Alt = flood fill." },
  place:  { key: "3", icon: "☺", label: "Place",  tip: "Place sprites (P or 3). Click the map to drop the chosen sprite." },
  hud:    { key: "4", icon: "⊞", label: "HUD",    tip: "Add a camera-fixed text label (4), e.g. a score." },
  zone:   { key: "5", icon: "▭", label: "Zone",   tip: "Drag a trigger rectangle (5), then tag it." },
  point:  { key: "6", icon: "✕", label: "Point",  tip: "Drop a named point (6), e.g. a spawn." },
  pan:    { key: "H", icon: "✋", label: "Pan",    tip: "Pan the view (H or hold Space). Wheel scrolls, Shift+wheel scrolls sideways, Ctrl+wheel zooms." },
};

let project = E.newProject();
let images = {};              // assetId -> HTMLImageElement
let artURLs = {};             // assetId -> dataURL (persisted in save)
const vp = new VP.Viewport();
const history = new HIST.History(80);

let sel = { asset: null, tileFrame: 1, tool: "select", tm: 0,
            entity: null, hud: null, zone: null, point: null, particle: null, tile: null,
            // MULTI-SELECT: shift-click adds/removes placed objects (sprites, HUD labels, zones,
            // points). Move/delete then apply to all of them; the LAST one clicked stays the
            // "primary" selection so the panel keeps showing its fields.
            multi: [] };
let showFlags = true, showGrid = true;
let pendingImport = null;     // {kind} while the file picker resolves
let clipboard = null;         // {kind, data} for copy/paste
let pickCycle = { x: null, y: null, i: 0, n: 0 };
let toasts = [];

function L() { return project.levels[project.current]; }
function curTm() { return L().tilemaps[sel.tm] || null; }
function gridTileSize() { const tm = curTm() || L().tilemaps[0]; const a = tm && project.assets[tm.asset]; return a ? (a.fw || 16) : 16; }

// ---------------------------------------------------------------- small helpers
function hexToRgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function rgbCss(c) { return "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")"; }
function rgbHex(c) { return "#" + c.map(function (v) { return ("0" + (v | 0).toString(16)).slice(-2); }).join(""); }
function idFromName(n) { return n.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_]/g, "_"); }
function isImg(a) { return E.isImg(a); }
function isTileset(a) { return !!a && (a.type === "tileset" || a.type === "tileset_color"); }
function isSprite(a) { return !!a && (a.type === "sprite" || a.type === "bitmap" || a.type === "rect"); }
function assetIds(pred) { return Object.keys(project.assets).filter(function (id) { return pred(project.assets[id]); }); }
function mk(tag, cls, txt) { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
function add(p) { for (let i = 1; i < arguments.length; i++) p.appendChild(arguments[i]); return p; }
function h3(t) { return mk("h3", null, t); }
function hint(t) { const d = mk("div", "hint"); d.innerHTML = t; return d; }

// undo checkpoint: call BEFORE a mutation
function snapshot() { history.push(project); scheduleAutosave(); }

// ---------------------------------------------------------------- session autosave
// Every mutation (snapshot/undo/redo/load) schedules a debounced dump of the full
// project (same shape as Save, incl. art dataURLs) into localStorage, so a stray
// Esc, tab close or back-navigation can't erase work. Restored on the next open.
const AUTOSAVE_KEY = "pg_ed_autosave";
let autosaveTimer = null, autosaveWarned = false;
function autosaveNow() {
  autosaveTimer = null;
  try {
    const sv = E.serialize(project); sv.art = artURLs;
    localStorage.setItem(AUTOSAVE_KEY, JSON.stringify(sv));
  } catch (e) {
    // storage full/blocked: warn once, keep the session usable (manual Save still works)
    if (!autosaveWarned) { autosaveWarned = true; toast("Autosave unavailable (storage full or blocked) — use Save", "err"); }
  }
}
function scheduleAutosave() { if (autosaveTimer) clearTimeout(autosaveTimer); autosaveTimer = setTimeout(autosaveNow, 800); }
function flushAutosave() { if (autosaveTimer) { clearTimeout(autosaveTimer); autosaveNow(); } }
window.addEventListener("pagehide", flushAutosave);
document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") flushAutosave(); });

// ---------------------------------------------------------------- toasts (no alert)
function toast(msg, kind) {
  const box = $("toasts"); if (!box) return;
  const el = mk("div", "toast " + (kind || "info"), msg);
  box.appendChild(el);
  const t = { el: el, until: Date.now() + 3600 };
  toasts.push(t);
  setTimeout(function () { el.classList.add("out"); setTimeout(function () { el.remove(); }, 300); }, 3400);
}

// ---------------------------------------------------------------- thumbnails
function drawThumb(cv, a, id, frame) {
  const c = cv.getContext("2d"); c.clearRect(0, 0, cv.width, cv.height); c.imageSmoothingEnabled = false;
  if (isImg(a) && images[id] && images[id].complete) c.drawImage(images[id], frame * a.fw, 0, a.fw, a.fh, 0, 0, cv.width, cv.height);
  else if (a.type === "tileset_color") { c.fillStyle = rgbCss(a.colors[String(frame)] || a.colors["1"] || [255, 0, 255]); c.fillRect(2, 2, cv.width - 4, cv.height - 4); }
  else if (a.type === "rect") { c.fillStyle = rgbCss(a.color); c.fillRect(2, 2, cv.width - 4, cv.height - 4); }
  else { c.fillStyle = "#0af"; c.fillRect(2, 2, cv.width - 4, cv.height - 4); }
}

// ================================================================ ASSET IMPORT
// PNG import uses inline panel fields for frame size (NOT prompt()). We stash the loaded
// image + dataURL, then the panel shows w/h inputs + a Confirm button.
function importPNG(kind) { pendingImport = { kind: kind }; $("file").click(); }
$("file").onchange = function (ev) {
  const f = ev.target.files[0]; if (!f) { pendingImport = null; return; }
  const fr = new FileReader();
  fr.onload = function () {
    const dataURL = fr.result, img = new Image();
    img.onload = function () {
      pendingImport.img = img; pendingImport.dataURL = dataURL; pendingImport.name = f.name;
      pendingImport.fw = pendingImport.kind === "tileset" ? 16 : img.height;
      pendingImport.fh = img.height;
      renderPanel();
    };
    img.src = dataURL;
  };
  fr.readAsDataURL(f); ev.target.value = "";
};
function confirmImport() {
  const pi = pendingImport; if (!pi || !pi.img) return;
  const id = idFromName(pi.name);
  const fw = Math.max(1, pi.fw | 0), fh = Math.max(1, pi.fh | 0);
  snapshot();
  project.assets[id] = { type: pi.kind, src: pi.name, fw: fw, fh: fh,
    frames: Math.max(1, Math.floor(pi.img.width / fw)), transparent: 0 };
  images[id] = pi.img; artURLs[id] = pi.dataURL;
  sel.asset = id;
  if (pi.kind === "tileset") ensureLayerFor(id);
  pendingImport = null;
  renderPanel(); refreshChrome(); toast("Imported " + id, "ok");
}
function addColorTileset() {
  snapshot();
  const id = "tiles" + Object.keys(project.assets).length;
  project.assets[id] = { type: "tileset_color", fw: 16, fh: 16,
    colors: { "1": [150, 90, 40], "2": [245, 215, 50], "3": [40, 200, 80] } };
  sel.asset = id; sel.tileFrame = 1; ensureLayerFor(id); renderPanel(); toast("Added colour tileset " + id, "ok");
}

// A colour-block placeholder sprite (the `rect` asset the demos use for hero/slime): lets you
// lay out and play a level before any art exists. Swap in a PNG later by removing it.
var SPRITE_PLACEHOLDER_COLORS = [[40, 90, 220], [200, 60, 60], [40, 200, 80], [245, 170, 40], [170, 100, 235], [240, 220, 60]];
function addColorSprite() {
  snapshot();
  const n = assetIds(function (a) { return a.type === "rect"; }).length;
  const id = n === 0 ? "player" : "sprite" + (Object.keys(project.assets).length);
  project.assets[id] = { type: "rect", fw: 12, fh: 16, color: SPRITE_PLACEHOLDER_COLORS[n % SPRITE_PLACEHOLDER_COLORS.length] };
  sel.asset = id; renderPanel(); toast("Added colour sprite " + id + " - click the map to place it", "ok");
}

// ---------------------------------------------------------------- tilemap layers
function ensureLayerFor(assetId) {
  for (let i = 0; i < L().tilemaps.length; i++) if (L().tilemaps[i].asset === assetId) { sel.tm = i; return; }
  addLayer(assetId, false);
}
function addLayer(assetId, fg) {
  const a = project.assets[assetId]; if (!a) return;
  // new layers default to FILL THE WHOLE WORLD (worldSize / tile size), so painting a
  // scrolling level "just works" once World size is set. Shrink a layer later if needed.
  const cr = E.layerSizeForWorld(L(), a);
  L().tilemaps.push(E.newTilemap(assetId, cr[0], cr[1], fg));
  sel.tm = L().tilemaps.length - 1; sel.asset = assetId;
}

// ================================================================ TOOLS
function setTool(t) {
  sel.tool = t;
  document.querySelectorAll(".tool").forEach(function (b) { b.classList.toggle("on", b.dataset.tool === t); });
  if (t === "paint") { if (!isTileset(project.assets[sel.asset])) sel.asset = assetIds(isTileset)[0] || null; if (sel.asset) ensureLayerFor(sel.asset); }
  if (t === "place") { if (!isSprite(project.assets[sel.asset])) sel.asset = assetIds(isSprite)[0] || null; }
  canvas.style.cursor = t === "pan" ? "grab" : (t === "paint" ? "crosshair" : "default");
  renderPanel();
}

function clearSel() { sel.entity = sel.hud = sel.zone = sel.point = sel.particle = sel.tile = null; sel.multi = []; }
function multiHas(o) { return sel.multi.some(function (m) { return m.obj === o; }); }
function multiToggle(kind, obj) {
  const i = sel.multi.findIndex(function (m) { return m.obj === obj; });
  if (i >= 0) sel.multi.splice(i, 1); else sel.multi.push({ kind: kind, obj: obj });
}
function multiArrFor(kind) {
  return { entity: L().entities, hud: L().hud, zone: L().zones, point: L().points, particle: L().particles }[kind];
}
function pick(kind, obj) { clearSel(); sel[kind] = obj; renderPanel(); }

// ---------------------------------------------------------------- render panel router
function renderPanel() {
  panel.innerHTML = "";
  if (pendingImport && pendingImport.img) return panelImport();
  if (sel.tool === "select") panelSelect();
  else if (sel.tool === "paint") panelPaint();
  else if (sel.tool === "place") panelPlace();
  else if (sel.tool === "pan") panelPan();
  else panelQuick();
  updateStatus();
}

// ---- IMPORT confirm panel (replaces prompt() for frame size) ----
function panelImport() {
  const pi = pendingImport;
  add(panel, h3("Import " + pi.kind));
  panel.appendChild(hint("File <b>" + pi.name + "</b> (" + pi.img.width + "x" + pi.img.height + "px). Set the frame size; frames = image width / frame width."));
  fieldNum(panel, "frame w", pi.fw, function (v) { pi.fw = v; });
  fieldNum(panel, "frame h", pi.fh, function (v) { pi.fh = v; });
  const row = mk("div", "row wrap");
  add(row, btn("Import", confirmImport), btn("Cancel", function () { pendingImport = null; renderPanel(); }));
  panel.appendChild(row);
}

// ---- SELECT ----
function panelSelect() {
  if (sel.multi.length > 1) {
    add(panel, h3(sel.multi.length + " objects selected"));
    panel.appendChild(hint("Shift-click to add/remove. Drag or arrow keys move them together; <b>Delete</b> removes all. The fields below edit the last one clicked."));
    const mrow = mk("div", "row wrap");
    const md = btn("Delete " + sel.multi.length + " objects", deleteSelection); md.className = "danger";
    add(mrow, btn("Clear selection", function () { clearSel(); renderPanel(); }), md);
    panel.appendChild(mrow);
  }
  if (sel.entity || sel.hud || sel.zone || sel.point || sel.particle || sel.tile) {
    panel.appendChild(btn("‹ Back to level", function () { clearSel(); pickCycle.n = 0; renderPanel(); }));
    if (pickCycle.n > 1) panel.appendChild(hint("Overlapping here — click the same spot again to cycle (" + (pickCycle.i + 1) + "/" + pickCycle.n + ")."));
    if (sel.tile) tileInspector(panel);
    else { add(panel, h3("Selected")); inspector(panel); }
    return;
  }
  add(panel, h3("Level"));
  fieldText(panel, "name", L().name || "", function (v) { L().name = v; refreshChrome(); });
  fieldColor(panel, "background", L().background, function (c) { L().background = c; });

  worldSizePanel(panel);

  // Device screen size (the one-screen guide box). Pairs with World size above: World =
  // the whole scrollable level; Device screen = one handheld view.
  add(panel, h3("Device screen"));
  panel.appendChild(hint("The dashed white box on the map = <b>one handheld screen</b>. World size (above) is the whole level; build it bigger than one screen to scroll."));
  const sr = mk("div", "row");
  add(sr, mk("label", null, "screen w×h"));
  const sw = mk("input"); sw.type = "number"; sw.value = project.size[0]; sw.style.width = "56px";
  const sh = mk("input"); sh.type = "number"; sh.value = project.size[1]; sh.style.width = "56px";
  sw.onchange = sh.onchange = function () { snapshot(); project.size = [parseInt(sw.value) || 320, parseInt(sh.value) || 240]; renderPanel(); };
  add(sr, sw, sh); panel.appendChild(sr);

  cameraPanel(panel);

  add(panel, h3("Objects"));
  const any = L().entities.length + L().hud.length + L().zones.length + L().points.length + L().particles.length;
  if (!any) { panel.appendChild(hint("Nothing placed yet. Use Paint to make ground, Place to drop sprites.")); return; }
  L().entities.forEach(function (en) { objRow((en.name || (en.tag ? "#" + en.tag : en.asset)), "entity", en); });
  L().hud.forEach(function (hd) { objRow("HUD " + hd.name, "hud", hd); });
  L().zones.forEach(function (z) { objRow("zone " + z.tag, "zone", z); });
  L().points.forEach(function (q) { objRow("• " + q.name, "point", q); });
  L().particles.forEach(function (p) { objRow("fx " + p.name, "particle", p); });
}
function objRow(label, kind, obj) {
  const b = mk("button", "objbtn", label);
  b.onclick = function () { setTool("select"); pick(kind, obj); centerSelection(); };
  panel.appendChild(b);
}

// WORLD SIZE -- the headline "how big is my level" knob (per-level, in pixels). This is
// the single source of truth for the world extent: camera auto-bounds, Fit, the render
// extent, the minimap, and new-layer sizing all read level.worldSize.
function worldSizePanel(box) {
  const lv = L();
  add(box, h3("World size"));
  box.appendChild(hint("How big is the whole level, in pixels. Make it bigger than one screen to scroll. This drives the camera, Fit, and new layers."));
  const wr = mk("div", "row");
  add(wr, mk("label", null, "world w×h"));
  const ww = mk("input"); ww.type = "number"; ww.value = lv.worldSize[0]; ww.style.width = "60px";
  const wh = mk("input"); wh.type = "number"; wh.value = lv.worldSize[1]; wh.style.width = "60px";
  add(wr, ww, wh); box.appendChild(wr);
  // live "≈ N × M screens" readout
  const sx = (lv.worldSize[0] / project.size[0]), sy = (lv.worldSize[1] / project.size[1]);
  const fmt = function (n) { return (Math.round(n * 10) / 10).toString().replace(/\.0$/, ""); };
  box.appendChild(hint("≈ <b>" + fmt(sx) + " × " + fmt(sy) + " screens</b> (one screen = " + project.size[0] + "×" + project.size[1] + ")."));
  box.appendChild(btn("Apply world size", function () {
    applyWorldSize(parseInt(ww.value) || project.size[0], parseInt(wh.value) || project.size[1]);
  }));
  // presets mirroring the demos
  const pr = mk("div", "row wrap");
  add(pr, presetBtn("1 screen", project.size[0], project.size[1]),
        presetBtn("3× wide", project.size[0] * 3, project.size[1]),
        presetBtn("2×2 screens", project.size[0] * 2, project.size[1] * 2));
  box.appendChild(pr);
}
function presetBtn(label, w, h) { return btn(label, function () { applyWorldSize(w, h); }); }

// Set the world size; then offer to grow/crop the tilemap layers to fill it (reusing the
// same confirm-on-lossy-shrink guard as per-layer Map size). Camera auto-bounds re-sync.
function applyWorldSize(w, h) {
  const lv = L();
  w = Math.max(1, w | 0); h = Math.max(1, h | 0);
  snapshot();
  lv.worldSize = [w, h];
  // does filling layers to the new world shrink any of them destructively?
  const anyLayers = (lv.tilemaps || []).some(function (tm) { return !(tm.pos && (tm.pos[0] || tm.pos[1])); });
  if (anyLayers) {
    // preview loss on a clone so the confirm is honest
    const clone = E.clone(project); const clv = clone.levels[clone.current]; clv.worldSize = [w, h];
    const wouldLose = E.fillLayersToWorld(clone, clv);
    const grow = confirm("Resize the tilemap layer(s) to fill the new " + w + "×" + h + " world?" +
      (wouldLose ? "\n\nWarning: some painted tiles fall outside the smaller area and will be deleted." : "\n\n(Grows layers with empty tiles; existing paint is kept.)"));
    if (grow) {
      if (wouldLose && !confirm("This deletes painted tiles outside the new area. Continue?")) { /* keep worldSize, skip resize */ }
      else E.fillLayersToWorld(project, lv);
    }
  }
  if (lv.camera && lv.camera.autoBounds !== false) lv.camera.bounds = [0, 0, w, h];
  doFit(); renderPanel();
  toast("World size " + w + "×" + h + " (≈ " + (Math.round(w / project.size[0] * 10) / 10) + "×" + (Math.round(h / project.size[1] * 10) / 10) + " screens)", "ok");
}

// camera editor: follow target + axis + bounds (auto = whole world, or explicit frame)
function cameraPanel(box) {
  add(box, h3("Camera"));
  const targets = L().entities.filter(function (e) { return e.name; });
  const row = mk("div", "row"); add(row, mk("label", null, "follow"));
  const s = mk("select"); s.appendChild(new Option("(no camera)", ""));
  targets.forEach(function (e) { s.appendChild(new Option(e.name, e.name)); });
  s.value = (L().camera && L().camera.target) || "";
  s.onchange = function () {
    snapshot();
    if (!s.value) { L().camera = null; }
    else {
      const b = E.levelBounds(project, L());
      L().camera = L().camera || { mode: "follow", axis: "x", bounds: [0, 0, b[0], b[1]], autoBounds: true };
      L().camera.target = s.value; L().camera.mode = "follow";
    }
    renderPanel();
  };
  add(row, s); box.appendChild(row);
  if (!targets.length) box.appendChild(hint("Name a sprite 'player' (Place a sprite, then Select it) to enable a follow camera."));
  if (!L().camera) return;
  const cam = L().camera;
  const ar = mk("div", "row"); add(ar, mk("label", null, "axis"));
  const as = mk("select"); ["x", "y", "xy"].forEach(function (v) { as.appendChild(new Option(v, v)); });
  as.value = cam.axis || "x"; as.onchange = function () { snapshot(); cam.axis = as.value; };
  add(ar, as); box.appendChild(ar);
  // bounds mode
  const bl = mk("label", "row");
  const cb = mk("input"); cb.type = "checkbox"; cb.checked = cam.autoBounds !== false;
  cb.onchange = function () { snapshot(); cam.autoBounds = cb.checked; if (cb.checked) { const b = E.levelBounds(project, L()); cam.bounds = [0, 0, b[0], b[1]]; } renderPanel(); };
  add(bl, cb, document.createTextNode(" bounds = whole world (auto)")); box.appendChild(bl);
  if (cam.autoBounds === false) {
    box.appendChild(hint("Explicit camera bounds (orange dashed frame on the map). Drag it with Select."));
    fieldNum(box, "bx", cam.bounds[0], function (v) { cam.bounds[0] = v; });
    fieldNum(box, "by", cam.bounds[1], function (v) { cam.bounds[1] = v; });
    fieldNum(box, "bw", cam.bounds[2], function (v) { cam.bounds[2] = v; });
    fieldNum(box, "bh", cam.bounds[3], function (v) { cam.bounds[3] = v; });
  } else {
    const b = E.levelBounds(project, L()); cam.bounds = [0, 0, b[0], b[1]];
    box.appendChild(hint("Camera can scroll the whole " + b[0] + "×" + b[1] + " world."));
  }
}

function tileInspector(box) {
  const a = project.assets[sel.tile.asset];
  add(box, h3("Tile " + sel.tile.value));
  box.appendChild(hint("Layer " + sel.tile.tm + " (" + sel.tile.asset + "), cell " + sel.tile.cx + "," + sel.tile.cy +
    ".<br><b>Flags/colour apply to EVERY tile of this value</b>. Want one cell different? Paint it with another tile."));
  if (a.type === "tileset_color") {
    const k = String(sel.tile.value);
    if (a.colors[k]) fieldColor(box, "colour", a.colors[k], function (c) { snapshot(); a.colors[k] = c; });
  }
  add(box, h3("Flags")); flagEditor(box, a, sel.tile.value);
  box.appendChild(btn("Paint with this tile", function () { sel.tileFrame = sel.tile.value; setTool("paint"); }));
}

function inspector(box) {
  if (sel.entity) {
    const en = sel.entity;
    fieldText(box, "name", en.name || "", function (v) { en.name = v || null; });
    fieldText(box, "tag", en.tag || "", function (v) { en.tag = v || null; });
    fieldNum(box, "x", en.x, function (v) { en.x = v; });
    fieldNum(box, "y", en.y, function (v) { en.y = v; });
    fieldNum(box, "anchorX", (en.anchor || [0, 0])[0], function (v) { en.anchor[0] = v; }, 0.1);
    fieldNum(box, "anchorY", (en.anchor || [0, 0])[1], function (v) { en.anchor[1] = v; }, 0.1);
    const ea = project.assets[en.asset];
    if (ea && isImg(ea) && ea.frames > 1) fieldNum(box, "frame", en.frame || 0, function (v) { en.frame = v; });
    if (ea && ea.animations && Object.keys(ea.animations).length) {
      const row = mk("div", "row"); add(row, mk("label", null, "anim"));
      const s = mk("select"); s.appendChild(new Option("(none)", ""));
      for (const nm in ea.animations) s.appendChild(new Option(nm, nm));
      s.value = en.anim || ""; s.onchange = function () { snapshot(); en.anim = s.value || null; };
      add(row, s); box.appendChild(row);
    }
    box.appendChild(mk("div", "hint", "data (JSON, read by the game as sprite.data):"));
    const ta = mk("textarea"); ta.rows = 2; ta.value = en.data ? JSON.stringify(en.data) : "";
    ta.onchange = function () { try { en.data = ta.value ? JSON.parse(ta.value) : null; ta.classList.remove("bad"); } catch (e) { ta.classList.add("bad"); toast("data is not valid JSON", "err"); } };
    box.appendChild(ta);
    dupDelRow(box, "entity", en, L().entities);
  } else if (sel.hud) {
    const hd = sel.hud;
    fieldText(box, "name", hd.name, function (v) { hd.name = v; });
    fieldNum(box, "x", hd.x, function (v) { hd.x = v; });
    fieldNum(box, "y", hd.y, function (v) { hd.y = v; });
    fieldColor(box, "fg", hd.fg || [255, 255, 255], function (c) { hd.fg = c; });
    fieldColor(box, "bg", hd.bg || [0, 0, 0], function (c) { hd.bg = c; });
    box.appendChild(hint("Camera-fixed; the game sets its text by name via view.named[...]."));
    dupDelRow(box, "hud", hd, L().hud);
  } else if (sel.zone) {
    const z = sel.zone;
    fieldText(box, "tag", z.tag, function (v) { z.tag = v; });
    fieldNum(box, "x", z.x, function (v) { z.x = v; }); fieldNum(box, "y", z.y, function (v) { z.y = v; });
    fieldNum(box, "w", z.w, function (v) { z.w = v; }); fieldNum(box, "h", z.h, function (v) { z.h = v; });
    box.appendChild(hint("view.in_zone(x, y, tag) returns this when a point is inside."));
    dupDelRow(box, "zone", z, L().zones);
  } else if (sel.point) {
    const q = sel.point;
    fieldText(box, "name", q.name, function (v) { q.name = v; });
    fieldNum(box, "x", q.x, function (v) { q.x = v; });
    fieldNum(box, "y", q.y, function (v) { q.y = v; });
    box.appendChild(hint("view.point(name) returns (x, y)."));
    dupDelRow(box, "point", q, L().points);
  } else if (sel.particle) {
    const p = sel.particle;
    fieldText(box, "name", p.name, function (v) { p.name = v; });
    fieldNum(box, "capacity", p.capacity, function (v) { p.capacity = v; });
    fieldNum(box, "size", p.size, function (v) { p.size = v; });
    fieldNum(box, "gravity", p.gravity, function (v) { p.gravity = v; }, 0.1);
    const bl = mk("label", "row"); const cb = mk("input"); cb.type = "checkbox"; cb.checked = !!p.fade;
    cb.onchange = function () { snapshot(); p.fade = cb.checked; }; add(bl, cb, document.createTextNode(" fade")); box.appendChild(bl);
    box.appendChild(hint("A particle emitter (view.named[name]); the game emits/updates it."));
    dupDelRow(box, "particle", p, L().particles);
  }
}

// copy / paste / duplicate / delete row. The same ops as Ctrl+C/V/D and Delete - as BUTTONS,
// because the shortcuts alone were undiscoverable (stream feedback: "I don't know how to use that").
function dupDelRow(box, kind, obj, arr) {
  const row = mk("div", "row wrap");
  add(row, btn("Copy", function () { doCopy(); renderPanel(); }));
  const pasteBtn = btn("Paste", function () { doPaste(); });
  if (!clipboard) { pasteBtn.disabled = true; pasteBtn.title = "Copy something first (Ctrl+C)"; }
  else pasteBtn.title = "Paste the copied " + clipboard.kind + " (Ctrl+V)";
  row.appendChild(pasteBtn);
  add(row, btn("Duplicate", function () {
    snapshot();
    const c = JSON.parse(JSON.stringify(obj));
    if (c.x != null) { c.x += 12; c.y += 12; }
    if (c.name) c.name = uniqueName(c.name, kind);
    arr.push(c); pick(kind, c); renderPanel(); toast(c.name ? "Duplicated as " + c.name : "Duplicated", "ok");
  }));
  const d = btn("Delete", function () {
    snapshot(); arr.splice(arr.indexOf(obj), 1); clearSel(); renderPanel(); refreshChrome();
    toast("Deleted (Ctrl+Z to undo)", "ok");
  });
  d.className = "danger"; row.appendChild(d);
  box.appendChild(row);
  box.appendChild(hint("Ctrl+C copy · Ctrl+V paste · Ctrl+D duplicate · Delete removes · Ctrl+Z undoes any of it."));
}

// ---- PAINT ----
function panelPaint() {
  add(panel, h3("Tileset"));
  const ts = assetIds(isTileset);
  const strip = mk("div", "strip");
  ts.forEach(function (id) { strip.appendChild(assetChip(id, function () { sel.asset = id; ensureLayerFor(id); renderPanel(); })); });
  panel.appendChild(strip);
  const imp = mk("div", "row wrap");
  add(imp, btn("+ Tileset PNG", function () { importPNG("tileset"); }), btn("+ Colour tileset", addColorTileset));
  panel.appendChild(imp);
  if (!ts.length) { panel.appendChild(hint("Import a tileset PNG or add a colour tileset to start painting.")); return; }
  if (!isTileset(project.assets[sel.asset])) sel.asset = ts[0];

  add(panel, h3("Layers"));
  L().tilemaps.forEach(function (tm, i) {
    const row = mk("div", "lrow");
    const b = mk("button", "pick" + (i === sel.tm ? " on" : ""), tm.asset + (tm.fg ? "  [fg]" : "  [bg]") + "  " + tm.cols + "×" + tm.rows);
    b.onclick = function () { sel.tm = i; sel.asset = tm.asset; renderPanel(); };
    const x = mk("button", "del", "×"); x.title = "remove layer";
    x.onclick = function () { snapshot(); L().tilemaps.splice(i, 1); sel.tm = 0; renderPanel(); toast("Layer removed", "ok"); };
    add(row, b, x); panel.appendChild(row);
  });
  const addrow = mk("div", "row wrap");
  add(addrow, btn("+ bg layer", function () { snapshot(); addLayer(sel.asset, false); renderPanel(); }),
             btn("+ fg layer", function () { snapshot(); addLayer(sel.asset, true); renderPanel(); }));
  panel.appendChild(addrow);

  const tm = curTm();
  if (tm && tm.asset !== sel.asset) panel.appendChild(hint("Active layer uses <b>" + tm.asset + "</b>. Add a layer for <b>" + sel.asset + "</b> to paint its tiles."));

  // ---- PER-LAYER MAP SIZE (advanced/parallax knob; World size is the headline) ----
  if (tm) {
    add(panel, h3("Layer size (this layer only)"));
    panel.appendChild(hint("This sizes <b>just this tilemap layer</b>. To set how big the level is overall, use <b>World size</b> in the Level panel (Select tool). One screen ≈ <b>" +
      Math.floor(project.size[0] / (project.assets[tm.asset].fw || 16)) + "×" + Math.floor(project.size[1] / (project.assets[tm.asset].fh || 16)) + "</b> tiles; a layer can be smaller than the world or offset (parallax)."));
    const gr = mk("div", "row");
    add(gr, mk("label", null, "cols × rows"));
    const ci = mk("input"); ci.type = "number"; ci.value = tm.cols; ci.style.width = "52px";
    const ri = mk("input"); ri.type = "number"; ri.value = tm.rows; ri.style.width = "52px";
    add(gr, ci, ri); panel.appendChild(gr);
    const brow = mk("div", "row wrap");
    add(brow, btn("Apply size", function () { applyMapSize(tm, parseInt(ci.value) || tm.cols, parseInt(ri.value) || tm.rows); }));
    add(brow, btn("3× wider", function () { applyMapSize(tm, tm.cols * 3, tm.rows); }));
    panel.appendChild(brow);
    // pos (world offset) for stacking parallax-ish layers
    const pr = mk("div", "row"); add(pr, mk("label", null, "pos x,y"));
    const px = mk("input"); px.type = "number"; px.value = tm.pos[0]; px.style.width = "52px";
    const py = mk("input"); py.type = "number"; py.value = tm.pos[1]; py.style.width = "52px";
    px.onchange = py.onchange = function () { snapshot(); tm.pos = [parseInt(px.value) || 0, parseInt(py.value) || 0]; };
    add(pr, px, py); panel.appendChild(pr);
  }

  const a = tm ? project.assets[tm.asset] : project.assets[sel.asset];
  add(panel, h3("Tiles"));
  panel.appendChild(hint("Tile 0 = erase. Drag to paint • Shift-drag = rectangle • Alt-click = flood fill."));
  const tilesEl = mk("div", "tiles");
  for (let v = 0; v < E.tileCount(a); v++) {
    const cv = mk("canvas"); cv.width = 28; cv.height = 28;
    if (v === 0) { const c = cv.getContext("2d"); c.strokeStyle = "#889"; c.lineWidth = 2; c.beginPath(); c.moveTo(5, 5); c.lineTo(23, 23); c.moveTo(23, 5); c.lineTo(5, 23); c.stroke(); }
    else drawThumb(cv, a, tm ? tm.asset : sel.asset, v);
    if (v === sel.tileFrame) cv.className = "sel";
    cv.title = v === 0 ? "erase" : "tile " + v;
    cv.onclick = function () { sel.tileFrame = v; renderPanel(); };
    tilesEl.appendChild(cv);
  }
  panel.appendChild(tilesEl);

  if (a.type === "tileset_color") { add(panel, h3("Colours")); colorEditor(panel, a); }

  add(panel, h3("Tile flags")); flagEditor(panel, a, sel.tileFrame);

  const fl = mk("label", "row"); const cb = mk("input"); cb.type = "checkbox"; cb.checked = showFlags;
  cb.onchange = function () { showFlags = cb.checked; }; add(fl, cb, document.createTextNode(" Show flag badges on map")); panel.appendChild(fl);
}

function applyMapSize(tm, cols, rows) {
  const shrinking = cols < tm.cols || rows < tm.rows;
  // preview whether shrink would lose painted tiles; if so confirm (only lossy op confirms)
  const test = { grid: tm.grid.map(function (r) { return r.slice(); }), cols: tm.cols, rows: tm.rows };
  const lost = E.resizeTilemap(test, cols, rows);
  if (shrinking && lost && !confirm("Shrinking will delete painted tiles outside the new " + cols + "×" + rows + " area. Continue?")) return;
  snapshot();
  E.resizeTilemap(tm, cols, rows);
  if (L().camera && L().camera.autoBounds !== false) { const b = E.levelBounds(project, L()); L().camera.bounds = [0, 0, b[0], b[1]]; }
  renderPanel();
  toast("Map is now " + cols + "×" + rows + " tiles", "ok");
}

function colorEditor(box, a) {
  Object.keys(a.colors).map(Number).sort(function (p, q) { return p - q; }).forEach(function (key) {
    const k = String(key), row = mk("div", "swatch");
    const ci = mk("input"); ci.type = "color"; ci.value = rgbHex(a.colors[k]); ci.oninput = function () { a.colors[k] = hexToRgb(ci.value); };
    const lab = mk("label", null, "tile " + k); lab.onclick = function () { sel.tileFrame = key; renderPanel(); };
    const del = mk("button", "del", "×"); del.onclick = function () { snapshot(); delete a.colors[k]; if (sel.tileFrame === key) sel.tileFrame = 1; renderPanel(); };
    add(row, ci, lab, del); box.appendChild(row);
  });
  box.appendChild(btn("+ add colour", function () {
    snapshot();
    const next = Math.max.apply(null, [0].concat(Object.keys(a.colors).map(Number))) + 1;
    a.colors[String(next)] = [200, 200, 200]; sel.tileFrame = next; renderPanel();
  }));
}
function flagEditor(box, a, value) {
  if (value === 0) { box.appendChild(hint("Tile 0 is the eraser — no flags.")); return; }
  const fb = mk("div", "flagbox");
  fb.appendChild(mk("div", "hint", "tile " + value + ":"));
  FLAGS.forEach(function (p) {
    const lab = mk("label"); const cb = mk("input"); cb.type = "checkbox";
    cb.checked = !!(a.props && a.props[String(value)] && a.props[String(value)][p]);
    cb.onchange = function () { snapshot(); E.setTileProp(a, value, p, cb.checked); };
    const sw = mk("span", "flag " + p, "■");
    add(lab, cb, sw, document.createTextNode(p)); fb.appendChild(lab);
  });
  box.appendChild(fb);
  const det = mk("details", "help"); det.appendChild(mk("summary", null, "What do flags do?"));
  det.appendChild(hint("Flags give a tile <b>meaning</b> the game reads — they don't change how it looks:<br>" +
    "<span class='flag solid'>■</span> <b>solid</b> blocks movement (<code>view.is_solid</code>)<br>" +
    "<span class='flag coin'>■</span> <b>coin</b> collectible<br>" +
    "<span class='flag goal'>■</span> <b>goal</b> level exit / win<br>" +
    "<span class='flag hazard'>■</span> <b>hazard</b> hurts the player"));
  box.appendChild(det);
}

// ---- PLACE ----
function panelPlace() {
  add(panel, h3("Sprite"));
  const sp = assetIds(isSprite);
  const strip = mk("div", "strip");
  sp.forEach(function (id) { strip.appendChild(assetChip(id, function () { sel.asset = id; renderPanel(); })); });
  panel.appendChild(strip);
  const imp = mk("div", "row wrap");
  add(imp, btn("+ Sprite PNG", function () { importPNG("sprite"); }), btn("+ Colour sprite", addColorSprite));
  panel.appendChild(imp);
  if (!sp.length) { panel.appendChild(hint("Import a sprite PNG, or add a <b>colour sprite</b> (a placeholder block - no art needed), then click the map to place it. Name one <code>player</code> with Select.")); return; }
  if (!isSprite(project.assets[sel.asset])) sel.asset = sp[0];
  panel.appendChild(hint("Click the map to drop <b>" + sel.asset + "</b>. Set its name/tag/anchor with Select."));

  const a = project.assets[sel.asset];
  if (a.type === "rect") {
    add(panel, h3("Placeholder block"));
    const row = mk("div", "row wrap");
    const wi = mk("input"); wi.type = "number"; wi.value = a.fw; wi.min = 1; wi.style.width = "56px"; wi.title = "width";
    const hi = mk("input"); hi.type = "number"; hi.value = a.fh; hi.min = 1; hi.style.width = "56px"; hi.title = "height";
    const ci = mk("input"); ci.type = "color"; ci.value = rgbHex(a.color);
    wi.onchange = function () { snapshot(); a.fw = Math.max(1, parseInt(wi.value) || 1); renderPanel(); };
    hi.onchange = function () { snapshot(); a.fh = Math.max(1, parseInt(hi.value) || 1); renderPanel(); };
    ci.oninput = function () { a.color = hexToRgb(ci.value); };
    add(row, mk("span", null, "w"), wi, mk("span", null, "h"), hi, ci);
    panel.appendChild(row);
    panel.appendChild(hint("Size in px + colour. Bakes as a solid block on the device; replace it with a PNG sprite of the same size when you have art."));
  }
  if (isImg(a)) {
    add(panel, h3("Animations"));
    a.animations = a.animations || {};
    for (const nm in a.animations) {
      const d = a.animations[nm], row = mk("div", "lrow");
      add(row, mk("span", "pick", nm + ": [" + d.frames.join(",") + "] @" + d.fps));
      const x = mk("button", "del", "×"); x.onclick = function () { snapshot(); delete a.animations[nm]; renderPanel(); };
      row.appendChild(x); panel.appendChild(row);
    }
    // inline animation add (NOT prompt) -- name/frames/fps fields
    const box = mk("div", "addbox");
    const an = mk("input"); an.type = "text"; an.placeholder = "name (walk)";
    const af = mk("input"); af.type = "text"; af.placeholder = "frames 0,1";
    const ap = mk("input"); ap.type = "number"; ap.value = 8; ap.style.width = "48px"; ap.title = "fps";
    add(box, an, af, ap, btn("+ add animation", function () {
      const nm = an.value.trim(); if (!nm) { toast("name the animation", "err"); return; }
      snapshot();
      a.animations[nm] = { frames: (af.value || "0").split(",").map(function (s) { return parseInt(s) || 0; }), fps: parseInt(ap.value) || 8, loop: true };
      renderPanel();
    }));
    panel.appendChild(box);
  }
}

// ---- PAN ----
function panelPan() {
  add(panel, h3("Navigate"));
  panel.appendChild(hint("Drag to pan the view. Or hold <b>Space</b> in any tool, or middle-mouse-drag. Wheel scrolls, <b>Shift+wheel</b> scrolls sideways, Ctrl+wheel zooms to cursor."));
  navButtons(panel);
}

// ---- HUD / ZONE / POINT + Particles list ----
function panelQuick() {
  const titles = { hud: "HUD labels", zone: "Zones", point: "Points" };
  add(panel, h3(titles[sel.tool]));
  panel.appendChild(hint(TOOL_META[sel.tool].tip));
  const list = sel.tool === "hud" ? L().hud : sel.tool === "zone" ? L().zones : L().points;
  list.forEach(function (o) {
    const label = sel.tool === "hud" ? o.name : sel.tool === "zone" ? o.tag : o.name;
    const b = mk("button", "objbtn", label);
    b.onclick = function () { setTool("select"); pick(sel.tool, o); };
    panel.appendChild(b);
  });
  // particles are managed from the HUD tool's panel too (rarely used, keep it discoverable)
  if (sel.tool === "hud") {
    add(panel, h3("Particle layers"));
    L().particles.forEach(function (p) { const b = mk("button", "objbtn", "fx " + p.name); b.onclick = function () { setTool("select"); pick("particle", p); }; panel.appendChild(b); });
    panel.appendChild(btn("+ particle layer", function () { snapshot(); const p = E.newParticles("fx" + L().particles.length); L().particles.push(p); setTool("select"); pick("particle", p); toast("Added particle layer", "ok"); }));
  }
}

// ---------------------------------------------------------------- widget builders
// The asset as a horizontal-strip PNG (the format the editor imports and the baker bakes):
// PNG assets = the imported image itself; placeholders (colour tileset / rect) get their strip
// GENERATED - frame 0 empty, then one flat tile per value - so a user can download the demo's
// "spritesheet", paint over it in an image editor keeping the same frame order, and re-import.
function assetStripDataURL(id) {
  const a = project.assets[id];
  if (isImg(a)) return artURLs[id] || null;
  const c = document.createElement("canvas");
  if (a.type === "tileset_color") {
    const keys = Object.keys(a.colors || {}).map(Number);
    const n = keys.length ? Math.max.apply(null, keys) : 0;
    c.width = a.fw * (n + 1); c.height = a.fh;
    const ctx = c.getContext("2d");
    for (let v = 1; v <= n; v++) {
      const col = a.colors[String(v)]; if (!col) continue;
      ctx.fillStyle = rgbCss(col); ctx.fillRect(v * a.fw, 0, a.fw, a.fh);
    }
    return c.toDataURL("image/png");
  }
  if (a.type === "rect") {
    c.width = a.fw; c.height = a.fh;
    const ctx = c.getContext("2d");
    ctx.fillStyle = rgbCss(a.color); ctx.fillRect(0, 0, a.fw, a.fh);
    return c.toDataURL("image/png");
  }
  return null;
}
function downloadAssetStrip(id) {
  const url = assetStripDataURL(id);
  if (!url) { toast("Nothing to download for " + id, "err"); return; }
  const a = mk("a"); a.href = url; a.download = id + ".png"; a.click();
  const asset = project.assets[id];
  const fw = asset.fw || 16, fh = asset.fh || 16;
  toast("Downloaded " + id + ".png - " + fw + "x" + fh + " frames in a row" +
        (isImg(asset) ? "" : " (placeholder art: paint over it, keep the frame order, re-import)"), "ok");
}

function assetChip(id, onpick) {
  const a = project.assets[id], wrap = mk("div", "chip" + (id === sel.asset ? " sel" : ""));
  const cv = mk("canvas"); cv.width = 40; cv.height = 40; drawThumb(cv, a, id, isTileset(a) && a.type === "tileset_color" ? 1 : 0);
  cv.onclick = onpick;
  const nm = mk("div", "name", id);
  const dl = mk("button", "del dl", "\u2b07"); dl.title = "download this asset as a PNG strip (frames left to right)";
  dl.onclick = function (ev) { ev.stopPropagation(); downloadAssetStrip(id); };
  const del = mk("button", "del", "×"); del.title = "remove asset";
  del.onclick = function (ev) {
    ev.stopPropagation();
    if (!confirm("Remove '" + id + "'? Layers and sprites using it are removed too.")) return;
    snapshot(); E.removeAsset(project, id); delete images[id]; delete artURLs[id];
    if (sel.asset === id) sel.asset = null;
    sel.tm = 0; clearSel(); renderPanel(); refreshChrome(); toast("Removed " + id, "ok");
  };
  add(wrap, cv, nm, dl, del); return wrap;
}
function btn(label, fn) { const b = mk("button", null, label); b.onclick = fn; return b; }
function fieldText(box, label, val, set) {
  const row = mk("div", "row"); add(row, mk("label", null, label));
  const inp = mk("input"); inp.type = "text"; inp.value = val;
  inp.onfocus = function () { snapshot(); }; inp.oninput = function () { set(inp.value); updateStatus(); };
  add(row, inp); box.appendChild(row); return inp;
}
function fieldNum(box, label, val, set, step) {
  const row = mk("div", "row"); add(row, mk("label", null, label));
  const inp = mk("input"); inp.type = "number"; if (step) inp.step = step; inp.value = val;
  inp.onfocus = function () { snapshot(); };
  inp.oninput = function () { set(step ? (parseFloat(inp.value) || 0) : (parseInt(inp.value) || 0)); };
  add(row, inp); box.appendChild(row); return inp;
}
function fieldColor(box, label, val, set) {
  const row = mk("div", "row"); add(row, mk("label", null, label));
  const inp = mk("input"); inp.type = "color"; inp.value = rgbHex(val);
  inp.onfocus = function () { snapshot(); }; inp.oninput = function () { set(hexToRgb(inp.value)); };
  add(row, inp); box.appendChild(row); return inp;
}
function navButtons(box) {
  const row = mk("div", "row wrap");
  add(row, btn("Fit", doFit), btn("100%", function () { vp.setZoom(1); }),
    btn("Zoom +", function () { vp.zoomAt(vp.w / 2, vp.h / 2, 1.25); }),
    btn("Zoom −", function () { vp.zoomAt(vp.w / 2, vp.h / 2, 0.8); }));
  box.appendChild(row);
}

// ================================================================ CANVAS SIZING
function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * dpr));
  canvas.height = Math.max(1, Math.round(rect.height * dpr));
  vp.setSize(rect.width, rect.height, dpr);
}
function doFit() { const b = E.levelBounds(project, L()); vp.fit(b[0], b[1]); }
function centerSelection() {
  const o = sel.entity || sel.hud || sel.point || sel.zone;
  if (o) vp.centerOn(o.x + (o.w ? o.w / 2 : 0), o.y + (o.h ? o.h / 2 : 0));
}

// ================================================================ POINTER -> WORLD
function evScreen(ev) {
  const r = canvas.getBoundingClientRect(), t = (ev.touches && ev.touches[0]) || ev;
  return { sx: t.clientX - r.left, sy: t.clientY - r.top };
}
function evWorld(ev) { const s = evScreen(ev); const w = vp.screenToWorld(s.sx, s.sy); return { x: w.x, y: w.y, sx: s.sx, sy: s.sy }; }

// paint one cell of the active layer at world point p (value = sel.tileFrame)
function paintCell(p, value) {
  const tm = curTm(); if (!tm) return false;
  const a = project.assets[tm.asset];
  const cx = Math.floor((p.x - tm.pos[0]) / a.fw), cy = Math.floor((p.y - tm.pos[1]) / a.fh);
  if (cy >= 0 && cy < tm.rows && cx >= 0 && cx < tm.cols) { tm.grid[cy][cx] = value; return true; }
  return false;
}
function cellAt(p, tm) {
  const a = project.assets[tm.asset];
  return { cx: Math.floor((p.x - tm.pos[0]) / a.fw), cy: Math.floor((p.y - tm.pos[1]) / a.fh) };
}
function floodFill(p, value) {
  const tm = curTm(); if (!tm) return;
  const c = cellAt(p, tm); if (c.cx < 0 || c.cy < 0 || c.cx >= tm.cols || c.cy >= tm.rows) return;
  const target = tm.grid[c.cy][c.cx]; if (target === value) return;
  const stack = [[c.cx, c.cy]];
  while (stack.length) {
    const [x, y] = stack.pop();
    if (x < 0 || y < 0 || x >= tm.cols || y >= tm.rows || tm.grid[y][x] !== target) continue;
    tm.grid[y][x] = value;
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
}

// hit-tests (world coords)
function entityHit(p, en) {
  const a = project.assets[en.asset]; if (!a) return false;
  const fw = a.fw || 16, fh = a.fh || 16;
  const ax = (en.anchor || [0, 0])[0] * fw, ay = (en.anchor || [0, 0])[1] * fh;
  return p.x >= en.x - ax && p.x < en.x - ax + fw && p.y >= en.y - ay && p.y < en.y - ay + fh;
}
function candidatesAt(p) {
  const out = [];
  for (let i = L().entities.length - 1; i >= 0; i--) if (entityHit(p, L().entities[i])) out.push({ kind: "entity", obj: L().entities[i] });
  for (let i = L().hud.length - 1; i >= 0; i--) { const hd = L().hud[i]; if (p.x >= hd.x - 2 && p.x < hd.x + 60 && p.y >= hd.y - 2 && p.y < hd.y + 12) out.push({ kind: "hud", obj: hd }); }
  const z = L().zones.find(function (z) { return p.x >= z.x && p.x < z.x + z.w && p.y >= z.y && p.y < z.y + z.h; }); if (z) out.push({ kind: "zone", obj: z });
  const q = L().points.find(function (q) { return Math.abs(q.x - p.x) < 8 && Math.abs(q.y - p.y) < 8; }); if (q) out.push({ kind: "point", obj: q });
  const t = tileAt(p); if (t) out.push({ kind: "tile", obj: t });
  return out;
}
function tileAt(p) {
  for (let i = L().tilemaps.length - 1; i >= 0; i--) {
    const tm = L().tilemaps[i], a = project.assets[tm.asset]; if (!a) continue;
    const cx = Math.floor((p.x - tm.pos[0]) / a.fw), cy = Math.floor((p.y - tm.pos[1]) / a.fh);
    if (cy >= 0 && cy < tm.rows && cx >= 0 && cx < tm.cols && tm.grid[cy][cx])
      return { tm: i, asset: tm.asset, cx: cx, cy: cy, value: tm.grid[cy][cx] };
  }
  return null;
}
// is world point p inside the camera-bounds frame edge? (for dragging the bounds)
function camBoundsHit(p) {
  const cam = L().camera; if (!cam || cam.autoBounds !== false) return false;
  const b = cam.bounds, edge = 6 / vp.zoom;
  const inX = p.x >= b[0] - edge && p.x <= b[0] + b[2] + edge;
  const inY = p.y >= b[1] - edge && p.y <= b[1] + b[3] + edge;
  const nearEdge = Math.abs(p.x - b[0]) < edge || Math.abs(p.x - (b[0] + b[2])) < edge || Math.abs(p.y - b[1]) < edge || Math.abs(p.y - (b[1] + b[3])) < edge;
  return inX && inY && nearEdge;
}

// ---------------------------------------------------------------- interaction state
let drag = null;              // active drag descriptor (varies by tool)
let rubberRect = null;        // world-space rect being dragged (for render preview)
let tileSelRect = null;       // world-space tile-region marquee (copy source)
let spacePan = false;         // space held -> temporary pan

// TOOL DISPATCH TABLE -------------------------------------------------------------
const tools = {
  select: {
    down: function (p, ev) {
      // drag camera-bounds frame?
      if (camBoundsHit(p)) { snapshot(); drag = { mode: "cambounds", start: p, orig: L().camera.bounds.slice() }; return; }
      const cands = candidatesAt(p);
      if (!cands.length) { clearSel(); pickCycle.x = null; pickCycle.n = 0; renderPanel(); return; }
      const same = pickCycle.x !== null && Math.abs(p.x - pickCycle.x) <= 3 && Math.abs(p.y - pickCycle.y) <= 3;
      pickCycle.i = same ? (pickCycle.i + 1) % cands.length : 0;
      pickCycle.x = p.x; pickCycle.y = p.y; pickCycle.n = cands.length;
      const c = cands[pickCycle.i];
      if (ev && ev.shiftKey && c.kind !== "tile") {           // shift-click: build a multi-selection
        const keep = sel.multi.slice();
        const prim = selectedObjAndArr();
        if (prim && !keep.some(function (m) { return m.obj === prim[0]; })) keep.push({ kind: prim[2], obj: prim[0] });
        clearSel(); sel.multi = keep;
        multiToggle(c.kind, c.obj);
        const last = sel.multi[sel.multi.length - 1];
        if (last) sel[last.kind] = last.obj;                  // primary = last one clicked
        renderPanel();
        return;
      }
      clearSel();
      if (c.kind === "tile") { sel.tile = c.obj; sel.asset = c.obj.asset; sel.tileFrame = c.obj.value; }
      else {
        sel[c.kind] = c.obj;
        if (c.obj.x != null) { snapshot(); drag = { mode: "move", obj: c.obj, ox: p.x - c.obj.x, oy: p.y - c.obj.y }; }
      }
      renderPanel();
    },
    move: function (p) {
      if (!drag) return;
      if (drag.mode === "move") {
        const nx = Math.round(p.x - drag.ox), ny = Math.round(p.y - drag.oy);
        if (sel.multi.length > 1 && multiHas(drag.obj)) {     // move every selected object by the same delta
          const dx = nx - drag.obj.x, dy = ny - drag.obj.y;
          sel.multi.forEach(function (m) { m.obj.x += dx; m.obj.y += dy; });
        } else { drag.obj.x = nx; drag.obj.y = ny; }
        pickCycle.x = null; renderPanel();
      }
      else if (drag.mode === "cambounds") {
        const b = L().camera.bounds; b[2] = Math.max(8, Math.round(p.x - drag.orig[0])); b[3] = Math.max(8, Math.round(p.y - drag.orig[1]));
      }
    },
    up: function () { drag = null; }
  },
  paint: {
    down: function (p, ev) {
      if (!curTm()) { toast("Add a tileset + layer first (Paint panel)", "err"); return; }
      snapshot();
      if (ev.altKey) { floodFill(p, sel.tileFrame); drag = null; renderPanel(); return; }
      if (ev.shiftKey) { drag = { mode: "rect", start: p }; return; }
      drag = { mode: "brush" }; paintCell(p, sel.tileFrame);
    },
    move: function (p) {
      if (!drag) return;
      if (drag.mode === "brush") paintCell(p, sel.tileFrame);
      else if (drag.mode === "rect") { const tm = curTm(); const s = cellAt(drag.start, tm), c = cellAt(p, tm); rubberRectFromCells(tm, s, c); }
    },
    up: function (p) {
      if (drag && drag.mode === "rect") {
        const tm = curTm(); const s = cellAt(drag.start, tm), c = cellAt(p, tm);
        const x0 = Math.min(s.cx, c.cx), x1 = Math.max(s.cx, c.cx), y0 = Math.min(s.cy, c.cy), y1 = Math.max(s.cy, c.cy);
        for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (y >= 0 && y < tm.rows && x >= 0 && x < tm.cols) tm.grid[y][x] = sel.tileFrame;
      }
      drag = null; rubberRect = null;
    }
  },
  place: {
    down: function (p) {
      if (!isSprite(project.assets[sel.asset])) { toast("Pick a sprite in the panel first", "err"); return; }
      snapshot();
      const en = { asset: sel.asset, name: null, tag: null, x: Math.round(p.x), y: Math.round(p.y), anchor: [0.5, 1.0], frame: 0 };
      // The first instance of an asset called "player" IS the player: pre-fill the name the
      // camera/game look for (only if no entity holds it yet - names must stay unique).
      if (sel.asset === "player" && !L().entities.some(function (e) { return e.name === "player"; })) en.name = "player";
      L().entities.push(en); setTool("select"); pick("entity", en);
      drag = { mode: "move", obj: en, ox: 0, oy: 0 };
    },
    move: function (p) { if (drag) { drag.obj.x = Math.round(p.x); drag.obj.y = Math.round(p.y); renderPanel(); } },
    up: function () { drag = null; }
  },
  hud: {
    down: function (p) {
      snapshot();
      const hd = { name: "label" + (L().hud.length + 1), x: Math.round(p.x), y: Math.round(p.y), fg: [255, 255, 255], bg: [0, 0, 0] };
      L().hud.push(hd); setTool("select"); pick("hud", hd); toast("HUD label added — rename it in the panel", "ok");
    }, move: function () {}, up: function () {}
  },
  zone: {
    down: function (p) { snapshot(); drag = { mode: "zone", start: p }; },
    move: function (p) { if (drag) { const s = drag.start; rubberRect = { x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) }; } },
    up: function (p) {
      if (drag && rubberRect && rubberRect.w > 4 && rubberRect.h > 4) {
        const z = { tag: "zone" + (L().zones.length + 1), x: Math.round(rubberRect.x), y: Math.round(rubberRect.y), w: Math.round(rubberRect.w), h: Math.round(rubberRect.h) };
        L().zones.push(z); setTool("select"); pick("zone", z); toast("Zone added — tag it in the panel", "ok");
      } else { history.discard(); }   // no real drag -> drop the checkpoint (no redo entry)
      drag = null; rubberRect = null;
    }
  },
  point: {
    down: function (p) {
      snapshot();
      const q = { name: "point" + (L().points.length + 1), x: Math.round(p.x), y: Math.round(p.y) };
      L().points.push(q); setTool("select"); pick("point", q); toast("Point added — rename it in the panel", "ok");
    }, move: function () {}, up: function () {}
  },
  pan: {
    down: function (p, ev) { const s = evScreen(ev); drag = { mode: "pan", lastSx: s.sx, lastSy: s.sy }; canvas.style.cursor = "grabbing"; },
    move: function (p, ev) { if (drag && drag.mode === "pan") { const s = evScreen(ev); vp.panScreen(s.sx - drag.lastSx, s.sy - drag.lastSy); drag.lastSx = s.sx; drag.lastSy = s.sy; } },
    up: function () { drag = null; canvas.style.cursor = "grab"; }
  }
};

function rubberRectFromCells(tm, s, c) {
  const a = project.assets[tm.asset];
  const x0 = Math.min(s.cx, c.cx), x1 = Math.max(s.cx, c.cx), y0 = Math.min(s.cy, c.cy), y1 = Math.max(s.cy, c.cy);
  rubberRect = { x: tm.pos[0] + x0 * a.fw, y: tm.pos[1] + y0 * a.fh, w: (x1 - x0 + 1) * a.fw, h: (y1 - y0 + 1) * a.fh };
}

// ---------------------------------------------------------------- pointer events
function onDown(ev) {
  ev.preventDefault(); canvas.focus();
  const isMiddle = ev.button === 1;
  const p = evWorld(ev);
  if (isMiddle || spacePan || ev.button === 2) { tools.pan.down(p, ev); drag && (drag.tempPan = true); return; }
  (tools[sel.tool] || tools.select).down(p, ev);
}
function onMove(ev) {
  if (!drag) return; ev.preventDefault();
  const p = evWorld(ev);
  if (drag.tempPan || drag.mode === "pan") { tools.pan.move(p, ev); return; }
  (tools[sel.tool] || tools.select).move(p, ev);
}
function onUp(ev) {
  if (!drag) return;
  const p = evWorld(ev);
  if (drag.tempPan || drag.mode === "pan") { tools.pan.up(); return; }
  (tools[sel.tool] || tools.select).up(p, ev);
}
canvas.addEventListener("mousedown", onDown);
window.addEventListener("mousemove", onMove);
window.addEventListener("mouseup", onUp);
canvas.addEventListener("touchstart", onDown, { passive: false });
window.addEventListener("touchmove", onMove, { passive: false });
window.addEventListener("touchend", onUp);
canvas.addEventListener("contextmenu", function (e) { e.preventDefault(); });

// wheel: scroll pans, shift+wheel pans horizontally, ctrl/cmd+wheel zooms to cursor.
// Deltas are normalized to CSS px first -- Firefox reports whole LINES for a real wheel
// mouse (deltaY ~3), so without this one notch would pan 3 px instead of ~100.
function wheelPx(ev) {
  const k = ev.deltaMode === 1 ? 16            // DOM_DELTA_LINE  -> ~one text line
    : ev.deltaMode === 2 ? vp.h                // DOM_DELTA_PAGE  -> one viewport
      : 1;                                     // DOM_DELTA_PIXEL
  return { x: ev.deltaX * k, y: ev.deltaY * k };
}

canvas.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  const s = evScreen(ev);
  const d = wheelPx(ev);
  if (ev.ctrlKey || ev.metaKey) { vp.zoomAt(s.sx, s.sy, d.y < 0 ? 1.12 : 0.89); return; }
  // Shift folds the vertical delta onto X. Summing (not swapping) is deliberate: some
  // browsers already report shift+wheel as deltaX, and then d.y is 0 -- either way one
  // notch scrolls horizontally exactly once, never twice.
  if (ev.shiftKey) { vp.camX += (d.x + d.y) / vp.zoom; return; }
  vp.camX += d.x / vp.zoom; vp.camY += d.y / vp.zoom;
}, { passive: false });

// ---------------------------------------------------------------- minimap interaction
if (minimap) {
  let mmDrag = false;
  function mmAt(ev) { const r = minimap.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; }
  minimap.addEventListener("mousedown", function (ev) { mmDrag = true; const m = mmAt(ev); MM.jump(m.x, m.y, minimap.clientWidth, minimap.clientHeight, vp, project, L()); });
  window.addEventListener("mousemove", function (ev) { if (!mmDrag) return; const m = mmAt(ev); MM.jump(m.x, m.y, minimap.clientWidth, minimap.clientHeight, vp, project, L()); });
  window.addEventListener("mouseup", function () { mmDrag = false; });
}

// ================================================================ KEYBOARD
window.addEventListener("keydown", function (ev) {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
  if (typing) return;
  if (ev.key === " ") { spacePan = true; canvas.style.cursor = "grab"; ev.preventDefault(); return; }
  const mod = ev.ctrlKey || ev.metaKey;
  if (mod && ev.key.toLowerCase() === "z" && !ev.shiftKey) { ev.preventDefault(); doUndo(); return; }
  if (mod && (ev.key.toLowerCase() === "y" || (ev.key.toLowerCase() === "z" && ev.shiftKey))) { ev.preventDefault(); doRedo(); return; }
  if (mod && ev.key.toLowerCase() === "c") { doCopy(); return; }
  if (mod && ev.key.toLowerCase() === "v") { doPaste(); return; }
  if (mod && ev.key.toLowerCase() === "d") { ev.preventDefault(); doDuplicate(); return; }
  if (mod) return;
  // tool hotkeys
  const byKey = { v: "select", b: "paint", p: "place", h: "pan" };
  if (byKey[ev.key.toLowerCase()]) { setTool(byKey[ev.key.toLowerCase()]); return; }
  if (ev.key >= "1" && ev.key <= "6") { setTool(TOOLS[parseInt(ev.key) - 1]); return; }
  if (ev.key === "Delete" || ev.key === "Backspace") { deleteSelection(); return; }
  if (ev.key === "Escape") { clearSel(); pendingImport = null; closeOverlays(); renderPanel(); return; }
  if (ev.key === "f" || ev.key === "F") { doFit(); return; }
  // zoom: + / = / numpad+ in, - / _ / numpad- out, 0 = 100% (the cheatsheet promised these)
  if (ev.key === "+" || ev.key === "=" || ev.code === "NumpadAdd") { ev.preventDefault(); vp.zoomAt(vp.w / 2, vp.h / 2, 1.25); return; }
  if (ev.key === "-" || ev.key === "_" || ev.code === "NumpadSubtract") { ev.preventDefault(); vp.zoomAt(vp.w / 2, vp.h / 2, 0.8); return; }
  if (ev.key === "0" || ev.code === "Numpad0") { ev.preventDefault(); vp.setZoom(1); return; }
  if (ev.key === "?") { toggleCheatsheet(); return; }
  // arrows: nudge selection, or pan camera when nothing selected
  const arrow = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[ev.key];
  if (arrow) {
    ev.preventDefault();
    const step = ev.shiftKey ? 10 : 1;
    if (sel.multi.length > 1) {
      snapshot();
      sel.multi.forEach(function (m) { m.obj.x += arrow[0] * step; m.obj.y += arrow[1] * step; });
      renderPanel();
      return;
    }
    const o = sel.entity || sel.hud || sel.point || sel.zone;
    if (o) { snapshot(); o.x += arrow[0] * step; o.y += arrow[1] * step; renderPanel(); }
    else vp.pan(arrow[0] * 40 / vp.zoom, arrow[1] * 40 / vp.zoom);
  }
});
window.addEventListener("keyup", function (ev) { if (ev.key === " ") { spacePan = false; canvas.style.cursor = sel.tool === "pan" ? "grab" : "default"; } });

// ---------------------------------------------------------------- edit ops
function selectedObjAndArr() {
  if (sel.entity) return [sel.entity, L().entities, "entity"];
  if (sel.hud) return [sel.hud, L().hud, "hud"];
  if (sel.zone) return [sel.zone, L().zones, "zone"];
  if (sel.point) return [sel.point, L().points, "point"];
  if (sel.particle) return [sel.particle, L().particles, "particle"];
  return null;
}
function deleteSelection() {
  if (sel.multi.length > 1) {
    snapshot();
    const n = sel.multi.length;
    sel.multi.forEach(function (m) { const arr = multiArrFor(m.kind); const i = arr.indexOf(m.obj); if (i >= 0) arr.splice(i, 1); });
    clearSel(); renderPanel(); refreshChrome(); toast("Deleted " + n + " objects (Ctrl+Z to undo)", "ok");
    return;
  }
  const s = selectedObjAndArr(); if (!s) return;
  snapshot(); s[1].splice(s[1].indexOf(s[0]), 1); clearSel(); renderPanel(); refreshChrome(); toast("Deleted (Ctrl+Z to undo)", "ok");
}
// Names must stay UNIQUE: the loader puts sprites, HUD labels and particle layers into one
// view.named dict (points have their own), and scene_build.py refuses a scene with duplicates.
// So a copy gets the first free "<name>_2", "<name>_3", ... - both for Ctrl+D/Ctrl+V and the
// Duplicate button (which used to append "_copy" once, so a second copy collided again).
function takenNames(kind) {
  const lv = L();
  if (kind === "point") return lv.points.map(function (p) { return p.name; });
  return [].concat(lv.entities.map(function (e) { return e.name; }),
                   lv.hud.map(function (h) { return h.name; }),
                   (lv.particles || []).map(function (p) { return p.name; }));
}
function uniqueName(base, kind) {
  if (!base) return base;
  const taken = takenNames(kind).filter(Boolean);
  if (taken.indexOf(base) < 0) return base;
  const stem = base.replace(/_\d+$/, "");
  for (let i = 2; i < 999; i++) if (taken.indexOf(stem + "_" + i) < 0) return stem + "_" + i;
  return base + "_copy";
}

function doCopy() { const s = selectedObjAndArr(); if (s) { clipboard = { kind: s[2], data: JSON.parse(JSON.stringify(s[0])) }; toast("Copied " + s[2], "ok"); } }
function doPaste() {
  if (!clipboard) return;
  snapshot();
  const c = JSON.parse(JSON.stringify(clipboard.data));
  if (c.x != null) { c.x += 12; c.y += 12; }
  if (c.name) c.name = uniqueName(c.name, clipboard.kind);       // never paste a duplicate name
  const arr = clipboard.kind === "entity" ? L().entities : clipboard.kind === "hud" ? L().hud : clipboard.kind === "zone" ? L().zones : clipboard.kind === "point" ? L().points : L().particles;
  arr.push(c); setTool("select"); pick(clipboard.kind, c);
  toast(c.name ? "Pasted as " + c.name : "Pasted", "ok");
}
function doDuplicate() { const s = selectedObjAndArr(); if (!s) return; clipboard = { kind: s[2], data: JSON.parse(JSON.stringify(s[0])) }; doPaste(); }
function doUndo() { const snap = history.undo(project); if (snap) { installProject(snap, true); toast("Undo", "info"); } else toast("Nothing to undo", "info"); }
function doRedo() { const snap = history.redo(project); if (snap) { installProject(snap, true); toast("Redo", "info"); } else toast("Nothing to redo", "info"); }
function installProject(p, keepView) {
  project = p;
  if (project.current >= project.levels.length) project.current = 0;
  clearSel(); sel.tm = Math.min(sel.tm, Math.max(0, L().tilemaps.length - 1));
  renderPanel(); refreshChrome();
  scheduleAutosave();
}

// ---------------------------------------------------------------- status
function updateStatus() {
  let what = "—";
  if (sel.entity) what = "entity " + (sel.entity.name || sel.entity.tag || sel.entity.asset);
  else if (sel.hud) what = "HUD '" + sel.hud.name + "'";
  else if (sel.zone) what = "zone '" + sel.zone.tag + "'";
  else if (sel.point) what = "point '" + sel.point.name + "'";
  else if (sel.particle) what = "fx '" + sel.particle.name + "'";
  else if (sel.tile) what = "tile " + sel.tile.value;
  const b = E.levelBounds(project, L());
  let extra = "";
  if (sel.tool === "paint") extra = " · layer <b>" + (curTm() ? (sel.tm + " " + curTm().asset) : "—") + "</b> · tile <b>" + sel.tileFrame + "</b>";
  else if (sel.tool === "select") extra = " · <b>" + what + "</b>" + (pickCycle.n > 1 ? " (click again: " + (pickCycle.i + 1) + "/" + pickCycle.n + ")" : "");
  else if (sel.tool === "place") extra = " · sprite <b>" + (sel.asset || "—") + "</b>";
  const st = $("status");
  if (st) st.innerHTML = "Tool: <b>" + (TOOL_META[sel.tool] ? TOOL_META[sel.tool].label : sel.tool) + "</b>" + extra +
    " · world <b>" + b[0] + "×" + b[1] + "</b> · zoom <b>" + Math.round(vp.zoom * 100) + "%</b>";
  const th = $("toolhelp"); if (th) th.innerHTML = TOOL_META[sel.tool] ? TOOL_META[sel.tool].tip : "";
}

// ================================================================ TOP BAR / FILES
function loadProject(p) {
  project = p; images = {}; artURLs = {}; history.clear();
  sel = { asset: null, tileFrame: 1, tool: "select", tm: 0, entity: null, hud: null, zone: null, point: null, particle: null, tile: null };
  document.querySelectorAll(".tool").forEach(function (b) { b.classList.toggle("on", b.dataset.tool === "select"); });
  setTimeout(doFit, 0);
  scheduleAutosave();
}
function refreshChrome() {
  const sel2 = $("levelSel"); if (!sel2) return; sel2.innerHTML = "";
  project.levels.forEach(function (lv, i) { sel2.appendChild(new Option(lv.name || ("level" + (i + 1)), i)); });
  sel2.value = project.current;
}
if ($("levelSel")) $("levelSel").onchange = function (e) { project.current = parseInt(e.target.value); clearSel(); sel.tm = 0; renderPanel(); refreshChrome(); doFit(); };
if ($("btnAddLevel")) $("btnAddLevel").onclick = function () {
  snapshot(); project.levels.push(E.newLevel("level" + (project.levels.length + 1))); project.current = project.levels.length - 1;
  clearSel(); sel.tm = 0; renderPanel(); refreshChrome(); doFit(); toast("Added level", "ok");
};
if ($("btnNew")) $("btnNew").onclick = function () { if (confirm("New project? Unsaved work is lost.")) { loadProject(E.newProject()); renderPanel(); refreshChrome(); } };

function download(name, text) { const b = new Blob([text], { type: "application/json" }); const a = mk("a"); a.href = URL.createObjectURL(b); a.download = name; a.click(); }
if ($("btnSave")) $("btnSave").onclick = function () { const s = E.serialize(project); s.art = artURLs; download("project.pgproj.json", JSON.stringify(s)); toast("Saved project.pgproj.json", "ok"); };
if ($("btnLoad")) $("btnLoad").onclick = function () { $("projfile").click(); };
function loadSave(obj) {
  loadProject(E.deserialize(obj));
  const art = obj.art || (obj.project && obj.project.art) || {};
  for (const id in art) { artURLs[id] = art[id]; const im = new Image(); im.src = art[id]; images[id] = im; }
  renderPanel(); refreshChrome();
}
// ---- Load: picogame project json OR a Tiled map (.tmj/.tmx + its tilesets + PNGs) ----
function readFile(f, mode) {
  return new Promise(function (res, rej) {
    const fr = new FileReader();
    fr.onload = function () { res(fr.result); };
    fr.onerror = rej;
    if (mode === "text") fr.readAsText(f); else fr.readAsDataURL(f);
  });
}

// XML -> the Tiled JSON shapes (mirrors tools/tiled2scene.py _tmx_to_dict/_tsx_to_dict)
function xmlProps(node) {
  const out = [];
  node.querySelectorAll(":scope > properties > property").forEach(function (pr) {
    const typ = pr.getAttribute("type") || "string";
    let val = pr.getAttribute("value"); if (val == null) val = pr.textContent || "";
    if (typ === "bool") val = (val === "true");
    else if (typ === "int" || typ === "object") val = parseInt(val, 10);
    else if (typ === "float") val = parseFloat(val);
    out.push({ name: pr.getAttribute("name"), type: typ, value: val });
  });
  return out;
}
function xmlTiles(root) {
  const tiles = [];
  root.querySelectorAll(":scope > tile").forEach(function (t) {
    const e = { id: parseInt(t.getAttribute("id"), 10) };
    const pl = xmlProps(t); if (pl.length) e.properties = pl;
    if (t.querySelector(":scope > animation")) e.animation = true;
    tiles.push(e);
  });
  return tiles;
}
function tsxToDict(xmlText) {
  const root = new DOMParser().parseFromString(xmlText, "text/xml").documentElement;
  const num = function (k, d) { const v = root.getAttribute(k); return v == null ? d : parseInt(v, 10); };
  const ts = { name: root.getAttribute("name") || "tiles",
    tilewidth: num("tilewidth"), tileheight: num("tileheight"),
    tilecount: num("tilecount", 0), columns: num("columns", 0),
    spacing: num("spacing", 0), margin: num("margin", 0) };
  const img = root.querySelector(":scope > image");
  if (img) {
    ts.image = img.getAttribute("source");
    if (img.getAttribute("trans")) ts.transparentcolor = "#" + img.getAttribute("trans").replace("#", "");
  }
  const tiles = xmlTiles(root); if (tiles.length) ts.tiles = tiles;
  return ts;
}
function tmxToDict(xmlText) {
  const root = new DOMParser().parseFromString(xmlText, "text/xml").documentElement;
  const num = function (el, k, d) { const v = el.getAttribute(k); return v == null ? d : parseFloat(v); };
  const m = { type: "map", orientation: root.getAttribute("orientation"),
    infinite: root.getAttribute("infinite") === "1",
    width: num(root, "width"), height: num(root, "height"),
    tilewidth: num(root, "tilewidth"), tileheight: num(root, "tileheight") };
  if (root.getAttribute("backgroundcolor")) m.backgroundcolor = root.getAttribute("backgroundcolor");
  m.tilesets = [];
  root.querySelectorAll(":scope > tileset").forEach(function (t) {
    if (t.getAttribute("source")) {
      m.tilesets.push({ firstgid: parseInt(t.getAttribute("firstgid"), 10), source: t.getAttribute("source") });
    } else {
      const ts = { firstgid: parseInt(t.getAttribute("firstgid"), 10), name: t.getAttribute("name"),
        tilewidth: num(t, "tilewidth"), tileheight: num(t, "tileheight"),
        tilecount: num(t, "tilecount", 0), columns: num(t, "columns", 0),
        spacing: num(t, "spacing", 0), margin: num(t, "margin", 0) };
      const img = t.querySelector(":scope > image");
      if (img) {
        ts.image = img.getAttribute("source");
        if (img.getAttribute("trans")) ts.transparentcolor = "#" + img.getAttribute("trans").replace("#", "");
      }
      const tiles = xmlTiles(t); if (tiles.length) ts.tiles = tiles;
      m.tilesets.push(ts);
    }
  });
  function layers(parent) {
    const out = [];
    parent.querySelectorAll(":scope > layer, :scope > objectgroup, :scope > imagelayer, :scope > group").forEach(function (el) {
      const vis = el.getAttribute("visible") !== "0";
      if (el.tagName === "layer") {
        const L = { type: "tilelayer", name: el.getAttribute("name"), visible: vis,
          width: num(el, "width"), height: num(el, "height"),
          opacity: num(el, "opacity", 1), offsetx: num(el, "offsetx", 0), offsety: num(el, "offsety", 0) };
        const d = el.querySelector(":scope > data");
        const enc = d.getAttribute("encoding");
        if (enc === "csv") L.data = d.textContent.split(/[\s,]+/).filter(Boolean).map(Number);
        else if (enc === "base64") { L.data = d.textContent.trim(); if (d.getAttribute("compression")) L.compression = d.getAttribute("compression"); }
        else L.data = Array.from(d.querySelectorAll("tile")).map(function (t) { return parseInt(t.getAttribute("gid") || "0", 10); });
        out.push(L);
      } else if (el.tagName === "objectgroup") {
        const objs = [];
        el.querySelectorAll(":scope > object").forEach(function (o) {
          const ob = { id: parseInt(o.getAttribute("id") || "0", 10),
            x: num(o, "x", 0), y: num(o, "y", 0), width: num(o, "width", 0), height: num(o, "height", 0) };
          if (o.getAttribute("name")) ob.name = o.getAttribute("name");
          const cls = o.getAttribute("class") || o.getAttribute("type");
          if (cls) ob.class = cls;
          if (o.getAttribute("gid")) ob.gid = parseInt(o.getAttribute("gid"), 10) >>> 0;
          if (o.getAttribute("rotation")) ob.rotation = parseFloat(o.getAttribute("rotation"));
          ["point", "ellipse", "polygon", "polyline", "text"].forEach(function (sh) {
            if (o.querySelector(":scope > " + sh)) ob[sh] = true;
          });
          const pl = xmlProps(o); if (pl.length) ob.properties = pl;
          objs.push(ob);
        });
        out.push({ type: "objectgroup", name: el.getAttribute("name"), visible: vis, objects: objs });
      } else if (el.tagName === "imagelayer") {
        out.push({ type: "imagelayer", name: el.getAttribute("name"), visible: vis });
      } else {
        out.push({ type: "group", name: el.getAttribute("name"), visible: vis,
          offsetx: num(el, "offsetx", 0), offsety: num(el, "offsety", 0), layers: layers(el) });
      }
    });
    return out;
  }
  m.layers = layers(root);
  return m;
}

// base64(+zlib/gzip) tilelayer data -> int array (DecompressionStream; async)
async function decodeTiledData(map) {
  async function fix(L) {
    if (L.type === "group") { for (const c of L.layers || []) await fix(c); return; }
    if (L.type !== "tilelayer" || typeof L.data !== "string") return;
    if (L.compression === "zstd") throw new Error("layer " + L.name + ": zstd compression - re-export with zlib/gzip/CSV");
    const bin = atob(L.data.trim());
    let bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    if (L.compression === "zlib" || L.compression === "gzip") {
      const fmt = L.compression === "zlib" ? "deflate" : "gzip";
      const ds = new DecompressionStream(fmt);
      const out = await new Response(new Blob([bytes]).stream().pipeThrough(ds)).arrayBuffer();
      bytes = new Uint8Array(out);
    }
    const n = bytes.length >> 2, arr = new Array(n);
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    for (let i = 0; i < n; i++) arr[i] = dv.getUint32(i * 4, true);
    L.data = arr;
    delete L.compression;
  }
  for (const L of map.layers || []) await fix(L);
}

function loadImageFromDataURL(dataURL) {
  return new Promise(function (res, rej) {
    const im = new Image();
    im.onload = function () { res(im); };
    im.onerror = rej;
    im.src = dataURL;
  });
}

// Execute the repack plan: horizontal strip (empty tile 0 + only the USED tiles,
// spacing/margin removed, transparentcolor -> alpha). Returns a dataURL.
function repackStrip(img, plan) {
  const c = document.createElement("canvas");
  c.width = plan.tw * (plan.used.length + 1); c.height = plan.th;
  const ctx = c.getContext("2d");
  plan.used.forEach(function (tid, slot) {
    const sx = plan.margin + (tid % plan.columns) * (plan.tw + plan.spacing);
    const sy = plan.margin + Math.floor(tid / plan.columns) * (plan.th + plan.spacing);
    ctx.drawImage(img, sx, sy, plan.tw, plan.th, (slot + 1) * plan.tw, 0, plan.tw, plan.th);
  });
  if (plan.transparent) {
    const h = plan.transparent.replace("#", "").slice(-6);
    const kr = parseInt(h.slice(0, 2), 16), kg = parseInt(h.slice(2, 4), 16), kb = parseInt(h.slice(4, 6), 16);
    const id = ctx.getImageData(0, 0, c.width, c.height);
    for (let i = 0; i < id.data.length; i += 4)
      if (id.data[i] === kr && id.data[i + 1] === kg && id.data[i + 2] === kb) id.data[i + 3] = 0;
    ctx.putImageData(id, 0, 0);
  }
  return c.toDataURL("image/png");
}

async function importTiledFiles(files) {
  const byName = {};
  files.forEach(function (f) { byName[f.name.toLowerCase()] = f; });
  const mapFile = files.find(function (f) { return /\.(tmj|tmx)$/i.test(f.name); });
  let map;
  if (/\.tmx$/i.test(mapFile.name)) map = tmxToDict(await readFile(mapFile, "text"));
  else map = JSON.parse(await readFile(mapFile, "text"));
  await decodeTiledData(map);

  // external tilesets: must be among the picked files (browsers can't follow paths)
  const external = {}, missing = [];
  for (const e of map.tilesets || []) {
    if (!e.source) continue;
    const base = e.source.replace(/^.*[\/\\]/, "").toLowerCase();
    const f = byName[base];
    if (!f) { missing.push(base); continue; }
    external[e.source.replace(/^.*[\/\\]/, "")] =
      /\.tsx$/i.test(base) ? tsxToDict(await readFile(f, "text")) : JSON.parse(await readFile(f, "text"));
  }
  if (missing.length) throw new Error("select these tileset files too: " + missing.join(", "));

  const res = E.importTiled(map, external);

  // tileset images: also picked by the user; repack each to a strip dataURL
  const missingImg = res.repack.filter(function (p) { return !byName[p.image.toLowerCase()]; })
    .map(function (p) { return p.image; });
  if (missingImg.length) throw new Error("select these tileset image(s) too: " + missingImg.join(", "));
  const strips = {};
  for (const plan of res.repack) {
    const img = await loadImageFromDataURL(await readFile(byName[plan.image.toLowerCase()], "dataurl"));
    const dataURL = repackStrip(img, plan);
    strips[plan.asset] = { dataURL: dataURL, img: await loadImageFromDataURL(dataURL) };
    res.project.assets[plan.asset].src = plan.asset + ".png";
  }

  loadProject(res.project);                      // NOTE: resets images/artURLs - fill AFTER
  for (const id in strips) { artURLs[id] = strips[id].dataURL; images[id] = strips[id].img; }
  renderPanel(); refreshChrome();
  toast("Imported " + mapFile.name, "ok");
  res.warnings.slice(0, 6).forEach(function (w) { toast(w, "info"); });
  if (res.warnings.length > 6) toast("…and " + (res.warnings.length - 6) + " more warnings (see console)", "info");
  if (res.warnings.length) console.log("Tiled import warnings:", res.warnings);
}

if ($("projfile")) $("projfile").onchange = function (ev) {
  const files = Array.from(ev.target.files || []);
  ev.target.value = "";
  if (!files.length) return;
  if (files.some(function (f) { return /\.(tmj|tmx)$/i.test(f.name); })) {
    importTiledFiles(files).catch(function (e) { toast("Tiled import: " + e.message, "err"); console.error(e); });
    return;
  }
  const f = files[0];
  const fr = new FileReader();
  fr.onload = function () { try { loadSave(JSON.parse(fr.result)); toast("Loaded " + f.name, "ok"); } catch (e) { toast("Could not read project file", "err"); } };
  fr.readAsText(f);
};
// The loadable demos. Each is a .pgproj.json in this folder (served same-origin). The
// two scrolling demos teach the big-map workflow: load one, inspect its Map size + camera.
const DEMOS = {
  sample:     { file: "sample.pgproj.json",       msg: "Loaded sample (one screen)" },
  platformer: { file: "demo_platformer.pgproj.json", msg: "Loaded scrolling platformer — 960×240, follow-camera axis x (clamps at both ends)" },
  openworld:  { file: "demo_openworld.pgproj.json",  msg: "Loaded open world — 640×480, follow-camera axis xy (free roam both ways)" },
};
function loadDemo(name) {
  const d = DEMOS[name]; if (!d) return;
  const EDBASE = (typeof window !== "undefined" && window.PG_EDITOR_BASE) || "";
  const dd = $("demosD"); if (dd) dd.open = false;
  fetch(EDBASE + d.file).then(function (r) { if (!r.ok) throw new Error("missing " + d.file); return r.json(); })
    .then(function (o) { loadSave(o); toast(d.msg, "ok"); })     // loadProject() fits the whole world to view
    .catch(function () { toast("Could not load demo (serve over http, not file://)", "err"); });
}
if ($("btnSample")) $("btnSample").onclick = function () { loadDemo("sample"); };
if ($("btnDemoPlatformer")) $("btnDemoPlatformer").onclick = function () { loadDemo("platformer"); };
if ($("btnDemoOpen")) $("btnDemoOpen").onclick = function () { loadDemo("openworld"); };
// Baked export: the SAME module scene_build.py writes (SCENE = {...}), produced in the browser -
// PNG assets get baked to PAL8 on the spot (inlinePngAssets), so no Python step is needed:
// drop <name>_scene.py next to your code and picogame_scene.load(pg, module.SCENE).
if ($("btnExportBaked")) $("btnExportBaked").onclick = function () {
  var d = $("exportD"); if (d) d.open = false;
  var scene;
  try { scene = E.exportScene(project); } catch (e) { toast("Could not export this level", "err"); return; }
  var pngIds = Object.keys(scene.assets || {}).filter(function (id) {
    var t = scene.assets[id].type; return t === "sprite" || t === "tileset" || t === "bitmap";
  });
  try {
    var res = inlinePngAssets(scene, pngIds);
    if (res.missing.length) { toast("No image data for: " + res.missing.join(", ") + " - re-import those PNGs first", "err"); return; }
    var text = E.sceneModule(scene);
    var stem = (L().name || "scene").replace(/\W+/g, "_");
    download(stem + "_scene.py", text);
    toast("Exported " + stem + "_scene.py (" + (text.length / 1024).toFixed(1) + " KB) - picogame_scene.load(pg, " + stem + "_scene.SCENE)", "ok");
  } catch (e) { toast("Bake failed: " + (e.message || e), "err"); console.error(e); }
};
if ($("btnExport")) $("btnExport").onclick = function () { download((L().name || "scene").replace(/\W+/g, "_") + ".scene.json", JSON.stringify(E.exportScene(project), null, 1)); const d = $("exportD"); if (d) d.open = false; toast("Exported scene.json — bake with scene_build.py", "ok"); };
if ($("btnExportProj")) $("btnExportProj").onclick = function () { download("game.project.json", JSON.stringify(E.exportProject(project), null, 1)); const d = $("exportD"); if (d) d.open = false; toast("Exported project.json", "ok"); };

// Try in playground: hand THIS level to the browser playground and run it live. The playground bakes
// colour assets in-browser (no PIL/files), so colour tilesets + rect sprites run natively. PNG-backed
// assets (sprite/bitmap/tileset) can't be baked in-browser -- but rather than decline, we OFFER to
// substitute them with coloured placeholder BLOCKS (after a warning) so the level still runs: a PNG
// sprite becomes a rect of the same size (distinct colour per asset), a PNG tileset becomes a
// tileset_color (a distinct colour per used tile index). Cancel keeps the clean decline. This is a pure
// editor-side transform on the EXPORTED COPY -- the real project is never touched, and scene_bake.py /
// the runner / the playground need no changes (rect + tileset_color are already supported).
// Transport: stash the (colour-only) scene JSON in localStorage (same-origin, no URL-size limit) and
// open the playground with ?from=editor; editor.js reads the key, wraps it in a short runner, Runs.

// Distinct, readable placeholder colours cycled across substituted assets so blocks are tell-apart.
var PLACEHOLDER_COLORS = [
  [80, 220, 90],    // bright green (often the player)
  [235, 80, 80],    // red
  [245, 170, 40],   // orange
  [170, 100, 235],  // purple
  [70, 170, 240],   // blue
  [240, 220, 60],   // yellow
  [240, 120, 200],  // pink
];

// Replace PNG-backed assets in an EXPORTED scene copy with colour placeholders. Returns the list of
// substituted asset ids (for the toast), or throws with a clear message if an asset can't be handled.
function substitutePngAssets(scene, pngIds) {
  var ci = 0;
  var nextColor = function () { return PLACEHOLDER_COLORS[ci++ % PLACEHOLDER_COLORS.length]; };
  var subbed = [];
  pngIds.forEach(function (id) {
    var a = scene.assets[id];
    if (a.type === "sprite" || a.type === "bitmap") {
      var fr = a.frame || a.size || [8, 8];               // sprite exports frame=[fw,fh]
      scene.assets[id] = { type: "rect", size: [fr[0], fr[1]], color: nextColor() };
      subbed.push(id);
    } else if (a.type === "tileset") {
      // PNG image tilemap -> tileset_color. Give each tile index actually used in any tilemap layer a
      // distinct placeholder colour so the map still renders as coloured tiles. Preserve props (solid
      // etc.) so collision keeps working. frames come from the asset; used indices from the grids.
      var tile = a.tile || a.frame || [16, 16];
      var used = {};
      (scene.layers || []).forEach(function (L) {
        if (L.kind === "tilemap" && L.asset === id && L.grid) {
          L.grid.forEach(function (row) { row.forEach(function (v) { if (v & 0xFF) used[v & 0xFF] = 1; }); });   // strip orientation bits 8-10
        } else if ((L.kind === "sprite" || L.kind === "group") && L.asset === id) {
          used[L.frame || 0] = 1;                            // tile objects placed as sprites of this tileset
        }
      });
      var colors = {};
      Object.keys(used).map(Number).sort(function (x, y) { return x - y; })
        .forEach(function (v) { colors[String(v)] = nextColor(); });
      if (!Object.keys(colors).length) colors["1"] = nextColor();   // never emit an empty colour map
      var repl = { type: "tileset_color", tile: [tile[0], tile[1]], colors: colors };
      if (a.props) repl.props = a.props;                   // keep solid/coin/goal flags
      scene.assets[id] = repl;
      subbed.push(id);
    } else {
      throw new Error("can't substitute asset '" + id + "' (type " + a.type + ")");
    }
  });
  // rect + tileset_color are 1-frame per value: reset any sprite-instance frame index on substituted
  // assets so a >0 frame doesn't overflow the placeholder bitmap.
  (scene.layers || []).forEach(function (L) {
    if ((L.kind === "sprite" || L.kind === "group") && subbed.indexOf(L.asset) >= 0) {
      if (scene.assets[L.asset].type === "rect" && L.frame) L.frame = 0;   // tileset_color keeps its per-value frame
      if (L.anim) delete L.anim;                           // no animation on placeholders
    }
  });
  return subbed;
}

function handoffScene(scene) {
  try { localStorage.setItem("pg_editor_level", JSON.stringify(scene)); }
  catch (e) { toast("Level too large to hand off", "err"); return; }
  var url = (typeof window !== "undefined" && window.PG_PLAYGROUND_URL) || "https://picogame.makerclass.cz/playground/";
  window.open(url + (url.indexOf("?") < 0 ? "?" : "&") + "from=editor", "_blank");
  toast("Opening this level in the playground…", "ok");
}

// Bake the editor's loaded PNG assets into inline PAL8 atlases (Canvas -> quantize -> base64) so the
// playground renders the REAL art. Same rules as the device bake (transparent = alpha<128 -> index 0,
// <=255 colours kept exactly, else median-cut). Assets whose image isn't loaded fall back to the
// colour-placeholder substitution below. Returns {inlined: [...ids], missing: [...ids]}.
function inlinePngAssets(scene, pngIds) {
  var inlined = [], missing = [];
  pngIds.forEach(function (id) {
    var img = images[id];
    if (!img || !img.complete || !img.naturalWidth) { missing.push(id); return; }
    var c = document.createElement("canvas");
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    var ctx = c.getContext("2d");
    ctx.drawImage(img, 0, 0);
    var rgba = ctx.getImageData(0, 0, c.width, c.height).data;
    scene.assets[id] = E.inlinePal8Asset(scene.assets[id], rgba, c.width, c.height);
    inlined.push(id);
  });
  return { inlined: inlined, missing: missing };
}

if ($("btnTryPlay")) $("btnTryPlay").onclick = function () {
  var scene;
  try { scene = E.exportScene(project); } catch (e) { toast("Could not export this level", "err"); return; }
  var pngIds = Object.keys(scene.assets || {}).filter(function (id) {
    var t = scene.assets[id].type; return t === "sprite" || t === "tileset" || t === "bitmap";
  });
  if (!pngIds.length) { handoffScene(scene); return; }     // colour-only level: unchanged flow
  var res;
  try { res = inlinePngAssets(scene, pngIds); }
  catch (e) { toast("Couldn't bake an image asset: " + (e.message || e), "err"); return; }
  if (res.missing.length) {
    // image not loaded (e.g. project file without embedded art): offer placeholders for those
    var ok = window.confirm(
      "No image data for: " + res.missing.join(", ") + ".\n\n" +
      "Open the playground with coloured placeholder blocks for those assets?\n\n" +
      "OK = run with placeholders   ·   Cancel = don't open");
    if (!ok) { toast("Cancelled", "info"); return; }
    try { substitutePngAssets(scene, res.missing); }
    catch (e) { toast("Couldn't substitute an image asset: " + (e.message || e), "err"); return; }
  }
  handoffScene(scene);
  if (res.inlined.length) toast("Baked " + res.inlined.length + " image asset(s) to PAL8 for the playground", "ok");
  if (res.missing.length) toast("Substituted " + res.missing.length + " asset(s) with placeholder blocks", "info");
};

// nav buttons in top bar (if present)
["btnFit", "btnZoom100", "btnZoomIn", "btnZoomOut"].forEach(function (id) { /* wired below if present */ });
if ($("btnUndo")) $("btnUndo").onclick = doUndo;
if ($("btnRedo")) $("btnRedo").onclick = doRedo;
if ($("btnFit")) $("btnFit").onclick = doFit;
if ($("btnZoom100")) $("btnZoom100").onclick = function () { vp.setZoom(1); };
if ($("btnZoomIn")) $("btnZoomIn").onclick = function () { vp.zoomAt(vp.w / 2, vp.h / 2, 1.25); };
if ($("btnZoomOut")) $("btnZoomOut").onclick = function () { vp.zoomAt(vp.w / 2, vp.h / 2, 0.8); };

// ---------------------------------------------------------------- overlays (help)
function closeOverlays() { const c = $("cheatsheet"); if (c) c.hidden = true; const g = $("gettingStarted"); if (g) g.hidden = true; }
function toggleCheatsheet() { const c = $("cheatsheet"); if (c) c.hidden = !c.hidden; }
if ($("btnHelp")) $("btnHelp").onclick = toggleCheatsheet;
if ($("cheatsheetClose")) $("cheatsheetClose").onclick = function () { $("cheatsheet").hidden = true; };
function dismissGS() { const g = $("gettingStarted"); if (g) g.hidden = true; try { localStorage.setItem("pg_ed_seen", "1"); } catch (e) {} }
if ($("gsClose")) $("gsClose").onclick = dismissGS;
if ($("gsSample")) $("gsSample").onclick = function () { dismissGS(); loadDemo("sample"); };
if ($("gsPlatformer")) $("gsPlatformer").onclick = function () { dismissGS(); loadDemo("platformer"); };
if ($("gsOpen")) $("gsOpen").onclick = function () { dismissGS(); loadDemo("openworld"); };

// tool buttons
document.querySelectorAll(".tool").forEach(function (b) {
  b.onclick = function () { setTool(b.dataset.tool); };
  const m = TOOL_META[b.dataset.tool]; if (m) b.title = m.tip;
});

// ================================================================ RENDER LOOP
function frame() {
  if (canvas.width !== Math.round(canvas.getBoundingClientRect().width * (window.devicePixelRatio || 1))) resizeCanvas();
  const guide = guidePos();
  R.draw(ctx, vp, project, L(), images, sel, {
    showFlags: showFlags, showGrid: showGrid, gridTile: gridTileSize(),
    rubberRect: rubberRect, tileSel: tileSelRect, guideX: guide.x, guideY: guide.y
  });
  if (mmCtx) MM.draw(mmCtx, minimap.clientWidth, minimap.clientHeight, vp, project, L());
  updateStatus();
  requestAnimationFrame(frame);
}
// one-screen guide box sits at the camera's current focus if following, else at 0,0
function guidePos() { return { x: 0, y: 0 }; }

window.addEventListener("resize", function () { resizeCanvas(); });

// expose a direct sample-load hook (used by file:// contexts where fetch is blocked)
window.__pgEdLoadSample = function (obj) { loadSave(obj); };

// ---------------------------------------------------------------- init
function init() {
  resizeCanvas();
  // resume the autosaved session, if any (see scheduleAutosave)
  let restored = false;
  try {
    const raw = localStorage.getItem(AUTOSAVE_KEY);
    if (raw) { loadSave(JSON.parse(raw)); restored = true; }
  } catch (e) {}
  // first-run getting-started overlay (dismissible; remembered; skipped when resuming)
  let seen = false; try { seen = localStorage.getItem("pg_ed_seen") === "1"; } catch (e) {}
  const gs = $("gettingStarted"); if (gs && (seen || restored)) gs.hidden = true;
  refreshChrome(); renderPanel(); doFit(); frame();
  if (restored) toast("Restored your last session — New starts a fresh project", "ok");
}
init();
})();   // end IIFE (keeps app.js re-loadable per open without redeclaring globals)
