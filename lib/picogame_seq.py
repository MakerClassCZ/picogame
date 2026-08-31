# picogame_seq - timed/sequenced logic as GENERATORS (a coroutine pattern). Each `yield` =
# "resume me next frame"; compose with `yield from`; drive one per frame with Seq.tick().
#
# Two jobs:
# 1) timed logic - intros, cutscene beats, "do X over N frames", staged AI:
#      def intro(spr, label):
#          yield from seq.wait(20)
#          yield from seq.move_over(spr, 160, 90, 24)     # glide over 24 frames
#          label.set("GO!")
#      s = seq.Seq(intro(player, hud))
#      ...each frame:  s.tick()      # .done when finished
#
# 2) SCRIPTED INPUT - the module's original purpose: a game that PLAYS ITSELF. `Script` is an
#    input source for picogame_input.Buttons, so the demo runs through the game's own input
#    path (just_pressed/repeat all work), on device and in the sim alike:
#      def play(s):                                   # masks = Buttons flags
#          yield from s.rest(6)
#          yield from s.tap(B.A)                      # leave the title
#          yield from s.hold(B.RIGHT, 40)             # drive
#      script = seq.Script(play, loop=True)
#      btn.attach(script)                             # attract mode ON (title sat idle)
#      ...each frame:  script.tick(); btn.poll()
#      if btn.state & ~script.mask:                   # a HUMAN pressed something ->
#          btn.detach(script); script.stop()          #  hand the controls back


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


class Script:
    """A scripted input source: plays a `play(script)` generator through
    `picogame_input.Buttons` - attract-mode demos, self-playing titles, and scripted
    verification runs, all through the game's OWN input path (device-legal; no sim
    backdoor). Inside play(): `yield from s.hold(mask, n)` / `s.tap(mask)` / `s.rest(n)`,
    masks being Buttons flags (B.A | B.RIGHT). Call `tick()` once per frame BEFORE
    btn.poll(); attach/detach with Buttons.attach()/detach(). `loop=True` restarts the
    script when it ends (an attract loop); reading `mask` lets the game spot a human
    override: `btn.state & ~script.mask`."""

    def __init__(self, play, loop=False):
        self._play = play
        self._loop = loop
        self._mask = 0
        self._gen = play(self)
        self.done = False

    def hold(self, mask, frames):
        """Hold exactly `mask` for `frames` frames (replaces the current press)."""
        self._mask = mask
        for _ in range(frames):
            yield

    def tap(self, mask, frames=2, gap=3, base=0):
        """Press `mask` for `frames` frames (1-2 = what just_pressed needs), then release
        back to `base` for `gap` frames. `base` = a mask to keep held throughout."""
        self._mask = base | mask
        for _ in range(frames):
            yield
        self._mask = base
        for _ in range(gap):
            yield

    def rest(self, frames):
        """Release everything for `frames` frames."""
        self._mask = 0
        for _ in range(frames):
            yield

    def tick(self):
        """Advance one frame. Returns True while the script is still running."""
        if self.done:
            return False
        try:
            next(self._gen)
        except StopIteration:
            if self._loop:
                self._gen = self._play(self)
            else:
                self._mask = 0
                self.done = True
        return not self.done

    def stop(self):
        """End the script and release every button it holds."""
        self._mask = 0
        self.done = True

    @property
    def mask(self):
        """The buttons the script is pressing THIS frame (for human-override detection)."""
        return self._mask

    def read(self):                          # Buttons source contract
        return self._mask
