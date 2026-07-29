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
#   for e in sorted(enemies, key=lambda e: -e.dist2(px, py)):   # far-to-near
#       p = rc.project_sprite(e.wx, e.wy)
#       if p:
#           sx, size, e.d = p
#           e.spr.x, e.spr.y = sx, HORIZON_Y        # anchor (0.5, 0.5)
#           e.spr.scale = size / BMP_H              # bitmap is BMP_H px tall
#           e.spr.visible = True
#       else:
#           e.spr.visible = False                   # off-screen or behind a wall
#   scene.refresh()
# The sprites must be add()ed to the Scene AFTER the StripDraw so they layer on
# top of the walls.
#
# PERF (RP2040): the whole thing is interpreted Python, so the two hot loops -
# the per-column DDA and the per-strip wall paint - dominate. Three levers keep
# it playable: `stride` casts one ray per N screen columns (2 = half the rays
# AND half the fill_rects for a small loss in wall crispness), the draw pass
# run-length-merges adjacent identical columns into one wide fill_rect (a flat
# wall face facing you collapses to a single rect), and both loops hoist every
# attribute to a local. Bump `stride` to 3-4 on a big map or a slow board.
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
        self.map = world
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
            return self.map[y][x] != "0"
        return True                          # out of bounds = wall

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
        # native caster (picogame.raycast: C on device, Python in the sim) - trig here, integer DDA
        # into the buffers; NO Python fallback (the caster is a required engine primitive).
        dirx = math.cos(ang)
        diry = math.sin(ang)
        planex = -diry * self.fov
        planey = dirx * self.fov
        top = array("H", bytes(2 * ncols))
        bot = array("H", bytes(2 * ncols))
        col = array("H", bytes(2 * ncols))
        zb = array("i", bytes(4 * ncols))            # perpendicular distance, 16.16
        k = 2.0 * stride / sw                          # camx step per column
        _pg.raycast(self._flat, self.mw, self.mh,
                    int(px * 65536), int(py * 65536),
                    int((dirx - planex) * 65536), int((diry - planey) * 65536),
                    int(planex * k * 65536), int(planey * k * 65536),
                    sh, stride, ncols, self._wc, top, bot, col, zb)
        self.top, self.bot, self.col, self.zbuf = top, bot, col, zb
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
          depth    - perpendicular distance; sort your sprites far-to-near on it
                     before positioning them, so nearer ones draw on top.
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
        """StripDraw callback: sky/floor background for this band, then the wall
        column runs that cross it. Adjacent equal columns merge into one rect."""
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
        # walls: run-length-merge adjacent identical columns, clipped to THIS region.
        # The region may be a horizontal sub-rect (vx>0, vw<full) when temporal rendering
        # invalidated only a column band - so map column screen-x to view-local (x - vx).
        top = self.top
        bot = self.bot
        col = self.col
        stride = self.stride
        ncols = len(top)
        rx1 = vx + vw
        c = vx // stride                         # first column touching the region
        c_end = (rx1 + stride - 1) // stride      # one past the last
        if c_end > ncols:
            c_end = ncols
        while c < c_end:
            t = top[c]
            b = bot[c]
            cc = col[c]
            c2 = c + 1
            while c2 < c_end and top[c2] == t and bot[c2] == b and col[c2] == cc:
                c2 += 1
            st = t if t > y0 else y0
            sb = b if b < y1 else y1
            if sb > st:
                sx0 = c * stride
                sx1 = c2 * stride
                if sx0 < vx:
                    sx0 = vx
                if sx1 > rx1:
                    sx1 = rx1
                if sx1 > sx0:
                    fr(sx0 - vx, st - vy, sx1 - sx0, sb - st, cc)
            c = c2
