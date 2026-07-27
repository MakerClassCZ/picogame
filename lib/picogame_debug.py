# picogame_debug - RAM watermarks + an optional on-screen FPS/free-RAM overlay.
#
# ram(tag) prints '[RAM] tag: free N alloc M' AFTER a gc.collect() (= true retention, not
# churn) at the big transitions (boot / level change / boss build) - the probe every
# on-device MemoryError hunt re-invents. Calls are cheap no-ops until you flip `enabled`,
# so shipping code can leave them in place. Watch adds a tiny 'FPS 30 FREE 31k' corner
# label, re-rendered ONLY when the text changes (never per frame - text rendering allocates).
#
#   import picogame_debug as dbg
#   dbg.enabled = True                     # flip while testing; default False = silent
#   dbg.ram("boot")                        # [RAM] boot: free 48128 alloc 23552
#   scene, bufA, bufB = picogame_game.setup()
#   watch = dbg.Watch(scene)               # overlay is explicit - independent of `enabled`
#   while True:
#       dt = clock.tick()
#       watch.step()                       # once per frame; ~free except at the window edge
#       scene.refresh()
#
# Overlay RAM cost: ONE small PAL8 text bitmap (~ w*h bytes ~= 1.3 KB for the full label),
# replaced (old one GC'd) on change - never cached, never re-rendered per frame.

import gc
import time
import os

# General debug switch for the whole engine. settings.toml `PICOGAME_DEBUG = 1` seeds it (a test can
# also set `picogame_debug.enabled = True` in code). Gates `ram()` + `note()` across every subsystem
# (audio, input, ...). A falsy value ("", "0", "false") = off; default off.
enabled = os.getenv("PICOGAME_DEBUG") not in (None, "", 0, False, "0", "false", "False")


def note(*args):
    """Crash-proof serial diagnostic for an UNEXPECTED failure at a subsystem boundary (a real problem:
    a mis-wired/missing I2S DAC driver, a claimed pin). Prints '[picogame] ...' ONLY when `enabled`, and
    NEVER raises (an OOM inside the print can't escape). Do NOT call it for an EXPECTED fallback (the sim
    has no synthio; a PWM board has no I2S DAC) - those must stay quiet."""
    if not enabled:
        return
    try:
        print("[picogame]", *args)
    except Exception:
        pass


def ram(tag):
    """gc.collect() then print '[RAM] tag: free N alloc M' (device = true retention).
    Sim/CPython (gc has no mem_free): prints tracemalloc numbers when tracing (run with
    PYTHONTRACEMALLOC=1), else stays silent - sim output stays clean."""
    if not enabled:
        return
    gc.collect()
    if hasattr(gc, "mem_free"):
        try:
            print("[RAM] %s: free %d alloc %d" % (tag, gc.mem_free(), gc.mem_alloc()))
        except AttributeError:             # a port without mem_alloc
            print("[RAM] %s: free %d" % (tag, gc.mem_free()))
    else:
        try:
            import tracemalloc
            if tracemalloc.is_tracing():
                cur, peak = tracemalloc.get_traced_memory()
                print("[RAM] %s: traced %d peak %d" % (tag, cur, peak))
        except ImportError:
            pass


# Wrap-safe ms timebase (same rationale as picogame_clock: supervisor.ticks_ms is a small
# int; time.monotonic_ns would heap-allocate a big-int every frame on device).
_MASK = (1 << 29) - 1
_HALF = 1 << 28
try:
    from supervisor import ticks_ms as _ms
except ImportError:
    def _ms():
        return int(time.monotonic() * 1000) & _MASK


class Watch:
    """One-line corner HUD 'FPS 30 FREE 31k', resampled every `every` frames.
    FPS = frames / measured wall time across the window (`clock` accepted for API
    symmetry; picogame_clock.Clock keeps no fps counter, so we always measure).
    FREE = gc.mem_free()//1024 after a collect (a deliberate debug-only hitch once
    per window; omitted on the sim, which has no mem_free). ONE live text bitmap,
    swapped only when the rounded numbers change. hide()/show() toggle the sprite;
    remove() detaches it from the scene for good. step() is ~free while hidden."""

    CELLS = 18                             # fixed width -> constant bitmap size (no shrink/stale, reused buffer)

    def __init__(self, scene, clock=None, every=30, x=2, y=2):
        import picogame as pg
        import terminalio
        import picogame_font
        self._pg, self._fontmod, self._font = pg, picogame_font, terminalio.FONT
        self._fg = pg.rgb565(255, 255, 128)
        self._bg = pg.rgb565(24, 24, 32)   # opaque bg: a redraw fully overwrites old text
        self.every = every
        self._n = 0
        self._t0 = _ms()
        self._text = None
        self._buf = None                   # reused glyph buffer -> NO per-update ~1 KB bitmap alloc
        # allocate the buffer + first bitmap ONCE, at a fixed CELLS width (space-padded thereafter)
        bmp, _, _, self._buf, _ = picogame_font._render_into(
            pg, self._font, " " * self.CELLS, self._fg, self._bg, None)
        self.sprite = pg.Sprite(bmp, x, y)
        self.sprite.anchor = (0.0, 0.0)
        self.scene = scene
        scene.add(self.sprite)

    def step(self):
        """Call once per frame."""
        if not self.sprite.visible:
            return
        self._n += 1
        if self._n < self.every:
            return
        now = _ms()
        ms = ((now - self._t0 + _HALF) & _MASK) - _HALF   # signed diff across the wrap
        fps = (self._n * 1000 + ms // 2) // ms if ms > 0 else 0
        self._n = 0
        self._t0 = now
        gc.collect()
        if hasattr(gc, "mem_free"):
            text = "FPS %d FREE %dk" % (fps, gc.mem_free() // 1024)
        else:
            text = "FPS %d" % fps
        text = text[:self.CELLS]
        text = text + " " * (self.CELLS - len(text))   # fixed width (constant size, no stale pixels);
        #                                                manual pad - str.ljust is absent on some CP builds
        if text != self._text:             # re-render into the REUSED buffer (only the small Bitmap wrapper allocs)
            self._text = text
            bmp, _, _, self._buf, _ = self._fontmod._render_into(
                self._pg, self._font, text, self._fg, self._bg, self._buf)
            self.sprite.bitmap = bmp

    def hide(self):
        self.sprite.visible = False

    def remove(self):
        """Detach the overlay from the scene for good (done debugging), so GC reclaims it."""
        self.scene.remove(self.sprite)

    def show(self):
        self.sprite.visible = True
