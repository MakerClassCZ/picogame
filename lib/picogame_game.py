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
    if fast and hasattr(pg, "Display"):
        backend = pg.Display(backend, rgb444=rgb444)
    scene = pg.Scene(backend, buf_a, buf_b, background=background,
                     top=top, bottom=bottom, left=left, right=right)
    return scene, buf_a, buf_b


def resolve_display(display=None):
    """Find and normalize the render target. Returns (backend, is_framebuffer).

    Search order: the explicit `display` -> `board.DISPLAY` -> `supervisor.runtime.display`
    (boards whose display the supervisor auto-constructs, e.g. the Fruit Jam DVI output).
    Normalization:
      - a `pg.Framebuffer` passes through unchanged (the WASM playground's board.DISPLAY);
      - a framebuffer display (has `.framebuffer`, e.g. framebufferio.FramebufferDisplay
        over picodvi) is unwrapped: auto-refresh off, root group cleared, and its RAW
        scanout buffer wrapped as `pg.Framebuffer(..., native_rgb565=True)` - requires the
        16-bit rotation-0 mode (Fruit Jam settings.toml: CIRCUITPY_DISPLAY_COLOR_DEPTH=16);
      - anything else is a busdisplay (SPI) returned as-is; setup() picks fast/portable.
    Shared by setup() and picogame_scene.load() so the platform logic lives ONCE."""
    if display is None:
        display = getattr(board, "DISPLAY", None)
    if display is None:
        try:
            import supervisor
            display = supervisor.runtime.display
        except (ImportError, AttributeError):
            display = None
    if display is None:
        raise RuntimeError("no display found; on a DVI board set "
                           "CIRCUITPY_PICODVI_ENABLE=\"always\" in settings.toml")
    if hasattr(pg, "Framebuffer") and isinstance(display, pg.Framebuffer):
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
        if getattr(raw, "color_depth", 16) != 16:
            raise ValueError("picogame needs a 16-bit framebuffer "
                             "(set CIRCUITPY_DISPLAY_COLOR_DEPTH=16 in settings.toml)")
        try:
            fb = pg.Framebuffer(raw, raw.width, raw.height, native_rgb565=True)
        except TypeError:
            raise RuntimeError("this firmware's picogame.Framebuffer lacks native_rgb565 - "
                               "flash a newer picogame build")
        # Tear-free full repaints: let the Scene wait for the DVI frame boundary before a
        # large/full-screen composite (e.g. a camera move). Opt-in + best-effort: absent on SPI
        # panels and older firmware, where it simply stays off (no sync).
        waiter = getattr(raw, "wait_for_vblank", None)
        if waiter is not None:
            try:
                fb.sync = waiter
            except AttributeError:
                pass
        return fb, True
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
    pg.render(display, items, buffer, x0, y0, x1, y1, background=background)
    scene.invalidate()
