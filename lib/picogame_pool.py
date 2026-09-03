# picogame_pool: a reusable fixed-size sprite pool - the exact pattern every
# spawner game (bullets, enemies, orbs, pipes) hand-rolled: pre-allocate N sprites
# added to the scene, a free-slot scan to spawn, hide to free, and a plain list to
# iterate.
#
# The pool keeps its OWN in-use bit (`pool.alive`, one byte per slot), so `sprite.visible`
# means what it means everywhere else in the engine: DRAW THIS. Hiding a pooled sprite is
# therefore safe - blink a pooled enemy through `.visible` like any other sprite and its slot
# stays taken. `spawn()` shows the slot it hands out and `free()` hides it again, so the usual
# `if not s.visible: continue` guard and inline `if b.visible and b.near(e, R)` collision reads
# stay correct. The one gap: while a live sprite is blinked OFF that guard skips it, so it
# doesn't move for those frames. A game that blinks pooled entities and cares about the
# half-speed drift guards on the pool's bit instead:
#
#   al = enemies.alive
#   for i in range(len(al)):
#       if not al[i]: continue
#       e = enemies.items[i]
#
# Read `alive`, never write it: the pool also keeps a live-slot counter, so `count()` and the
# "pool full" answer are O(1) - a slot bit flipped by hand would desync the two. Go through
# `spawn()`/`free()`.
#
# `sprite.data` for per-entity state - the pool NEVER reads or writes it, so pre-allocating one
# dict per slot at start-up and only mutating it keeps a pool allocation-free.
#
# A recycled slot comes back in its BASELINE look - the blit effect, scale/angle, frame and
# flips are restored to how the sprites looked at the FIRST spawn(), so last life's hit-flash
# (or a death scale-up) never leaks into the next spawn, while the usual set-up right after
# construction (`for e in enemies.items: e.flip_y = True`) is kept - it happens before anything
# is spawned. Reconfigure the sprites later? Call `baseline()` once to re-snapshot.
#
#   bullets = Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))
#   b = bullets.spawn()                  # -> a now-visible sprite, or None if full
#   if b: b.data = {"vx": 6}; b.move(x, y)
#   for s in bullets.items:              # zero-alloc iteration
#       if not s.visible: continue
#       ...
#       if done: bullets.free(s)


_NF = 9   # baseline fields per slot: flash, tint, dither, shadow, scale, angle, frame, flip_x, flip_y


class Pool:
    def __init__(self, scene, bitmap, capacity, anchor=None, fixed=False):
        import picogame as pg
        self.items = [pg.Sprite(bitmap, 0, 0, visible=False) for _ in range(capacity)]
        self.alive = bytearray(capacity)   # the in-use bit; `visible` is purely "draw this"
        self._live = 0                     # how many bits are set (read-only for callers)
        for s in self.items:
            if anchor is not None:
                s.anchor = anchor
            s.data = None
            scene.add(s, fixed=fixed)
        # What a fresh slot looks like - 9 fields per slot in ONE flat list (no per-slot tuple:
        # 64 slots = 2.3 KB instead of 3.3 KB), allocated HERE on the clean start-up heap and only
        # written to at the first spawn(), so post-construction set-up counts and the first shot
        # of the game allocates nothing.
        self._base = [0] * (_NF * capacity)
        self._snapped = False

    def baseline(self):
        """Snapshot what a FRESH slot looks like (scale/angle/frame/flips/a permanent tint).
        `spawn()` restores this snapshot, so a slot never comes back wearing the last user's
        hit-flash. Taken by itself at the first spawn(); call this to re-snapshot after
        reconfiguring the sprites later in the game."""
        b = self._base
        k = 0
        for s in self.items:               # in-place: the list was sized at construction
            b[k] = s.flash
            b[k + 1] = s.tint
            b[k + 2] = s.dither
            b[k + 3] = s.shadow
            b[k + 4] = s.scale
            b[k + 5] = s.angle
            b[k + 6] = s.frame
            b[k + 7] = s.flip_x
            b[k + 8] = s.flip_y
            k += _NF
        self._snapped = True
        return self

    def spawn(self):
        """Take the first free slot, show it and return its sprite (or None if full).

        The slot is handed back in its BASELINE look (see `baseline()`): the blit effect,
        scale/angle, frame and flips are restored to what they were at the first spawn(),
        so a rock recycled from an exploding one is not still flashing white. Only `.data`
        and position are the caller's to set."""
        al = self.alive
        if self._live == len(al):          # full: skip the scan (the usual case for a spammed
            return None                    #  bullet pool, and the slowest one before this)
        if not self._snapped:
            self.baseline()
        b = self._base
        for i in range(len(al)):
            if not al[i]:
                al[i] = 1
                self._live += 1
                s = self.items[i]
                k = i * _NF
                if (b[k] != s.flash or b[k + 1] != s.tint or b[k + 2] != s.dither
                        or b[k + 3] != s.shadow):
                    s.flash, s.tint, s.dither, s.shadow = b[k], b[k + 1], b[k + 2], b[k + 3]
                if b[k + 4] != s.scale:
                    s.scale = b[k + 4]
                if b[k + 5] != s.angle:
                    s.angle = b[k + 5]
                if b[k + 6] != s.frame:
                    s.frame = b[k + 6]
                if b[k + 7] != s.flip_x:
                    s.flip_x = b[k + 7]
                if b[k + 8] != s.flip_y:
                    s.flip_y = b[k + 8]
                s.visible = True
                return s
        return None

    def free(self, s):
        """Return s's slot to the pool and hide it. Raises ValueError if s isn't ours."""
        i = self.items.index(s)
        if self.alive[i]:                  # a second free() of the same sprite is a no-op
            self.alive[i] = 0
            self._live -= 1
        s.visible = False

    def free_all(self):
        al = self.alive
        for i in range(len(al)):
            al[i] = 0
        self._live = 0
        for s in self.items:
            s.visible = False

    def count(self):
        """Count of live slots (O(1)). Iterate `pool.items` for the sprites."""
        return self._live
