# picogame sprite animation helpers. Drive a Sprite from a frame sequence on a time
# basis, so games stop hand-rolling `(frame // 4) % n`.
#
# A "frame" in the sequence is either an int (a frame index into the sprite's own
# multi-frame bitmap -> sets sprite.frame; the classic sheet case), or a whole Bitmap
# (swapped in via sprite.bitmap; lets you animate a LIST of separate bitmaps -- e.g.
# from_mask sprites, which are one bitmap each). Don't mix the two kinds in one list.

class FrameAnim:
    """Plays one frame sequence on a sprite. Call tick(dt) each frame.
    Sequence entries are frame indices (int -> sprite.frame) or Bitmaps (-> sprite.bitmap)."""

    def __init__(self, sprite, frames, *, fps=8, loop=True):
        self.sprite = sprite
        self.configure(frames, fps, loop)

    def configure(self, frames, fps=8, loop=True):
        """(Re)point this animation at a frame sequence + reset - lets one FrameAnim be reused
        across animation switches instead of allocating a new one. `frames` is referenced, not
        copied (treated read-only)."""
        self.frames = frames
        self.fps = fps
        self.loop = loop
        self.reset()
        return self

    def _show(self, frame):
        # int = index into the sprite's sheet; anything else = a Bitmap to swap in
        if isinstance(frame, int):
            self.sprite.frame = frame
        else:
            self.sprite.bitmap = frame

    def reset(self):
        self.t = 0.0
        self.i = 0
        self.done = False
        if self.frames:
            self._show(self.frames[0])

    def tick(self, dt):
        if self.done or not self.frames:
            return
        self.t += dt
        adv = int(self.t * self.fps)
        if adv:
            self.t -= adv / self.fps
            self.i += adv
            n = len(self.frames)
            if self.i >= n:
                if self.loop:
                    self.i %= n
                else:
                    self.i = n - 1
                    self.done = True
            self._show(self.frames[self.i])


class AnimatedSprite:
    """A sprite with named animations: anims = {name: (frames, fps, loop)}.
    `frames` is a list of frame indices (into the sprite's sheet) OR a list of Bitmaps
    to swap in (for from_mask-style sprites that are one bitmap each).

        hero = picogame_anim.AnimatedSprite(sprite, {
            "idle": ([0], 1, True),
            "walk": ([1, 2, 3, 2], 8, True),          # frame indices into a sheet
        })
        hero.play("walk"); ... hero.tick(dt)
    """

    def __init__(self, sprite, anims):
        self.sprite = sprite
        self.anims = anims
        self.current = None
        self.anim = FrameAnim(sprite, (), fps=8, loop=True)   # one reusable instance (no per-switch alloc)

    def play(self, name):
        if name == self.current:
            return
        self.current = name
        frames, fps, loop = self.anims[name]
        self.anim.configure(frames, fps, loop)

    def tick(self, dt):
        if self.anim is not None:
            self.anim.tick(dt)
