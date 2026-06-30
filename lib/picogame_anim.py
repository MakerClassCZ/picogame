# picogame sprite animation helpers. Drive a Sprite's frame from a
# frame sequence on a time basis, so games stop hand-rolling `(frame // 4) % n`.

class FrameAnim:
    """Plays one frame sequence on a sprite. Call tick(dt) each frame."""

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

    def reset(self):
        self.t = 0.0
        self.i = 0
        self.done = False
        if self.frames:
            self.sprite.frame = self.frames[0]

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
            self.sprite.frame = self.frames[self.i]


class AnimatedSprite:
    """A sprite with named animations: anims = {name: (frames, fps, loop)}.

        hero = picogame_anim.AnimatedSprite(sprite, {
            "idle": ([0], 1, True),
            "walk": ([1, 2, 3, 2], 8, True),
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
