# picogame scaffold: one-call setup of the display takeover, a retained Scene and
# its double strip buffers, so games skip the boilerplate.
#
#   import picogame_game
#   scene, bufA, bufB = picogame_game.setup(background=picogame.rgb565(20, 24, 40))
#   ...
#   scene.add(sprite); scene.refresh()

import board
import picogame as pg


def setup(display=None, strip_h=None, background=0, fast=True, top=0, bottom=0, left=0, right=0,
          rgb444=False):
    """Take over the display and return (scene, buffer_a, buffer_b).

    Disables displayio auto-refresh, clears the root group and builds a Scene. On a
    busdisplay (SPI) target it also allocates two strip buffers (full width x `strip_h`,
    each `width*strip_h*2` bytes -> these two are the bulk of setup's RAM). On a
    FRAMEBUFFER target (WASM playground, Fruit Jam DVI) the scene composites straight
    into the framebuffer and the returned buffers are None.

    `strip_h` defaults to `picogame.STRIP_H` (board compile-time default: 8 on DMA boards, 24
    without). Measured (RP2040): on a DMA board smaller `strip_h` is BOTH less RAM AND faster
    (the DMA/render overlap is finer); without DMA, larger wins (fewer blocking sends). A typical
    dirty-rect repaint is insensitive to it. Pass an int to override per game. See /memory/.

    `top`/`bottom`/`left`/`right` reserve a border (px) the scene won't render into, so it
    paints only the inner play rect - draw the border yourself (HUD bars, side panels,
    a frame) so it's never recomputed per frame. E.g. a centred Tetris column: left/right.

    fast=True uses the platform fast Display (async DMA, where available).
    fast=False drives the plain busdisplay via the portable bus.send renderer -
    the same path used on ports without a DMA backend (correct everywhere, slower).

    rgb444=True (fast Display only) sends 12-bit RGB444 instead of 16-bit RGB565: ~25% less
    SPI traffic -> more FPS on transfer-bound (full-screen/scrolling) scenes, 4096 colours
    (plenty for PAL8 art). Needs a controller with COLMOD 12-bit (ST7789/ST7735; not ILI9341).
    rgb444="auto" enables it only where the board reports support (picogame.RGB444_SUPPORTED),
    so one codebase runs optimally on ST7789 and safely (RGB565) on ILI9341 - no per-board code."""
    if rgb444 == "auto":
        rgb444 = getattr(pg, "RGB444_SUPPORTED", False)
    if strip_h is None:
        strip_h = getattr(pg, "STRIP_H", 8)   # board compile-time default (CIRCUITPY_PICOGAME_STRIP_H; 8 DMA/24 not)
    # PICOGAME_INVERT in settings.toml = the panel's correct resting inversion state. ST7789 panels
    # come in BOTH polarities and the board init picks one (PicoPad sends INVON) - a user with the
    # other panel variant sees a negative. When the key IS SET, enforce it here (pg.invert sends
    # INVON/INVOFF - free, no pixel data); unset = leave the board init alone (other boards may not
    # send INVON at all). picogame_fx.PANEL_INVERTED reads the same key, so the InvertFlash
    # hit-flash stays calibrated with it - one toml key fixes both.
    # Two siblings for the other panel-variant/QoL fixes reachable on a board.c-built display:
    #   PICOGAME_MADCTL     absolute MADCTL byte (0x36 register: mirrors + BGR order). Absolute on
    #                       purpose - the register can't be read back, so bit-flips would need a
    #                       per-board baseline. PicoPad values: 0x60 stock | 0x68 BGR panel |
    #                       0xA0 mounted 180 deg | 0xA8 both. (DIY boards: use the custom-board
    #                       PICOGAME_FLIP/PICOGAME_BGR keys instead - their launcher rebuilds.)
    #   PICOGAME_BRIGHTNESS backlight, integer PERCENT 0-100 (settings.toml has no floats).
    try:
        import os
        _inv = os.getenv("PICOGAME_INVERT")
        _mad = os.getenv("PICOGAME_MADCTL")
        _bri = os.getenv("PICOGAME_BRIGHTNESS")
        if _inv is not None or _mad is not None or _bri is not None:
            _d = _current_display()          # supervisor.runtime.display (the primary display)
            if _inv is not None:
                _on = (_inv != 0) if isinstance(_inv, int) else \
                    str(_inv).strip().lower() not in ("", "0", "false", "no")
                pg.invert(_d, _on)
            if _mad is not None:
                _d.bus.send(0x36, bytes([int(str(_mad), 0) & 0xFF]))
            if _bri is not None:
                _d.brightness = max(0, min(100, int(_bri))) / 100
    except Exception:
        pass                                  # no display / no invert (sim variants): ignore
    backend, is_fb = resolve_display(display)
    if is_fb:
        # Framebuffer target (WASM playground, Fruit Jam DVI): the scene composites straight
        # into it - no strip buffers exist on this path, so none are allocated. The returned
        # buffers are None; pg.render ignores its buffer arg on this target, so HUD helpers
        # that just pass it through still work. (A helper that STAGES bytes into the buffer -
        # picogame_cutscene bands - needs its own bytearray on this platform.)
        scene = pg.Scene(backend, None, None, background=background,
                         top=top, bottom=bottom, left=left, right=right)
        return scene, None, None
    # busdisplay (SPI): stop displayio's refresh loop, allocate the two strip buffers.
    try:
        backend.auto_refresh = False
    except (AttributeError, TypeError):
        pass
    try:
        backend.root_group = None
    except (AttributeError, TypeError):
        pass
    w = backend.width
    buf_a = bytearray(w * strip_h * 2)
    buf_b = bytearray(w * strip_h * 2)
    # Use the fast DMA Display where the firmware provides it; otherwise (a port without
    # the backend, e.g. ESP32) fall back to the plain busdisplay -> Scene's portable renderer.
    if fast and getattr(pg, "FAST_DISPLAY_SUPPORTED", hasattr(pg, "Display")):
        backend = pg.Display(backend, rgb444=rgb444)
    scene = pg.Scene(backend, buf_a, buf_b, background=background,
                     top=top, bottom=bottom, left=left, right=right)
    return scene, buf_a, buf_b


_RESOLVED = {}   # id(display) -> (display, backend, is_fb): setup() and every HUD that normalizes
                 # the display share ONE wrapper (no per-frame Framebuffer realloc). The original
                 # display is kept as a STRONG ref in the tuple so its id can't be reused by a later
                 # object (stale-alias guard), and the hit is re-verified with `is` before reuse.


_TARGET = {}   # id(display) -> (display, backend): alloc-free hot-path cache for target()


def open_framebuffer(width, height, color_depth=None):
    """Ensure the display is a DVI framebuffer at width x height, and return it.

    Lets a game pick its OWN resolution in code (fresh interpreter per game via the launcher),
    so nothing has to be hand-set in settings.toml. Behaviour by board:
      - a DVI/framebuffer board that exposes the picodvi pins (Fruit Jam: board.CKP/CKN/D0P...):
        if the current display already matches width x height it is reused (no realloc / flicker,
        and this cleanly absorbs a resolution left behind by the previous game across a soft
        reload); otherwise release_displays() + a fresh picodvi.Framebuffer at this size;
      - a fixed-panel board (ST7789 SPI PicoPad) or the sim: a NO-OP - returns the existing
        display unchanged (the panel is a fixed size; the request is simply ignored).

    If the new size does not fit in internal SRAM, the PREVIOUS mode is rebuilt and republished
    before the MemoryError propagates - a failed switch must never leave the board displayless
    (a soft reload does not re-run the firmware's display auto-construct, so that state survives
    until a power cycle). CALL THIS BEFORE importing any module that captures the display at
    import time.

    color_depth defaults to 16 (RGB565) for <= 320x240 and 8 (RGB332) above - 8-bit is the only
    depth picodvi offers at 640x480, and the engine already renders RGB332. 640x480 needs PSRAM.
    """
    try:
        import board
    except ImportError:
        return None
    cur = _display_or_none()          # the display in use right now, if any
    # fixed-panel board / sim: no picodvi module or no DVI pins -> use whatever display exists
    try:
        import picodvi
        import framebufferio
        import displayio
    except ImportError:
        return cur
    if not hasattr(board, "CKP"):
        return cur
    if cur is not None and getattr(cur, "width", None) == width \
            and getattr(cur, "height", None) == height:
        return cur                              # already the right size -> reuse
    if color_depth is None:
        color_depth = 16 if width * height <= 320 * 240 else 8
    # The size we are leaving, so a failed switch can put it back. release_displays() frees the
    # scanout buffer we are about to reuse the memory of, so it has to happen first - which is
    # exactly why a failure here would otherwise leave the board with NO display until a power
    # cycle (a soft reload does not re-run the firmware's auto-construct).
    prev = (getattr(cur, "width", 0), getattr(cur, "height", 0)) if cur is not None else None
    displayio.release_displays()

    def _build(w, h, depth):
        fb = picodvi.Framebuffer(
            w, h,
            clk_dp=board.CKP, clk_dn=board.CKN,
            red_dp=board.D0P, red_dn=board.D0N,
            green_dp=board.D1P, green_dn=board.D1N,
            blue_dp=board.D2P, blue_dn=board.D2N,
            color_depth=depth)
        return framebufferio.FramebufferDisplay(fb, auto_refresh=False)

    try:
        disp = _build(width, height, color_depth)
    except MemoryError:
        if prev is None or prev == (width, height):
            raise MemoryError(_scanout_hint(width, height, color_depth))
        try:                                    # put the previous mode back, then report
            disp = _build(prev[0], prev[1], 16 if prev[0] * prev[1] <= 320 * 240 else 8)
        except MemoryError:
            raise MemoryError(
                "no memory for %dx%d, and %dx%d could not be restored - power-cycle the board"
                % (width, height, prev[0], prev[1]))
        _publish(disp)
        raise MemoryError("%s (kept %dx%d)"
                          % (_scanout_hint(width, height, color_depth), prev[0], prev[1]))
    _publish(disp)
    return disp


def _scanout_hint(width, height, depth):
    """Explain a failed mode switch in terms of the resource that actually ran out.

    A bare MemoryError sends people to gc.mem_free(), which on a PSRAM board (Fruit Jam) cheerfully
    reports megabytes free and even hands out a 599 kB bytearray - while the scanout buffer needs
    CONTIGUOUS SRAM that the GC heap has already taken. Measured 2026-08-23: 640x480x8 = 307200 B
    fails from code.py with ~8 MB of heap 'free'. The heap number is not the constraint; when it is
    claimed is."""
    return ("no memory for %dx%d: the scanout buffer needs %d B of CONTIGUOUS SRAM, which gc.mem_free() "
            "does not measure (the heap may live in PSRAM). Claim the mode in boot.py, before the "
            "heap grows into SRAM." % (width, height, width * height * (depth // 8)))


def _publish(disp):
    """Make `disp` the display everything else finds.

    Publishing it as the PRIMARY display is not best-effort: release_displays() cleared the primary
    slot, and display()/screen() read nothing else - a swallowed failure here would surface later
    as "no display" from setup(). Only a host without supervisor is tolerated. board.DISPLAY is
    set too where the slot is writable, as a courtesy to code that still reads it directly."""
    try:
        import board
        board.DISPLAY = disp                 # boards with a settable slot (our custom-board builds)
    except (AttributeError, TypeError):
        pass
    try:
        import supervisor
    except ImportError:
        supervisor = None
    if supervisor is not None:
        supervisor.runtime.display = disp


def target(display):
    """Immediate-render target for pg.render: a framebuffer board's FramebufferDisplay -> its
    pg.Framebuffer (memoized via resolve_display); a BusDisplay / pg.Display / pg.Framebuffer (none of
    which carry a `.framebuffer` attr) passes straight through. Lets HUD / Label / overlay / cutscene
    helpers accept a bare display object on every platform. Resolver errors (bad rotation / colour
    depth / old firmware) propagate - the caller sees the real reason, not a later 'expected a BusDisplay'."""
    if getattr(display, "framebuffer", None) is None:
        return display
    key = id(display)                        # alloc-free on hits: resolve_display's (backend, is_fb)
    hit = _TARGET.get(key)                    # tuple would allocate per call on this per-frame path
    if hit is not None and hit[0] is display:
        return hit[1]
    backend = resolve_display(display)[0]
    _TARGET[key] = (display, backend)
    return backend


def _display_or_none():
    """The board's primary display, or None where nothing published one (no raise)."""
    try:
        import supervisor
        return supervisor.runtime.display
    except (ImportError, AttributeError):
        return None


def _current_display():
    """The board's display, wherever it comes from - use this instead of `board.DISPLAY` so a game
    runs on every board:

        hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, BG)

    The source is `supervisor.runtime.display` - the board's PRIMARY display - and only that, so
    there is ONE way a display reaches a game on every platform:
      - the firmware built one: CircuitPython selects it right after board_init(), before boot.py;
      - a boot.py, a launcher or open_framebuffer() built one: they publish it with
        `supervisor.runtime.display = disp` (it survives into code.py - reset_displays() does not
        clear the primary slot);
      - the simulator and the WASM playground ship a `supervisor` shim whose runtime.display
        proxies their own display.
    Reading it (rather than a board's static DISPLAY) also means a RELEASED display reads back as
    None instead of a stale handle. A host without `supervisor` - another MicroPython embedding -
    adds the same small shim; it has no `board.DISPLAY` either, so there is nothing to fall back to.
    """
    d = _display_or_none()
    if d is None:
        raise RuntimeError("no display: build one in boot.py and publish it with "
                           "`supervisor.runtime.display = disp` (see CUSTOM_BOARD)")
    return d


display = _current_display          # public name (resolve_display's parameter shadows it inside)


def screen():
    """Screen size as `(width, height)` - the size-independent way to lay a game out:

        W, H = picogame_game.screen()

    Same source as display(), so it works on every board and in the sim/playground alike."""
    d = _current_display()
    return (d.width, d.height)


def resolve_display(display=None):
    """Find and normalize the render target. Returns (backend, is_framebuffer).

    Search order: the explicit `display` -> `supervisor.runtime.display` (the primary display: set
    by the firmware, or published by boot.py / a launcher / the sim+playground supervisor shim).
    Normalization:
      - a `pg.Framebuffer` passes through unchanged (the WASM playground's display);
      - a framebuffer display (has `.framebuffer`, e.g. framebufferio.FramebufferDisplay
        over picodvi) is unwrapped: auto-refresh off, root group cleared, and its RAW
        scanout buffer wrapped as `pg.Framebuffer(..., native_rgb565=True)` - requires the
        16-bit rotation-0 mode (Fruit Jam settings.toml: CIRCUITPY_DISPLAY_COLOR_DEPTH=16);
      - anything else is a busdisplay (SPI) returned as-is; setup() picks fast/portable.
    Shared by setup() and picogame_scene.load() so the platform logic lives ONCE."""
    if display is None:
        try:
            display = _current_display()          # the board's primary display
        except RuntimeError:
            raise RuntimeError("no display: if you just added boot.py press RESET once (boot.py runs "
                               "only at power-on, not on save/reload); on a DVI board set "
                               "CIRCUITPY_PICODVI_ENABLE=\"always\" in settings.toml; on a bare "
                               "board publish yours with `supervisor.runtime.display = disp`")
    key = id(display)
    hit = _RESOLVED.get(key)
    if hit is not None and hit[0] is display:      # verify identity: guards a reused id() (stale alias)
        return hit[1], hit[2]
    if hasattr(pg, "Framebuffer") and isinstance(display, pg.Framebuffer):
        _RESOLVED[key] = (display, display, True)
        return display, True
    raw = getattr(display, "framebuffer", None)
    if raw is not None:
        # a displayio FramebufferDisplay: stop its refresh loop, then wrap the raw buffer
        try:
            display.auto_refresh = False
            display.root_group = None
        except (AttributeError, TypeError):
            pass
        if getattr(display, "rotation", 0) != 0:
            raise ValueError("picogame needs rotation 0 (set CIRCUITPY_DISPLAY_ROTATION=0)")
        depth = getattr(raw, "color_depth", 16)
        if depth not in (8, 16):
            raise ValueError("picogame needs a 16-bit or 8-bit framebuffer "
                             "(set CIRCUITPY_DISPLAY_COLOR_DEPTH=16 in settings.toml)")
        # The engine composites each dirty band OFF-SCREEN (a private scratch strip) and memcpys only
        # the finished band into the live scanout buffer, so the beam never samples a half-composited
        # region (no flicker) and never wire-order bytes (no colour tearing). Colour handling: if the
        # scanout HW byte-swaps 16bpp pixels on read (`pixel_byte_swap=True`, the default), the buffer
        # must hold NATIVE RGB565 so the engine byte-swaps the scratch before the copy; a build that
        # disabled the HW swap reports `pixel_byte_swap=False` and we store the engine's WIRE order
        # directly. Absent property (normal firmware) -> assume native. Two-way firmware skew-tolerant.
        if depth == 8:
            # 8-bit picodvi scanout is RGB332 (the only depth the HW offers at
            # 640x480, e.g. Fruit Jam full-res) - the engine quantizes each
            # finished band 565->332 while publishing it.
            try:
                fb = pg.Framebuffer(raw, raw.width, raw.height, rgb332=True)
            except TypeError:
                raise RuntimeError("this firmware's picogame.Framebuffer lacks rgb332 - "
                                   "flash a newer picogame build")
        else:
            native = bool(getattr(raw, "pixel_byte_swap", True))
            try:
                fb = pg.Framebuffer(raw, raw.width, raw.height, native_rgb565=native)
            except TypeError:
                raise RuntimeError("this firmware's picogame.Framebuffer lacks native_rgb565 - "
                                   "flash a newer picogame build")
        _RESOLVED[key] = (display, fb, True)
        return fb, True
    _RESOLVED[key] = (display, display, False)
    return display, False


def overlay(scene, display, items, buffer, x0, y0, x1, y1, *, background=0):
    """Immediate-draw `items` over a live retained scene, keeping the two consistent.

    `pg.render()` paints straight to the panel; the retained scene doesn't know those
    pixels changed, so its next `refresh()` would repaint only its own dirty rects and
    leave stale overlay fragments on screen. This wraps `pg.render` + `scene.invalidate()`
    so the first refresh after the overlay repaints the full frame.

    Use it for one-off screens drawn OVER the scene's play area: pause, menu, cutscene,
    a banner. HUD bands OUTSIDE the play rect (the `top=`/`bottom=` reserves) do NOT
    need it - the scene never touches those pixels, call `pg.render` there directly.

    Args mirror `pg.render`: `items` may be any layer kinds (a StripDraw with `view.text`
    = a 0-RAM text screen), `buffer` is a strip buffer (reuse the one from setup())."""
    pg.render(target(display), items, buffer, x0, y0, x1, y1, background=background)
    scene.invalidate()
