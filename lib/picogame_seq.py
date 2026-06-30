# picogame_seq - write timed/sequenced logic as GENERATORS (a coroutine pattern): cutscenes,
# "do X over N frames", staged AI, intros. Each `yield` = "resume me next frame". Compose with
# `yield from`. Drive one per frame with Seq.tick().
#
#   import picogame_seq as seq
#   def intro(spr, label):
#       yield from seq.wait(20)
#       yield from seq.move_over(spr, 160, 90, 24)        # glide over 24 frames
#       label.set("GO!")
#       yield from seq.wait(15)
#   s = seq.Seq(intro(player, hud))
#   ...each frame:  s.tick()        # advances to the next yield; .done when finished


def wait(frames):
    """Pause for `frames` frames."""
    for _ in range(frames):
        yield


def over(frames, fn):
    """Call fn(t) each frame with t going 0..1 over `frames` frames (generic tween)."""
    for i in range(1, frames + 1):
        fn(i / frames)
        yield


def move_over(sprite, x, y, frames):
    """Glide a sprite to (x, y) over `frames` frames (linear)."""
    x0, y0 = sprite.x, sprite.y
    for i in range(1, frames + 1):
        t = i / frames
        sprite.move(int(x0 + (x - x0) * t), int(y0 + (y - y0) * t))
        yield


class Seq:
    """Runs one generator, one step per tick(). Reusable via start()."""

    def __init__(self, gen=None):
        self.gen = gen
        self.done = gen is None

    def start(self, gen):
        self.gen = gen
        self.done = False
        return self

    def tick(self):
        """Advance to the next yield. Returns True when the sequence has finished."""
        if self.done:
            return True
        try:
            next(self.gen)
        except StopIteration:
            self.done = True
        return self.done
