# picogame timing helpers: frame-rate cap + dt, and a fixed-timestep accumulator.
# Uses time.monotonic_ns / time.sleep - no firmware changes needed.
# tick_async() additionally needs the `asyncio` library (frozen in firmware or in
# CIRCUITPY/lib); the rest works on any build.

import time

from micropython import const

try:
    import asyncio
except ImportError:
    asyncio = None

_NS = const(1_000_000_000)
_now = time.monotonic_ns        # bound once: avoids a per-tick attribute lookup
_sleep = time.sleep


class Clock:
    """Caps the loop to `fps` and returns dt (seconds elapsed) each frame, so
    movement can be frame-rate independent and a quick D-pad tap no longer flings
    a sprite across the screen at high FPS.

        clock = picogame_clock.Clock(30)
        while True:
            dt = clock.tick()      # sleeps to the frame boundary, returns real dt
            update(dt)             # ignore dt for fixed-feel, or scale by it
            scene.refresh()
    """

    def __init__(self, fps=30, max_dt=0.1):
        self.max_dt = max_dt
        self.set_fps(fps)
        self._last = _now()

    def set_fps(self, fps):
        self.frame_ns = int(_NS / fps) if fps and fps > 0 else 0   # 0 = uncapped

    def _advance(self, now, anchor=None):
        dt = (now - self._last) / _NS
        self._last = now if anchor is None else anchor
        if dt < 0:
            return 0.0
        if dt > self.max_dt:           # clamp after a pause/stall -> no teleport
            return self.max_dt
        return dt

    def tick(self):
        if self.frame_ns:
            target = self._last + self.frame_ns
            now = _now()
            if now < target:                       # made the deadline: sleep to it and anchor the
                _sleep((target - now) / _NS)        # schedule to the ideal boundary so a small oversleep
                now = _now()                        # can't accumulate into drift (resync if sleep
                anchor = target if (now - target) <= self.frame_ns else now   # itself wildly overshot)
                return self._advance(now, anchor)
            # overran the budget (no sleep): anchor to the REAL now -- anchoring to target here would
            # leave the schedule lagging real time and inflate dt cumulatively every slow frame.
            return self._advance(now)
        return self._advance(_now())

    async def tick_async(self):
        """Like tick(), but yields to other asyncio tasks during the idle wait.
        Note: rendering is blocking, so async only helps in this cap-sleep gap."""
        if asyncio is None:
            raise RuntimeError("asyncio not available (freeze it or add to /lib)")
        if self.frame_ns:
            target = self._last + self.frame_ns
            now = _now()
            if now < target:
                await asyncio.sleep((target - now) / _NS)
                now = _now()
                anchor = target if (now - target) <= self.frame_ns else now
                return self._advance(now, anchor)
            return self._advance(now)             # overran: anchor to real now (keep dt accurate)
        return self._advance(_now())


class FixedStep:
    """Fixed-timestep accumulator: runs game logic in equal steps regardless of
    render time (deterministic physics/collision), rendering once per frame.

        fixed = picogame_clock.FixedStep(60)
        while True:
            for _ in range(fixed.step_count()):  # alloc-free; dt is constant in fixed.dt
                update(fixed.dt)
            scene.refresh()
    """

    def __init__(self, step_fps=60, max_steps=5):
        self.step_ns = int(_NS / step_fps)
        self.dt = self.step_ns / _NS
        self.max_steps = max_steps
        self._last = _now()
        self._accum = 0

    def step_count(self):
        """How many fixed steps to run this frame (0..max_steps). Loop `for _ in range(...)`
        and use the constant `self.dt` - no per-frame generator allocation."""
        now = _now()
        self._accum += now - self._last
        self._last = now
        n = 0
        while self._accum >= self.step_ns and n < self.max_steps:
            self._accum -= self.step_ns
            n += 1
        if n >= self.max_steps:
            self._accum = 0            # drop backlog -> avoid spiral of death
        return n

    def steps(self):
        """Generator form (allocates a generator per call). Prefer `step_count()` in hot loops."""
        for _ in range(self.step_count()):
            yield self.dt
