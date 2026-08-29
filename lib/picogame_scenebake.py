# picogame_scenebake - bake an editor scene JSON into the runtime SCENE dict ON THE DEVICE.
#
# The normal pipeline bakes ahead of time: tools/scene_build.py (CPython + PIL) turns a level's
# scene.json into a <name>_scene.py module you import. This module does the same job at runtime with
# no PIL and no files, so you can edit a level's JSON and just re-run it - no conversion step in the
# loop. Handy while ITERATING; ship the pre-baked module when you are done.
#
#   view = picogame_scene.load_json(pg, "level.json")     # <- use this, it scopes the intermediates
#
# Or drive it yourself, MINDING THE SHAPE (measured, RP2040-class heap):
#
#   def build():                                   # a FUNCTION, so the text and the parse tree are
#       import json, picogame_scenebake as sb      # locals that die on return
#       return sb.bake(json.loads(open("level.json").read()))
#   SCENE = build()
#
# Cost on a 1200-cell level, 32-bit MicroPython: ~17 kB PEAK (parse tree + SCENE alive at once) and
# +336 B steady state vs importing the pre-baked module - so the price is a startup SPIKE, not a
# standing tax. Bake EARLY, while the heap is still one contiguous block: the GC does not move
# objects, so a late spike leaves holes exactly where the render strip buffers want to go. This
# module itself costs ~3.6 kB while imported; after the last level, reclaim it with
#   import sys; del sys.modules["picogame_scenebake"]
#
# COLOUR ASSETS ONLY (tileset_color, rect, and PAL8 the editor already inlined). A PNG-backed asset
# needs median-cut quantization, which belongs on a desktop - those raise NotImplementedError, so
# bake those levels with tools/scene_build.py. Byte-identical to that CLI for everything it does
# accept; tests/test_scenebake.py compares the two so they cannot drift.

def _w565(rgb):
    # WIRE-order rgb565 (SPI byte order) -- byte-identical to scene_build.py's w565. The playground
    # now runs the NATIVE C ENGINE, whose whole pipeline is wire-order (pg.rgb565(255,0,0)=0x00F8;
    # the engine itself byte-swaps finished regions for the native_rgb565 framebuffer the canvas
    # blits), same as the device/sim. picogame_scene.load
    # writes this baked palette straight into the native framebuffer, so it MUST be wire-order too --
    # otherwise every scene colour comes out byte-swapped (authored brown -> light blue). Every colour
    # the baker emits (tileset_color palettes, background, rect colours, hudlabel colours) goes through
    # here, so this one change fixes them all. (The old NATIVE variant compensated for the retired
    # pure-Python browser shim, which no longer exists.)
    r, g, b = rgb
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


def _bake_asset(a):
    """-> (fmt, hexdata, w, h, frames, transparent_or_None, palette_tuple). Colour assets only."""
    t = a["type"]
    if t == "pal8_inline":
        # An atlas the EDITOR already quantized (Canvas -> PAL8) and inlined: base64 index bytes +
        # wire-order palette. Pure passthrough into the loader's asset tuple - the browser's PNG path.
        import binascii
        fw, fh = a.get("tile") or a.get("frame") or [a["width"], a["height"]]
        raw = binascii.a2b_base64(a["data"].encode())     # MicroPython wants bytes here
        return ("pal8", binascii.hexlify(raw).decode(), fw, fh, a.get("frames", 1), 0,
                tuple(a["palette"]))
    if t in ("sprite", "bitmap", "tileset"):
        raise NotImplementedError("Try-it supports colour-tileset levels for now (image sprites coming)")
    if t == "rect":
        w, h = a["size"]
        data = bytes([1]) * (w * h)
        pal = (_w565((0, 0, 0)), _w565(a["color"]))
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
        pal = [_w565((0, 0, 0))]
        for v in range(1, frames):                 # sparse colour maps are legal: gaps -> magenta
            pal.append(_w565(colors.get(str(v), (255, 0, 255))))
        return ("pal8", bytes(data).hex(), tw, th, frames, 0, tuple(pal))
    raise ValueError("unknown asset type: " + t)


def _tile_props(a):
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


def _bake_assets(assets):
    a_out, tp_out, an_out = {}, {}, {}
    for aid, a in assets.items():
        a_out[aid] = _bake_asset(a)
        tp = _tile_props(a)
        if tp:
            tp_out[aid] = tp
        if "animations" in a:
            an_out[aid] = {nm: (tuple(d["frames"]), d.get("fps", 8), d.get("loop", True))
                           for nm, d in a["animations"].items()}
    return a_out, tp_out, an_out


def _bake_tilemap(layer):
    g2 = layer["grid"]                            # 2-D int array (what the editor exports)
    nrows = len(g2)
    cols = len(g2[0]) if nrows else 0
    grid = bytearray(cols * nrows)
    orient = None                                 # bits 8-10 of a value = native tile orientation
    for ry, row in enumerate(g2):
        for cx in range(cols):
            v = row[cx] if cx < len(row) else 0
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


def _bake_layers(layers_json):
    out = []
    for layer in layers_json:
        k = layer["kind"]
        if k == "tilemap":
            out.append(_bake_tilemap(layer))
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
                        _w565(layer.get("fg", [255, 255, 255])), _w565(layer.get("bg", [0, 0, 0]))))
        elif k == "particles":
            out.append(("particles", layer.get("name"), layer.get("capacity", 64),
                        layer.get("size", 1), layer.get("gravity", 0.0), layer.get("fade", False)))
        else:
            raise ValueError("unknown layer kind: " + k)
    return out


def _bake_camera(cam, size):
    if not cam:
        return None
    b = cam.get("bounds", [0, 0, size[0], size[1]])
    return (cam.get("mode", "follow"), cam.get("target"), cam.get("axis", "x"),
            b[0], b[1], b[2], b[3])


def _add_extras(out, src):
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


def bake(scene):
    """Bake ONE standalone editor scene (exportScene output) into the runtime SCENE dict.
    Raises NotImplementedError for PNG-backed assets. Mirrors scene_build.py's single-scene path."""
    size = scene.get("size", [320, 240])
    a, tp, an = _bake_assets(scene["assets"])
    out = {"bg": _w565(scene.get("background", [0, 0, 0])), "assets": a,
           "tileprops": tp, "anims": an, "layers": _bake_layers(scene["layers"]),
           "camera": _bake_camera(scene.get("camera"), size)}
    if out["camera"] is None:
        del out["camera"]
    _add_extras(out, scene)
    return out
