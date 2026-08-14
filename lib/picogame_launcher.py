# picogame_launcher - engine-native list+preview launcher (320x240 baseline).
#
# Discovery precedence PER FOLDER:
#   picogame.json  (extended; "apps":[{title,entry,icon,author,category,players,desc}, ...] -> N apps
#                   in one folder; a flat {title,entry,...} = one app)
#   metadata.json  (FruitJamOS-compatible: {title, icon}; also accepts manifest.json) -> one app (entry=code.py)
#   code.py exists -> one app named after the folder            (back-compat with the old flat scan)
#
# Icons: an app's `icon` (relative to its folder) is loaded from a small BMP (BI_RGB 1/4/8/24/32-bit;
# export BI_RGB, not BI_BITFIELDS) into an RGB565 Bitmap for the preview; missing/unreadable/oversize
# -> a lettered placeholder. The preview panel is framed with a 1px view.rect (a rectangle is a
# rectangle - no box-drawing glyphs / font dependency needed).
#
# Launch reuses the proven chaining: supervisor.set_next_code_file(ABSOLUTE entry, working_directory=folder)
# + reload, so each game runs in a fresh interpreter (one game's RAM live) and RESET returns here.
import os
import json
import struct
from array import array
import terminalio
import picogame as pg
import picogame_game
import picogame_clock
from picogame_input import Buttons
try:
    import supervisor          # device only; absent in the desktop sim
except ImportError:
    supervisor = None

FONT = terminalio.FONT
LINE_H = 13

_BG = pg.rgb565(14, 16, 22)
_FG = pg.rgb565(214, 218, 230)
_DIM = pg.rgb565(120, 128, 145)
# picogame brand orange + darker/lighter variants
_ACC = pg.rgb565(0xff, 0x8a, 0x4c)     # #ff8a4c  (title bar, badge)
_ACC_D = pg.rgb565(0xd8, 0x54, 0x0f)   # #d8540f  (selection bar, frame, divider)
_ACC_L = pg.rgb565(0xff, 0xe2, 0xd1)   # #ffe2d1  (selected-row text)
_SEL = _ACC_D
_PANEL = pg.rgb565(26, 30, 42)
_ICON = pg.rgb565(90, 200, 110)

# picogame mark (2 eyes + mouth bar + 3 teeth), tiny 2px units in an 8x8 grid (from logo.svg)
_LOGO = ((1, 0, 2, 2), (5, 0, 2, 2), (0, 3, 8, 2), (0, 6, 2, 2), (3, 6, 2, 2), (6, 6, 2, 2))


class App:
    __slots__ = ("root", "entry", "title", "icon", "author", "category", "players", "desc")

    def __init__(self, root, entry, title, icon=None, author="", category="", players=1, desc=""):
        self.root = root
        self.entry = entry
        self.title = title
        self.icon = icon
        self.author = author
        self.category = category
        self.players = players
        self.desc = desc


# --------------------------------------------------------------------------- BMP -> RGB565 Bitmap
def load_bmp(path):
    """Minimal BMP reader (BI_RGB, 8/24/32-bit; bottom-up or top-down) -> RGB565 pg.Bitmap, or None.
    For small icon.bmp files; not a general image loader."""
    try:
        f = open(path, "rb")
    except Exception:
        return None
    try:
        hdr = f.read(54)
        if len(hdr) < 54 or hdr[0:2] != b"BM":
            return None
        off = struct.unpack_from("<I", hdr, 10)[0]
        dib = struct.unpack_from("<I", hdr, 14)[0]
        w = struct.unpack_from("<i", hdr, 18)[0]
        h = struct.unpack_from("<i", hdr, 22)[0]
        bpp = struct.unpack_from("<H", hdr, 28)[0]
        comp = struct.unpack_from("<I", hdr, 30)[0]
        # cap to what a preview icon needs (48-96 px). 256x256 would be a 128 KB RGB565 buffer =
        # instant OOM on the RP2040; reject early instead of churning the heap for a MemoryError.
        if comp != 0 or w <= 0 or h == 0 or w > 128 or abs(h) > 128 or w * abs(h) > 96 * 96:
            return None
        top_down = h < 0
        hh = -h if top_down else h
        pal = None
        if bpp <= 8:
            ncol = min(struct.unpack_from("<I", hdr, 46)[0] or (1 << bpp), 1 << bpp, 256)
            f.seek(14 + dib)
            praw = f.read(ncol * 4)
            pal = [pg.rgb565(praw[i * 4 + 2], praw[i * 4 + 1], praw[i * 4]) for i in range(ncol)]
        f.seek(off)
        out = array('H', bytes(2 * w * hh))   # 16-bit-unit buffer (sim _u16 path + device wire order)
        row_bytes = ((bpp * w + 31) // 32) * 4
        for ry in range(hh):
            row = f.read(row_bytes)
            base = (ry if top_down else (hh - 1 - ry)) * w
            if bpp == 24 or bpp == 32:
                st = bpp // 8
                for x in range(w):
                    o = x * st
                    out[base + x] = pg.rgb565(row[o + 2], row[o + 1], row[o])
            elif bpp == 8:
                for x in range(w):
                    out[base + x] = pal[row[x]]
            elif bpp == 4:
                for x in range(w):
                    b = row[x >> 1]
                    out[base + x] = pal[(b >> 4) if (x & 1) == 0 else (b & 0xF)]
            elif bpp == 1:
                for x in range(w):
                    out[base + x] = pal[(row[x >> 3] >> (7 - (x & 7))) & 1]
            else:
                return None
        return pg.Bitmap(out, w, hh, format=pg.RGB565, frames=1, stride=w)
    except Exception:
        return None
    finally:
        try:
            f.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- discovery
def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _players(d):
    try:
        return int(d.get("players", 1))
    except (TypeError, ValueError):     # "players": "two" etc. must not sink the whole scan
        return 1


def _apps_in(folder, tag=""):
    name = folder.rsplit("/", 1)[-1]
    pj = _read_json(folder + "/picogame.json")
    if isinstance(pj, dict):            # a stray top-level list/str must not reach .get() -> crash
        apps = pj.get("apps")
        entries = apps if isinstance(apps, list) else [pj]
        out = []
        for e in entries:
            if not isinstance(e, dict):
                continue                # a malformed apps[] entry is skipped, not fatal
            out.append(App(folder, e.get("entry", "code.py"), e.get("title", name), e.get("icon"),
                           e.get("author", ""), e.get("category", tag), _players(e), e.get("desc", "")))
        return out
    mj = _read_json(folder + "/metadata.json") or _read_json(folder + "/manifest.json")
    if isinstance(mj, dict):
        return [App(folder, mj.get("entry", "code.py"), mj.get("title", name), mj.get("icon"),
                    mj.get("author", ""), mj.get("category", tag), _players(mj), mj.get("desc", ""))]
    try:
        os.stat(folder + "/code.py")
        return [App(folder, "code.py", name, category=tag)]
    except OSError:
        return []


def scan(roots=("demos", "games", "apps")):
    """Walk each root, apply the per-folder precedence, return a flat sorted list of App records.
    A missing root is skipped, so the default set is fine even when a drive has only some of them."""
    apps = []
    for d in roots:
        try:
            found = sorted(os.listdir(d))
        except OSError:
            continue
        tag = d.rstrip("/").rsplit("/", 1)[-1]
        for f in found:
            path = d + "/" + f
            try:
                is_dir = (os.stat(path)[0] & 0x4000) != 0
            except OSError:
                continue
            if is_dir:
                apps.extend(_apps_in(path, tag))
            elif f.startswith("picogame_") and f.endswith(".py"):
                # flat dev layout: `picogame_<name>.py` IS a game entry; other .py in the folder
                # (enemy.py, pic_bird.py, *_assets.py ...) are submodules -> skip. Per-folder games
                # (with code.py [+ metadata.json/picogame.json]) are the richer, preferred layout.
                apps.append(App(d, f, f[9:-3], category=tag))
    apps.sort(key=lambda a: a.title.lower())        # plain alphabetical by title
    return apps


def _wrap(s, n, maxlines=3):
    out = []
    s = s or ""
    while s and len(out) < maxlines:
        if len(s) <= n:
            out.append(s)
            break
        cut = s.rfind(" ", 0, n)
        if cut <= 0:
            cut = n
        out.append(s[:cut])
        s = s[cut:].lstrip()
    return out


# --------------------------------------------------------------------------- UI
class _UI:
    def __init__(self, apps, w, h, title):
        self.apps = apps
        self.w = w
        self.h = h
        self.title = title
        self.sel = 0
        self.top = 0
        self.list_w = 176
        self.rows = max(3, (h - 16 - 16) // LINE_H)
        self.cur_icon = None
        self._loaded_sel = -1
        self._desc_lines = ()
        # preview panel geometry
        self.pfx = self.list_w + 4
        self.pfy = 18
        self.pfw = w - self.pfx - 2
        self.pfh = h - self.pfy - 16
        self.pchars = max(8, (self.pfw - 20) // 6)   # chars that fit the preview text column

    def move(self, d):
        n = len(self.apps)
        if not n:
            return
        self.sel = (self.sel + d) % n
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + self.rows:
            self.top = self.sel - self.rows + 1

    def ensure_icon(self):
        if self._loaded_sel == self.sel:
            return
        self._loaded_sel = self.sel
        self.cur_icon = None
        self._desc_lines = ()
        if self.apps:
            a = self.apps[self.sel]
            if a.icon:
                self.cur_icon = load_bmp(a.root + "/" + a.icon)
            # cache the word-wrap per SELECTION: draw() runs once per render strip, so wrapping
            # there redid the same split strips-per-repaint times (10x with the 24-row buffer)
            self._desc_lines = _wrap(a.desc, self.pchars)

    def draw(self, view, vx, vy, vw, vh):
        w, h = self.w, self.h

        def txt(x, y, s, c):
            view.text(x - vx, y - vy, s, c, FONT)

        def box(x, y, bw, bh, c):
            view.fill_rect(x - vx, y - vy, bw, bh, c)

        view.clear(_BG)
        # title bar (brand orange) + mini picogame mark (2 eyes + mouth bar + 3 teeth)
        box(0, 0, w, 15, _ACC)
        for (lx, ly, lw, lh) in _LOGO:            # 8px mark, centred against the 12px text x-height
            box(6 + lx, 3 + ly, lw, lh, _BG)
        txt(18, 2, self.title, _BG)               # 12px terminalio cell centred in the 15px bar
        txt(w - 42, 2, "A play", _BG)
        # list (left)
        ly0 = 18
        for i in range(self.rows):
            idx = self.top + i
            if idx >= len(self.apps):
                break
            a = self.apps[idx]
            y = ly0 + i * LINE_H
            if idx == self.sel:
                box(2, y - 1, self.list_w - 6, LINE_H, _SEL)
            txt(8, y + 1, a.title[:24], _ACC_L if idx == self.sel else _DIM)
        # preview panel frame - a 1px rectangle (the box-drawing glyphs were only ever drawing this)
        px0, py0, pw, ph = self.pfx, self.pfy, self.pfw, self.pfh
        view.rect(px0 - vx, py0 - vy, pw, ph, _ACC_D)
        # preview content
        if self.apps:
            a = self.apps[self.sel]
            cx = px0 + 10
            iy = py0 + 10
            if self.cur_icon is not None:
                iw = self.cur_icon.width
                ih = self.cur_icon.height
                ix = px0 + (pw - iw) // 2
                view.blit(self.cur_icon, ix - vx, iy - vy)
                ibot = iy + ih
            else:
                iw = 48
                ix = px0 + (pw - iw) // 2
                box(ix, iy, iw, iw, _PANEL)
                box(ix + 5, iy + 5, iw - 10, iw - 10, _ICON)
                txt(ix + iw // 2 - 3, iy + iw // 2 - 4, (a.title[:1] or "?").upper(), _BG)
                ibot = iy + iw
            ty = ibot + 8
            txt(cx, ty, a.title[:self.pchars], _FG)
            if a.author:
                txt(cx, ty + LINE_H, ("by " + a.author)[:self.pchars], _DIM)
            badge = (a.category or "")[:9]
            if a.players and a.players > 1:
                badge = (badge + " " if badge else "") + "%dP" % a.players
            if badge:
                txt(cx, ty + LINE_H * 2, badge, _ACC)
            for j, ln in enumerate(self._desc_lines):
                txt(cx, ty + LINE_H * (3 + j), ln, _DIM)
        # hint bar
        box(0, h - 14, w, 14, _PANEL)
        txt(6, h - 12, "UP/DOWN  A=play", _DIM)
        pos = "%d/%d" % (self.sel + 1, len(self.apps)) if self.apps else "0/0"
        txt(w - 42, h - 12, pos, _DIM)


# --------------------------------------------------------------------------- launch + loop
def _launch(app):
    wd = app.root if app.root.startswith("/") else "/" + app.root
    full = wd + "/" + app.entry
    try:
        os.stat(full)                       # a bad picogame.json `entry` must not chain into nothing
    except OSError:
        print("launcher: entry not found:", full)
        return None
    if supervisor is None:
        print("launcher: would run", full, "(wd=%s)" % wd)
        return app
    try:
        supervisor.set_next_code_file(full, working_directory=wd)
    except TypeError:
        supervisor.set_next_code_file(full)
    supervisor.reload()
    return app                              # device: never reached (reload reboots)


def run(apps=None, roots=("demos", "games", "apps"), title="picogame"):
    if apps is None:
        apps = scan(roots)
    # On a DVI board (Fruit Jam) run at the native 320x240 layout - also resets a resolution a
    # previously-run game left behind. No-op on a fixed panel / the sim (returns board.DISPLAY).
    disp = picogame_game.open_framebuffer(320, 240)
    display, is_fb = picogame_game.resolve_display(disp)
    if not is_fb:
        disp.auto_refresh = False
        try:
            disp.root_group = None
        except Exception:
            pass
    w, h = disp.width, disp.height          # size from the display we resolved, not global board.DISPLAY
    buf = None if is_fb else bytearray(w * 24 * 2)
    ui = _UI(apps, w, h, title)
    strips = [pg.StripDraw(ui.draw, 0, 0, w, h)]   # hoisted: no per-paint list alloc
    btn = Buttons()
    clock = picogame_clock.Clock(30)

    def paint():
        ui.ensure_icon()
        pg.render(display, strips, buf, 0, 0, w, h)   # the draw callback view.clear(_BG)s the strip

    paint()
    last = ui.sel                           # first frame already painted - don't repaint it
    while True:
        btn.poll()
        if btn.just_pressed(btn.UP):
            ui.move(-1)
        elif btn.just_pressed(btn.DOWN):
            ui.move(1)
        elif apps and btn.just_pressed(btn.A):
            picked = _launch(apps[ui.sel])
            if picked is not None:
                return picked
        if ui.sel != last:
            paint()
            last = ui.sel
        clock.tick()


def main():
    run()
