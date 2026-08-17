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
      if (a.props) e.props = a.props;
      if (a.animations) e.animations = a.animations;
      out[id] = e;
    }
    return out;
  }

  function tilemapLayer(tm) {
    const L = { kind: "tilemap", asset: tm.asset, pos: tm.pos.slice(),
      grid: tm.grid.map(function (r) { return r.slice(); }) };
    if (tm.fg) L.fg = true;
    return L;
  }

  // ordered layers (bg tilemaps -> sprites/groups/particles -> fg tilemaps -> hud)
  // + camera/zones/points/music for one level.
  function buildLevel(level) {
    const bg = [], mid = [], fg = [], hud = [];
    (level.tilemaps || []).forEach(function (tm) { (tm.fg ? fg : bg).push(tilemapLayer(tm)); });
    const byTag = {};
    (level.entities || []).forEach(function (en) {
      if (en.tag) {
        const g = byTag[en.tag] = byTag[en.tag] ||
          { asset: en.asset, anchor: en.anchor, anim: en.anim, insts: [] };
        g.insts.push([en.x, en.y]);
      } else {
        const L = { kind: "sprite", asset: en.asset, name: en.name || null,
          pos: [en.x, en.y], anchor: (en.anchor || [0, 0]).slice(), frame: en.frame || 0 };
        if (en.anim) L.anim = en.anim;
        if (en.data) L.data = en.data;
        if (en.angle) L.angle = en.angle;
        mid.push(L);
      }
    });
    for (const tag in byTag) {
      const g = byTag[tag];
      const L = { kind: "group", asset: g.asset, tag: tag,
        anchor: (g.anchor || [0, 0]).slice(), instances: g.insts };
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
    if (level.music) out.music = level.music;
    return out;
  }

  function exportScene(project, idx) {
    const level = project.levels[idx == null ? project.current : idx];
    const o = buildLevel(level);
    const out = { format: "picogame-scene", version: 1, size: project.size.slice(),
      background: level.background.slice(), assets: exportAssets(project), layers: o.layers };
    if (o.camera) out.camera = o.camera;
    if (o.zones) out.zones = o.zones;
    if (o.points) out.points = o.points;
    if (Object.keys(project.sounds || {}).length) out.sounds = project.sounds;
    if (o.music) out.music = o.music;
    return out;
  }

  function exportProject(project) {
    const out = { format: "picogame-project", version: 1, size: project.size.slice(),
      assets: exportAssets(project), levels: [] };
    if (Object.keys(project.sounds || {}).length) out.sounds = project.sounds;
    out.levels = project.levels.map(function (l) {
      const o = buildLevel(l);
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
    const hist = {};
    for (let i = 0; i < w * h; i++) {
      if (rgba[i * 4 + 3] < 128) continue;
      const k = (rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2];
      hist[k] = (hist[k] || 0) + 1;
    }
    let colors = Object.keys(hist).map(function (k) { k = +k; return [k >> 16, (k >> 8) & 255, k & 255, hist[k]]; });
    // preserve first-seen order for the exact case (deterministic, matches a scan of the strip)
    let reps = colors.length <= 255 ? colors.map(function (c) { return [c[0], c[1], c[2]]; }) : medianCut(colors, 255);
    const idxOf = {};                        // exact colour -> palette index (1-based)
    reps.forEach(function (c, i) { idxOf[(c[0] << 16) | (c[1] << 8) | c[2]] = i + 1; });
    function nearest(r, g, b) {
      let bi = 1, bd = 1e12;
      for (let i = 0; i < reps.length; i++) {
        const dr = reps[i][0] - r, dg = reps[i][1] - g, db = reps[i][2] - b;
        const d = dr * dr + dg * dg + db * db;
        if (d < bd) { bd = d; bi = i + 1; }
      }
      return bi;
    }
    const data = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      if (rgba[i * 4 + 3] < 128) continue;
      const k = (rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2];
      data[i] = idxOf[k] || nearest(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]);
    }
    const palette = [0];
    reps.forEach(function (c) { palette.push(w565(c[0], c[1], c[2])); });
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
        const g2 = L.grid, nrows = g2.length, cols = nrows ? g2[0].length : 0;
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
    exportProject: exportProject, serialize: serialize, deserialize: deserialize, clone: clone,
    importTiled: importTiled, TILED_ORIENT: TILED_ORIENT,
    bakePal8: bakePal8, inlinePal8Asset: inlinePal8Asset, w565: w565,
    bakeScene: bakeScene, sceneModule: sceneModule, pyRepr: pyRepr, PyTuple: PyTuple, PyBytes: PyBytes, PyFloat: PyFloat };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PGEditor = api;
})(typeof window !== "undefined" ? window : globalThis);
