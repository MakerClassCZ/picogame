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
# `sprite.data` for per-entity state - the pool NEVER reads or writes it, so pre-allocating one
# dict per slot at start-up and only mutating it keeps a pool allocation-free.
#
# A recycled slot comes back in its BASELINE look - the blit effect, scale/angle, frame and
# flips are restored to how the pool was built, so last life's hit-flash (or a death scale-up)
# never leaks into the next spawn. Configure the sprites after construction? Call `baseline()`
# once to re-snapshot; the pool then preserves THAT.
#
#   bullets = Pool(scene, bullet_bm, 6, anchor=(0.5, 0.5))
#   b = bullets.spawn()                  # -> a now-visible sprite, or None if full
#   if b: b.data = {"vx": 6}; b.move(x, y)
#   for s in bullets.items:              # zero-alloc iteration
#       if not s.visible: continue
#       ...
#       if done: bullets.free(s)


class Pool:
    def __init__(self, scene, bitmap, capacity, anchor=None, fixed=False):
        import picogame as pg
        self.items = [pg.Sprite(bitmap, 0, 0, visible=False) for _ in range(capacity)]
        self.alive = bytearray(capacity)   # the in-use bit; `visible` is purely "draw this"
        for s in self.items:
            if anchor is not None:
                s.anchor = anchor
            s.data = None
            scene.add(s, fixed=fixed)
        self.baseline()                    # what a fresh slot looks like; re-snap with baseline()
                                           #  if you configure the sprites AFTER construction

    def baseline(self):
        """Re-snapshot what a FRESH slot looks like - call after configuring the pool's sprites
        (scale/angle/frame/a permanent tint). `spawn()` restores this snapshot, so a slot never
        comes back wearing the last user's hit-flash."""
        self._base = [(s.flash, s.tint, s.dither, s.shadow, s.scale, s.angle,
                       s.frame, s.flip_x, s.flip_y) for s in self.items]
        return self

    def spawn(self):
        """Take the first free slot, show it and return its sprite (or None if full).

        The slot is handed back in its BASELINE look (see `baseline()`): the blit effect,
        scale/angle, frame and flips are restored to what they were when the pool was built,
        so a rock recycled from an exploding one is not still flashing white. Only `.data`
        and position are the caller's to set."""
        al = self.alive
        for i in range(len(al)):
            if not al[i]:
                al[i] = 1
                s = self.items[i]
                b = self._base[i]
                if b[0] != s.flash or b[1] != s.tint or b[2] != s.dither or b[3] != s.shadow:
                    s.flash, s.tint, s.dither, s.shadow = b[0], b[1], b[2], b[3]
                if b[4] != s.scale:
                    s.scale = b[4]
                if b[5] != s.angle:
                    s.angle = b[5]
                if b[6] != s.frame:
                    s.frame = b[6]
                if b[7] != s.flip_x:
                    s.flip_x = b[7]
                if b[8] != s.flip_y:
                    s.flip_y = b[8]
                s.visible = True
                return s
        return None

    def free(self, s):
        """Return s's slot to the pool and hide it. Raises ValueError if s isn't ours."""
        self.alive[self.items.index(s)] = 0
        s.visible = False

    def free_all(self):
        al = self.alive
        for i in range(len(al)):
            al[i] = 0
        for s in self.items:
            s.visible = False

    def count(self):
        """Count of live slots (cheap). Iterate `pool.items` for the sprites."""
        return sum(self.alive)
