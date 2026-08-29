# picogame declarative-scene loader: build a ready Scene from a baked SCENE dict
# (see SCENE_FORMAT.md + tools/scene_build.py). Uses only the
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

    def _prop_bytes(self, name):
        if self._tm is None:
            return None
        return self._props.get(self._tm[1], {}).get(name)

    def is_solid(self, tx, ty):
        return self.tile_has(tx, ty, "solid")

    def tile_has(self, tx, ty, prop):
        b = self._prop_bytes(prop)
        if b is None or self._tm is None:
            return False
        return bool(b[self._tm[0].get_tile(tx, ty)])


def _build_bitmaps(pg, assets):
    bm = {}
    for aid, (fmt, hexdata, bw, bh, frames, transp, pal) in assets.items():
        if fmt != "pal8":
            # this loader only knows how to rebuild PAL8 atlases; anything else
            # would be silently misinterpreted (wrong stride/format) - refuse.
            raise ValueError("asset %r: format %r not supported by this loader (PAL8 only)"
                             % (aid, fmt))
        palette = array.array("H", pal)
        bm[aid] = pg.Bitmap(bytes.fromhex(hexdata), bw, bh, format=pg.PAL8,
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


def load(pg, scene, display=None, strip_h=None, font=None, bank=None):
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
        v.bufA = bytearray(w * strip_h * 2)
        v.bufB = bytearray(w * strip_h * 2)
        if getattr(pg, "FAST_DISPLAY_SUPPORTED", hasattr(pg, "Display")):
            backend = pg.Display(backend)
        v.scene = pg.Scene(backend, v.bufA, v.bufB, background=scene["bg"])

    if bank is not None:                      # shared bank: reuse its bitmaps/props/anims
        bitmaps = bank["bitmaps"]
        v._props = bank["tileprops"]
        anims = bank["anims"]
    else:                                     # standalone scene: build from its own assets
        bitmaps = _build_bitmaps(pg, scene["assets"])
        v._props = scene.get("tileprops", {})
        anims = scene.get("anims", {})

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
                v.groups[tag] = lst
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
        scene = picogame_scenebake.bake(json.load(f))
    if release:
        import sys
        del sys.modules["picogame_scenebake"]
    return load(pg, scene, display=display, strip_h=strip_h, font=font, bank=bank)
