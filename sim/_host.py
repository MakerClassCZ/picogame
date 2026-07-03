# Desktop host for the picogame simulator: an RGB565 framebuffer the engine shim
# draws into, a button/key state, a frame counter + stop signal, and pluggable
# "present" backends -- PIL (headless: screenshots / CI, always available) and
# pygame (a live window + keyboard, if installed). The game's own loop drives it;
# present() is called every frame from Scene.refresh / Display.render.

import os as _os
# Display size: defaults to the PicoPad's 320x240, override for other boards via
# PICOGAME_SIM_SIZE=WxH (e.g. "240x240" for the Pimoroni PicoSystem).
try:
    _w, _h = _os.environ.get("PICOGAME_SIM_SIZE", "320x240").lower().split("x")
    W, H = int(_w), int(_h)
except Exception:
    W, H = 320, 240

fb = [0] * (W * H)          # framebuffer, RGB565 wire-order ints
pressed_pins = set()        # SW_* pin names currently held down

_frame = 0
_max_frames = None          # headless: stop after this many presented frames
_frame_hook = None          # optional per-frame callback fn(frame_no) — used by --profile
_backend = None             # set by run.py: "pil" or "pygame"
_pyg = None                 # pygame module + surface, when used
_last_image = None          # PIL.Image of the last frame (pil backend)
_inverted = False           # hardware colour inversion (pg.invert) - show fb's negative while True
_shot_path = None
_shot_at = None             # frame index at which to save a screenshot


class SimStop(Exception):
    """Raised to unwind the game's `while True` loop (frame limit / window close)."""


def configure(backend="pil", max_frames=None, shot=None, shot_at=None):
    global _backend, _max_frames, _shot_path, _shot_at
    _backend = backend
    _max_frames = max_frames
    _shot_path = shot
    _shot_at = shot_at if shot_at is not None else (max_frames - 1 if max_frames else 0)
    if backend == "pygame":
        _init_pygame()


def _init_pygame():
    global _pyg
    import pygame
    pygame.init()
    surf = pygame.display.set_mode((W * 2, H * 2))   # 2x zoom for visibility
    pygame.display.set_caption("picogame simulator")
    _pyg = (pygame, surf)


# wire RGB565 -> (r, g, b) 888
def _unwire(c):
    c = ((c >> 8) | (c << 8)) & 0xFFFF
    return (((c >> 11) & 0x1F) << 3, ((c >> 5) & 0x3F) << 2, (c & 0x1F) << 3)


_KEYMAP = {}     # filled by pygame backend: pygame key -> pin name


def _to_image():
    from PIL import Image
    img = Image.new("RGB", (W, H))
    inv = _inverted
    img.putdata([_unwire((c ^ 0xFFFF) if inv else c) for c in fb])
    return img


def set_frame_hook(fn):
    """Register a callback run once per presented frame as fn(frame_no) (profiling)."""
    global _frame_hook
    _frame_hook = fn


def present():
    """Show the current framebuffer; pump input; enforce the frame limit."""
    global _frame, _last_image
    if _backend == "pygame":
        _present_pygame()
    else:
        if _shot_path is not None and _frame == _shot_at:
            _to_image().save(_shot_path)
    _frame += 1
    if _frame_hook is not None:
        _frame_hook(_frame)
    if _max_frames is not None and _frame >= _max_frames:
        if _backend != "pygame" and _shot_path is not None and _shot_at >= _max_frames:
            _to_image().save(_shot_path)
        raise SimStop()


def _present_pygame():
    pygame, surf = _pyg
    img = bytes()
    # build a 320x240 surface from fb, then scale x2
    frame = pygame.Surface((W, H))
    pa = pygame.PixelArray(frame)
    for y in range(H):
        row = y * W
        for x in range(W):
            c = fb[row + x]
            r, g, b = _unwire((c ^ 0xFFFF) if _inverted else c)
            pa[x, y] = (r << 16) | (g << 8) | b
    del pa
    pygame.transform.scale(frame, (W * 2, H * 2), surf)
    pygame.display.flip()
    pressed_pins.clear()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            raise SimStop()
    keys = pygame.key.get_pressed()
    for key, pin in _KEYMAP.items():
        if keys[key]:
            pressed_pins.add(pin)


def setup_keymap():
    """Map keyboard -> PicoPad SW_* pins (call after pygame init)."""
    import pygame
    # Move with the arrows OR WASD; face buttons on the F/G (A/B) + R/T (X/Y) cluster right of WASD,
    # plus the Ctrl/Space thumb keys, and Q/E as the second X/Y. NO Shift (5x = Windows Sticky Keys).
    _KEYMAP.update({
        pygame.K_UP: "SW_UP", pygame.K_DOWN: "SW_DOWN",
        pygame.K_LEFT: "SW_LEFT", pygame.K_RIGHT: "SW_RIGHT",
        pygame.K_w: "SW_UP", pygame.K_s: "SW_DOWN", pygame.K_a: "SW_LEFT", pygame.K_d: "SW_RIGHT",
        pygame.K_f: "SW_A", pygame.K_LCTRL: "SW_A", pygame.K_RCTRL: "SW_A",
        pygame.K_g: "SW_B", pygame.K_SPACE: "SW_B",
        pygame.K_r: "SW_X", pygame.K_q: "SW_X",
        pygame.K_t: "SW_Y", pygame.K_e: "SW_Y",
    })
