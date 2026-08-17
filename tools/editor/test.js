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

console.log("\neditor/test.js: ALL OK");
