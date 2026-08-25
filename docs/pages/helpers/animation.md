---
title: "Animation & sequencing"
description: "Guide to picogame_anim, picogame_seq and picogame_cutscene: time-based sprite frames, coroutine timelines, and low-RAM cutscene images."
---

These three Python helpers cover sprite animation, timed sequences, and full-screen still images. `picogame_anim` advances animation from elapsed time, `picogame_seq` expresses timelines as generators, and `picogame_cutscene` streams an image without keeping the full frame in the Python heap. See [/reference/](/reference/) for their signatures.

## picogame_anim

Give `FrameAnim` a sequence and an `fps`, then call `tick(dt)` once per game frame with the elapsed time in seconds. Sequence entries can be frame indices for a sprite sheet or separate `Bitmap` objects. The animation follows elapsed time instead of loop count.

There are two classes:

- **`FrameAnim(sprite, frames, *, fps=8, loop=True)`** - plays one sequence. `frames` is a list or tuple of frame indices, or of `Bitmap` objects. The sequence is referenced rather than copied, so treat it as read-only. `fps` sets the animation speed and `loop` is keyword-only. Construction displays `frames[0]` when the sequence is not empty.
  - **`.tick(dt)`** - advance by `dt` real seconds. Accumulates time, steps the frame when enough has passed. No-op once a non-looping anim is finished or if `frames` is empty. No return value.
  - **`.configure(frames, fps=8, loop=True)`** - re-point this same instance at a new sequence and reset it. Returns `self`. Lets you reuse one `FrameAnim` instead of allocating a new one on every switch.
  - **`.reset()`** - back to frame 0, clears the `done` flag and time accumulator.
  - Attributes you can read: **`.done`** (True when a non-looping anim has reached its last frame), `.i` (current index into `frames`), `.frames`, `.fps`, `.loop`.
- **`AnimatedSprite(sprite, anims)`** - a sprite with named states. `anims` is a dictionary `{name: (frames, fps, loop)}`. It keeps one reusable `FrameAnim`, so switching an animation does not allocate another driver.
  - **`.play(name)`** - switch to that named animation. Looks up `anims[name]` and reconfigures. Calling `play` with the name already playing is a no-op, so it is safe to call every frame.
  - **`.tick(dt)`** - advance the current animation.

```python
import picogame_anim

hero = picogame_anim.AnimatedSprite(self.spr, {
    "run":  (DINO_RUN, 12, True),
    "jump": ((DINO_JUMP,), 1, False),
})
hero.play("run")
# each frame, with dt = real seconds since last frame:
hero.play("jump" if self.jumping else "run")  # cheap to call every frame
hero.tick(dt)
```

For one sequence, such as a spinning coin, use `FrameAnim` directly: `spin = picogame_anim.FrameAnim(sprite, list(range(COIN_FRAMES)), fps=15)`.

:::note[Gotchas]
you must pass real `dt` (seconds per frame, e.g. from `picogame_clock`), not a frame count - passing `1` makes it run at `fps` frames per *call*. The `frames` list is held by reference, so do not mutate it while it is in use. `.done` only ever becomes True for `loop=False`.
:::

## picogame_seq

`picogame_seq` expresses timed logic as generators. Each `yield` pauses until the next game frame, and each `tick()` advances one generator to its next `yield`. Use it for intros, staged AI, and other ordered actions. Compose smaller sequences with `yield from`.

Generator helpers (call them with `yield from`):

- **`wait(frames)`** - pause for `frames` frames (yields that many times, doing nothing).
- **`over(frames, fn)`** - generic tween: calls `fn(t)` each frame with `t` ramping `0..1` (specifically `i/frames` for `i` in `1..frames`) over `frames` frames.
- **`move_over(sprite, x, y, frames)`** - glide a sprite from its current position to `(x, y)` over `frames` frames, linearly, via `sprite.move(...)`.

The driver:

- **`Seq(gen=None)`** - wraps one generator. If `gen` is `None` it starts already `.done`.
  - **`.start(gen)`** - point it at a (new) generator and clear `done`. Returns `self`, so it is reusable.
  - **`.tick()`** - advance to the next `yield`. Catches `StopIteration` and sets `.done`. **Returns** the `done` flag (True once finished), so you can branch on it.
  - **`.done`** - True when the sequence has finished.

```python
import picogame_seq as seq

def intro(hero, label):
    yield from seq.wait(30)
    label.set("GO!")
    yield from seq.move_over(hero, 120, hero.y, 20)   # glide over 20 frames

s = seq.Seq(intro(player, hud))
# each frame:
if not s.tick():        # advances one step; True once the intro is over
    ...                 # still running
```

:::note[Gotchas]
`tick()` advances exactly one step (to the next `yield`) per call, so drive it once per game frame. Anything between `yield`s runs in a single frame - keep heavy work behind a `yield`. A `Seq` runs *one* generator; to run several timelines at once, give each its own `Seq`, or merge them with `yield from` inside one generator.
:::

## picogame_cutscene

`picogame_cutscene` displays a full-screen still without loading the complete image into the Python heap. A 320x240 source occupies 153,600 bytes in RGB565 or 76,800 bytes in PAL8. The module instead reads a raw, row-major file from flash one **band** at a time and renders each band to the display backend.

The temporary source band costs `w * band` bytes for PAL8 or `w * band * 2` bytes for RGB565. With the default `w=320` and `band=24`, that is 7,680 or 15,360 bytes in addition to the render buffer passed to `show()`. Reduce `band` if the allocation does not fit. Once rendered, the still image needs no additional Python object containing the full frame. See [/memory/](/memory/) for the other memory costs.

Bake the raw file first with `tools/bake_cutscene.py` (PNG to PAL8 + a palette module, or wire-order RGB565 rows). See [/scene-format/](/scene-format/) for engine bitmap formats and [/hardware/](/hardware/) for the display and buttons.

- **`palette(pg, rgb)`** - build the device palette (`array('H')` of wire colours) from a `bake_cutscene.py` palette module, a list of `(r, g, b)` triplets, or wire ints. Build it ONCE at setup and reuse it - `show()` would otherwise rebuild it per call.
- **`show(pg, display, buffer, path, pal=None, w=320, h=240, scale=None, band=24, bg=0)`** - stream the image at `path` one band at a time and render each band with the supplied engine strip `buffer`. `pal` selects PAL8 input (1 B/px); `None` selects RGB565 (2 B/px). `scale=None` derives an integer scale from the display (`width // w`) and rejects a source size that does not fill both axes. A short final band is cleared with `bg`. Returns the scale used.
- **`play(pg, display, buffer, btn, path, pal=None, w=320, h=240, scale=None, band=24, caption=None, caption_lines=None, auto_hold=0, clock=None, bg=0)`** - show the image, add optional caption lines in a dark bar, then block until **A** or **B** is pressed. With `auto_hold > 0`, it advances after that many loop ticks and `btn` may be `None`. Pass a `picogame_clock` instance as `clock` to pace the wait loop.

```python
import picogame_cutscene as cut
import board

PAL = cut.palette(pg, intro_pal)                       # once, at setup
cut.play(pg, picogame_game.display(), bufA, btn, "intro.raw", pal=PAL,
         caption="Chapter 1", clock=clock)
scene.invalidate()                                     # the image clobbered the LCD
```

:::note[Gotchas]
this uses the immediate drawing path, outside the scene. Pause or fade the scene first, then call `scene.invalidate()` after `play()` returns so the next `refresh()` repaints it. The input must be a raw, row-major file produced by `bake_cutscene.py`; a PNG cannot be passed directly. `play()` blocks the game loop while it waits.
:::
