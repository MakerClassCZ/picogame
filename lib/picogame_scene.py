# picogame declarative-scene loader: build a ready Scene from a baked SCENE dict
# (see docs/scene-format.md + tools/scene_build.py). Uses only the
# public picogame API, so the SAME loader runs on the device and in the simulator.
# Loading is one-time (not a hot path), so Python is the right place for it.
#
#   import picogame_scene as pgs, world1_scene, terminalio
#   view = pgs.load(pg, world1_scene.SCENE)              # hudlabels use terminalio.FONT
#   view = pgs.load(pg, world1_scene.SCENE, font=my_extrafont)   # ... or your own
#   player = view.named["player"];  enemies = view.group("enemies")
#   if view.is_solid(tx, ty): ...                      # tile-property query
#   view.scene.set_view(ox, 0); view.scene.refresh()

import array
import board


class View:
    """What load() returns: the populated Scene plus addressable handles."""
    def __init__(self):
        self.scene = None
        self.bufA = None
        self.bufB = None
        self.named = {}
        self.groups = {}
        self.anims = []          # AnimatedSprite instances to advance each frame
        self.camera = None
        self.zones = []          # list of (tag, x, y, w, h[, data]) - data only when authored
        self.points = {}         # name -> (x, y)
        self.pdata = {}          # name -> custom data dict (points that carry any)
        self.sounds = {}         # id -> audio sample (or None if unavailable)
        self.audio = None        # picogame_audio.Audio (or None)
        self.tilemap = None      # the primary tilemap object (read/write tiles)
        self._tm = None          # (tilemap, asset_id, cols, rows) of the primary tilemap
        self._tile = (0, 0, 16, 16)   # (ox, oy, tile_w, tile_h) - dims kept here, not
                                      # read off the C Tilemap (which doesn't expose them)
        self._props = {}         # asset_id -> {prop: bytes}
        self._cur = {}           # the primary tilemap's prop table (see _bind)
        self._solid = None       # ... and its "solid" table, or None
        self.effects = []        # story rules [{if, swap, solid, unsolid, hide, show}] (data)
        self.world = None        # (w, h) authored world size, or None

    def swap_tiles(self, a, b):
        """Replace every cell holding tile `a` with tile `b` on the primary tilemap - the LOOK
        half of a story effect (a gate opens: the gate tile becomes floor)."""
        tm = self.tilemap
        if tm is None or a == b:
            return 0
        n = 0
        cols, rows = self._tm[2], self._tm[3]
        for ty in range(rows):
            for tx in range(cols):
                if tm.get_tile(tx, ty) == a:
                    tm.set_tile(tx, ty, b)
                    n += 1
        return n

    @property
    def tile_size(self):
        """(tile_w, tile_h) of the primary tilemap - what a game needs for probes and offsets."""
        return (self._tile[2], self._tile[3])

    def tile_xy(self, px, py):
        """World pixel -> (tx, ty) tile coords of the primary tilemap."""
        ox, oy, tw, th = self._tile
        return ((px - ox) // tw, (py - oy) // th)

    def group(self, tag):
        return self.groups.get(tag, [])

    def tick(self, dt):
        """Advance all auto-animated sprites (call once per frame with dt seconds)."""
        for a in self.anims:
            a.tick(dt)

    def point(self, name):
        return self.points.get(name)

    def in_zone(self, x, y, tag=None):
        """First zone (tag, x, y, w, h) containing (px, py) [matching tag], or None."""
        for z in self.zones:
            if tag is not None and z[0] != tag:
                continue
            if z[1] <= x < z[1] + z[3] and z[2] <= y < z[2] + z[4]:
                return z
        return None

    def play(self, sound_id):
        if self.audio and self.sounds.get(sound_id):
            self.audio.sfx(self.sounds[sound_id])

    def _bind(self):
        # Cache the primary tilemap's prop tables: the per-frame probes below are then two
        # lookups instead of a dict chain that built a throwaway {} on every call.
        tm = self._tm
        self._cur = self._props.get(tm[1], {}) if tm is not None else {}
        self._solid = self._cur.get("solid")

    def _prop_bytes(self, name):
        return self._cur.get(name)

    def is_solid(self, tx, ty):
        b = self._solid
        if b is None:
            return False
        return bool(b[self.tilemap.get_tile(tx, ty)])

    def set_tile_prop(self, tile, prop, on=True):
        """Flip a flag for a TILE TYPE at runtime: every cell holding that tile
        changes meaning at once (a lever makes all gate tiles walkable, ice
        melts, Baba-style rules rewrite what ROCK does). Complements the native
        Tilemap.set_tile, which changes ONE cell by swapping its tile instead.
        Tables are copied per load(), so changes never leak into other levels
        sharing a bank; a prop that was never baked is created on first set."""
        t = self._props.setdefault(self._tm[1], {})
        b = t.get(prop)
        if b is None:
            # engine cells are one byte, so 256 covers every possible tile value
            b = t[prop] = bytearray(256)
        elif tile >= len(b):
            b.extend(bytes(tile + 1 - len(b)))
        b[tile] = 1 if on else 0
        self._bind()                       # the table (or the asset's dict) may be new

    def tile_has(self, tx, ty, prop):
        b = self._cur.get(prop)
        if b is None:
            return False
        return bool(b[self.tilemap.get_tile(tx, ty)])


def read_pal8(path):
    """Read a .pal8 sidecar (see picogame_scenebake.encode_pal8).
    -> (palette array('H'), index bytes, fw, fh, frames, transparent_or_None).
    The index bytes are read with readinto, so the only allocation is the bitmap itself."""
    import struct
    with open(path, "rb") as f:
        hdr = f.read(16)
        if len(hdr) < 16 or hdr[:4] != b"PAL8":
            raise ValueError("%s is not a .pal8 file" % path)
        _, ver, flags, fw, fh, frames, ncol, _ = struct.unpack("<4sBBHHHHH", hdr)
        if ver != 1:
            raise ValueError("%s: unsupported .pal8 version %d" % (path, ver))
        pal = array.array("H", struct.unpack("<%dH" % ncol, f.read(2 * ncol)))
        data = bytearray(fw * frames * fh)
        got = f.readinto(data)
        if got != len(data):
            raise ValueError("%s: truncated (%d of %d index bytes)" % (path, got, len(data)))
    return pal, data, fw, fh, frames, (0 if flags & 1 else None)


def _build_bitmaps(pg, assets):
    bm = {}
    for aid, (fmt, data, bw, bh, frames, transp, pal) in assets.items():
        if fmt == "pal8f":
            # a .pal8 sidecar: the file is self-describing, game.json says what it expects
            pal, data, fw, fh, fr, ftransp = read_pal8(data)
            if (fw, fh, fr) != (bw, bh, frames):
                raise ValueError("%s is %dx%dx%d, game.json says %dx%dx%d for %r: Save in the "
                                 "editor or run scene_build.py art"
                                 % (assets[aid][1], fw, fh, fr, bw, bh, frames, aid))
            if transp is None:
                transp = ftransp
            palette = pal
        elif fmt == "pal8":
            palette = array.array("H", pal)
            if isinstance(data, str):             # older baked modules carry hex text
                data = bytes.fromhex(data)
        else:
            # this loader only knows how to rebuild PAL8 atlases; anything else
            # would be silently misinterpreted (wrong stride/format) - refuse.
            raise ValueError("asset %r: format %r not supported by this loader (PAL8 only)"
                             % (aid, fmt))
        bm[aid] = pg.Bitmap(data, bw, bh, format=pg.PAL8,
                            palette=palette, frames=frames, stride=bw * frames,
                            transparent=transp)
    return bm


def _build_sounds(sounds):
    """Best-effort: build one Audio + load each wav. Missing files/modules -> None
    samples (so the simulator, with no wavs, doesn't crash)."""
    audio = None
    out = {}
    if sounds:
        try:
            import picogame_audio
            audio = picogame_audio.Audio()
            for sid, path in sounds.items():
                try:
                    out[sid] = audio.load(path)
                except Exception:
                    out[sid] = None
        except Exception:
            audio = None
    return audio, out


def load_bank(pg, bank):
    """Build the shared asset bank ONCE; pass the result to load(..., bank=) for
    each level so the (unchanged) art/sounds aren't rebuilt per level."""
    audio, sounds = _build_sounds(bank.get("sounds"))
    return {"bitmaps": _build_bitmaps(pg, bank["assets"]),
            "tileprops": bank.get("tileprops", {}),
            "anims": bank.get("anims", {}),
            "audio": audio, "sounds": sounds}


def load(pg, scene, display=None, strip_h=None, font=None, bank=None, bufs=None):
    # Shared platform logic (board.DISPLAY / supervisor display / Framebuffer unwrap /
    # busdisplay) lives in picogame_game.resolve_display - ONE resolver for both entry points.
    import picogame_game
    backend, is_fb = picogame_game.resolve_display(display)
    if strip_h is None:
        strip_h = getattr(pg, "STRIP_H", 8)   # board default (8 DMA / 24 not)
    v = View()
    if is_fb:
        # framebuffer target: the scene composites straight into it - no strip buffers
        v.bufA = v.bufB = None
        v.scene = pg.Scene(backend, None, None, background=scene["bg"])
    else:
        try:
            backend.auto_refresh = False
        except (AttributeError, TypeError):
            pass
        try:
            backend.root_group = None
        except (AttributeError, TypeError):
            pass
        w = backend.width
        if bufs is not None:                  # strip buffers shared across levels (Game)
            v.bufA, v.bufB = bufs
        else:
            v.bufA = bytearray(w * strip_h * 2)
            v.bufB = bytearray(w * strip_h * 2)
        if getattr(pg, "FAST_DISPLAY_SUPPORTED", hasattr(pg, "Display")):
            backend = pg.Display(backend)
        v.scene = pg.Scene(backend, v.bufA, v.bufB, background=scene["bg"])

    if bank is not None:                      # shared bank: reuse its bitmaps/props/anims
        bitmaps = bank["bitmaps"]
        src_props = bank["tileprops"]
        anims = bank["anims"]
    else:                                     # standalone scene: build from its own assets
        bitmaps = _build_bitmaps(pg, scene["assets"])
        src_props = scene.get("tileprops", {})
        anims = scene.get("anims", {})
    # A per-load bytearray copy of the prop tables, so set_tile_prop can flip
    # flags at runtime without writing into the baked module or into a bank
    # shared by other levels - loading a level resets its tile meanings.
    v._props = {aid: {name: bytearray(b) for name, b in tabs.items()}
                for aid, tabs in src_props.items()}

    def _animate(sprite, aid, name):
        if aid in anims and name:
            import picogame_anim
            asp = picogame_anim.AnimatedSprite(sprite, anims[aid])
            asp.play(name)
            v.anims.append(asp)

    for layer in scene["layers"]:
        kind = layer[0]
        if kind == "tilemap":
            _, aid, cols, rows, ox, oy, grid = layer[:7]
            orient = layer[7] if len(layer) > 7 else None
            tm = pg.Tilemap(bitmaps[aid], cols, rows)
            tm.move(ox, oy)
            for i in range(len(grid)):
                gv = grid[i]
                if gv:
                    o = orient[i] if orient else 0
                    if o:
                        tm.set_tile(i % cols, i // cols, gv,
                                flip_x=bool(o & 1), flip_y=bool(o & 2), transpose=bool(o & 4))
                    else:
                        tm.set_tile(i % cols, i // cols, gv)
            v.scene.add(tm)
            if v._tm is None:                 # first (background) tilemap = primary
                v._tm = (tm, aid, cols, rows)
                v.tilemap = tm
                bm = bitmaps[aid]
                v._tile = (ox, oy, bm.width, bm.height)
        elif kind == "sprite":
            _, aid, name, x, y, ax, ay, frame, data = layer[:9]
            anim = layer[9] if len(layer) > 9 else None
            s = pg.Sprite(bitmaps[aid], x, y, frame=frame)
            s.anchor = (ax, ay)
            s.data = data
            if len(layer) > 10 and layer[10]:
                s.angle = layer[10]
            v.scene.add(s)
            if name:
                v.named[name] = s
            if len(layer) > 11 and layer[11]:     # a tagged single sprite joins its group
                v.groups.setdefault(layer[11], []).append(s)
            _animate(s, aid, anim)
        elif kind == "group":
            _, aid, tag, ax, ay, insts = layer[:6]
            anim = layer[6] if len(layer) > 6 else None
            lst = []
            for (x, y) in insts:
                s = pg.Sprite(bitmaps[aid], x, y)
                s.anchor = (ax, ay)
                v.scene.add(s)
                lst.append(s)
                _animate(s, aid, anim)
            if tag:
                v.groups.setdefault(tag, []).extend(lst)   # tagged singles may already be here
        elif kind == "particles":
            _, name, cap, size, gravity, fade = layer
            p = pg.Particles(cap, size=size, gravity=gravity, fade=fade)
            v.scene.add(p)
            if name:
                v.named[name] = p
        elif kind == "hudlabel":
            _, name, x, y, fg, bg = layer
            import picogame_ui as ui
            if font is None:
                # A hudlabel layer needs a font and CircuitPython always ships one, so default to
                # it here (as picogame_debug/picogame_cutscene do) rather than handing None to
                # SceneLabel - which failed deep in picogame_font on get_bounding_box, naming
                # neither the font nor the scene. font= stays for a custom/ExtraFont.
                import terminalio
                font = terminalio.FONT
            hl = ui.SceneLabel(v.scene, pg, font, x, y, fg, bg)
            if name:
                v.named[name] = hl
        else:
            raise ValueError("unknown layer kind: " + kind)

    if bank is not None:
        v.audio = bank.get("audio")
        v.sounds = bank.get("sounds", {})
    else:
        v.audio, v.sounds = _build_sounds(scene.get("sounds"))
    v.zones = scene.get("zones", [])
    v.points = scene.get("points", {})
    v.pdata = scene.get("pdata", {})
    music = scene.get("music")
    if music and v.audio and v.sounds.get(music):
        v.audio.music(v.sounds[music])
    v.camera = scene.get("camera")
    v.effects = scene.get("effects", [])
    v.world = scene.get("world")
    v._bind()
    return v


class Game:
    """A whole game's levels from ONE source: game.json (streamed, baked at boot) or a baked
    bank module (`scene_build.py build --mpy`). One call site either way:

        game = picogame_scene.Game(pg, "game.json", font=terminalio.FONT)
        view = game.load(game.start)          # ... later: view = game.load("cave", "entry")

    JSON mode bakes EVERY level at boot on a clean heap (measured 42-58 ms and ~4.5 kB per level
    on an RP2040) and then releases the baker; lazy=True keeps only the bank and bakes a level
    when it is loaded (skipping the others costs their parse time, not RAM). Module mode imports
    `<src>` for the BANK and `level_<name>` per load, dropping it from sys.modules afterwards, so
    only the current level stays resident. The strip buffers are allocated once and shared."""

    def __init__(self, pg, src, display=None, strip_h=None, font=None, lazy=False):
        self.pg = pg
        self.display = display
        self.strip_h = strip_h
        self.font = font
        self.levels = []          # level names in file order
        self.start = None
        self.size = (320, 240)
        self.name = None
        self.bank = None
        self._baked = {}          # name -> LEVEL (json mode, not lazy)
        self._offsets = {}        # name -> byte offset in game.json (lazy mode)
        self._bufs = None
        self._mod = None
        if src.endswith(".json"):
            self._path = src
            self._base = src.rsplit("/", 1)[0] if "/" in src else None
            self._lazy = lazy
            self._build_json()
        else:
            self._path = None
            self._mod = src
            self._build_module()

    # -- json mode ---------------------------------------------------------
    def _build_json(self):
        import picogame_scenebake as sb
        top = {}
        pending = []

        def on_level(lv, i, pos):
            name = lv.get("name") or "level%d" % (i + 1)
            self.levels.append(name)
            if self._lazy:
                self._offsets[name] = pos         # seek straight here later: no re-parse
                return
            if "assets" in top and "size" in top:
                # canonical order (small keys first): bake now and drop the tree at once
                self._baked[name] = sb.bake_level(lv, top["size"], top["assets"])
            else:
                pending.append((name, lv))        # levels before assets: bake after the walk

        with open(self._path, "rb") as f:
            sb.walk(f, on_level, None, top)
        self.size = tuple(top.get("size", self.size))
        self.name = top.get("name")
        self.start = top.get("start")
        assets = top.get("assets", {})
        for name, lv in pending:
            self._baked[name] = sb.bake_level(lv, self.size, assets)
        pending = None
        self.bank = load_bank(self.pg, sb.bake_bank(assets, top.get("sounds"), self._base))
        self._top_assets = assets if self._lazy else None
        if not self.start and self.levels:
            self.start = self.levels[0]
        if not self._lazy:
            import sys
            sys.modules.pop("picogame_scenebake", None)

    _top_assets = None

    def _find_level(self, name):
        """Lazy mode: seek to the level's remembered byte offset and bake just that one."""
        import picogame_scenebake as sb
        if name not in self._offsets:
            raise KeyError("game.json has no level %r (have %s)" % (name, self.levels))
        with open(self._path, "rb") as f:
            return sb.level_at(f, self._offsets[name], self.size, self._top_assets)

    # -- module mode -------------------------------------------------------
    def _build_module(self):
        mod = __import__(self._mod)
        bank = mod.BANK
        self.levels = list(bank.get("levels", ()))
        self.start = bank.get("start") or (self.levels[0] if self.levels else None)
        self.size = tuple(bank.get("size", self.size))
        self.name = bank.get("name")
        self.bank = load_bank(self.pg, bank)
        import sys
        sys.modules.pop(self._mod, None)

    def _level_module(self, name):
        import sys
        modname = "level_" + name
        mod = __import__(modname)
        lv = mod.LEVEL
        sys.modules.pop(modname, None)
        return lv

    # -- loading -----------------------------------------------------------
    def level(self, name):
        """The baked LEVEL dict for `name` (json: from the boot bake or a lazy walk; module:
        imported on demand)."""
        if self._mod is not None:
            return self._level_module(name)
        if name in self._baked:
            return self._baked[name]
        if self._lazy:
            return self._find_level(name)
        raise KeyError("no level %r (have %s)" % (name, self.levels))

    def load(self, name=None, at=None):
        """Build the View for level `name` (default: start). Drop every reference to the previous
        View (and call gc.collect()) BEFORE this, so its scene is freed first."""
        name = name or self.start
        lv = self.level(name)
        v = load(self.pg, lv, display=self.display, strip_h=self.strip_h, font=self.font,
                 bank=self.bank, bufs=self._bufs)
        if self._bufs is None and v.bufA is not None:
            self._bufs = (v.bufA, v.bufB)
        v.name = name
        if at:
            p = v.point(at)
            if p and "player" in v.named:
                v.named["player"].move(p[0], p[1])
        return v


def load_json(pg, path, display=None, strip_h=None, font=None, bank=None, release=True):
    """Bake a level's scene JSON and load it, in one call - the edit-and-rerun path.

    Skips the tools/scene_build.py step so a level can be iterated on as plain JSON. The reason
    this is a function and not three lines at module scope is MEASURED: the JSON text and the
    parse tree are several times the size of the finished SCENE, and as locals they die the moment
    this returns. Written out inline they stay reachable for the life of the program.

    Call it EARLY, before the big allocations - the peak here is transient, but the GC does not
    move objects, so a late spike leaves holes where the strip buffers want to go.

    `release=True` drops the baker module afterwards (~3.6 kB). Pass False when loading several
    levels in a row, then release it yourself after the last one.

    Colour-tileset levels only (see picogame_scenebake); PNG-backed art must be pre-baked.
    """
    import json
    import picogame_scenebake
    with open(path) as f:
        src = json.load(f)
    if "levels" in src:                       # a game.json project: first (start) level via Game
        src = None
        return Game(pg, path, display=display, strip_h=strip_h, font=font).load()
    base = path.rsplit("/", 1)[0] if "/" in path else None
    scene = picogame_scenebake.bake(src, base)
    if release:
        import sys
        del sys.modules["picogame_scenebake"]
    return load(pg, scene, display=display, strip_h=strip_h, font=font, bank=bank)
