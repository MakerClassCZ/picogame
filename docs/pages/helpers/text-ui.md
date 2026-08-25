---
title: "Text & UI"
description: "Bitmap text, HUD labels, dialog boxes, cursor menus, and editable options."
---

These modules render bitmap text and provide HUD, dialog, menu, grid-cursor, and options controls. See the [reference](/reference/) for signatures and the tutorials for complete examples.

## picogame_font

This module renders a `fontio` font, commonly `terminalio.FONT`, into a PAL8 `picogame.Bitmap`. Use it for text that needs to become a sprite or an immediate label.

If you just want a score in a corner, `Label` is the simplest choice; the fuller widget picture (scene layers vs. immediate widgets) is explained below under [picogame_ui](#picogame_ui).

- `render_text(pg, font, text, fg, bg=None)` - composes `text` into a `PAL8` bitmap and returns the tuple `(bmp, w, h)` (bitmap plus pixel size). `fg`/`bg` are wire colours from `pg.rgb565(...)`. `bg=None` leaves the background transparent (palette index 0); an opaque `bg` means a redraw fully overwrites the old text, so HUD updates need no separate clear.
- `render_text_pal(pg, font, text, fg, bg=None)` - same as above but returns `(bmp, w, h, palette)`. Keep the `palette` (an `array('H')`) and mutate `palette[1]` (the fg colour) for a live colour shimmer without rebuilding the bitmap - the C `Bitmap` reads the same buffer.
- `Label(pg, font, x, y, fg, bg)` - a positioned label drawn immediately (good for a HUD over a screen you render yourself).
  - `.set(text)` - re-renders only if the text changed; returns `True` if it did, `False` if skipped. Coerces non-strings via `str()`.
  - `.move(x, y)` - repositions and forces a re-render at the new spot on the next `set`/`draw`.
  - `.draw(display, buffer)` - repaints just the label's rectangle via `pg.render` (a single present).
  - `.w`, `.h` - pixel size of the last rendered text.

```python
import picogame_font, terminalio
hud = picogame_font.Label(pg, terminalio.FONT, 4, 4,
                          pg.rgb565(255, 255, 255), BG)
shown_score = -1                # shadow int: last value the label shows
# each frame, after you draw the screen:
if score != shown_score:        # only format when the number changes
    shown_score = score
    hud.set("SCORE %06d" % score)
hud.draw(picogame_game.display(), bufA)   # repaints just its rect
```

![picogame_font.Label — immediate HUD text chips](/img/ui_label.png)

:::note[Gotchas]
after changing `bmp.palette` or the array returned by `render_text_pal()`, the new colour appears on the next repaint. Use `picogame_ui.SceneLabel` over a live scene; an immediate `Label` is not tracked by `scene.refresh()`.
:::

### Extra glyphs: `ExtraFont`

`terminalio.FONT` is ASCII only. `picogame_font.ExtraFont` extends it with glyphs from one or more small
BDF files, looked up as **fallbacks** — the built-in font first, then each BDF in order, so extra files
only ever *add* glyphs and blend seamlessly with normal text. Two subsets ship in `lib/fonts/` (cut from
CircuitPython's own Terminus build, the same one `terminalio.FONT` comes from):

- **`picogame_cz.bdf`** — Czech diacritics (á č ď é ě í ň ó ř š ť ú ů ý ž and capitals).
- **`picogame_symbols.bdf`** — game symbols: arrows, hearts, block/shade fills, triangles, ✓/✗, ♥ ♫ ☼, ° ½ × ÷ and more:

![The picogame_symbols.bdf game-glyph set, with each glyph's Unicode code point](/img/extrafont_symbols.png)

```python
import picogame_font
font = picogame_font.ExtraFont("/lib/fonts/picogame_cz.bdf", "/lib/fonts/picogame_symbols.bdf")
bmp, w, h = picogame_font.render_text(pg, font, "Život 3  ♥♥♥  →", fg)
```

Pass the `ExtraFont` anywhere this module takes a font (`render_text`, `render_text_pal`, `Label`, and the
`picogame_ui` widgets built on them). Glyphs load eagerly (~20 B each; a 30-glyph set is under 1 KB).

**Limitation:** `ExtraFont` is a *Python-side* font for this module's render paths only. The **native C
text path** (`picogame.Canvas.text`, and therefore `picogame_ui.SceneLabel` / `HudBar` and a `StripDraw`
`view.text`) validates a `fontio.BuiltinFont` in firmware and will **not** accept an `ExtraFont` — use the
`render_text`/`Label` path when you need the extra glyphs. To make your own subset, `tools/make_bdf_subset.py`.

## picogame_bitfont

This 8×8 bitmap font uses four shades and includes arrows, hearts, a star, a note, and box-drawing symbols in codes 0–31; codes 32 and above cover ASCII. Its outline can keep transparent text legible over the game world.

- `render_text(pg, text, fg=None, outline=None, mid=None, bg=None)` - renders `text` to a `PAL8` bitmap and returns `(bitmap, w, h)`. The four shades map to: `0 -> bg`/transparent, `1 -> outline`, `2 -> mid`, `3 -> fg`. Colour defaults: `fg` white, `outline` black, `mid` mid-grey; all are `rgb565` wire colours. Supports `\n` for multi-line. Pass `bg` for an opaque background (else index 0 is transparent).
- Symbol constants (1-char strings you concatenate into text): `ARROW_U`, `ARROW_D`, `ARROW_R`, `ARROW_L`, `BOXX`, `STAR`, `HEART`, `BALL`, `NOTE`.
- `GLYPH_W`, `GLYPH_H` - both `8`, the per-glyph cell size.

```python
import picogame_bitfont as bf
bmp, w, h = bf.render_text(pg, "LIVES " + bf.HEART * 3)  # white, outlined, transparent
spr = pg.Sprite(bmp, x, y)                               # place anywhere
spr.scale = 2                                            # scale up for big text
```

![picogame_bitfont — outlined transparent text over the world](/img/ui_bitfont.png)

:::note[Gotchas]
the module returns a bitmap but does not provide a label class. Create and update its `Sprite` yourself. Each rendered string occupies its own PAL8 pixel buffer; see [memory](/memory/) when choosing between persistent text sprites and immediate text.
:::

## picogame_ui

Choose widgets by who owns the affected pixels:

- `SceneLabel`, `SceneBox`, and `SceneMenu` are fixed scene layers. `scene.refresh()` repaints them when needed, so use them inside a live or scrolling scene.
- `picogame_font.Label`, `TextBox`, and `Menu` draw immediately through `pg.render()`. Use them on a screen whose redraw you control. `HudBar` is also immediate, but belongs in a border reserved outside the scene.

Pick by what owns the pixels:

| Situation | Class |
|---|---|
| Static screen you redraw yourself (title, game-over, a HUD you repaint) | `Label` |
| A live, scrolling scene where the HUD must **not** scroll | `SceneLabel` |
| A reserved edge bar / status strip | `HudBar` |
| A transient dialog / message box over the live world | `SceneBox` |
| A dialog / battle / menu box on a static screen | `TextBox` |

`tick()`-based widgets return: a chosen index/cell on **A** (confirm), `ui.CANCEL` (`-2`) on **B** (back), or `None` while navigating. See [scene-format](/scene-format/) for the `fixed` layer and [hardware](/hardware/) for the buttons.

**`SceneLabel(scene, pg, font, x, y, fg, bg)`** - one line of text pinned over a scrolling world.
- `.set(text)` - re-renders only on change (swaps the sprite's bitmap; dirty-rect handles old/new bounds). A blank/empty string hides the sprite, leaving no leftover bg patch.
- `.reserve(chars)` - reserve the label's text buffer **now**, on the fresh startup heap, for up to `chars` characters, so a long line first shown *later* (e.g. a game-over banner) isn't allocated on a fragmented heap (a `MemoryError`). Renders nothing visible. See [memory](/memory/).

**`SceneBox(scene, pg, font, x, y, w, h, fg, bg, nlines=3, key=None, border=None)`** - a multi-line dialog or status panel over a live scene. Its `StripDraw` callback composites the panel, border, and text without retaining a pixel surface. Pass `border` for a raised frame.
- `.show(lines)` - fill the panel and set text, then reveal. **Call once**, not per frame.
- `.hide()` - make the panel fully transparent and blank the rows.
- `.set_line(i, text)` - update one row in place (no Canvas/border redraw).

![picogame_ui.SceneBox — a bordered dialog box over a live scene](/img/ui_dialog.png)

**`HudBar(pg, display, buffer, x, y, w, h, bg)`** - an immediate HUD drawn in a border reserved with `Scene(..., top=/bottom=)`. Call `draw()` only after its contents change. It stores label strings and icon references but no panel-sized pixel surface. `buffer` is the render buffer from setup on SPI targets and may be `None` on framebuffer targets.
- `.add(sprite)` - store an icon sprite (hearts, gauges) in the bar; returns it. It's blitted at its own x/y on `draw()`.
- `.label(font, x, y, fg, text=" ")` - add a text field; returns a `_HudLabel` **handle** (not a sprite) which you update with `handle.set(text)` (the same `.set` verb as `SceneLabel`). The text is composited directly, no per-label sprite.
- `.draw()` - repaint the bar (flat bg + icons + text) and push it in one `pg.render`. Takes no arguments - the bar stores the display/buffer/geometry at construction. Call only on HUD changes.

```python
hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, pg.rgb565(10, 12, 24))
hud_l = hud.label(terminalio.FONT, 4, 3, INK, "SCORE 0   LIVES 3")
hud.draw()
# later, only when it changes:
hud_l.set("SCORE %d   LIVES %d" % (score, lives))
hud.draw()
```

![picogame_ui.HudBar — a reserved-band status bar over gameplay](/img/ui_hudbar.png)

**`TextBox(pg, font, x, y, w, h, fg, bg, maxlines=6)`** - a screen-space multi-line box (filled rect + text rows) for static dialog/battle/menu screens.
- `.draw(display, buffer, lines, force=False)` - skips the repaint when `lines` are unchanged; when it does draw, the bg and every row go out in **one** `pg.render` (no blank-fill flash). Pass `force=True` after the screen under it was wiped (e.g. a full-screen `pg.render`).
- `.draw_line(display, buffer, i, text)` - repaint a single row in place, atomically.

**`Menu(pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None, paged=True)`** - an immediate cursor menu built on `TextBox`. UP and DOWN use auto-repeat. `rows=None` shows all items; a smaller value creates a scrolling window. With `paged=True`, crossing an edge moves by a page instead of one row. Arguments after `*` are keyword-only.
- `.tick(btn)` - returns the chosen index on A, `ui.CANCEL` on B, else `None`.
- `.draw(display, buffer, force=False)` - repaints only what changed (nothing / the 2 affected rows on a cursor move / the whole box on scroll). `force=True` repaints unconditionally after a wipe.

```python
bmenu = ui.Menu(pg, terminalio.FONT, 8, H - 72,
                ["ATTACK", "MAGIC", "HEAL", "FLEE"], WHITE, NAVY)
# each frame:
act = bmenu.tick(btn)          # index on A, ui.CANCEL on B, else None
bmenu.draw(picogame_game.display(), bufA)
```

**`SceneMenu(scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None, border=None, paged=True)`** - the same menu but built on `SceneBox`, for use **over a live scene** (battle actions, an in-game popup). Same navigation/paging as `Menu`.
- `.show(sel=0)` - reveal it (resets the cursor). The scene paints it from then on - no `draw()` call.
- `.hide()` - hide it.
- `.tick(btn)` - same return contract as `Menu`; repaints only the rows that changed.

![picogame_ui.SceneMenu — a cursor menu over a live scene](/img/ui_menu.png)

**`GridCursor(cols, rows, tx=0, ty=0, wrap=False)`** - logic-only 2D cursor for a battlefield, tile inventory, or match-3. It owns movement (D-pad auto-repeat) and confirm/cancel; *you* draw the grid and a highlight at `(cursor.tx, cursor.ty)`. `wrap=True` wraps at edges, else it clamps.
- `.tick(btn)` - returns the `(tx, ty)` tuple on A, `ui.CANCEL` on B, else `None`.
- `.tx`, `.ty` - current cell.
- `.index` (property) - `ty * cols + tx`, handy for indexing a flat list.

```python
cur = ui.GridCursor(N, N)               # N x N board
# each frame:
pick = cur.tick(btn)                    # (tx, ty) on A, ui.CANCEL on B, else None
# you draw the highlight yourself at (cur.tx, cur.ty)
```

:::note[Gotchas]
an immediate `Menu` or `TextBox` is not part of the scene and can be overwritten by a later `scene.refresh()`. Use the corresponding `Scene*` widget over a live scene. The default menu width estimates about 11 pixels per character; pass `width=` when using a narrow font or long labels. Call `SceneBox.show()` when its contents change, not every frame.
:::

## picogame_options

`OptionsMenu` adds editable rows to a `SceneBox`. Use it for settings, shops, or selection screens that combine choices, numeric steps, toggles, and actions. It is a scene-layer widget, so `scene.refresh()` displays value changes.

- `OptionsMenu(scene, pg, font, x, y, w, rows, fg, bg, title=None, border=None)` - `rows` is a list of dicts, each with a `kind`:
  - `choice` - `{"key", "label", "kind": "choice", "choices": [...]}`; cycles through the list. (A non-empty `choices` is required - it raises `ValueError` up front otherwise.)
  - `stepper` - `{"key", "label", "kind": "stepper", "value", "min", "max"}`; also honours an optional `"step"` (default 1). Clamps to `min`/`max`.
  - `toggle` - `{"key", "label", "kind": "toggle", "value": True/False}`.
  - `action` - `{"key", "label", "kind": "action"}`; no value, just returns its key on A.
- `.show(sel=0)` - reveal and render (call once); `scene.refresh()` paints it after.
- `.hide()` - hide the panel.
- `.tick(btn)` - UP/DOWN move the cursor; LEFT/RIGHT change the selected row's value live (steppers/choices auto-repeat while held; a toggle flips only on a fresh press, so it can't oscillate). Returns the selected row's `key` on **A**, `ui.CANCEL` on **B**, else `None`.
- `.value(key)` - read a row's current value any time: a `choice` returns the chosen string, a `stepper` an int, a `toggle` a bool; `None` if no such key.

```python
import picogame_options as opt
menu = opt.OptionsMenu(scene, pg, font, 40, 40, 240, [
    {"key": "diff", "label": "Difficulty", "kind": "choice", "choices": ["Easy", "Normal", "Hard"]},
    {"key": "vol",  "label": "Volume",     "kind": "stepper", "value": 7, "min": 0, "max": 10},
    {"key": "snd",  "label": "Sound",      "kind": "toggle",  "value": True},
    {"key": "done", "label": "Start",      "kind": "action"},
], WHITE, NAVY, title="OPTIONS")
menu.show()
while True:
    btn.poll()
    k = menu.tick(btn)
    if k == "done":
        diff = menu.value("diff")          # read live values on the action row
    elif k == opt.CANCEL:
        menu.hide()
    scene.refresh()                        # paints the menu - no draw() call
```

![picogame_options.OptionsMenu — editable settings rows](/img/ui_options.png)

:::note[Gotchas]
it imports `CANCEL` from `picogame_ui`, so `opt.CANCEL` and `ui.CANCEL` are the same `-2`. Being a `SceneBox` widget, it needs a live `scene.refresh()` under it - it won't paint on a static screen drawn purely with `pg.render`.
:::
