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

    trauma is squared before use (Eiserloh) so small events barely shake and big ones slam.
    `max_offset` ~6 px suits 320x240 (>10 hides the action). `decay` is trauma lost per frame
    (~0.03 ≈ 0.8/sec at 30 fps -> a 'kick', not a 'rumble')."""

    def __init__(self, scene, max_offset=6, decay=0.03, seed=0x9E37):
        self.scene = scene
        self.max = max_offset
        self.decay = decay
        self.trauma = 0.0
        self._r = seed & 0xFFFF

    def _rnd(self):                                  # tiny 16-bit LCG -> -1.0 .. +1.0
        # 16-bit state + a multiplier under 2^14 keep every intermediate below MicroPython's
        # 31-bit small-int limit, so a per-frame shake allocates NO transient big-ints (a>0
        # is ==1 mod 4 and c odd -> full 65536 period; quality is plenty for screen jitter).
        self._r = (self._r * 12345 + 12345) & 0xFFFF
        return (self._r % 2001 - 1000) / 1000.0

    def add(self, amount):
        """Add trauma (0..1). e.g. 0.6 = a hit/explosion, 0.15 = a small bump."""
        self.trauma = min(1.0, self.trauma + amount)

    def tick(self, cam_x=0, cam_y=0):
        """Apply shake on top of (cam_x, cam_y). Returns True while still shaking."""
        if self.trauma <= 0.0:                       # idle: track the camera, but skip the RNG
            self.scene.set_view(cam_x, cam_y)         # (no per-frame _rnd() calls when not shaking)
            return False
        sh = self.trauma * self.trauma
        ox = int(self.max * sh * self._rnd())
        oy = int(self.max * sh * self._rnd())
        self.scene.set_view(cam_x + ox, cam_y + oy)
        self.trauma = max(0.0, self.trauma - self.decay)
        return self.trauma > 0.0


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
        self.sd = pg.StripDraw(self._draw, 0, 0, 0, 0)   # collapsed until active
        scene.add(self.sd, fixed=True)                          # fixed: ignore the camera

    def _activate(self, on):
        self._active = on
        self.sd.x = self.X
        self.sd.y = self.Y
        self.sd.width = self.W if on else 0
        self.sd.height = self.H if on else 0
        if not on:
            self.scene.invalidate()                       # clean repaint once removed

    def to(self, target, speed=2.0):
        self.target = max(0.0, min(float(self.LEVELS), float(target)))
        self.speed = speed
        if self.target > 0 or self.level > 0:
            self._activate(True)
        return self

    def out(self, speed=2.0):                              # -> opaque
        return self.to(self.LEVELS, speed)

    def into(self, speed=2.0):                             # -> clear
        return self.to(0.0, speed)

    def set(self, level):
        self.level = self.target = max(0.0, min(float(self.LEVELS), float(level)))
        self._activate(self.level > 0)
        return self

    def dim(self, level=8):                                # hold a partial dim (menus)
        return self.set(level)

    def clear(self):
        return self.set(0)

    def pulse(self, level=12, speed=2.0):                 # RAMP up to the peak, then back to 0
        # The smooth fxdemo-style flash: ramp the dither UP to `level` then back DOWN at `speed`
        # (levels/frame), instead of SNAPPING on (which read as too abrupt/strong). peak<16 keeps
        # it a see-through dither even at its strongest - never a solid wall of colour.
        self._pulse = self.LEVELS if level is None else level
        return self.to(self._pulse, speed)

    @property
    def is_done(self):
        return self.level == self.target

    def tick(self):
        """Step level toward target by `speed`. Returns True when the target is reached."""
        if self._hold > 0:                   # hold at the current level (a flash's "pop")
            self._hold -= 1
            return False
        if self.level < self.target:
            self.level = min(self.target, self.level + self.speed)
        elif self.level > self.target:
            self.level = max(self.target, self.level - self.speed)
        if self._pulse is not None and self.level >= self._pulse:   # pulse hit its peak -> fall back
            self.target = 0.0
            self._pulse = None
        if self.level <= 0 and self.target <= 0 and self._active:
            self._activate(False)        # deactivate ONCE on reaching idle - NOT every idle frame
        return self.level == self.target  # (the every-frame scene.invalidate() flickered HUDs)

    def _draw(self, view, vx, vy, vw, vh):
        lvl = int(self.level)
        if lvl <= 0:
            return
        S = self.cell
        col = self.color
        bayer = _BAYER
        fill = view.fill_rect                          # bind once: this inner loop runs per dither cell
        by0, by1 = vy // S, (vy + vh - 1) // S
        bx0, bx1 = vx // S, (vx + vw - 1) // S
        for by in range(by0, by1 + 1):
            brow = bayer[by & 3]
            sy = by * S - vy
            for bx in range(bx0, bx1 + 1):
                if brow[bx & 3] < lvl:
                    fill(bx * S - vx, sy, S, S, col)


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
    """

    def __init__(self, scene, w, h, lerp=0.18, world_w=0, world_h=0):
        self.scene = scene
        self.w = w
        self.h = h
        self.lerp = lerp
        self.world_w = world_w
        self.world_h = world_h
        self.cx = w / 2.0                           # camera centre, world coords
        self.cy = h / 2.0
        self.ox = 0                                 # last computed view offset (ints, alloc-free)
        self.oy = 0

    def follow(self, tx, ty, snap=False):
        if snap:
            self.cx, self.cy = float(tx), float(ty)
        else:
            self.cx += (tx - self.cx) * self.lerp
            self.cy += (ty - self.cy) * self.lerp
        return self

    def _compute(self):
        ox = self.w / 2.0 - self.cx
        oy = self.h / 2.0 - self.cy
        if self.world_w:                            # clamp so we don't show past the world edge
            ox = min(0.0, max(float(self.w - self.world_w), ox))
        if self.world_h:
            oy = min(0.0, max(float(self.h - self.world_h), oy))
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
    - the classic Game Boy/raster trick. ZERO RAM (no buffer). Change `top`/`bottom` over time
    for day-night. Add it FIRST (it's a background layer).

        sky = Sky(scene, 0, 0, W, HORIZON, pg.rgb565(60,120,240), pg.rgb565(200,230,255))
    """

    def __init__(self, scene, x, y, w, h, top, bottom):
        self.y = y
        self.h = max(1, h)
        self.top = top
        self.bottom = bottom
        self._key = None                               # row-colour LUT, rebuilt only when top/bottom change
        self._lut = array.array("H", bytes(2 * self.h))
        self.sd = pg.StripDraw(self._draw, x, y, w, h)
        scene.add(self.sd, fixed=True)

    def _draw(self, view, vx, vy, vw, vh):
        key = (self.top, self.bottom)
        if key != self._key:                           # rebuild only on a colour change (day-night stays mutable)
            self._key = key
            lut = self._lut
            hh = self.h
            for r in range(hh):
                lut[r] = _lerp565(self.top, self.bottom, r / hh)
        lut = self._lut
        fill = view.fill_rect
        y0 = self.y
        hh = self.h
        for ly in range(vh):                           # per scanline: an array index, no float divide/lerp
            r = vy + ly - y0
            if 0 <= r < hh:
                fill(0, ly, vw, 1, lut[r])


class Scanlines:
    """A CRT-style scanline overlay: darken every Nth row. StripDraw, ZERO RAM. Add it LAST
    (on top). `step`=2 darkens every other line; `dark` is the checker colour written on those rows."""

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
        self.sd = pg.StripDraw(self._draw, x, y, w, h)
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

        flash = InvertFlash(board.DISPLAY)
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
        self.normal = PANEL_INVERTED if normal is None else normal
        self.t = 0

    def pulse(self, frames=None):
        if self.t == 0:
            pg.invert(self.display, not self.normal)      # flip AWAY from the resting state
        self.t = frames if frames is not None else self.frames

    def tick(self):
        if self.t > 0:
            self.t -= 1
            if self.t == 0:
                pg.invert(self.display, self.normal)      # restore the resting (normal) state
        return self.t > 0
