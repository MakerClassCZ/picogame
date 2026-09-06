# picogame_scenebake - bake authoring JSON (a game.json project or a standalone scene) into the
# runtime BANK / LEVEL / SCENE structures ON THE DEVICE, with no PIL and no host step.
#
# Two shapes come in:
#   game.json (format "picogame-project", version 2): {name, size, start, assets, sounds, levels[]}
#       -> bake_bank(assets, sounds, base)  = the shared BANK (bitmaps, tile props, anims, sounds)
#       -> bake_level(level, size, assets)  = one LEVEL (layers, camera, zones, points, effects)
#   a standalone scene (the old scene.json / a handoff level, assets inline)
#       -> bake(scene)                      = the old SCENE dict (bank + level in one)
#
# picogame_scene.Game drives this: it streams game.json level by level (CircuitPython's json.load
# returns the first complete value, see walk()), bakes each level to a small tuple and drops the
# parse tree, then releases this module. Bake EARLY, while the heap is one contiguous block: the GC
# does not move objects, so a late spike leaves holes where the strip buffers want to go. Measured
# on an RP2040: 42-58 ms and ~4.5 kB resident per level, 3.1 kB for this module while imported.
#
# PIXELS never live in JSON. A PNG-backed asset ("src": "hero.png") is served from a sidecar
# hero.pal8 next to the JSON (written by the editor's Save or by scene_build.py art); this module
# only records the path - picogame_scene reads the file straight into the Bitmap. Colour assets
# (tileset_color, rect) are generated here. tools/scene_build.py is a thin CLI over this module,
# so host and device bake byte-identically; tests/test_scenebake.py holds the goldens.

import struct


def _w565(rgb):
    # WIRE-order rgb565 (SPI byte order) - what the native engine, the framebuffer and the
    # simulator all expect; every colour the baker emits goes through here.
    r, g, b = rgb
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c >> 8) | (c << 8)) & 0xFFFF


# ------------------------------------------------------------------------- .pal8 sidecars
# Little-endian header, 16 bytes: "PAL8", version u8 (1), flags u8 (bit0: index 0 is transparent),
# fw u16, fh u16, frames u16, ncol u16, reserved u16; then ncol x u16 wire-RGB565 palette; then
# fw*frames*fh index bytes (stride fw*frames). Self-describing so the same file serves any game.
PAL8_MAGIC = b"PAL8"
PAL8_HDR = "<4sBBHHHHH"
PAL8_HDR_LEN = 16


def encode_pal8(data, fw, fh, frames, palette, transparent):
    """-> bytes of a complete .pal8 file (data = index bytes, stride fw*frames)."""
    if len(data) != fw * frames * fh:
        raise ValueError("pal8 data is %d bytes, expected %d" % (len(data), fw * frames * fh))
    flags = 1 if transparent == 0 else 0
    hdr = struct.pack(PAL8_HDR, PAL8_MAGIC, 1, flags, fw, fh, frames, len(palette), 0)
    pal = struct.pack("<%dH" % len(palette), *palette)
    return hdr + pal + bytes(data)


def _sidecar(src):
    """hero.png -> hero.pal8 (same folder, extension swapped)."""
    dot = src.rfind(".")
    stem = src[:dot] if dot > src.rfind("/") else src
    return stem + ".pal8"


def _bake_asset(a, base=None):
    """-> (fmt, data, w, h, frames, transparent_or_None, palette_tuple).
    fmt 'pal8': data = index bytes (or a hex str in older baked modules; the loader takes both).
    fmt 'pal8f': data = path of a .pal8 sidecar the loader reads itself; palette None."""
    t = a["type"]
    if t == "pal8_inline":
        # An atlas the editor already quantized (Canvas -> PAL8) and inlined as base64 - the
        # playground handoff shape. Decoded straight to bytes: no hex round trip.
        import binascii
        fw, fh = a.get("tile") or a.get("frame") or [a["width"], a["height"]]
        raw = binascii.a2b_base64(a["data"].encode())
        return ("pal8", raw, fw, fh, a.get("frames", 1), 0, tuple(a["palette"]))
    if t in ("sprite", "bitmap", "tileset"):
        fw, fh = a.get("frame") or a.get("tile") or a["size"]
        if not a.get("src"):
            raise ValueError("asset of type %s has no src (and no sidecar)" % t)
        path = _sidecar(a["src"])
        if base:
            path = base.rstrip("/") + "/" + path
        return ("pal8f", path, fw, fh, a.get("frames", 1), a.get("transparent", 0), None)
    if t == "rect":
        w, h = a["size"]
        data = bytes([1]) * (w * h)
        pal = (_w565((0, 0, 0)), _w565(a["color"]))
        return ("pal8", data, w, h, 1, None, pal)
    if t == "tileset_color":
        tw, th = a["tile"]
        colors = a["colors"]
        n = max(int(k) for k in colors)            # tile values 1..n; 0 = empty
        frames = n + 1
        stride = tw * frames
        data = bytearray(stride * th)
        for f in range(1, frames):                 # frame f filled with index f
            for y in range(th):
                base_i = y * stride + f * tw
                for x in range(tw):
                    data[base_i + x] = f
        pal = [_w565((0, 0, 0))]
        for v in range(1, frames):                 # sparse colour maps are legal: gaps -> magenta
            pal.append(_w565(colors.get(str(v), (255, 0, 255))))
        return ("pal8", bytes(data), tw, th, frames, 0, tuple(pal))
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


def _bake_assets(assets, base=None):
    a_out, tp_out, an_out = {}, {}, {}
    for aid, a in assets.items():
        a_out[aid] = _bake_asset(a, base)
        tp = _tile_props(a)
        if tp:
            tp_out[aid] = tp
        if "animations" in a:
            an_out[aid] = {nm: (tuple(d["frames"]), d.get("fps", 8), d.get("loop", True))
                           for nm, d in a["animations"].items()}
    return a_out, tp_out, an_out


def bake_sounds(sounds, base=None):
    """{id:{src}} | {id:src} -> {id: path} (wavs stay wav; loaded at runtime)."""
    if not sounds:
        return None
    out = {}
    for k, v in sounds.items():
        p = v["src"] if isinstance(v, dict) else v
        out[k] = (base.rstrip("/") + "/" + p) if base else p
    return out


def bake_bank(assets, sounds=None, base=None):
    """The shared BANK of a project: assets + tile props + anims (+ sounds)."""
    a, tp, an = _bake_assets(assets, base)
    bank = {"assets": a, "tileprops": tp, "anims": an}
    snd = bake_sounds(sounds, base)
    if snd:
        bank["sounds"] = snd
    return bank


def _bake_tilemap(layer, assets=None):
    orient = None                                 # bits 8-10 of a value = native tile orientation
    if "grid" in layer:                           # 2-D int array (the old editor export)
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
    else:                                         # rows of chars + a legend (the ASCII form)
        # The legend lives in the ASSET (game.json v2); a layer-level legend is the v1 form and
        # wins when present. Same cell semantics as the grid, so both forms bake identically.
        legend = layer.get("legend")
        if legend is None and assets is not None:
            legend = assets.get(layer["asset"], {}).get("legend")
        legend = legend or {}
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


def _bake_layers(layers_json, assets=None):
    out = []
    for layer in layers_json:
        k = layer["kind"]
        if k == "tilemap":
            out.append(_bake_tilemap(layer, assets))
        elif k == "sprite":
            ax, ay = layer.get("anchor", [0, 0])
            x, y = layer["pos"]
            t = ("sprite", layer["asset"], layer.get("name"),
                 x, y, ax, ay, layer.get("frame", 0), layer.get("data"), layer.get("anim"),
                 layer.get("angle", 0))
            if layer.get("tag"):                  # a tagged single sprite joins groups[tag] too
                t += (layer["tag"],)
            out.append(t)
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
    if src.get("effects"):
        out["effects"] = src["effects"]           # plain data; picogame_story applies the rules
    if src.get("worldSize"):
        out["world"] = tuple(src["worldSize"])


def bake_level(level, size, assets=None):
    """One LEVEL of a project (no assets of its own: those come from the bank)."""
    out = {"bg": _w565(level.get("background", [0, 0, 0])),
           "layers": _bake_layers(level["layers"], assets),
           "camera": _bake_camera(level.get("camera"), size)}
    if out["camera"] is None:
        del out["camera"]
    _add_extras(out, level)
    return out


def bake(scene, base=None):
    """Bake ONE standalone scene (assets inline) into the old SCENE dict: bank and level in one.
    Kept for scene.json v1 files, handoff levels and the existing goldens."""
    size = scene.get("size", [320, 240])
    a, tp, an = _bake_assets(scene["assets"], base)
    out = {"bg": _w565(scene.get("background", [0, 0, 0])), "assets": a,
           "tileprops": tp, "anims": an, "layers": _bake_layers(scene["layers"], scene["assets"]),
           "camera": _bake_camera(scene.get("camera"), size)}
    if out["camera"] is None:
        del out["camera"]
    snd = bake_sounds(scene.get("sounds"), base)
    if snd:
        out["sounds"] = snd
    _add_extras(out, scene)
    return out


# ------------------------------------------------------------------------- streaming walker
# CircuitPython's json.load(f) returns the FIRST complete JSON value in the stream and reads with
# exactly one byte of lookahead, so after it returns f is positioned one byte past the value and
# seek(-1, 1) hands that byte back. That lets us read game.json one top-level value at a time and
# one level at a time - peak RAM is one level's tree, not the whole file. On CPython/the simulator
# json.load would swallow the file, so _load_first() falls back to raw_decode on the remaining
# text; the walker itself is the same code on both.

_WS = b" \t\r\n"


def _is_cp():
    import sys
    return sys.implementation.name == "circuitpython"


def _load_first(f):
    """json.load the next value from f, leaving f exactly ONE byte past its end (CP semantics)."""
    import json
    if _is_cp():
        return json.load(f)
    start = f.tell()
    text = f.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    i = 0
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if hasattr(json, "JSONDecoder"):              # CPython: the stdlib knows where a value ends
        val, end = json.JSONDecoder().raw_decode(text, i)
    else:                                         # MicroPython (playground/sim): scan the value
        end = _value_end(text, i)
        val = json.loads(text[i:end])
    used = len(text[:end].encode("utf-8"))
    f.seek(start + used + 1)                      # +1 = the lookahead byte CP would have eaten
    return val


def _value_end(text, i):
    """Index just past the JSON value starting at text[i] (string-aware, no allocation of a tree)."""
    c = text[i]
    if c in "{[":
        depth = 0
        instr = False
        esc = False
        j = i
        while j < len(text):
            ch = text[j]
            if instr:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    instr = False
            elif ch == '"':
                instr = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return j + 1
            j += 1
        raise ValueError("unterminated JSON value")
    if c == '"':
        j = i + 1
        while j < len(text):
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == '"':
                return j + 1
            j += 1
        raise ValueError("unterminated JSON string")
    j = i
    while j < len(text) and text[j] not in ",]} \t\r\n":
        j += 1
    return j


def _ws(f):
    while True:
        c = f.read(1)
        if not c or c not in _WS:
            return c


def _key(f):
    k = bytearray()
    while True:
        c = f.read(1)
        if not c:
            raise ValueError("unterminated key")
        if c == b"\\":
            k.extend(c + f.read(1))
            continue
        if c == b'"':
            return bytes(k).decode("utf-8")
        k.extend(c)


def _value(f):
    f.seek(-1, 1)
    v = _load_first(f)
    f.seek(-1, 1)
    return v


def walk(f, on_level=None, stop_after=None, top=None):
    """Read the top-level object of a game.json from a binary file.

    Every value except `levels` is loaded whole (they are small) into `top` (a dict you may pass
    in, so a level callback can already see the keys read so far); `levels` is streamed element
    by element into on_level(level_dict, index). stop_after = a set of keys: return as soon as all
    of them are known (the launcher reads name/icon and stops). Key order is free; canonical
    files put the small keys first and `levels` last."""
    if top is None:
        top = {}
    f.seek(0)
    if f.read(3) == b"\xef\xbb\xbf":            # UTF-8 BOM from some editors
        pass
    else:
        f.seek(0)
    if _ws(f) != b"{":
        raise ValueError("game.json: not a JSON object")
    while True:
        c = _ws(f)
        if not c or c == b"}":
            break
        if c == b",":
            continue
        if c != b'"':
            raise ValueError("game.json: expected a key at byte %d" % (f.tell() - 1))
        key = _key(f)
        if _ws(f) != b":":
            raise ValueError("game.json: expected ':' after %r" % key)
        if key == "levels":
            if _ws(f) != b"[":
                raise ValueError("game.json: levels must be an array")
            i = 0
            while True:
                c = _ws(f)
                if not c or c == b"]":
                    break
                if c == b",":
                    continue
                pos = f.tell() - 1
                try:
                    lv = _value(f)
                except ValueError as e:
                    raise ValueError("game.json: level %d (byte %d): %s" % (i, pos, e))
                if on_level is not None:
                    on_level(lv, i, pos)
                lv = None
                i += 1
            top["_levels"] = i
        else:
            if not _ws(f):
                raise ValueError("game.json: missing value for %r" % key)
            top[key] = _value(f)
        if stop_after and stop_after <= set(top):
            return top
    return top


def level_at(f, pos, size, assets):
    """Bake the ONE level whose object starts at byte `pos` (an offset walk() reported) - the
    lazy path: no other level is parsed."""
    f.seek(pos)
    lv = _load_first(f)
    return bake_level(lv, size, assets)


def head(path, want=("name", "icon")):
    """The small top-level values of a game.json without touching the levels - for launchers.
    3 ms per file on a Fruit Jam when the keys come first (they do in canonical files)."""
    with open(path, "rb") as f:
        return walk(f, None, set(want))
