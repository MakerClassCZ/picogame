# picogame_ray: a first-person raycaster (Wolfenstein-style corridors/dungeons)
# drawn into a buffer-less StripDraw view - a fake-3D mode at ZERO retained RAM,
# pure Python, no firmware change. A tile map of walls, solid distance-shaded
# columns via the engine's C fill_rect. Cast once per frame, then the Scene's
# per-strip refresh paints it.
#
#   rc = picogame_ray.Raycaster(MAP, wall_colors, sky, floor)
#   sd = pg.StripDraw(rc.draw, 0, 0, W, H)   ; scene.add(sd)
#   ...each frame: rc.cast(px, py, angle, W, H) ; scene.refresh()
# MAP = list of equal-length strings, '0' = empty, '1'..'9' = wall types.
#
# BILLBOARD SPRITES (enemies/pickups), depth-tested against the walls: cast()
# leaves a per-column wall z-buffer (rc.zbuf); project each sprite with
# project_sprite(worldx, worldy) and drive a pooled pg.Sprite from the result -
#   rc.cast(px, py, ang, W, H)
#   # A Scene draws in the order items were ADDED, so iterating your own list in sorted order
#   # does NOT reorder anything - sort, then write the sorted enemies into a FIXED list of
#   # sprites added once. The nearest lands in the last slot, which is drawn last, on top.
#   for e, spr in zip(sorted(enemies, key=lambda e: -e.dist2(px, py)), SLOTS):   # far-to-near
#       p = rc.project_sprite(e.wx, e.wy)
#       if p:
#           sx, size, e.d = p
#           spr.bitmap = e.bmp                      # the slot shows whoever it holds this frame
#           spr.x, spr.y = sx, HORIZON_Y            # anchor (0.5, 0.5)
#           e.spr.scale = size / BMP_H              # bitmap is BMP_H px tall
#           e.spr.visible = True
#       else:
#           e.spr.visible = False                   # off-screen or behind a wall
#   scene.refresh()
# The sprites must be add()ed to the Scene AFTER the StripDraw so they layer on
# top of the walls.
#
# PERF (RP2040): the DDA is native (pg.raycast); the Python cost is the once-per-frame
# run-length merge in cast() (adjacent identical columns -> one rect; a flat wall face
# facing you collapses to a single run) plus a cheap per-strip paint of those runs in
# draw(). The merge is deliberately HOISTED into cast(): it is strip-independent, and
# doing it per strip callback (the old layout) multiplied it by strips-per-frame (30x at
# strip_h=8 - measured 2.6x slower frames). Levers: `stride` casts one ray per N screen
# columns (2 = half the rays for a small loss in wall crispness; 3-4 for a big map or a
# slow board); attach() adds temporal repaint on top.
import math
from array import array

# The per-column DDA is the native engine primitive `picogame.raycast` (C on device, a Python
# implementation in the desktop sim's picogame - like Canvas.mode7). This lib is the DRIVER: it does
# the once-per-frame trig, hands the caster 16.16 ray params, then owns the paint, temporal
# invalidate, pose-cache and billboards. There is deliberately NO pure-Python DDA fallback here.
import picogame as _pg


class Raycaster:
    def __init__(self, world, wall_colors, sky, floor, fov=0.66, stride=2):
        # world: list of strings; wall_colors: {type_int: (near_color, side_color)}
        self.map = list(world)               # a copy set_cell() can rewrite rows of
        self.mw = len(world[0])
        self.mh = len(world)
        # flat int grid for the hot DDA loop: flat[y*mw+x] = wall type (0 = empty).
        # Avoids per-step nested indexing + 1-char string alloc + string compare.
        flat = bytearray(self.mw * self.mh)
        for y, row in enumerate(world):
            base = y * self.mw
            for x, ch in enumerate(row):
                flat[base + x] = 0 if ch == "0" else int(ch)
        self._flat = flat
        # colour table for the caster (C + fallback): _wc[t*2]=near, _wc[t*2+1]=side(far);
        # unknown wall type -> type 1 (matches the old wget default).
        maxt = max(wall_colors) if wall_colors else 1
        n1, f1 = wall_colors.get(1, (0, 0))
        wc = array("H", bytes(4 * (maxt + 1)))
        for t in range(maxt + 1):
            nc, fc = wall_colors.get(t, (n1, f1))
            wc[t * 2] = nc
            wc[t * 2 + 1] = fc
        self._wc = wc
        self.wall = wall_colors
        self.sky = sky
        self.floor = floor
        self.fov = fov
        self.stride = stride if stride > 0 else 1
        self.sw = self.sh = 0
        self.top = self.bot = self.col = self.zbuf = None
        # camera pose of the last cast(), cached for project_sprite()
        self._px = self._py = 0.0
        self._dirx = self._diry = self._planex = self._planey = 0.0
        # temporal dirty-band rendering (opt-in via attach()): the StripDraw + previous frame
        self._sd = None
        self._ptop = self._pbot = self._pcol = None
        self._cang = None                    # last cast() heading (pose-cache: skip re-cast if unchanged)
        # merged wall runs: the native caster emits them (pg.raycast runs plane) - x in PIXELS.
        # All per-frame buffers are PERSISTENT (allocated once per ncols, reused every cast: no
        # per-frame heap churn). Column arrays are DOUBLE-buffered (A/B swap) so the temporal
        # diff in _after_cast still sees the previous frame after the swap.
        self._r0 = self._r1 = self._rt = self._rb = self._rcol = None
        self._runs = None
        self._nruns = 0
        self._alloc = -1                     # ncols the buffers are sized for
        self._flip = False
        self._colbufs = None                 # ((topA,botA,colA), (topB,botB,colB))

    def attach(self, stripdraw):
        """Enable TEMPORAL (dirty-band) rendering. Pass the buffer-less StripDraw that draws
        this raycaster, created with ``always_dirty=False``. cast() then invalidates only the
        column band whose (top, bottom, colour) changed since the previous frame, so the Scene
        recomposites and pushes JUST those columns - unchanged columns keep last frame's pixels.
        Huge win when standing still / moving slowly (a lot of a raycast frame is identical to the
        last). Without attach() the layer full-repaints every frame (use ``always_dirty=True``)."""
        self._sd = stripdraw
        self._ptop = self._pbot = self._pcol = None    # force a full first repaint

    def solid(self, x, y):
        if 0 <= x < self.mw and 0 <= y < self.mh:
            return self._flat[y * self.mw + x] != 0    # _flat is the truth (set_cell mutates it)
        return True                          # out of bounds = wall

    def set_cell(self, x, y, v):
        """Change ONE world cell at runtime - a door opening, a wall dropping, a secret
        revealed. v = wall type 0-9 (0 = empty; string maps are single-digit by design).
        Keeps everything consistent: the C caster's grid, solid(), and .map (minimaps),
        and drops the pose cache so a STANDING camera still sees the change next frame.
        For EVENTS, not animation - each call forces one full re-cast; swapping dozens of
        cells per frame throws away the standing-still optimisation every frame."""
        if not (0 <= x < self.mw and 0 <= y < self.mh):
            return
        v = int(v)
        self._flat[y * self.mw + x] = v
        row = self.map[y]
        self.map[y] = row[:x] + str(v) + row[x + 1:]   # rare event -> the tiny alloc is fine
        self._cang = None                    # invalidate the pose cache (see cast())

    def cast(self, px, py, ang, sw, sh):
        """DDA one ray per `stride` screen columns; cache wall top/bottom/colour.
        Arrays are COMPACT (length ceil(sw/stride)); draw() expands them back."""
        # Pose-cache: if the camera hasn't moved since the last cast, the result is identical -
        # skip the whole DDA and leave nothing to invalidate (standing still = ~free).
        if (self.top is not None and px == self._px and py == self._py
                and ang == self._cang and sw == self.sw and sh == self.sh):
            return
        self.sw, self.sh = sw, sh
        stride = self.stride
        ncols = (sw + stride - 1) // stride
        # PERSISTENT buffers, sized once per ncols: two column sets (A/B, swapped each cast so
        # the temporal diff still sees the previous frame) + the zbuf + the runs planes. Zero
        # per-frame heap allocation (the old per-cast arrays churned ~3 KB/frame).
        if self._alloc != ncols:
            self._colbufs = (
                (array("H", bytes(2 * ncols)), array("H", bytes(2 * ncols)), array("H", bytes(2 * ncols))),
                (array("H", bytes(2 * ncols)), array("H", bytes(2 * ncols)), array("H", bytes(2 * ncols))),
            )
            self.zbuf = array("i", bytes(4 * ncols))
            runs = array("H", bytes(2 * 5 * ncols))    # five planes: [x0 | x1 | top | bot | col]
            mv = memoryview(runs)
            self._runs = runs
            self._r0 = mv[0:ncols]
            self._r1 = mv[ncols:2 * ncols]
            self._rt = mv[2 * ncols:3 * ncols]
            self._rb = mv[3 * ncols:4 * ncols]
            self._rcol = mv[4 * ncols:5 * ncols]
            self._ptop = self._pbot = self._pcol = None    # sizes changed: full repaint next
            self._alloc = ncols
            self._flip = False
        top, bot, col = self._colbufs[1 if self._flip else 0]
        self._flip = not self._flip
        # native caster (picogame.raycast: C on device, Python in the sim) - trig here, integer
        # DDA + RLE run merge in ONE native pass; NO Python fallback (required engine primitive).
        dirx = math.cos(ang)
        diry = math.sin(ang)
        planex = -diry * self.fov
        planey = dirx * self.fov
        k = 2.0 * stride / sw                          # camx step per column
        n = _pg.raycast(self._flat, self.mw, self.mh,
                        int(px * 65536), int(py * 65536),
                        int((dirx - planex) * 65536), int((diry - planey) * 65536),
                        int(planex * k * 65536), int(planey * k * 65536),
                        sh, stride, ncols, self._wc, top, bot, col, self.zbuf, self._runs)
        if self._r1[n - 1] > sw:
            self._r1[n - 1] = sw               # last run: stride rounding can overshoot the screen
        self._nruns = n
        self.top, self.bot, self.col = top, bot, col
        self._px, self._py = px, py
        self._cang = ang
        self._dirx, self._diry = dirx, diry
        self._planex, self._planey = planex, planey
        self._after_cast(top, bot, col, ncols, stride, sh)

    def _after_cast(self, top, bot, col, ncols, stride, sh):
        # TEMPORAL dirty band: attached to an always_dirty=False StripDraw, invalidate only the
        # column range that changed vs the previous frame (unchanged columns aren't repainted/pushed).
        sd = self._sd
        if sd is None:
            return
        ptop = self._ptop
        if ptop is None:
            sd.invalidate()                          # first frame: repaint the whole layer
        else:
            pbot = self._pbot
            pcol = self._pcol
            lo = -1
            hi = 0
            for c in range(ncols):
                if top[c] != ptop[c] or bot[c] != pbot[c] or col[c] != pcol[c]:
                    if lo < 0:
                        lo = c
                    hi = c + 1
            if lo >= 0:                              # invalidate only the changed column band
                sd.invalidate(lo * stride, 0, (hi - lo) * stride, sh)
            # lo < 0 -> nothing changed -> no invalidate -> layer not repainted this frame
        self._ptop = top
        self._pbot = bot
        self._pcol = col

    def project_sprite(self, sx, sy, margin=0.2):
        """Project world point (sx, sy) to a billboard for the LAST cast().
        Returns (screen_x, size, depth), or None if the point is behind the
        camera or hidden by a nearer wall at its centre column:
          screen_x - centre x in screen px
          size     - on-screen height in px, the SAME scale as the walls: set
                     your sprite's scale to size / bitmap_height
          depth    - perpendicular distance. Sort far-to-near on it, then write the
                     sorted entities into a FIXED list of Sprites you added to the
                     Scene once: draw order is ADD order, so sorting your own list
                     changes nothing on its own. The nearest goes in the last slot.
        Walls occlude via the per-column z-buffer (`margin` world units of slack
        so a sprite flush against a wall is not culled). The depth test is at the
        sprite's centre column only - right for a single billboard sprite: it is
        shown or hidden as a whole, not clipped per column. Call cast() first."""
        zbuf = self.zbuf
        if zbuf is None:
            return None
        relx = sx - self._px
        rely = sy - self._py
        det = self._planex * self._diry - self._dirx * self._planey
        if det == 0:
            return None
        inv = 1.0 / det
        ty = inv * (-self._planey * relx + self._planex * rely)   # depth along view dir
        if ty <= 0.02:
            return None                          # behind / on the camera plane
        tx = inv * (self._diry * relx - self._dirx * rely)        # lateral (plane units)
        screen_x = int((self.sw >> 1) * (1.0 + tx / ty))
        ci = screen_x // self.stride
        if 0 <= ci < len(zbuf) and int(ty * 65536) > zbuf[ci] + int(margin * 65536):
            return None                          # hidden behind a nearer wall (zbuf is 16.16)
        return screen_x, int(self.sh / ty), ty

    def draw(self, view, vx, vy, vw, vh):
        """StripDraw callback: sky/floor background for this band, then the pre-merged
        wall runs that cross it (the RLE merge runs once per frame in cast(), not here).

        ROW 0 IS THE TOP OF THE RAYCAST VIEW, not of the screen: the horizon sits at
        `sh >> 1` of the height you passed `cast()`, compared against `vy`. If your layer
        does NOT start at screen y=0 - the reserved-HUD-band pattern, `setup(top=BAND)` +
        `StripDraw(cb, 0, BAND, W, H - BAND)` - pass `vy - BAND`:

            def cb(view, vx, vy, vw, vh):
                rc.draw(view, vx, vy - BAND, vw, vh)

        Without it the whole view renders BAND pixels too high: the top of the picture hides
        under the HUD and a strip of bare floor colour is left at the bottom. The alternative
        is to keep the view full-screen (`cast(..., H)`, layer at y=0) and float the HUD over
        it as fixed SceneLabels - costs no view height, which suits a first-person game."""
        if self.top is None:
            return
        fr = view.fill_rect
        half = self.sh >> 1
        y0 = vy
        y1 = vy + vh
        # background: sky above the horizon, floor below (split at screen mid)
        if y1 <= half:
            fr(0, 0, vw, vh, self.sky)
        elif y0 >= half:
            fr(0, 0, vw, vh, self.floor)
        else:
            fr(0, 0, vw, half - y0, self.sky)
            fr(0, half - y0, vw, y1 - half, self.floor)
        # walls: paint the pre-merged runs clipped to THIS region in ONE Python/C crossing -
        # the engine's Canvas.vspans batch primitive (x_off/y_off = negated strip origin, like
        # the fill_triangles replay). The per-strip cost does not scale with the run count.
        # vspans is a REQUIRED engine primitive (like pg.raycast - no Python fallback).
        view.vspans(self._r0, self._r1, self._rt, self._rb, self._rcol, self._nruns, -vx, -vy)
