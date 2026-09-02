#!/usr/bin/env python3
"""The sim's PUBLIC surface must equal the firmware's - in BOTH directions.

The sim exists to be trusted: a game built against it must run unchanged on the device.
That breaks two ways, and both happened in one week (2026-08-30):
  * sim-only leakage - the sim exposed `Tilemap.grid` / `Bitmap.data` as ordinary attributes,
    an agent found them via dir() and shipped a game that AttributeErrors on real firmware;
  * reverse drift - the firmware grew `road_edges`/`Canvas.road` and the sim silently didn't,
    so the documented racing path was unbuildable in the only place games get built.

So: for the module and each engine class, compare the sim's public names against the firmware
surface (transcribed below from shared-bindings/picogame ROM tables - update BOTH when the
frozen API ever changes). Extra public names in the sim FAIL (underscore them); missing names
FAIL unless listed in DEVICE_ONLY with a reason.

Names alone are not enough. A sim-only PARAMETER passes a name check in silence and still breaks
the game on the device - an added `Canvas.mode7(up=)` and `raycast(wallx=)` did exactly that. So
every callable in C_SIG is signature-checked as well: parameter names in order, with `*` marking
the keyword-only split.

Regenerating C_SIG (do it from the INTEGRATION branch, never a feature branch - a branch that has
not shipped is precisely what must NOT be mirrored here): extract shared-bindings/picogame from
that branch, then parse the `//| def ...` docstrings and print one line per callable.

    python3 sim/selftest_api.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board            # noqa: E402  (DISPLAY stub for a Scene instance)
import picogame as pg   # noqa: E402

# shared-bindings/picogame/*.c ROM tables (methods + properties), branch `picogame`.
C_MODULE = {
    "API_LEVEL", "Bitmap", "Canvas", "Display", "FAST_DISPLAY_SUPPORTED", "FPU",
    "FRAMEBUFFER_SUPPORTED", "Framebuffer", "PAL8", "Particles", "RGB444_SUPPORTED", "RGB565",
    "STRIP_H", "Scene", "Sprite", "StripDraw", "Tilemap", "Triangles", "collide", "core1",
    "fat_layout", "fat_max_free_run", "fbm1d", "fbm2d", "invert", "picogame", "project",
    "raycast", "refresh_async", "render", "repack", "rgb565", "road_edges", "value1d",
    "value2d", "vblank", "xip_map",
}
C_CLASS = {
    "Sprite": {"anchor", "angle", "bitmap", "data", "dither", "flash", "flip_x", "flip_y",
               "frame", "fx", "fy", "move", "near", "overlaps", "scale", "shadow", "tint",
               "touch", "transpose", "visible", "x", "y"},
    "Bitmap": {"format", "frames", "height", "palette", "stride", "transparent", "width"},
    "Tilemap": {"cols", "fill", "get_tile", "move", "rows", "set_tile", "x", "y"},
    "Canvas": {"blit", "circle", "clear", "ellipse", "fill_circle", "fill_ellipse", "fill_rect",
               "fill_round_rect", "fill_triangle", "fill_triangles", "frame3d", "height", "line",
               "mode7", "move", "pixel", "rect", "ring", "road", "text", "triangle", "vspans",
               "width", "x", "y"},
    "StripDraw": {"always_dirty", "height", "invalidate", "width", "x", "y"},
    "Particles": {"clear", "emit", "tick"},
    "Triangles": {"count"},
    "Scene": {"add", "add_all", "display", "invalidate", "refresh", "remove", "set_view", "view"},
}
# Firmware SIGNATURES, transcribed from the same shared-bindings docstrings: parameter names in
# order, `*` marking the keyword-only split, `self` omitted. Names matter because MicroPython
# accepts them as keywords, and an extra parameter is how a sim-only feature leaks in unnoticed
# (a name-only check passes an added `up=` or `wallx=` in silence). Only callables listed here are
# signature-checked; add a line when the frozen API grows one.
C_SIG = {
    None: {
        'collide': ['x1', 'y1', 'x2', 'y2', 'ax1', 'ay1', 'ax2', 'ay2'],
        'fat_layout': ['path'],
        'fat_max_free_run': ['path'],
        'fbm1d': ['x', '*', 'octaves', 'seed', 'lacunarity', 'gain'],
        'fbm2d': ['x', 'y', '*', 'octaves', 'seed', 'lacunarity', 'gain'],
        'invert': ['display', 'on'],
        'project': ['cam', 'pts', 'n', 'out_sx', 'out_sy'],
        'raycast': ['map', 'mw', 'mh', 'posx', 'posy', 'lrx', 'lry', 'srx', 'sry', 'sh', 'stride', 'ncols', 'wcolors', 'top', 'bot', 'col', 'dist', 'runs'],
        'render': ['display', 'layers', 'buffer', 'x0', 'y0', 'x1', 'y1', '*', 'background'],
        'repack': ['path'],
        'rgb565': ['r', 'g', 'b'],
        'road_edges': ['rl', 'rr', 'hw', 'n', 'cx0', 'dist', 'cfg'],
        'value1d': ['x', '*', 'seed'],
        'value2d': ['x', 'y', '*', 'seed'],
        'vblank': ['framebuffer'],
        'xip_map': ['path'],
    },
    'Canvas': {
        'blit': ['bitmap', 'x', 'y', 'frame', 'flip_x', 'flip_y'],
        'circle': ['cx', 'cy', 'r', 'color'],
        'clear': ['color'],
        'ellipse': ['cx', 'cy', 'rx', 'ry', 'color'],
        'fill_circle': ['cx', 'cy', 'r', 'color'],
        'fill_ellipse': ['cx', 'cy', 'rx', 'ry', 'color'],
        'fill_rect': ['x', 'y', 'w', 'h', 'color'],
        'fill_round_rect': ['x', 'y', 'w', 'h', 'r', 'color'],
        'fill_triangle': ['x0', 'y0', 'x1', 'y1', 'x2', 'y2', 'color'],
        'fill_triangles': ['verts', 'colors', 'n', 'x_off', 'y_off'],
        'frame3d': ['x', 'y', 'w', 'h', 'light', 'dark'],
        'line': ['x0', 'y0', 'x1', 'y1', 'color'],
        'mode7': ['texture', 'horizon', 'y_off', 'z', 'rx0', 'ry0', 'rsx', 'rsy', 'cam_x', 'cam_y'],
        'move': ['x', 'y'],
        'pixel': ['x', 'y', 'color'],
        'rect': ['x', 'y', 'w', 'h', 'color'],
        'ring': ['cx', 'cy', 'r', 'thickness', 'color'],
        'road': ['ri0', 'tab', 'rl', 'rr', 'd05_q8', 'd07_q8', 'colors'],
        'text': ['x', 'y', 's', 'fg', 'font', 'bg'],
        'triangle': ['x0', 'y0', 'x1', 'y1', 'x2', 'y2', 'color'],
        'vspans': ['x0s', 'x1s', 'tops', 'bots', 'colors', 'n', 'x_off', 'y_off'],
    },
    'Particles': {
        'clear': [],
        'emit': ['x', 'y', 'count', 'speed', 'life', 'color'],
        'tick': [],
    },
    'Scene': {
        'add': ['item', '*', 'fixed'],
        'add_all': ['items'],
        'invalidate': [],
        'refresh': [],
        'remove': ['item'],
        'set_view': ['ox', 'oy'],
    },
    'Sprite': {
        'move': ['x', 'y'],
        'near': ['other', 'r'],
        'overlaps': ['other', 'inset'],
        'touch': [],
    },
    'StripDraw': {
        'invalidate': ['x', 'y', 'w', 'h'],
    },
    'Tilemap': {
        'fill': ['value'],
        'get_tile': ['tx', 'ty'],
        'move': ['x', 'y'],
        'set_tile': ['tx', 'ty', 'value', '*', 'flip_x', 'flip_y', 'transpose'],
    },
}

# In the firmware but deliberately NOT in the sim - each with the reason it stays that way.
DEVICE_ONLY = {
    None: {           # module level
        "refresh_async",     # FAST_DISPLAY async DMA overlap - no DMA to overlap on a PC
        "vblank",            # DVI scanout beam sync (RP2350)
        "repack",            # device heap defrag
        "core1",             # RP2 second core routing (fork branch)
        "xip_map",           # fork branch: XIP flash mapping
        "fat_layout",        # fork/tooling: FAT extent probing
        "fat_max_free_run",  # -"-
        "picogame",          # firmware self-reference quirk of the module table
        "Framebuffer",       # framebuffer boards (Fruit Jam) - sim drives a BusDisplay stub
        "Display",           # exposed as a TYPE in fw; the sim's stub lives in board.py -- but
                             # the sim DOES export Display, so this entry is unused; kept for doc
    },
}


def check(label, sim_names, c_names, device_only=()):
    extra = sorted(n for n in sim_names - c_names if not n.startswith("_"))
    missing = sorted(n for n in c_names - sim_names if n not in device_only)
    for n in extra:
        print("FAIL %-9s sim-only public name: %s (underscore it - real firmware has no '%s')"
              % (label, n, n))
    for n in missing:
        print("FAIL %-9s missing vs firmware: %s (implement it, or add to DEVICE_ONLY with a reason)"
              % (label, n))
    return len(extra) + len(missing)


def sim_signature(obj):
    """The sim's parameter names in order, `*` for the keyword-only split, self dropped."""
    import inspect
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return None
    out, star = [], False
    for prm in sig.parameters.values():
        if prm.name == "self":
            continue
        if prm.kind is prm.VAR_POSITIONAL:
            out.append("*" + prm.name)
        elif prm.kind is prm.VAR_KEYWORD:
            out.append("**" + prm.name)
        else:
            if prm.kind is prm.KEYWORD_ONLY and not star:
                out.append("*")
                star = True
            out.append(prm.name)
    return out


def check_sigs(label, obj, expected):
    """Compare each listed callable's signature against the firmware's."""
    bad = 0
    for name, want in sorted(expected.items()):
        fn = getattr(obj, name, None)
        if fn is None:
            continue                       # a missing NAME is already reported by check()
        got = sim_signature(fn)
        if got is None or got == want:
            continue
        bad += 1
        print("FAIL %-9s %s(%s) - firmware takes (%s)"
              % (label, name, ", ".join(got), ", ".join(want)))
    return bad


def main():
    bad = 0
    mod = {n for n in dir(pg) if not n.startswith("_")}
    bad += check("module", mod, C_MODULE, DEVICE_ONLY[None])
    bad += check_sigs("module", pg, C_SIG[None])

    bm = pg.Bitmap(bytearray(8), 2, 2)
    insts = {
        "Sprite": pg.Sprite(bm, 0, 0),
        "Bitmap": bm,
        "Tilemap": pg.Tilemap(bm, 4, 4),
        "Canvas": pg.Canvas(8, 8),
        "StripDraw": pg.StripDraw(lambda *a: None, 0, 0, 8, 8),
        "Particles": pg.Particles(8),
        "Triangles": pg.Triangles(bytearray(24), bytearray(4)),
        "Scene": pg.Scene(board.DISPLAY, bytearray(320 * 8 * 2), bytearray(320 * 8 * 2)),
    }
    for name, obj in insts.items():
        sim = {n for n in dir(obj) if not n.startswith("_")}
        bad += check(name, sim, C_CLASS[name], DEVICE_ONLY.get(name, ()))
        bad += check_sigs(name, type(obj), C_SIG.get(name, {}))

    print("selftest_api: %s" % ("OK - sim public surface == firmware surface" if bad == 0
                                else "%d drift(s)" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
