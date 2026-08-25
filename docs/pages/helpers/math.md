---
title: "Math, random & collision"
description: "Numeric helpers, reproducible random sequences, and the collision tests built into Sprite."
---

This page covers numeric helpers, a seedable random generator, and the collision methods on `Sprite`. Neither helper module requires engine setup. See [/reference/](/reference/) for the signatures.

## picogame_math

`picogame_math` provides `clamp`, `lerp`, `approach`, `wrap`, 2D vector functions, and trigonometry expressed in turns. Functions ending in `_t` use the interval `[0,1)` for one full rotation, which is convenient for stored headings and aiming. The module also keeps the vector helpers formerly provided by `picogame_vec`.

API:

- `clamp(v, lo, hi)` - returns `v` pinned into `[lo, hi]`. The everyday helper for keeping a position on screen or HP in range.
- `mid(a, b, c)` - median of three; behaves like a clamp when the middle arg is the value.
- `lerp(a, b, t)` - linear blend `a + (b-a)*t`. With a small `t` each frame it gives a smooth follow/ease.
- `inv_lerp(a, b, v)` - inverse of `lerp`: where `v` sits in `[a,b]` as `0..1`. Returns `0.0` if `a == b`.
- `remap(v, a, b, c, d)` - map `v` from range `[a,b]` onto `[c,d]`. Safe when `a == b` (maps to `c`).
- `sgn(x)` - sign as `-1`, `0`, or `1`.
- `approach(v, target, step)` - move `v` toward `target` by at most `step`, never overshooting. Great for friction/acceleration toward a value.
- `wrap(v, lo, hi)` - wrap `v` into the half-open range `[lo, hi)`. Degenerate or inverted ranges return `lo` (no division by zero, never out of range).
- `sin_t(turns)` / `cos_t(turns)` - sine/cosine of an angle in TURNS (`1.0` = full circle). Positive is clockwise on a y-down screen.
- `atan2_t(dy, dx)` - angle of vector `(dx, dy)` in turns, normalized to `0..1`. Use for aiming.
- `length(dx, dy)` - magnitude of a vector.
- `distance(x1, y1, x2, y2)` - distance between two points.
- `normalize(dx, dy)` - unit vector; returns `(0.0, 0.0)` for a zero-length input.
- `angle_rad(dx, dy)` - angle in RADIANS (raw `atan2`); `from_angle_rad(a, mag=1.0)` - vector of length `mag` at radian angle `a`.
- `TAU` - the constant `2*pi`, used internally by the `_t` trig.

Example (rotate a ship and thrust along its nose, as in asteroids):

```python
import picogame_math as m

ang = 0.0                       # heading, in turns 0..1
TURN = 0.01
ang = (ang + TURN) % 1.0        # rotate right
dx, dy = m.sin_t(ang), -m.cos_t(ang)   # nose-up direction
vx += dx * 0.25
vy += dy * 0.25
sp = m.length(vx, vy)           # current speed
x = m.clamp(x, 8, W - 8)        # keep on screen
```

:::note[Gotchas]
- The `_t` trig is clockwise on the y-down screen, and "up" is `-cos_t` - flip the sign of the y component, like the asteroids ship above, or your sprite turns the wrong way.
- `wrap` is half-open: `wrap(hi, lo, hi)` returns `lo`, not `hi`. For an inverted or zero-width range it just returns `lo` rather than raising.
- Use turns (`sin_t`/`cos_t`/`atan2_t`) and radians (`angle_rad`/`from_angle_rad`) consistently; do not mix the two for the same angle.
:::

## picogame_rand

This seedable xorshift32 generator supports weighted choices, in-place shuffling, and a shuffle bag. Use a fixed seed for reproducible replays, ghost data, tests, or level layouts. `Rand()` without an argument seeds itself from the clock. `Bag` emits each item once per shuffled cycle, which prevents long streaks caused by independent choices.

`Rand(seed=None)`:

- `Rand(1234)` seeds from an int (reproducible); `Rand()` seeds from the clock. `seed=0` is remapped internally (xorshift cannot start at zero).
- `seed(s)` - reseed an existing generator.
- `below(n)` - integer in `0 .. n-1`. Returns `0` if `n <= 0`.
- `randint(a, b)` - integer in `a .. b` inclusive. Raises `ValueError` if `b < a`.
- `random()` - float in `[0.0, 1.0)`.
- `chance(p)` - `True` with probability `p` (where `p` is `0..1`).
- `choice(seq)` - one element of `seq`. Raises `ValueError` on an empty sequence.
- `shuffle(lst)` - Fisher-Yates shuffle of `lst`, in place (returns `None`).
- `weighted(weights)` - return an index `0..len-1` picked proportionally to `weights`. Raises `ValueError` if the total is `<= 0`. No streak control (independent draws).

`Bag(items, rng)`:

- A shuffle-bag / "7-bag": yields every item once per cycle in shuffled order, so no long streaks or droughts. Fairer than independent picks for spawns and pieces.
- `next()` - return the next item, reshuffling automatically at the start of each cycle. Raises `ValueError` at construction if `items` is empty.

Example (one seeded RNG for the whole game, plus an anti-streak spawn bag):

```python
import picogame_rand

rng = picogame_rand.Rand(0x1234)      # seeded -> reproducible
x = rng.randint(40, W - 40)           # 40 .. W-40 inclusive
if rng.chance(0.25):
    spawn_powerup(x)
kind = rng.weighted([5, 3, 1])        # index 0 most likely
bag = picogame_rand.Bag([0, 1, 2, 3, 4, 5, 6], rng)
piece = bag.next()                    # every value once per cycle
```

:::note[Gotchas]
- Reach for `picogame_rand` (or plain `random.randint`) instead of `random.shuffle`, `random.sample`, or `random.choices`: those exist only in desktop CPython, so a game using them runs in the [simulator](/simulator/) but crashes with `AttributeError: module 'random' has no attribute 'shuffle'` on the board and in the browser playground (both are MicroPython). `Rand.shuffle` is a drop-in replacement.
- `shuffle` mutates the list in place and returns `None` - do not write `lst = rng.shuffle(lst)`.
- `Bag` takes ownership of a copy of `items`; `next()` reshuffles that internal list, so the order you passed in is not preserved.
- `weighted` returns an index, not the value - index into your own list with it.
- Same seed plus same call sequence equals same results: that is the point, but it also means an accidentally shared `rng` couples two systems' randomness.
:::

## Sprite collision

Every `Sprite` has box and radius collision methods. They use the drawn bounds after anchor, scale, and rotation without allocating a result object. Use `overlaps()` for sprite or rectangular intersections and `near()` for a circular distance check.

API (methods on any `Sprite`):

- `a.overlaps(b, inset=0)` - inclusive AABB box overlap (they collide the moment they touch). `b` may be another `Sprite`, a point `(x, y)`, or a rect `(x1, y1, x2, y2)` - e.g. a trigger zone, or `(0, 0, W, H)` to test whether the sprite is still on screen. `inset` shrinks THIS sprite's box by N px on each side, for a hitbox smaller than the art. Returns a bool.
- `a.near(b, r)` - circular test: is this sprite's centre within `r` px of `b`'s centre? Uses squared distance, so no `sqrt`. `b` may be a `Sprite` or a point `(x, y)`.

Boxes and centres come from the sprite's drawn rectangle, so both methods are anchor/scale/rotation aware - correct for any anchor (unlike a hand-rolled `x`-based test). See [/scene-format/](/scene-format/) for anchors.

For arbitrary boxes with no sprite (two computed regions), drop to the raw primitive `pg.collide(x1, y1, x2, y2, ax1, ay1[, ax2, ay2])`. For tile-grid walls/terrain, probe `picogame_tiles` flags rather than overlapping every tile.

Example (bullets vs rocks circular, player vs enemy boxed - from asteroids and a platformer):

```python
for b in bullets:
    for r in rocks:
        if b.visible and b.near(r, 18):   # circular, no sqrt
            kill(b, r)

if player.overlaps(enemy):                # box overlap, anchor-correct
    take_damage()

if not ship.overlaps((0, 0, W, H)):       # off-screen? despawn it
    pool.free(ship)
```

:::note[Gotchas]
- These read live sprite positions. If you track motion in floats (`data["x"]`), call `sprite.move(int(x), int(y))` before testing, or the collision lags a frame behind the visible sprite.
- `overlaps` is a box test, not pixel-perfect - use `inset` (often a few px) so art corners do not register false hits.
- Guard with `if sprite.visible` (and any "alive" flag) yourself - the methods test geometry only, not whether an entity is active. See [/memory/](/memory/) on pooling freed entities.
:::
