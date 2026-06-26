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
    stride = fw * frames
    data = bytearray(stride * fh)
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
        for v in range(1, frames):
            pal.append(w565(colors[str(v)]))
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
    for name in names:
        b = bytearray(length)
        for vs, flags in a["props"].items():
            if flags.get(name):
                b[int(vs)] = 1
        out[name] = bytes(b)
    return out


def bake_tilemap(layer):
    if "grid" in layer:                       # 2-D int array (what the editor exports)
        g2 = layer["grid"]
        nrows = len(g2)
        cols = len(g2[0]) if nrows else 0
        grid = bytearray(cols * nrows)
        for ry, row in enumerate(g2):
            for cx in range(cols):
                grid[ry * cols + cx] = row[cx] if cx < len(row) else 0
    else:                                     # rows of chars + a legend
        legend = layer["legend"]
        rows = layer["rows"]
        cols = len(rows[0])
        nrows = len(rows)
        grid = bytearray(cols * nrows)
        for ry, row in enumerate(rows):
            for cx in range(cols):
                grid[ry * cols + cx] = legend.get(row[cx], 0) if cx < len(row) else 0
    ox, oy = layer.get("pos", [0, 0])
    return ("tilemap", layer["asset"], cols, nrows, ox, oy, bytes(grid))


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
                        x, y, ax, ay, layer.get("frame", 0), layer.get("data"), layer.get("anim")))
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
        out["zones"] = [tuple([z.get("tag")]) + (z["x"], z["y"], z["w"], z["h"]) for z in src["zones"]]
    if src.get("points"):
        out["points"] = {p["name"]: (p["x"], p["y"]) for p in src["points"] if p.get("name")}
    if src.get("music"):
        out["music"] = src["music"]


def write_module(path, name, data):
    with open(path, "w") as f:
        f.write("# AUTO-GENERATED by tools/scene_build.py\n")
        f.write(name + " = " + repr(data) + "\n")
    print("wrote", path, "(%d bytes)" % os.path.getsize(path))


def main():
    src = sys.argv[1]
    scene = json.load(open(src))
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
