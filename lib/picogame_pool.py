# picogame_pool: a reusable fixed-size sprite pool - the exact pattern every
# spawner game (bullets, enemies, orbs, pipes) hand-rolled: pre-allocate N sprites
# added to the scene, a free-slot scan to spawn, hide to free, and a plain list to
# iterate. Uses `sprite.visible` AS the alive flag (no parallel data["on"]), and
# `sprite.data` for per-entity state. Iterate `pool.items` directly (zero alloc).
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
        for s in self.items:
            if anchor is not None:
                s.anchor = anchor
            s.data = None
            scene.add(s, fixed=fixed)

    def spawn(self):
        """Make the first free sprite visible and return it (or None if full)."""
        for s in self.items:
            if not s.visible:
                s.visible = True
                return s
        return None

    def free(self, s):
        s.visible = False

    def free_all(self):
        for s in self.items:
            s.visible = False

    def count(self):
        """Count of live sprites (cheap). Iterate `pool.items` for the sprites."""
        n = 0
        for s in self.items:
            if s.visible:
                n += 1
        return n
