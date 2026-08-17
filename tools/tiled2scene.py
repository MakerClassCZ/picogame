#!/usr/bin/env python3
"""Convert a Tiled (mapeditor.org) map into a picogame scene.json.

    python3 tools/tiled2scene.py map.tmj|map.tmx [-o scene.json] [--follow NAME] [--axis x|y|xy]

Accepts both Tiled formats: JSON (.tmj/.json) and XML (.tmx). Tilesets are COMPACTED:
the repacked strip contains only the tiles the map actually uses (real-world tilesets
often have hundreds of tiles; engine tilemap cells are one byte, so up to 253 DISTINCT
tiles per tileset may be in use).

What converts:
  tile layers   -> picogame tilemap layers (flip/rotate bits -> native tile orientations;
                   a layer that mixes tilesets is split into one tilemap layer per tileset)
  tile objects  -> sprite layers (rotation -> sprite.angle; custom properties -> data)
  rect objects  -> zones (class -> tag; custom properties -> data)
  point objects -> points (custom properties -> data)
  tilesets      -> repacked horizontal-strip PNGs written next to the output json
                   (empty tile 0 prepended - picogame convention; spacing/margin removed;
                   `transparentcolor` becomes alpha), embedded / external .tsj / .tsx
  bool tile custom properties (e.g. solid/coin/goal/hazard) -> per-tile props

What doesn't (reported, not silent): infinite maps, non-orthogonal maps, zstd-compressed
layers (fatal); per-tile animations, sub-tile collision shapes, image layers, layer
opacity/tint/parallax, polygon/ellipse/text objects, flipped tile OBJECTS (warned).

Bake the result as usual:  python3 tools/scene_build.py scene.json
"""
import argparse
import base64
import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET
import zlib

GID_H, GID_V, GID_D = 0x80000000, 0x40000000, 0x20000000
GID_MASK = 0x0FFFFFFF
# Verified Tiled(H|V<<1|D<<2) -> picogame(flipX|flipY<<1|transpose<<2) map: both sides
# cover the 8 orientations of the square, but the flip axes swap when the diagonal bit
# is set (Tiled flips AFTER its x/y swap; the engine flips source coords). Derived by
# exhaustive comparison against the sim blitter math - do not "simplify" by intuition.
ORIENT_MAP = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 5, 7: 7}

warnings = []


def warn(msg):
    warnings.append(msg)


def fatal(msg):
    sys.exit("tiled2scene: ERROR: %s" % msg)


def props_to_dict(plist):
    """Tiled properties list [{name,type,value}] -> {name: value}."""
    out = {}
    for p in plist or []:
        out[p["name"]] = p.get("value")
    return out


def _xml_props(node):
    """<properties> under an XML node -> Tiled JSON properties list."""
    plist = []
    for pr in node.findall("./properties/property"):
        typ = pr.get("type", "string")
        val = pr.get("value") if pr.get("value") is not None else (pr.text or "")
        if typ == "bool":
            val = (val == "true")
        elif typ in ("int", "object"):
            val = int(val)
        elif typ == "float":
            val = float(val)
        plist.append({"name": pr.get("name"), "type": typ, "value": val})
    return plist


# ---------------------------------------------------------------- tilesets
def _tsx_to_dict(path):
    """Parse an external .tsx (XML) tileset into the same dict shape as JSON tilesets."""
    root = ET.parse(path).getroot()
    ts = {k: int(root.get(k)) for k in
          ("tilewidth", "tileheight", "tilecount", "columns") if root.get(k)}
    ts["name"] = root.get("name") or os.path.splitext(os.path.basename(path))[0]
    for k in ("spacing", "margin"):
        if root.get(k):
            ts[k] = int(root.get(k))
    img = root.find("image")
    if img is not None:
        ts["image"] = img.get("source")
        if img.get("trans"):
            ts["transparentcolor"] = "#" + img.get("trans").lstrip("#")
    tiles = []
    for t in root.findall("tile"):
        entry = {"id": int(t.get("id"))}
        plist = _xml_props(t)
        if plist:
            entry["properties"] = plist
        if t.find("animation") is not None:
            entry["animation"] = True
        tiles.append(entry)
    if tiles:
        ts["tiles"] = tiles
    return ts


# ---------------------------------------------------------------- .tmx (XML map)
def _tmx_layer(el):
    L = {"type": "tilelayer", "name": el.get("name"),
         "width": int(el.get("width")), "height": int(el.get("height")),
         "visible": el.get("visible") != "0", "opacity": float(el.get("opacity", 1)),
         "offsetx": float(el.get("offsetx", 0)), "offsety": float(el.get("offsety", 0))}
    d = el.find("data")
    enc = d.get("encoding")
    if enc == "csv":
        L["data"] = [int(t) for t in d.text.replace("\n", ",").split(",") if t.strip()]
    elif enc == "base64":
        L["data"] = d.text.strip()
        if d.get("compression"):
            L["compression"] = d.get("compression")
    else:                                          # plain XML <tile gid=.../> children
        L["data"] = [int(t.get("gid", 0)) for t in d.findall("tile")]
    return L


def _tmx_object(el):
    o = {"id": int(el.get("id", 0)), "x": float(el.get("x", 0)), "y": float(el.get("y", 0)),
         "width": float(el.get("width", 0)), "height": float(el.get("height", 0))}
    for k in ("name", "type", "class"):
        if el.get(k):
            o["class" if k in ("type", "class") else k] = el.get(k)
    if el.get("gid"):
        o["gid"] = int(el.get("gid"))
    if el.get("rotation"):
        o["rotation"] = float(el.get("rotation"))
    for shape in ("point", "ellipse", "polygon", "polyline", "text"):
        if el.find(shape) is not None:
            o[shape] = True
    plist = _xml_props(el)
    if plist:
        o["properties"] = plist
    return o


def _tmx_layers(parent):
    out = []
    for el in parent:
        if el.tag == "layer":
            out.append(_tmx_layer(el))
        elif el.tag == "objectgroup":
            out.append({"type": "objectgroup", "name": el.get("name"),
                        "visible": el.get("visible") != "0",
                        "objects": [_tmx_object(o) for o in el.findall("object")]})
        elif el.tag == "imagelayer":
            out.append({"type": "imagelayer", "name": el.get("name")})
        elif el.tag == "group":
            out.append({"type": "group", "name": el.get("name"),
                        "visible": el.get("visible") != "0",
                        "offsetx": float(el.get("offsetx", 0)),
                        "offsety": float(el.get("offsety", 0)),
                        "layers": _tmx_layers(el)})
    return out


def _tmx_to_dict(path):
    """Parse a .tmx map into the Tiled JSON map shape."""
    root = ET.parse(path).getroot()
    m = {"type": "map", "orientation": root.get("orientation"),
         "infinite": root.get("infinite") == "1",
         "width": int(root.get("width")), "height": int(root.get("height")),
         "tilewidth": int(root.get("tilewidth")), "tileheight": int(root.get("tileheight"))}
    if root.get("backgroundcolor"):
        m["backgroundcolor"] = root.get("backgroundcolor")
    tilesets = []
    for t in root.findall("tileset"):
        if t.get("source"):
            tilesets.append({"firstgid": int(t.get("firstgid")), "source": t.get("source")})
        else:
            ts = {"firstgid": int(t.get("firstgid")), "name": t.get("name"),
                  "tilewidth": int(t.get("tilewidth")), "tileheight": int(t.get("tileheight")),
                  "tilecount": int(t.get("tilecount", 0)), "columns": int(t.get("columns", 0))}
            for k in ("spacing", "margin"):
                if t.get(k):
                    ts[k] = int(t.get(k))
            img = t.find("image")
            if img is not None:
                ts["image"] = img.get("source")
                if img.get("trans"):
                    ts["transparentcolor"] = "#" + img.get("trans").lstrip("#")
            tiles = []
            for tl in t.findall("tile"):
                entry = {"id": int(tl.get("id"))}
                plist = _xml_props(tl)
                if plist:
                    entry["properties"] = plist
                if tl.find("animation") is not None:
                    entry["animation"] = True
                tiles.append(entry)
            if tiles:
                ts["tiles"] = tiles
            tilesets.append(ts)
    m["tilesets"] = tilesets
    m["layers"] = _tmx_layers(root)
    return m


def load_tilesets(m, map_dir):
    """-> list of dicts sorted by firstgid, each with resolved image path + props."""
    out = []
    for entry in m.get("tilesets", []):
        firstgid = entry["firstgid"]
        base = map_dir
        if "source" in entry:                     # external tileset
            src = os.path.normpath(os.path.join(map_dir, entry["source"]))
            base = os.path.dirname(src)
            if src.endswith(".tsx"):
                ts = _tsx_to_dict(src)
            else:                                 # .tsj / .json
                ts = json.load(open(src))
        else:
            ts = entry
        if "image" not in ts:
            fatal("tileset %r: image-collection tilesets (no single image) are not supported"
                  % ts.get("name", "?"))
        name = "".join(c if c.isalnum() else "_" for c in (ts.get("name") or "tiles")).lower()
        props, anims = {}, 0
        for t in ts.get("tiles", []):
            flags = {}
            for k, v in props_to_dict(t.get("properties")).items():
                if isinstance(v, bool):
                    if v:
                        flags[k] = True
                else:
                    warn("tileset %r tile %d: non-bool property %r ignored (tile props are flags)"
                         % (name, t["id"], k))
            if flags:
                props[t["id"]] = flags            # keyed by RAW local id; remapped later
            if t.get("animation"):
                anims += 1
        if anims:
            warn("tileset %r: %d animated tile(s) - tile animation is not supported, static tile used"
                 % (name, anims))
        out.append({
            "firstgid": firstgid, "name": name,
            "tw": ts["tilewidth"], "th": ts["tileheight"],
            "count": ts["tilecount"], "columns": ts.get("columns") or 1,
            "spacing": ts.get("spacing", 0), "margin": ts.get("margin", 0),
            "image": os.path.normpath(os.path.join(base, ts["image"])),
            "transparent": ts.get("transparentcolor"),
            "props": props,
        })
    out.sort(key=lambda t: t["firstgid"])
    if not out:
        fatal("map has no tilesets")
    return out


def repack_tileset(ts, used, out_dir, stem):
    """Write a horizontal-strip PNG holding ONLY the used tiles, in remap order
    (empty tile 0 first, spacing/margin removed, transparentcolor -> alpha).
    Returns (png_basename, frames)."""
    from PIL import Image
    im = Image.open(ts["image"]).convert("RGBA")
    if ts["transparent"]:
        h = ts["transparent"].lstrip("#")
        key = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                p = px[x, y]
                if p[:3] == key:
                    px[x, y] = (0, 0, 0, 0)
    tw, th = ts["tw"], ts["th"]
    strip = Image.new("RGBA", (tw * (len(used) + 1), th), (0, 0, 0, 0))
    for slot, tid in enumerate(used):
        sx = ts["margin"] + (tid % ts["columns"]) * (tw + ts["spacing"])
        sy = ts["margin"] + (tid // ts["columns"]) * (th + ts["spacing"])
        strip.paste(im.crop((sx, sy, sx + tw, sy + th)), ((slot + 1) * tw, 0))
    png = "%s_%s.png" % (stem, ts["name"])
    strip.save(os.path.join(out_dir, png))
    return png, len(used) + 1


def find_tileset(tilesets, gid):
    hit = None
    for ts in tilesets:
        if ts["firstgid"] <= gid:
            hit = ts
        else:
            break
    return hit


# ---------------------------------------------------------------- layers
def decode_data(layer):
    data = layer.get("data")
    if isinstance(data, list):
        return data
    comp = layer.get("compression") or ""
    if comp == "zstd":
        fatal("layer %r: zstd compression is not supported - re-export with zlib/gzip/CSV"
              % layer.get("name"))
    raw = base64.b64decode(data)
    if comp == "zlib":
        raw = zlib.decompress(raw)
    elif comp == "gzip":
        raw = gzip.decompress(raw)
    return [int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4)]


def convert_tilelayer(layer, tilesets, off, out_layers):
    name = layer.get("name") or "layer"
    if layer.get("opacity", 1) != 1:
        warn("layer %r: opacity ignored (engine has no per-layer alpha)" % name)
    if layer.get("tintcolor"):
        warn("layer %r: tintcolor ignored" % name)
    if layer.get("parallaxx", 1) != 1 or layer.get("parallaxy", 1) != 1:
        warn("layer %r: parallax factor ignored (engine layers scroll with the camera)" % name)
    w, h = layer["width"], layer["height"]
    data = decode_data(layer)
    per_ts = {}                                   # tileset name -> grid rows
    flips = 0
    for i, gid in enumerate(data):
        if gid == 0:
            continue
        bits = ((1 if gid & GID_H else 0) | (2 if gid & GID_V else 0)
                | (4 if gid & GID_D else 0))
        clean = gid & GID_MASK
        ts = find_tileset(tilesets, clean)
        if ts is None or clean - ts["firstgid"] >= ts["count"]:
            warn("layer %r cell %d: gid %d matches no tileset tile - left empty" % (name, i, clean))
            continue
        local = clean - ts["firstgid"]
        if ts["name"] not in per_ts:
            per_ts[ts["name"]] = [[0] * w for _ in range(h)]
        v = ts["remap"][local]
        if bits:
            v |= ORIENT_MAP[bits] << 8
            flips += 1
        per_ts[ts["name"]][i // w][i % w] = v
    if len(per_ts) > 1:
        warn("layer %r uses %d tilesets - split into %d stacked tilemap layers"
             % (name, len(per_ts), len(per_ts)))
    pos = [round(layer.get("offsetx", 0) + off[0]), round(layer.get("offsety", 0) + off[1])]
    for tsname in [t["name"] for t in tilesets if t["name"] in per_ts]:
        out_layers.append({"kind": "tilemap", "asset": tsname, "pos": list(pos),
                           "grid": per_ts[tsname]})
    return flips


def convert_objectgroup(layer, tilesets, off, out_layers, zones, points):
    for o in layer.get("objects", []):
        data = props_to_dict(o.get("properties"))
        name = o.get("name") or None
        x = o["x"] + off[0]
        y = o["y"] + off[1]
        if o.get("gid"):
            gid = o["gid"]
            if gid & (GID_H | GID_V | GID_D):
                warn("object %r: flipped tile object - flip bits dropped (sprites carry "
                     "rotation via `angle`, not flips)" % (name or o.get("id")))
            clean = gid & GID_MASK
            ts = find_tileset(tilesets, clean)
            if ts is None or clean - ts["firstgid"] >= ts["count"]:
                warn("object %r: gid %d matches no tileset tile - skipped" % (name or o.get("id"), clean))
                continue
            spr = {"kind": "sprite", "asset": ts["name"],
                   "pos": [round(x), round(y)], "anchor": [0, 1],   # Tiled tile objects anchor bottom-left
                   "frame": ts["remap"][clean - ts["firstgid"]]}
            if name:
                spr["name"] = name
            if o.get("rotation"):
                spr["angle"] = round(o["rotation"]) % 360
            if data:
                spr["data"] = data
            out_layers.append(spr)
        elif o.get("point"):
            if not name:
                warn("point object #%s has no name - skipped (points are looked up by name)" % o.get("id"))
                continue
            pt = {"name": name, "x": round(x), "y": round(y)}
            if data:
                pt["data"] = data
            points.append(pt)
        elif o.get("ellipse") or o.get("polygon") or o.get("polyline") or o.get("text"):
            shape = ("ellipse" if o.get("ellipse") else
                     "polygon" if o.get("polygon") else
                     "polyline" if o.get("polyline") else "text")
            warn("object %r: %s objects are not supported - skipped (zones are rectangles)"
                 % (name or o.get("id"), shape))
        else:
            z = {"x": round(x), "y": round(y), "w": round(o.get("width", 0)),
                 "h": round(o.get("height", 0))}
            tag = o.get("class") or o.get("type") or name
            if tag:
                z["tag"] = tag
            if data:
                z["data"] = data
            zones.append(z)


def hexcolor(c, default):
    if not c:
        return default
    h = c.lstrip("#")
    if len(h) == 8:                               # #AARRGGBB
        h = h[2:]
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def main():
    ap = argparse.ArgumentParser(description="Tiled JSON map -> picogame scene.json")
    ap.add_argument("map", help="Tiled map (.tmj / .json)")
    ap.add_argument("-o", "--out", help="output scene.json (default: <map>_scene.json)")
    ap.add_argument("--follow", metavar="NAME",
                    help="emit a follow-camera targeting the sprite object NAME")
    ap.add_argument("--axis", default="x", choices=["x", "y", "xy"],
                    help="camera axis for --follow (default x)")
    args = ap.parse_args()

    if args.map.endswith(".tmx"):
        m = _tmx_to_dict(args.map)
    else:
        m = json.load(open(args.map))
    if m.get("orientation") != "orthogonal":
        fatal("only orthogonal maps convert (map is %r)" % m.get("orientation"))
    if m.get("infinite"):
        fatal("infinite maps are not supported - set a fixed map size in Tiled")

    map_dir = os.path.dirname(os.path.abspath(args.map))
    out_path = args.out or os.path.join(
        map_dir, os.path.splitext(os.path.basename(args.map))[0] + "_scene.json")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    stem = os.path.splitext(os.path.basename(out_path))[0].replace("_scene", "") or "tiles"

    tilesets = load_tilesets(m, map_dir)

    # Pass 1 - which tiles does the map actually USE? (tile layers + tile objects).
    # The repacked strip holds only those (compaction): big real-world tilesets fit the
    # one-byte tilemap cells as long as <= 253 DISTINCT tiles of one tileset are in use.
    used = {}                                     # tileset name -> set of local ids

    def collect(layers):
        for layer in layers:
            if not layer.get("visible", True):
                continue
            t = layer.get("type")
            if t == "group":
                collect(layer.get("layers", []))
            elif t == "tilelayer":
                for gid in decode_data(layer):
                    if gid:
                        ts = find_tileset(tilesets, gid & GID_MASK)
                        if ts and (gid & GID_MASK) - ts["firstgid"] < ts["count"]:
                            used.setdefault(ts["name"], set()).add((gid & GID_MASK) - ts["firstgid"])
            elif t == "objectgroup":
                for o in layer.get("objects", []):
                    if o.get("gid"):
                        ts = find_tileset(tilesets, o["gid"] & GID_MASK)
                        if ts and (o["gid"] & GID_MASK) - ts["firstgid"] < ts["count"]:
                            used.setdefault(ts["name"], set()).add((o["gid"] & GID_MASK) - ts["firstgid"])

    collect(m.get("layers", []))

    assets = {}
    for ts in tilesets:
        u = sorted(used.get(ts["name"], ()))
        if not u:
            warn("tileset %r: no tile of it is used - skipped" % ts["name"])
            ts["remap"] = {}
            continue
        if len(u) > 253:
            fatal("tileset %r: %d distinct tiles in use - engine tilemap cells are one byte "
                  "(max 253 per tileset)" % (ts["name"], len(u)))
        ts["remap"] = {tid: slot + 1 for slot, tid in enumerate(u)}
        if len(u) < ts["count"]:
            ts["compacted"] = True
        png, frames = repack_tileset(ts, u, out_dir, stem)
        a = {"type": "tileset", "src": png, "frames": frames, "tile": [ts["tw"], ts["th"]]}
        props = {str(ts["remap"][tid]): f for tid, f in ts["props"].items() if tid in ts["remap"]}
        if props:
            a["props"] = props
        assets[ts["name"]] = a

    out_layers, zones, points = [], [], []
    flips = 0

    def walk(layers, off):
        nonlocal flips
        for layer in layers:
            if not layer.get("visible", True):
                warn("layer %r: hidden - skipped" % layer.get("name"))
                continue
            t = layer.get("type")
            if t == "group":
                walk(layer.get("layers", []),
                     (off[0] + layer.get("offsetx", 0), off[1] + layer.get("offsety", 0)))
            elif t == "tilelayer":
                flips += convert_tilelayer(layer, tilesets, off, out_layers)
            elif t == "objectgroup":
                convert_objectgroup(layer, tilesets, off, out_layers, zones, points)
            elif t == "imagelayer":
                warn("layer %r: image layers are not supported - skipped" % layer.get("name"))
            else:
                warn("layer %r: unknown type %r - skipped" % (layer.get("name"), t))

    walk(m.get("layers", []), (0, 0))

    size = [m["width"] * m["tilewidth"], m["height"] * m["tileheight"]]
    scene = {"format": "picogame-scene", "version": 1, "size": size,
             "background": hexcolor(m.get("backgroundcolor"), [0, 0, 0]),
             "assets": assets, "layers": out_layers}
    if zones:
        scene["zones"] = zones
    if points:
        scene["points"] = points
    sprite_names = [L.get("name") for L in out_layers if L["kind"] == "sprite" and L.get("name")]
    if args.follow:
        if args.follow not in sprite_names:
            fatal("--follow %r: no sprite object with that name (have: %s)"
                  % (args.follow, ", ".join(sprite_names) or "none"))
        scene["camera"] = {"mode": "follow", "target": args.follow, "axis": args.axis,
                           "bounds": [0, 0, size[0], size[1]]}

    json.dump(scene, open(out_path, "w"), indent=1)
    tm = sum(1 for L in out_layers if L["kind"] == "tilemap")
    sp = sum(1 for L in out_layers if L["kind"] == "sprite")
    print("tiled2scene: %s -> %s" % (os.path.basename(args.map), os.path.basename(out_path)))
    print("  world %dx%d px, %d tilemap layer(s), %d sprite(s), %d zone(s), %d point(s), "
          "%d oriented tile(s)" % (size[0], size[1], tm, sp, len(zones), len(points), flips))
    for ts in tilesets:
        if ts["name"] not in assets:
            continue
        n = assets[ts["name"]]["frames"] - 1
        note = " (compacted from %d)" % ts["count"] if ts.get("compacted") else ""
        kb = assets[ts["name"]]["frames"] * ts["tw"] * ts["th"] / 1024.0
        print("  tileset %r -> %s (%d used tile(s) + empty 0%s) ~%.1f KB PAL8 on device"
              % (ts["name"], assets[ts["name"]]["src"], n, note, kb))
        if kb > 20:
            print("  NOTE: a large tileset for a small MCU (RP2040 heap ~138 KB total)."
                  " Fewer distinct tiles = less RAM; the strip holds only what the map uses.")
    if "camera" not in scene and "player" in sprite_names:
        print("  hint: object 'player' found - add a scrolling camera with: --follow player")
    for w in warnings:
        print("  WARNING: " + w)
    print("  bake it:  python3 tools/scene_build.py " + os.path.basename(out_path))


if __name__ == "__main__":
    main()
