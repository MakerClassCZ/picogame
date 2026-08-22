#!/usr/bin/env python3
# Bake a picogame authoring scene (*.scene.json) into a compact runtime Python
# module (SCENE = {...}) the device/simulator imports. Colors -> wire RGB565,
# tilemap grid -> bytes, color assets -> PAL8 atlases (hex). Run the result through
# tools/build_mpy.sh for the on-device .mpy. (Loader: lib/picogame_scene.py.)
#
#   python tools/scene_build.py examples/levels/world1.scene.json
#       -> examples/levels/world1_scene.py  (module attr SCENE)

import json
import os
import sys


def w565(rgb):
    r, g, b = rgb
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


def bake_png(path, fw, fh, frames, transparent=None):
    """Convert a PNG (horizontal atlas of `frames` fw x fh cells, RGBA) to a PAL8
    atlas. Opaque pixels quantize to a shared <=255-colour palette; alpha<128 ->
    transparent index 0. Mirrors cavern_pack / png2picogame."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    pix = []
    for f in range(frames):
        cell = im.crop((f * fw, 0, f * fw + fw, fh)).convert("RGB")
        al = im.crop((f * fw, 0, f * fw + fw, fh)).getchannel("A")
        rgb = list(cell.getdata())
        aa = list(al.getdata())
        pix.extend(rgb[i] for i in range(len(aa)) if aa[i] >= 128)
    # <= 255 distinct opaque colours (the pixel-art norm): keep them EXACTLY, first-seen order -
    # PIL's median-cut quantizer merges close shades even when it has room, which silently
    # altered art on device. Only when the art really exceeds 255 colours do we median-cut.
    # (The web editor's in-browser baker applies the same rule, so both bake identically.)
    uniq = []
    seen = {}
    for c in pix:
        if c not in seen:
            seen[c] = len(uniq) + 1
            uniq.append(c)
            if len(uniq) > 255:
                break
    stride = fw * frames
    data = bytearray(stride * fh)
    if len(uniq) <= 255:
        palette = [w565((0, 0, 0))] + [w565(c) for c in uniq]
        for f in range(frames):
            cell = list(im.crop((f * fw, 0, f * fw + fw, fh)).convert("RGB").getdata())
            al = list(im.crop((f * fw, 0, f * fw + fw, fh)).getchannel("A").getdata())
            for p in range(fw * fh):
                if al[p] >= 128:
                    data[(p // fw) * stride + f * fw + (p % fw)] = seen[cell[p]]
        return ("pal8", bytes(data).hex(), fw, fh, frames, 0, tuple(palette))
    samp = Image.new("RGB", (max(1, len(pix)), 1))
    samp.putdata(pix or [(0, 0, 0)])
    pal_img = samp.quantize(colors=255, method=Image.MEDIANCUT)
    pr = pal_img.getpalette() or []
    ncol = len(pr) // 3
    palette = [w565((0, 0, 0))]
    for i in range(255):
        if i < ncol:
            palette.append(w565((pr[i * 3], pr[i * 3 + 1], pr[i * 3 + 2])))
        else:
            palette.append(0)
    for f in range(frames):
        cell = im.crop((f * fw, 0, f * fw + fw, fh)).convert("RGB").quantize(palette=pal_img)
        al = list(im.crop((f * fw, 0, f * fw + fw, fh)).getchannel("A").getdata())
        idx = list(cell.getdata())
        for p in range(fw * fh):
            if al[p] >= 128:
                data[(p // fw) * stride + f * fw + (p % fw)] = idx[p] + 1
    return ("pal8", bytes(data).hex(), fw, fh, frames, 0, tuple(palette))


def bake_asset(a, base="."):
    """-> (fmt, hexdata, w, h, frames, transparent_or_None, palette_tuple)."""
    t = a["type"]
    if t == "pal8_inline":
        # Pre-quantized PAL8 atlas inlined in the JSON (the web editor's playground handoff emits
        # these; mirrored by web/play/scene_bake.py). Passthrough - no PNG on disk needed.
        import base64
        fw, fh = a.get("tile") or a.get("frame") or [a["width"], a["height"]]
        raw = base64.b64decode(a["data"])
        return ("pal8", raw.hex(), fw, fh, a.get("frames", 1), 0, tuple(a["palette"]))
    if t in ("sprite", "bitmap", "tileset"):
        fw, fh = a.get("frame") or a.get("tile") or a["size"]
        return bake_png(os.path.join(base, a["src"]), fw, fh, a.get("frames", 1),
                        a.get("transparent"))
    if t == "rect":
        w, h = a["size"]
        data = bytes([1]) * (w * h)
        pal = (w565((0, 0, 0)), w565(a["color"]))
        return ("pal8", data.hex(), w, h, 1, None, pal)
    if t == "tileset_color":
        tw, th = a["tile"]
        colors = a["colors"]
        n = max(int(k) for k in colors)            # tile values 1..n; 0 = empty
        frames = n + 1
        stride = tw * frames
        data = bytearray(stride * th)
        for f in range(1, frames):                 # frame f filled with index f
            for y in range(th):
                base = y * stride + f * tw
                for x in range(tw):
                    data[base + x] = f
        pal = [w565((0, 0, 0))]
        for v in range(1, frames):                 # sparse colour maps are legal: gaps -> magenta
            pal.append(w565(colors.get(str(v), (255, 0, 255))))
        return ("pal8", bytes(data).hex(), tw, th, frames, 0, tuple(pal))
    raise ValueError("unknown asset type: " + t)


def tile_props(a):
    """-> {propname: bytes indexed by tile value} for any tileset with props."""
    if "props" not in a:
        return None
    length = max(int(k) for k in a["props"]) + 1
    if "frames" in a:
        length = max(length, a["frames"])
    if "colors" in a:
        length = max(length, max(int(k) for k in a["colors"]) + 1)
    names = set()
    for v in a["props"].values():
        names.update(v.keys())
    out = {}
    for name in sorted(names):                    # deterministic module text (set order varies per run)
        b = bytearray(length)
        for vs, flags in a["props"].items():
            if flags.get(name):
                b[int(vs)] = 1
        out[name] = bytes(b)
    return out


def bake_tilemap(layer):
    orient = None
    if "grid" in layer:                       # 2-D int array (what the editor exports)
        # A cell value may carry orientation in bits 8-10 (value = tile | orient << 8;
        # bit8 flipX, bit9 flipY, bit10 transpose - the native Tilemap orient bits).
        # Baked as a parallel bytes plane, present only when some cell uses it.
        g2 = layer["grid"]
        nrows = len(g2)
        cols = len(g2[0]) if nrows else 0
        grid = bytearray(cols * nrows)
        for ry, row in enumerate(g2):
            for cx in range(cols):
                v = row[cx] if cx < len(row) else 0
                grid[ry * cols + cx] = v & 0xFF
                if v >> 8:
                    if orient is None:
                        orient = bytearray(cols * nrows)
                    orient[ry * cols + cx] = v >> 8
    else:                                     # rows of chars + a legend (the ASCII form)
        # Same cell semantics as the grid above, so the two forms bake byte-identically: a
        # legend value may carry orientation in bits 8-10, which becomes the parallel plane.
        legend = layer["legend"]
        rows = layer["rows"]
        cols = len(rows[0]) if rows else 0
        nrows = len(rows)
        grid = bytearray(cols * nrows)
        for ry, row in enumerate(rows):
            for cx in range(cols):
                v = legend.get(row[cx], 0) if cx < len(row) else 0
                grid[ry * cols + cx] = v & 0xFF
                if v >> 8:
                    if orient is None:
                        orient = bytearray(cols * nrows)
                    orient[ry * cols + cx] = v >> 8
    ox, oy = layer.get("pos", [0, 0])
    out = ("tilemap", layer["asset"], cols, nrows, ox, oy, bytes(grid))
    if orient is not None:
        out += (bytes(orient),)
    return out


def bake_assets(assets, base):
    """-> (assets_dict, tileprops, anims) -- the shared 'bank'."""
    a_out, tp_out, an_out = {}, {}, {}
    for aid, a in assets.items():
        a_out[aid] = bake_asset(a, base)
        tp = tile_props(a)
        if tp:
            tp_out[aid] = tp
        if "animations" in a:
            an_out[aid] = {nm: (tuple(d["frames"]), d.get("fps", 8), d.get("loop", True))
                           for nm, d in a["animations"].items()}
    return a_out, tp_out, an_out


def bake_layers(layers_json):
    out = []
    for layer in layers_json:
        k = layer["kind"]
        if k == "tilemap":
            out.append(bake_tilemap(layer))
        elif k == "sprite":
            ax, ay = layer.get("anchor", [0, 0])
            x, y = layer["pos"]
            out.append(("sprite", layer["asset"], layer.get("name"),
                        x, y, ax, ay, layer.get("frame", 0), layer.get("data"), layer.get("anim"),
                        layer.get("angle", 0)))
        elif k == "group":
            ax, ay = layer.get("anchor", [0, 0])
            insts = tuple(tuple(p) for p in layer["instances"])
            out.append(("group", layer["asset"], layer.get("tag"), ax, ay, insts, layer.get("anim")))
        elif k in ("hudlabel", "hud"):
            x, y = layer["pos"]
            out.append(("hudlabel", layer.get("name"), x, y,
                        w565(layer.get("fg", [255, 255, 255])), w565(layer.get("bg", [0, 0, 0]))))
        elif k == "particles":
            out.append(("particles", layer.get("name"), layer.get("capacity", 64),
                        layer.get("size", 1), layer.get("gravity", 0.0), layer.get("fade", False)))
        else:
            raise ValueError("unknown layer kind: " + k)
    return out


def bake_camera(cam, size):
    if not cam:
        return None
    b = cam.get("bounds", [0, 0, size[0], size[1]])
    return (cam.get("mode", "follow"), cam.get("target"), cam.get("axis", "x"),
            b[0], b[1], b[2], b[3])


def bake_sounds(sounds):
    """{id:{src}} | {id:src} -> {id: src_path} (wavs stay wav; loaded at runtime)."""
    if not sounds:
        return None
    return {k: (v["src"] if isinstance(v, dict) else v) for k, v in sounds.items()}


def _add_extras(out, src):
    """Pass through trigger zones / spawn points / music (plain data)."""
    if src.get("zones"):
        out["zones"] = [tuple([z.get("tag")]) + (z["x"], z["y"], z["w"], z["h"])
                        + ((z["data"],) if z.get("data") else ())
                        for z in src["zones"]]
    if src.get("points"):
        out["points"] = {p["name"]: (p["x"], p["y"]) for p in src["points"] if p.get("name")}
        pdata = {p["name"]: p["data"] for p in src["points"] if p.get("name") and p.get("data")}
        if pdata:
            out["pdata"] = pdata
    if src.get("music"):
        out["music"] = src["music"]


def _asset_frames(a):
    """Frame count the asset will bake to (mirrors bake_asset), or None if unknown."""
    t = a.get("type")
    if t in ("sprite", "bitmap", "tileset", "pal8_inline"):
        return a.get("frames", 1)
    if t == "rect":
        return 1
    if t == "tileset_color":
        try:
            return max(int(k) for k in a["colors"]) + 1
        except (KeyError, ValueError):
            return None
    return None


def validate(scene):
    """Build-time sanity check of the authoring JSON (host-only, no firmware
    impact). Returns a list of 'path: problem' strings; empty = valid. Catches
    the mistakes that otherwise surface as garbage pixels / skipped tiles / UB
    on device: dangling asset ids, out-of-range sprite frames / tile indices /
    animation frames, non-rectangular tilemap grids, duplicate layer names or
    group tags, and props tables indexing past the tileset."""
    errs = []
    assets = scene.get("assets", {})
    frames = {}
    for aid, a in assets.items():
        f = _asset_frames(a)
        if f is not None:
            frames[aid] = f
        for nm, d in (a.get("animations") or {}).items():
            for i, fr in enumerate(d.get("frames", ())):
                if f is not None and fr >= f:
                    errs.append("assets[%r].animations[%r].frames[%d]: frame %d >= frames (%d)"
                                % (aid, nm, i, fr, f))
        for k in (a.get("props") or {}):
            try:
                kv = int(k)
            except ValueError:
                errs.append("assets[%r].props[%r]: key is not an integer tile value" % (aid, k))
                continue
            if f is not None and kv >= f:
                errs.append("assets[%r].props[%r]: tile value %d >= frames (%d)"
                            % (aid, k, kv, f))

    def check_layers(layers, where):
        names = {}                       # name / group tag -> owning layer path
        for i, layer in enumerate(layers):
            p = "%s[%d]" % (where, i)
            kind = layer.get("kind")
            aid = layer.get("asset")
            f = None
            if kind in ("tilemap", "sprite", "group"):
                if aid not in assets:
                    errs.append("%s.asset: unknown asset %r" % (p, aid))
                else:
                    f = frames.get(aid)
            field = "tag" if kind == "group" else "name"
            label = layer.get(field)
            if label:
                if label in names:
                    errs.append("%s.%s: duplicate %r (already used by %s)"
                                % (p, field, label, names[label]))
                else:
                    names[label] = p
            if kind == "sprite" and f is not None and layer.get("frame", 0) >= f:
                errs.append("%s.frame: frame %d >= asset %r frames (%d)"
                            % (p, layer.get("frame", 0), aid, f))
            if kind in ("sprite", "group"):
                anim = layer.get("anim")
                if anim and aid in assets and anim not in (assets[aid].get("animations") or {}):
                    errs.append("%s.anim: asset %r declares no animation %r" % (p, aid, anim))
            if kind != "tilemap":
                continue
            if "grid" in layer:                    # 2-D int array
                g2 = layer["grid"]
                cols0 = len(g2[0]) if g2 else 0
                for ry, row in enumerate(g2):
                    if len(row) != cols0:
                        errs.append("%s.grid[%d]: row length %d != %d (row 0) - grid not rectangular"
                                    % (p, ry, len(row), cols0))
                dc, dr = layer.get("cols"), layer.get("rows")
                if isinstance(dc, int) and dc != cols0:
                    errs.append("%s.grid: %d columns != declared cols (%d)" % (p, cols0, dc))
                if isinstance(dr, int) and dr != len(g2):
                    errs.append("%s.grid: %d rows != declared rows (%d)" % (p, len(g2), dr))
                for ry, row in enumerate(g2):
                    for cx, v in enumerate(row):
                        t, o = v & 0xFF, v >> 8
                        if o > 7:
                            errs.append("%s.grid[%d][%d]: bad orientation bits %d (value %d; bits 8-10 only)"
                                        % (p, ry, cx, o, v))
                        elif o and t == 0:
                            errs.append("%s.grid[%d][%d]: orientation bits on an empty cell (value %d)"
                                        % (p, ry, cx, v))
                        if f is not None and t >= f:
                            errs.append("%s.grid[%d][%d]: tile index %d >= tileset frames (%d)"
                                        % (p, ry, cx, t, f))
            elif "rows" in layer:                  # rows of chars + a legend
                rows = layer["rows"]
                cols0 = len(rows[0]) if rows else 0
                for ry, row in enumerate(rows):
                    if len(row) != cols0:
                        errs.append("%s.rows[%d]: row length %d != %d (row 0) - grid not rectangular"
                                    % (p, ry, len(row), cols0))
                legend = layer.get("legend") or {}
                for ch, v in legend.items():
                    t, o = v & 0xFF, v >> 8
                    if o > 7:
                        errs.append("%s.legend[%r]: bad orientation bits %d (value %d; bits 8-10 only)"
                                    % (p, ch, o, v))
                    if f is not None and t >= f:
                        errs.append("%s.legend[%r]: tile index %d >= tileset frames (%d)"
                                    % (p, ch, t, f))
                # A char the legend doesn't define bakes as empty, which turns a typo into a
                # silent hole in the level - the one failure mode of hand-edited ASCII maps.
                # '.' and ' ' are the conventional empties, so they need no entry.
                unknown = sorted({ch for row in rows for ch in row} - set(legend) - {".", " "})
                if unknown:
                    errs.append("%s.rows: character(s) %s are not in the legend (they would bake "
                                "as empty)" % (p, ", ".join(repr(c) for c in unknown)))

    if "levels" in scene:
        for li, lv in enumerate(scene["levels"]):
            check_layers(lv.get("layers", []), "levels[%d].layers" % li)
    else:
        check_layers(scene.get("layers", []), "layers")
    return errs


def write_module(path, name, data):
    with open(path, "w") as f:
        f.write("# AUTO-GENERATED by tools/scene_build.py\n")
        f.write(name + " = " + repr(data) + "\n")
    print("wrote", path, "(%d bytes)" % os.path.getsize(path))


def main():
    src = sys.argv[1]
    scene = json.load(open(src))
    errs = validate(scene)
    if errs:
        for e in errs:
            sys.stderr.write("scene_build: %s\n" % e)
        sys.exit("%s: scene validation failed (%d error%s)"
                 % (src, len(errs), "" if len(errs) == 1 else "s"))
    base = os.path.dirname(os.path.abspath(src))
    size = scene.get("size", [320, 240])
    stem = os.path.splitext(os.path.splitext(src)[0])[0]

    if "levels" in scene:
        # Multi-level project: ONE shared bank module + one module per level.
        a, tp, an = bake_assets(scene["assets"], base)
        bank = {"assets": a, "tileprops": tp, "anims": an}
        snd = bake_sounds(scene.get("sounds"))
        if snd:
            bank["sounds"] = snd
        write_module(stem + "_bank.py", "BANK", bank)
        for lv in scene["levels"]:
            name = lv.get("name", "level")
            out = {"bg": w565(lv.get("background", [0, 0, 0])),
                   "layers": bake_layers(lv["layers"]),
                   "camera": bake_camera(lv.get("camera"), size)}
            _add_extras(out, lv)
            safe = "".join(c if c.isalnum() else "_" for c in name)
            write_module(os.path.join(base, safe + "_level.py"), "LEVEL", out)
        return

    # Single standalone scene (assets inline).
    a, tp, an = bake_assets(scene["assets"], base)
    out = {"bg": w565(scene.get("background", [0, 0, 0])), "assets": a,
           "tileprops": tp, "anims": an, "layers": bake_layers(scene["layers"]),
           "camera": bake_camera(scene.get("camera"), size)}
    if out["camera"] is None:
        del out["camera"]
    snd = bake_sounds(scene.get("sounds"))
    if snd:
        out["sounds"] = snd
    _add_extras(out, scene)
    write_module(stem + "_scene.py", "SCENE", out)


if __name__ == "__main__":
    main()
