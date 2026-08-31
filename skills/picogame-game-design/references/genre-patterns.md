# Genre Design Patterns — Small 2D Games for picogame

Reference for quickly designing a *fun* game in a chosen genre on a constrained
device.

**The kind of device you're designing for:** a microcontroller with a small display
and a few buttons — typically D-pad + A/B (sometimes X/Y), no analog sticks, minimal
RAM. Read the actual parameters (resolution, buttons) from the board
(`picogame_game.screen()`, `picogame_input`), not from this document. The concrete numbers
here are taken from the classics of each genre, not guessed — treat them as a
starting point to tune.

## Cross-genre rules (read first)

- **Convert frame counts from the classics to your FPS.** The classic tuning
  numbers in this document (and in the arcade literature) are frame counts **at
  60 fps** — but picogame games typically run at **30 fps**, so the same frame
  count takes twice as long and the game feels sluggish (e.g. a "15-frame delay"
  from a 60fps game = 0.25 s; at 30 fps that would be 0.5 s). So either halve
  frame counts from 60fps sources, or — cleaner — convert the value to seconds
  (frames ÷ 60) and work in seconds × `dt` from `picogame_clock` in code.
  **Watch the unit — only counts convert linearly.** A duration or velocity in
  *per-frame* units scales by the fps ratio (px/frame → px/s = × fps), but an
  ACCELERATION is per-frame², so it scales by the SQUARE (px/frame² → px/s² =
  × fps²). Applying the frame-count rule to a gravity constant is off by a whole
  factor of fps. Unless a section says otherwise, the per-frame numbers below are
  **30 fps** (this project's baseline), so e.g. `gravity 0.4 px/frame²` = 360 px/s².
- **Make the collision area smaller than the drawn art.** A hit across the whole
  sprite rect feels unfair ("that didn't touch me!") — the player perceives only
  the core of the figure; the edges of the art are visual. Shmups take it
  furthest (ship 16–24 px, hit-core ~4 px). *picogame:* `a.overlaps(b, inset=N)`
  shrinks the tested box by N px per side, or `a.near(b, r)` with `r` smaller
  than the art.
- **Motion = velocities you set yourself; collision = simple tests.** Don't
  simulate "real" physics (forces, bounces, rotating bodies) — move objects by
  `vx/vy` you control directly and test overlaps via `overlaps`/`near`. It's
  more stable (no tunneling, no snagging), cheaper, easier to tune. Cap speed so
  an object never skips a whole cell/obstacle in one frame — then collision
  stays one cheap test per frame.
- **Object-pool everything repeatedly spawned** (bullets, pipes, platforms,
  rocks). Recycle a fixed handful instead of creating/destroying sprites at
  runtime; cap simultaneous entities — it's a RAM guard *and* a design lever.
  *picogame:* `picogame_pool.Pool(scene, bitmap, capacity)`.
- **Single-screen / flip-screen layouts** are the RAM-cheapest choice and read
  best on a small display. Add scrolling/streaming only once the core loop is
  proven.
- **Autofire on hold**, never tap-to-fire — mashing cramps thumbs on a handheld.
- **Identity is carried by silhouette + color, never color alone.** Each entity
  type should be recognizable by shape AND color (Pac-Man's ghost colors work
  because the ghosts also share one readable shape and differ by behavior;
  distinguish differently-roled enemies by shape). Color-only fails under
  colorblindness and at small sprite sizes (see SKILL.md §1.8).
- **Forgiveness mechanics are nearly free, high-impact**: coyote time, input
  buffering, contact i-frames, direction queuing — a few variables each.
  *picogame:* `picogame_input.Timer(frames)` covers coyote and buffer (see
  `techniques.md` §3).

---

## 1. Breakout / Block-Breaker
*Device-proven: the Bounce tutorial ships this genre end-to-end.*

*Exemplars: Breakout, Super Breakout, Arkanoid + Revenge of Doh, DX-Ball.*

**CORE LOOP** — Deflect a bouncing ball off a horizontally-moving paddle to
destroy every brick without letting the ball fall past the bottom, then advance.

**WHAT MAKES IT FUN** — Player-authored ball angle: *where* on the paddle you hit
controls deflection, so the paddle is a steering tool, not a wall. Skilled play
aims the ball into the gap above the wall to ricochet between ceiling and bricks
for a destruction streak (Arkanoid). Power-up capsules drift down forcing a
dive-for-it-or-stay-safe choice; escalating speed ramps tension.

**CONTROLS**
- **D-pad L/R** — move paddle (the only essential input; an accel curve helps fine
  aiming). Up/Down unused — single-axis control *is the point*.
- **A** — Serve/Launch; also Catch-release (sticky) and Laser fire when active.
- **X** — pause. **B/Y** — optional fine-vs-fast toggle / nudge.

**LEVEL / DIFFICULTY** — Brick types: normal (1 hit), silver (multi-hit, scales
with round), gold (indestructible — must be excluded from clear condition).
Arkanoid = 33 rounds to the DOH boss; classic Breakout = 8 rows × 14 bricks.
Difficulty levers by impact: ball base speed → escalation aggressiveness →
paddle width → silver hit-counts → helpful:harmful power-up ratio. Serve: ball
stuck to paddle, press to launch, with a **timeout auto-launch** so players can't
camp.

**TUNING / RULES OF THUMB**
- **Angle-control trick:** `rel = (ball.x − paddle.cx)/(paddle.w/2)`, clamp
  **−1..+1**; `angle = rel * MAX_ANGLE`, **MAX_ANGLE ≈ 60°** from vertical. Fixed
  speed scalar: `vx = speed·sin(angle)`, `vy = −speed·cos(angle)` (force vy up).
  Cheap alt: 3–5 discrete paddle zones.
- **Speed escalation (original Breakout):** steps up after the **4th, 8th, 12th**
  paddle hit, and again on reaching the orange/red upper rows. Handheld: 3–4
  tiers, ~1.15–1.25× each, reset on new ball/level.
- **Min-vy clamp:** if `|vy| < MIN_VY`, restore it (preserve sign) and recompute
  vx to keep speed constant — fixes the classic "ball stuck near-horizontal" bug.
- **Arkanoid power-ups:** Laser, Enlarge, Catch (sticky), Slow, Disruption
  (multiball), Break/Warp, extra life. One capsule on screen at a time; **never**
  drop from silver/gold bricks. Extra-life/Warp ~half as likely as others.

**WHERE BRICK STATE LIVES** — the wall is a `Tilemap`, which stores exactly **one byte per
cell**: the tile index. So brick *state* has to BE the index — give silver 3 tile indices
(cracked stages) and decrement by writing the next one, which repaints just that cell and shows
the damage for free; gold is its own index that the hit handler and the clear-count both skip.
Don't bolt a parallel Python HP array onto a tilemap wall (extra RAM, two things to keep in
sync); do use `techniques.md §5`'s tile-flag idiom to classify indices.

**PITFALLS** — Don't just invert velocity on paddle hit (recompute from hit
position). Keep the ball speed constant and compute bounces yourself (no "real"
physics — see Cross-genre); cap it so the ball can't skip the paddle or a brick
in one frame. Don't skip auto-launch. Don't count gold bricks toward "level
clear." Always min-vy clamp.

**MVP:** position-based deflection (−1..1 → ±60°, fixed speed) · one-hit bricks +
win/lose · serve-on-press with min-vy clamp.
**NICE TO HAVE:** power-ups (Enlarge, Multiball, Slow first) · speed tiers +
multi-hit silver · Catch/sticky + Laser.

---

## 2. Fixed & Vertical Shooters / Shmups
*Device-proven: Starship tutorial, boxshmup, picowing.*

*Exemplars: Space Invaders, Galaga, 1942, Touhou, DoDonPachi, Ikaruga.*

**CORE LOOP** — Pilot a ship up a battlefield, weave dense fire while shooting
waves, bank limited screen-clear bombs for panic moments, chase a high score.

**WHAT MAKES IT FUN** — The gap between *looks deadly* and *is survivable*: a tiny
hitbox inside a big sprite makes threading a bullet curtain feel graceful every
time. Layered with pattern-reading, the panic bomb, and a scoring meta
(graze/chains/rank) that rewards greed over safety.

**CONTROLS**
- **D-pad** — free 8-direction movement (not grid).
- **A** — Shoot (autofire on hold; never mash).
- **B** — Bomb/screen-clear (slight activation delay so panic-dodging doesn't
  waste it).
- **X** — **Focus/slow-move** (Touhou staple): halve speed for precise dodging
  *and reveal the hitbox dot* while held. The single most genre-correct control.
- **Y** — alt fire / polarity / shot-mode. Pause → Start, not a face button.

**LEVEL / DIFFICULTY** — **Formations + dives (Galaga):** enemies hold a swaying
grid, peel off on scripted dives; as the stage thins, survivors dive
continuously and fire more. **March speedup (Space Invaders):** tie step-rate to
remaining-enemy count (the original was a CPU accident kept as a feature).
**Pattern vocabulary:** aimed, fixed spread (n-way), spiral, wall/stream, danmaku.
Touhou structures bosses as **spell cards** — each a readable pattern with its own
timer/HP. **Polarity twist (Ikaruga):** absorb same-color, die to opposite, chain
groups of 3. **Rank:** keep any dynamic difficulty *gentle and visible* (rises
with skill, resets on death — DoDonPachi); avoid opaque suicide-to-manage rank
(Battle Garegga).

**TUNING / RULES OF THUMB**
- **Player hitbox (smaller than sprite):** Touhou modern ≈ **circular r ≈ 3 px**;
  DoDonPachi ≈ **6×7 px**. Rule of thumb: sprite 16–24 px, hitbox **4–6 px core
  dot**, revealed on focus. *Not* literally one pixel.
- **Bullet speeds:** keep **~70–90% of enemy bullets slower than player move
  speed** — that's what makes dense curtains dodgeable. Player shots fast/snappy.
  Draw small/fast bullets on top of big/slow for readability.
- **Bombs:** start **2–3**, cap ~5, refill on death; bomb cancels all bullets (→
  score) + grants i-frames during the blast. Respawn i-frames ~1–2 s.
- **Graze:** ring just outside the hitbox (~a bullet-radius); boosts point-item
  value, not raw score.
- **Power-up curve (Gradius):** Speed→Missile→Double→Laser→Option→Shield; Options
  are trailing satellite pods. Simpler: discrete shot tiers + 1–2 option pods.

**PITFALLS** — Don't size hitbox to sprite, or hide it with no reveal. Don't make
the majority of bullets faster than reaction. Don't require mashing. Don't ship
opaque punishing rank. Don't overdraw on tiny RAM — cap simultaneous bullets, tie
pacing to live-entity count. Don't let bombs fire accidentally.

**MVP:** 8-dir move + autofire + tiny central hitbox · bomb (limited, clears
bullets + i-frames) · a few emitters (aimed/spread/spiral) with formation+dive
waves.
**NICE TO HAVE:** focus button that reveals hitbox · graze scoring · a scoring
twist (polarity/chains or a gentle visible rank).

**Field note:** drive enemy patterns with **`(dx, dy, steps)` movement-script tables** — a tiny array per pattern, stepped one entry per frame; cheap, data-authored, easy to
tune. For an Invaders fleet move the whole grid in **lockstep** (slide → on edge: drop + reverse),
fire from the bottom-most live column, and use **cadence as difficulty** (fewer aliens → faster step)
for free self-balancing. Details in `techniques.md`.

---

## 3. Asteroids-Style / Vector Action
*Device-proven: the asteroids example.*

*Exemplars: Asteroids (1979), Geometry Wars, Robotron 2084, twin-stick shooters.*

**CORE LOOP** — Pilot one ship in an open arena, shoot drifting hazards that
fragment (or swarm), survive escalating density and a lurking aimed-shot
antagonist while chasing score — until one collision kills you.

**WHAT MAKES IT FUN** — The challenge *is* the controls. Asteroids has Newtonian
momentum with near-zero friction; orientation and velocity are *decoupled*, so
every thrust is a commitment you must later cancel. Geometry Wars keeps the open
arena + decoupled aim/move but swaps inertia-mastery for reflex density and a
lose-on-death multiplier driving greed-vs-survival.

**CONTROLS — two schemes**
- **A. Classic rotate/thrust (RAM-cheapest):** D-pad L/R rotate in place; D-pad Up
  = thrust in facing dir (adds to velocity vector); **A** fire (bullet inherits
  facing, wraps); **B** hyperspace; **X** optional smartbomb/shield.
- **B. Twin-stick on buttons:** D-pad (8-way) = absolute move; **Y/A/X/B = fire
  up/down/left/right** (auto-repeat on hold; two adjacent buttons = diagonal →
  full 8-way aim from 4 buttons; the diamond maps spatially to directions —
  follows Robotron via Vanguard's four-fire-button idiom).

**LEVEL / DIFFICULTY** — Wave starts with **4–6 large asteroids**; clear all
rocks+fragments to advance; each wave adds more, fragments faster.
**Anti-camping saucer (critical):** large saucer shoots poorly; small saucer
fires often and its aim *tightens as score rises* until it snipes — becomes the
regular threat. **Entity cap:** original capped at 26 asteroids — over the cap, a
large rock splits into a *single* medium instead of two (adopt this to bound your
pool). Geometry Wars: no discrete levels, spawn rate climbs continuously,
multiplier lost on death.

**TUNING / RULES OF THUMB**
- **Scoring:** large 20, medium 50, small 100, large saucer 200, small saucer
  1000; extra life per 10,000 pts.
- **Splitting:** large→2 medium→2 small→gone (3 tiers, 2 splits; smaller = faster
  + more points).
- **Hyperspace:** random teleport, **does not check for clear space**, ~**1-in-4**
  self-destruct chance — the risk is the point.
- **Movement (per-frame @60fps):** rotation ±4°/frame, thrust ~0.05 px/frame²,
  `velocity *= 0.95` above max ~5 px/frame. **Drag rule of thumb:** multiply
  velocity by `<1`/frame — `0.99` slippery, `0.95` draggy, `0.90` twitchy, `1.0`
  = true no-friction (clamp max speed). Thrust:
  `vx += cos(a)*thrust; vy += sin(a)*thrust` then clamp.
- **Screen wrap (toroidal):** apply to ship, asteroids, *and* bullets; for
  edge-straddling objects **draw twice** (real + offset by ±screen dim) and test
  wrapped collision.

**PITFALLS** — Don't bind rotation to the movement vector (kills decoupled facing).
Don't only wrap the ship. Don't make hyperspace safe. Don't omit the saucer (no
anti-camp = no skill ceiling). Don't let fragments multiply unbounded. Don't
require tap-firing. Don't skip a max-speed clamp.

**MVP:** rotate+thrust+inertia with max-speed clamp and full screen-wrap · 3-tier
splitting with 20/50/100 scoring + one-hit death · wave respawn + entity cap.
**NICE TO HAVE:** lurking saucer with score-scaled aim · hyperspace with
self-destruct risk · twin-stick-on-buttons mode / smartbomb + lose-on-death
multiplier.

---

## 4. Platformer
*Device-proven: the platformer example (incl. a scene-format variant).*

*Exemplars: Super Mario Bros, Celeste, Sonic, Mega Man.*

**CORE LOOP** — Traverse hazardous terrain by timing jumps and movement to reach
the level exit without dying.

**WHAT MAKES IT FUN** — A satisfying, *forgiving* jump arc the player feels in
control of even when they mistime it. Modern "feel" is a bundle of small cheats
(coyote time, jump buffering, apex hang, corner correction) that widen
timing/positioning windows so players succeed when they *intended* to (Matt
Thorson, Celeste: these exist "to favor player success").

**CONTROLS**
- D-pad L/R move; Down crouch/fast-fall/drop-through; Up optional look-up.
- **A = Jump** (the one button that must feel perfect).
- **B = Run / dash / fire** (hold-to-run like SMB; or Celeste dash; or Mega Man
  shoot). X/Y secondary (special weapon, grab/climb). Never overload jump.

**LEVEL / DIFFICULTY**
- **Four-beat grammar (kishōtenketsu):** Introduce a mechanic safely → Develop via
  repetition → Twist (variation/combination) → Conclude with a mastery test.
  Nintendo's documented formula.
- **Safe-then-challenge:** introduce every new hazard where the player can
  experiment without dying, then escalate (World 1-1).
- **Mega Man waves:** spawn weak enemies in waves of 3–4, ramp within the wave but
  make the *last* easier so players exit on a win. Checkpoint before every boss.
- **One-screen / flip-screen** reads instantly and costs almost no RAM; add
  horizontal scroll once the jump feel and core loop are solid. **Generous, frequent checkpoints**
  (Celeste room restarts) keep the death-retry loop tight.

**TUNING (units px and seconds @60fps — convert to your fps, see Cross-genre)**

These are **Celeste's** constants, and Celeste's world is on **8 px tiles** — pixel values do not
carry across a different tile size (at picogame's usual 16 px the same numbers clear HALF the
tiles). What carries is the scale-free quantity: **jump height measured in TILES**. Celeste's is
~3; the shipped `demos/picogame_platformer.py` jumps ~6 (measured) — both play well, they just
feel different. So pick the height in tiles that your platform spacing wants, then derive `v0`
and gravity from it (`height ≈ v0² / 2g`), and use the table below for the SHAPE of the feel
(apex hang, variable jump, terminal velocity) rather than as numbers to copy.

| Constant | Value | Meaning |
|---|---|---|
| Gravity | 900 px/s² | base downward accel |
| HalfGravThreshold | 40 px/s | near apex, gravity **halved** → "apex hang" |
| MaxFall | 160 px/s | terminal velocity |
| FastMaxFall | 240 px/s | terminal velocity holding Down |
| JumpSpeed | −105 px/s | initial jump impulse |
| VarJumpTime | 0.2 s | how long holding Jump keeps applying upward force |
| JumpGraceTime | 0.1 s | **coyote time** ≈ 6 frames |
| MaxRun / RunAccel | 90 / 1000 px/s(²) | run speed / accel |
| DashSpeed | 240 px/s | dash |

- **Coyote time:** ~5–6 frames (Celeste). Common range **3–8 frames**
  (~0.05–0.13 s).
- **Jump buffer:** press jump shortly before landing → jump on the landing frame.
  Common window **~4 frames**.
- **Variable jump height (release-to-cut):** release Jump while rising → cut
  upward velocity (SMB, Super Meat Boy).
- **Asymmetric gravity:** **fall gravity ≈ 1.5–2× rise gravity** — floaty up,
  snappy down (SMB, SMW).
- **Corner correction:** if the head clips a corner by a few px, nudge the player
  sideways past it instead of stopping the jump (Celeste).
- **Sonic (momentum option):** jump impulse 6.5 px/frame; rolling caps x at
  16 px/frame; air accel > ground accel.

**PITFALLS** — Don't ship a jump with **zero coyote + zero buffer** (feels broken).
Don't use one symmetric gravity for up & down. Don't make jump purely fixed in an
exploratory game. Don't kill with blind off-screen hazards (telegraph). Don't put
checkpoints only at level start in a precision platformer.

**COLLISION** — Resolve the body against solid tiles **one axis at a time** (move+resolve
X, then Y), probing the leading edge at 2+ points and sub-stepping fast falls so speed can't
tunnel through a floor — the stable, corner-snag-free idiom (it's also what makes corner
correction above implementable). Recipe + code in `techniques.md §5`.
Plain per-object Python (cheap, no C) — keep it inline per game, don't build a collision module.

**DECIDE ONE-WAY VS SOLID PER TILE, AND SAY SO OUT LOUD.** A *one-way* platform is only
tested while falling (`if vy > 0`), so the player jumps up through it and lands on top — the
cheapest possible platformer and what the shipped `demos/picogame_platformer.py` does
(see its `ONE-WAY platforms` comment). A *solid* tile also needs the rising branch (head bump:
`vy < 0` → stop and zero `vy`) and the horizontal one (walls). The consequence matters the
moment the level gains anything above the player: **a ceiling or a full wall built from the
one-way tile is passable from below**, which reads as a bug even though the collision code is
"working as written". So when a request adds geometry (ceiling, wall, shaft, closed room) to a
one-way game, either extend the resolver first or tell the player which tiles stay one-way —
never silently reuse the platform tile for a solid.

**IF YOU DO EXTEND IT, WRITE ONE RESOLVER, NOT A SECOND BRANCH.** The tempting patch is to bolt a
ceiling case onto the falling code, and it rots fast: the falling half stays hard-coded for `+y`
(its arithmetic assumes "land on the tile's top"), while the ceiling half stops probing tiles at
all and clamps against a remembered `ceiling_y` — so shafts, moving into a wall from below, and
closed rooms each want a third case. Resolve **one axis at a time, in the direction of travel**:
probe the cell the mover would enter this frame, and on a hit snap flush against it and zero that
velocity. The direction falls out of the sign, so there is nothing to duplicate, and one-way
collapses into a single condition on the probe (`solid or (one_way and vy > 0 and crossed)`) instead of a
parallel code path. `crossed` is the bit everyone gets wrong: a one-way tile catches you only if
your FEET CROSSED its top edge this frame - `prev_feet <= tile_top <= new_feet`. Testing `vy > 0`
alone re-lands you on a platform you are still overlapping after jumping up through it (the
classic "sticky ceiling-platform" bug), which is why hand-rolled versions end up bolting on
mid-body-embedding hacks and an extra standing-still probe. Keep the previous frame's foot y and
the whole special case disappears:

```python
prev_feet = st.y + PH                       # BEFORE the move
st.y += st.vy
feet = st.y + PH
t = tiles.at(st.x + PW // 2, feet)          # tile under the mover's centre
if solid(t) or (one_way(t) and st.vy > 0 and prev_feet <= tile_top(feet) <= feet):
    st.y = tile_top(feet) - PH              # snap flush
    st.vy = 0; st.on_ground = True
```

**MVP:** tunable jump with asymmetric rise/fall gravity + variable height · coyote
time + jump buffer · AABB tile collision with checkpoints.
**NICE TO HAVE:** apex hang (half-gravity near peak) · corner correction ·
dash/run-button + momentum/slopes.

---

## 5. Top-Down Adventure / RPG-Lite
*Device-proven: Quest tutorial, journey.*

*Exemplars: Zelda 1, Pokémon, classic JRPGs.*

**CORE LOOP** — Explore a tiled world room-by-room, fight/avoid enemies and talk
to NPCs, gather items/keys, and unlock progress toward a goal.

**WHAT MAKES IT FUN** — Exploration + small, legible problem-solving. The bird's-eye
view makes paths/obstacles/interactive objects easy to read; the reward is
*discovery* (a new room, an item, a shortcut), not stat-grinding.

**CONTROLS**
- D-pad: 4-dir movement (also sets facing — facing drives attack/interact dir).
- **A = Attack / Confirm** (sword swing in faced dir; advances dialog).
- **B = Use equipped item / Cancel** (Zelda B-item slot model).
- **X / Y = Inventory / Map** or a second item slot.
- Interaction is *contextual on facing*: walk into an NPC/sign, press A to
  talk/examine — no separate examine button.

**CAMERA / WORLD**
- **Room-based / screen-flip (Zelda 1):** world is a grid of screen-sized rooms;
  crossing an edge slides to the adjacent room. **Cheapest for RAM** — only the
  current room (+ neighbor being scrolled in) is resident. Best for tiny hardware.
- **Follow camera (Link to the Past / Pokémon):** tracks player continuously,
  confined to region bounds; smoother but needs a streamed map + culling. Bias
  the camera slightly ahead of facing.
- **Recommendation for 320×240 + tiny RAM:** start with **flip-screen rooms**
  sized to the screen.

**TILE COLLISION & INTERACTION** — Each tile has a passable/solid flag (plus
ledge/water/trigger). Movement checks the destination tile's flag. Interactions
are tile/entity triggers: face a tile + press A → run its script.

**COMBAT (keep simple)** — Melee sword arc: short-lived hitbox in the faced dir
for a few frames. Contact damage: enemies hurt on touch + brief i-frames/knockback
after a hit. Optional projectiles. Avoid turn-based battle systems unless that
*is* your game.

**KEEPING SCOPE TINY** — No leveling/XP; use **item-gated progression** (got the
key/boots/bombs → new area opens). Tiny inventory, one equipped B-item.
**Quests as flags, not systems** ("talked to elder = true"). Reuse tiles/enemies
with palette swaps.

**PITFALLS** — Don't build a full menu-driven JRPG battle system "because RPG"
(biggest scope trap). Don't make rooms look identical (players navigate by
landmark). Don't gate progress on undiscoverable info (cryptic Zelda-1 "burn this
bush"). Don't put long walls of text on a 320×240 screen — short paged boxes.

**MVP:** tile map + tile-flag collision with flip-screen camera · facing-based
melee + contact damage with i-frames · NPC dialog + item-gated doors (flags).
**NICE TO HAVE:** follow camera with bounds · small inventory/B-item slot ·
pushable blocks / simple environmental puzzles.

---

## 6. Maze / Collect (Pac-Man)
*Device-proven: the maze example.*

**CORE LOOP** — Clear every dot from a maze while evading four ghosts; eat power
pellets to briefly turn the tables.

**WHAT MAKES IT FUN** — Four ghosts with *distinct, readable AI personalities*
create emergent pressure and brief windows of relief. The tension/release rhythm
of scatter↔chase plus the risk/reward of chasing frightened ghosts for combo
points is the whole game. *(Source: Jamey Pittman's Pac-Man Dossier.)*

**CONTROLS** — D-pad steer (4-dir) with **direction queuing** (next input buffered,
applied at the next legal turn). **Cornering trick:** allow pre/post-turning
within ~4 px of an intersection center for a slight speed edge. A/B/X/Y reserved
for Start/Pause — pure Pac-Man is a one-stick game.

**THE FOUR GHOST AI ARCHETYPES** (exact rules, Dossier)
- **Blinky (red) "Shadow":** target = Pac-Man's **current tile** (direct chase).
  Becomes **Cruise Elroy** when remaining dots drop below a threshold — speeds up
  and keeps chasing even during scatter.
- **Pinky (pink) "Speedy":** target = **4 tiles ahead** of Pac-Man's facing
  (ambush). *Overflow bug:* facing up → 4 up **and 4 left** (authentic to replicate).
- **Inky (cyan) "Bashful":** take the tile **2 ahead** of Pac-Man, draw a vector
  from **Blinky's** position to that tile, **double its length** → endpoint is
  Inky's target. Erratic, Blinky-dependent.
- **Clyde (orange) "Pokey":** if **>8 tiles** from Pac-Man → target Pac-Man; if
  **≤8 tiles** → target his **own scatter corner** (bottom-left). Approaches then
  peels away.
- **Scatter corners:** Blinky top-right, Pinky top-left, Inky bottom-right, Clyde
  bottom-left.

**SCATTER/CHASE TIMER** (seconds, Dossier)

| Phase | Lvl 1 | Lvl 2–4 | Lvl 5+ |
|---|---|---|---|
| Scatter | 7 | 7 | 5 |
| Chase | 20 | 20 | 20 |
| Scatter | 7 | 7 | 5 |
| Chase | 20 | 20 | 20 |
| Scatter | 5 | 5 | 5 |
| Chase | 20 | ~∞ | ~∞ |

On every mode change, ghosts **reverse direction** (except leaving frightened).
Late levels are effectively permanent chase.

**FRIGHTENED MODE** — Eating an energizer flips ghosts to frightened: slow, blue,
flee semi-randomly at junctions; Pac-Man speeds up (lvls 1–4). Duration
**decreases with level**; ghosts flash white before reverting. **By level 19 they
no longer turn blue at all.** Eating frightened ghosts in one pellet scores
**200 → 400 → 800 → 1600**.

**RELEASE / SPEEDS / BOARD** — Ghost release by dot counters (Lvl 1: Inky at 30,
Clyde at 60). Anti-camping: eat no dot for **4 s** (3 s lvl 5+) → force-release
next ghost. Pac-Man: 80% speed lvl 1 → 100% by lvl 5. **Tunnel/warp:** wraps
Pac-Man across screen; ghosts move at **~half speed** in the tunnel (key escape).
**Fruit:** after 70 dots, again after 170; values 100 (cherry) → 5000 (key).
Single-screen maze fits 320×240; high-contrast walls, visible dots, instantly
distinct ghost colors.

**PITFALLS** — Don't make all four ghosts chase directly (identical AI kills
strategy). Don't forget the mode-change direction reversal (fairness cue). Don't
make frightened mode too generous at high levels. Don't omit tunnel slowdown.
Don't randomize ghost targets — deterministic targeting is what makes it learnable.

**MVP:** single-screen tile maze + dot-clear win + direction-queued movement · 2-4 chasers
whose targeting rules DIFFER from each other (Pac-Man's Blinky/Pinky/Inky/Clyde split is the
canonical worked example, not a shopping list - copy the *idea* of contrasting hunters, or the
result is the pacman demo already in the tree) · one pressure-release valve (power pellets are
Pac-Man's; a hiding spot, a slow field, a one-shot scare all serve the same beat).
**BRAID THE MAZE:** a "perfect" maze (exactly one path between any two cells) is unplayable as a
chase board - dead ends are death sentences. Knock out ~10-20% of the walls so every junction has
a loop, then check that no cell is more than a couple of steps from a loop.
**NICE TO HAVE:** full scatter/chase timer + mode reversal · tunnel warp with ghost
slowdown · fruit bonuses + Cruise Elroy speed-up.

**Field note:** the #1 grid-feel win is **turn buffering** — store the last-pressed
direction and apply it the instant the corner opens, so a slightly-early turn isn't dropped. Ghosts
use a **4-target greedy** AI: each picks a target tile (Blinky = you, Pinky = ahead of you, Inky =
mirrored through Blinky, Clyde = scatter when near) and greedily steps toward it — four lines, four
personalities. Details in `techniques.md`.

---

## 7. Puzzle (Falling-Block & Match-3)
*Device-proven on the workspace's dev titles (match-3, picotris); the public tree ships no puzzle exemplar yet - the runnable reference is the playground's `?game=match3`.*

*Exemplars: Tetris, Bejeweled/Candy Crush, Dr. Mario, Columns.*

**CORE LOOP** — A randomized stream of pieces falls into a confined well you steer
and rotate to form clearing patterns; clears free space and score, mistakes
accrete toward a top-out, and rising speed forces faster decisions — one bad
placement ends the run, so you always want "just one more."

**WHAT MAKES IT FUN** — **Tension ratchet** (the board is a debt you pay down;
failure is gradual and self-inflicted). **Outcomes bigger than input** (a 3-gem
move triggering a 9+ cascade; hoarding for a 4-line Tetris). **Risk/reward**:
delaying small clears to set up a multiplier trades safety for score.

**CONTROLS** (falling-block)
- D-pad L/R move (with DAS/ARR) · Down soft drop · Up hard drop *(or bind hard
  drop to X if Up risks accidental top-outs)*.
- A rotate CW · B rotate CCW · X Hold piece (or Columns: cycle jewels) · Y pause.
- Match-3 cursor style: D-pad move cursor · A confirm swap · B cancel · X booster.

**LEVEL / DIFFICULTY** — Tetris endless: difficulty *is* the gravity curve (speeds
every 10 lines). Dr. Mario: goal-based, fixed virus layouts, scale by virus count
+ fall speed. Columns: 6×13 well, matches of 3+ H/V/**diagonal** (signature
twist). Candy Crush: hand-authored levels with move limits + easy→hard→relief
sawtooth. Universal knob: **rising speed** — start very slow (free rule-learning),
escalate smoothly, no single cliff.

**TUNING**
- **7-bag randomizer:** shuffle all 7 tetrominoes, deal the bag before reshuffling.
  Bounds drought to **max 12 pieces between I-pieces**. Pure uniform random feels
  unfair (permits arbitrarily long droughts).
- **Classic NES gravity (frames/cell @60fps):** L0=48, L1=43, L2=38, L3=33, L4=28,
  L5=23, L6=18, L7=13, L8=8, L9=6, L10–12=5, L13–15=4, L16–18=3, L19–28=2,
  **L29+=1** (killscreen).
- **Modern Guideline gravity:** `sec/row = (0.8 − (L−1)·0.007)^(L−1)`; L1≈1.0 s/row;
  20G ≈ instant (playable only via lock delay).
- **Scoring (classic Nintendo, level L):** Single 40·(L+1), Double 100·(L+1),
  Triple 300·(L+1), **Tetris 1200·(L+1)** — ~30× ratio is why hoarding is optimal.
- **Scoring (modern Guideline, ×L):** Single 100, Double 300, Triple 500, Tetris
  800; **Back-to-Back ×1.5**; Combo +50·combo; soft drop 1 pt/cell, hard drop 2.
- **Lock delay (Guideline):** **30 frames = 0.5 s**; move/rotate resets, capped at
  **15 resets**.
- **DAS/ARR/ARE (@60fps):** DAS 10 frames ≈ 167 ms; ARR 2 frames ≈ 33 ms/cell;
  ARE ≈ 100 ms.

**PITFALLS** — Don't use pure uniform random (use 7-bag). Don't ship without lock
delay at high speed. Don't put hard drop adjacent to rotate, or on Up if Up also
nudges. Don't omit DAS/ARR or set DAS too long. Don't start fast, bury the rule,
or ship flat clears with no "juice." Match-3: detect & reshuffle no-valid-move
deadlocks.

**MVP:** solid 7-bag + clear rule + top-out · gravity curve tied to level/line
counter · lock delay (~0.5 s) + DAS/ARR.
**NICE TO HAVE:** hold + ghost piece · combos / back-to-back / drop points ·
next-piece preview + clear/cascade juice.

**Field note:** author levels as **ASCII-art strings** (Sokoban/Train) — one char per
cell, trivially editable and tiny; parse into the board on load. For continue-without-NVM, gate
progress with a **password** (a lookup table + a D-pad character editor) alongside `picogame_save`.
Details in `techniques.md`.

---

## 8. Racing — Pseudo-3D & Top-Down
*Device-proven both ways on the workspace's dev titles; the public tree ships no racing exemplar yet - the runnable references are the road example on `docs/pages/helpers/pseudo-3d.md` (8A) and `picogame_mode7`'s docs (8B).*

*Exemplars: Pole Position, OutRun, Super Sprint, Micro Machines, Mario Kart.*

### 8A. Pseudo-3D (OutRun / Pole Position)

**CORE LOOP** — Drive into the screen down a forward-scrolling road, reading
approaching curves/hills and dodging traffic, racing a clock or rivals to a
checkpoint.

**WHAT MAKES IT FUN** — Sensation of speed and weight: the road bends, the
vanishing point sways on corners (Pole Position's innovation), scenery streaks
faster as you accelerate. OutRun's "Super Scaler" sold exhilaration over
simulation.

**CONTROLS** — D-pad L/R steer (lateral `playerX`, −1..+1) · A accelerate · B
brake/reverse · X gear Hi/Lo · Y horn/look-back. At top speed a full road crossing
(−1→+1) should take ~1 s.

**TRACK DESIGN** — Build from **segments** tagged with curve + hill delta;
concatenate equal-curve runs into corners (enter/hold/leave lengths shape the
read). **Curvature accumulates by addition** per scanline (`dx += segment.curve`)
— authentic addition-only fixed-point. Branching forks add replayability.
Checkpoint timer (OutRun) or qualifying lap (Pole Position) drives tension.

**TUNING (canonical Jake Gordon "javascript-racer" values)**
- Projection: `cameraDepth = 1/tan((fov/2)·π/180)`; **fov=100° → ≈0.84**;
  `scale = cameraDepth/camera.z`; `screen.w = scale·roadWidth·w/2`.
- `cameraHeight=1000`, `roadWidth=2000` (half), `segmentLength=200`,
  `rumbleLength=3`, `lanes=3`.
- `drawDistance=300` segments — **on 320×240 tiny-RAM, cut to 80–160 and fog-cull
  early.**
- Curve presets EASY 2 / MED 4 / HARD 6; Hill LOW 20 / MED 40 / HIGH 60.
- `centrifugal=0.3` — push off road on corners:
  `playerX −= dx·speedPercent·curve·centrifugal` (faster + tighter = flung wider —
  the steering challenge).
- Speed @60fps: `maxSpeed = segmentLength/step = 12000` (clamp so the car can't
  skip a segment — keeps collision per-segment); `accel = maxSpeed/5` (0→top ~5 s);
  off-road decel `−maxSpeed/2`, off-road speed limit `maxSpeed/4`.
- Parallax: sky 0.001, hills 0.002, trees 0.003 per unit curve.

**PITFALLS** — "Oatmeal effect" (wrong/constant zoom rate → shimmering road) — keep
`scale=cameraDepth/z` strictly per-segment. Never move >1 segment/frame (breaks
cheap collision). Avoid S-curves over crests (the raster cheat shows). Don't
over-render `drawDistance` on weak HW. Sort sprites back-to-front by segment z.

**MVP:** forward-scrolling road, per-segment scaling + curve-by-accumulation ·
accel/brake/steer with centrifugal push · checkpoint timer.
**NICE TO HAVE:** hills + parallax layers · traffic/rivals · branching forks.

*picogame — pick the ground renderer:* **segment/scanline road** into a `StripDraw` (the classic
OutRun look: curves, hills, rumble strips, ~0 RAM — see `examples/picogame_stripdraw_example.py`), or the native
**`picogame_mode7` floor** for a *textured, steerable* ground you drive across in any direction
(kart-racer look, ~29 fps full-screen, also 0 RAM in a `StripDraw`). Mode-7 gives real texture and
free rotation but no hills; the scanline road gives hills and crests but no true 2D ground. Traffic
and scenery are ordinary Sprites. **Match the sprite maths to the renderer you picked:** with the
SEGMENT projector, `sprite.scale = F/(F+z)`; with the C road pair the rows are LINEAR in screen
space, so scale by the row's half-width instead (`scale = hw[row] / hw[N-1] * FULL`), or cars read
mis-sized against the road at their own row. Draw order: the engine draws in add order (no
z-sort), so use the fixed-slots pattern — pre-add N sprites once, each frame sort your entity
list and re-assign it into the slots (worked example: the pseudo-3d page's billboard section -
NOTE it demonstrates the RAYCASTER's `project_sprite`; on the road, position sprites from
`road.row_of(z)` / `edges_of(row)` and scale by `half_of(row)` instead - only the fixed-slots
draw-order idiom carries over).

**The road renderer — `picogame_road.Road` (device-proven on picobike: 15 → 39 fps over the
Python loop):** the per-scanline Python road is the genre's classic wall; the wrapper drives the
native `pg.road_edges` + `Canvas.road` pair from human units and owns every fixed-point table:

- `Road(pg, W, H, horizon, colors, curves=((period_wu, swing_px), ...), hill_amp=...)` — curve
  periods in world units, swing in pixels of lateral bend (periods are pow2-rounded internally:
  the int32 phase-wrap safety).
- per frame: `road.tick(dist, lateral_px)`; per strip: `road.draw(view, vy)`; **hills**:
  `road.set_grade(-1..1)` moves the horizon (downhill lifts it — more road visible). Give the
  StripDraw `hill_amp` px of headroom ABOVE the nominal horizon; the wrapper sizes its tables.
  Derive grade from two *incommensurate* sines of distance (one plain sine reads as a washboard),
  and feed it into speed (`speed += grade * PULL`) — a hill you can only see is scenery.
- gameplay reads the SAME curve model back: `curve_at(dist)` for centrifugal pull / AI, and
  `row_of(z)` / `half_of(row)` / `edges_of(row)` to place and scale sprites ON the road
  (the rows are linear — scale by `half_of`, not `F/(F+z)`).

**Know the trade first: the curvature is a fixed two-sine FIELD of world distance, not an
authored track** — you choose periods and swings, not corners. That gives an endless,
non-repeating road (which suits a 1–3 minute handheld run), but you cannot author a specific
enter/hold/leave corner, a fork, or a memorable circuit. Want those? Accumulate the edges in
Python from your own per-segment curvature table — and budget for it: ~8–10 ms/frame on an
RP2040 (measured on picobike before the C pair), a quarter of a 30 fps budget. Decide BEFORE
designing the track; the TRACK DESIGN paragraph above assumes the authored-segment model.

The raw pair (`pg.road_edges` + `Canvas.road`) is for a custom road look only — its full calling
contract (row order, tables, typecodes, the phase-wrap rule) lives in
`docs/pages/helpers/pseudo-3d.md` and the API reference. The simulator implements the pair
bit-identically to the firmware (golden-tested), so build and screenshot the road in the sim like
any other game; `hasattr(pg, "road_edges")` guards only OLD firmware. Keep in Python: grass fill
(one rect/strip), the finish-line chequer, and gameplay.

### 8B. Top-Down (Super Sprint / Micro Machines / Mario Kart)

**CORE LOOP** — See the track from above, corner cleanly, grab boosts/items,
out-position rivals over laps.

**WHAT MAKES IT FUN** — Readable whole-track tactics + close contested racing.
Super Sprint fits the whole circuit on one non-scrolling screen; Micro Machines
makes proximity the game (push a rival off-screen to score).

**CONTROLS** — D-pad steer (L/R rotate car) · A accelerate · B brake/reverse · X
drift/handbrake (hold to charge mini-turbo) · Y use item.

**CAMERA TRADEOFFS** — Fixed whole-track (Super Sprint): zero scroll, cheapest,
full strategic read, tiny cars. Scrolling shared-screen (Micro Machines): bigger
tracks, no split-screen — **ideal for tiny handheld**. Behind-car chase: most
immersive but needs the pseudo-3D pipeline. **Top-down is lower-RAM/CPU and reads
better on 320×240.**

**DESIGN / CATCH-UP / DRIFT**
- Hazards escalate by tier (oil slicks, tornadoes; walls destroy car). Between-race
  upgrades (Super Sprint wrenches).
- **Position-based items:** trailing players draw powerful items, leader gets
  bananas/coins. Blue shell (MK64, 1996) existed to keep players together.
- **Drift mini-turbo (Mario Kart):** charge while steering into the turn; short
  drift → small boost, long → big; **3 tiers max**; always telegraph the
  spark/charge tier. Reference durations (MK8DX): mini ~0.62 s, super ~1.67 s,
  ultra ~2.63 s.

**PITFALLS** — Obvious rubber-banding feels like cheating — keep AI catch-up subtle,
prefer *item-based* (player agency) over raw AI speed. Don't overuse leader-punish
at the line. Keep top-down sprites ≥~12 px. Always telegraph drift charge. Define
the exact lead distance that scores in shared-screen.

**MVP:** rotate-and-thrust car + off-track penalty · lap/finish (or
screen-distance score) · one waypoint-following CPU rival.
**NICE TO HAVE:** drift + 2-tier mini-turbo · position-based items / one catch-up
item · hazards + between-race upgrades.

---

## 9. Endless / Arcade
*Device-proven: corona, Starfall.*

*Exemplars: Flappy Bird, Snake, Doodle Jump, Canabalt, runners.*

**CORE LOOP** — No "win," only a high score and a death you can blame on yourself:
constant/auto motion + minimal input; one mistake ends the run; instant retry.

**WHAT MAKES IT FUN** — The near-miss effect (almost-clears light up the same
regions as wins → "almost won") + sub-second restart = "one more try." With one
input and fair generation, **death always feels self-inflicted.**

**CONTROLS** — Many are genuinely **one-button**:
- **Canabalt / Flappy:** A = jump/flap (Canabalt: hold longer = higher jump).
  Leave the rest unbound — that *is* the design.
- **Snake:** D-pad steer; **block 180° reversals** (can't turn into your neck).
- **Doodle Jump:** D-pad L/R steer (apply velocity, not instant position); jump is
  automatic; A optional shoot; screen edges wrap.

**DIFFICULTY / GENERATION** — Canabalt: continuous acceleration, geometry stays
similar, reaction windows shrink (no discrete levels). Flappy: flat speed,
difficulty in the margin; randomize gap *position* within safe bounds, constant
horizontal spacing. Doodle Jump: stacked platforms, **max vertical gap ≤ ~0.7–0.8
× jump height**, variety = static/moving/breakable/disappearing. **Universal
fairness rule:** every generated gap must be clearable given current physics +
speed — randomize *within* safe bounds, never *across* the solvability boundary.

**TUNING (real, reverse-engineered)**
- **Flappy Bird (60fps):** gravity ~0.25–0.6 px/frame² (gentle clones 0.25–0.3);
  flap sets velocity to ~−5 to −9 px/frame (−6.5 popular); vertical gap ~100–150
  px; horizontal pipe spacing ~200 px; scroll ~3–4 px/frame. The *flap* is
  deliberately unrealistic (constant post-tap velocity regardless of prior
  velocity — that consistency makes it learnable). **For 320×240:** gap ≈90–100 px,
  scroll ≈2–3 px/frame, gravity ≈0.4, flap ≈−6.
- **Snake (Nokia 6110, 1997):** logical grid ~20×15 cells; starts at 3 segments;
  +1 per food; progressive speed-up. **For 320×240:** 16-px cells → 20×15 grid;
  start ~8 cells/sec, shorten tick ~3–5% per food, floor ~15 cells/sec.
- **Doodle Jump:** fixed bounce velocity → fixed jump height H; clamp platform gaps
  below ~0.8·H; recycle off-screen platforms (object pool).
- **Restart target:** death → playable in **under 1 second**, single button, no
  menus/animations.

**SCORE PSYCHOLOGY** — High-score chasing = variable reward / partial reinforcement
(slot-machine effect). Near-miss = feels like almost-winning. "My fault" death
converts frustration into retention.

**PITFALLS** — Slow/menu-gated restart (kills the loop). Generating impossible gaps
(one unfair death → players blame the game). Spawning food/obstacles inside the
player. Too many inputs (destroys death legibility). Step-wise difficulty spikes
(use smooth ramps). Allowing 180° instant reversal in Snake. Floaty/inconsistent
jump impulse. No object pooling (recycle a fixed handful — critical on tiny RAM).

**Trail/history recycling** (wake-style games, snakes, ghost paths): the worked pattern is
`demos/picogame_snake.py` (a bounded deque drained in place + a Tilemap body - zero per-frame
allocation); read it before hand-rolling a ring buffer.

**MVP:** one core verb with deterministic tunable physics (the 3–4 constants) ·
fair generation with a guaranteed-solvable spacing clamp · sub-1-second one-button
restart + persistent high score.
**NICE TO HAVE:** difficulty-via-speed ramp · obstacle/platform variety · near-miss
feedback (sound/flash on tight clears) + screen-edge wrap.

---

## 10. Tower Defense / Grid Placement
*Recipe only — no shipped exemplar yet; treat the tunings as starting points and validate on device early.*

*Exemplars: SALVO (this project), Kingdom Rush, Bloons.*

**CORE LOOP** — Plan → watch → adapt: place/upgrade towers on a grid, then waves of
enemies walk a fixed path while towers auto-fire; earn currency per kill to build
more between (or during) waves; survive N waves before too many leak past.

**WHAT MAKES IT FUN** — The plan-then-watch tension (you commit, then can't act) +
a wave you *barely* survive + the economy decision (save for a big tower vs. spam
cheap ones). Reading a near-breach and topping up the right lane is the hook.

**CONTROLS** — Grid, not twitch: `picogame_ui.GridCursor` moves a build cursor over
buildable cells (D-pad), **A** opens a build/upgrade menu (`SceneMenu`/`OptionsMenu`),
**B** cancels; a dedicated **start-wave** button (or auto-start on a timer). All the
"pick from options over a grid" UI already exists — don't hand-roll it.

**ENGINE MAPPING** — Path + buildable cells as a **Tilemap** (tile ids flag path vs.
buildable, queried with `picogame_tiles`); enemies as a **`Pool`** walking a waypoint
list (lerp toward the next node); towers = sprites with a per-tower fire timer +
range test (`tower.near(enemy, r)`); projectiles/hitscan as a **`Pool`** (never alloc
per shot); currency/wave/lives on a **fixed `HudBar`** layer. `set_view` only if the
field is bigger than the screen.

**DIFFICULTY** — Ramp waves by **count → speed → composition** (armored/fast/flying
variants that beat one tower type), plus modest HP growth; **telegraph the next
wave's makeup** during the build phase so a loss is "my build," not a surprise. Give
a real build/breather phase between waves.

**PITFALLS** — Unreadable tower **range** and enemy **path** (draw range rings on
select; make the path a distinct tile). Per-frame projectile allocation (Pool it).
Too many moving enemies on RP2040 (**cap the live count**, tune waves to it). Fiddly
free placement (snap to the grid via `GridCursor`). Fully-passive play (let upgrades/
targeting priority give the watch-phase a decision).

**MVP:** one Tilemap path · one tower (place + auto-fire nearest-in-range) · one
enemy `Pool` on waypoints · currency + ~5 telegraphed waves + lose-on-leak.
**NICE TO HAVE:** tower types/upgrades · range preview on select · a boss wave ·
`picogame_save` meta-progress.

---

## 11. Card / Menu-Driven Roguelite (Deckbuilder)
*Device-proven: picatro, Star Cluster.*

*Exemplars: picatro (this project), Slay the Spire, Balatro-likes.*

**CORE LOOP** — Turn-based, menu-driven: draw a hand → **choose** cards/targets from a
selection → resolve effects (score/damage/status) → advance through a run of
escalating encounters; a meta layer (unlocks/relics) rewards the *next* run.

**WHAT MAKES IT FUN** — **Synergy discovery** and the snowball: a run where your
picks start comboing. "One more run" comes from seeded variety + meta unlocks, not
twitch. **This is a slow genre — the 10-second bar means *intrigued by the first
combo*, not *scoring in 10 s*; runs are minutes and turn-based, so there is no frame-
timing pressure at all** (see the quality-bar note).

**CONTROLS** — Pure selection: `GridCursor`/`SceneMenu` to move over the hand/targets,
**A** = play/confirm, **B** = back; no real-time input. Lean entirely on `picogame_ui`
+ `picogame_options` — these widgets exist for exactly this.

**ENGINE MAPPING** — Cards as sprites driven by **one multi-frame bitmap** (`frame` =
card face), or DRAWN: **one `StripDraw(always_dirty=False)` per card slot**, built once at
boot — the callback's `view` IS a Canvas, so `view.fill_round_rect` + `view.text` paint the
card with zero retained bytes. Three rules the pattern lives on (worked example:
`games/picatro/code.py`, `class Card`): the callback ERASES its own rect first (a StripDraw
does not clear), coords are absolute-minus-strip-origin (`ox = self.x - vx`), and you
`invalidate()` a slot only when its card changes. The hand is a small list/
`Pool`; a `state` machine (DRAW → SELECT → RESOLVE → NEXT); **`picogame_rand.Bag`**
for the deck (no-streak draws = fair) and a seeded `Rand` for daily/repeatable runs;
**`picogame_save`** for meta-progression. Almost all cost is UI + logic, so RAM is
easy — spend the budget on readability.

**DIFFICULTY / PACING** — Escalate **encounter stakes and enemy patterns**, not
reflexes; telegraph what's coming. Balance around the deck's power curve; give the
player agency to shape the deck (add/remove/upgrade between encounters).

**PITFALLS** — Text-heavy UI that won't fit 320×240 (**iconographic cards + short
labels**, not paragraphs; use `Canvas.text` sparingly). Making it real-time (it's
turn-based — don't force arcade pacing or the arcade quality bar). Per-frame
rebuilding of card lists (reuse). Opaque effects (show the number/outcome).

**JUICE for a menu game** (screenshake is structurally out - fixed layers ignore `set_view`,
so SS1.3's list needs a substitute): card LIFT on select (redraw the slot a few px higher),
a 1-3 frame colour flash on the hit panel (swap the fill colour + `invalidate()`), number
pop-ups via a short-lived SceneLabel, `Particles` sparks on damage (they ride ABOVE StripDraws),
hit-stop on big resolves, and `sfx.Kit` on every card played. All of it is invalidate-driven -
none of it needs a moving camera.

**MVP:** a deck (`Bag`) · a hand you select from (`GridCursor` + `SceneMenu`) · a
resolve step with a visible score/damage · a short run of ~3 encounters · seeded
`Rand`. **NICE TO HAVE:** card synergies/relics · `picogame_save` meta-unlocks ·
a daily seed.

---

## 12. First-person raycaster / dungeon crawler
*The public tree ships no raycaster exemplar yet - the runnable reference is the raycaster section of `docs/pages/helpers/pseudo-3d.md` (full wiring: StripDraw, attach, billboards).*

*Exemplars: Wolfenstein 3D, Eye of the Beholder, Legend of Grimrock, DOOM (in
atmosphere).*

**CORE LOOP** — Walk corridors in first person, where something may wait around
every corner; fight enemies that rush you and grow, find the key/exit/treasure.

**WHAT MAKES IT FUN** — The tension of what's around the corner (you only see
where you're looking) and the illusion of depth on a 2D display: an enemy that
grows from a distant dot into a threat filling half the screen is the cheapest
jump-scare this hardware can produce.

**TWO SUB-GENRES by movement — pick one up front:**
- **Step-based dungeon crawler** (cell-by-cell steps, 90° turns) — ideal for
  picogame: the camera doesn't move between steps, so with `.attach()` (temporal
  redraw + pose-cache) standing still costs ~nothing and the game holds ~30 fps.
  Combat can be turn-based/menu-driven (combine with §11). Easiest to read and
  to tune.
- **Continuous shooter raycaster** (Wolfenstein) — smooth walking and turning,
  ~22–30 fps while moving; billboard enemies via `project_sprite`, action in the
  same frame.

**CONTROLS** — UP/DOWN step forward/back · LEFT/RIGHT turn · **A** action/sidestep
(strafe modifier) · **B** attack/fire. Step-based: one press = one step (with a
short glide via `picogame_seq`/`Tween`); use `repeat()` for smooth repeat on hold.

**MAP / DIFFICULTY** — Map = a list of strings (`'0'` empty, `'1'..'9'` wall
types) — small and readable (≤ ~16×16 per level; longer corridors = longer rays =
slower cast). Different wall types (colors) serve as landmarks — in a maze of
all-gray walls the player gets lost and bored. Scale difficulty by enemy density
and approach speed, not HP sponges.

**TUNING / RULES OF THUMB**
- `Raycaster(world, wall_colors, sky, floor, fov=0.66, stride=2)`; side walls a
  notch darker (color pairs in `wall_colors`) = a free depth cue.
- **`stride`** is the main perf/sharpness knob: 1 sharpest, 2 default, 3 balanced,
  6 fastest (coarser columns). Raise `strip_h` too (see `engine-capabilities.md`).
- **Movement without walking through walls:** `rc.solid(int(nx), int(ny))` before
  each step (off-map = wall).
- **Enemies = billboards:** plain `Sprite`s added to the scene **after** the
  StripDraw; every frame `p = rc.project_sprite(g.x, g.y)` → `None` = hide
  (behind a wall/off-screen), otherwise set position + `scale = size /
  bitmap_height`; draw farthest first (sort by depth). Keep enemy speed below
  player speed.
- Have enemies **announce the attack by growing** — the player must have time to
  react before they arrive (see SKILL.md §1.4, ~250 ms reaction threshold).

**PITFALLS** — Don't write your own DDA in Python — the native `pg.raycast` (via
`picogame_ray`) is an order of magnitude faster; only the desktop sim has a
Python version. With temporal redraw, create the StripDraw with
`always_dirty=False` and call `rc.attach(sd)` — otherwise a full-screen redraw
every frame throws away the whole win. Add billboard sprites to the scene after
the StripDraw (or the walls draw over them). At grazing angles a thin column
occasionally flickers (a "tooth") — an inherent DDA artifact; `stride=1` softens
it at a performance cost.

**MVP:** map from strings + `Raycaster` + `.attach()` · movement with a `solid()`
test · 1 billboard enemy type that walks toward the player · exit tile = win.
**NICE TO HAVE:** keys/doors — `Raycaster.set_cell(x, y, 0)` opens one cell at runtime (grid, `solid()` and `.map` stay consistent; works with a standing camera) · minimap (a small
`Tilemap` in a corner) · collectibles (billboard + WORLD-space distance: `(ix-px)**2 + (iy-py)**2 < r*r` in map units - `Sprite.near()` is a SCREEN-space test and first person has no player sprite) · `mode7` textured
floor under the walls · step-based menu combat (§11).

---
