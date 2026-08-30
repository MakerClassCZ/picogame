# Game Techniques Playbook — reusable recipes mapped to picogame

**How to use.** A catalog of concrete, cross-genre technique recipes (the "how"). When you're
implementing a specific mechanic, pull its recipe here; for *why a
small game is fun* read `SKILL.md`, for *what the API does* read `engine-capabilities.md`, for
*whole-genre walkthroughs* read `genre-patterns.md`. Each entry is: what it is + when → **picogame
mapping** (which class/helper) → a tiny sketch only where it clarifies. Numbers are deliberate.

> Helper note: several recipes use the small Python helpers `picogame_tiles` (tile flags),
> `picogame_seq` (coroutine sequences), `picogame_math` (clamp/lerp/turn-trig), `picogame_palette`
> (cycle/swap/fade). These are tile-id-keyed / generator-driven / pure-math — light to ship.
> `picogame_rand`, `picogame_fx`, `picogame_pool`, `picogame_input.Timer` are in
> the shipped helper table (`engine-capabilities.md` §3).

---

## 1. Game flow & state machines

**Screen flow = one loop + one state variable, not a framework.** Handle `title → play → gameover`
with ONE `while True` loop that branches each frame on a single `mode` int (TITLE/PLAY/OVER) —
exactly the SKILL.md §1.6 skeleton. No FSM class with transitions and hooks, and no blocking
per-screen functions either (a `while` of its own inside `title()` etc.) — those break the single
frame end (`refresh()` + `tick()` in one place) and instant restart. *picogame:* `mode` drives what
you update and draw, but **build the `Scene` ONCE and keep it across states** — toggle `visible`/overlays, and
rebuild only on a true level change (then `gc.collect()`). The non-moving GC fragments if you churn
scenes, so don't tear down and rebuild per state. No engine machinery needed.

**Per-entity state = a small enum in `sprite.data`.** Ghosts carry SCATTER/CHASE/FRIGHTEN/EATEN; a
ball carries SERVE/IN-PLAY. State lives *per actor*, not centrally. *picogame:* stash an int (or a
tuple) in `sprite.data` — the free per-sprite payload — and branch on it in the update loop.

**Sub-step the logic, render once.** Run N deterministic logic steps per visible frame so fast
movers can't tunnel through walls and so replays stay deterministic (typically 2 sub-steps;
Train fixes 6 steps/sec). *picogame:* `picogame_clock.FixedStep(step_fps).steps()` — iterate logic
per yielded step, `scene.refresh()` once. Prescribe this for grid movers, stacking puzzles, and
anything that needs replay determinism (§9).

**Cutscenes / "do X over N frames" via coroutine sequences.** Instead of hand-rolled frame counters
and `if`-ladders, express timed sequences as generators that `yield` once per frame. *picogame:*
`picogame_seq` — `wait(n)`, `move_over(obj, x, y, n)`, and a `Seq` that advances ONE generator a step
per `tick()`; compose many with `yield from`. A `picogame_fx.Tween`/`Shake` can itself be yielded.

```python
def intro(hero):
    yield from wait(30); show("GO!"); yield from move_over(hero, 120, hero.y, 20)
s = seq.Seq(intro(hero))     # s.tick() once per frame; s.done when finished
```

---

## 2. Enemy & AI patterns

**Movement scripts as `(dx, dy, steps)` segment tables.** Most shmup/flyer enemies have *no* AI —
they follow a waypoint script: a list of `(dx, dy, frames)` advanced by an index, `steps=0` meaning
loop. One update loop + different tables = zigzag, dive, weave, boss-sweep, all as data (the
classic arcade approach). *picogame:* store the path list in `sprite.data`, advance an index each step — zero
per-frame allocation, fully tweakable, and the same machinery gives you demo playback for free.

```python
PATH = [(2,0,30), (0,2,20), (-2,0,30)]   # in sprite.data
dx,dy,n = PATH[i]; spr.x += dx; spr.y += dy; n -= 1   # next i when n hits 0
```

**Greedy 4-target chase (the canonical ghost AI).** Give each chaser a *different target tile* and,
at every tile, pick the non-wall neighbour minimizing straight-line distance to that target — no A*,
4 distance compares per ghost. Four targets = four felt personalities: chaser→player tile; ambusher→
4 tiles ahead of the player; flanker→reflect "2-ahead" across the chaser; patroller→chase when >8
tiles away, flee to its corner when closer. *picogame:* read neighbours from the `Tilemap`; use
`sprite.near`-style squared distance (no sqrt) to score them. See `genre-patterns.md` §6.

**Lockstep fleet (Space Invaders).** Move the whole grid as one unit: track live min/max X, reverse
direction and drop ~8 px at the edge, fire one shot per column from the lowest live alien gated by a
random roll. *picogame:* a `picogame_pool` of aliens + a single shared "fleet offset" added each
step; derive each alien's screen pos from `grid_index + offset`. The famous "music speeds up as you
clear them" falls out of cadence-as-difficulty (§8). See `genre-patterns.md` §2.

**Target-with-inaccuracy AI.** A simple opponent (Pong paddle, turret) aims at the player but with a
deliberate error margin tuned to difficulty — beatable, not perfect. *picogame:* lerp the AI toward
the target and add a jitter that shrinks as difficulty rises.

---

## 3. Input feel

**Coyote time & jump buffering — use the shipped helper.** Let a jump fire a few frames *after*
leaving a ledge (coyote 3–8 frames) and let a jump pressed just *before* landing still register
(buffer 3–6 frames). *picogame:* `picogame_input.Timer(frames)` — `.feed(cond)`, `.is_active`,
`.consume()`. One Timer fed by "on ground" gives coyote; one fed by "jump pressed" gives the buffer.
Don't hand-roll counters.

**Turn buffering for grid movers (the #1 feel win, nearly free).** Pac-Man feels responsive despite
grid-locking because it stores the player's *next desired direction* and applies it the instant that
direction becomes legal. *picogame:* one int in player state for the buffered direction; each step,
if the destination cell is non-solid (`Tilemap` lookup / `picogame_tiles`), commit the turn. Sub-step
the slide (e.g. interpolate a move over 4 quarter-steps) for smoothness.

**Auto-repeat for menus & cursors.** Edge-press that auto-repeats while held — default 15-frame
initial delay, then every 4 frames. Essential for menus, Tetris DAS, RPG cursors.
*picogame:* `Buttons` ships `.is_pressed`/`.just_pressed` and `repeat(button, delay=15, interval=4)`
(True on first press and each repeat tick). Pair with `picogame_input.Timer`.

---

## 4. Camera & world

**Parallax = N layers, integer speeds, wrap by split-blit.** Scroll several wide background layers
at speeds like 1/2/3 px/frame; nearer = faster. The load-bearing trick is wrapping a wide image by
drawing it in **two pieces** when the scroll phase crosses the seam. picogame ships *no* parallax
helper — you roll it. *picogame:* (a) a few `fixed=True` wide `Tilemap`/`Canvas` strips whose source-x
you advance each frame (split-draw at the seam), or (b) a `StripDraw` that samples a far layer at a
per-band x-offset `cam_x * factor`. See `engine-capabilities.md` §4 (`set_view`).

**Scrolling & follow camera.** A moving-camera world subtracts the view offset from all draw coords.
*picogame:* `Scene.set_view(ox, oy)` is the global camera register; `picogame_fx.Camera(...).follow(x,y)
.apply()` gives a smooth-follow camera that composes with `Shake`. Note: a `set_view` change repaints
everything (no dirty-rect win), so keep screen shakes short — 2–6 frames (§6).

**Pseudo-3D — pick by what scales:**
- **Scanline / strip road (cheap, ~0 RAM).** Draw the ground per render strip from a precomputed
  perspective table `y(z)`; scroll the texture by a phase. Objects scale by distance. *picogame:* a
  `StripDraw` ground + `sprite.scale = F/(F+z)` per object — picogame can scale at runtime, so you
  **don't** need pre-baked size frames. Minimal example: `examples/picogame_stripdraw_example.py`
  (a receding road at 0 B).
- **Mode-7 perspective floor (true warp, native C).** Each screen row below the horizon samples one
  distance into a power-of-2 texture, so a flat top-down image becomes a receding ground plane.
  *picogame:* the engine primitive `Canvas.mode7`, driven by `picogame_mode7.Camera(...).draw(view,
  texture, x, y, angle, horizon, height, y_off=vy)` into a `StripDraw` view = **0 RAM**, ~29 fps
  full-screen. Pick this over the scanline road when you want a *textured, steerable* ground (a
  proper track, a flying carpet) rather than a strip road. A **tiling** texture wraps forever (use a
  big `height`); a one-shot circuit image needs a small `height` or the distance repeats.
- **Raycast walls (first-person corridors, native C).** One DDA ray per screen column finds the
  nearest wall; each column draws as a distance-shaded vertical slice. *picogame:*
  `picogame_ray.Raycaster` driving the native `pg.raycast` (integer 16.16) into a `StripDraw` =
  **0 RAM**, **~22-30 fps** full-screen. Add `.attach(sd)` on an `always_dirty=False` StripDraw for
  temporal repaint (standing still costs ~nothing — ideal for a grid-step dungeon crawler), and
  `.project_sprite()` for depth-tested billboard enemies. Combine with `mode7` if you want a
  textured floor under the walls.

See `genre-patterns.md` §8A and `helpers/pseudo-3d` in the docs.

**Pre-bake rotation frames for the hot path.** Runtime `sprite.angle`/`scale` is fine for a *few*
sprites or smooth values, but for an always-rotating or many-instance object, pre-bake heading frames
and step `.frame` (e.g. a car with 17 pre-baked headings). *picogame:* `picogame_shapes.poly_frames` bakes them.
(Game logic can stay in plain Python floats — `dt`, positions — that's fine and readable. The engine's
own hot paths, incl. sprite rotate/scale, `mode7` and `raycast`, are already integer fixed-point in C
because the RP2040's M0+ has no FPU, so you don't hand-roll fixed-point math yourself.)

---

## 5. Collision

**Tile-flag collision (no per-game side tables).** Tag each *tile index* with bits (SOLID/HAZARD/
LADDER) and test the leading edge before moving — the universal grid-collision idiom. *picogame:*
`picogame_tiles` (tile-id-keyed flags, baked from the scene/map JSON): `tf.at_px(tilemap, x, y,
tiles.B_SOLID)`. **Convention (easy to get wrong):** `B_SOLID/B_HAZARD/…` are BIT INDICES — pass them to
`get/set/at/at_px`; `SOLID/HAZARD/…` are MASKS — use them only to build the `{tile: flags}` table.
Passing a mask where a bit index is wanted silently probes the wrong flag. Use this for platformer/
top-down walls and hazards instead of hand-rolling a lookup each game.

```python
if not tf.at_px(tm, x + dx, y, tiles.B_SOLID): x += dx   # test then move (at_px does the >>3 for you)
```

**Circle hit as the default sprite test.** Use `dx*dx + dy*dy < r*r` (squared, no sqrt) for round-ish
actors — bullets, enemies, pickups. *picogame:* `a.near(b, r)`. Shrink the radius
*below* the visual size for forgiving, fair hitboxes.

**AABB for boxy things.** Reserve rectangle overlap for bricks, paddles, walls, platforms. *picogame:*
`a.overlaps(b)` (AABB box, anchor-correct, zero-alloc) — `b` may be a sprite, point, or rect.

**Per-axis swept resolution — the platformer move (plain Python, no C, no module).** Detecting a hit is
what the engine gives you (`tf.at`/`overlaps`); *resolving* a moving body against solid tiles is plain
Python that runs **per object per frame** (a handful of calls) — cheap, so it never wants a C binding.
Move and resolve **one axis at a time** (horizontal, then vertical): each axis is an independent 1-D
overlap, which is what makes it stable and **corner-snag-free** (resolving both at once wedges the body
in inside corners). Probe the **leading edge at two-plus points** (both feet, or head+mid) so the body
can't slip through a one-tile gap, and **sub-step fast vertical motion** 1 px at a time while falling so
a high `vy` can't tunnel through a floor; stop on the first solid row and latch `landed`/`vy=0` there for
the jump check.

```python
def move_h(x, y, dx, half_w, hh):                 # resolve X: stop at the wall, don't enter it
    edge = x + (half_w if dx > 0 else -half_w)
    if block_at(edge, y - 2) or block_at(edge, y - hh // 2):  # probe top AND mid of the body
        return x
    return x + dx

def move_v(x, y, vy, half_w):                      # resolve Y: step down 1 px so speed can't tunnel
    if vy > 0:
        for _ in range(vy):
            if block_at(x, y + 1) or block_at(x - half_w + 2, y + 1) or block_at(x + half_w - 2, y + 1):
                return y, 0, True                 # landed: y unchanged, vy zeroed, grounded
            y += 1
    return y + vy, vy, False
```

*Field tip:* when `move_h`/`move_v` are called many times per frame (player + enemies + pickups,
easily ~11×), have them write into a shared scratch list instead of returning a tuple — saves a
tuple alloc per call.
**Don't extract this into a helper/module yet.** It's ~30 lines tightly bound to each game's solid test,
body half-size, and jump state; a generic version needs so many callbacks it ends up shallower than the
inline code (and a one-function `_collide` revival is exactly that shallow-module trap). Extract a shared
resolver only when a *second* platformer repeats the pattern.

**A stepped mover that stops on contact must keep its LAST FREE position — and that is where anything
it spawns goes.** Cheap to write, easy to forget, and the bug it causes reads as a physics failure
rather than a placement one: the impact effect, the decal, the placed block, the teleport exit, the
dropped item ends up *inside* the tile that stopped the mover, so whatever appears there next is
embedded in geometry and falls through the world. You don't need a ray for this — a projectile that
visibly flies is already stepping, so the previous step IS the flush contact point. **The axis you
were stepping on when the probe hit is also the surface normal** — step X and you hit a vertical
face, step Y and you hit a floor or a ceiling, with the sign of the step giving the direction. That
is free from the loop below, and it is what anything ORIENTED at the contact point needs: a decal
that must lie flat on the wall, a spark that sprays away from it, a placed thing that has to know
which way is "out". Keep both, the position and the axis:

```python
while alive:
    last = (x, y)                 # known-free
    x += vx; y += vy
    if tf.at_px(tm, x, y, tiles.B_SOLID):
        spawn_at(*last)           # NOT (x, y) - that cell is the wall
        break
```

(A ray march through the tiles is only needed for an *instant* hit — a zero-flight-time laser or a
line-of-sight test. Note `pg.raycast` is NOT that function: it is the first-person renderer's
per-screen-column DDA, with fixed-point ray params, wall-colour tables and buffer outputs.)

**Grid-locked movement needs no collision math.** Tile-to-tile movement makes "can I move?" a single
`Tilemap` lookup — no continuous collision at all (Pac-Man/Sokoban/Train). Combine with turn buffering
(§3).

**Destructible terrain via tile/canvas erosion — pixel readback does NOT port.** Other engines
destroy the Invaders bunkers by reading framebuffer pixels under the shot; picogame's retained
renderer has **no mid-frame readable framebuffer**, so you can't do that. *picogame substitute:*
model destructible cover as a `Tilemap` of small chunks you clear on hit (`tm.set_tile(tx,ty,0)`), or a
`Canvas` you draw into and re-blit. Reach for erosion, never for pixel readback.

**Self-fired projectiles: spawn at the muzzle, arm after clearing the shooter.** A shell/bullet born at
the firing unit's own position sits *inside* its own hitbox, so the very next collision check scores a hit
on the shooter — an instant self-destruct (worst at low speed / steep angle, where the projectile lingers
in the box for several frames). Fix with two cheap guards: (1) spawn it at the **muzzle tip** — offset along
the aim vector past the hull (`px = x + cos·dir·MUZZLE; py = y − sin·MUZZLE`); (2) **disarm collisions**
until it leaves a small clearance radius around the shooter (`(px−sx)² + (py−sy)² < ARM²` → skip all
collision this frame). Once it clears, normal collisions resume, so a shot lobbed straight up can still
fall back on you (fair) — you just never suicide on launch. Mirror the same spawn in any AI shot-prediction
sim so the AI aims where the real shell goes. (Bang!Bang!/Scorched-Earth artillery, any forward-firing turret.)

---

## 6. Procedural generation

> RAM rule on this hardware: generate **into the tilemap you already own, one pass, no big
> intermediates**. Recipes below.

**Seeded RNG is the foundation.** The whole world becomes a pure function of one 32-bit seed — store
the seed, not the world; same seed → same level forever (dailies, shareable runs, replays). *picogame:*
`picogame_rand.Rand(seed)` (below/randint/chance/choice/shuffle/weighted). **Use it for every gameplay
draw** — never CircuitPython `random` for anything reproducible. Keep **separate streams** for gameplay
vs cosmetics so a new particle effect doesn't shift the map. Daily seed = `year*10000+month*100+day`;
per-level sub-seed = `run_seed ^ (level*0x9E3779B9)`.

**Weighted spawn tables, ramped by difficulty.** Parallel item/weight arrays, roll in `[0,sum)`. Make
weights a function of run progress `t∈0..1` (common foes fade, hard foes ramp). *picogame:*
`Rand.weighted(weights)` (returns an index). A few bytes → infinite, self-scaling variety.

**Anti-streak fairness — three tools, cheapest last:**
- **7-bag / shuffle** for "deal from a set" (pieces, wave types, question order): one of each in a bag,
  Fisher-Yates shuffle, deal until empty, refill — bounds droughts (Tetris: ≤12 between I's). *picogame:*
  `picogame_rand.Bag(items, rng).next()` — already implements it.
- **PRD** for a *chance* event (crit/rare drop): raise the chance by constant C each miss, reset on hit
  — kills "whiffed 5× in a row" without changing the long-run average (for a stated 25%, C≈0.085).
- **"No more than K in a row" clamp:** remember the last pick, re-roll once if about to over-repeat.

**Generation algorithms (cheapest first, with RAM cost):**
- **Chunk stitching** (runners/shmups) — *recommended default.* Hand-author a few fair segments;
  concatenate by weighted pick honoring an entry/exit-height contract so jumps always connect. **RAM:
  on-screen chunks only** (object-pooled). Mix in rare hand-authored set-pieces.
- **Cellular-automata caves** — fill ~45% wall, then ~4–6 passes of "≥5 wall neighbours → wall," then
  **mandatory flood-fill** to re-wall unreachable cells. **RAM: 2× the grid as byte buffers** (40×30 ≈
  1.2 KB each).
- **Recursive-backtracker maze** — perfect (solvable) maze via DFS with an **explicit stack** (never
  Python recursion on an MCU). **RAM: grid bitfield + stack** (~longest path). A random wall-punching
  variant avoids the deep stack — note it for tight RAM. `picogame_maze` uses the backtracker.
- **Template/grammar rooms (Spelunky)** — carve a guaranteed solution path on a small macro grid (force
  the room below to accept a top entrance on each drop = guaranteed solvability), then fill off-path
  rooms with templates. **RAM: tiny path grid**; templates stream from flash. Best control-vs-variety.
- **WFC-lite** — Simple Tiled Model with bitmask adjacency (`domain[cell] &= allowed`). Spiky cost,
  can contradict → keep the grid small (one 8×8 room), cap iterations, **fall back to a hand-authored
  room on contradiction**. Decorator only, not your main generator.

**Fairness: build the path first, decorate after** (or verify after with flood-fill). Never ship a
generator that *can* produce an unwinnable level — because it's seeded, **fuzz it over thousands of
seeds offline** and reject failures before shipping.

---

## 7. Visual techniques

**Palette cycling / animation (animated water/lava/portals, ~0 art).** Rotate a run of palette
entries each frame so pixels painted with those indices "flow" — O(palette-size), zero pixel data
touched. *picogame:* `picogame_palette.cycle(palette, lo, hi, step)`; reserve e.g. indices 8–11 for
"flowing water," paint water tiles with them. **Gotcha:** dirty-rect can't see a palette mutation —
call `sprite.touch()` (or `scene.invalidate()`) after editing the palette.

**Palette fade vs dither fade — pick the look.** *Palette fade* lerps every entry toward black/white
for a uniform, clean cinematic darken (`picogame_palette.fade(palette, base, t)`). *Dither fade* is a
stippled per-sprite see-through (`spr.dither`) — great for ghosts/fog/translucency. Offer the designer
both.

**Palette swap for recolors (cheaper than a 2nd bitmap).** Keep one PAL8 hero, hand different palettes
to player 1/2 or normal/frightened states. *picogame:* `picogame_palette.swap(dst_palette, src_palette)`
(copies `src` colours into the live `dst` palette array in place — palettes only, not a bitmap).
Caveat: palette is **per Bitmap**, so all sprites sharing a Bitmap recolor together (a feature for
swarms, a gotcha for soloing one — give it its own Bitmap to recolor alone).

**Raster / scanline effects via StripDraw (0-byte buffer).** `StripDraw`'s callback runs once per
render strip — the per-scanline register-rewrite trick of the Game Boy, but in Python with Canvas
primitives. Recipes: **gradient/day-night sky** (`fill_rect(0, ly, vw, 1, shade(ly))` per line);
**wavy water/heat-haze** (shift a source row by `int(amp*sin((ly+t)*k))`); **per-band parallax** (§4).
For content that changes only occasionally (a panel, a minimap), make a StripDraw with
`always_dirty=False` and call `.invalidate(x,y,w,h)` after a change — it repaints only then and only
there. See `engine-capabilities.md` §4 and `examples/picogame_stripdraw_example.py`.

**Screen shake & flash for impact.** `picogame_fx.Shake(scene).add(amt)` + `.tick(cam_x,cam_y)` jitters
the view on hits; `picogame_fx.Fade(...).pulse()` flashes. Keep shakes 2–6 frames (a view change is a
full repaint — §4).

**1-bit offset drop-shadow for cheap depth.** A flat dark silhouette offset under an actor sells
height for ~1/8 the bytes of real art. *picogame:* `spr.shadow = True` (opaque pixels
darken the destination); give the shadow its own offset sprite, or reuse the actor bitmap. Near-free juice.

**Drop-shadow / `flip_x` art reuse & tile dedup (asset wins).** Store symmetric art once and mirror
with `flip_x`/`flip_y`. **Tile dedup:** a hand-drawn level is typically 40–70% duplicate 8×8 blocks —
hash each block, keep uniques, remap the map array, so the tileset Bitmap shrinks directly. This is a
converter/tooling pass (`png2picogame.py --dedup`), the single biggest free asset win; pairs with RLE
on sparse maps (index 0 = transparent).

**Animate by a shared phase counter / tile swap.** Choose frames with a free-running counter masked
per entity (`(anim >> shift) & mask`) for zero-allocation animation of many sprites; or animate a
waterfall/coin by pointing the map cell at the next tile (`tm.set_tile(tx,ty,next)`) rather than redrawing
pixels. `picogame_anim.FrameAnim` is the smoother dt-driven version.

**Mosaic / pixelate transition.** Render small into a low-res Bitmap then blit with `sprite.scale = N`
(nearest-neighbour = chunky pixels); animate `scale` 4→1 for a pixelate-in. Uses only existing API.

---

## 8. Level authoring

**ASCII-art level strings — the default for any map a human and an agent both touch.** Store the level
as a list of strings (`#`=wall, `$`=box, `.`=goal, `@`=player…); a tiny loader walks it into a `Tilemap`
once at load. Human-readable, diffable, hand-editable — far better than a byte blob; bake to `.mpy` to
ship. It started as the Sokoban/Boulder idiom but the reason is general: **geometry you can SEE is
geometry you can agree on.** A prose request ("put a ceiling below the HUD, a wall three quarters up")
becomes a picture you paste back for confirmation, and "one tile too far left" is then obvious instead
of argued. The declarative scene format accepts the same thing natively — a tilemap layer takes
`"legend": {char: tile}` + `"rows": [str, …]` instead of `"grid": [[int…]…]`, and `tools/scene_build.py`
bakes both to the identical `bytes` — so ASCII is not a lesser path, it is the *authoring* path.

**Who owns the level file (agent vs the editor).** The web editor round-trips an authoring
`scene.json`: it can export the ASCII form and **open an exported scene back**, so a level can pass
between you and the user — you do the bulk/systematic passes, they draw and polish. It is turn-taking,
NOT merging by itself — but if the level is in git, **git merges it**: in the ASCII form one map row
is one line, so your ceiling (top rows) and their floor (bottom rows) merge with no conflict, and only
edits to the SAME row collide (git then leaves both versions as two readable map rows). So: commit the
level before a bulk pass, and say which of you is holding the file. Two practical notes —
the editor resolves art by filename from the folder it saves into, so keep the level's PNGs beside it;
and a scene has no level name of its own (the file name becomes it). Full schema: `SCENE_FORMAT.md`
(published at `/scene-format/`).

**Difficulty is data + one ramp formula, not branching code.** Keep tuning numbers in module-level
tuples indexed by level (lines-to-advance, fruit/scatter/frighten timers), and ramp continuous
difficulty as a function of score/elapsed. The Invaders self-balancer — *fewer enemies move faster*
(`speed = count/4 + 2`) — is a famous emergent ramp worth reusing.

**Bit-pack the tile byte to seed content.** One tile byte can carry type in the upper bits + variant/
index in the lower bits (e.g. "enemy type 2, variant 3" in one byte). Cheap way to spawn enemies straight
from the map.

**teach → test → twist (kishōtenketsu / rule of three).** Build one level around *one* idea in four
beats: **introduce** risk-free → **develop** (now it matters, safety net) → **twist** (recombine/invert,
net removed) → **conclude** (demands the mastery). For puzzles, the rule of three = intro / complicate
/ resolve across 3 screens reusing one tileset + one verb. A 1–3 min handheld session has room for
*exactly one* idea — the twist *is* your content.

**Teach by layout, no tutorial text (World 1-1).** First screen doubles as onboarding: empty space
biased toward the goal direction (the emptiness is the arrow); a slow, telegraphed, survivable first
threat; an unmissable reward in the obvious path; then *demonstrate-then-test* (show a shape safely,
re-present it with stakes). A stranger should learn the controls watching ≤10 s.

**Placement is the content (rule of three for encounters).** Place threats *relative to terrain* (a
shover by a pit, a ranged enemy on a ledge), pair *complementary* enemies to pincer, and give every
first-time threat readable telegraph distance on a ≤320 px screen. Two well-placed enemies beat six in
a line at a third of the RAM.

**Set-pieces & checkpoints.** One memorable oversized moment (collapsing bridge, mid-boss) gives a
scrolling stage a spine; put a checkpoint **after each difficulty spike** — on a 90-second game a death
that rewinds 90 seconds is the whole game.

---

## 9. Replay & ghosts

**Deterministic loop + recorded inputs = attract mode + replay + ghosts, from one mechanism.** With
`FixedStep` (§1) + seeded `picogame_rand` (§6), a recorded *button stream* replays identically. The
same recording drives a title-screen demo/attract mode, a tutorial playback, and a translucent ghost
racing the player (verified: best-lap ghost in `games/picoracer`). *picogame:* record the input bitmask per
fixed step; store **inputs (+seed), not positions** — a few bytes/sec. Draw the ghost with `spr.dither`.

**Passwords as a save system (no NVM writes).** Gate level progress with short A–Z passwords via a
`level→password` lookup table; to continue, the player edits chars with the D-pad and you match the
buffer against the table. The password *is* the save — shareable, restorable, no flash writes. Use as a
complement to `picogame_save` (NVM) for level-based games. The D-pad char editor (cycle A–Z on UP/DOWN,
move cursor on LEFT/RIGHT) is a reusable widget.

**Replay value without procedural generation (bytes, not buffers).** Persistent high score (one int),
combo/multiplier (one timer + one int), modifiers/mutators (one flag each: no-hit, mirrored, one-life),
difficulty modes (scaled spawn weights, §6), unlockables gated by an NVM bitfield (`picogame_save`).
Stack freely: a *seeded daily* + *score chase* + *ghost of yesterday's best* is three overlapping
reasons to play sharing one RNG and one saved record.

---

## See also

(Recipes are in our own words — no upstream code copied.) `engine-capabilities.md`
(the API + costs), `genre-patterns.md` (per-genre playbooks), `SKILL.md` (design philosophy).

---

## Audio recipes (full detail; the summary lives in SKILL.md §1.7)

A beep on the key action confirms what the eye is doing and is the best fun-per-byte juice.
- **Minimal SFX set**: the main verb (jump/shoot), a hit/score, a pickup, a death/fail, a menu blip.
  **`picogame_sfx.Kit` ships exactly this, hardware-tuned** — reach for it FIRST; hand-roll
  `picogame_synth` notes only for a bespoke palette. Full usage:

  ```python
  import picogame_synth as snd
  import picogame_sfx as sfx
  kit = sfx.Kit(snd.Synth())      # builds the voices ONCE, at boot
  # ...on events: kit.jump() / kit.coin() / kit.zap() / kit.hit() / kit.explosion()
  # ...once per frame (next to clock.tick()): kit.tick()
  ```

  Available sounds: `blip coin powerup zap pew jump hit hurt boom explosion`. On audioless builds
  everything silently degrades to a no-op — no guards needed.
- **Same-frame** as the event (audio latency must be imperceptible).
- Chiptune-style: square/triangle/noise + a quick **pitch sweep** = blip/zap/explosion; arpeggios as
  cheap chords. `picogame_audio` (PWM/tone + wav) / `picogame_synth` (chiptune) — both auto-pick the
  output (`picogame_audioout`: PWM, or the I2S DAC on a Fruit Jam), so **no board-specific audio code**;
  volume/output live in `settings.toml` (`PICOGAME_HP_VOLUME`, `PICOGAME_AUDIO_OUT`).
- **Crisp, not rich** (hard-won): short DRY **square** beeps read best on a tiny speaker. Use a pitch
  sweep (`pitch_bend`) ONLY on zaps + death — it's a sine *wobble*, not a clean glide, and long decays
  with bends everywhere sound mushy. Carry meaning in the **contour**: ascending = win/kill, descending
  = lose/death, two alternating tones = warning/heartbeat, rising pitch = filling/charging.
- **You can't judge sound yourself — have it listened to**: the simulator is **silent** (no audio
  backend — but the libs import and no-op fine there, no guard needed), and you don't hear it either.
  Don't design custom `picogame_synth` sounds blind: if `tools/synth_preview.py` is in the repo,
  render them to WAV and ask the USER to listen and approve before shipping. The ready-made
  `picogame_sfx.Kit` skips this — it's pre-tuned, which is why it's the first choice.
- **Music is optional** — short loops fatigue, and handhelds are often played quietly; a tune helps
  menus/title more than frantic play. **Never rely on audio alone** — always pair with a visual.
