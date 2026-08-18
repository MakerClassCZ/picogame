// picogame asset converter -- the browser twin of tools/png2picogame.py.
// Same rules, same module shape: index 0 = transparent (alpha < 128), <=255 colours kept
// exactly (PAL8 quantize + optional dither via median-cut), tile grids repacked to a strip
// (+ dedup of identical tiles up to orientation, with the REMAP table), RGB565 with the
// #F800F8 colour key, per-row RLE. Output = a .py module with bitmap(pg). No server.
(function () {
  "use strict";
  const E = window.PGEditor;
  const $ = (id) => document.getElementById(id);

  let srcImg = null, srcName = "image";
  let last = null;                       // last conversion result {module, ...}

  // ---------------------------------------------------------------- helpers
  function toast(msg, kind) {
    const box = $("toasts"); const el = document.createElement("div");
    el.className = "toast " + (kind || "info"); el.textContent = msg; box.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }
  function rgbaOf(img) {
    const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
    const ctx = c.getContext("2d"); ctx.drawImage(img, 0, 0);
    return { data: ctx.getImageData(0, 0, c.width, c.height).data, w: c.width, h: c.height };
  }
  function pyBytes(u8) {                 // repr(bytes) like CPython: b'..' with escapes
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

  // apply the transparency rule -> RGBA copy with alpha 0 where transparent
  function applyTransparency(rgba, w, h, rule) {
    const out = new Uint8ClampedArray(rgba);
    if (rule === "none") { for (let i = 3; i < out.length; i += 4) out[i] = 255; return out; }
    if (rule === "alpha") return out;
    let kr, kg, kb;
    if (rule === "topleft") { kr = out[0]; kg = out[1]; kb = out[2]; }
    else { kr = 0xF8; kg = 0; kb = 0xF8; }
    for (let i = 0; i < out.length; i += 4)
      if (out[i] === kr && out[i + 1] === kg && out[i + 2] === kb) out[i + 3] = 0;
    return out;
  }

  // tile grid -> horizontal strip (row-major tile order, like repack_tiles)
  function repackTiles(rgba, w, h, tw, th) {
    const cols = Math.floor(w / tw), rows = Math.floor(h / th), n = cols * rows;
    const out = new Uint8ClampedArray(tw * n * th * 4);
    const stride = tw * n;
    for (let t = 0; t < n; t++) {
      const sx = (t % cols) * tw, sy = Math.floor(t / cols) * th;
      for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) {
        const si = ((sy + y) * w + sx + x) * 4, di = (y * stride + t * tw + x) * 4;
        out[di] = rgba[si]; out[di + 1] = rgba[si + 1]; out[di + 2] = rgba[si + 2]; out[di + 3] = rgba[si + 3];
      }
    }
    return { rgba: out, w: stride, h: th, frames: n };
  }

  // engine-formula orientation of one tile (mirrors _orient_bytes): key string of pixels
  function orientKey(rgba, stride, t, tw, th, tp, fx, fy) {
    const dw = tp ? th : tw, dh = tp ? tw : th;
    let s = "";
    for (let ly = 0; ly < dh; ly++) for (let lx = 0; lx < dw; lx++) {
      let su = tp ? ly : lx, sv = tp ? lx : ly;
      if (fx) su = tw - 1 - su;
      if (fy) sv = th - 1 - sv;
      const i = (sv * stride + t * tw + su) * 4;
      const a = rgba[i + 3] < 128 ? 0 : 1;
      s += a ? (rgba[i] << 16 | rgba[i + 1] << 8 | rgba[i + 2]).toString(36) + "," : "t,";
    }
    return s;
  }
  function dedupTiles(strip, tw, th, n) {
    const combos = [[0, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 1]];
    if (tw === th) combos.push([1, 0, 0], [1, 1, 0], [1, 0, 1], [1, 1, 1]);
    const variant = {}, remap = [], uniques = [];
    for (let t = 0; t < n; t++) {
      const key = orientKey(strip, tw * n, t, tw, th, 0, 0, 0);
      if (variant[key] !== undefined) { remap.push(variant[key]); continue; }
      const ui = uniques.length; uniques.push(t); remap.push([ui, 0, 0, 0]);
      combos.forEach(([tp, fx, fy]) => {
        const k = orientKey(strip, tw * n, t, tw, th, tp, fx, fy);
        if (variant[k] === undefined) variant[k] = [ui, fx, fy, tp];
      });
    }
    const out = new Uint8ClampedArray(tw * uniques.length * th * 4);
    const ostride = tw * uniques.length, istride = tw * n;
    uniques.forEach((ot, ui) => {
      for (let y = 0; y < th; y++) for (let x = 0; x < tw; x++) {
        const si = (y * istride + ot * tw + x) * 4, di = (y * ostride + ui * tw + x) * 4;
        out[di] = strip[si]; out[di + 1] = strip[si + 1]; out[di + 2] = strip[si + 2]; out[di + 3] = strip[si + 3];
      }
    });
    return { rgba: out, w: ostride, h: th, frames: uniques.length, remap };
  }

  // Floyd-Steinberg dither onto a fixed palette (reps = [[r,g,b]]) -> PAL8 indices (1-based, 0 = transparent)
  function ditherPal8(rgba, w, h, reps) {
    const data = new Uint8Array(w * h);
    const err = new Float32Array(w * h * 3);
    function nearest(r, g, b) {
      let bi = 0, bd = 1e12;
      for (let i = 0; i < reps.length; i++) {
        const dr = reps[i][0] - r, dg = reps[i][1] - g, db = reps[i][2] - b, d = dr * dr + dg * dg + db * db;
        if (d < bd) { bd = d; bi = i; }
      }
      return bi;
    }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (rgba[i * 4 + 3] < 128) continue;
      const r = Math.max(0, Math.min(255, rgba[i * 4] + err[i * 3])),
            g = Math.max(0, Math.min(255, rgba[i * 4 + 1] + err[i * 3 + 1])),
            b = Math.max(0, Math.min(255, rgba[i * 4 + 2] + err[i * 3 + 2]));
      const k = nearest(r, g, b); data[i] = k + 1;
      const er = r - reps[k][0], eg = g - reps[k][1], eb = b - reps[k][2];
      const push = (xx, yy, f) => {
        if (xx < 0 || xx >= w || yy >= h) return;
        const j = (yy * w + xx) * 3; err[j] += er * f; err[j + 1] += eg * f; err[j + 2] += eb * f;
      };
      push(x + 1, y, 7 / 16); push(x - 1, y + 1, 3 / 16); push(x, y + 1, 5 / 16); push(x + 1, y + 1, 1 / 16);
    }
    return data;
  }

  function convertPal8(rgba, w, h, maxColors, dither) {
    // exact path when it fits and no dither asked (matches CLI: sorted unique colours)
    const hist = {};
    for (let i = 0; i < w * h; i++) {
      if (rgba[i * 4 + 3] < 128) continue;
      const k = (rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2];
      hist[k] = (hist[k] || 0) + 1;
    }
    const uniq = Object.keys(hist).map(Number);
    let reps, data;
    if (!dither && uniq.length <= maxColors) {
      uniq.sort((a, b) => a - b);                     // CLI: sorted(opaque)
      reps = uniq.map(k => [k >> 16, (k >> 8) & 255, k & 255]);
      const idxOf = {}; uniq.forEach((k, i) => idxOf[k] = i + 1);
      data = new Uint8Array(w * h);
      for (let i = 0; i < w * h; i++) {
        if (rgba[i * 4 + 3] < 128) continue;
        data[i] = idxOf[(rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2]];
      }
    } else {
      const q = E.bakePal8(rgba, w, h);                // median-cut to <=255 (uses first-seen exact if fits)
      let pal = q.palette.slice(1).map(v => { const n = ((v >> 8) | (v << 8)) & 0xFFFF; return [((n >> 11) & 31) << 3, ((n >> 5) & 63) << 2, (n & 31) << 3]; });
      if (pal.length > maxColors) {                    // reduce further: cheap re-quantize on the palette
        const cols = uniq.map(k => [k >> 16, (k >> 8) & 255, k & 255, hist[k]]);
        pal = medianCutN(cols, maxColors);
      }
      reps = pal;
      data = dither ? ditherPal8(rgba, w, h, reps) : nearestPal8(rgba, w, h, reps);
    }
    const palette = [0].concat(reps.map(c => E.w565(c[0], c[1], c[2])));
    return { data, palette, ncolors: reps.length };
  }
  function nearestPal8(rgba, w, h, reps) {
    const data = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      if (rgba[i * 4 + 3] < 128) continue;
      let bi = 0, bd = 1e12;
      for (let k = 0; k < reps.length; k++) {
        const dr = reps[k][0] - rgba[i * 4], dg = reps[k][1] - rgba[i * 4 + 1], db = reps[k][2] - rgba[i * 4 + 2], d = dr * dr + dg * dg + db * db;
        if (d < bd) { bd = d; bi = k; }
      }
      data[i] = bi + 1;
    }
    return data;
  }
  function medianCutN(colors, n) {                    // same algorithm as core.js medianCut, exposed for max-colours
    let boxes = [colors];
    const range = b => [0, 1, 2].map(c => { let lo = 255, hi = 0; b.forEach(p => { if (p[c] < lo) lo = p[c]; if (p[c] > hi) hi = p[c]; }); return hi - lo; });
    while (boxes.length < n) {
      let bi = -1, best = -1;
      boxes.forEach((b, i) => { if (b.length < 2) return; const m = Math.max(...range(b)); if (m > best) { best = m; bi = i; } });
      if (bi < 0 || best === 0) break;
      const b = boxes[bi], rg = range(b), axis = rg.indexOf(Math.max(...rg));
      b.sort((x, y) => x[axis] - y[axis]);
      const total = b.reduce((a, p) => a + p[3], 0); let acc = 0, cut = 1;
      for (let i = 0; i < b.length - 1; i++) { acc += b[i][3]; if (acc * 2 >= total) { cut = i + 1; break; } }
      boxes.splice(bi, 1, b.slice(0, cut), b.slice(cut));
    }
    return boxes.map(b => { let r = 0, g = 0, bl = 0, k = 0; b.forEach(p => { r += p[0] * p[3]; g += p[1] * p[3]; bl += p[2] * p[3]; k += p[3]; }); return [Math.round(r / k), Math.round(g / k), Math.round(bl / k)]; });
  }
  function convertRgb565(rgba, w, h) {
    const out = new Uint8Array(w * h * 2); const key = E.w565(0xF8, 0, 0xF8); let transp = false;
    for (let i = 0; i < w * h; i++) {
      let v;
      if (rgba[i * 4 + 3] < 128) { v = key; transp = true; } else v = E.w565(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]);
      out[i * 2] = v & 255; out[i * 2 + 1] = v >> 8;   // struct '<H'
    }
    return { data: out, transparent: transp ? key : null };
  }
  function rleEncode(data, w, h) {
    const out = [];
    for (let y = 0; y < h; y++) {
      let x = 0;
      while (x < w) {
        const v = data[y * w + x]; let run = 1;
        while (x + run < w && run < 255 && data[y * w + x + run] === v) run++;
        out.push(run, v); x += run;
      }
    }
    return new Uint8Array(out);
  }

  // ---------------------------------------------------------------- convert (all options)
  function convert() {
    if (!srcImg) return null;
    const mode = $("mode").value, name = ($("name").value.trim() || "asset");
    let { data: rgba, w, h } = rgbaOf(srcImg);
    rgba = applyTransparency(rgba, w, h, $("transp").value);
    let frames = 1, remap = null, notes = [];
    if (mode === "tile") {
      const tw = Math.max(1, +$("tw").value | 0), th = Math.max(1, +$("th").value | 0);
      const rp = repackTiles(rgba, w, h, tw, th);
      if (w % tw || h % th) notes.push("image " + w + "x" + h + " is not a whole number of " + tw + "x" + th + " tiles - edge remainder dropped");
      rgba = rp.rgba; w = rp.w; h = rp.h; frames = rp.frames;
      if ($("dedup").checked) {
        const before = frames, dd = dedupTiles(rgba, tw, th, frames);
        rgba = dd.rgba; w = dd.w; frames = dd.frames; remap = dd.remap;
        notes.push("dedup: " + before + " -> " + frames + " tiles (" + Math.round(100 * (before - frames) / (before || 1)) + "% saved)");
      }
    } else if (mode === "frames") {
      frames = Math.max(1, +$("frames").value | 0);
      if (w % frames) { notes.push("frames must divide the width (" + w + ") - using 1"); frames = 1; }
    }
    const frameW = w / frames;
    let fmt = $("fmt").value, maxColors = Math.max(1, Math.min(255, +$("colors").value | 0)), dither = $("dither").checked;
    if (dither || maxColors < 255) fmt = "pal8";
    if (fmt === "auto") {
      const set = new Set();
      for (let i = 0; i < w * h && set.size <= 256; i++) if (rgba[i * 4 + 3] >= 128) set.add((rgba[i * 4] << 16) | (rgba[i * 4 + 1] << 8) | rgba[i * 4 + 2]);
      fmt = set.size <= 255 ? "pal8" : "rgb565";
    }
    const lines = []; let dataBytes, paletteRepr = "None", fmtConst, transparent, ncolors = 0, rleBytes = null;
    if (fmt === "pal8") {
      const q = convertPal8(rgba, w, h, maxColors, dither);
      dataBytes = q.data; ncolors = q.ncolors; fmtConst = 1; transparent = 0;
      paletteRepr = "array.array('H', [" + q.palette.join(", ") + "])";      // repr(list), like the CLI
      if ($("rle").checked) {
        if (frames !== 1) notes.push("RLE needs a single-frame image - skipped");
        else rleBytes = rleEncode(dataBytes, w, h);
      }
    } else {
      const c = convertRgb565(rgba, w, h); dataBytes = c.data; fmtConst = 0; transparent = c.transparent;
      if ($("rle").checked) notes.push("RLE is PAL8-only - skipped");
    }
    if (rleBytes) {
      lines.push("import array",
        "# picogame RLE asset from " + srcName + " (" + w + "x" + h + ", inflates to a PAL8 Bitmap on load)",
        "WIDTH = " + w, "HEIGHT = " + h, "TRANSPARENT = " + transparent, "PALETTE = " + paletteRepr,
        "RLE = " + pyBytes(rleBytes), "", "",
        "def bitmap(pg):", "    data = bytearray(WIDTH * HEIGHT)", "    rle = RLE; i = 0; p = 0; n = len(rle)",
        "    while p < n:", "        c = rle[p]; v = rle[p + 1]; p += 2", "        for _ in range(c):", "            data[i] = v; i += 1",
        "    return pg.Bitmap(data, WIDTH, HEIGHT, format=1, palette=PALETTE,",
        "                     frames=1, stride=WIDTH, transparent=TRANSPARENT)", "");
    } else {
      if (fmt === "pal8") lines.push("import array");
      lines.push("# picogame asset from " + srcName + " (" + fmt + ", frame " + frameW + "x" + h + ", frames " + frames + ")",
        "WIDTH = " + frameW, "HEIGHT = " + h, "FRAMES = " + frames, "STRIDE = " + w,
        "FORMAT = " + fmtConst + "  # 0=RGB565, 1=PAL8",
        "TRANSPARENT = " + (transparent === null ? "None" : transparent),
        "PALETTE = " + paletteRepr, "DATA = " + pyBytes(dataBytes));
      if (remap) lines.push("REMAP = [" + remap.map(r => "(" + r.join(", ") + ")").join(", ") + "]  # per old tile: (idx, flip_x, flip_y, transpose); tm.tile(x, y, *REMAP[old])");
      lines.push("", "", "def bitmap(pg):",
        "    return pg.Bitmap(DATA, WIDTH, HEIGHT, format=FORMAT, palette=PALETTE,",
        "                     frames=FRAMES, stride=STRIDE, transparent=TRANSPARENT)", "");
    }
    const ram = fmt === "pal8" ? w * h + 2 * (ncolors + 1) : w * h * 2;
    return { module: lines.join("\n"), name, fmt, w, h, frames, frameW, ncolors, ram, notes,
             dataBytes, rgba, rleLen: rleBytes ? rleBytes.length : null, palette: fmt === "pal8" ? paletteRepr : null };
  }

  // ---------------------------------------------------------------- UI
  function fmtKB(b) { return b >= 1024 ? (b / 1024).toFixed(1) + " KB" : b + " B"; }
  function render() {
    const r = convert(); last = r;
    $("btnDl").disabled = $("btnTry").disabled = !r;
    if (!r) return;
    const bigWarn = r.ram > 40 * 1024 ? "  <- large for an RP2040 (~138 KB heap); use PAL8 + fewer colours, or smaller art" : (r.ram > 15 * 1024 ? "  (fine on RP2350/Jam; watch it on RP2040)" : "");
    $("stat").innerHTML =
      r.fmt.toUpperCase() + "  " + r.frameW + "x" + r.h + " x " + r.frames + " frame(s)" +
      (r.fmt === "pal8" ? "  " + r.ncolors + " colour(s)" : "") + "\n" +
      "device RAM for the Bitmap: <b class=\"" + (r.ram > 40 * 1024 ? "warn" : "ok") + "\">" + fmtKB(r.ram) + "</b>" + bigWarn +
      (r.rleLen !== null ? "\nRLE module data: " + fmtKB(r.rleLen) + " (" + Math.round(100 * r.rleLen / (r.w * r.h)) + "% of raw; inflates to " + fmtKB(r.w * r.h) + " on load)" : "") +
      "\nmodule .py: " + fmtKB(r.module.length) +
      (r.notes.length ? "\n" + r.notes.map(n => "note: " + n).join("\n") : "");
    // frames preview: draw each frame from the CONVERTED pixels (what the engine gets)
    const fr = $("framesView"); fr.innerHTML = "";
    const scale = r.frameW <= 32 ? 3 : (r.frameW <= 96 ? 2 : 1);
    const show = Math.min(r.frames, 64);
    for (let f = 0; f < show; f++) {
      const c = document.createElement("canvas"); c.width = r.frameW; c.height = r.h;
      c.style.width = (r.frameW * scale) + "px"; c.style.height = (r.h * scale) + "px";
      const ctx = c.getContext("2d"), id = ctx.createImageData(r.frameW, r.h);
      for (let y = 0; y < r.h; y++) for (let x = 0; x < r.frameW; x++) {
        const si = (y * r.w + f * r.frameW + x) * 4, di = (y * r.frameW + x) * 4;
        id.data[di] = r.rgba[si]; id.data[di + 1] = r.rgba[si + 1]; id.data[di + 2] = r.rgba[si + 2]; id.data[di + 3] = r.rgba[si + 3] < 128 ? 0 : 255;
      }
      ctx.putImageData(id, 0, 0);
      const wrap = document.createElement("div"); wrap.className = "fr"; wrap.appendChild(c);
      const lab = document.createElement("div"); lab.textContent = f; wrap.appendChild(lab); fr.appendChild(wrap);
    }
    if (r.frames > show) { const more = document.createElement("div"); more.className = "fr"; more.textContent = "+" + (r.frames - show) + " more"; fr.appendChild(more); }
    // palette
    const pal = $("pal"); pal.innerHTML = "";
    if (r.palette) {
      const m = r.palette.match(/\[(.*)\]/); const vals = m ? m[1].split(",").map(s => +s.trim()).filter(v => !isNaN(v)) : [];
      vals.forEach((v, i) => {
        const n = ((v >> 8) | (v << 8)) & 0xFFFF; const s = document.createElement("span");
        s.style.background = i === 0 ? "transparent" : "rgb(" + (((n >> 11) & 31) << 3) + "," + (((n >> 5) & 63) << 2) + "," + ((n & 31) << 3) + ")";
        s.title = i === 0 ? "0 = transparent" : "index " + i; pal.appendChild(s);
      });
    } else pal.textContent = "RGB565: no palette (2 bytes per pixel)";
    // preview: head of the module (DATA truncated)
    $("code").textContent = r.module.length > 4000 ? r.module.slice(0, 4000) + "\n… (" + fmtKB(r.module.length) + " total - download for the full module)" : r.module;
  }

  function download() {
    if (!last) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([last.module], { type: "text/x-python" }));
    a.download = last.name + ".py"; a.click();
    toast("Downloaded " + last.name + ".py - import it next to your code", "ok");
  }

  // Try in playground: a tiny program showing the sprite (frames cycling) with the module inlined.
  async function tryPlayground() {
    if (!last) return;
    const prog = last.module + "\n\n" +
      "# --- preview: the converted asset on screen (frames cycle; LEFT/RIGHT step) ---\n" +
      "import picogame as pg, picogame_game, picogame_input, picogame_clock\n" +
      "W, H = picogame_game.screen()\n" +
      "scene, _, _ = picogame_game.setup(background=pg.rgb565(40, 44, 60))\n" +
      "bm = bitmap(pg)\n" +
      "spr = pg.Sprite(bm, W // 2, H // 2)\n" +
      "spr.anchor = (0.5, 0.5)\n" +
      "scene.add(spr)\n" +
      "btn = picogame_input.Buttons(); clock = picogame_clock.Clock(30)\n" +
      "f = 0; t = 0\n" +
      "while True:\n" +
      "    btn.poll()\n" +
      "    n = " + last.frames + "\n" +
      "    if btn.just_pressed(btn.RIGHT): f = (f + 1) % n\n" +
      "    if btn.just_pressed(btn.LEFT): f = (f - 1) % n\n" +
      "    t += 1\n" +
      "    if n > 1 and t % 8 == 0: f = (f + 1) % n\n" +
      "    spr.frame = f\n" +
      "    scene.refresh(); clock.tick()\n";
    const cs = new CompressionStream("deflate-raw");
    const w = cs.writable.getWriter(); w.write(new TextEncoder().encode(prog)); w.close();
    const bytes = new Uint8Array(await new Response(cs.readable).arrayBuffer());
    let s = ""; for (const b of bytes) s += String.fromCharCode(b);
    const c = btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const url = (window.PG_PLAYGROUND_URL || "https://picogame.makerclass.cz/playground/") + "#c=" + c;
    if (url.length > 60000) { toast("Asset too big to hand off in a link - download the .py instead", "err"); return; }
    window.open(url, "_blank");
  }

  function loadFile(f) {
    if (!f) return;
    const fr = new FileReader();
    fr.onload = () => { const im = new Image(); im.onload = () => { srcImg = im; srcName = f.name;
      $("name").value = f.name.replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/^([0-9])/, "_$1") || "asset";
      // sensible defaults: square-ish wide image -> guess frames from height
      if (im.naturalWidth % im.naturalHeight === 0 && im.naturalWidth > im.naturalHeight) $("frames").value = im.naturalWidth / im.naturalHeight;
      // no alpha at all (indexed BMP/GIF with a background colour): default the key to the top-left
      // pixel so sprites don't come out on a solid block; the user can still pick "none"/"magenta"
      const px = rgbaOf(im); let anyAlpha = false;
      for (let i = 3; i < px.data.length; i += 4) if (px.data[i] < 128) { anyAlpha = true; break; }
      if (!anyAlpha && $("transp").value === "alpha") { $("transp").value = "topleft"; toast("No alpha channel - using the top-left pixel colour as transparent (change under 'transparent')", "info"); }
      render(); }; im.src = fr.result; };
    fr.readAsDataURL(f);
  }

  // wiring
  const drop = $("drop");
  drop.onclick = () => $("file").click();
  $("file").onchange = (e) => loadFile(e.target.files[0]);
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("hot"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("hot"); }));
  drop.addEventListener("drop", e => loadFile(e.dataTransfer.files[0]));
  document.addEventListener("paste", e => { const it = Array.from(e.clipboardData.items).find(i => i.type.startsWith("image/")); if (it) loadFile(it.getAsFile()); });
  ["mode", "frames", "tw", "th", "dedup", "fmt", "colors", "dither", "transp", "rle", "name"].forEach(id => $(id).addEventListener("input", () => {
    $("rowFrames").hidden = $("mode").value !== "frames"; $("rowTile").hidden = $("mode").value !== "tile"; render();
  }));
  $("btnDl").onclick = download;
  $("btnTry").onclick = tryPlayground;
  $("rowFrames").hidden = $("mode").value !== "frames"; $("rowTile").hidden = $("mode").value !== "tile";
})();
