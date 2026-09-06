// picogame editor -- pure model + exporters (no DOM), shared by the browser app and
// node tests. This is the ONLY place the authoring formats in ../SCENE_FORMAT.md are
// produced, so it stays DOM-free and unit-tested headless with `node test.js`.
//
//   project = {
//     size:[320,240],                        // device screen (the "one-screen" guide box)
//     assets:{ id:{type,...} },              // SHARED bank: sprite/tileset/rect/tileset_color
//     sounds:{ id:{src} },                   // SHARED bank: wav references
//     levels:[ {
//        name, background,
//        tilemaps:[ {asset,cols,rows,grid,pos,fg} ],   // many layers; fg drawn over sprites
//        entities:[ {asset,name,tag,x,y,anchor,frame,anim,data} ],
//        hud:[ {name,x,y,fg,bg} ],
//        zones:[ {tag,x,y,w,h} ],            // trigger/collision rectangles
//        points:[ {name,x,y} ],              // spawn points / waypoints
//        particles:[ {name,capacity,size,gravity,fade} ],   // fx layers
//        camera, music,
//     } ],
//     current: 0,
//   }
//
// The exported scene/project JSON is consumed UNCHANGED by tools/scene_build.py; the
// exact shape (tilemap grid, sprite/group folding, hud/zones/points/particles, camera,
// tileprops, anims, colour tilesets) is the load-bearing contract -- do not drift it.

(function (root) {
  "use strict";

  // ---------------------------------------------------------------- factories
  // worldSize [w,h] in PIXELS is the level's headline extent (default = one device screen).
  // Callers that know the project size may override it; the editor defaults new levels to
  // the project's screen and grows it via the Level panel's World size control.
  function newLevel(name, worldSize) {
    return { name: name || "level", background: [90, 150, 230],
             worldSize: (worldSize || [320, 240]).slice(),
             tilemaps: [], entities: [], hud: [], zones: [], points: [],
             particles: [], camera: null, music: null };
  }

  function newProject() {
    return { size: [320, 240], assets: {}, sounds: {},
             levels: [newLevel("level1")], current: 0 };
  }

  // A tilemap layer. cols/rows are AUTHORING-time (can far exceed one screen); the grid
  // is a rows x cols 2-D int array (0 = empty). pos is the world offset in pixels.
  function newTilemap(assetId, cols, rows, fg) {
    const grid = [];
    for (let y = 0; y < rows; y++) grid.push(new Array(cols).fill(0));
    return { asset: assetId, cols: cols, rows: rows, grid: grid, pos: [0, 0], fg: !!fg };
  }

  function newParticles(name) {
    return { name: name || "fx", capacity: 64, size: 2, gravity: 0.0, fade: false };
  }

  // ---------------------------------------------------------------- tile helpers
  function setTileProp(asset, value, prop, on) {
    asset.props = asset.props || {};
    const key = String(value);
    asset.props[key] = asset.props[key] || {};
    if (on) asset.props[key][prop] = true;
    else delete asset.props[key][prop];
  }

  // Grow/crop a tilemap to cols x rows. Grow pads with 0 (empty); shrink crops the
  // right/bottom (the caller confirms a shrink -- data past the new edge is dropped).
  // Returns true if anything past the new bounds was non-empty (a destructive shrink).
  function resizeTilemap(tm, cols, rows) {
    cols = Math.max(1, cols | 0);
    rows = Math.max(1, rows | 0);
    let lost = false;
    const old = tm.grid;
    for (let y = 0; y < old.length; y++)
      for (let x = 0; x < old[y].length; x++)
        if (old[y][x] && (x >= cols || y >= rows)) lost = true;
    const grid = [];
    for (let y = 0; y < rows; y++) {
      const row = new Array(cols).fill(0);
      if (y < old.length) for (let x = 0; x < cols && x < old[y].length; x++) row[x] = old[y][x];
      grid.push(row);
    }
    tm.grid = grid; tm.cols = cols; tm.rows = rows;
    return lost;
  }

  // The IMPLICIT extent of a level's content in pixels: the union of every tilemap layer's
  // (pos + cols*tile) plus any placed object, floored at the device screen. Used only to
  // DERIVE a worldSize for old projects that predate the explicit field; the live world
  // extent is level.worldSize (see below).
  function contentBounds(project, level) {
    let w = project.size[0], h = project.size[1];
    (level.tilemaps || []).forEach(function (tm) {
      const a = project.assets[tm.asset];
      const tw = a ? tileW(a) : 16, th = a ? tileH(a) : 16;
      w = Math.max(w, tm.pos[0] + tm.cols * tw);
      h = Math.max(h, tm.pos[1] + tm.rows * th);
    });
    (level.entities || []).forEach(function (en) { w = Math.max(w, en.x + 8); h = Math.max(h, en.y + 8); });
    (level.zones || []).forEach(function (z) { w = Math.max(w, z.x + z.w); h = Math.max(h, z.y + z.h); });
    (level.points || []).forEach(function (q) { w = Math.max(w, q.x + 8); h = Math.max(h, q.y + 8); });
    return [Math.ceil(w), Math.ceil(h)];
  }

  // The world extent of a level in PIXELS -- the SINGLE SOURCE OF TRUTH. It is the explicit
  // level.worldSize (a first-class per-level property); if a project predates that field,
  // deserialize() derives it from contentBounds. Camera "auto" bounds, Fit, the render
  // extent, the minimap world rect, and new-layer sizing all read this. (Named levelBounds
  // for continuity with the rest of the editor, which already calls it everywhere.)
  function levelBounds(project, level) {
    if (level.worldSize && level.worldSize.length === 2)
      return [Math.max(1, level.worldSize[0] | 0), Math.max(1, level.worldSize[1] | 0)];
    return contentBounds(project, level);
  }

  // Resize every tilemap layer anchored at world origin to fill worldSize (cols/rows from
  // the layer's own tile size). Layers with a non-zero pos (parallax/offset layers) keep
  // their size. Returns true if any layer's shrink dropped painted tiles. Used when the
  // user changes World size and opts to grow/crop layers with it.
  function fillLayersToWorld(project, level) {
    const ww = level.worldSize[0], wh = level.worldSize[1];
    let lost = false;
    (level.tilemaps || []).forEach(function (tm) {
      if (tm.pos && (tm.pos[0] || tm.pos[1])) return;      // offset layer: leave it alone
      const a = project.assets[tm.asset]; if (!a) return;
      const cols = Math.max(1, Math.round(ww / tileW(a)));
      const rows = Math.max(1, Math.round(wh / tileH(a)));
      if (resizeTilemap(tm, cols, rows)) lost = true;
    });
    return lost;
  }

  // cols/rows for a fresh layer that fills the whole world at asset a's tile size.
  function layerSizeForWorld(level, a) {
    return [Math.max(1, Math.round(level.worldSize[0] / tileW(a))),
            Math.max(1, Math.round(level.worldSize[1] / tileH(a)))];
  }

  function tileW(a) { return a.fw || 16; }
  function tileH(a) { return a.fh || 16; }
  function isImg(a) { return !!a && (a.type === "sprite" || a.type === "tileset" || a.type === "bitmap"); }

  // number of paintable tile values (indices) for a tileset (value 0 = empty/erase).
  function tileCount(a) {
    if (!a) return 1;
    if (a.type === "tileset_color") return Math.max.apply(null, [0].concat(Object.keys(a.colors).map(Number))) + 1;
    if (isImg(a)) return a.frames || 1;
    return 1;
  }

  // Remove an asset and every level reference to it (tilemap layers + entities).
  function removeAsset(project, id) {
    delete project.assets[id];
    project.levels.forEach(function (lv) {
      lv.tilemaps = lv.tilemaps.filter(function (tm) { return tm.asset !== id; });
      lv.entities = lv.entities.filter(function (en) { return en.asset !== id; });
    });
  }

  // ---------------------------------------------------------------- exporters
  function exportAssets(project) {
    const out = {};
    for (const id in project.assets) {
      const a = project.assets[id];
      const e = { type: a.type };
      if (a.type === "sprite" || a.type === "tileset" || a.type === "bitmap") {
        e.src = a.src; e.frames = a.frames || 1;
        if (a.type === "tileset") e.tile = [a.fw, a.fh]; else e.frame = [a.fw, a.fh];
        if (a.transparent != null) e.transparent = a.transparent;
      } else if (a.type === "rect") {
        e.size = [a.fw, a.fh]; e.color = a.color;
      } else if (a.type === "tileset_color") {
        e.tile = [a.fw, a.fh]; e.colors = a.colors;
      }
      if (a.props && Object.keys(a.props).length) e.props = a.props;
      if (a.animations && Object.keys(a.animations).length) e.animations = a.animations;
      out[id] = e;
    }
    return out;
  }

  // Legend alphabet for the ASCII map form. '.' is reserved for tile 0 (empty); the rest are
  // assigned in ASCENDING CELL-VALUE order, which keeps a legend STABLE across exports — the
  // whole point of the form is that a level's diff stays a picture, and frequency-ordered chars
  // would reshuffle it whenever a map changes slightly. JSON-hostile chars (" \) are excluded.
  const LEGEND_CHARS = "#o=+*xXOA BCDEFGHIJKLMNPQRSTUVWYZabcdefghijklmnpqrstuvwyz0123456789" +
    "!$%&()<>?@[]^_{|}~;:,'`/".replace(/ /g, "");

  // A tilemap layer in one of the two forms the baker accepts: the int `grid` (compact, what a
  // machine reads) or `rows` over a legend (the same map as an ASCII picture — reviewable in a
  // diff, editable by hand or by an agent). In game.json (v2) the legend lives in the ASSET and
  // is shared by every layer that paints with it; a v1 scene carries it on the layer. Falls back
  // to the grid when a map needs more distinct values than the alphabet has characters.
  function tilemapLayer(tm, ascii, assetLegend) {
    const L = { kind: "tilemap", asset: tm.asset, pos: tm.pos.slice() };
    const rows = ascii ? asciiRows(tm.grid, assetLegend) : null;
    if (rows) {
      if (!assetLegend) L.legend = rows.legend;      // v1 form: legend on the layer
      L.rows = rows.rows;
    } else {
      L.grid = tm.grid.map(function (r) { return r.slice(); });
    }
    if (tm.fg) L.fg = true;
    return L;
  }

  // The int grid of a tilemap layer in EITHER authoring form — the one place that knows both,
  // so every consumer (the baker below, importers, tests) reads a grid and nothing else has to
  // branch. Mirrors _bake_tilemap() in picogame_scenebake. `assets` supplies the v2 asset legend.
  function layerGrid(L, assets) {
    if (L.grid) return L.grid;
    const legend = L.legend || (assets && assets[L.asset] && assets[L.asset].legend) || {};
    return (L.rows || []).map(function (row) {
      return row.split("").map(function (ch) { return legend[ch] || 0; });
    });
  }

  // grid -> {legend: {char: value}, rows: [str]}, or null if it doesn't fit the alphabet.
  // The legend is APPEND-ONLY: chars already in `legend` keep their value (so a map's diff stays
  // a picture and an agent's mnemonic letters survive a Save), new values get the next free
  // char in ascending-value order. `legend` is MUTATED (it is the asset's persistent legend).
  // A cell value may carry orientation in bits 8-10; the legend value carries it too, so an
  // oriented tile is just its own legend entry.
  function asciiRows(grid, legend) {
    legend = legend || {};
    if (!(("." in legend) && legend["."] === 0)) legend["."] = 0;
    const charOf = {};
    for (const ch in legend) if (!(legend[ch] in charOf)) charOf[legend[ch]] = ch;
    const missing = [];
    grid.forEach(function (r) {
      r.forEach(function (v) { if (!(v in charOf) && missing.indexOf(v) < 0) missing.push(v); });
    });
    missing.sort(function (a, b) { return a - b; });
    let ci = 0;
    for (const v of missing) {
      while (ci < LEGEND_CHARS.length && (LEGEND_CHARS[ci] in legend)) ci++;
      if (ci >= LEGEND_CHARS.length) return null;
      legend[LEGEND_CHARS[ci]] = v; charOf[v] = LEGEND_CHARS[ci]; ci++;
    }
    return { legend: legend, rows: grid.map(function (r) {
      return r.map(function (v) { return charOf[v]; }).join("");
    }) };
  }

  // ordered layers (bg tilemaps -> sprites/groups/particles -> fg tilemaps -> hud)
  // + camera/zones/points/music for one level. `assets` (v2) = the project's assets, whose
  // legends the ASCII rows use; a tagged entity that also carries a name, data, frame or anim is
  // exported as a sprite WITH a tag (the loader still files it under its group), so nothing of it
  // is lost in the group fold.
  function buildLevel(level, ascii, assets) {
    const bg = [], mid = [], fg = [], hud = [];
    (level.tilemaps || []).forEach(function (tm) {
      const a = assets && assets[tm.asset];
      if (a && ascii) a.legend = a.legend || {};
      (tm.fg ? fg : bg).push(tilemapLayer(tm, ascii, a ? a.legend : null));
    });
    const byTag = {};
    (level.entities || []).forEach(function (en) {
      const plain = en.tag && !en.name && !en.data && !en.frame && !en.angle;
      if (plain) {
        const g = byTag[en.tag] = byTag[en.tag] ||
          { asset: en.asset, anchor: en.anchor, anim: en.anim, insts: [] };
        g.insts.push([en.x, en.y]);
      } else {
        const L = { kind: "sprite", asset: en.asset };
        if (en.name) L.name = en.name;
        if (en.tag) L.tag = en.tag;
        L.pos = [en.x, en.y];
        const an = en.anchor || [0, 0];
        if (an[0] || an[1]) L.anchor = an.slice();
        if (en.frame) L.frame = en.frame;
        if (en.anim) L.anim = en.anim;
        if (en.data) L.data = en.data;
        if (en.angle) L.angle = en.angle;
        mid.push(L);
      }
    });
    for (const tag in byTag) {
      const g = byTag[tag];
      const L = { kind: "group", asset: g.asset, tag: tag };
      const ga = g.anchor || [0, 0];
      if (ga[0] || ga[1]) L.anchor = ga.slice();
      L.instances = g.insts;
      if (g.anim) L.anim = g.anim;
      mid.push(L);
    }
    (level.particles || []).forEach(function (p) {
      mid.push({ kind: "particles", name: p.name, capacity: p.capacity,
        size: p.size, gravity: p.gravity, fade: !!p.fade });
    });
    (level.hud || []).forEach(function (h) {
      hud.push({ kind: "hudlabel", name: h.name, pos: [h.x, h.y],
        fg: h.fg || [255, 255, 255], bg: h.bg || [0, 0, 0] });
    });
    const out = { layers: bg.concat(mid, fg, hud) };
    if (level.camera) {
      const c = level.camera;
      out.camera = { mode: c.mode || "follow", target: c.target,
        axis: c.axis || "x", bounds: c.bounds.slice() };
    }
    if (level.zones && level.zones.length)
      out.zones = level.zones.map(function (z) { return Object.assign({}, z); });
    if (level.points && level.points.length)
      out.points = level.points.map(function (p) { return Object.assign({}, p); });
    if (level.effects && level.effects.length)
      out.effects = level.effects.map(function (r) { return Object.assign({}, r); });
    if (level.music) out.music = level.music;
    return out;
  }

  // A file merged by git can arrive with conflict markers in it, which stop it being JSON. Report
  // that as what it is - the level is fine, two edits of the same rows just need picking - instead
  // of the generic "could not read" the parse error would produce. Returns [line numbers] (1-based).
  function findConflictMarkers(text) {
    const out = [];
    text.split("\n").forEach(function (line, i) {
      if (/^(<{7}|={7}|>{7}|\|{7})( |$)/.test(line)) out.push(i + 1);
    });
    return out;
  }

  // ---------------------------------------------------------------- importers (exported -> editor)
  // The inverse of exportAssets/buildLevel: turn an EXPORTED scene or project (the bake input,
  // `layers[]`) back into an editable project. Without this the editor can only ever open a level
  // it saved itself, so a level someone else touched - a person with a text editor, an agent doing
  // a bulk pass - leaves the editor for good. Pixels are NOT in the export (assets carry a `src`
  // filename), so the caller supplies them afterwards; everything else round-trips.
  const ASSET_KEYS = ["type", "src", "frame", "tile", "size", "frames", "transparent", "color",
    "colors", "legend", "props", "animations"];
  const LEVEL_KEYS = ["name", "title", "background", "worldSize", "layers", "camera", "zones",
    "points", "effects", "music"];
  const GAME_KEYS = ["format", "version", "name", "icon", "size", "start", "launcher", "assets",
    "sounds", "scripts", "levels"];

  // Keys this editor does not model are kept aside (`extra`) and written back on export, so a
  // file that an agent or a newer tool extended survives a round trip through here untouched.
  function keepExtra(obj, known) {
    const extra = {};
    let any = false;
    for (const k in obj || {}) if (known.indexOf(k) < 0) { extra[k] = obj[k]; any = true; }
    return any ? extra : null;
  }

  function importAssets(assets) {
    const out = {};
    for (const id in assets || {}) {
      const e = assets[id], a = { type: e.type };
      const dims = e.tile || e.frame || e.size || [16, 16];
      a.fw = dims[0]; a.fh = dims[1];
      if (e.type === "sprite" || e.type === "tileset" || e.type === "bitmap") {
        a.src = e.src; a.frames = e.frames || 1;
        if (e.transparent != null) a.transparent = e.transparent;
      } else if (e.type === "rect") {
        a.color = e.color;
      } else if (e.type === "tileset_color") {
        a.colors = e.colors || {};
      }
      if (e.props) a.props = e.props;
      if (e.animations) a.animations = e.animations;
      if (e.legend) a.legend = Object.assign({}, e.legend);
      const extra = keepExtra(e, ASSET_KEYS);
      if (extra) a.extra = extra;
      out[id] = a;
    }
    return out;
  }

  // One exported level ({layers, camera, zones, points, music}) -> an editor level. `assets` =
  // the exported assets (v2 rows read their legend from them).
  function importLevel(src, name, assets) {
    const lv = newLevel(name || "level");
    // The export carries no world extent (only the device screen), so drop newLevel's default
    // one-screen worldSize and let deserialize() derive it from the content - the same path old
    // projects take. Keeping the default would shrink a scrolling level's world to one screen,
    // and with it the camera bounds.
    delete lv.worldSize;
    if (src.worldSize && src.worldSize.length === 2) lv.worldSize = src.worldSize.slice();
    if (src.title) lv.title = src.title;
    if (src.background) lv.background = src.background.slice();
    (src.layers || []).forEach(function (L) {
      if (L.kind === "tilemap") {
        const grid = layerGrid(L, assets).map(function (r) { return r.slice(); });
        lv.tilemaps.push({ asset: L.asset, cols: grid[0] ? grid[0].length : 0, rows: grid.length,
          grid: grid, pos: (L.pos || [0, 0]).slice(), fg: !!L.fg });
      } else if (L.kind === "sprite") {
        const en = { asset: L.asset, name: L.name || null, x: (L.pos || [0, 0])[0],
          y: (L.pos || [0, 0])[1], anchor: (L.anchor || [0, 0]).slice(), frame: L.frame || 0 };
        if (L.tag) en.tag = L.tag;
        if (L.anim) en.anim = L.anim;
        if (L.data) en.data = L.data;
        if (L.angle) en.angle = L.angle;
        lv.entities.push(en);
      } else if (L.kind === "group") {
        // a group is the export's FOLDING of same-tag entities; unfold it back to entities
        (L.instances || []).forEach(function (xy) {
          const en = { asset: L.asset, tag: L.tag, x: xy[0], y: xy[1],
            anchor: (L.anchor || [0, 0]).slice(), frame: 0 };
          if (L.anim) en.anim = L.anim;
          lv.entities.push(en);
        });
      } else if (L.kind === "particles") {
        lv.particles.push({ name: L.name || "fx", capacity: L.capacity || 64,
          size: L.size || 2, gravity: L.gravity || 0, fade: !!L.fade });
      } else if (L.kind === "hudlabel") {
        lv.hud.push({ name: L.name, x: (L.pos || [0, 0])[0], y: (L.pos || [0, 0])[1],
          fg: L.fg || [255, 255, 255], bg: L.bg || [0, 0, 0] });
      }
    });
    if (src.camera) lv.camera = Object.assign({}, src.camera);
    if (src.zones) lv.zones = src.zones.map(function (z) { return Object.assign({}, z); });
    if (src.points) lv.points = src.points.map(function (p) { return Object.assign({}, p); });
    if (src.effects) lv.effects = src.effects.map(function (r) { return Object.assign({}, r); });
    if (src.music) lv.music = src.music;
    const extra = keepExtra(src, LEVEL_KEYS);
    if (extra) lv.extra = extra;
    return lv;
  }

  // An exported scene OR project (v1 scene.json / project.json, v2 game.json) -> a project.
  // `name` names the single level of a scene (the export has no level name - it was the file
  // name). deserialize() then fills in everything the export does not carry: worldSize comes
  // from contentBounds, exactly as it does for projects that predate the field.
  function importExported(obj, name) {
    const p = { size: (obj.size || [320, 240]).slice(), assets: importAssets(obj.assets),
      sounds: obj.sounds || {}, levels: [], current: 0 };
    if (obj.name) p.name = obj.name;
    if (obj.icon) p.icon = obj.icon;
    if (obj.launcher) p.launcher = Object.assign({}, obj.launcher);
    if (obj.scripts) p.scripts = Object.assign({}, obj.scripts);   // v1 project.json carried Python bodies
    if (obj.format === "picogame-project" || obj.levels) {
      p.levels = (obj.levels || []).map(function (lv, i) {
        return importLevel(lv, lv.name || ("level" + (i + 1)), obj.assets);
      });
      if (obj.start) p.start = obj.start;
      // a v1 project put the legend on each layer: pull them up into the assets (append-only)
      (obj.levels || []).forEach(function (lv) {
        (lv.layers || []).forEach(function (L) {
          if (L.kind !== "tilemap" || !L.legend || !p.assets[L.asset]) return;
          const a = p.assets[L.asset];
          a.legend = a.legend || {};
          for (const ch in L.legend) if (!(ch in a.legend)) a.legend[ch] = L.legend[ch];
        });
      });
    } else {
      p.levels = [importLevel(obj, name || "level1", obj.assets)];
    }
    if (!p.levels.length) p.levels = [newLevel("level1")];
    const extra = keepExtra(obj, GAME_KEYS);
    if (extra) p.extra = extra;
    return deserialize(p);
  }

  // ---------------------------------------------------------------- game.json (v2) export
  // ONE file for the whole game: name/size/start, the assets table (references + legends +
  // props, never pixels), sounds and every level with ASCII rows. Unknown keys a tool or an agent
  // added ride through untouched (see keepExtra). This is what Save writes, what the device and
  // scene_build.py read, and what an agent edits.
  // level names are identifiers (module suffixes on the device, keys everywhere): the same rule
  // as scene_build.py's _slug, so both tools agree on the name a level gets
  function slugName(name) {
    let s = String(name == null ? "" : name).replace(/[^A-Za-z0-9_]/g, "_").toLowerCase();
    if (!s || /^[0-9]/.test(s)) s = "l_" + s;
    return s;
  }

  function exportGame(project) {
    const assets = exportAssets(project);
    for (const id in assets) {
      const a = project.assets[id];
      if (a.legend) assets[id].legend = a.legend;       // the same object: buildLevel appends to it
      if (a.extra) Object.assign(assets[id], a.extra);
    }
    // legends are shared objects between the model asset and the export: append-only growth
    for (const id in assets) if (assets[id].legend) { project.assets[id].legend = assets[id].legend; }
    const out = { format: "picogame-project", version: 2 };
    if (project.name) out.name = project.name;
    if (project.icon) out.icon = project.icon;
    out.size = project.size.slice();
    const startLv = project.levels.find(function (l) { return l.name === project.start; }) || project.levels[0];
    if (startLv) out.start = startLv.name;
    if (project.launcher) out.launcher = Object.assign({}, project.launcher);
    out.assets = assets;
    out.sounds = Object.assign({}, project.sounds || {});
    const ren = {};
    project.levels.forEach(function (l) { const sl = slugName(l.name); if (sl !== l.name) ren[l.name] = sl; });
    if (out.start in ren) out.start = ren[out.start];
    out.levels = project.levels.map(function (l) {
      const o = buildLevel(l, true, assets);
      const e = { name: ren[l.name] || l.name };
      if (l.title) e.title = l.title; else if (ren[l.name]) e.title = l.name;
      (o.zones || []).forEach(function (z) {          // goto targets follow the rename
        const d = z.data; if (!d || !d.goto) return;
        if (Array.isArray(d.goto)) { if (d.goto[0] in ren) { d.goto = d.goto.slice(); d.goto[0] = ren[d.goto[0]]; } }
        else if (d.goto in ren) d.goto = ren[d.goto];
      });
      e.background = l.background.slice();
      // worldSize is written only when it says more than the content does (a level whose world
      // equals its painted extent round-trips without the key, as it was authored)
      const cb = contentBounds(project, l);
      if (l.worldSize && (l.worldSize[0] !== cb[0] || l.worldSize[1] !== cb[1])) e.worldSize = l.worldSize.slice();
      e.layers = o.layers;
      if (o.camera) e.camera = o.camera;
      if (o.zones) e.zones = o.zones;
      if (o.points) e.points = o.points;
      if (o.effects) e.effects = o.effects;
      if (o.music) e.music = o.music;
      if (l.extra) Object.assign(e, l.extra);
      return e;
    });
    if (project.extra) for (const k in project.extra) if (!(k in out)) out[k] = project.extra[k];
    return out;
  }

  // ---------------------------------------------------------------- canonical text
  // The ONE text form of a game.json, byte-identical to `scene_build.py fmt` (key order from the
  // shared tables, indent 1, scalar arrays on one line = a map row per line, integral floats as
  // ints, UTF-8 as is, trailing newline). Both writers are golden-tested against the same fixture,
  // so an agent's `fmt` and the editor's Save never fight over whitespace.
  const ORDER = {
    project: GAME_KEYS,
    asset: ASSET_KEYS,
    level: LEVEL_KEYS,
    layer: ["kind", "asset", "name", "tag", "pos", "anchor", "frame", "anim", "angle", "data",
      "instances", "fg", "bg", "capacity", "size", "gravity", "fade", "legend", "rows", "grid"],
    zone: ["tag", "x", "y", "w", "h", "data"],
    point: ["name", "x", "y", "data"],
    camera: ["mode", "target", "axis", "bounds"],
  };
  function childKind(kind, key) {
    if (kind === "project") return { assets: "assets", levels: "level" }[key] || null;
    if (kind === "assets") return "asset";
    if (kind === "level") return { layers: "layer", zones: "zone", points: "point", camera: "camera" }[key] || null;
    return null;
  }
  function orderedKeys(obj, kind) {
    const keys = Object.keys(obj);
    if (kind === "assets") return keys.slice().sort();   // the assets table: by id, like fmt
    if (kind && ORDER[kind]) {
      const known = ORDER[kind].filter(function (k) { return k in obj; });
      const rest = keys.filter(function (k) { return ORDER[kind].indexOf(k) < 0; }).sort();
      return known.concat(rest);
    }
    // a plain dict: digit keys first in numeric order, then the others as they came (what both
    // JS objects and Python dicts can promise)
    const num = keys.filter(function (k) { return /^-?\d+$/.test(k); }).sort(function (a, b) { return a - b; });
    return num.concat(keys.filter(function (k) { return !/^-?\d+$/.test(k); }));
  }
  function scalar(v) {
    if (v === true) return "true";
    if (v === false) return "false";
    if (v == null) return "null";
    if (typeof v === "number") return Number.isFinite(v) ? String(v) : "null";
    return JSON.stringify(v);
  }
  function isScalarList(v) {
    return Array.isArray(v) && v.every(function (x) { return x === null || typeof x !== "object"; });
  }
  // numbers (a position, a colour, a bounds box) stay on one line; strings (map rows, dialogue
  // lines) go one per line so a map reads as a picture
  function isInlineList(v) { return isScalarList(v) && v.every(function (x) { return typeof x !== "string"; }); }
  function canonical(obj, kind, ind) {
    const pad = " ".repeat(ind || 0);
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      const keys = orderedKeys(obj, kind);
      if (!keys.length) return "{}";
      return "{\n" + keys.map(function (k) {
        return pad + " " + JSON.stringify(k) + ": " + canonical(obj[k], childKind(kind, k), (ind || 0) + 1);
      }).join(",\n") + "\n" + pad + "}";
    }
    if (Array.isArray(obj)) {
      if (!obj.length) return "[]";
      if (isInlineList(obj)) return "[" + obj.map(scalar).join(", ") + "]";
      if (isScalarList(obj)) return "[\n" + obj.map(function (x) { return pad + " " + scalar(x); }).join(",\n") + "\n" + pad + "]";
      return "[\n" + obj.map(function (x) { return pad + " " + canonical(x, kind, (ind || 0) + 1); }).join(",\n") + "\n" + pad + "]";
    }
    return scalar(obj);
  }
  function canonicalJson(game) { return canonical(game, "project", 0) + "\n"; }

  // ---------------------------------------------------------------- .pal8 sidecars
  // The device reads pixels from <stem>.pal8 next to game.json (picogame_scene.read_pal8):
  // "PAL8" | ver u8 | flags u8 (bit0: index 0 transparent) | fw u16 | fh u16 | frames u16 |
  // ncol u16 | reserved u16 (16 bytes, little-endian) | ncol x u16 wire-RGB565 | fw*frames*fh indices.
  function encodePal8(data, fw, fh, frames, palette, transparent) {
    if (data.length !== fw * frames * fh) throw new Error("pal8 data is " + data.length + " bytes, expected " + fw * frames * fh);
    const out = new Uint8Array(16 + palette.length * 2 + data.length);
    const dv = new DataView(out.buffer);
    out[0] = 0x50; out[1] = 0x41; out[2] = 0x4C; out[3] = 0x38;      // "PAL8"
    out[4] = 1; out[5] = transparent === 0 ? 1 : 0;
    dv.setUint16(6, fw, true); dv.setUint16(8, fh, true); dv.setUint16(10, frames, true);
    dv.setUint16(12, palette.length, true); dv.setUint16(14, 0, true);
    palette.forEach(function (c, i) { dv.setUint16(16 + i * 2, c, true); });
    out.set(data, 16 + palette.length * 2);
    return out;
  }
  function decodePal8(u8) {
    if (u8.length < 16 || u8[0] !== 0x50 || u8[1] !== 0x41 || u8[2] !== 0x4C || u8[3] !== 0x38) throw new Error("not a .pal8 file");
    const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    const fw = dv.getUint16(6, true), fh = dv.getUint16(8, true), frames = dv.getUint16(10, true), ncol = dv.getUint16(12, true);
    const palette = [];
    for (let i = 0; i < ncol; i++) palette.push(dv.getUint16(16 + i * 2, true));
    const data = u8.subarray(16 + ncol * 2, 16 + ncol * 2 + fw * frames * fh);
    return { fw: fw, fh: fh, frames: frames, palette: palette, data: data, transparent: (u8[5] & 1) ? 0 : null };
  }
  // wire-order RGB565 -> [r, g, b] (the inverse of w565, for showing a .pal8 in the editor)
  function fromW565(w) {
    const c = ((w & 0xFF) << 8) | (w >> 8);
    const r = (c >> 11) & 31, g = (c >> 5) & 63, b = c & 31;
    return [(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)];
  }
  // a decoded .pal8 -> RGBA bytes of the whole strip (index 0 transparent)
  function pal8ToRGBA(p) {
    const w = p.fw * p.frames, h = p.fh, out = new Uint8ClampedArray(w * h * 4);
    const rgb = p.palette.map(fromW565);
    for (let i = 0; i < w * h; i++) {
      const v = p.data[i];
      if (!v) continue;
      const c = rgb[v] || [255, 0, 255];
      out[i * 4] = c[0]; out[i * 4 + 1] = c[1]; out[i * 4 + 2] = c[2]; out[i * 4 + 3] = 255;
    }
    return { rgba: out, w: w, h: h };
  }

  function exportScene(project, idx, ascii) {
    const level = project.levels[idx == null ? project.current : idx];
    const o = buildLevel(level, ascii);
    const out = { format: "picogame-scene", version: 1, size: project.size.slice(),
      background: level.background.slice(), assets: exportAssets(project), layers: o.layers };
    if (o.camera) out.camera = o.camera;
    if (o.zones) out.zones = o.zones;
    if (o.points) out.points = o.points;
    if (Object.keys(project.sounds || {}).length) out.sounds = project.sounds;
    if (o.music) out.music = o.music;
    return out;
  }

  function exportProject(project, ascii) {
    const out = { format: "picogame-project", version: 1, size: project.size.slice(),
      assets: exportAssets(project), levels: [] };
    if (Object.keys(project.sounds || {}).length) out.sounds = project.sounds;
    out.levels = project.levels.map(function (l) {
      const o = buildLevel(l, ascii);
      const e = { name: l.name, background: l.background.slice(), layers: o.layers };
      if (o.camera) e.camera = o.camera;
      if (o.zones) e.zones = o.zones;
      if (o.points) e.points = o.points;
      if (o.music) e.music = o.music;
      return e;
    });
    return out;
  }

  // ---------------------------------------------------------------- save / load
  function serialize(project) {
    return { format: "picogame-project-save", version: 1, project: project };
  }

  // Accept old + new save shapes. Migrations kept identical to the historical editor:
  //   flat project (no levels[])          -> single level
  //   level with single `tilemap`          -> tilemaps[]
  // plus fill in newer per-level arrays (zones/points/particles) so old files open.
  function deserialize(obj) {
    const p = (obj && obj.project) ? obj.project : obj;
    if (!p.assets) p.assets = {};
    if (!p.sounds) p.sounds = {};
    if (!p.size) p.size = [320, 240];
    if (!p.levels) {                                   // migrate old flat project
      const lv = newLevel("level1");
      lv.background = p.background || lv.background;
      lv.entities = p.entities || []; lv.hud = p.hud || []; lv.camera = p.camera || null;
      if (p.tilemap) lv.tilemaps = [p.tilemap];
      p.levels = [lv];
      ["background", "tilemap", "entities", "hud", "camera"].forEach(function (k) { delete p[k]; });
    }
    p.levels.forEach(function (lv) {                   // migrate single tilemap -> tilemaps[]
      if (lv.tilemap && !lv.tilemaps) { lv.tilemaps = [lv.tilemap]; delete lv.tilemap; }
      if (!lv.tilemaps) lv.tilemaps = [];
      if (!lv.entities) lv.entities = [];
      if (!lv.hud) lv.hud = [];
      if (!lv.zones) lv.zones = [];
      if (!lv.points) lv.points = [];
      if (!lv.particles) lv.particles = [];
      // back-fill authoring cols/rows for old tilemaps that only stored a grid
      lv.tilemaps.forEach(function (tm) {
        if (tm.rows == null) tm.rows = tm.grid ? tm.grid.length : 0;
        if (tm.cols == null) tm.cols = tm.grid && tm.grid[0] ? tm.grid[0].length : 0;
        if (!tm.pos) tm.pos = [0, 0];
      });
      // migrate the world extent to the explicit worldSize field: old projects have no
      // worldSize, so derive it from the union of layer/object extents (falls back to the
      // device screen when the level is empty). New projects already carry it.
      if (!lv.worldSize || lv.worldSize.length !== 2) lv.worldSize = contentBounds(p, lv);
    });
    if (p.current == null || p.current >= p.levels.length) p.current = 0;
    return p;
  }

  // ---------------------------------------------------------------- Tiled import
  // Verified Tiled(H|V<<1|D<<2) -> picogame(flipX|flipY<<1|transpose<<2) orientation map.
  // The flip axes SWAP when the diagonal bit is set (Tiled flips AFTER its x/y swap; the
  // engine flips source coords) - regression-tested in test.js, do not simplify.
  const TILED_ORIENT = { 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 5, 7: 7 };
  const GID_H = 0x80000000, GID_V = 0x40000000, GID_D = 0x20000000, GID_MASK = 0x0FFFFFFF;

  // Convert a Tiled map (JSON shape; every tilelayer's `data` ALREADY an int array -
  // the caller decodes base64/zlib) into an editor project + a tileset repack plan.
  // `external` = {basename: tilesetDict} for <tileset source="..."> references.
  // Tilesets are COMPACTED: the plan lists only the tiles the map uses (engine cells
  // are one byte -> max 253 distinct tiles per tileset).
  // Returns { project, repack: [{asset, image, tw, th, columns, spacing, margin,
  //           transparent, used}], warnings: [..] }.
  function importTiled(map, external) {
    const warnings = [];
    if (map.orientation !== "orthogonal") throw new Error("only orthogonal maps convert (map is " + map.orientation + ")");
    if (map.infinite) throw new Error("infinite maps are not supported - set a fixed map size in Tiled");

    // resolve tilesets
    const tilesets = (map.tilesets || []).map(function (e) {
      let ts = e;
      if (e.source) {
        const base = e.source.replace(/^.*[\/\\]/, "");
        ts = (external || {})[base];
        if (!ts) throw new Error("external tileset not among the selected files: " + base);
        ts = Object.assign({ firstgid: e.firstgid }, ts);
      }
      if (!ts.image) throw new Error("tileset " + (ts.name || "?") + ": image-collection tilesets are not supported");
      const name = String(ts.name || "tiles").toLowerCase().replace(/[^a-z0-9]/g, "_");
      const props = {};
      let anims = 0;
      (ts.tiles || []).forEach(function (t) {
        const flags = {};
        (t.properties || []).forEach(function (pr) {
          if (typeof pr.value === "boolean") { if (pr.value) flags[pr.name] = true; }
          else warnings.push("tileset " + name + " tile " + t.id + ": non-bool property " + pr.name + " ignored");
        });
        if (Object.keys(flags).length) props[t.id] = flags;
        if (t.animation) anims++;
      });
      if (anims) warnings.push("tileset " + name + ": " + anims + " animated tile(s) - static tile used");
      return { firstgid: ts.firstgid, name: name,
        tw: ts.tilewidth, th: ts.tileheight, count: ts.tilecount || 0,
        columns: ts.columns || 1, spacing: ts.spacing || 0, margin: ts.margin || 0,
        image: String(ts.image).replace(/^.*[\/\\]/, ""),
        transparent: ts.transparentcolor || null, rawprops: props };
    }).sort(function (a, b) { return a.firstgid - b.firstgid; });

    function tsFor(gid) {
      let hit = null;
      for (const ts of tilesets) { if (ts.firstgid <= gid) hit = ts; else break; }
      return (hit && gid - hit.firstgid < hit.count) ? hit : null;
    }

    // pass 1: which tiles does the map use?
    const used = {};
    (function collect(layers) {
      (layers || []).forEach(function (L) {
        if (L.visible === false) return;
        if (L.type === "group") collect(L.layers);
        else if (L.type === "tilelayer") (L.data || []).forEach(function (gid) {
          const ts = gid && tsFor(gid & GID_MASK);
          if (ts) (used[ts.name] = used[ts.name] || new Set()).add((gid & GID_MASK) - ts.firstgid);
        });
        else if (L.type === "objectgroup") (L.objects || []).forEach(function (o) {
          const ts = o.gid && tsFor(o.gid & GID_MASK);
          if (ts) (used[ts.name] = used[ts.name] || new Set()).add((o.gid & GID_MASK) - ts.firstgid);
        });
      });
    })(map.layers);

    const project = newProject();          // project.size stays the device screen
    const level = project.levels[0];
    level.worldSize = [map.width * map.tilewidth, map.height * map.tileheight];
    if (map.backgroundcolor) {
      const h = map.backgroundcolor.replace("#", "").slice(-6);
      level.background = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    }

    const repack = [];
    tilesets.forEach(function (ts) {
      const u = Array.from(used[ts.name] || []).sort(function (a, b) { return a - b; });
      ts.remap = {};
      if (!u.length) { warnings.push("tileset " + ts.name + ": unused - skipped"); return; }
      if (u.length > 253) throw new Error("tileset " + ts.name + ": " + u.length + " distinct tiles in use (max 253 - engine cells are one byte)");
      u.forEach(function (tid, slot) { ts.remap[tid] = slot + 1; });
      const props = {};
      u.forEach(function (tid) { if (ts.rawprops[tid]) props[String(ts.remap[tid])] = ts.rawprops[tid]; });
      project.assets[ts.name] = { type: "tileset", src: ts.image, fw: ts.tw, fh: ts.th,
        frames: u.length + 1, transparent: 0 };
      if (Object.keys(props).length) project.assets[ts.name].props = props;
      repack.push({ asset: ts.name, image: ts.image, tw: ts.tw, th: ts.th,
        columns: ts.columns, spacing: ts.spacing, margin: ts.margin,
        transparent: ts.transparent, used: u });
    });

    (function walk(layers, offx, offy) {
      (layers || []).forEach(function (L) {
        if (L.visible === false) { warnings.push("layer " + L.name + ": hidden - skipped"); return; }
        if (L.type === "group") { walk(L.layers, offx + (L.offsetx || 0), offy + (L.offsety || 0)); return; }
        if (L.type === "imagelayer") { warnings.push("layer " + L.name + ": image layers are not supported - skipped"); return; }
        if (L.type === "tilelayer") {
          if ((L.opacity != null && L.opacity !== 1)) warnings.push("layer " + L.name + ": opacity ignored");
          if ((L.parallaxx || 1) !== 1 || (L.parallaxy || 1) !== 1) warnings.push("layer " + L.name + ": parallax ignored");
          const perTs = {};
          (L.data || []).forEach(function (gid, i) {
            if (!gid) return;
            const bits = (gid & GID_H ? 1 : 0) | (gid & GID_V ? 2 : 0) | (gid & GID_D ? 4 : 0);
            const ts = tsFor(gid & GID_MASK);
            if (!ts) { warnings.push("layer " + L.name + " cell " + i + ": unknown gid - left empty"); return; }
            let tm = perTs[ts.name];
            if (!tm) {
              tm = perTs[ts.name] = newTilemap(ts.name, L.width, L.height, false);
              tm.pos = [Math.round((L.offsetx || 0) + offx), Math.round((L.offsety || 0) + offy)];
            }
            tm.grid[(i / L.width) | 0][i % L.width] =
              ts.remap[(gid & GID_MASK) - ts.firstgid] | (TILED_ORIENT[bits] << 8);
          });
          const names = Object.keys(perTs);
          if (names.length > 1) warnings.push("layer " + L.name + ": uses " + names.length + " tilesets - split into " + names.length + " layers");
          tilesets.forEach(function (ts) { if (perTs[ts.name]) level.tilemaps.push(perTs[ts.name]); });
          return;
        }
        if (L.type === "objectgroup") {
          (L.objects || []).forEach(function (o) {
            const data = {};
            (o.properties || []).forEach(function (pr) { data[pr.name] = pr.value; });
            const hasData = Object.keys(data).length > 0;
            const x = o.x + offx, y = o.y + offy;
            if (o.gid) {
              const ts = tsFor(o.gid & GID_MASK);
              if (!ts || !ts.remap[(o.gid & GID_MASK) - ts.firstgid]) { warnings.push("object " + (o.name || o.id) + ": unknown gid - skipped"); return; }
              if (o.gid & (GID_H | GID_V | GID_D)) warnings.push("object " + (o.name || o.id) + ": flip bits on a tile object dropped");
              const en = { asset: ts.name, name: o.name || null, tag: null,
                x: Math.round(x), y: Math.round(y), anchor: [0, 1],
                frame: ts.remap[(o.gid & GID_MASK) - ts.firstgid], data: hasData ? data : null };
              if (o.rotation) en.angle = Math.round(o.rotation) % 360;
              level.entities.push(en);
            } else if (o.point) {
              if (!o.name) { warnings.push("point object #" + o.id + " has no name - skipped"); return; }
              const pt = { name: o.name, x: Math.round(x), y: Math.round(y) };
              if (hasData) pt.data = data;
              level.points.push(pt);
            } else if (o.ellipse || o.polygon || o.polyline || o.text) {
              warnings.push("object " + (o.name || o.id) + ": shape objects are not supported - skipped");
            } else {
              const z = { tag: o.class || o.type || o.name || null, x: Math.round(x), y: Math.round(y),
                w: Math.round(o.width || 0), h: Math.round(o.height || 0) };
              if (hasData) z.data = data;
              level.zones.push(z);
            }
          });
        }
      });
    })(map.layers, 0, 0);

    return { project: project, repack: repack, warnings: warnings };
  }

  // ---------------------------------------------------------------- PAL8 baking (in-browser)
  // Quantize an RGBA pixel buffer (a horizontal frame strip, w = fw*frames) to the engine's PAL8
  // atlas: index 0 = transparent (alpha < 128, the CLI's rule), indices 1..255 = a shared palette.
  // Wire-order RGB565 palette (byte-swapped), byte-identical to scene_build.py's w565. Up to 255
  // distinct opaque colours are kept EXACTLY (the common pixel-art case = lossless, so this path
  // is byte-identical to the CLI's bake_png output for such art); more are median-cut to 255.
  function w565(r, g, b) {
    const c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
    return ((c >> 8) | (c << 8)) & 0xFFFF;
  }
  function medianCut(colors, n) {           // colors: [[r,g,b,count]] -> up to n representative [r,g,b]
    let boxes = [colors];
    while (boxes.length < n) {
      let bi = -1, best = -1;
      boxes.forEach(function (b, i) {
        if (b.length < 2) return;
        const rng = [0, 1, 2].map(function (c) {
          let lo = 255, hi = 0; b.forEach(function (p) { if (p[c] < lo) lo = p[c]; if (p[c] > hi) hi = p[c]; });
          return hi - lo;
        });
        const m = Math.max(rng[0], rng[1], rng[2]);
        if (m > best) { best = m; bi = i; }
      });
      if (bi < 0 || best === 0) break;
      const b = boxes[bi];
      const rng = [0, 1, 2].map(function (c) {
        let lo = 255, hi = 0; b.forEach(function (p) { if (p[c] < lo) lo = p[c]; if (p[c] > hi) hi = p[c]; });
        return hi - lo;
      });
      const axis = rng.indexOf(Math.max(rng[0], rng[1], rng[2]));
      b.sort(function (x, y) { return x[axis] - y[axis]; });
      const total = b.reduce(function (a, p) { return a + p[3]; }, 0);
      let acc = 0, cut = 1;
      for (let i = 0; i < b.length - 1; i++) { acc += b[i][3]; if (acc * 2 >= total) { cut = i + 1; break; } }
      boxes.splice(bi, 1, b.slice(0, cut), b.slice(cut));
    }
    return boxes.map(function (b) {
      let r = 0, g = 0, bl = 0, n = 0;
      b.forEach(function (p) { r += p[0] * p[3]; g += p[1] * p[3]; bl += p[2] * p[3]; n += p[3]; });
      return [Math.round(r / n), Math.round(g / n), Math.round(bl / n)];
    });
  }
  function bakePal8(rgba, w, h) {
    // rgba: Uint8ClampedArray/array of length w*h*4 -> { data: Uint8Array(w*h), palette: [wire565...] }
    // Palette = the distinct opaque colours in FIRST-SEEN order scanning the strip row by row -
    // exactly what scene_build.py's quantize_png does, so both write byte-identical .pal8 files.
    // More than 255 colours or a soft alpha is an error (pixel art has neither; two quantizers
    // could never agree): run tools/png2picogame.py once on such art.
    const data = new Uint8Array(w * h);
    const idxOf = {};
    const palette = [0];
    for (let i = 0; i < w * h; i++) {
      const a = rgba[i * 4 + 3];
      if (a < 128) {
        if (a !== 0) throw new Error("soft alpha at pixel " + (i % w) + "," + ((i / w) | 0) + " - picogame art is hard-edged (flatten it, or run tools/png2picogame.py)");
        continue;
      }
      if (a !== 255) throw new Error("soft alpha at pixel " + (i % w) + "," + ((i / w) | 0) + " - picogame art is hard-edged (flatten it, or run tools/png2picogame.py)");
      const k = (rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2];
      let idx = idxOf[k];
      if (idx === undefined) {
        if (palette.length > 255) throw new Error("more than 255 colours - quantize it once with tools/png2picogame.py");
        idx = idxOf[k] = palette.length;
        palette.push(w565(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]));
      }
      data[i] = idx;
    }
    return { data: data, palette: palette };
  }
  function bytesToBase64(u8) {
    let s = "";
    for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return (typeof btoa !== "undefined") ? btoa(s) : Buffer.from(s, "binary").toString("base64");
  }
  // Replace one PNG-backed exported asset with an inline PAL8 atlas the browser baker accepts.
  function inlinePal8Asset(asset, rgba, w, h) {
    const q = bakePal8(rgba, w, h);
    const fw = (asset.tile || asset.frame || [w, h]);
    const out = { type: "pal8_inline", data: bytesToBase64(q.data), width: w, height: h,
      frames: asset.frames || 1, palette: q.palette };
    if (asset.tile) out.tile = asset.tile.slice(); else out.frame = fw.slice();
    if (asset.props) out.props = asset.props;
    if (asset.animations) out.animations = asset.animations;
    return out;
  }

  // ---------------------------------------------------------------- in-browser scene bake
  // Mirror of tools/scene_build.py's single-scene path (and web/play/scene_bake.py) producing the
  // SAME runtime SCENE structure - so the editor can hand out a ready `<name>_scene.py` module
  // (SCENE = {...}) with no Python step. Values are typed for pyRepr: PyTuple / PyBytes wrappers
  // keep tuple-vs-list and bytes-vs-str distinct so the emitted repr matches CPython's byte for byte.
  function PyTuple(a) { this.a = a; }
  function PyBytes(u8) { this.u8 = u8; }
  function PyFloat(v) { this.v = v; }          // JS can't tell 0 from 0.0; wrap where CPython has a float
  const T = (...a) => new PyTuple(a);
  function pyRepr(v) {
    if (v === null || v === undefined) return "None";
    if (v === true) return "True";
    if (v === false) return "False";
    if (v instanceof PyFloat) return Number.isInteger(v.v) ? v.v.toFixed(1) : String(v.v);
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(v);
    if (typeof v === "string") return pyStr(v);
    if (v instanceof PyBytes) return pyBytesRepr(v.u8);
    if (v instanceof PyTuple) return "(" + v.a.map(pyRepr).join(", ") + (v.a.length === 1 ? "," : "") + ")";
    if (Array.isArray(v)) return "[" + v.map(pyRepr).join(", ") + "]";
    if (typeof v === "object") return "{" + Object.keys(v).map(k => pyStr(k) + ": " + pyRepr(v[k])).join(", ") + "}";
    return String(v);
  }
  function pyStr(s) {
    // CPython repr: single quotes unless the string has ' and no "
    const q = (s.includes("'") && !s.includes('"')) ? '"' : "'";
    let out = q;
    for (const ch of s) {
      const c = ch.codePointAt(0);
      if (ch === q || ch === "\\") out += "\\" + ch;
      else if (ch === "\n") out += "\\n"; else if (ch === "\r") out += "\\r"; else if (ch === "\t") out += "\\t";
      else if (c < 0x20 || c === 0x7f) out += "\\x" + c.toString(16).padStart(2, "0");
      else out += ch;
    }
    return out + q;
  }
  function pyBytesRepr(u8) {
    let s = "b'";
    for (let i = 0; i < u8.length; i++) {
      const b = u8[i];
      if (b === 0x27) s += "\\'"; else if (b === 0x5c) s += "\\\\";
      else if (b === 0x0a) s += "\\n"; else if (b === 0x0d) s += "\\r"; else if (b === 0x09) s += "\\t";
      else if (b >= 0x20 && b < 0x7f) s += String.fromCharCode(b);
      else s += "\\x" + b.toString(16).padStart(2, "0");
    }
    return s + "'";
  }
  function hexOf(u8) { let s = ""; for (let i = 0; i < u8.length; i++) s += u8[i].toString(16).padStart(2, "0"); return s; }
  function b64ToU8(b64) { const bin = (typeof atob !== "undefined") ? atob(b64) : Buffer.from(b64, "base64").toString("binary"); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }

  // Bake ONE exported scene (exportScene() output; PNG assets must already be pal8_inline -
  // the editor's handoff does that) -> the runtime SCENE dict (JS values, tuples/bytes typed).
  function bakeScene(scene) {
    const size = scene.size || [320, 240];
    const rgb = c => w565(c[0], c[1], c[2]);
    const assets = {}, tileprops = {}, anims = {};
    for (const aid in scene.assets) {
      const a = scene.assets[aid];
      let baked;
      if (a.type === "pal8_inline") {
        const fw = (a.tile || a.frame || [a.width, a.height]);
        baked = T("pal8", hexOf(b64ToU8(a.data)), fw[0], fw[1], a.frames || 1, 0, new PyTuple(a.palette.slice()));
      } else if (a.type === "rect") {
        const w = a.size[0], h = a.size[1];
        baked = T("pal8", "01".repeat(w * h), w, h, 1, null, T(rgb([0, 0, 0]), rgb(a.color)));
      } else if (a.type === "tileset_color") {
        const tw = a.tile[0], th = a.tile[1];
        const keys = Object.keys(a.colors).map(Number); const n = keys.length ? Math.max(...keys) : 0;
        const frames = n + 1, stride = tw * frames;
        const data = new Uint8Array(stride * th);
        for (let f = 1; f < frames; f++) for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) data[y * stride + f * tw + x] = f;
        const pal = [rgb([0, 0, 0])];
        for (let v = 1; v < frames; v++) pal.push(rgb(a.colors[String(v)] || [255, 0, 255]));
        baked = T("pal8", hexOf(data), tw, th, frames, 0, new PyTuple(pal));
      } else {
        throw new Error("asset '" + aid + "' (" + a.type + ") has no image data - re-import its PNG");
      }
      assets[aid] = baked;
      if (a.props) {
        let length = Math.max(...Object.keys(a.props).map(Number)) + 1;
        if (a.frames) length = Math.max(length, a.frames);
        if (a.colors) length = Math.max(length, Math.max(...Object.keys(a.colors).map(Number)) + 1);
        const names = new Set(); Object.values(a.props).forEach(f => Object.keys(f).forEach(k => names.add(k)));
        const tp = {};
        Array.from(names).sort().forEach(nm => { const b = new Uint8Array(length); for (const vs in a.props) if (a.props[vs][nm]) b[+vs] = 1; tp[nm] = new PyBytes(b); });
        tileprops[aid] = tp;
      }
      if (a.animations) {
        const an = {};
        for (const nm in a.animations) { const d = a.animations[nm]; an[nm] = T(new PyTuple(d.frames.slice()), d.fps == null ? 8 : d.fps, d.loop == null ? true : d.loop); }
        anims[aid] = an;
      }
    }
    const layers = (scene.layers || []).map(L => {
      if (L.kind === "tilemap") {
        const g2 = layerGrid(L), nrows = g2.length, cols = nrows ? g2[0].length : 0;
        const grid = new Uint8Array(cols * nrows); let orient = null;
        g2.forEach((row, ry) => { for (let cx = 0; cx < cols; cx++) { const v = cx < row.length ? row[cx] : 0; grid[ry * cols + cx] = v & 0xFF; if (v >> 8) { if (!orient) orient = new Uint8Array(cols * nrows); orient[ry * cols + cx] = v >> 8; } } });
        const pos = L.pos || [0, 0];
        const t = ["tilemap", L.asset, cols, nrows, pos[0], pos[1], new PyBytes(grid)];
        if (orient) t.push(new PyBytes(orient));
        return new PyTuple(t);
      }
      if (L.kind === "sprite") {
        const an = L.anchor || [0, 0];
        return T("sprite", L.asset, L.name == null ? null : L.name, L.pos[0], L.pos[1], an[0], an[1], L.frame || 0, L.data == null ? null : L.data, L.anim == null ? null : L.anim, L.angle || 0);
      }
      if (L.kind === "group") {
        const an = L.anchor || [0, 0];
        return T("group", L.asset, L.tag == null ? null : L.tag, an[0], an[1], new PyTuple(L.instances.map(p => new PyTuple(p.slice()))), L.anim == null ? null : L.anim);
      }
      if (L.kind === "hudlabel" || L.kind === "hud") return T("hudlabel", L.name == null ? null : L.name, L.pos[0], L.pos[1], rgb(L.fg || [255, 255, 255]), rgb(L.bg || [0, 0, 0]));
      if (L.kind === "particles") return T("particles", L.name == null ? null : L.name, L.capacity == null ? 64 : L.capacity, L.size == null ? 1 : L.size, L.gravity == null ? new PyFloat(0.0) : L.gravity, !!L.fade);
      throw new Error("unknown layer kind: " + L.kind);
    });
    const out = { bg: rgb(scene.background || [0, 0, 0]), assets: assets, tileprops: tileprops, anims: anims, layers: layers };
    if (scene.camera) { const c = scene.camera, b = c.bounds || [0, 0, size[0], size[1]]; out.camera = T(c.mode || "follow", c.target == null ? null : c.target, c.axis || "x", b[0], b[1], b[2], b[3]); }
    if (scene.sounds && Object.keys(scene.sounds).length) { const snd = {}; for (const k in scene.sounds) { const v = scene.sounds[k]; snd[k] = (v && typeof v === "object") ? v.src : v; } out.sounds = snd; }
    if (scene.zones && scene.zones.length) out.zones = scene.zones.map(z => { const t = [z.tag == null ? null : z.tag, z.x, z.y, z.w, z.h]; if (z.data && Object.keys(z.data).length) t.push(z.data); return new PyTuple(t); });
    if (scene.points && scene.points.length) {
      const pts = {}, pdata = {};
      scene.points.forEach(p => { if (p.name) { pts[p.name] = T(p.x, p.y); if (p.data && Object.keys(p.data).length) pdata[p.name] = p.data; } });
      out.points = pts; if (Object.keys(pdata).length) out.pdata = pdata;
    }
    if (scene.music) out.music = scene.music;
    return out;
  }
  function sceneModule(scene) { return "# AUTO-GENERATED by tools/scene_build.py\nSCENE = " + pyRepr(bakeScene(scene)) + "\n"; }

  // deep clone via JSON -- the project is plain data, so this is the undo snapshot too.
  function clone(project) { return JSON.parse(JSON.stringify(project)); }

  const api = { newProject: newProject, newLevel: newLevel, newTilemap: newTilemap,
    newParticles: newParticles, setTileProp: setTileProp, resizeTilemap: resizeTilemap,
    levelBounds: levelBounds, contentBounds: contentBounds, fillLayersToWorld: fillLayersToWorld,
    layerSizeForWorld: layerSizeForWorld,
    tileW: tileW, tileH: tileH, isImg: isImg, tileCount: tileCount,
    removeAsset: removeAsset, exportAssets: exportAssets, exportScene: exportScene,
    layerGrid: layerGrid, asciiRows: asciiRows,
    importExported: importExported, importLevel: importLevel, importAssets: importAssets,
    findConflictMarkers: findConflictMarkers,
    exportProject: exportProject, exportGame: exportGame, canonicalJson: canonicalJson,
    encodePal8: encodePal8, decodePal8: decodePal8, pal8ToRGBA: pal8ToRGBA, fromW565: fromW565,
    serialize: serialize, deserialize: deserialize, clone: clone,
    importTiled: importTiled, TILED_ORIENT: TILED_ORIENT, slugName: slugName,
    bakePal8: bakePal8, inlinePal8Asset: inlinePal8Asset, w565: w565,
    bakeScene: bakeScene, sceneModule: sceneModule, pyRepr: pyRepr, PyTuple: PyTuple, PyBytes: PyBytes, PyFloat: PyFloat };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PGEditor = api;
})(typeof window !== "undefined" ? window : globalThis);
