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

    Disables displayio auto-refresh, clears the root group, allocates two strip
    buffers (full width x `strip_h`, each `width*strip_h*2` bytes -> these two are the
    bulk of setup's RAM) and builds a Scene.

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
    display = display if display is not None else board.DISPLAY
    display.auto_refresh = False
    try:
        display.root_group = None
    except Exception:
        pass
    w = display.width
    buf_a = bytearray(w * strip_h * 2)
    buf_b = bytearray(w * strip_h * 2)
    # Use the fast DMA Display where the firmware provides it; otherwise (a port without
    # the backend, e.g. ESP32) fall back to the plain busdisplay -> Scene's portable renderer.
    backend = pg.Display(display, rgb444=rgb444) if (fast and hasattr(pg, "Display")) else display
    scene = pg.Scene(backend, buf_a, buf_b, background=background,
                     top=top, bottom=bottom, left=left, right=right)
    return scene, buf_a, buf_b
