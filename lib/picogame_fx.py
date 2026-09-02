# picogame_fx - juice helpers built on the engine (no firmware change needed):
#   * Shake - trauma-model screen shake (Eiserloh) that COMPOSES with your camera.
#   * Fade  - dither screen fade / dim / flash (a StripDraw overlay, 0 bytes, no alpha
#              needed; looks like a classic 1-bit/Game Boy fade).
# Both validated in the simulator. The numbers (shake max_offset/decay, fade cell/step) are tuned in
# the picogame-game-design skill's technique recipes.

import array

import picogame as pg

# The panel's RESTING colour-inversion state (True if its init sends INVON, like the PicoPad).
# InvertFlash defaults to this when its `normal` arg is left None, so the hardware hit-flash is
# correct on any board. The display can't report this (busdisplay has no invert read-back), so it
# follows PICOGAME_INVERT from settings.toml when set (a custom board's config), else True (PicoPad).
def _panel_inverted_default():
    import os
    v = os.getenv("PICOGAME_INVERT")
    if v is None:
        return True                                  # PicoPad and most ST7789 boards send INVON
    return (v != 0) if isinstance(v, int) else v.strip().lower() not in ("", "0", "false", "no")


PANEL_INVERTED = _panel_inverted_default()

# 4x4 ordered (Bayer) dither matrix, thresholds 0..15.
_BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


class Shake:
    """Trauma-model screen shake. Bump trauma on impacts (`add`), then call `tick(cam_x,
    cam_y)` every frame: it adds a decaying random offset ON TOP of your camera and applies
    the combined view via `scene.set_view`, so shake and a moving camera don't fight.

    STRIP-RENDERED games (road, raycaster, mode-7): `set_view` never moves a StripDraw -
    the "camera" lives in your renderer's parameters, and so does its shake. Pass
    `scene=None`: tick() then only updates `self.ox`/`self.oy` (the frame's offset) and you
    spend them yourself - `road.tick(dist, lateral + sh.ox)`, a horizon jittered by `sh.oy`,
    a raycaster angle nudged by `sh.ox * 0.002`. Same trauma model, your camera.

    trauma is squared before use (Eiserloh) so small events barely shake and big ones slam.
    `max_offset` ~6 px suits 320x240 (>10 hides the action). `decay` is trauma lost per frame
    (~0.03 = 0.9/sec at 30 fps -> a 'kick', not a 'rumble'). Amounts: 0.6 = a small kick,
    0.8 = a hit, 1.0 = a big impact. Below ~0.5 the squared offset is under one pixel at
    max_offset 6 (0.4 -> 0.96 px), i.e. invisible - it only costs the full repaints."""

    def __init__(self, scene, max_offset=6, decay=0.03, seed=0x9E37):
        self.scene = scene                           # None = offset-only mode (StripDraw games)
        self.max = max_offset
        self.decay = decay
        self.trauma = 0.0
        self.ox = 0                                  # the frame's applied offset, always readable
        self.oy = 0
        self._r = seed & 0xFFFF

    def _rnd(self):                                  # tiny 16-bit LCG -> -1.0 .. +1.0
        # 16-bit state + a multiplier under 2^14 keep every intermediate below MicroPython's
        # 31-bit small-int limit, so a per-frame shake allocates NO transient big-ints (a>0
        # is ==1 mod 4 and c odd -> full 65536 period; quality is plenty for screen jitter).
        self._r = (self._r * 12345 + 12345) & 0xFFFF
        return (self._r % 2001 - 1000) / 1000.0

    def add(self, amount):
        """Add trauma (0..1): 0.6 = a small kick, 0.8 = a hit/explosion, 1.0 = a big impact.
        Under ~0.5 nothing visibly moves (sub-pixel at max_offset 6)."""
        self.trauma = min(1.0, self.trauma + amount)

    def tick(self, cam_x=0, cam_y=0):
        """Apply shake on top of (cam_x, cam_y). Returns True while still shaking."""
        if self.trauma <= 0.0:                       # idle: track the camera, but skip the RNG
            self.ox = self.oy = 0
            if self.scene is not None:
                self.scene.set_view(cam_x, cam_y)     # (no per-frame _rnd() calls when not shaking)
            return False
        sh = self.trauma * self.trauma
        self.ox = int(self.max * sh * self._rnd())
        self.oy = int(self.max * sh * self._rnd())
        if self.scene is not None:
            self.scene.set_view(cam_x + self.ox, cam_y + self.oy)
        self.trauma = max(0.0, self.trauma - self.decay)
        return self.trauma > 0.0


class Flash:
    """The 1-3 frame hit-flash, without the ordering trap.

    Hand-rolled counters get this wrong: set `n = 2` in the collision pass and decrement it in
    the entity pass, and the sprite renders flashed for exactly ONE frame - the count is spent
    before the frame it was meant to cover. `Flash` counts DRAWN frames: `hit()` arms it, `tick()`
    runs ONCE per frame after the logic and before refresh(), and the sprite stays lit for exactly
    the frames you asked for.

        fl = fx.Flash(enemy)
        if hit: fl.hit(WHITE, 2)          # anywhere in the frame, any number of times
        ...
        fl.tick(); scene.refresh()

    Mind the shared effect slot: a truthy flash clears an active tint/dither/shadow, so when the
    flash ends this puts back whatever the sprite wore before it."""

    __slots__ = ("sprite", "t", "_prev_mode", "_prev_val")

    def __init__(self, sprite):
        self.sprite = sprite
        self.t = 0
        self._prev_mode = None
        self._prev_val = None

    def hit(self, color, frames=2):
        """Arm (or re-arm) the flash. Safe to call several times in one frame."""
        s = self.sprite
        if self.t <= 0:                      # remember what the sprite wore before the flash
            if s.tint:
                self._prev_mode, self._prev_val = "tint", s.tint
            elif s.dither:
                self._prev_mode, self._prev_val = "dither", s.dither
            elif s.shadow:
                self._prev_mode, self._prev_val = "shadow", True
            else:
                self._prev_mode = None
        if frames > self.t:
            self.t = frames
        s.flash = color

    def tick(self):
        """Call once per frame after the logic. True while the flash is still showing."""
        if self.t <= 0:
            return False
        self.t -= 1
        if self.t <= 0:
            s = self.sprite
            s.flash = 0                      # falsy write clears ONLY the flash slot
            m = self._prev_mode
            if m == "tint":
                s.tint = self._prev_val
            elif m == "dither":
                s.dither = self._prev_val
            elif m == "shadow":
                s.shadow = True
            self._prev_mode = None
            return False
        return True


class Fade:
    """Dither screen fade / dim / flash. A StripDraw overlay that stipples `color` over the
    screen with an ordered (Bayer) dither at block size `cell` - no alpha blending needed.
    `level` 0 = clear .. 16 = solid. Idle (level 0) it collapses to a 0x0 rect so it costs
    nothing on the device's dirty-rect renderer.

    Typical use:
        fade = Fade(scene, W, H)            # black, added on top, starts clear
        fade.set(16)                        # start opaque (for a fade-IN)
        ...each frame:  done = fade.tick()
        fade.out()                          # fade to black (e.g. on game over)
        fade.into()                         # fade back to clear
        fade.dim(8)                         # hold a 50% dim behind a menu
    A WHITE Fade pulsed quickly is a full-screen hit-flash:  Fade(scene,W,H,color=WHITE).pulse()
    """

    LEVELS = 16

    def __init__(self, scene, width, height, x=0, y=0, color=0, cell=8):
        # x/y/width/height = the screen RECT to cover. Defaults (0,0,W,H) = whole screen
        # (transitions, menu dim). A sub-rect dims just that area: a panel behind a dialog,
        # a darkened side bar, a crude fog patch.
        self.scene = scene
        self.X = x
        self.Y = y
        self.W = width
        self.H = height
        self.color = color
        self.cell = cell
        self.level = 0.0
        self.target = 0.0
        self.speed = 2.0
        self._hold = 0                                   # frames to stay at full before fading
        self._pulse = None                               # ramp-up target for pulse() (auto-reverses)
        self._active = False                             # is the overlay currently shown?
        # always_dirty=False + invalidate-on-change: a HELD dim (menu/pause) costs ~0/frame -
        # the overlay recomposites only where other layers dirty under it. The dither pattern
        # depends only on int(level), so repaints are driven by _mark() below.
        self.sd = pg.StripDraw(self._draw, 0, 0, 0, 0, always_dirty=False)   # collapsed until active
        scene.add(self.sd, fixed=True)                          # fixed: ignore the camera
        # Pre-merged x-runs of LIT dither cells per Bayer row phase (4 phases), rebuilt only
        # when int(level) changes; _draw paints them with ONE Canvas.vspans call per cell row
        # (1-2 per strip) instead of a Python loop + fill_rect per cell (~1200 crossings/frame).
        ncell = (width + cell - 1) // cell + 1
        self._rx0 = [array.array("H", bytes(2 * ncell)) for _ in range(4)]
        self._rx1 = [array.array("H", bytes(2 * ncell)) for _ in range(4)]
        self._rn = [0, 0, 0, 0]
        self._rt = array.array("H", bytes(2 * ncell))               # tops: all 0
        self._rb = array.array("H", [cell] * ncell)                 # bots: all `cell`
        self._rc = array.array("H", [color & 0xFFFF] * ncell)       # colors: all `color`
        self._built = -1                                            # int(level) the runs are built for

    def _rebuild(self, lvl):
        # Rebuild the lit-cell x-runs for dither level `lvl` (screen-aligned cell grid, so a
        # cell's Bayer phase is (screen_x // cell) & 3). Adjacent lit cells merge into one run.
        S = self.cell
        bx0 = self.X // S
        bx1 = (self.X + self.W - 1) // S
        bayer = _BAYER
        for r in range(4):
            brow = bayer[r]
            x0 = self._rx0[r]
            x1 = self._rx1[r]
            n = 0
            run = -1
            for bx in range(bx0, bx1 + 1):
                if brow[bx & 3] < lvl:
                    if run < 0:
                        run = bx
                else:
                    if run >= 0:
                        x0[n] = run * S
                        x1[n] = bx * S
                        n += 1
                        run = -1
            if run >= 0:
                x0[n] = run * S
                x1[n] = (bx1 + 1) * S
                n += 1
            self._rn[r] = n
        self._built = lvl

    def _mark(self):
        # Repaint when the DRAWN pattern changed (int(level) moved). always_dirty=False makes
        # this the only trigger besides other layers dirtying the overlapped region.
        lvl = int(self.level)
        if lvl != self._built and self._active:
            self.sd.invalidate()

    def _activate(self, on):
        self._active = on
        self.sd.x = self.X
        self.sd.y = self.Y
        self.sd.width = self.W if on else 0
        self.sd.height = self.H if on else 0
        if on:
            self.sd.invalidate()                          # first paint (always_dirty=False)
        else:
            self.scene.invalidate()                       # clean repaint once removed

    def to(self, target, speed=2.0):
        self.target = max(0.0, min(float(self.LEVELS), float(target)))
        self.speed = speed
        if self.target > 0 or self.level > 0:
            self._activate(True)
        return self

    def out(self, speed=2.0):                              # -> opaque
        """Fade to FULLY opaque - a solid wall of `color` that hides everything under it. That is
        what a scene transition wants; it is NOT what a game-over screen wants, because the message
        you are fading in goes under it too. For a darkened-but-readable backdrop use `dim(level)`
        (or `pulse(peak)` for a flash), where a level below 16 stays a see-through dither."""
        return self.to(self.LEVELS, speed)

    def into(self, speed=2.0):                             # -> clear
        return self.to(0.0, speed)

    def set(self, level):
        self.level = self.target = max(0.0, min(float(self.LEVELS), float(level)))
        self._activate(self.level > 0)
        self._mark()
        return self

    def dim(self, level=8):                                # hold a partial dim (menus)
        return self.set(level)

    def clear(self):
        return self.set(0)

    def pulse(self, level=12, speed=2.0):                 # RAMP up to the peak, then back to 0
        # The smooth fxdemo-style flash: ramp the dither UP to `level` then back DOWN at `speed`
        # (levels/frame), instead of SNAPPING on (which read as too abrupt/strong). peak<16 keeps
        # it a see-through dither even at its strongest - never a solid wall of colour.
        # CLAMP the stored peak to the achievable range: to() caps target at LEVELS, so an
        # out-of-range peak (pulse(20)) would never satisfy `level >= _pulse` and the flash
        # would stay opaque forever. speed is clamped positive for the same reason.
        peak = self.LEVELS if level is None else max(0.0, min(float(self.LEVELS), float(level)))
        self._pulse = peak
        return self.to(peak, max(0.01, speed))

    @property
    def is_done(self):
        return self.level == self.target

    def tick(self):
        """Step level toward target by `speed`. Returns True when the target is reached."""
        if self._hold > 0:                   # hold at the current level (a flash's "pop")
            self._hold -= 1
            return False
        if self.level == self.target and self._pulse is None:
            return True                      # idle or held: nothing moves, nothing to repaint
        if self.level < self.target:
            self.level = min(self.target, self.level + self.speed)
        elif self.level > self.target:
            self.level = max(self.target, self.level - self.speed)
        if self._pulse is not None and self.level >= self._pulse:   # pulse hit its peak -> fall back
            self.target = 0.0
            self._pulse = None
        if self.level <= 0 and self.target <= 0 and self._active:
            self._activate(False)        # deactivate ONCE on reaching idle - NOT every idle frame
        else:
            self._mark()                 # repaint only when int(level) moved this tick
        return self.level == self.target  # (the every-frame scene.invalidate() flickered HUDs)

    def _draw(self, view, vx, vy, vw, vh):
        lvl = int(self.level)
        if lvl <= 0:
            return
        if lvl != self._built:
            self._rebuild(lvl)
        S = self.cell
        vs = view.vspans
        by0, by1 = vy // S, (vy + vh - 1) // S
        rx0 = self._rx0
        rx1 = self._rx1
        rn = self._rn
        for by in range(by0, by1 + 1):                 # 1-2 cell rows per strip: ONE vspans each
            r = by & 3
            n = rn[r]
            if n:
                vs(rx0[r], rx1[r], self._rt, self._rb, self._rc, n, -vx, by * S - vy)


class Tween:
    """Ease a scalar toward a target - UI slides, pop-up scales, zoom, a value that should
    'catch up' smoothly. Cheap per-frame exponential ease-out (no schedule/keyframes).

        t = Tween(0)
        t.to(100)                  # head for 100
        ...each frame: y = t.tick()
    """

    def __init__(self, value=0.0, speed=0.2):
        self.value = float(value)
        self.target = float(value)
        self.speed = speed                          # 0..1: fraction of the gap closed per frame

    def to(self, target, speed=None):
        self.target = float(target)
        if speed is not None:
            self.speed = speed
        return self

    def set(self, value):
        self.value = self.target = float(value)
        return self

    @property
    def is_done(self):
        return self.value == self.target

    def tick(self):
        self.value += (self.target - self.value) * self.speed
        if abs(self.target - self.value) < 0.01:    # snap when close enough
            self.value = self.target
        return self.value


class Camera:
    """A smoothed follow camera. Tracks a world point and produces the scene view offset
    (centred, optionally clamped to a world size). Compose with Shake by feeding the camera
    offset into shake.tick(); or call apply() directly when there's no shake.

        cam = Camera(scene, W, H, world_w=MAP_W, world_h=MAP_H)
        cam.follow(player.x, player.y)
        cam.apply()                                  # no shake
        # --- or with shake: ---
        ox, oy = cam.follow(player.x, player.y).offset()
        shaker.tick(ox, oy)

    `w`/`h` are the SCREEN size. A scene built with a reserved HUD band (`Scene(top=BAR)` /
    `picogame_game.setup(top=BAR)`) never scrolls those rows, so pass the same band here
    (`top=BAR`, and `bottom`/`left`/`right` alike): the camera then centres on the rows that
    actually show the world and clamps so world 0 lands at the band's inner edge and the far
    edge is reachable. Padding `h` by the band instead fixes the centre but not the clamp -
    the view stops BAR px short of the world's end. The firmware Scene does not expose its
    band, which is why it is stated here again; the simulator flags a mismatch.
    """

    def __init__(self, scene, w, h, lerp=0.18, world_w=0, world_h=0,
                 top=0, bottom=0, left=0, right=0):
        self.scene = scene
        self.w = w
        self.h = h
        self.lerp = lerp
        # the visible play rect (screen coords) - the reserved bands never show the world
        self._vx = left
        self._vy = top
        self._vw = w - left - right
        self._vh = h - top - bottom
        self._hx = self._vx + self._vw / 2.0        # view centre: offset = centre - camera
        self._hy = self._vy + self._vh / 2.0
        self.cx = self._hx                          # camera centre, world coords (start: offset 0)
        self.cy = self._hy
        self.ox = 0                                 # last computed view offset (ints, alloc-free)
        self.oy = 0
        self.world_w = world_w                      # 0 = unclamped; may be reassigned (new level)
        self.world_h = world_h
        self._bounds()
        _check_band(scene, top, bottom, left, right)

    # The clamp bounds depend only on the play rect and the world size, so they are computed
    # once per world size, not per frame. Plain attributes, deliberately NOT a property: on
    # MicroPython a class with any property pays a class lookup on EVERY attribute store
    # (MP_TYPE_FLAG_HAS_SPECIAL_ACCESSORS), 4 -> 19 us per store on RP2040 - more than the
    # whole saving. _compute re-derives the bounds when it sees a changed world size instead.
    def _bounds(self):
        self._ww = self.world_w
        self._wh = self.world_h
        self._xmin = float(self._vx + self._vw - self._ww)
        self._xmax = float(self._vx)
        self._ymin = float(self._vy + self._vh - self._wh)
        self._ymax = float(self._vy)

    def follow(self, tx, ty, snap=False):
        if snap:
            self.cx, self.cy = float(tx), float(ty)
        else:
            self.cx += (tx - self.cx) * self.lerp
            self.cy += (ty - self.cy) * self.lerp
        return self

    def _compute(self):
        # screen column s shows world column s - ox (set_view semantics), so the visible rect
        # [vx, vx+vw) shows world [vx-ox, vx+vw-ox); clamp keeps that inside [0, world_w).
        ox = self._hx - self.cx
        oy = self._hy - self.cy
        ww = self.world_w
        wh = self.world_h
        if ww != self._ww or wh != self._wh:        # world resized after construction
            self._bounds()
        if ww:                                      # clamp so we don't show past the world edge
            if ox < self._xmin:                     # (lower bound first: a world narrower than
                ox = self._xmin                     #  the view pins to the upper bound, as before)
            if ox > self._xmax:
                ox = self._xmax
        if wh:
            if oy < self._ymin:
                oy = self._ymin
            if oy > self._ymax:
                oy = self._ymax
        self.ox = int(ox)
        self.oy = int(oy)

    def offset(self):
        """Return the view offset as a tuple (allocates). To compose with Shake without a per-frame
        tuple, use `cam.apply()` (no shake) or read `cam.ox`/`cam.oy` after `_compute()`."""
        self._compute()
        return self.ox, self.oy

    def apply(self):
        """Update the scene camera directly - allocation-free (no tuple). Returns None."""
        self._compute()
        self.scene.set_view(self.ox, self.oy)


def _check_band(scene, top, bottom, left, right):
    """Simulator only: the reserved band is stated twice (Scene(top=...) and Camera(top=...))
    because the firmware Scene does not expose it - say so once when the two disagree, since
    the symptom (the view centred/clamped a band's height off) is otherwise silent. Device: no-op."""
    try:
        import _host                            # simulator only; the board has no such module
    except ImportError:
        return
    if scene is None or not hasattr(scene, "_top"):
        return
    got = (scene._top, scene._bottom, scene._left, scene._right)
    if got != (top, bottom, left, right):
        _host.note("Camera(top=%d, bottom=%d, left=%d, right=%d) but its Scene reserves "
                   "top=%d, bottom=%d, left=%d, right=%d - the camera centres and clamps on the "
                   "wrong rows/columns (the view sits a band's height off at the world edges). "
                   "Pass the Scene's band to Camera." % ((top, bottom, left, right) + got))


def _unwire(c):
    n = ((c >> 8) | (c << 8)) & 0xFFFF
    return (n >> 11) & 0x1F, (n >> 5) & 0x3F, n & 0x1F


def _wire(r, g, b):
    n = ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F)
    return ((n >> 8) | (n << 8)) & 0xFFFF


def _lerp565(a, b, t):
    ra, ga, ba = _unwire(a)
    rb, gb, bb = _unwire(b)
    return _wire(int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


class Sky:
    """A vertical gradient band (sky / background / day-night), drawn per-scanline via StripDraw
    - the classic Game Boy/raster trick. No retained full-screen buffer: it keeps only a small
    per-scanline colour LUT (`h` entries x 2 B), rebuilt only when `top`/`bottom` change. Change
    `top`/`bottom` over time for day-night. Add it FIRST (it's a background layer).

        sky = Sky(scene, 0, 0, W, HORIZON, pg.rgb565(60,120,240), pg.rgb565(200,230,255))
    """

    def __init__(self, scene, x, y, w, h, top, bottom):
        self.y = y
        self.h = max(1, h)
        self.w = w
        self._top = top
        self._bottom = bottom
        self._ktop = self._kbot = None                 # colours the runs are built for
        # Adjacent gradient rows quantize to the SAME RGB565 colour in long runs, so the band
        # merges into a few dozen vertical spans - painted with ONE Canvas.vspans per strip.
        # always_dirty=False: a static sky costs ~0/frame (repaints only where overlapped);
        # assigning .top/.bottom (day-night) invalidates via the properties below.
        self._rx0 = self._rx1 = self._rt = self._rb = self._rc = None
        self._nruns = 0
        self.sd = pg.StripDraw(self._draw, x, y, w, h, always_dirty=False)
        scene.add(self.sd, fixed=True)

    @property
    def top(self):
        return self._top

    @top.setter
    def top(self, v):
        if v != self._top:
            self._top = v
            self.sd.invalidate()

    @property
    def bottom(self):
        return self._bottom

    @bottom.setter
    def bottom(self, v):
        if v != self._bottom:
            self._bottom = v
            self.sd.invalidate()

    def _rebuild(self):
        # Merge equal-colour scanline runs (screen coords) once per colour change.
        hh = self.h
        den = hh - 1 if hh > 1 else 1                   # so the last row reaches `bottom` exactly
        r0 = self._rx0
        if r0 is None:
            self._rx0 = array.array("H", bytes(2 * hh))            # x0 = 0: from the view's left edge
            self._rx1 = array.array("H", [0xFFFF] * hh)            # x1 = huge: clipped to the view width
            self._rt = array.array("H", bytes(2 * hh))
            self._rb = array.array("H", bytes(2 * hh))
            self._rc = array.array("H", bytes(2 * hh))
        rt = self._rt
        rb = self._rb
        rc = self._rc
        y0 = self.y
        n = 0
        prev = -1
        top = self._top
        bot = self._bottom
        for r in range(hh):
            c = _lerp565(top, bot, r / den)
            if c != prev:
                rt[n] = y0 + r
                rb[n] = y0 + r
                rc[n] = c
                prev = c
                n += 1
            rb[n - 1] = y0 + r + 1
        self._nruns = n
        self._ktop = top
        self._kbot = bot

    def _draw(self, view, vx, vy, vw, vh):
        if self._top != self._ktop or self._bottom != self._kbot:
            self._rebuild()
        view.vspans(self._rx0, self._rx1, self._rt, self._rb, self._rc, self._nruns, -vx, -vy)


class Scanlines:
    """A CRT-style scanline overlay: darken every Nth row via StripDraw - no retained full-screen
    buffer, just a reused 1-row PAL8 bitmap (`w` B + a 2-colour palette). Add it LAST (on top).
    `step`=2 darkens every other line; `dark` is the checker colour written on those rows."""

    def __init__(self, scene, x, y, w, h, step=2, dark=pg.rgb565(0, 0, 0)):
        self.y = y
        self.step = step
        # Precompute a 1px-tall dither ROW (checker of `dark` over a transparent index 0). Darkening a
        # scanline is then ONE view.blit instead of a per-pixel view.pixel() loop (~w/2 binding calls
        # per row -> ~19k round-trips/frame for a full-screen overlay, the no-hot-path-churn rule).
        row = bytearray(w)
        for i in range(w):
            row[i] = i & 1                              # 0 = transparent, 1 = dark
        pal = array.array("H", (dark, dark))            # entry 1 = dark (entry 0 unused; transparent)
        self._row = pg.Bitmap(row, w, 1, format=pg.PAL8, palette=pal, frames=1, stride=w, transparent=0)
        # always_dirty=False: the overlay is static, so it repaints only where the layers UNDER it
        # dirty (re-darkening exactly the refreshed rows). always_dirty=True here was the classic
        # full-screen-StripDraw trap - it forced a full recomposite+push every frame for the whole
        # session, defeating the scene's dirty-rect tracking for every game that stacked it on top.
        self.sd = pg.StripDraw(self._draw, x, y, w, h, always_dirty=False)
        scene.add(self.sd, fixed=True)

    def _draw(self, view, vx, vy, vw, vh):
        row = self._row
        blit = view.blit
        step = self.step
        for ly in range((-vy) % step, vh, step):        # stride straight to the aligned rows (no per-row modulo)
            blit(row, 0, ly)                            # one blit per darkened scanline (checker dither)


class InvertFlash:
    """A FREE full-screen hit-flash via the panel's hardware colour inversion (pg.invert) -
    no StripDraw, no buffer, no repaint: the whole screen flips to its negative for a few
    frames. Cheaper than a Fade overlay; great for a sharp 1-bit "hit". Needs a controller
    that supports INVON/INVOFF (ST7789/ST7735); the sim emulates it (preview shows the negative).

        flash = InvertFlash(picogame_game.display())
        ...on hit:      flash.pulse()
        ...each frame:  flash.tick()
    """

    def __init__(self, display, frames=3, normal=None):
        # `normal` = the invert value of the panel's RESTING (correct-looking) state. Many ST7789
        # boards (incl. the PicoPad) send INVON in their init, so their normal state is invert=True;
        # the flash must flip to the OPPOSITE and restore to `normal` (NOT hardcode True/False, which
        # left the PicoPad stuck inverted - pulse() set INVON=normal=no flash, then "revert" set
        # INVOFF=inverted-and-stuck). Left None it follows `picogame_fx.PANEL_INVERTED` (default True =
        # PicoPad); a custom-board launcher sets that from its INVERT, so games need not pass `normal`.
        self.display = display
        self.frames = frames
        if normal is not None:
            self.normal = normal
        elif type(display).__name__ == "Framebuffer":
            # A RAM framebuffer (RP2350 DVI / Fruit Jam / the WASM playground) has NO panel INVON, so
            # its resting state is un-inverted - regardless of PANEL_INVERTED, which tracks an ST7789
            # panel's init (INVON). Without this a framebuffer board would "restore" to invert-on.
            self.normal = False
        else:
            self.normal = PANEL_INVERTED
        self.t = 0
        self._ok = True       # cleared if the target has no hardware invert (a Framebuffer/DVI panel
                              # or the WASM playground) -> pulse() degrades to a silent no-op there

    def pulse(self, frames=None):
        if not self._ok:
            return
        if self.t == 0:
            try:
                pg.invert(self.display, not self.normal)  # flip AWAY from the resting state
            except (TypeError, AttributeError, NotImplementedError, ValueError):
                self._ok = False                          # no INVON/INVOFF on this target -> disable
                return
        self.t = frames if frames is not None else self.frames

    def tick(self):
        if self._ok and self.t > 0:
            self.t -= 1
            if self.t == 0:
                try:
                    pg.invert(self.display, self.normal)  # restore the resting (normal) state
                except (TypeError, AttributeError, NotImplementedError, ValueError):
                    self._ok = False
        return self.t > 0
