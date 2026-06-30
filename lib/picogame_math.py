# picogame_math - the small numeric helpers every game reaches for: clamp/mid/lerp/sgn/approach/wrap,
# TURN-BASED trig (angles as 0..1 turns, friendlier than radians for games; positive = clockwise on a
# y-down screen), and 2D vector helpers (length/distance/normalize/angle).
#
#   import picogame_math as m
#   hp = m.clamp(hp, 0, hpmax)
#   x  = m.lerp(x, target_x, 0.2)               # smooth follow
#   a  = m.atan2_t(ty - y, tx - x)              # aim, in turns (0..1)
#   px = x + m.cos_t(a) * speed; py = y + m.sin_t(a) * speed
#   d  = m.distance(x, y, ex, ey)               # vector helpers (folded in from the old picogame_vec)

import math

TAU = 6.283185307179586


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def mid(a, b, c):
    """Median of three; = clamp when the middle arg is the value."""
    return max(min(a, b), min(max(a, b), c))


def lerp(a, b, t):
    return a + (b - a) * t


def inv_lerp(a, b, v):
    return 0.0 if a == b else (v - a) / (b - a)


def remap(v, a, b, c, d):
    """Map v from range [a,b] onto [c,d]."""
    return c + (d - c) * (0.0 if a == b else (v - a) / (b - a))


def sgn(x):
    return -1 if x < 0 else (1 if x > 0 else 0)


def approach(v, target, step):
    """Move v toward target by at most `step` (no overshoot)."""
    if v < target:
        return min(target, v + step)
    return max(target, v - step)


def wrap(v, lo, hi):
    """Wrap v into [lo, hi)."""
    n = hi - lo
    return lo if n <= 0 else lo + (v - lo) % n   # degenerate/inverted range -> lo (no %0, no out-of-range)


def sin_t(turns):
    """sin of an angle in TURNS (1.0 = full circle)."""
    return math.sin(turns * TAU)


def cos_t(turns):
    return math.cos(turns * TAU)


def atan2_t(dy, dx):
    """Angle of (dx, dy) in TURNS, 0..1."""
    return (math.atan2(dy, dx) / TAU) % 1.0


# --- 2D vector helpers (folded in from the former picogame_vec) ---

def length(dx, dy):
    return math.sqrt(dx * dx + dy * dy)


def distance(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def normalize(dx, dy):
    """Unit vector (dx, dy); (0.0, 0.0) for a zero vector."""
    d = math.sqrt(dx * dx + dy * dy)
    return (0.0, 0.0) if d == 0 else (dx / d, dy / d)


def angle_rad(dx, dy):
    """Angle of (dx, dy) in RADIANS (atan2). Use atan2_t for turns (0..1)."""
    return math.atan2(dy, dx)


def from_angle_rad(a, mag=1.0):
    """Vector of magnitude `mag` at angle `a` (RADIANS)."""
    return (math.cos(a) * mag, math.sin(a) * mag)
