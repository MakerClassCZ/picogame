# picogame timing helpers: frame-rate cap + dt, and a fixed-timestep accumulator.
# Both are driven by ONE primitive - a _Metronome of ideal event boundaries spaced at exactly the
# requested rate, on a millisecond timebase (supervisor.ticks_ms). Clock sleeps to the next boundary;
# FixedStep counts the boundaries that have passed. tick_async() additionally needs `asyncio` - a
# BUILT-IN (native C) module in the picogame firmware, so no /lib file is required; the ImportError
# fallback keeps everything else working on a build that happens to omit it.

import time

from micropython import const

try:
    import asyncio
except ImportError:
    asyncio = None

# Millisecond timebase: wrap-safe and allocation-free on device. supervisor.ticks_ms() returns a
# SMALL int that wraps at 2**29 ms (~6.2 days) - unlike time.monotonic_ns(), which is a big-int
# after ~1 s of uptime and so allocates a transient mpz on EVERY call (steady GC churn in the frame
# loop). The sim / plain CPython has no `supervisor`, so fall back to monotonic masked into the same
# 2**29 period, so the identical wrap-safe math drives both. The wrap only ever affects the single
# frame that straddles the 2**29 boundary; the signed _ms_diff handles it, so even a device left on
# for days can't glitch.
_HALF = const(1 << 28)
_MASK = const((1 << 29) - 1)

try:
    from supervisor import ticks_ms as _ms
except ImportError:
    _mono = time.monotonic
    def _ms():
        return int(_mono() * 1000) & _MASK

_sleep = time.sleep


def _ms_diff(a, b):             # signed (a - b) across the 2**29 wrap; result stays a small int
    return ((a - b + _HALF) & _MASK) - _HALF


class _Metronome:
    """Ideal event boundaries at exactly `rate` per second, in ms, wrap-safe. The interval averages
    1000/rate ms EXACTLY via a Bresenham carry (base ms per tick, +1 ms on the fraction of ticks that
    the remainder demands) - so there is no integer-rounding rate drift (e.g. 60/s is 60, not 62.5),
    yet every value stays a small int -> no per-tick heap allocation. `rate` up to 1000 (finer than
    1 ms/tick isn't representable on this timebase, and no handheld game needs it). rate<=0 = off
    (Clock's uncapped mode, which never calls advance()). Clock sleeps to `_next`; FixedStep counts
    how many `_next` boundaries `now` has passed."""

    def __init__(self, rate):
        self.set_rate(rate)
        self._next = _ms()
        self.advance()           # prime one interval ahead: a fresh Clock's first tick then sleeps to
                                 # a real boundary (dt ~ 1/rate, never 0), and FixedStep starts at 0 steps

    def set_rate(self, rate):
        rate = int(rate) if rate else 0      # tolerate a float rate (e.g. Clock(30.0))
        if rate > 0:
            self._base = 1000 // rate        # whole ms per interval
            self._num = 1000 % rate          # + this many /rate of a ms, spread by the carry
            self._den = rate
        else:
            self._base = self._num = 0
            self._den = 1
        self._carry = 0

    def advance(self):
        """Move `_next` forward by one Bresenham-exact interval (base ms, +1 when the carry fills)."""
        inc = self._base
        self._carry += self._num
        if self._carry >= self._den:
            self._carry -= self._den
            inc += 1
        self._next = (self._next + inc) & _MASK

    def resync(self, now):
        """Reset the schedule to `now` (drop accumulated backlog after a stall)."""
        self._next = now
        self._carry = 0


class Clock:
    """Caps the loop to `fps` and returns dt (seconds elapsed) each frame, so
    movement can be frame-rate independent and a quick D-pad tap no longer flings
    a sprite across the screen at high FPS.

        clock = picogame_clock.Clock(30)
        while True:
            dt = clock.tick()      # sleeps to the frame boundary, returns real dt
            update(dt)             # ignore dt for fixed-feel, or scale by it
            scene.refresh()

    dt granularity is 1 ms (immaterial at 30-60 fps). `fps` is used as an integer >= 1 (a fractional
    fps below 1 isn't representable on the ms rate model and runs uncapped). Uncapped mode (fps=0)
    can return dt==0.0 on a sub-millisecond frame (e.g. a trivial loop in the desktop sim) - guard
    `x / dt` if you rely on it.
    """

    def __init__(self, fps=30, max_dt=0.1):
        self.max_dt = max_dt
        self._capped = bool(fps and fps > 0)
        self._metro = _Metronome(fps)
        self._last = _ms()               # anchor for the dt measurement (see _advance)

    def set_fps(self, fps):
        self._capped = bool(fps and fps > 0)
        self._metro.set_rate(fps)
        if self._capped:                     # reset the schedule to now (a stale _next from uncapped
            self._metro.resync(_ms())        # running could otherwise read as far-future -> huge sleep)

    def _advance(self, now, anchor):
        dt = _ms_diff(now, self._last) / 1000.0
        self._last = anchor
        if dt < 0:
            return 0.0
        if dt > self.max_dt:           # clamp after a pause/stall -> no teleport
            return self.max_dt
        return dt

    def tick(self):
        now = _ms()
        if not self._capped:                          # uncapped: just measure real elapsed dt
            return self._advance(now, now)
        m = self._metro
        boundary = m._next
        behind = _ms_diff(boundary, now)              # >0: ahead of the boundary -> sleep to it
        if behind > 0:                                # made the deadline
            _sleep(behind / 1000.0)
            now = _ms()
            m.advance()                               # keep the ideal grid running
            if _ms_diff(now, m._next) > 0:            # overslept past a whole interval -> schedule lags
                m.resync(now); m.advance()            # reset phase to now, dt from real now
                return self._advance(now, now)
            return self._advance(now, boundary)       # small oversleep: dt from the ideal boundary (smooth)
        # Overran the budget (no sleep): now is at/past the boundary. Anchor dt to REAL now so the
        # overrun is NOT double-counted (the old cumulative-dt-inflation trap this restores), and
        # reset the schedule phase to now + one interval (matches the old now+frame_ms reset).
        m.resync(now); m.advance()
        return self._advance(now, now)

    async def tick_async(self):
        """Like tick(), but yields to other asyncio tasks during the idle wait.
        Note: rendering is blocking, so async only helps in this cap-sleep gap."""
        if asyncio is None:
            raise RuntimeError("asyncio not available in this build")
        now = _ms()
        if not self._capped:
            return self._advance(now, now)
        m = self._metro
        boundary = m._next
        behind = _ms_diff(boundary, now)
        if behind > 0:
            await asyncio.sleep(behind / 1000.0)
            now = _ms()
            m.advance()
            if _ms_diff(now, m._next) > 0:
                m.resync(now); m.advance()
                return self._advance(now, now)
            return self._advance(now, boundary)
        m.resync(now); m.advance()
        return self._advance(now, now)


class FixedStep:
    """Fixed-timestep accumulator: runs game logic in equal steps regardless of
    render time (deterministic physics/collision), rendering once per frame.

        fixed = picogame_clock.FixedStep(60)
        while True:
            for _ in range(fixed.step_count()):  # alloc-free; dt is constant in fixed.dt
                update(fixed.dt)
            scene.refresh()

    `dt` is the EXACT fixed timestep (1/step_fps s) regardless of the 1 ms timebase - the Bresenham
    metronome makes the average step RATE exact too, so physics neither drifts nor rounds.
    """

    def __init__(self, step_fps=60, max_steps=5):
        step_fps = int(step_fps)       # tolerate a float rate; keep dt consistent with the metronome
        self._metro = _Metronome(step_fps)
        self.dt = 1.0 / step_fps       # the exact, constant fixed timestep in seconds
        self.max_steps = max_steps

    def step_count(self):
        """How many fixed steps to run this frame (0..max_steps). Loop `for _ in range(...)`
        and use the constant `self.dt` - no per-frame generator allocation."""
        now = _ms()
        m = self._metro
        n = 0
        while n < self.max_steps and _ms_diff(now, m._next) >= 0:   # a boundary has passed -> a step is due
            m.advance()
            n += 1
        if n >= self.max_steps and _ms_diff(now, m._next) > 0:
            m.resync(now)              # still behind after max_steps: drop backlog -> no spiral of death
        return n

    def steps(self):
        """Generator form (allocates a generator per call). Prefer `step_count()` in hot loops."""
        for _ in range(self.step_count()):
            yield self.dt
