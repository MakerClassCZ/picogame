# picogame_road: the missing wrapper around the native racing-road pair (pg.road_edges +
# Canvas.road) - the same job picogame_mode7.Camera does for Canvas.mode7: nobody should
# hand-feed Q16/Q20 fixed-point tables from the reference. Owns everything the raw pair leaves
# to the caller: the per-row perspective tables (hw/tab), cfg from HUMAN units (curve periods in
# world units, swing in pixels), the int32-safe phase wrap (power-of-two periods, dist wrapped by
# the longest - an arbitrary period makes the road JUMP every ~2^31 of phase), hills as a moving
# horizon with the table headroom that needs, and the two queries gameplay always ends up
# re-deriving: curve_at() for physics/AI and row_of()/half_of() for placing sprites ON the road.
#
# Zero allocation per frame: all arrays are built once in __init__; tick() writes rl/rr in place.
# Needs firmware/sim with the native pair (upstream engine, sim, and the WASM playground all
# have it, bit-identically - the sim golden-tests them).
#
#   road = picogame_road.Road(pg, W, H, horizon=H // 3,
#                             colors=dict(sky=..., road_a=..., road_b=...,
#                                         rumble_a=..., rumble_b=..., dash=...))
#   def draw(view, vx, vy, vw, vh):
#       road.draw(view, vy)                     # StripDraw callback body (0-RAM road)
#   scene.add(pg.StripDraw(draw, 0, 0, W, H))
#   while True:
#       dist += speed
#       road.tick(dist, lateral_px)             # once per frame, before refresh
#       steer -= road.curve_at(dist) * grip     # centrifugal pull from the SAME curve model
#       scene.refresh()

import math
from array import array

_Q16 = 65536
_DEG_Q20 = 360 * (1 << 20)


def _pow2(v):
    # round a period to the NEAREST power of two - f = 360*2^20/P stays exact and every
    # phase wraps continuously when dist wraps by the longest period (the int32 contract)
    p = 1
    while p < v:
        p <<= 1
    return p if (p - v) <= (v - (p >> 1)) else (p >> 1)


class Road:
    def __init__(self, pg, width, height, horizon, colors, *,
                 half_width=0.47, hw_min=6.0, depth=600.0,
                 curves=((16384, 90.0), (4096, 30.0)),
                 world_step=6, curve_step=2, hill_amp=0, edge_frac=0.12, dash_frac=0.07,
                 dash_min_hw=7.0, band=20.0, dash_band=14.0):
        """width/height/horizon in px (horizon = first road row). colors = dict with sky,
        road_a, road_b, rumble_a, rumble_b, dash (wire-RGB565 from pg.rgb565).
        The perspective is the DEVICE-PROVEN picobike model: half-width grows QUADRATICALLY
        from `hw_min` px at the horizon to `half_width * width` at the bottom (the OutRun
        hug-the-horizon-then-flare look), and the stripe phases sample a road `depth` world
        units deep. curves = up to two (period_world_units, swing_px) pairs - period is
        rounded to the NEAREST power of two (phase-wrap safety), swing = how far the road tip
        bends sideways at full curvature. hill_amp = max horizon shift in px (0 = flat game);
        give the StripDraw hill_amp px of headroom ABOVE the horizon, this class sizes its
        tables for it. edge_frac/dash_frac = rumble/dash width as a fraction of the row's
        half-width; rows narrower than `dash_min_hw` px draw no dashes. band/dash_band =
        world units per road-colour stripe / centre-dash cycle."""
        self.pg = pg
        self.w = width
        self.horizon = horizon
        self.hill_amp = hill_amp
        n = (height - horizon) + hill_amp        # rows incl. downhill headroom
        self.rows = n
        self._pitch = 0
        self.rl = array("h", bytes(2 * n))
        self.rr = array("h", bytes(2 * n))
        self._hw = array("i", bytes(4 * n))
        self._tab = array("h", bytes(2 * 5 * n))
        nrow = height - horizon                  # nominal (flat) row count for perspective
        self._nrow = nrow
        hw_max = width * half_width
        for i in range(n):
            t = (i + 1) / nrow                   # 0 at horizon, 1 at bottom (>1 in headroom)
            hw = hw_min + (hw_max - hw_min) * (t * t)     # quadratic + floor: the proven look
            self._hw[i] = int(hw * _Q16)
            wb = (1.0 - t) * depth               # world distance of this row up the road
            self._tab[i * 5] = max(1, int(hw * edge_frac))
            self._tab[i * 5 + 1] = max(1, int(hw * dash_frac))
            self._tab[i * 5 + 2] = int(wb * 256.0 / band)        # SIGNED: hill-headroom rows sit
            self._tab[i * 5 + 3] = int(wb * 256.0 / dash_band)   #  slightly PAST the car (wb < 0)
            self._tab[i * 5 + 4] = 1 if hw > dash_min_hw else 0
        self.colors = array("H", (colors["sky"], colors["road_a"], colors["road_b"],
                                  colors["rumble_a"], colors["rumble_b"], colors["dash"]))
        # cfg from human units. ck accumulates ddx per row, so the tip's lateral swing after
        # k rows is amp * k*(k+1)/2 (Q16 px) - invert that so `swing_px` means what it says.
        cs = list(curves)[:2] + [(1, 0.0)] * (2 - len(curves[:2]))
        self._periods = []
        cfg = []
        gain = 2.0 / (nrow * (nrow + 1))         # 1 / sum(1..nrow)
        for period, swing in cs:
            p2 = _pow2(max(2, int(period)))
            self._periods.append(p2)
            cfg.append(_DEG_Q20 // p2)           # exact -> phase continuous across the wrap
        for _, swing in cs:
            cfg.append(int(swing * gain * _Q16))
        cfg += [world_step, curve_step, nrow - 1]   # NOMINAL bottom row samples dist exactly (hill headroom rows sample slightly past it, as picobike does)
        self.cfg = array("i", cfg)
        self._wrap = max(self._periods)
        self._world_step = world_step
        self._band = band
        self._dash_band = dash_band
        self._d05 = 0
        self._d07 = 0
        # curve_at() precomputes: radians per world unit + normalised amplitudes (zero-alloc call)
        self._w1 = math.radians(_DEG_Q20 // self._periods[0] / (1 << 20))
        self._w2 = math.radians(_DEG_Q20 // self._periods[1] / (1 << 20))
        total = (cs[0][1] + cs[1][1]) or 1.0
        self._a1 = cs[0][1] / total
        self._a2 = cs[1][1] / total

    def tick(self, dist, lateral_px=0):
        """Run the frame's curve pass. dist = world distance travelled (any int - wrapped
        internally, phases stay continuous). lateral_px = player's sideways offset in px
        (positive shifts the road left, i.e. the car moves right)."""
        d = int(dist) % self._wrap
        # stripe phases wrap by their OWN cycle (2 stripes = one full parity period), so a
        # forever-growing dist never breeds big-ints on MicroPython and the pattern stays
        # continuous for any monotone dist
        self._d05 = int((dist % (2.0 * self._band)) * 256.0 / self._band)
        self._d07 = int((dist % (2.0 * self._dash_band)) * 256.0 / self._dash_band)
        self.pg.road_edges(self.rl, self.rr, self._hw, self.rows,
                           (self.w // 2 - int(lateral_px)) * _Q16, d, self.cfg)

    def set_grade(self, grade):
        """Hills: grade -1..+1 (downhill positive lifts the horizon -> more road visible).
        Feed grade into your speed too (speed += grade * pull) - a hill you can only see is
        scenery. Needs hill_amp > 0 at construction."""
        self._pitch = -int(grade * self.hill_amp)

    @property
    def horizon_now(self):
        """This frame's effective horizon row (horizon + hill pitch) - for overlays that map
        their own rows onto the road (a finish chequer, roadside sprites)."""
        return self.horizon + self._pitch

    def draw(self, view, vy):
        """StripDraw callback body: draw this strip's sky + road rows. Grass: the scene
        background (Scene clears each strip to it), or fill the view yourself first."""
        view.road(vy - self.horizon_now, self._tab, self.rl, self.rr,
                  self._d05, self._d07, self.colors)

    # --- gameplay queries (the same curve model the C runs) -----------------
    def curve_at(self, dist):
        """Signed curvature -1..+1 at a world distance - for centrifugal pull, AI steering,
        a minimap. Mirrors the C's two-sine field, normalised by the total swing.
        Zero-alloc: call it per car per frame freely."""
        d = dist % self._wrap
        return math.sin(d * self._w1) * self._a1 + math.sin(d * self._w2) * self._a2

    def row_of(self, z):
        """Table row for a point z world units ahead. Row `nrow - 1` (the NOMINAL bottom -
        the same row the curve sampling anchors `dist` at) is the car; hill-headroom rows
        lie PAST it. None when beyond the horizon. Screen y = horizon_now + row.
        NOTE the depth scale: rows step `world_step` wu apiece here (matching the drawn
        EDGES/curves), while the surface stripes scroll on the `depth`-model (~depth/rows
        wu per row) - picobike's historical split. For stripe-consistent sprite motion set
        world_step ~= depth / (height - horizon) at construction."""
        i = self._nrow - 1 - int(z // self._world_step)
        return i if 0 <= i < self.rows else None

    def half_of(self, row):
        """Road half-width in px at a table row - scale roadside sprites by
        half_of(row) / half_of(rows - 1) instead of F/(F+z) (the rows are LINEAR)."""
        return self._hw[row] >> 16

    def edges_of(self, row):
        """(left, right) screen x of the road at a table row, this frame - place traffic
        between them so it follows the curves."""
        return self.rl[row], self.rr[row]
