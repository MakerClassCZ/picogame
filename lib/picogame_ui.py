# picogame_ui: the UI scaffolding the ergonomics review found missing - a
# camera-independent HUD label, a multi-line text box, and a cursor menu. Built on
# the new Scene `fixed` layer (SceneLabel) + the universal pg.render path (TextBox/
# Menu). See ENGINE_ERGONOMICS.md.
#
#   import picogame_ui as ui
#   score = ui.SceneLabel(scene, pg, font, 4, 4, white, black)   # pinned over a scroll
#   score.set("SCORE 1200")                                    # drawn by scene.refresh()
#
#   box = ui.TextBox(pg, font, 8, 180, 304, 52, white, navy)
#   box.draw(scene.display, bufA, ["Villager:", "Beware the slimes."])
#
#   menu = ui.Menu(pg, font, 8, 160, ["ATTACK", "MAGIC", "FLEE"], white, navy)
#   pick = menu.tick(btn); menu.draw(scene.display, bufA)      # pick>=0 on confirm
#
# Lifecycle rule for the Scene* widgets: RECURRING UI (a HUD label, the battle menu) = build ONCE
# and toggle with set("")/hide()/show() - never re-create per visit. ONE-SHOT UI (a tutorial hint,
# a one-time dialog) = destroy() when dismissed, which detaches it from the scene (Scene.remove)
# so GC reclaims it.

import picogame_font

from micropython import const

# The immediate text twin lives in picogame_font; re-export it here so both twins are discoverable
# together: ui.Label (immediate, draw via pg.render) vs ui.SceneLabel (scene-layer, painted by refresh).
Label = picogame_font.Label

LINE_H = const(12)


def _txt(x):
    # None -> "" (a blank/hidden field), not the literal "None"; everything else -> str.
    return "" if x is None else str(x)


# display normalization for pg.render (framebuffer board -> its pg.Framebuffer, else pass-through) is
# the same logic as picogame_font's, so reuse that one rather than ship a second copy.
_target = picogame_font._target


def wrap(text, width, maxlines=None):
    """Word-wrap `text` to `width` chars per line (also breaking on existing newlines); stops after
    `maxlines` lines when given. Returns a list of lines. One wrapper for dialog boxes / mission text /
    the launcher desc etc. (an over-long single word overflows its own line rather than being split)."""
    if not text:
        return []                                    # None/"" -> no lines (a mid-text "\n\n" still keeps its blank)
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if len(trial) <= width:
                line = trial
            else:
                if line:
                    out.append(line)
                    if maxlines and len(out) >= maxlines:
                        return out
                line = word
        out.append(line)
        if maxlines and len(out) >= maxlines:
            return out[:maxlines]
    return out

# tick() return values for Menu / SceneMenu / GridCursor: an index/cell on A (confirm), CANCEL on B
# (back), or None while still navigating. Text menus can also exit via a "Back" item; graphical/tile
# menus use B (the cancel). Pick whichever fits - both are supported.
CANCEL = const(-2)


class SceneLabel:
    """One line of text pinned in the scene as a `fixed` (camera-independent) layer; scene.refresh()
    paints it (no draw call). Text is composed as PAL8 (1 byte/px - HALF the RAM of the old RGB565
    path) via picogame_font, the SAME renderer as the immediate `ui.Label` twin. `bg=None` = transparent
    text over the world; `bg=colour` = a 2-colour opaque box; `scale` = crisp integer scale.

    `reserve(chars)` (or a later over-long string) switches the label to FIXED width: the Bitmap +
    palette are built once and `set()` composes glyphs straight into the retained buffer + touch() -
    NO growth and no rebuilds; the compose leaves ~0.3-0.5 KB of short-lived slice churn per CHANGED
    update on device (freed at the next GC), so update on change, not per frame. Without reserve it
    grows on demand.

    NAMING: scene-layer widgets are `Scene*` (SceneLabel / SceneBox / SceneMenu) - use them OVER a
    live scene (one still calling scene.refresh()). Their immediate twins (Label / TextBox / Menu)
    draw via pg.render and are for a STATIC screen you render entirely yourself.
    FONTS: the glyph-compose path supports ExtraFont; the C `Canvas.text` used by SceneBox/TextBox is
    BuiltinFont-only - so pass an ExtraFont here, not to the box widgets."""

    def __init__(self, scene, pg, font, x, y, fg, bg=None, scale=1, fixed=True):
        self.pg = pg
        self.scene = scene
        self.font = font
        self.fg = fg
        self.bg = bg                        # None = transparent text over the world; a colour = 2-colour box
        self._buf = None
        self._pal = None
        self._fixed = False                 # -> True after reserve()/an over-run: zero-alloc set()
        self._w = 0
        self._chars = 0
        bmp, _, _, self._buf, self._pal = picogame_font._render_into(pg, font, " ", fg, bg, self._buf)
        self.sprite = pg.Sprite(bmp, x, y)
        if scale != 1:
            self.sprite.scale = scale       # integer scale (crisp) - e.g. a big centred message
        scene.add(self.sprite, fixed=fixed)  # fixed=True = camera-independent HUD; False = world-space
        self._text = None

    def _make_fixed(self, n):
        # Build the Bitmap + palette over a fixed n-char buffer ONCE; set() then composes in place.
        bmp, w, _, self._buf, self._pal = picogame_font._render_into(
            self.pg, self.font, " " * n, self.fg, self.bg, None)
        self.sprite.bitmap = bmp
        self._w = w
        self._chars = n
        self._fixed = True

    def set(self, text):
        text = _txt(text)
        if text == self._text:
            return
        self._text = text
        if not text:                        # empty (incl. None) -> hide fully, leaving no bg patch
            self.sprite.visible = False     # (dirty-rect erases the old text box cleanly)
            return
        if self._fixed:
            if len(text) > self._chars:     # outgrew the reserve -> re-fix bigger (one realloc, then stable)
                self._make_fixed(len(text))
            picogame_font.compose_into(self.font, text, self._buf, self._w, self._chars)
            self.sprite.visible = True
            self.sprite.touch()             # pixels changed in place - no new Bitmap, no growth
        else:
            bmp, _, _, self._buf, self._pal = picogame_font._render_into(
                self.pg, self.font, text, self.fg, self.bg, self._buf)
            self.sprite.bitmap = bmp        # grow path: swap (dirty-rect handles old/new bounds)
            self.sprite.visible = True

    def color(self, fg):
        """Recolour in place: rewrite the fg palette entry + touch (no re-render, no alloc)."""
        if fg != self.fg:
            self.fg = fg
            if self._pal is not None:
                self._pal[1] = fg
            self.sprite.touch()

    def show(self, on):
        """Show/hide the label; a blank one stays hidden (matches the box widgets' show())."""
        self.sprite.visible = bool(on and self._text)

    def reserve(self, chars):
        """Pre-build the FIXED-width buffer NOW, on the fresh/contiguous startup heap, for up to `chars`
        characters - so a long line shown only later can't fail on a fragmented heap, AND every set()
        after is zero-alloc (composes in place). A later longer string re-fixes once, then stays stable."""
        self._make_fixed(max(1, chars))
        self.sprite.visible = False         # nothing shown yet...
        self._text = None                   # ...and forget the cached text so a later set() re-renders

    def destroy(self):
        """TRANSIENT label teardown: detach from the scene + drop the text buffer, so GC reclaims
        it (unlike set(None)/visible, which keep the slot + buffer forever). The label is dead -
        make a new one to show text again. (A double destroy raises Scene.remove's ValueError -
        that's a game bug, surfaced, not masked.)"""
        self.scene.remove(self.sprite)
        self._buf = None                    # drop the reused text buffer
        self._pal = None
        self._text = None


class SceneBox:
    """A multi-line text box pinned in the scene, toggled with show()/hide(). A buffer-less StripDraw:
    scene.refresh() composites its panel + border + text straight into the live strip (Canvas.clear /
    frame3d / Canvas.text) - ZERO retained RAM (no Canvas panel), one present, no flicker over a
    scrolling/animated world.

    The scene-layer twin of the immediate `TextBox`. Use SceneBox for a dialog/status box OVER a LIVE
    scene (overworld talk, in-game popup). Use `TextBox` (immediate, pg.render) on a STATIC screen.

        dlg = ui.SceneBox(scene, pg, font, 8, H - 70, W - 16, 62, fg, bg, nlines=3)
        dlg.show(["Villager:", "Beware the slimes", "in the tall grass."])   # call ONCE
        ...                              # scene.refresh() each frame paints it; no per-frame draw
        dlg.hide()                       # when dismissed
    """

    def __init__(self, scene, pg, font, x, y, w, h, fg, bg, nlines=3,
                 key=None, border=None):
        self.pg = pg
        self.scene = scene
        self.font = font
        self.x, self.y, self.w, self.h = x, y, w, h
        self.fg = fg
        self.bg = bg
        self.border = border
        self.nlines = nlines
        self._lines = [""] * nlines
        self._hidden = True
        # On-demand StripDraw (always_dirty=False): repaints only when invalidate()d or overlapped, so
        # a static dialog doesn't re-rasterize+re-push every frame. Every content/visibility change below
        # MUST invalidate() (the box is invisible until something does). Keeps full height: when hidden,
        # the callback draws nothing and invalidate() repaints the rect as bg -> a clean erase.
        self._sd = pg.StripDraw(self._draw, x, y, w, h, always_dirty=False)
        scene.add(self._sd, fixed=True)

    def _draw(self, view, vx, vy, vw, vh):
        # The view spans the WHOLE scene region (vx = region origin, not self.x) - so draw at ABSOLUTE
        # screen coords minus (vx, vy), and fill only our own rect (view.clear would fill the full width).
        if self._hidden:
            return                           # hidden: draw nothing -> the rect shows bg/world (erased)
        x0 = self.x - vx
        y0 = self.y - vy
        view.fill_rect(x0, y0, self.w, self.h, self.bg)
        if self.border is not None:
            view.frame3d(x0, y0, self.w, self.h, self.border, self.bg)
        for i, ln in enumerate(self._lines):
            if ln:
                view.text(x0 + 8, y0 + 7 + i * LINE_H, ln, self.fg, self.font)

    def show(self, lines):
        """Set the text + reveal. Call once (not per frame) - scene.refresh() paints it on change."""
        for i in range(self.nlines):
            self._lines[i] = _txt(lines[i]) if i < len(lines) else ""
        self._hidden = False
        self._sd.invalidate()

    def hide(self):
        self._hidden = True
        self._sd.invalidate()                # repaint the rect once (as bg) -> clean erase, then idle

    def set_line(self, i, text):
        """Update ONE line; invalidate so the next scene.refresh() repaints the box with it."""
        if 0 <= i < self.nlines:
            self._lines[i] = _txt(text)
            self._sd.invalidate()

    def destroy(self):
        """TRANSIENT box teardown: erase + detach from the scene so GC reclaims it (hide() keeps
        the scene slot forever). Dead after - make a new one to show a box again."""
        self.hide()                          # one clean erase repaint first
        self.scene.remove(self._sd)


class _HudLabel:
    """A text field handle returned by HudBar.label(); update with `.set(text)` (same verb as
    SceneLabel.set), then call the bar's draw()."""
    __slots__ = ("x", "y", "fg", "font", "text")

    def __init__(self, x, y, fg, font, text):
        self.x = x
        self.y = y
        self.fg = fg
        self.font = font
        self.text = _txt(text)

    def set(self, text):
        self.text = _txt(text)


class HudBar:
    """A HUD strip drawn OUTSIDE the scene, in a region the scene reserves with
    Scene(..., top=/bottom=). The scene never paints there; `draw()` composites the bar and
    pushes it via one pg.render.

    **Zero retained RAM.** The bar is a buffer-less ``StripDraw``: on draw, ``pg.render`` walks
    the band in strips and the callback composites bg + icons + text straight into the live strip
    via ``Canvas.text`` / ``Canvas.blit`` - NO band buffer, NO glyph cache (``_MASKS``), NO per-label
    Bitmap/Sprite. So the bar can't fragment the heap as it did when text was added incrementally,
    and its cost is independent of the band's size (a full-height side panel is still 0 RAM).
    (Requires firmware where pg.render accepts a StripDraw; the sim mirrors it.)

    Add Sprites (hearts, gauges) with add(); add text with label() -> a handle you update with
    `handle.set(text)`; then call draw(). x/y are screen-absolute. `buffer` is any scratch strip
    buffer (e.g. the scene's bufA) used only as the per-strip push scratch."""

    def __init__(self, pg, display, buffer, x, y, w, h, bg):
        self.pg = pg
        self.display = _target(display)   # accept board.DISPLAY on a framebuffer board (Fruit Jam)
        self.buffer = buffer
        self.x, self.y, self.w, self.h = x, y, w, h
        self.bg = bg
        self._labels = []                   # _HudLabel handles
        self._icons = []                    # icon sprites blitted into the band
        self._sd = pg.StripDraw(self._draw, x, y, w, h)   # buffer-less -> 0 retained RAM

    def _draw(self, view, vx, vy, vw, vh):
        # view-local (0,0) == screen (vx, vy); items are stored screen-absolute, so subtract (vx,vy).
        view.clear(self.bg)
        for spr in self._icons:
            if getattr(spr, "visible", True):
                view.blit(spr.bitmap, spr.x - vx, spr.y - vy, getattr(spr, "frame", 0))
        for lb in self._labels:
            if lb.text:
                view.text(lb.x - vx, lb.y - vy, lb.text, lb.fg, lb.font)

    def add(self, sprite):
        """An icon Sprite (heart, gauge) blitted into the bar at its own x/y on draw()."""
        self._icons.append(sprite)
        return sprite

    def label(self, font, x, y, fg, text=" "):
        """Add a text field; returns a handle - update it with `handle.set(text)` (the same .set as
        SceneLabel), then call `draw()`. The text is composited directly, no per-label sprite."""
        lb = _HudLabel(x, y, fg, font, text)
        self._labels.append(lb)
        return lb

    def draw(self):
        """Repaint the bar (bg + icons + text) and push it. Call only on HUD changes."""
        self.pg.render(self.display, [self._sd], self.buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)


class TextBox:
    """A screen-space multi-line box (immediate, for a STATIC screen). A buffer-less StripDraw: ONE
    pg.render composites bg + (optional border) + text rows straight into the strip via Canvas.text -
    no glyph cache, no per-row sprite, ONE present (no blank-fill flash, no row pop-in). draw() skips
    when the text is unchanged. The immediate twin of SceneBox (use SceneBox over a LIVE scene)."""

    def __init__(self, pg, font, x, y, w, h, fg, bg, maxlines=6, border=None):
        self.pg = pg
        self.font = font
        self.x, self.y, self.w, self.h = x, y, w, h
        self.fg = fg
        self.bg = bg
        self.border = border
        self.maxlines = maxlines
        self._lines = []
        self._drawn = None                  # last drawn lines - skip the repaint if unchanged
        self._sd = pg.StripDraw(self._draw, x, y, w, h)

    def _draw(self, view, vx, vy, vw, vh):
        view.clear(self.bg)
        if self.border is not None:
            view.frame3d(0, self.y - vy, self.w, self.h, self.border, self.bg)
        for i, ln in enumerate(self._lines):
            if ln:
                view.text(6, (self.y + 6 + i * LINE_H) - vy, ln, self.fg, self.font)

    def _render(self, display, buffer):
        self.pg.render(_target(display), [self._sd], buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)

    def draw(self, display, buffer, lines, force=False):
        # Skip when unchanged (callers often redraw a static box every frame). force=True repaints
        # even if unchanged (the screen under us was wiped, e.g. a full-screen pg.render).
        # Compare element-wise (not `list(lines) == self._drawn`) so the common unchanged frame
        # allocates NO throwaway list; the retained copy on change is unavoidable.
        if not force and self._drawn is not None and _seq_eq(lines, self._drawn):
            return
        self._lines = [_txt(x) for x in lines[:self.maxlines]]
        self._drawn = list(lines)
        self._render(display, buffer)

    def draw_line(self, display, buffer, i, text):
        """Update ONE row and repaint the box (one StripDraw push - the whole box is composited in C,
        so a per-row repaint isn't worth a separate pass)."""
        if 0 <= i < len(self._lines):
            self._lines[i] = str(text)
        self._drawn = None
        self._render(display, buffer)


def _seq_eq(a, b):
    """Element-wise sequence compare WITHOUT allocating a copy (unlike `list(a) == b`), so a
    per-frame draw of an unchanged text box makes no throwaway list on the hot idle path."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _menu_step(btn, sel, top, rows, n, paged):
    """Shared cursor + scroll/paging math for both menus (immediate Menu and scene-layer SceneMenu),
    so they navigate identically. Returns (new_sel, new_top, action) where action is "A" (confirm),
    "B" (cancel) or None (still navigating). paged: window jumps a whole page at the edges (cheap -
    most moves keep `top`); else a line scroll (a full repaint per step)."""
    if n == 0:                                        # empty menu -> nothing to navigate
        return sel, top, None
    if btn.repeat(btn.DOWN):                          # auto-repeat while held
        sel = (sel + 1) % n
    elif btn.repeat(btn.UP):
        sel = (sel - 1) % n
    if paged:
        if sel < top or sel >= top + rows:
            top = (sel // rows) * rows
    elif sel < top:
        top = sel
    elif sel >= top + rows:
        top = sel - rows + 1
    if btn.just_pressed(btn.A):
        return sel, top, "A"
    if btn.just_pressed(btn.B):
        return sel, top, "B"
    return sel, top, None


# --- shared menu bits (Menu / SceneMenu / picogame_options.OptionsMenu) ---
def _menu_w(items, width):
    """Box width: explicit `width` wins; else a ~11px/char heuristic sized to the longest label."""
    return width if width else max(60, 11 * max((len(s) for s in items), default=4) + 16)


def _panel_h(nlines):
    """Panel height for a box holding `nlines` text rows (title counts as a row)."""
    return 10 + nlines * LINE_H


def _menu_pick(sel, action):
    """A/B result mapping: chosen index/key on A, CANCEL on B, else None (still navigating)."""
    return sel if action == "A" else (CANCEL if action == "B" else None)


def _menu_lines(title, row_text, top, rows, count):
    """[title?] + the visible window of rows, each via `row_text(i)`. Shared by the item-list menus
    and OptionsMenu's value rows (they differ only in what row_text() returns)."""
    out = [title] if title else []
    for i in range(top, min(top + rows, count)):
        out.append(row_text(i))
    return out


def _marked(item, is_sel):
    """A plain menu row: '> ' cursor marker + the item label."""
    return ("> " if is_sel else "  ") + item


class Menu:
    """A cursor menu over a TextBox. `tick(btn)` returns the chosen index on A (confirm),
    `ui.CANCEL` on B (back), or None while navigating. D-pad UP/DOWN navigate with auto-repeat
    when held. If there are more items than `rows`, the list scrolls to keep the cursor in
    view (default `rows=None` shows them all - no scroll). `draw()` renders a '>' marker.

    `paged=True` (default) advances the window a whole PAGE at a time at the edges instead of
    one line: moving within a page is a cheap 2-row repaint, and only crossing a page boundary
    triggers a full-box repaint. On this hardware a line-by-line scroll repaints the WHOLE box
    every step (the panel can't be hardware-scrolled and the display can't be read back), so
    paging is dramatically snappier on long, near-full-screen lists. Pass paged=False for the
    classic line scroll (smoother-looking, but a full repaint per step) on short lists."""

    def __init__(self, pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None,
                 paged=True):
        self.items = list(items)
        self.title = title
        self.sel = 0
        self.top = 0                                  # first visible item (scroll window)
        self.paged = paged
        self.rows = max(1, min(rows or len(self.items), len(self.items)))   # >=1 so an empty menu still boxes
        n = self.rows + (1 if title else 0)
        self.box = TextBox(pg, font, x, y, _menu_w(self.items, width), _panel_h(n), fg, bg, maxlines=n)
        self._title_rows = 1 if title else 0
        self._dsel = -1            # last-drawn sel/top (two ints, not a per-frame tuple) - detects
        self._dtop = -1            # move vs. scroll vs. idle; -1 sentinel forces the first paint

    def tick(self, btn):
        self.sel, self.top, a = _menu_step(btn, self.sel, self.top, self.rows, len(self.items), self.paged)
        return _menu_pick(self.sel, a)

    def _row_text(self, i):
        return _marked(self.items[i], i == self.sel)

    def draw(self, display, buffer, force=False):
        # Typically called every frame; repaints only on a change (cursor move / scroll) and skips
        # otherwise. The repaint is the whole box in ONE StripDraw pg.render (composited in C, no per-row
        # pop-in), so there's no separate incremental path. force=True repaints unconditionally - pass it
        # when the screen UNDER the menu was wiped (e.g. a full-screen pg.render), since the skip assumes
        # the menu's pixels are still on screen.
        if force:
            self._dsel = -1                           # sentinel never matches a real sel -> repaint
        if self.sel == self._dsel and self.top == self._dtop:
            return
        self.box.draw(display, buffer, _menu_lines(self.title, self._row_text, self.top, self.rows,
                                                   len(self.items)), force=force)
        self._dsel = self.sel
        self._dtop = self.top


class SceneMenu:
    """A cursor menu that lives IN the scene (built on `SceneBox` - a single buffer-less StripDraw
    that composites panel + border + text straight into the live strip, 0 retained RAM). Use it
    OVER a LIVE scene - one that calls `scene.refresh()` every frame (battle actions, an in-game
    choice popup). Because the scene paints it, the fast Display can't push its strips over it and
    erase it (the trap that makes an immediate `Menu` vanish over a live scene).

        m = ui.SceneMenu(scene, pg, font, 96, 64, ["Fireball", "Rally"], WHITE, NAVY, title="CAST")
        m.show()                          # reveal it
        ...each frame:  pick = m.tick(btn)     # >=0 index on A, ui.CANCEL on B, None navigating
        if pick is not None: m.hide()          # hide() to dismiss (destroy() to free the slot)
        # scene.refresh() paints it - no draw() call.

    Same navigation/paging as `Menu` (shared `_menu_step`). Pick `Menu` instead for a STATIC screen
    drawn entirely with pg.render (no scene.refresh under it)."""

    def __init__(self, scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None,
                 border=None, paged=True):
        self.items = list(items)
        self.title = title
        self.sel = 0
        self.top = 0
        self.paged = paged
        self.rows = max(1, min(rows or len(self.items), len(self.items)))
        self._t = 1 if title else 0
        n = self.rows + self._t
        self.panel = SceneBox(scene, pg, font, x, y, _menu_w(self.items, width), _panel_h(n),
                              fg, bg, nlines=n, border=border)
        self.active = False

    def _clamp(self, sel):
        return max(0, min(sel, len(self.items) - 1))

    def _row_text(self, i):
        return _marked(self.items[i], i == self.sel)

    def _render_full(self):
        self.panel.show(_menu_lines(self.title, self._row_text, self.top, self.rows, len(self.items)))

    def show(self, sel=0):
        """Reveal the menu (resets the cursor). The scene paints it until hide()/destroy()."""
        self.active = True
        self.sel = self._clamp(sel)
        self.top = (self.sel // self.rows) * self.rows if self.paged else max(0, min(self.sel, len(self.items) - self.rows))
        self._render_full()

    def hide(self):
        self.active = False
        self.panel.hide()

    def destroy(self):
        """TRANSIENT menu teardown (a one-shot dialog): tears down the underlying SceneBox so the
        scene slot is freed. Dead after."""
        self.active = False
        self.panel.destroy()

    def tick(self, btn):
        if not self.active:
            return None
        osel, otop = self.sel, self.top
        self.sel, self.top, a = _menu_step(btn, self.sel, self.top, self.rows, len(self.items), self.paged)
        if self.top != otop:                                  # scrolled/paged -> redraw the box
            self._render_full()
        elif self.sel != osel:                                # moved in-window -> just the 2 rows
            self.panel.set_line(self._t + (osel - self.top), self._row_text(osel))
            self.panel.set_line(self._t + (self.sel - self.top), self._row_text(self.sel))
        return _menu_pick(self.sel, a)


class GridCursor:
    """A 2D cursor over a cols x rows grid - the battlefield, a tile inventory, match-3, etc.
    LOGIC ONLY: you draw the grid + a highlight at (cursor.tx, cursor.ty); this handles
    movement (D-pad with auto-repeat) and confirm/cancel. `tick(btn)` returns the (tx, ty)
    tuple on A (confirm), `ui.CANCEL` on B (the "cross"/back), or None while navigating.
    `wrap=True` wraps at the edges; otherwise the cursor clamps."""

    def __init__(self, cols, rows, tx=0, ty=0, wrap=False):
        self.cols = cols
        self.rows = rows
        self.tx = tx
        self.ty = ty
        self.wrap = wrap

    @property
    def index(self):
        return self.ty * self.cols + self.tx

    def tick(self, btn):
        dx = (1 if btn.repeat(btn.RIGHT) else 0) - (1 if btn.repeat(btn.LEFT) else 0)
        dy = (1 if btn.repeat(btn.DOWN) else 0) - (1 if btn.repeat(btn.UP) else 0)
        if dx or dy:
            if self.wrap:
                self.tx = (self.tx + dx) % self.cols
                self.ty = (self.ty + dy) % self.rows
            else:
                self.tx = max(0, min(self.cols - 1, self.tx + dx))
                self.ty = max(0, min(self.rows - 1, self.ty + dy))
        if btn.just_pressed(btn.A):
            return (self.tx, self.ty)
        if btn.just_pressed(btn.B):
            return CANCEL
        return None
