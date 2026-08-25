---
title: Game patterns
description: Small recipes for state, levels, camera, scoring, collision, and feedback.
sidebar:
  order: 3
---

These recipes show the *shape* of code reused across genres — the structure and the why. For the
paste-ready code of a specific task (HUD updates, pools, restart, shuffle, input timing), see
[Snippets](/snippets/); the [API reference](/reference/) gives exact signatures and the
[examples](/examples/) show complete games. Keep actors distinguishable by both shape and colour so
they stay readable on a small screen and without colour cues.

## Game structure: state machine + restart
Hold all mutable game state in one **`State`** object, put the per-frame loop in a **function** (`main`),
and branch on `st.mode`. The function keeps the loop's name lookups fast (locals instead of module-global
dict lookups — a measured win on device), and the single object makes restart a one-liner.
```python
class State:
    def __init__(self): self.reset()
    def reset(self):
        self.mode = "title"          # "title" -> "play" -> "over"
        self.score = 0; self.lives = 3

st = State()

def new_game():
    st.reset(); st.mode = "play"     # re-init IN PLACE (clear pools, re-show sprites)

def main():                          # the loop lives in a function -> its names are fast locals
    poll, refresh, tick = btn.poll, scene.refresh, clock.tick   # hoist hot calls to locals
    while True:
        poll()
        if st.mode == "play":
            ...                      # move, collide, score; on death: st.mode = "over"
        elif btn.just_pressed(btn.A):
            new_game()               # title / game-over -> instant restart, no reload
        refresh(); tick()

main()
```
A tiny game (a few state vars) can stay module-level, but this `State` + `main()` shape scales cleanly
and is the recommended default. Ready-to-run skeleton: [try it in the browser](/playground/?ex=game-skeleton).

## Object pool
Reuse a fixed pool for short-lived things such as bullets, coins, blocks, and sparks.
```python
pool = picogame_pool.Pool(scene, BMP, 16, anchor=(0.5, 0.5))
s = pool.spawn()                 # None if full; .visible is the alive flag
if s: s.move(x, y); s.data = ... # pool.free(s) to recycle
```

## Tilemap level
The board for mazes, bricks, platforms, RPG maps: 1 byte/cell, read and written at runtime.
```python
level = pg.Tilemap(tileset, cols, rows); scene.add(level)
level.set_tile(cx, cy, EMPTY)             # write a cell: eat a pellet, break a brick
hit = level.get_tile(cx, cy) in WALLS     # read a cell for collision
```

## Solid-tile collision (per-axis)
For platformer walls and floors, move and resolve **one axis at a time** (X, then Y) so the body never
wedges in corners; probe the leading edge at two points, and step a fast fall one pixel at a time so a
big `vy` can't tunnel through a floor. It's plain per-object Python: cheap, no special engine call.
```python
def move_x(x, y, dx, hw):                       # stop at the wall, don't enter it
    e = x + (hw if dx > 0 else -hw)
    return x if solid(e, y - 2) or solid(e, y - 14) else x + dx

def move_y(x, y, vy, hw):                        # step down so a big vy can't tunnel through the floor
    if vy > 0:
        for _ in range(vy):
            if solid(x, y + 1) or solid(x - hw, y + 1) or solid(x + hw, y + 1):
                return y, 0, True                # landed: y held, vy zeroed, grounded
            y += 1
    return y + vy, vy, False
```

## Scrolling camera
When the world is bigger than the screen: follow and clamp the view; keep the HUD on a `fixed` layer.
```python
scene.set_view(clamp(player.x - W // 2, 0, world_w - W), 0)
```

## Turn-based loop
Puzzle, tactics, RPG: wait for input, resolve one move, redraw. Most frames draw nothing, so it's cheap.
```python
if btn.just_pressed(btn.A):
    resolve_move()               # advance exactly one turn
scene.refresh()                  # only the changed cells repaint
```

## Impact feedback
Combine a sound, short flash, restrained shake, [hit-stop](/helpers/effects/), or particles according to the size of the event.
```python
spr.flash = WHITE                # flat, 1-3 frames
shake.add(0.4)                   # picogame_fx.Shake; shake.tick() each frame
if audio: audio.sfx(picogame_audio.tone(150, 70))
```

## Damage forgiveness: hitbox & i-frames
Make a timing game feel fair: a hitbox smaller than the sprite, plus a mercy window after a hit.
```python
if inv == 0 and threat.near(player, 12):   # hitbox < sprite art
    inv = 45                     # i-frames; blink the player while inv > 0
```

## Score chain
Reward greed: consecutive hits ramp a multiplier; a miss resets it.
```python
# on a hit:  chain += 1; mult = 1 + chain // 5; score += pts * mult
# on a miss: chain = 0;  mult = 1
```
To *display* the score on screen, see [Text & UI](/helpers/text-ui/).

## Difficulty ramp
Ramp speed/density (not HP), in a sawtooth: build, ease at a milestone, re-engage harder.
```python
interval = max(11, 30 - t // 160)            # spawns speed up over time
if (t % 600) >= 54 and t % interval == 0:    # with a ~1.8s lull every ~20s
    spawn()
```

## Scrolling background
A few wrapping sprites create an endless parallax background without a full-screen background bitmap.
```python
for s in stars:
    s.fy += s.speed
    if s.fy > H: s.fy = -2; s.fx = rng.below(W)   # wrap to the top
```

---
For the design *why* (the one verb, juice, difficulty, scope) see [Making it fun](/concepts/making-it-fun/); for the mental model, [How picogame works](/concepts/how-it-works/); the
[tutorials](/tutorials/) build Breakout, a shooter, and an RPG step by step.
