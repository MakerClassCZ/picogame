# picogame_mode7: drive the C Canvas.mode7 perspective floor (Mode-7) from friendly
# camera params. Zero engine cost - all the trig is here in Python; the C primitive
# just does the per-scanline fill. The texture must have power-of-2 width/height;
# one world unit = one full texture tile.
#
#   import picogame_mode7 as m7
#   cam = m7.Camera(fov=0.66)
#   ...each frame, into a StripDraw view OR a Canvas:
#   cam.draw(view, road_tex, x=px, y=py, angle=heading, horizon=90, height=8.0)
import math

_F = 16
_ONE = 1 << _F


def _q16(f):
    return int(f * _ONE)


class Camera:
    """Holds the field-of-view; call draw() each frame with the pose."""

    def __init__(self, fov=0.66):
        self.fov = fov
        self._x = self._y = self._a = self._h = self._fov = self._w = None   # last converted pose

    def draw(self, canvas, texture, x, y, angle, horizon, height, y_off=0):
        """Fill `canvas` (a Canvas or a StripDraw view) below `horizon` with a
        perspective ground plane of `texture`. x/y = camera position in world
        (tile) units, angle = heading in radians, height = how high the camera
        sits (bigger = ground recedes slower)."""
        # A StripDraw calls this once per strip with the SAME pose; the trig + the ten Q16
        # conversions (~270 us on RP2040) run only when the pose actually changed.
        w = canvas.width
        fov = self.fov
        if (x != self._x or y != self._y or angle != self._a or height != self._h
                or fov != self._fov or w != self._w):
            self._x = x
            self._y = y
            self._a = angle
            self._h = height
            self._fov = fov
            self._w = w
            dx, dy = math.cos(angle), math.sin(angle)
            px, py = -dy * fov, dx * fov             # camera plane (FOV half-width)
            r0x, r0y = dx - px, dy - py              # left-edge ray
            r1x, r1y = dx + px, dy + py              # right-edge ray
            self._qz = _q16(height)
            self._q0x, self._q0y = _q16(r0x), _q16(r0y)
            self._qsx, self._qsy = _q16((r1x - r0x) / w), _q16((r1y - r0y) / w)
            self._qcx, self._qcy = _q16(x), _q16(y)
        canvas.mode7(texture, horizon, y_off, self._qz, self._q0x, self._q0y,
                     self._qsx, self._qsy, self._qcx, self._qcy)
