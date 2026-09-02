# picogame_script: run story scripts written as Python GENERATORS - cutscenes,
# dialogue, levers, map transitions - resumed one step per frame.
#
# A script is a plain generator; `yield` means "wait a frame", the Director's
# primitives are sub-generators that wait for the player or an effect:
#
#     import picogame_script
#
#     def intro(d):
#         yield from d.text(["Old man:", "The gate is stuck.", "Try the lever."])
#         yield from d.ask(["Pull it now?"])
#         if d.answer:
#             view.set_tile_prop(GATE_TILE, "solid", False)
#             d.ev_set("gate_open")
#             yield from d.fade_out()
#             # ... switch maps here ...
#             yield from d.fade_in()
#
#     d = picogame_script.Director(pg, view.scene, btns, terminalio.FONT)
#     d.on("intro", intro)
#
#     while True:                       # the game loop OWNS the frame (nothing blocks)
#         btns.poll()
#         if d.tick():                  # True while a script runs -> freeze the player
#             pass
#         else:
#             move_player()
#             z = view.in_zone(px, py)
#             if z and len(z) > 5 and "script" in z[5]:
#                 d.start(z[5]["script"])
#         view.scene.refresh()
#         clock.tick()
#
# Why generators and not a bytecode VM: in Python, code already IS data - it
# lives on CIRCUITPY, edits need no rebake, and the language ships the resumable
# interpreter (a generator). Bulk TEXT still belongs in data (a dict, or a .dat
# streamed like picogame_cutscene); per-level scripts go in per-level .mpy
# modules imported on map entry, the usual split-per-scene pattern.
#
# Events (`ev_set`/`ev`/`ev_clear`) are a plain set of names - the story's
# "already happened" memory. Persist it yourself with the game's picogame_save
# schema (e.g. pack chosen names into an int) - the Director does not own your
# save file.
#
# RAM: the dialog box is a picogame_ui.SceneBox (buffer-less StripDraw, zero
# retained RAM) and the fade is picogame_fx.Fade; both are built lazily on
# first use, so a game that never calls text() pays nothing. The fade is always
# added to the scene BEFORE the box (layer order is draw order), so dialogue
# stays readable over a dim or a fade; a game that only ever fades pays for
# no box.
#
# The runner underneath is picogame_seq.Seq - the Director adds what a STORY
# needs on top of a bare sequence: the dialog primitives, a script registry the
# level's zones can name, no-interrupt semantics, and the event flags. For
# timed logic with none of that (a glide, a staged intro) use picogame_seq
# directly; its helpers (`seq.move_over`, `seq.over`) compose into scripts here
# with `yield from` just the same.

import picogame_seq


class Director:
    def __init__(self, pg, scene, buttons, font, box=None, nlines=3,
                 fg=0xFFFF, bg=0x0000):
        """`box` = (x, y, w, h) for the dialog panel; default = a bottom strip
        sized from picogame_game.screen()."""
        self.pg = pg
        self.scene = scene
        self.btn = buttons
        self.font = font
        self._boxgeom = box
        self._nlines = nlines
        self._fg, self._bg = fg, bg
        self._scripts = {}
        self._seq = picogame_seq.Seq()
        self._box = None
        self._fade = None
        self.answer = False      # set by ask()
        self.events = set()      # story flags; persist via your save schema

    # -- registry / lifecycle -------------------------------------------------
    def on(self, name, genfunc):
        self._scripts[name] = genfunc
        return self

    def start(self, script):
        """Start a script: a registered name, a generator function, or a
        generator. A script already running is NOT interrupted (returns False)."""
        if not self._seq.done:
            return False
        g = self._scripts.get(script, script)
        if callable(g):
            g = g(self)
        self._seq.start(g)
        return True

    def retarget(self, scene):
        """Point the Director at a NEW scene after a map load. The dialog box
        and fade are dropped and lazily rebuilt on the new scene; the script
        registry and events survive - that is the point of a map transition:
        the story remembers, the world reloads."""
        self.scene = scene
        self._box = None
        self._fade = None

    @property
    def active(self):
        return not self._seq.done

    def tick(self):
        """Advance the running script by one step. Call once per frame, after
        buttons.poll(). Returns True while a script is running - INCLUDING the
        step on which it finishes. That final True is what stops the A press
        that dismissed the last dialog from falling through into the same
        frame's game input and re-triggering the talk zone the player is still
        standing in."""
        if self._seq.done:
            return False
        if self._seq.tick():                  # finished on this step
            if self._box is not None:
                self._box.hide()
        return True

    # -- waiting primitives (use with `yield from`) ---------------------------
    def text(self, lines):
        """Show lines in the dialog box, wait for A, hide."""
        box = self._ensure_box()
        box.show(lines)
        yield                     # the A that STARTED the script must not dismiss it
        while not self.btn.just_pressed(self.btn.A):
            yield
        box.hide()

    def ask(self, lines):
        """Like text(), but A/B choose: d.answer = True (A) / False (B)."""
        box = self._ensure_box()
        box.show(lines)
        yield
        while True:
            if self.btn.just_pressed(self.btn.A):
                self.answer = True
                break
            if self.btn.just_pressed(self.btn.B):
                self.answer = False
                break
            yield
        box.hide()

    def wait(self, frames):
        return picogame_seq.wait(frames)

    def fade_out(self, speed=2.0):
        f = self._ensure_fade()
        f.out(speed)
        while not f.is_done:
            f.tick()
            yield

    def fade_in(self, speed=2.0):
        f = self._ensure_fade()
        f.into(speed)
        while not f.is_done:
            f.tick()
            yield

    # -- events (story flags) -------------------------------------------------
    def ev(self, name):
        return name in self.events

    def ev_set(self, name):
        self.events.add(name)

    def ev_clear(self, name):
        self.events.discard(name)

    # -- lazy parts -----------------------------------------------------------
    def _screen(self):
        import picogame_game
        return picogame_game.screen()

    def _ensure_box(self):
        if self._box is None:
            # Insertion order is z-order, so build the fade FIRST: a box created before the fade
            # would sit under it forever, and dialogue shown over a dim()/fade would be invisible.
            self._ensure_fade()
            import picogame_ui
            if self._boxgeom is None:
                w, h = self._screen()
                bh = 14 * self._nlines + 8
                self._boxgeom = (4, h - bh - 4, w - 8, bh)
            x, y, bw, bh = self._boxgeom
            self._box = picogame_ui.SceneBox(self.scene, self.pg, self.font,
                                             x, y, bw, bh, self._fg, self._bg,
                                             nlines=self._nlines)
        return self._box

    def _ensure_fade(self):
        if self._fade is None:
            import picogame_fx
            w, h = self._screen()
            self._fade = picogame_fx.Fade(self.scene, w, h)
        return self._fade
