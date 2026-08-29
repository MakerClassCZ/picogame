// Headless test for the editor's pure model + exporters (core.js). No DOM.
//   node editor/test.js
"use strict";
const assert = require("assert");
const fs = require("fs");
const E = require("./core.js");

function section(name) { process.stdout.write("  " + name + " ... "); }
function ok() { process.stdout.write("ok\n"); }

// ---- model: build a project, flag tiles, place everything, export ----
section("export shape (scene) round-trips every field");
const p = E.newProject();
const L = p.levels[0];
p.assets.ground = { type: "tileset_color", fw: 16, fh: 16, colors: { "1": [150, 90, 40], "2": [245, 215, 50] } };
E.setTileProp(p.assets.ground, 1, "solid", true);
E.setTileProp(p.assets.ground, 2, "coin", true);
L.tilemaps.push(E.newTilemap("ground", 20, 15, false));
L.tilemaps[0].grid[14][0] = 1; L.tilemaps[0].grid[10][5] = 2;
L.entities.push({ asset: "ground", name: "player", tag: null, x: 40, y: 208, anchor: [0.5, 1.0], frame: 0, data: { lives: 3 } });
L.entities.push({ asset: "ground", name: null, tag: "foes", x: 100, y: 208, anchor: [0.5, 1.0], frame: 0, anim: "walk" });
L.hud.push({ name: "score", x: 4, y: 4, fg: [255, 255, 255], bg: [0, 0, 0] });
L.points.push({ name: "spawn", x: 40, y: 208 });
L.zones.push({ tag: "trigger", x: 10, y: 10, w: 40, h: 40 });
L.particles.push(E.newParticles("fx"));
L.camera = { mode: "follow", target: "player", axis: "x", bounds: [0, 0, 640, 240] };

const scene = E.exportScene(p, 0);
const kinds = scene.layers.map(function (x) { return x.kind; });
assert.deepStrictEqual(kinds, ["tilemap", "sprite", "group", "particles", "hudlabel"], "layer order bg->mid->fg->hud");
assert.strictEqual(scene.assets.ground.props["1"].solid, true, "solid prop exported");
assert.strictEqual(scene.layers[0].grid[14][0], 1, "tilemap grid exported as 2-D int array");
const groupLayer = scene.layers.find(function (l) { return l.kind === "group"; });
assert.strictEqual(groupLayer.tag, "foes", "tag -> group fold");
assert.deepStrictEqual(groupLayer.instances[0], [100, 208], "group instance world coords");
assert.strictEqual(groupLayer.anim, "walk", "group anim survives");
const spriteLayer = scene.layers.find(function (l) { return l.kind === "sprite"; });
assert.deepStrictEqual(spriteLayer.data, { lives: 3 }, "sprite data survives");
assert.deepStrictEqual(spriteLayer.anchor, [0.5, 1.0], "sprite anchor survives");
const parts = scene.layers.find(function (l) { return l.kind === "particles"; });
assert.strictEqual(parts.capacity, 64, "particles capacity exported");
assert.strictEqual(scene.points[0].name, "spawn");
assert.strictEqual(scene.zones[0].tag, "trigger");
assert.strictEqual(scene.camera.target, "player");
assert.deepStrictEqual(scene.camera.bounds, [0, 0, 640, 240], "camera bounds > one screen");
ok();

section("export shape (project) with bank + levels");
const proj = E.exportProject(p);
assert.strictEqual(proj.format, "picogame-project");
assert.strictEqual(proj.levels.length, 1);
assert.ok(proj.assets.ground, "shared asset bank");
assert.strictEqual(proj.levels[0].camera.axis, "x");
ok();

section("resizeTilemap grows (pad) and shrinks (crop, reports loss)");
const tm = E.newTilemap("ground", 4, 3, false);
tm.grid[2][3] = 7;                                    // a painted tile at the far corner
let lost = E.resizeTilemap(tm, 8, 5);                  // grow
assert.strictEqual(tm.cols, 8); assert.strictEqual(tm.rows, 5);
assert.strictEqual(tm.grid.length, 5); assert.strictEqual(tm.grid[0].length, 8);
assert.strictEqual(tm.grid[2][3], 7, "existing tile preserved on grow");
assert.strictEqual(tm.grid[4][7], 0, "new cells padded with 0");
assert.strictEqual(lost, false, "growing loses nothing");
lost = E.resizeTilemap(tm, 3, 5);                      // shrink past the painted tile at x=3
assert.strictEqual(tm.cols, 3);
assert.strictEqual(lost, true, "shrink that drops a painted tile reports loss");
ok();

section("levelBounds returns worldSize; contentBounds spans the biggest tilemap");
const big = E.newProject();
big.assets.t = { type: "tileset_color", fw: 16, fh: 16, colors: { "1": [1, 2, 3] } };
big.levels[0].tilemaps.push(E.newTilemap("t", 40, 15, false));   // 640 x 240 tiles (2x wide)
// levelBounds = the explicit worldSize (source of truth), default one screen for a new level
assert.deepStrictEqual(E.levelBounds(big, big.levels[0]), [320, 240], "levelBounds = worldSize (headline)");
// contentBounds still measures the painted extent (used to DERIVE worldSize on migration)
assert.deepStrictEqual(E.contentBounds(big, big.levels[0]), [640, 240], "contentBounds spans the wide tilemap");
// set worldSize explicitly -> levelBounds follows it
big.levels[0].worldSize = [960, 480];
assert.deepStrictEqual(E.levelBounds(big, big.levels[0]), [960, 480], "levelBounds follows an explicit worldSize");
ok();

section("worldSize: round-trips serialize/deserialize; derived for old projects");
const wp = E.newProject(); wp.levels[0].worldSize = [1280, 240];
const rt = E.deserialize(JSON.parse(JSON.stringify(E.serialize(wp))));
assert.deepStrictEqual(rt.levels[0].worldSize, [1280, 240], "explicit worldSize survives save/load");
// an OLD project (no worldSize) derives it from content on load
const oldp = { size: [320, 240], assets: { t: { type: "tileset_color", fw: 16, fh: 16, colors: { "1": [1, 2, 3] } } },
  levels: [{ name: "old", background: [0, 0, 0], tilemaps: [E.newTilemap("t", 40, 15, false)], entities: [] }] };
delete oldp.levels[0].worldSize;
const migrated = E.deserialize(oldp);
assert.deepStrictEqual(migrated.levels[0].worldSize, [640, 240], "missing worldSize derived from content");
// empty old level falls back to the device screen
const emptyOld = E.deserialize({ size: [320, 240], assets: {}, levels: [{ name: "e", background: [0, 0, 0], tilemaps: [] }] });
assert.deepStrictEqual(emptyOld.levels[0].worldSize, [320, 240], "empty level -> one screen");
ok();

section("fillLayersToWorld grows/crops layers to the world (skips offset layers)");
const fp = E.newProject();
fp.assets.g = { type: "tileset_color", fw: 16, fh: 16, colors: { "1": [1, 2, 3] } };
fp.levels[0].tilemaps.push(E.newTilemap("g", 20, 15, false));   // origin layer
const off = E.newTilemap("g", 10, 10, false); off.pos = [200, 0];   // offset (parallax) layer
fp.levels[0].tilemaps.push(off);
fp.levels[0].worldSize = [960, 240];                            // 60 x 15 tiles
E.fillLayersToWorld(fp, fp.levels[0]);
assert.strictEqual(fp.levels[0].tilemaps[0].cols, 60, "origin layer grown to fill world width");
assert.strictEqual(fp.levels[0].tilemaps[0].rows, 15, "origin layer fills world height");
assert.strictEqual(fp.levels[0].tilemaps[1].cols, 10, "offset (parallax) layer left untouched");
ok();

section("removeAsset drops the asset + every layer/entity using it");
E.removeAsset(p, "ground");
assert.ok(!p.assets.ground, "asset removed");
assert.strictEqual(p.levels[0].tilemaps.length, 0, "tilemap layers using it removed");
assert.strictEqual(p.levels[0].entities.length, 0, "entities using it removed");
ok();

section("migration: flat project (no levels[]) -> single level");
const flat = { size: [320, 240], assets: {}, background: [1, 2, 3],
  tilemap: { asset: "x", cols: 2, rows: 2, grid: [[0, 0], [0, 0]], pos: [0, 0], fg: false },
  entities: [{ asset: "x", x: 1, y: 2, anchor: [0, 0] }], hud: [], camera: null };
const mf = E.deserialize(flat);
assert.strictEqual(mf.levels.length, 1, "flat -> one level");
assert.strictEqual(mf.levels[0].tilemaps.length, 1, "flat tilemap -> tilemaps[]");
assert.strictEqual(mf.levels[0].entities.length, 1, "flat entities kept");
assert.ok(!mf.tilemap && !mf.entities, "old flat keys deleted");
ok();

section("migration: level with single `tilemap` -> tilemaps[]");
const single = { size: [320, 240], assets: {}, levels: [
  { name: "a", background: [0, 0, 0], tilemap: { asset: "x", cols: 1, rows: 1, grid: [[0]], pos: [0, 0], fg: false }, entities: [] } ] };
const ms = E.deserialize(single);
assert.strictEqual(ms.levels[0].tilemaps.length, 1, "single tilemap migrated");
assert.ok(!ms.levels[0].tilemap, "old single key deleted");
assert.ok(Array.isArray(ms.levels[0].zones) && Array.isArray(ms.levels[0].particles), "newer arrays back-filled");
ok();

// ---- shipped sample loads + round-trips ----
section("shipped sample.pgproj.json loads + exports");
const save = JSON.parse(fs.readFileSync(__dirname + "/sample.pgproj.json", "utf8"));
const sp = E.deserialize(save);
assert.strictEqual(sp.levels.length, 1, "sample has a level");
const ss = E.exportScene(sp, 0);
assert.ok(ss.assets.player && ss.assets.goomba && ss.assets.ground, "sample assets present");
assert.strictEqual(ss.assets.ground.props["2"].coin, true, "sample coin flag");
assert.ok(ss.layers.some(function (l) { return l.kind === "group" && l.tag === "foes"; }), "sample foes group");
assert.ok(ss.points.some(function (q) { return q.name === "spawn"; }), "sample spawn point");
assert.strictEqual(ss.camera.target, "player", "sample camera");
assert.ok(sp.levels[0].worldSize && sp.levels[0].worldSize.length === 2, "sample gets a worldSize on load (derived if absent)");
ok();

// ---- the two scrolling demos load + export + are genuinely bigger than one screen ----
section("demo_platformer.pgproj.json: bounded, wider than one screen, axis x");
const dp = E.deserialize(JSON.parse(fs.readFileSync(__dirname + "/demo_platformer.pgproj.json", "utf8")));
assert.deepStrictEqual(dp.levels[0].worldSize, [960, 240], "platformer worldSize = 960x240");
const dpb = E.levelBounds(dp, dp.levels[0]);
assert.ok(dpb[0] > dp.size[0], "platformer world is WIDER than one screen (" + dpb[0] + " > " + dp.size[0] + ")");
const dps = E.exportScene(dp, 0);
assert.ok(dps.camera && dps.camera.axis === "x", "platformer camera axis x (bounded scroll)");
assert.deepStrictEqual(dps.camera.bounds, [0, 0, dpb[0], dpb[1]], "platformer bounds = finite world (clamps)");
assert.ok(dps.layers.some(function (l) { return l.kind === "tilemap"; }), "platformer has a tilemap");
assert.ok(dps.layers.some(function (l) { return l.kind === "sprite" && l.name === "player"; }), "platformer has a named player");
assert.ok(dps.layers.some(function (l) { return l.kind === "group"; }), "platformer has an enemy group");
ok();

section("demo_openworld.pgproj.json: bigger BOTH ways, axis xy");
const dw = E.deserialize(JSON.parse(fs.readFileSync(__dirname + "/demo_openworld.pgproj.json", "utf8")));
assert.deepStrictEqual(dw.levels[0].worldSize, [640, 480], "open-world worldSize = 640x480");
const dwb = E.levelBounds(dw, dw.levels[0]);
assert.ok(dwb[0] > dw.size[0] && dwb[1] > dw.size[1], "open world bigger than one screen in BOTH dims (" + dwb[0] + "x" + dwb[1] + ")");
const dws = E.exportScene(dw, 0);
assert.ok(dws.camera && dws.camera.axis === "xy", "open-world camera axis xy (free roam)");
assert.deepStrictEqual(dws.camera.bounds, [0, 0, dwb[0], dwb[1]], "open-world bounds = big world");
assert.ok(dws.zones && dws.zones.length >= 1, "open world has zones (POIs)");
assert.ok(dws.layers.some(function (l) { return l.kind === "sprite" && l.name === "player"; }), "open world has a named player");
ok();

// ---- Tiled import: orientations, compaction, objects, format extensions ----
section("Tiled orientation map matches a from-scratch derivation");
(function () {
  function pgT(S, fx, fy, tp) {
    const sh = S.length, sw = S[0].length;
    if (tp) {
      const R = [];
      for (let ly = 0; ly < sw; ly++) { R.push([]); for (let lx = 0; lx < sh; lx++)
        R[ly].push(S[fy ? sh - 1 - lx : lx][fx ? sw - 1 - ly : ly]); }
      return R;
    }
    const R = [];
    for (let r = 0; r < sh; r++) { R.push([]); for (let c = 0; c < sw; c++)
      R[r].push(S[fy ? sh - 1 - r : r][fx ? sw - 1 - c : c]); }
    return R;
  }
  function tiledT(S, H, V, D) {
    if (D) S = S[0].map(function (_, i) { return S.map(function (row) { return row[i]; }); });
    if (H) S = S.map(function (row) { return row.slice().reverse(); });
    if (V) S = S.slice().reverse();
    return S;
  }
  const S = [[1, 2, 3], [4, 5, 6]];
  for (let bits = 0; bits < 8; bits++) {
    const want = JSON.stringify(tiledT(S, !!(bits & 1), !!(bits & 2), !!(bits & 4)));
    const hits = [];
    for (let fx = 0; fx < 2; fx++) for (let fy = 0; fy < 2; fy++) for (let tp = 0; tp < 2; tp++)
      if (JSON.stringify(pgT(S, fx, fy, tp)) === want) hits.push(fx | fy << 1 | tp << 2);
    assert.deepStrictEqual(hits, [E.TILED_ORIENT[bits]], "bits " + bits);
  }
})();
ok();

section("importTiled: grids, compaction remap, objects, angle/data");
(function () {
  const H = 0x80000000, V = 0x40000000, D = 0x20000000;
  const gid = function (local, f) { return ((local + 1) | (f || 0)) >>> 0; };
  const map = {
    type: "map", orientation: "orthogonal", infinite: false,
    width: 3, height: 2, tilewidth: 8, tileheight: 8, backgroundcolor: "#4080c0",
    tilesets: [{ firstgid: 1, name: "terrain", image: "tiles.png",
      tilewidth: 8, tileheight: 8, tilecount: 8, columns: 4,
      tiles: [{ id: 0, properties: [{ name: "solid", type: "bool", value: true }] },
              { id: 5, properties: [{ name: "hazard", type: "bool", value: true }] }] }],
    layers: [
      { type: "tilelayer", name: "ground", width: 3, height: 2, visible: true,
        data: [gid(0), gid(0, H), gid(0, H + D), gid(5), 0, gid(5, V + D)] },
      { type: "objectgroup", name: "stuff", objects: [
        { id: 1, gid: gid(5), name: "player", x: 8, y: 16, width: 8, height: 8, rotation: 90,
          properties: [{ name: "lives", type: "int", value: 3 }] },
        { id: 2, name: "exit", class: "goal", x: 16, y: 0, width: 8, height: 16,
          properties: [{ name: "next", type: "string", value: "level2" }] },
        { id: 3, name: "spawn", point: true, x: 4, y: 12 },
      ] },
    ],
  };
  const res = E.importTiled(map, {});
  const lv = res.project.levels[0];
  const g = lv.tilemaps[0].grid;
  // compaction: used locals {0, 5} -> values 1, 2 (a 6-tile gap collapsed)
  assert.strictEqual(g[0][0], 1);
  assert.strictEqual(g[0][1], 1 | (1 << 8));                 // H
  assert.strictEqual(g[0][2], 1 | (6 << 8));                 // H+D -> flipY+transpose (the swap)
  assert.strictEqual(g[1][0], 2);
  assert.strictEqual(g[1][1], 0);
  assert.strictEqual(g[1][2], 2 | (5 << 8));                 // V+D -> flipX+transpose
  assert.deepStrictEqual(res.repack[0].used, [0, 5]);
  assert.strictEqual(res.project.assets.terrain.frames, 3);  // empty + 2 used
  assert.deepStrictEqual(res.project.assets.terrain.props, { "1": { solid: true }, "2": { hazard: true } });
  const en = lv.entities[0];
  assert.strictEqual(en.name, "player");
  assert.strictEqual(en.frame, 2);                           // remapped local 5
  assert.strictEqual(en.angle, 90);
  assert.deepStrictEqual(en.data, { lives: 3 });
  assert.deepStrictEqual(en.anchor, [0, 1]);
  assert.strictEqual(lv.zones[0].tag, "goal");
  assert.deepStrictEqual(lv.zones[0].data, { next: "level2" });
  assert.strictEqual(lv.points[0].name, "spawn");
  assert.deepStrictEqual(res.project.size, [320, 240]);       // device screen untouched
  assert.deepStrictEqual(lv.worldSize, [24, 16]);              // map extent -> world size
  assert.deepStrictEqual(lv.background, [64, 128, 192]);
  // export carries the extensions: grid orient bits verbatim + sprite angle + zone data
  res.project.assets.terrain.src = "terrain.png";
  const sc = E.exportScene(res.project, 0);
  const tmL = sc.layers.filter(function (l) { return l.kind === "tilemap"; })[0];
  assert.strictEqual(tmL.grid[0][2], 1 | (6 << 8));
  const spL = sc.layers.filter(function (l) { return l.kind === "sprite"; })[0];
  assert.strictEqual(spL.angle, 90);
  assert.deepStrictEqual(sc.zones[0].data, { next: "level2" });
})();
ok();

// ---- in-browser bake: pyRepr + sceneModule against the CLI's golden output ----
section("pyRepr matches CPython repr for the SCENE value types");
assert.strictEqual(E.pyRepr(new E.PyTuple([1])), "(1,)");
assert.strictEqual(E.pyRepr(new E.PyTuple(["a", null, true, 2.5, 3])), "('a', None, True, 2.5, 3)");
assert.strictEqual(E.pyRepr(new E.PyBytes(new Uint8Array([0, 1, 39, 92, 65, 255]))), "b'\\x00\\x01\\'\\\\A\\xff'");
assert.strictEqual(E.pyRepr({ k: [1, 2] }), "{'k': [1, 2]}");
assert.strictEqual(E.pyRepr(new E.PyFloat(0)), "0.0");
assert.strictEqual(E.pyRepr(0.5), "0.5");
assert.strictEqual(E.pyRepr("it's"), '"it\'s"');
ok();

section("sceneModule == tools/scene_build.py output (golden fixtures under web/fixtures)");
["demo_platformer_scene", "demo_openworld_scene", "ext_orient_scene"].forEach(function (f) {
  const gold = __dirname + "/../web/fixtures/" + f + "_scene.py";
  if (!fs.existsSync(gold)) return;                          // golden .py generated by tbake/CLI runs
  const scene = JSON.parse(fs.readFileSync(__dirname + "/../web/fixtures/" + f + ".json", "utf8"));
  assert.strictEqual(E.sceneModule(scene), fs.readFileSync(gold, "utf8"), f + " must be byte-identical to the CLI bake");
});
ok();

// ---- ASCII map form: legend+rows must be a lossless, byte-identical alternative to the grid ----
section("ASCII export (legend+rows) bakes identically to the int grid");
(function () {
  const p = E.newProject();
  p.assets.tiles = { type: "tileset_color", fw: 16, fh: 16, colors: { 1: [120, 90, 60], 2: [255, 220, 60], 3: [40, 40, 40] } };
  const tm = E.newTilemap("tiles", 6, 3);
  tm.grid = [[0, 0, 2, 2, 0, 0],
             [0, 1, 1, 1, 1, 0],
             [1, 1, 3, 3, 1, 1 | (1 << 8)]];     // last cell also carries a flipX orientation
  p.levels[0].tilemaps = [tm];

  const grid = E.exportScene(p, null, false), ascii = E.exportScene(p, null, true);
  assert.ok(grid.layers[0].grid, "default export keeps the int grid");
  assert.ok(!ascii.layers[0].grid && ascii.layers[0].rows, "ascii export emits rows, not a grid");

  // the picture reads like the level: '.' is empty, chars are assigned by ascending tile value
  // an oriented cell is a value of its own, so it reads as its own character ('+' = brick, flipX)
  assert.deepStrictEqual(ascii.layers[0].rows, ["..oo..", ".####.", "##==#+"]);
  assert.deepStrictEqual(ascii.layers[0].legend, { ".": 0, "#": 1, o: 2, "=": 3, "+": 257 });

  // both forms read back to the same grid, and BAKE to the same bytes (incl. the orient plane)
  assert.deepStrictEqual(E.layerGrid(ascii.layers[0]), tm.grid);
  assert.strictEqual(E.sceneModule(ascii), E.sceneModule(grid),
    "an ASCII scene must bake byte-identically to the same scene as a grid");
})();
ok();

section("ASCII export falls back to the grid when a map outgrows the legend alphabet");
(function () {
  const p = E.newProject();
  p.assets.tiles = { type: "tileset", fw: 8, fh: 8, frames: 400, src: "t.png" };
  const tm = E.newTilemap("tiles", 120, 2);
  let v = 1;
  tm.grid = tm.grid.map(function (r) { return r.map(function () { return v++; }); });   // 240 distinct
  p.levels[0].tilemaps = [tm];
  const out = E.exportScene(p, null, true);
  assert.ok(out.layers[0].grid && !out.layers[0].rows, "too many distinct tiles -> stays a grid");
})();
ok();

// ---- importing an EXPORTED scene/project back into the editor (the round trip) ----
function richProject() {
  const p = E.newProject();
  p.assets.tiles = { type: "tileset", fw: 16, fh: 16, frames: 5, src: "tiles.png", props: { 1: { solid: true } } };
  p.assets.hero = { type: "sprite", fw: 12, fh: 16, frames: 6, src: "hero.png", transparent: 0,
                    animations: { walk: { frames: [0, 1], fps: 8, loop: true } } };
  p.sounds = { jump: { src: "jump.wav" } };
  const bg = E.newTilemap("tiles", 60, 15);            // 960 px wide -> a scrolling world
  bg.grid[14] = new Array(60).fill(1);
  bg.grid[10][4] = 2 | (1 << 8);                       // an oriented cell
  const front = E.newTilemap("tiles", 60, 15, true);
  front.grid[0][0] = 3;
  const lv = p.levels[0];
  lv.tilemaps = [bg, front];
  lv.entities = [{ asset: "hero", name: "player", x: 40, y: 208, anchor: [0.5, 1], frame: 0, anim: "walk", data: { lives: 3 } },
                 { asset: "hero", tag: "enemies", x: 224, y: 208, anchor: [0.5, 1], frame: 0 },
                 { asset: "hero", tag: "enemies", x: 480, y: 208, anchor: [0.5, 1], frame: 0 }];
  lv.hud = [{ name: "score", x: 4, y: 4, fg: [255, 255, 255], bg: [0, 0, 0] }];
  lv.particles = [{ name: "fx", capacity: 64, size: 2, gravity: 0.5, fade: true }];
  lv.zones = [{ tag: "door", x: 900, y: 180, w: 20, h: 40 }];
  lv.points = [{ name: "spawn", x: 40, y: 208 }];
  lv.camera = { mode: "follow", target: "player", axis: "x", bounds: [0, 0, 960, 240] };
  lv.music = "theme";
  lv.worldSize = [960, 240];
  return p;
}

section("import(export(project)) == export(project), in both map forms");
[false, true].forEach(function (ascii) {
  const scene = E.exportScene(richProject(), null, ascii);
  const back = E.importExported(JSON.parse(JSON.stringify(scene)), "level1");
  assert.deepStrictEqual(E.exportScene(back, null, ascii), scene,
    (ascii ? "ascii" : "grid") + " form must survive export -> import -> export unchanged");
});
ok();

section("import derives the world extent (a scrolling level keeps its camera bounds)");
(function () {
  const back = E.importExported(E.exportScene(richProject(), null, true), "level1");
  // the export carries only the device screen, so worldSize must come from the content (960x240),
  // else a scrolling level would come back one screen wide - and drag its camera bounds with it
  assert.deepStrictEqual(back.levels[0].worldSize, [960, 240]);
  assert.deepStrictEqual(back.levels[0].camera.bounds, [0, 0, 960, 240]);
  assert.strictEqual(back.levels[0].entities.filter(function (e) { return e.tag === "enemies"; }).length, 2,
    "an exported group unfolds back into tagged entities");
})();
ok();

section("import handles the project form (bank + several levels)");
(function () {
  const p = richProject();
  p.levels.push(E.newLevel("level2", [320, 240]));
  const proj = E.exportProject(p, true);
  const back = E.importExported(JSON.parse(JSON.stringify(proj)));
  assert.strictEqual(back.levels.length, 2);
  assert.deepStrictEqual(back.levels.map(function (l) { return l.name; }), ["level1", "level2"]);
  assert.deepStrictEqual(E.exportProject(back, true), proj);
})();
ok();

section("git conflict markers are detected, ASCII map rows are not mistaken for them");
(function () {
  const conflicted = ["{", " \"rows\": [", "<<<<<<< HEAD", "  \"###...\",", "=======",
                      "  \"...###\",", ">>>>>>> agent", " ]", "}"].join("\n");
  assert.deepStrictEqual(E.findConflictMarkers(conflicted), [3, 5, 7]);
  assert.deepStrictEqual(E.findConflictMarkers("{\n \"a\": 1\n}"), []);
  // a level row may legitimately be a run of '=' or '<' tiles - only a marker at line start counts
  assert.deepStrictEqual(E.findConflictMarkers('  "=======",\n  "<<<<<<<",'), []);
  assert.deepStrictEqual(E.findConflictMarkers("||||||| base\n"), [1]);   // diff3 style
})();
ok();

console.log("\neditor/test.js: ALL OK");
