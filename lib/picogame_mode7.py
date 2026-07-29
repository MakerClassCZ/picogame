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

    def draw(self, canvas, texture, x, y, angle, horizon, height, y_off=0):
        """Fill `canvas` (a Canvas or a StripDraw view) below `horizon` with a
        perspective ground plane of `texture`. x/y = camera position in world
        (tile) units, angle = heading in radians, height = how high the camera
        sits (bigger = ground recedes slower)."""
        dx, dy = math.cos(angle), math.sin(angle)
        px, py = -dy * self.fov, dx * self.fov      # camera plane (FOV half-width)
        r0x, r0y = dx - px, dy - py                  # left-edge ray
        r1x, r1y = dx + px, dy + py                  # right-edge ray
        w = canvas.width
        canvas.mode7(
            texture, horizon, y_off, _q16(height),
            _q16(r0x), _q16(r0y),
            _q16((r1x - r0x) / w), _q16((r1y - r0y) / w),
            _q16(x), _q16(y))
