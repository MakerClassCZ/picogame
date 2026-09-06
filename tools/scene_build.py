#!/usr/bin/env python3
"""scene_build.py - the host side of picogame's data pipeline (a thin CLI over picogame_scenebake).

    scene_build.py check   [game.json]        validate: dangling ids, legend/rows, zones, effects, story refs
    scene_build.py fmt     [game.json]        rewrite in the canonical form (key order, one map row per line)
    scene_build.py art     [game.json]        PNG assets -> <name>.pal8 sidecars next to the JSON
    scene_build.py build   [game.json] [--mpy] [--out build]
                                              bank + level modules (+ story.mpy, code.py) for shipping
    scene_build.py migrate <old.scene.json | project.json | .pgproj.json> [-o game.json]
    scene_build.py watch   [game.json] [--build]   re-run check+art (+build) whenever a source changes
    scene_build.py <file.scene.json | project.json>   (legacy) bake to <stem>_scene.py / _bank.py + _level.py

The device bakes the very same game.json with the very same module (picogame_scenebake), so what
this writes and what the board bakes at boot are one implementation, not two. Only PNG -> PAL8
quantization (PIL) and .mpy compilation are host-only.
"""

import json
import os
import sys

# picogame_scenebake is the ONE baker. Find it next to this tool (a picogame checkout keeps the
# libs in lib/), in the libs repo of the dev workspace, or on the path.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_HERE, "..", "lib"),
              os.path.join(_HERE, "..", "..", "picogame-libs"),
              os.path.join(_HERE, "..", "..", "..", "repos", "picogame-libs")):
    if os.path.exists(os.path.join(_cand, "picogame_scenebake.py")):
        sys.path.insert(0, os.path.abspath(_cand))
        break
import picogame_scenebake as sb  # noqa: E402

w565 = sb._w565
IMG_TYPES = ("sprite", "bitmap", "tileset")


# ---------------------------------------------------------------------- PNG -> PAL8 (host only)
def quantize_png(path, fw, fh, frames):
    """-> (index bytes with stride fw*frames, wire-RGB565 palette list). Palette = the distinct
    opaque colours in FIRST-SEEN order scanning the fw*frames x fh strip row by row (the editor's
    in-browser baker scans the same way, so both write byte-identical .pal8 files). Index 0 is
    transparent (alpha < 128). More than 255 colours or a soft alpha is an ERROR: pixel art has
    neither, and two quantizers can never agree - run tools/png2picogame.py once instead."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    sw, sh = fw * frames, fh
    if im.width < sw or im.height < sh:
        raise SystemExit("%s: image is %dx%d, needs at least %dx%d for %d frames of %dx%d"
                         % (path, im.width, im.height, sw, sh, frames, fw, fh))
    px = im.crop((0, 0, sw, sh)).load()
    data = bytearray(sw * sh)
    seen = {}
    palette = [w565((0, 0, 0))]
    for y in range(sh):
        for x in range(sw):
            r, g, b, a = px[x, y]
            if a < 128:
                if a != 0:
                    raise SystemExit("%s: soft alpha at (%d,%d) - picogame art is hard-edged; "
                                     "flatten the alpha or run tools/png2picogame.py" % (path, x, y))
                continue
            if a != 255:
                raise SystemExit("%s: soft alpha at (%d,%d) - picogame art is hard-edged; "
                                 "flatten the alpha or run tools/png2picogame.py" % (path, x, y))
            c = (r, g, b)
            i = seen.get(c)
            if i is None:
                if len(palette) > 255:
                    raise SystemExit("%s: more than 255 colours - quantize it once with "
                                     "tools/png2picogame.py" % path)
                i = seen[c] = len(palette)
                palette.append(w565(c))
            data[y * sw + x] = i
    return bytes(data), palette


def png_assets(project):
    for aid, a in project.get("assets", {}).items():
        if a.get("type") in IMG_TYPES and a.get("src"):
            yield aid, a


def asset_geometry(a):
    fw, fh = a.get("frame") or a.get("tile") or a["size"]
    return fw, fh, a.get("frames", 1)


def art(project, base, verbose=True):
    """Write <stem>.pal8 for every PNG asset (only when the bytes changed). -> written paths."""
    out = []
    for aid, a in png_assets(project):
        fw, fh, frames = asset_geometry(a)
        src = os.path.join(base, a["src"])
        if not os.path.exists(src):
            raise SystemExit("assets[%r]: %s not found next to game.json" % (aid, a["src"]))
        data, palette = quantize_png(src, fw, fh, frames)
        blob = sb.encode_pal8(data, fw, fh, frames, palette, 0)
        dst = os.path.join(base, sb._sidecar(a["src"]))
        old = open(dst, "rb").read() if os.path.exists(dst) else None
        if old != blob:
            with open(dst, "wb") as f:
                f.write(blob)
            out.append(dst)
            if verbose:
                print("wrote", os.path.relpath(dst), "(%d colours)" % (len(palette) - 1))
    return out


# ---------------------------------------------------------------------- reading any input
FORMAT = "picogame-project"


def _slug(name):
    s = "".join(c if c.isalnum() or c == "_" else "_" for c in str(name)).lower()
    if not s or s[0].isdigit():
        s = "l_" + s
    return s


def load_any(path):
    """Read game.json v2, a v1 project.json, a v1 .scene.json or an editor .pgproj.json and return
    a v2 project dict (in memory; nothing is written). The migration is mechanical:
    a scene = a project with one level, a v1 project = v2 with legends moved into the assets."""
    with open(path, encoding="utf-8") as f:
        src = json.load(f)
    fmt = src.get("format", "")
    stem = os.path.basename(path).split(".")[0]
    if fmt == "picogame-project-save":            # editor working copy: the raw model inside
        src = src.get("project", src)
        fmt = "picogame-project"
        src = _from_editor_model(src, stem)
    if fmt == "picogame-scene" or ("levels" not in src and "layers" in src):
        lv = {k: v for k, v in src.items() if k not in ("format", "version", "size", "assets", "sounds")}
        lv.setdefault("name", stem)
        src = {"format": FORMAT, "version": 2, "name": stem, "size": src.get("size", [320, 240]),
               "assets": src.get("assets", {}), "sounds": src.get("sounds", {}), "levels": [lv]}
    src.setdefault("format", FORMAT)
    if int(src.get("version", 1)) < 2:
        src = _upgrade_v1(src, stem)
    _slugify(src)
    _asciify(src)
    return src


def _from_editor_model(m, stem):
    """The .pgproj raw model keeps assets as the editor sees them (fw/fh, image handles) - map the
    parts the runtime needs; the grid form is kept, fmt turns it into rows later."""
    out = {"format": FORMAT, "version": 1, "name": m.get("name", stem),
           "size": m.get("size", [320, 240]), "assets": {}, "sounds": m.get("sounds", {}),
           "levels": []}
    for aid, a in (m.get("assets") or {}).items():
        e = {"type": a.get("type")}
        if a.get("type") in IMG_TYPES:
            e["src"] = a.get("src")
            e["frames"] = a.get("frames", 1)
            if a.get("type") == "tileset":
                e["tile"] = [a.get("fw"), a.get("fh")]
            else:
                e["frame"] = [a.get("fw"), a.get("fh")]
            if a.get("transparent") is not None:
                e["transparent"] = a["transparent"]
        elif a.get("type") == "rect":
            e["size"] = [a.get("fw"), a.get("fh")]
            e["color"] = a.get("color")
        elif a.get("type") == "tileset_color":
            e["tile"] = [a.get("fw"), a.get("fh")]
            e["colors"] = a.get("colors")
        for k in ("props", "animations", "legend"):
            if a.get(k):
                e[k] = a[k]
        out["assets"][aid] = e
    for lv in m.get("levels") or []:
        out["levels"].append(_level_from_model(lv, out["assets"]))
    if m.get("scripts"):
        out["scripts"] = m["scripts"]
    return out


def _level_from_model(lv, assets):
    """Mirror of the editor's buildLevel(): tilemaps (bg, then fg) / entities (tagged ones fold
    into groups unless they carry a name, data, frame or anim) / particles / hud -> layers[]."""
    e = {"name": lv.get("name", "level"), "background": lv.get("background", [0, 0, 0])}
    if lv.get("worldSize"):
        e["worldSize"] = lv["worldSize"]
    bg, mid, fg, hud = [], [], [], []
    for tm in lv.get("tilemaps") or []:
        L = {"kind": "tilemap", "asset": tm.get("asset"), "pos": list(tm.get("pos") or [0, 0]),
             "grid": [list(r) for r in tm.get("grid") or []]}
        if tm.get("fg"):
            L["fg"] = True
        (fg if tm.get("fg") else bg).append(L)
    groups = {}
    for en in lv.get("entities") or []:
        tag = en.get("tag")
        plain = tag and not en.get("name") and not en.get("data") and not en.get("frame") and not en.get("angle")
        if plain:
            g = groups.get(tag)
            if g is None:
                g = groups[tag] = {"kind": "group", "asset": en.get("asset"), "tag": tag}
                an = en.get("anchor") or [0, 0]
                if an[0] or an[1]:
                    g["anchor"] = list(an)
                g["instances"] = []
                if en.get("anim"):
                    g["anim"] = en["anim"]
            g["instances"].append([en.get("x", 0), en.get("y", 0)])
            continue
        L = {"kind": "sprite", "asset": en.get("asset")}
        if en.get("name"):
            L["name"] = en["name"]
        if tag:
            L["tag"] = tag
        L["pos"] = [en.get("x", 0), en.get("y", 0)]
        an = en.get("anchor") or [0, 0]
        if an[0] or an[1]:
            L["anchor"] = list(an)
        if en.get("frame"):
            L["frame"] = en["frame"]
        for k in ("anim", "data", "angle"):
            if en.get(k):
                L[k] = en[k]
        mid.append(L)
    mid.extend(groups.values())
    for p in lv.get("particles") or []:
        mid.append({"kind": "particles", "name": p.get("name"), "capacity": p.get("capacity", 64),
                    "size": p.get("size", 2), "gravity": p.get("gravity", 0.0), "fade": bool(p.get("fade"))})
    for h in lv.get("hud") or []:
        hud.append({"kind": "hudlabel", "name": h.get("name"), "pos": [h.get("x", 0), h.get("y", 0)],
                    "fg": h.get("fg", [255, 255, 255]), "bg": h.get("bg", [0, 0, 0])})
    e["layers"] = bg + mid + fg + hud
    if lv.get("camera"):
        c = lv["camera"]
        e["camera"] = {"mode": c.get("mode", "follow"), "target": c.get("target"),
                       "axis": c.get("axis", "x"), "bounds": list(c.get("bounds") or [])}
    for k in ("zones", "points", "effects", "music"):
        if lv.get(k):
            e[k] = lv[k]
    return e


def _upgrade_v1(p, stem):
    p = dict(p)
    p["version"] = 2
    p.setdefault("name", stem)
    assets = p.setdefault("assets", {})
    for lv in p.get("levels", []):
        for layer in lv.get("layers", []):
            if layer.get("kind") == "tilemap" and "legend" in layer:
                a = assets.get(layer.get("asset"))
                if a is not None:
                    cur = a.setdefault("legend", {})
                    for ch, v in layer["legend"].items():
                        if ch in cur and cur[ch] != v:
                            print("warning: legend %r differs for %r (%d vs %d): the level keeps "
                                  "its own legend" % (ch, layer.get("asset"), cur[ch], v))
                            break
                    else:
                        cur.update(layer["legend"])
                        del layer["legend"]
    if "start" not in p and p.get("levels"):
        p["start"] = p["levels"][0].get("name")
    return p


# The ASCII alphabet for map rows - the editor's LEGEND_CHARS, character for character, so both
# tools give a new tile the same letter. '.' is tile 0; " and \ are excluded (JSON-hostile).
LEGEND_CHARS = ("#o=+*xXOA BCDEFGHIJKLMNPQRSTUVWYZabcdefghijklmnpqrstuvwyz0123456789"
                "!$%&()<>?@[]^_{|}~;:,'`/").replace(" ", "")


def _rows_from_grid(grid, legend):
    """int grid -> rows over `legend` (mutated append-only, like the editor's asciiRows), or None
    when the alphabet runs out."""
    legend.setdefault(".", 0)
    char_of = {}
    for ch, v in legend.items():
        char_of.setdefault(v, ch)
    missing = sorted({v for row in grid for v in row if v not in char_of})
    ci = 0
    for v in missing:
        while ci < len(LEGEND_CHARS) and LEGEND_CHARS[ci] in legend:
            ci += 1
        if ci >= len(LEGEND_CHARS):
            return None
        legend[LEGEND_CHARS[ci]] = v
        char_of[v] = LEGEND_CHARS[ci]
        ci += 1
    return ["".join(char_of[v] for v in row) for row in grid]


def _asciify(p):
    """Every tilemap layer as ASCII rows over its asset's legend - the one authoring form. A grid
    stays only when a layer uses more distinct tiles than the alphabet holds."""
    assets = p.get("assets", {})
    for lv in p.get("levels", []):
        for layer in lv.get("layers", []):
            if layer.get("kind") != "tilemap" or "grid" not in layer:
                continue
            a = assets.get(layer.get("asset"))
            if a is None:
                continue
            legend = a.setdefault("legend", {})
            if layer.get("legend"):
                for ch, v in layer["legend"].items():
                    legend.setdefault(ch, v)
            rows = _rows_from_grid(layer["grid"], legend)
            if rows is None:
                continue
            layer["rows"] = rows
            del layer["grid"]
            layer.pop("legend", None)
            layer.pop("cols", None)
            layer.pop("rows_", None)


def _slugify(p):
    """Level and script names become identifiers (module suffixes); every reference follows."""
    ren = {}
    for lv in p.get("levels", []):
        n = lv.get("name") or "level"
        s = _slug(n)
        if s != n:
            lv.setdefault("title", n)
            ren[n] = s
            lv["name"] = s
    if not ren:
        return
    if p.get("start") in ren:
        p["start"] = ren[p["start"]]
    for lv in p.get("levels", []):
        for z in lv.get("zones", []):
            d = z.get("data") or {}
            g = d.get("goto")
            if isinstance(g, list) and g and g[0] in ren:
                g[0] = ren[g[0]]
            elif isinstance(g, str) and g in ren:
                d["goto"] = ren[g]
    print("renamed levels:", ", ".join("%s -> %s" % kv for kv in ren.items()))


# ---------------------------------------------------------------------- canonical text
ORDER = {
    "project": ["format", "version", "name", "icon", "size", "start", "launcher", "assets",
                "sounds", "scripts", "levels"],
    "asset": ["type", "src", "frame", "tile", "size", "frames", "transparent", "color", "colors",
              "legend", "props", "animations"],
    "level": ["name", "title", "background", "worldSize", "layers", "camera", "zones", "points",
              "effects", "music"],
    "layer": ["kind", "asset", "name", "tag", "pos", "anchor", "frame", "anim", "angle", "data",
              "instances", "fg", "bg", "capacity", "size", "gravity", "fade", "legend", "rows", "grid"],
    "zone": ["tag", "x", "y", "w", "h", "data"],
    "point": ["name", "x", "y", "data"],
    "camera": ["mode", "target", "axis", "bounds"],
}


def _ordered(d, kind):
    keys = ORDER.get(kind, [])
    return [k for k in keys if k in d] + sorted(k for k in d if k not in keys)


def _scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        return str(int(v))
    if isinstance(v, (int, float)):
        return json.dumps(v)
    return json.dumps(v, ensure_ascii=False)


def _is_scalar_list(v):
    return isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v)


def canonical(obj, kind="project", ind=0):
    """The one text form of a project: fixed key order, indent 1, scalar arrays on one line
    (a map row per line, a point on one line), integral floats as ints, UTF-8 as is."""
    pad = " " * ind
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        keys = _ordered(obj, kind) if kind else _plain_keys(obj)
        parts = []
        for k in keys:
            v = obj[k]
            sub = _child_kind(kind, k)
            parts.append("%s %s: %s" % (pad, json.dumps(k, ensure_ascii=False), canonical(v, sub, ind + 1)))
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if _is_scalar_list(obj):
            return "[" + ", ".join(_scalar(x) for x in obj) + "]"
        return "[\n" + ",\n".join(pad + " " + canonical(x, kind, ind + 1) for x in obj) + "\n" + pad + "]"
    return _scalar(obj)


def _plain_keys(d):
    """A dict with no schema: digit keys first in numeric order, then the rest as they came -
    the one order both a JS object and a Python dict can promise (the editor's Save matches)."""
    num = sorted((k for k in d if str(k).lstrip("-").isdigit()), key=lambda k: int(k))
    return num + [k for k in d if not str(k).lstrip("-").isdigit()]


def _child_kind(kind, key):
    if kind == "project":
        return {"assets": "assets", "levels": "level", "sounds": None}.get(key, None)
    if kind == "assets":
        return "asset"
    if kind == "level":
        return {"layers": "layer", "zones": "zone", "points": "point", "camera": "camera"}.get(key)
    return None


def fmt_text(project):
    return canonical(project, "project") + "\n"


# ---------------------------------------------------------------------- validation
def _asset_frames(a):
    t = a.get("type")
    if t in IMG_TYPES or t == "pal8_inline":
        return a.get("frames", 1)
    if t == "rect":
        return 1
    if t == "tileset_color":
        try:
            return max(int(k) for k in a["colors"]) + 1
        except (KeyError, ValueError):
            return None
    return None


def _cond_flags(c, out):
    if c is None:
        return
    for one in (c if isinstance(c, list) else [c]):
        out.add(str(one).lstrip("!"))


def validate(project, base=None, story=None):
    """-> list of 'path: problem' strings; empty = valid. story = the story.py text if present."""
    errs = []
    warn = []
    assets = project.get("assets", {})
    frames = {}
    if project.get("format") not in (FORMAT, None):
        errs.append("format: %r is not %r" % (project.get("format"), FORMAT))
    for aid, a in assets.items():
        if not aid.replace("_", "").isalnum() or aid[0].isdigit():
            errs.append("assets[%r]: asset id must be an identifier" % aid)
        f = _asset_frames(a)
        if f is not None:
            frames[aid] = f
        if a.get("type") in IMG_TYPES:
            if not a.get("src"):
                errs.append("assets[%r]: needs src (a PNG next to game.json)" % aid)
            elif "/" in a["src"] or "\\" in a["src"]:
                errs.append("assets[%r].src: %r must be a bare file name next to game.json" % (aid, a["src"]))
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
                errs.append("assets[%r].props[%r]: tile value %d >= frames (%d)" % (aid, k, kv, f))
            for flag in (a["props"][k] or {}):
                if flag == "transparent":
                    errs.append("assets[%r].props[%r]: 'transparent' is not a tile flag (it is the "
                                "asset's transparent colour index); use solid/hazard/... " % (aid, k))
        for ch, v in (a.get("legend") or {}).items():
            if len(ch) != 1:
                errs.append("assets[%r].legend[%r]: legend keys are single characters" % (aid, ch))
            if f is not None and (v & 0xFF) >= f:
                errs.append("assets[%r].legend[%r]: tile %d >= frames (%d)" % (aid, ch, v & 0xFF, f))

    names = [lv.get("name") for lv in project.get("levels", [])]
    for n in names:
        if not n or not n.replace("_", "").isalnum() or n[0].isdigit():
            errs.append("levels: name %r must be an identifier (run fmt/migrate to slugify)" % n)
    if len(set(names)) != len(names):
        errs.append("levels: duplicate level names")
    if project.get("start") and project["start"] not in names:
        errs.append("start: unknown level %r" % project["start"])
    tested, setflags = set(), set()
    for li, lv in enumerate(project.get("levels", [])):
        where = "levels[%d]" % li
        seen = {}
        tm_assets = []
        for i, layer in enumerate(lv.get("layers", [])):
            p = "%s.layers[%d]" % (where, i)
            kind = layer.get("kind")
            aid = layer.get("asset")
            f = None
            if kind in ("tilemap", "sprite", "group"):
                if aid not in assets:
                    errs.append("%s.asset: unknown asset %r" % (p, aid))
                else:
                    f = frames.get(aid)
            label = layer.get("tag") if kind == "group" else layer.get("name")
            if label:
                if label in seen:
                    errs.append("%s: duplicate name/tag %r (also %s)" % (p, label, seen[label]))
                seen[label] = p
            if kind == "sprite" and f is not None and layer.get("frame", 0) >= f:
                errs.append("%s.frame: %d >= asset %r frames (%d)" % (p, layer.get("frame", 0), aid, f))
            if kind in ("sprite", "group"):
                anim = layer.get("anim")
                if anim and aid in assets and anim not in (assets[aid].get("animations") or {}):
                    errs.append("%s.anim: asset %r has no animation %r" % (p, aid, anim))
            if kind != "tilemap":
                continue
            tm_assets.append(aid)
            if "grid" in layer:
                g2 = layer["grid"]
                cols0 = len(g2[0]) if g2 else 0
                for ry, row in enumerate(g2):
                    if len(row) != cols0:
                        errs.append("%s.grid[%d]: row length %d != %d" % (p, ry, len(row), cols0))
                    for cx, v in enumerate(row):
                        if f is not None and (v & 0xFF) >= f:
                            errs.append("%s.grid[%d][%d]: tile %d >= frames (%d)" % (p, ry, cx, v & 0xFF, f))
            elif "rows" in layer:
                rows = layer["rows"]
                cols0 = len(rows[0]) if rows else 0
                legend = layer.get("legend") or (assets.get(aid) or {}).get("legend") or {}
                for ry, row in enumerate(rows):
                    if len(row) != cols0:
                        errs.append("%s.rows[%d]: row length %d != %d" % (p, ry, len(row), cols0))
                unknown = sorted({ch for row in rows for ch in row} - set(legend) - {".", " "})
                if unknown:
                    errs.append("%s.rows: %s not in the legend of %r (they would bake as empty)"
                                % (p, ", ".join(repr(c) for c in unknown), aid))
            else:
                errs.append("%s: a tilemap needs rows (or grid)" % p)
        for zi, z in enumerate(lv.get("zones", [])):
            p = "%s.zones[%d]" % (where, zi)
            d = z.get("data") or {}
            if "script" in d and any(k in d for k in ("say", "ask", "goto")):
                errs.append("%s.data: a zone is either data (say/ask/goto) or a script, not both" % p)
            if "goto" in d:
                g = d["goto"] if isinstance(d["goto"], list) else [d["goto"]]
                if g[0] not in names:
                    errs.append("%s.data.goto: unknown level %r" % (p, g[0]))
                elif len(g) > 1 and g[1]:
                    tgt = [x for x in project["levels"] if x.get("name") == g[0]][0]
                    if g[1] not in [pt.get("name") for pt in tgt.get("points", [])]:
                        errs.append("%s.data.goto: level %r has no point %r" % (p, g[0], g[1]))
                _cond_flags(d.get("if"), tested)
            if "say" in d:
                for e in d["say"]:
                    if isinstance(e, dict):
                        _cond_flags(e.get("if"), tested)
                        if e.get("set"):
                            setflags.add(e["set"])
            if "ask" in d and d["ask"].get("set"):
                setflags.add(d["ask"]["set"])
            if "script" in d:
                s = d["script"]
                if not str(s).replace("_", "").isalnum():
                    errs.append("%s.data.script: %r is not a Python identifier" % (p, s))
                elif story is not None and ("def %s(" % s) not in story:
                    warn.append("%s.data.script: story.py has no def %s(d)" % (p, s))
        for ei, rule in enumerate(lv.get("effects", [])):
            p = "%s.effects[%d]" % (where, ei)
            _cond_flags(rule.get("if"), tested)
            for key in ("swap", "solid", "unsolid"):
                for t in (rule.get(key) or []):
                    if not isinstance(t, int):
                        errs.append("%s.%s: tiles are integers, not legend characters" % (p, key))
                    elif tm_assets and frames.get(tm_assets[0]) is not None and t >= frames[tm_assets[0]]:
                        errs.append("%s.%s: tile %d >= frames of %r" % (p, key, t, tm_assets[0]))
            for n in (rule.get("hide") or []) + (rule.get("show") or []):
                if n not in seen:
                    errs.append("%s: hide/show names unknown sprite %r" % (p, n))
    if story:
        import re
        for m in re.finditer(r"d\.set\(\s*[\"']([^\"']+)[\"']", story):
            setflags.add(m.group(1))
    for flag in sorted(tested - setflags):
        warn.append("flag %r is tested but nothing sets it" % flag)
    return errs, warn


def check(path, verbose=True):
    project = load_any(path)
    base = os.path.dirname(os.path.abspath(path))
    story_path = os.path.join(base, "story.py")
    story = open(story_path, encoding="utf-8").read() if os.path.exists(story_path) else None
    errs, warn = validate(project, base, story)
    for aid, a in png_assets(project):
        if not os.path.exists(os.path.join(base, a["src"])):
            errs.append("assets[%r]: %s missing next to game.json" % (aid, a["src"]))
        elif not os.path.exists(os.path.join(base, sb._sidecar(a["src"]))):
            warn.append("assets[%r]: no %s yet - run scene_build.py art" % (aid, sb._sidecar(a["src"])))
    for legacy in os.listdir(base):
        if legacy.endswith((".scene.json", ".pgproj.json")) and os.path.basename(path) == "game.json":
            errs.append("%s lies next to game.json - migrate it (scene_build.py migrate) and delete it" % legacy)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if project.get("format") == FORMAT and int(project.get("version", 1)) == 2 and text != fmt_text(project):
        warn.append("not in canonical form (key order / layout): run scene_build.py fmt")
    if verbose:
        for e in errs:
            print("error:", e)
        for w in warn:
            print("warning:", w)
        if not errs:
            print("%s: ok (%d level%s, %d asset%s)" % (path, len(project.get("levels", [])),
                  "" if len(project.get("levels", [])) == 1 else "s", len(project.get("assets", {})),
                  "" if len(project.get("assets", {})) == 1 else "s"))
    return errs, warn


# ---------------------------------------------------------------------- build (ship)
def write_module(path, name, data, header="scene_build.py"):
    with open(path, "w") as f:
        f.write("# GENERATED by %s from game.json - do not edit, re-run the build\n" % header)
        f.write(name + " = " + repr(data) + "\n")
    print("wrote", os.path.relpath(path), "(%d bytes)" % os.path.getsize(path))


def find_mpy_cross():
    import shutil
    cands = [os.environ.get("MPY_CROSS"), shutil.which("mpy-cross"),
             os.path.join(_HERE, "..", "..", "..", "build", "circuitpython", "mpy-cross", "build", "mpy-cross")]
    for c in cands:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def build(path, out_dir=None, mpy=False):
    project = load_any(path)
    base = os.path.dirname(os.path.abspath(path))
    errs, _ = validate(project, base)
    if errs:
        for e in errs:
            sys.stderr.write("scene_build: %s\n" % e)
        raise SystemExit("%s: validation failed (%d error%s)" % (path, len(errs), "" if len(errs) == 1 else "s"))
    out_dir = out_dir or os.path.join(base, "build")
    os.makedirs(out_dir, exist_ok=True)
    art(project, base, verbose=False)
    stem = "game"
    bank = sb.bake_bank(project["assets"], project.get("sounds"), None)
    # the bank ships the .pal8 sidecars by name (they are copied next to it)
    bank["levels"] = [lv["name"] for lv in project["levels"]]
    bank["start"] = project.get("start") or bank["levels"][0]
    bank["size"] = list(project.get("size", [320, 240]))
    bank["name"] = project.get("name")
    written = []
    p = os.path.join(out_dir, stem + "_bank.py")
    write_module(p, "BANK", bank)
    written.append(p)
    for lv in project["levels"]:
        p = os.path.join(out_dir, "level_%s.py" % lv["name"])
        write_module(p, "LEVEL", sb.bake_level(lv, project.get("size", [320, 240]), project["assets"]))
        written.append(p)
    import shutil
    for aid, a in png_assets(project):
        shutil.copy(os.path.join(base, sb._sidecar(a["src"])), out_dir)
    for sid, s in (project.get("sounds") or {}).items():
        src = s["src"] if isinstance(s, dict) else s
        if os.path.exists(os.path.join(base, src)):
            shutil.copy(os.path.join(base, src), out_dir)
    code = os.path.join(base, "code.py")
    if os.path.exists(code):
        text = open(code, encoding="utf-8").read()
        if '"game.json"' not in text and "'game.json'" not in text:
            print("warning: code.py does not load game.json via Game(pg, \"game.json\") - copied as is")
        text = text.replace('"game.json"', '"%s_bank"' % stem).replace("'game.json'", "'%s_bank'" % stem)
        with open(os.path.join(out_dir, "code.py"), "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote", os.path.relpath(os.path.join(out_dir, "code.py")), "(Game(pg, \"%s_bank\"))" % stem)
    story = os.path.join(base, "story.py")
    if os.path.exists(story):
        shutil.copy(story, out_dir)
        written.append(os.path.join(out_dir, "story.py"))
    shutil.copy(path, os.path.join(out_dir, "game.json"))
    if mpy:
        mc = find_mpy_cross()
        if not mc:
            raise SystemExit("mpy-cross not found: set MPY_CROSS=/path/to/mpy-cross (build it from the "
                             "CircuitPython tree that matches the board's version, see boot_out.txt)")
        import subprocess
        for src in written:
            dst = src[:-3] + ".mpy"
            subprocess.check_call([mc, "-s", os.path.basename(src), "-o", dst, src])
            os.remove(src)
            print("compiled", os.path.relpath(dst))
    print("build: %s -> %s" % (os.path.relpath(path), os.path.relpath(out_dir)))


# ---------------------------------------------------------------------- legacy bake (single scene / v1)
def bake_legacy(src):
    """The old positional call: <name>.scene.json -> <name>_scene.py (SCENE), a v1 project.json ->
    <stem>_bank.py + <level>_level.py. Kept so existing docs, goldens and demos keep working."""
    with open(src) as f:
        scene = json.load(f)
    base = os.path.dirname(os.path.abspath(src))
    size = scene.get("size", [320, 240])
    stem = os.path.splitext(os.path.splitext(src)[0])[0]
    if "levels" in scene:
        bank = sb.bake_bank(scene["assets"], scene.get("sounds"), None)
        _materialize(bank, scene, base)
        write_module(stem + "_bank.py", "BANK", bank)
        for lv in scene["levels"]:
            name = lv.get("name", "level")
            safe = "".join(c if c.isalnum() else "_" for c in name)
            write_module(os.path.join(base, safe + "_level.py"), "LEVEL",
                         sb.bake_level(lv, size, scene["assets"]))
        return
    errs, _ = validate(load_any(src), base)
    if errs:
        for e in errs:
            sys.stderr.write("scene_build: %s\n" % e)
        raise SystemExit("%s: scene validation failed (%d error%s)" % (src, len(errs), "" if len(errs) == 1 else "s"))
    out = sb.bake(scene, None)
    _materialize(out, scene, base)
    write_module(stem + "_scene.py", "SCENE", out)


def _materialize(baked, scene, base):
    """Legacy modules carry the pixels INSIDE (no sidecars): quantize PNG assets in place."""
    for aid, a in png_assets(scene):
        fw, fh, frames = asset_geometry(a)
        data, palette = quantize_png(os.path.join(base, a["src"]), fw, fh, frames)
        baked["assets"][aid] = ("pal8", data, fw, fh, frames, 0, tuple(palette))


# ---------------------------------------------------------------------- commands
def cmd_fmt(path):
    project = load_any(path)
    text = fmt_text(project)
    old = open(path, encoding="utf-8").read()
    if old != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("formatted", path)
    else:
        print(path, "already canonical")


def _write_pgproj_art(path, project, base):
    """A .pgproj keeps the PNG pixels inside (data URLs): write them out next to game.json."""
    import base64
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    art = raw.get("art") or (raw.get("project") or {}).get("art") or {}
    n = 0
    for aid, url in art.items():
        a = project.get("assets", {}).get(aid)
        if not a or not isinstance(url, str) or "," not in url:
            continue
        name = a.get("src") or (aid + ".png")
        a["src"] = name
        dst = os.path.join(base, name)
        if not os.path.exists(dst):
            with open(dst, "wb") as f:
                f.write(base64.b64decode(url.split(",", 1)[1]))
            n += 1
    if n:
        print("wrote %d PNG(s) from the .pgproj" % n)


def cmd_migrate(path, out=None):
    project = load_any(path)
    base = os.path.dirname(os.path.abspath(path))
    if path.endswith(".pgproj.json"):
        _write_pgproj_art(path, project, base)
    out = out or os.path.join(base, "game.json")
    if os.path.abspath(out) == os.path.abspath(path):
        raise SystemExit("migrate: give the old file, game.json is written next to it")
    if os.path.exists(out):
        raise SystemExit("%s exists - merge by hand or move it away" % out)
    scripts = project.pop("scripts", None)
    with open(out, "w", encoding="utf-8") as f:
        f.write(fmt_text(project))
    print("wrote", out)
    if scripts:
        story = os.path.join(base, "story.py")
        with open(story, "a", encoding="utf-8") as f:
            for name, body in scripts.items():
                lines = str(body).replace("\r", "").split("\n")
                f.write("\n\ndef %s(d):\n" % _slug(name))
                f.write("\n".join(("    " + l) if l.strip() else "" for l in lines) or "    yield")
                f.write("\n")
        print("appended %d script(s) to %s - bodies that used goto()/view./apply_effects() need "
              "d.goto()/d.view/d.effects()" % (len(scripts), story))
    legacy = os.path.join(base, "legacy")
    os.makedirs(legacy, exist_ok=True)
    os.replace(path, os.path.join(legacy, os.path.basename(path)))
    print("moved %s -> legacy/" % os.path.basename(path))


def cmd_watch(path, do_build=False):
    import time
    base = os.path.dirname(os.path.abspath(path))
    print("watching", base, "(Ctrl-C to stop)")
    last = None
    while True:
        stamps = []
        for n in sorted(os.listdir(base)):
            if n.endswith((".json", ".png", ".py", ".wav")):
                try:
                    stamps.append((n, os.stat(os.path.join(base, n)).st_mtime))
                except OSError:
                    pass
        if stamps != last:
            last = stamps
            try:
                errs, _ = check(path)
                if not errs:
                    project = load_any(path)
                    art(project, base)
                    if do_build:
                        build(path)
            except SystemExit as e:
                print(e)
        time.sleep(1.0)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    rest = argv[1:]
    if cmd in ("check", "fmt", "art", "build", "migrate", "watch"):
        path = next((a for a in rest if not a.startswith("-")), "game.json")
        if cmd == "check":
            errs, _ = check(path)
            return 1 if errs else 0
        if cmd == "fmt":
            cmd_fmt(path)
        elif cmd == "art":
            project = load_any(path)
            if not art(project, os.path.dirname(os.path.abspath(path))):
                print("art up to date")
        elif cmd == "build":
            out = rest[rest.index("--out") + 1] if "--out" in rest else None
            build(path, out, mpy="--mpy" in rest)
        elif cmd == "migrate":
            out = rest[rest.index("-o") + 1] if "-o" in rest else None
            cmd_migrate(path, out)
        elif cmd == "watch":
            cmd_watch(path, "--build" in rest)
        return 0
    bake_legacy(cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
