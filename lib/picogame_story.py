# picogame_story: run a game.json's STORY DATA and your story.py through the Director.
#
# The level editor lets a zone carry story data instead of code:
#   {"say": ["line", ...]}                                   one text box
#   {"say": [{"if": "flag", "lines": [...], "set": "f"},     guarded variants, FIRST match wins
#            {"lines": [...]}]}
#   {"ask": {"lines": [...], "set": "flag",                  A/B question; A sets the flag;
#            "yes": [...], "no": [...], "done": [...]}}      "done" shows when it is already set
#   {"goto": ["level", "point"], "if": cond, "denied": [...]} travel with an optional guard
#   {"script": "boss_fight"}                                 -> def boss_fight(d) in story.py
# cond = "flag" | "!flag" | ["flag", "!other"] (AND). Per-level `effects` rules
#   [{"if": cond, "swap": [a, b], "solid": [...], "unsolid": [...], "hide": [...], "show": [...]}]
# are replayed after every level load and after every flag change, so a flag flips the world at
# once and the change survives map travel.
#
# Nothing is compiled or generated: the data is interpreted here (the same ~100 lines on the
# device, in the simulator and in the playground), and story.py is ordinary Python you own.
#
#   import story                                   # your story.py (optional)
#   d = picogame_script.Director(pg, view.scene, btn, terminalio.FONT)
#   st = picogame_story.Story(d, game, story)
#   ...
#   while True:
#       btn.poll()
#       if d.tick():                               # a script runs: player frozen
#           if d.pending:                          # a script asked for another level
#               level, at = d.pending; d.pending = None
#               player = None; view = None; gc.collect()          # two-phase goto: free first
#               view = game.load(level, at); d.retarget(view.scene); st.effects(view)
#       else:
#           move_player()
#           st.enter(view, px, py)                 # start the zone's story on entry (edge-latched)

import picogame_script


def _cond(d, c):
    if c is None:
        return True
    if isinstance(c, (list, tuple)):
        for one in c:
            if not _cond(d, one):
                return False
        return True
    c = str(c)
    if c.startswith("!"):
        return not d.ev(c[1:])
    return d.ev(c)


class Story:
    def __init__(self, director, game=None, module=None):
        self.d = director
        self.game = game
        self.module = module          # your story.py, or None
        self.view = None
        self._zone = None             # the zone the player is standing in (edge latch)
        director.zone_runner = self.zone
        director.on_flag = self._on_flag

    # -- zones ------------------------------------------------------------------
    def enter(self, view, x, y):
        """Call every frame the player moves. Starts the story of the zone just ENTERED
        (a zone the player is still standing in does not restart). Returns True on a start."""
        z = view.in_zone(x, y)
        if z is not self._zone:
            self._zone = z
            if z is not None and len(z) > 5 and isinstance(z[5], dict):
                return self.d.start(z[5])
        return False

    def leave(self):
        """Forget the latched zone (after a level change)."""
        self._zone = None

    def script(self, name):
        fn = getattr(self.module, name, None) if self.module is not None else None
        if fn is None:
            print("story: no def %s(d) in story.py" % name)

            def stub(d):
                yield from d.text(["story.py has no def %s(d)" % name, "write it!"])
            return stub
        return fn

    def zone(self, data):
        """A zone's data -> the generator that plays it (what Director.start runs for a dict)."""
        d = self.d
        if data.get("script"):
            return self.script(data["script"])(d)
        if "say" in data:
            return self._say(data["say"])
        if "ask" in data:
            return self._ask(data["ask"])
        if "goto" in data:
            return self._goto(data)
        return None

    def _say(self, say):
        d = self.d
        if all(isinstance(e, str) for e in say):     # plain string list = one box
            yield from d.text(list(say))
            return
        for e in say:
            if isinstance(e, str):
                e = {"lines": [e]}
            if _cond(d, e.get("if")):
                yield from d.text(list(e.get("lines", ())))
                if e.get("set"):
                    d.set(e["set"])
                return                               # first match wins

    def _ask(self, a):
        d = self.d
        if a.get("set") and a.get("done") and d.ev(a["set"]):
            yield from d.text(list(a["done"]))       # one-shot switch already thrown
            return
        yield from d.ask(list(a.get("lines", ())))
        if d.answer:
            if a.get("set"):
                d.set(a["set"])
            if a.get("yes"):
                yield from d.text(list(a["yes"]))
        elif a.get("no"):
            yield from d.text(list(a["no"]))

    def _goto(self, data):
        d = self.d
        if not _cond(d, data.get("if")):
            yield from d.text(list(data.get("denied") or ["The way is barred."]))
            return
        target = data["goto"]
        if isinstance(target, str):
            target = [target]
        yield from d.goto(target[0], target[1] if len(target) > 1 else None)

    # -- effects ----------------------------------------------------------------
    def effects(self, view):
        """Replay the level's effect rules whose condition holds. Call after every load and
        after every flag change (the Director does the latter through on_flag)."""
        self.view = view
        self.d.view = view                # scripts reach the level through d.view
        if view is None:
            return
        d = self.d
        for rule in view.effects:
            if not _cond(d, rule.get("if")):
                continue
            sw = rule.get("swap")
            if sw:
                view.swap_tiles(sw[0], sw[1])
            for t in rule.get("unsolid", ()):
                view.set_tile_prop(t, "solid", False)
            for t in rule.get("solid", ()):
                view.set_tile_prop(t, "solid", True)
            for n in rule.get("hide", ()):
                s = view.named.get(n)
                if s is not None:
                    s.visible = False
            for n in rule.get("show", ()):
                s = view.named.get(n)
                if s is not None:
                    s.visible = True

    def _on_flag(self, flag):
        self.effects(self.view)
