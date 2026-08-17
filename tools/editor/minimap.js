// picogame editor -- minimap: the whole world scaled into a small canvas with a
// viewport rectangle showing where the main view is looking. Click/drag on it to jump
// the main viewport there. Gives the "big map" a birds-eye so the author never gets lost.
//
//   PGMinimap.draw(mmCtx, mmW, mmH, vp, project, level)   -- render
//   PGMinimap.jump(mx, my, mmW, mmH, vp, project, level)  -- click/drag -> recenters vp

(function (root) {
  "use strict";
  const E = (typeof require !== "undefined") ? require("./core.js") : root.PGEditor;

  function rgbCss(c) { return "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")"; }

  function scaleFor(mmW, mmH, worldW, worldH) {
    return Math.min(mmW / Math.max(1, worldW), mmH / Math.max(1, worldH));
  }

  function draw(mmCtx, mmW, mmH, vp, project, level) {
    const b = E.levelBounds(project, level), worldW = b[0], worldH = b[1];
    const s = scaleFor(mmW, mmH, worldW, worldH);
    mmCtx.clearRect(0, 0, mmW, mmH);
    // world background
    mmCtx.fillStyle = rgbCss(level.background); mmCtx.fillRect(0, 0, worldW * s, worldH * s);
    // tilemaps as coarse blocks (bg tint) -- enough to read the shape of the level
    (level.tilemaps || []).forEach(function (tm) {
      const a = project.assets[tm.asset]; if (!a) return;
      const tw = (a.fw || 16) * s, th = (a.fh || 16) * s;
      mmCtx.fillStyle = a.type === "tileset_color" ? "#c9d3ec" : "#6f7fb0";
      for (let y = 0; y < tm.rows; y++) for (let x = 0; x < tm.cols; x++) {
        if (!tm.grid[y][x]) continue;
        const mv = tm.grid[y][x] & 0xFF;
        if (a.type === "tileset_color" && a.colors[String(mv)]) mmCtx.fillStyle = rgbCss(a.colors[String(mv)]);
        mmCtx.fillRect((tm.pos[0]) * s + x * tw, (tm.pos[1]) * s + y * th, Math.max(1, tw), Math.max(1, th));
      }
    });
    // entities as dots
    mmCtx.fillStyle = "#ffd23f";
    (level.entities || []).forEach(function (en) { mmCtx.fillRect(en.x * s - 1, en.y * s - 1, 2, 2); });
    // world outline
    mmCtx.strokeStyle = "#3a4666"; mmCtx.lineWidth = 1; mmCtx.strokeRect(0.5, 0.5, worldW * s, worldH * s);
    // viewport rectangle
    const vr = vp.visibleRect();
    mmCtx.strokeStyle = "#8fb0ff"; mmCtx.lineWidth = 1.5;
    mmCtx.strokeRect(vr.x * s, vr.y * s, vr.w * s, vr.h * s);
    mmCtx.fillStyle = "#8fb0ff22"; mmCtx.fillRect(vr.x * s, vr.y * s, vr.w * s, vr.h * s);
    return s;
  }

  // minimap pixel (mx,my) -> center the main viewport on that world point
  function jump(mx, my, mmW, mmH, vp, project, level) {
    const b = E.levelBounds(project, level), worldW = b[0], worldH = b[1];
    const s = scaleFor(mmW, mmH, worldW, worldH);
    vp.centerOn(mx / s, my / s);
  }

  const api = { draw: draw, jump: jump };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PGMinimap = api;
})(typeof window !== "undefined" ? window : globalThis);
