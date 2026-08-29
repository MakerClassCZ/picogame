// picogame editor -- world-space canvas renderer. Draws the level through the Viewport
// (ctx.setTransform in WORLD coords), plus authoring overlays: the dashed one-screen
// device guide box, the world extent, a tile grid, the camera-bounds frame, and dimming
// of the off-world area so "what's in the level vs. outside" is visually unambiguous.
//
// PGRender.draw(ctx, vp, project, level, images, sel, opts) is called every frame.

(function (root) {
  "use strict";
  const E = (typeof require !== "undefined") ? require("./core.js") : root.PGEditor;

  // The four the helper libs already act on. A game can read ANY name via view.tile_has(tx, ty, name),
  // so these are a starting set, not a closed list -- see flagsOf().
  const FLAGS = ["solid", "coin", "goal", "hazard"];
  const FLAG_COLOR = { solid: "#ff4d4d", coin: "#ffd23f", goal: "#45e08a", hazard: "#ff5fff" };

  // Custom flags need no schema: asset.props IS the storage, so the set of names a tileset uses is
  // simply the names that appear in it. That means a flag hand-written into a .json (or added by the
  // game's own tooling) shows up in the editor UI the moment the project loads.
  function flagsOf(asset) {
    const out = FLAGS.slice(), p = asset && asset.props;
    if (p) {
      for (const k in p) {
        for (const n in p[k]) { if (out.indexOf(n) < 0) out.push(n); }
      }
    }
    return out;
  }

  // Stable colour for a custom flag, hashed from the name so its badge looks the same every session.
  function flagColor(name) {
    if (FLAG_COLOR[name]) return FLAG_COLOR[name];
    let h = 0;
    for (let i = 0; i < name.length; i++) { h = (h * 31 + name.charCodeAt(i)) & 0xffff; }
    return "hsl(" + (h % 360) + ", 85%, 62%)";
  }
  const SEL_COLOR = "#ffd23f";

  function rgbCss(c) { return "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")"; }

  // Oriented-tile cache: grid values may carry orientation in bits 8-10 (bit8 flipX,
  // bit9 flipY, bit10 transpose - the engine encoding). Each (image, frame, orient)
  // is materialized ONCE into a small canvas via the exact engine pixel mapping
  // (R[row=ly][col=lx] = S[row = fy? th-1-lx : lx][col = fx? tw-1-ly : ly] for
  // transpose; plain axis flips otherwise), then drawn like any tile.
  const _orientCache = (typeof WeakMap !== "undefined") ? new WeakMap() : null;
  function orientedTile(img, v, o, tw, th) {
    if (!_orientCache || typeof document === "undefined") return null;
    let per = _orientCache.get(img);
    if (!per) { per = {}; _orientCache.set(img, per); }
    const key = v + "|" + o;
    if (per[key]) return per[key];
    const fx = !!(o & 1), fy = !!(o & 2), tp = !!(o & 4);
    if (tp && tw !== th) return null;             // transpose only defined for square tiles
    const src = document.createElement("canvas");
    src.width = tw; src.height = th;
    const sctx = src.getContext("2d");
    sctx.drawImage(img, v * tw, 0, tw, th, 0, 0, tw, th);
    const sd = sctx.getImageData(0, 0, tw, th).data;
    const out = document.createElement("canvas");
    out.width = tw; out.height = th;
    const octx = out.getContext("2d");
    const od = octx.createImageData(tw, th);
    for (let r = 0; r < th; r++) for (let c = 0; c < tw; c++) {
      let sx, sy;
      if (tp) { sx = fx ? tw - 1 - r : r; sy = fy ? th - 1 - c : c; }
      else { sx = fx ? tw - 1 - c : c; sy = fy ? th - 1 - r : r; }
      const si = (sy * tw + sx) * 4, di = (r * tw + c) * 4;
      od.data[di] = sd[si]; od.data[di + 1] = sd[si + 1];
      od.data[di + 2] = sd[si + 2]; od.data[di + 3] = sd[si + 3];
    }
    octx.putImageData(od, 0, 0);
    per[key] = out;
    return out;
  }
  function isImg(a) { return !!a && (a.type === "sprite" || a.type === "tileset" || a.type === "bitmap"); }
  function tileProp(a, v) { return (a.props && a.props[String(v)]) || null; }

  function drawTilemap(ctx, tm, project, images, showFlags, dim) {
    const a = project.assets[tm.asset]; if (!a) return;
    const tw = a.fw || 16, th = a.fh || 16;
    ctx.globalAlpha = dim ? 0.5 : 1;
    for (let y = 0; y < tm.rows; y++) for (let x = 0; x < tm.cols; x++) {
      const v0 = tm.grid[y][x]; if (!v0) continue;
      const v = v0 & 0xFF, o = v0 >> 8;
      const dx = tm.pos[0] + x * tw, dy = tm.pos[1] + y * th;
      if (isImg(a) && images[tm.asset] && images[tm.asset].complete) {
        const oc = o ? orientedTile(images[tm.asset], v, o, tw, th) : null;
        if (oc) ctx.drawImage(oc, dx, dy);
        else ctx.drawImage(images[tm.asset], v * tw, 0, tw, th, dx, dy, tw, th);
      } else if (a.type === "tileset_color") {
        ctx.fillStyle = rgbCss(a.colors[String(v)] || [255, 0, 255]); ctx.fillRect(dx, dy, tw, th);
      } else { ctx.fillStyle = "#0af"; ctx.fillRect(dx, dy, tw, th); }
      if (showFlags) {
        const pr = tileProp(a, v);
        if (pr) { let i = 0; for (const p in pr) { if (pr[p]) { ctx.fillStyle = flagColor(p); ctx.fillRect(dx + 1 + i * 4, dy + 1, 3, 3); i++; } } }
      }
    }
    ctx.globalAlpha = 1;
  }

  function drawEntitySprite(ctx, en, project, images, selected) {
    const a = project.assets[en.asset]; if (!a) return;
    const fw = a.fw || 16, fh = a.fh || 16;
    const dx = en.x - (en.anchor || [0, 0])[0] * fw, dy = en.y - (en.anchor || [0, 0])[1] * fh;
    if (isImg(a) && images[en.asset] && images[en.asset].complete)
      ctx.drawImage(images[en.asset], (en.frame || 0) * fw, 0, fw, fh, dx, dy, fw, fh);
    else if (a.type === "rect") { ctx.fillStyle = rgbCss(a.color); ctx.fillRect(dx, dy, fw, fh); }
    else { ctx.fillStyle = "#0af"; ctx.fillRect(dx, dy, fw, fh); }
    if (selected) { ctx.strokeStyle = SEL_COLOR; ctx.lineWidth = px(2); ctx.strokeRect(dx, dy, fw, fh); }
    // anchor dot -- shows the sprite's world position (the point it's placed at)
    ctx.fillStyle = selected ? SEL_COLOR : "#ffffff88";
    ctx.fillRect(en.x - px(1), en.y - px(1), px(2), px(2));
  }

  // line width / marker sizes are given in screen px but we draw in world space, so
  // divide by zoom -- overlays stay a constant on-screen thickness at any zoom.
  let _zoom = 1;
  function px(n) { return n / _zoom; }

  // members of a shift-click multi-selection draw with the same highlight as the primary pick
  function isSel(sel, o, prim) { return o === prim || (sel.multi && sel.multi.some(function (m) { return m.obj === o; })); }

  function draw(ctx, vp, project, level, images, sel, opts) {
    opts = opts || {};
    _zoom = vp.zoom;
    const dpr = vp.dpr;
    // 1) clear whole canvas (screen space) to the "outside the world" colour
    vp.resetTransform(ctx);
    ctx.fillStyle = "#0b0d13";
    ctx.fillRect(0, 0, vp.w, vp.h);

    // 2) world space from here on
    vp.applyTransform(ctx);
    ctx.imageSmoothingEnabled = false;

    const bounds = E.levelBounds(project, level);
    const worldW = bounds[0], worldH = bounds[1];

    // level background fills the world extent (so off-world stays dark = obvious edge)
    ctx.fillStyle = rgbCss(level.background);
    ctx.fillRect(0, 0, worldW, worldH);

    // optional tile grid (aligned to the active/first tilemap's tile size)
    if (opts.showGrid) {
      const gt = opts.gridTile || 16;
      ctx.strokeStyle = "#ffffff12"; ctx.lineWidth = px(1);
      ctx.beginPath();
      for (let x = 0; x <= worldW; x += gt) { ctx.moveTo(x, 0); ctx.lineTo(x, worldH); }
      for (let y = 0; y <= worldH; y += gt) { ctx.moveTo(0, y); ctx.lineTo(worldW, y); }
      ctx.stroke();
    }

    // bg tilemaps -> entities/groups/particles -> fg tilemaps
    (level.tilemaps || []).forEach(function (tm) { if (!tm.fg) drawTilemap(ctx, tm, project, images, opts.showFlags); });
    (level.entities || []).forEach(function (en) { drawEntitySprite(ctx, en, project, images, isSel(sel, en, sel.entity)); });
    (level.particles || []).forEach(function (p) {
      // fx layers have no fixed footprint; mark their emitter origin at world 0,0-ish top-left
    });
    (level.tilemaps || []).forEach(function (tm) { if (tm.fg) drawTilemap(ctx, tm, project, images, opts.showFlags); });

    // HUD labels (camera-fixed at runtime; drawn at their world pos here so authors place them)
    (level.hud || []).forEach(function (hd) {
      ctx.fillStyle = rgbCss(hd.bg || [0, 0, 0]); ctx.fillRect(hd.x - 1, hd.y - 1, 58, 11);
      ctx.fillStyle = rgbCss(hd.fg || [255, 255, 255]);
      ctx.font = "8px monospace"; ctx.textBaseline = "top"; ctx.fillText(hd.name || "", hd.x, hd.y);
      if (isSel(sel, hd, sel.hud)) { ctx.strokeStyle = SEL_COLOR; ctx.lineWidth = px(2); ctx.strokeRect(hd.x - 1.5, hd.y - 1.5, 59, 12); }
    });

    // zones (magenta trigger rects)
    (level.zones || []).forEach(function (z) {
      ctx.strokeStyle = isSel(sel, z, sel.zone) ? SEL_COLOR : "#ff5fff"; ctx.lineWidth = px(2);
      ctx.strokeRect(z.x, z.y, z.w, z.h);
      ctx.fillStyle = isSel(sel, z, sel.zone) ? "#ffd23f22" : "#ff5fff18"; ctx.fillRect(z.x, z.y, z.w, z.h);
      ctx.fillStyle = isSel(sel, z, sel.zone) ? SEL_COLOR : "#ff9fff";
      ctx.font = px(9) + "px monospace"; ctx.textBaseline = "bottom"; ctx.fillText(z.tag || "zone", z.x + px(2), z.y - px(1));
    });

    // points (green dots + name)
    (level.points || []).forEach(function (q) {
      ctx.fillStyle = isSel(sel, q, sel.point) ? SEL_COLOR : "#5fffa0";
      ctx.fillRect(q.x - px(3), q.y - px(3), px(6), px(6));
      ctx.font = px(8) + "px monospace"; ctx.textBaseline = "bottom"; ctx.fillText(q.name || "", q.x + px(5), q.y);
    });

    // picked tile cell highlight
    if (sel.tile) {
      const tm = (level.tilemaps || [])[sel.tile.tm];
      if (tm) { const a = project.assets[tm.asset]; if (a) {
        ctx.strokeStyle = SEL_COLOR; ctx.lineWidth = px(2);
        ctx.strokeRect(tm.pos[0] + sel.tile.cx * a.fw, tm.pos[1] + sel.tile.cy * a.fh, a.fw, a.fh);
      } }
    }

    // in-progress rectangle preview (paint-rect / zone drag), given in WORLD coords
    if (opts.rubberRect) {
      const r = opts.rubberRect;
      ctx.strokeStyle = "#8fb0ff"; ctx.lineWidth = px(2); ctx.setLineDash([px(4), px(4)]);
      ctx.strokeRect(r.x, r.y, r.w, r.h);
      ctx.fillStyle = "#8fb0ff22"; ctx.fillRect(r.x, r.y, r.w, r.h);
      ctx.setLineDash([]);
    }

    // tile-region marquee (copy/paste selection) in world coords
    if (opts.tileSel) {
      const t = opts.tileSel;
      ctx.strokeStyle = "#45e08a"; ctx.lineWidth = px(2); ctx.setLineDash([px(3), px(3)]);
      ctx.strokeRect(t.x, t.y, t.w, t.h); ctx.setLineDash([]);
    }

    // 3) CAMERA BOUNDS frame (the world region the follow-camera may scroll within)
    if (level.camera && level.camera.bounds) {
      const b = level.camera.bounds;
      ctx.strokeStyle = "#ff9d4d"; ctx.lineWidth = px(2); ctx.setLineDash([px(6), px(4)]);
      ctx.strokeRect(b[0], b[1], b[2], b[3]); ctx.setLineDash([]);
      ctx.fillStyle = "#ff9d4d"; ctx.font = px(9) + "px system-ui"; ctx.textBaseline = "top";
      ctx.fillText("camera bounds", b[0] + px(3), b[1] + px(3));
    }

    // 4) world extent outline
    ctx.strokeStyle = "#3a4666"; ctx.lineWidth = px(1);
    ctx.strokeRect(0, 0, worldW, worldH);

    // 5) THE ONE-SCREEN GUIDE BOX -- device-screen-sized dashed rect so the author always
    //    sees "how much fits on the handheld at once" while building a wider level.
    const sw = project.size[0], sh = project.size[1];
    const gx = opts.guideX || 0, gy = opts.guideY || 0;
    ctx.strokeStyle = "#ffffff"; ctx.lineWidth = px(2); ctx.setLineDash([px(5), px(4)]);
    ctx.strokeRect(gx, gy, sw, sh); ctx.setLineDash([]);
    ctx.fillStyle = "#ffffffcc"; ctx.font = px(9) + "px system-ui"; ctx.textBaseline = "bottom";
    ctx.fillText("one screen (" + sw + "x" + sh + ")", gx + px(3), gy + sh - px(3));

    vp.resetTransform(ctx);
    return { worldW: worldW, worldH: worldH };
  }

  const api = { draw: draw, FLAGS: FLAGS, FLAG_COLOR: FLAG_COLOR, flagsOf: flagsOf, flagColor: flagColor };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PGRender = api;
})(typeof window !== "undefined" ? window : globalThis);
