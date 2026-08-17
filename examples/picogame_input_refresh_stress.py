# picogame input -> sprite mutation -> Scene.refresh() stress test.
#
# This is a hardware diagnostic, not a game. It replays logical UP/DOWN button
# masks without depending on a particular GPIO or USB input backend, then tests
# the renderer paths separately:
#
#   1. baked rotation frames (the path used by the Starship tutorial),
#   2. runtime Sprite.angle rotation,
#   3. sub-pixel movement through fx/fy,
#   4. runtime angle plus a forced full repaint (and fb.sync, when configured).
#
# Copy as code.py together with picogame_game.py and picogame_shapes.py. On the
# desktop simulator:
#
#   python3 sim/run.py examples/picogame_input_refresh_stress.py --backend pil
#
# A successful device run ends with "[PG-REFRESH] PASS" on the serial console.
# A hard fault/reset is identified by the last printed "BEGIN ..." marker.

import gc
import sys
import time

import picogame as pg
import picogame_game
import picogame_shapes as shapes


W, H = 320, 240
FRAMES = 16
IMPLEMENTATION = getattr(sys.implementation, "name", "")
ON_DEVICE = IMPLEMENTATION == "circuitpython"
NATIVE_WASM = IMPLEMENTATION == "micropython"
ITERATIONS = 600 if ON_DEVICE else (1000 if NATIVE_WASM else 24)
CYCLES = 3 if ON_DEVICE else 1
PREFIX = "[PG-REFRESH]"


def mem_free():
    fn = getattr(gc, "mem_free", None)
    return fn() if fn is not None else -1


class ReplayButtons:
    """Minimal Buttons-compatible source alternating logical UP and DOWN."""

    # picogame_input's public bitmask contract, repeated here deliberately so
    # this renderer test cannot be affected by the USB backend under development.
    UP = 1 << 0
    DOWN = 1 << 1

    def __init__(self):
        self.state = 0
        self._step = 0

    def poll(self):
        # Include released samples so this also resembles button edge traffic.
        sequence = (self.UP, 0, self.DOWN, 0)
        self.state = sequence[self._step & 3]
        self._step += 1
        return self.state

    def is_pressed(self, mask):
        return bool(self.state & mask)


def check_dirty(rect):
    if rect is None:
        raise RuntimeError("mutation produced no dirty rect")
    if not (0 <= rect[0] < rect[2] <= W and 0 <= rect[1] < rect[3] <= H):
        raise RuntimeError("invalid dirty rect: %r" % (rect,))


def run_phase(name, mutate, cycle_index, *, full_repaint=False):
    gc.collect()
    before = mem_free()
    print("%s BEGIN %s cycle=%d iterations=%d free=%d" %
          (PREFIX, name, cycle_index + 1, ITERATIONS, before))
    for _ in range(ITERATIONS):
        buttons.poll()
        changed = mutate()
        if full_repaint:
            scene.invalidate()
        dirty = scene.refresh()
        if changed or full_repaint:
            check_dirty(dirty)
    gc.collect()
    after = mem_free()
    print("%s END %s free=%d delta=%d" % (PREFIX, name, after, after - before))


scene, _, _ = picogame_game.setup(background=pg.rgb565(7, 10, 20))
buttons = ReplayButtons()

# Left: the exact pre-baked frame pattern used by 02-starship.
baked_bitmap = shapes.poly_frames(
    30, [(0, -13), (10, 11), (0, 6), (-10, 11)], FRAMES,
    pg.rgb565(120, 210, 255),
)
baked_ship = pg.Sprite(baked_bitmap, 90, H // 2)
baked_ship.anchor = (0.5, 0.5)

# Right: deliberately asymmetric so every runtime angle is visually obvious.
runtime_bitmap = shapes.from_mask([
    "....##......",
    "....####....",
    "############",
    "############",
    "....####....",
    "....##......",
], pg.rgb565(255, 170, 70))
runtime_ship = pg.Sprite(runtime_bitmap, 230, H // 2)
runtime_ship.anchor = (0.5, 0.5)

scene.add_all([baked_ship, runtime_ship])
scene.refresh()

frame_index = 0
runtime_angle = 0
move_direction = 1


def mutate_frame():
    # Intentionally let vertical input drive the same local frame index that
    # LEFT/RIGHT drives in Starship. This covers a mis-mapped gamepad D-pad too.
    global frame_index
    if buttons.is_pressed(buttons.UP):
        frame_index = (frame_index - 1) % FRAMES
    elif buttons.is_pressed(buttons.DOWN):
        frame_index = (frame_index + 1) % FRAMES
    else:
        return False
    baked_ship.frame = frame_index
    return True


def mutate_angle():
    global runtime_angle
    if buttons.is_pressed(buttons.UP):
        runtime_angle += 11
    elif buttons.is_pressed(buttons.DOWN):
        runtime_angle -= 4
    else:
        return False
    runtime_angle %= 360
    runtime_ship.angle = runtime_angle
    return True


def mutate_position():
    global move_direction
    if buttons.is_pressed(buttons.UP):
        move_direction = -1
    elif buttons.is_pressed(buttons.DOWN):
        move_direction = 1
    else:
        return False
    runtime_ship.fy += move_direction * 0.75
    if runtime_ship.fy < 40:
        runtime_ship.fy = H - 40
    elif runtime_ship.fy > H - 40:
        runtime_ship.fy = 40
    return True


print("%s START cycles=%d iterations=%d" % (PREFIX, CYCLES, ITERATIONS))
for cycle in range(CYCLES):
    run_phase("baked-frame-dirty", mutate_frame, cycle)
    run_phase("runtime-angle-dirty", mutate_angle, cycle)
    run_phase("position-dirty", mutate_position, cycle)
    run_phase("runtime-angle-full-repaint", mutate_angle, cycle, full_repaint=True)

print("%s PASS" % PREFIX)

# Keep the final frame visible on-device and prove an idle scene remains stable.
# Host runners (the Python simulator and native-C WASM test) must be allowed to exit.
while ON_DEVICE:
    time.sleep(1)
    scene.refresh()
