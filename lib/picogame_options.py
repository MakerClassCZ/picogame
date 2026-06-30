# picogame_options: a settings/value menu, built ON the core picogame_ui (SceneBox + rows).
#
# PROVISIONAL - kept OUT of the core `ui` widgets so it can keep evolving without touching tuned,
# shipped widgets. The pick-an-index `ui.Menu` can't carry an adjustable value per row; this can
# (difficulty choice, volume stepper, sound toggle, "Start" action) - the settings / shop pattern.
#
#   import picogame_options as opt
#   m = opt.OptionsMenu(scene, pg, font, 40, 40, 240, [
#           {"key": "diff", "label": "Difficulty", "kind": "choice", "choices": ["Easy","Normal","Hard"]},
#           {"key": "vol",  "label": "Volume",     "kind": "stepper", "value": 7, "min": 0, "max": 10},
#           {"key": "snd",  "label": "Sound",      "kind": "toggle",  "value": True},
#           {"key": "done", "label": "Start",      "kind": "action"},
#       ], WHITE, NAVY, title="OPTIONS")
#   m.show()                              # call once; scene.refresh() paints it
#   ...each frame:  k = m.tick(btn)       # row key on A, ui.CANCEL on B, None navigating
#   if k == "done": diff = m.value("diff")

from picogame_ui import SceneBox, LINE_H, CANCEL


class OptionsMenu:
    """A scene-layer menu whose rows carry an adjustable VALUE - the settings/recruit pattern the
    plain `ui.Menu` (pick-an-index) can't do. UP/DOWN move the cursor, LEFT/RIGHT change the selected
    row's value LIVE (auto-repeat), `A` returns the selected row's `key` (use it for `action` rows
    like "Done"), `B` returns `ui.CANCEL`. Built on `ui.SceneBox`, so use it OVER a live scene
    (`scene.refresh()` every frame); the value changes show immediately.

    rows = a list of dicts; each row is one of:
        {"key": "diff", "label": "Difficulty", "kind": "choice", "choices": ["Easy","Normal","Hard"]}
        {"key": "vol",  "label": "Volume",     "kind": "stepper", "value": 7, "min": 0, "max": 10}
        {"key": "snd",  "label": "Sound",      "kind": "toggle",  "value": True}
        {"key": "done", "label": "Start",      "kind": "action"}
    Read a value any time with `m.value("diff")`. Call `m.show()` once; `scene.refresh()` paints it.
    """

    def __init__(self, scene, pg, font, x, y, w, rows, fg, bg, title=None, border=None):
        self.rows = rows
        self.title = title
        self.sel = 0
        self._t = 1 if title else 0
        for r in rows:                                        # normalise defaults + validate up front
            if r["kind"] == "choice":
                if not r.get("choices"):                      # fail fast here, not mid-render in _vtext/
                    raise ValueError("choice row needs a non-empty 'choices' list")   # _change/value
                r.setdefault("i", 0)
            elif r["kind"] == "stepper":
                r.setdefault("value", r.get("min", 0))
            elif r["kind"] == "toggle":
                r.setdefault("value", False)
        n = len(rows) + self._t
        self.panel = SceneBox(scene, pg, font, x, y, w, 10 + n * LINE_H, fg, bg, nlines=n, border=border)
        self.active = False

    def value(self, key):
        """Current value of the row with this key (choice -> the chosen string, stepper -> int,
        toggle -> bool); None if no such key."""
        for r in self.rows:
            if r.get("key") == key:
                if r["kind"] == "choice":
                    ch = r.get("choices")
                    return ch[r.get("i", 0)] if ch else None
                return r.get("value")
        return None

    def _vtext(self, r):
        if r["kind"] == "choice":
            return r["choices"][r["i"]]
        if r["kind"] == "stepper":
            return str(r["value"])
        if r["kind"] == "toggle":
            return "On" if r["value"] else "Off"
        return ""

    def _row_text(self, i):
        r = self.rows[i]
        mark = "> " if i == self.sel else "  "
        if r["kind"] == "action":
            return mark + r["label"]
        v = self._vtext(r)
        return mark + r["label"] + ("  <%s>" % v if i == self.sel else "   %s " % v)

    def _render(self):
        lines = [self.title] if self.title else []
        for i in range(len(self.rows)):
            lines.append(self._row_text(i))
        self.panel.show(lines)

    def show(self, sel=0):
        self.active = True
        self.sel = max(0, min(sel, len(self.rows) - 1))
        self._render()

    def hide(self):
        self.active = False
        self.panel.hide()

    def _change(self, d):
        r = self.rows[self.sel]
        k = r["kind"]
        if k == "choice":
            r["i"] = (r["i"] + d) % len(r["choices"])
        elif k == "stepper":
            r["value"] = max(r.get("min", 0), min(r.get("max", 99), r["value"] + d * r.get("step", 1)))
        elif k == "toggle":
            r["value"] = not r["value"]
        else:
            return False
        return True

    def tick(self, btn):
        """Returns the selected row's `key` on A, `ui.CANCEL` on B, else None. Value edits (L/R) apply
        live - read them with value()."""
        if not self.active or not self.rows:
            return None
        osel = self.sel
        if btn.repeat(btn.DOWN):
            self.sel = (self.sel + 1) % len(self.rows)
        elif btn.repeat(btn.UP):
            self.sel = (self.sel - 1) % len(self.rows)
        # a toggle flips on a FRESH press only (auto-repeat would oscillate it while held); steppers
        # and choices use repeat so holding L/R adjusts smoothly.
        if self.rows[self.sel]["kind"] == "toggle":
            right, left = btn.just_pressed(btn.RIGHT), btn.just_pressed(btn.LEFT)
        else:
            right, left = btn.repeat(btn.RIGHT), btn.repeat(btn.LEFT)
        changed = self._change(1) if right else (self._change(-1) if left else False)
        if self.sel != osel:                                  # repaint just the two affected rows
            self.panel.set_line(self._t + osel, self._row_text(osel))
            self.panel.set_line(self._t + self.sel, self._row_text(self.sel))
        elif changed:
            self.panel.set_line(self._t + self.sel, self._row_text(self.sel))
        if btn.just_pressed(btn.A):
            return self.rows[self.sel].get("key", self.sel)
        if btn.just_pressed(btn.B):
            return CANCEL
        return None
