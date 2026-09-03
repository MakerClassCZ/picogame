---
name: picogame-game-design
description: >-
  Design and build a 2D game for the picogame engine (a 2D engine for CircuitPython on
  microcontrollers — RP2040 / RP2350 / ESP32-S3, e.g. the PicoPad) — use when
  the task is making, designing, or implementing a small game or example for it, e.g. "make a tiny shooter".
metadata:
  api_level: 1  # picogame API level this skill was written against
  validated_engine_commit: a1bc391d43 (MakerClassCZ/circuitpython, branch picogame)
  last_validated: 2026-09-03
---

# picogame game design

You design and build small games for **picogame** — a retained-mode 2D engine for CircuitPython on
microcontrollers (RP2040 / RP2350 / ESP32-S3), e.g. the PicoPad: D-pad + a few buttons, little RAM,
most commonly a 320×240 display (but the game reads the resolution from `picogame_game.screen()` — it's not
hardcoded). The engine comes with a desktop simulator. **Your job is GOOD GAME DESIGN
first, then mapping it onto the engine.** This file carries the design knowledge; reach for the
references only for engine specifics, a genre recipe, or a named technique. Build in the simulator and
validate with screenshots.

**How binding are the rules here?** Three levels, used consistently:
- **MUST** — technical correctness on this platform (`pg.rgb565()`, no full-screen Canvas on RP2040,
  `touch()` after in-place edits, pools instead of per-frame alloc). Breaking these breaks the game.
- **DEFAULT** — measured best practice (State object, loop-in-function, A=confirm/B=cancel, constants
  over settings menus). **Default to it unless the game's stated requirements justify an exception —
  and say so.** A ≤50-line prototype proving a core loop may use 3 bare globals and skip the
  DEFAULT architecture (State object, loop-in-function) — MUSTs still hold; graduate it when the
  loop earns it.
- **TASTE** — design heuristics (one verb, ramp shape, palette size, juice set, title layout). Strong
  guidance, not law — **break any of them for a stated reason.** Rules below are tagged `[MUST]` /
  `[DEFAULT]` / `[TASTE]` where the voice alone would not tell you; an untagged bold imperative in a
  design section is TASTE, in an engine section MUST.

The bar for "done" is not "it runs" — it's **fun in the first 10 seconds**. Everything below serves
that and the **"one more go."**

---

## What the engine gives you — and its limits

Design **inside this envelope** (details + costs in `references/engine-capabilities.md`):

**You get:** a retained **Scene** with automatic dirty-rect redraw (mutate objects, call
`scene.refresh()`); **Sprites** (move, flip, multi-frame animation, runtime `scale`/`angle`/90°
`transpose`, and cheap blit effects `flash`/`tint`/`dither`/`shadow`); **Tilemaps** (big grids/boards,
cheap); a **moving camera** (`set_view`) over a world bigger than the screen + fixed HUD layers;
**Canvas** (a retained shape/panel surface), **StripDraw** (0-RAM drawing straight into the frame:
full-screen animated effects (road, gradient sky, pseudo-3D) AND text/HUD/panels with no buffer —
`picogame_ui` (HudBar, text boxes) is built on it — plus on-demand panels that repaint only on
change), **Particles**; native **pseudo-3D** (`Canvas.mode7` perspective floor, `pg.raycast`
first-person walls — both 0-RAM in a StripDraw, driven by `picogame_mode7`/`picogame_ray`); helpers
for input (incl. auto USB gamepad/keyboard), timing, collision, pools, text/HUD, audio, NVM save,
seeded random, juice (`picogame_fx`); and a **desktop simulator** so you build without hardware.

**The limits (design around these):**
- **Tiny RAM** — RP2040 ≈ 138 KB heap *typical for the supported build — measure yours* (RP2350 ≈ 520 KB). **Assets dominate.** Never a full-screen
  `Canvas` (320×240 = 150 KB); use a Tilemap or StripDraw. Keep the **moving-object count low** (a
  static background + a small moving foreground is the sweet spot).
- **Few buttons** — D-pad + A/B (sometimes X/Y). No analog, no mouse. Map the whole game to these.
- **No GPU / no alpha blending** — transparency is a single transparent color, plus the `dither`
  (stipple) and `shadow`/`tint` blit modes. Rotation is nearest-neighbour (crisp at 90°/integer
  scale, shimmery otherwise).
- **Small screen, ~30 fps** — design for readability at 320×240 and short sessions.
- **Paletted art is cheapest** — PAL8 = 1 byte/px; build every color with `pg.rgb565(r,g,b)`.

These limits are your **style engine, not just a budget** — a constraint embraced becomes a
signature (*Downwell*'s three colours, *Canabalt*'s single button, *Thomas Was Alone*'s rectangles —
three different answers). Pick which limit becomes *this* game's look rather than fighting toward
fidelity the device can't give. If a design still needs more than the envelope, **cut it down**
until it fits — that's the craft, not a failure.

---

## Part 1 — Design fundamentals (apply these every time)

### 1.0 Fantasy before the verb (what the player gets to *be*)
Before naming the verb, name the **fantasy** — what the player gets to be, or feel they're doing. The
same verb under a different fantasy is a different game: *catch* = frantic short-order cook /
lighthouse keeper hauling in the shipwrecked / last-line goalie. Test: can you say in one line what
the player will *brag about*? Pick the fantasy first and let it bias every later choice (palette,
sound, name, the twist). Then write two one-liners *before any code*:
- **Identity** — either "It's *$GENRE*, **and also** ___" or "It's *$FANTASY*, played through
  *$VERB*". The test is not "does it sound fresh": the twist must **change a decision the player
  makes every few seconds, or change what the verb acts on** — if it only changes the skin, it's a
  clone; keep going (one twist, not five).
- **Anti-pillars** — 1–2 things this game is **NOT** (your defense against scope- and tone-drift).

### 1.0b Divergence pass (before the brief — two minutes of thinking, no code)
Write **three** one-line concepts that all satisfy the request, each differing from the others on at
least one axis: the fantasy, what the verb acts on, or what ends a run; for each, one clause on what
the player would tell a friend. Rules: none may be the nearest shipped example or a genre exemplar
with the names changed; at least one must change *what the verb acts on* rather than add a
mechanic; at least one must fit the RP2040 envelope with room to spare. Choose ONE and write why it
beat the other two in one sentence — "most fun" is not a reason, "the twist changes a decision the
player makes every few seconds" is. Record the losers in the brief under *considered*.
Everything this skill lists after this point — juice touches, ramp shape, palette size, title
presentation, control map, MVP items — is a **menu you draw from to express THAT concept, not a
checklist**: for each item you take, be able to say what it does for this game; skip the ones that
do nothing. If the user already handed you a concept, run the pass on the *twist* (three twists,
pick one). If the user asked for a faithful clone, say so in the brief and skip the pass.

### 1.1 Core loop & one verb
The **core mechanic** is the single verb the player repeats (jump, shoot, steer, match, dodge). The
**core loop** is the tightest cycle on it: *act → see result → reward → act again, with a twist.*
- Name the verb in ONE word (Tetris=fit, Snake=grow, Asteroids=thrust+shoot, Flappy=flap,
  Papers Please=inspect — any genre). If you can't, the design isn't focused — cut until you can.
- One game, one idea. `[TASTE]` Add depth by giving the **same verb new contexts** (Tetris adds speed
  before it adds a button) before adding a verb; a second verb needs a reason in the brief.
- The loop must be legible by *watching* for ≤10 s, and **fun with no art and no sound** — prototype
  with generated shapes and prove the loop before adding anything.

### 1.2 Design backward from a feeling (MDA)
Decide the **target feeling** first — name the emotion (the MDA aesthetics: sensation, fantasy,
challenge, discovery, expression, fellowship, narrative, submission; or plainer: tension, calm,
curiosity, dread, glee), then **reason backward** down the MDA chain: feeling → the dynamic that
produces it → the ONE mechanic that creates that dynamic. Worked: *dread* → not knowing what is
behind you → a limited view cone. Write the chain in the brief; it is what you tune against.

### 1.3 Game feel & juice (the cheap wins, ranked by fun-per-byte)
Polish the *response*, not the simulation. On a handheld you own the whole pipeline — act on the
**same frame** the button is read (≤1–2 frames latency). Then a **menu**, roughly in fun-per-byte
order — take what expresses the fantasy (a cozy or a dread game may take one item, or none), and
say what each touch expresses; the numbers are starting ranges:
1. **Sound on the key action** — the single highest fun-per-byte feedback (see 1.7).
2. **Hit-flash** — `picogame_fx.Flash(spr)`: `fl.hit(WHITE, 2)` on impact, `fl.tick()` once per frame before `refresh()`. Cheapest visual punch, and the helper exists because the hand-rolled counter is off by one (it counts LOGIC frames, so the sprite lights for one frame instead of two) and because a flash overwrites a tint/dither the sprite may be wearing.
3. **Screenshake (trauma model)** — keep a scalar `trauma 0..1`; events *add* (small kick +0.6,
   hit +0.8, big +1.0 — under ~0.5 the squared offset is sub-pixel, i.e. invisible and only costs
   repaints); each frame offset = `max_off * trauma² * rand(-1,1)` via `picogame_fx.Shake`
   (strip-rendered games — road/raycaster/mode-7 — use `Shake(None)` and spend `.ox`/`.oy` in the
   renderer's own camera params; `set_view` never moves a StripDraw). `max_off ≈ 6 px` on
   320×240 (>10 hides the action); decay ≈ 0.9/s (the default 0.03/frame).
4. **Hit-stop** — freeze the sim **2–8 frames** (2–6 typical) on a big impact; makes hits *connect*.
5. **A particle/pop on the event** — `picogame_fx`/`Particles`; a ring or sparks on catch/score.
6. **Easing/tween** — UI and pickups ease in (`picogame_fx.Tween`, ~0.15–0.35 per frame), don't snap.
7. **Number pop-ups**, screen flash (1–3 frames white) for big moments.
Don't over-shake or juice gameplay-critical readability away. `picogame_fx` (Shake/Fade/Tween/Camera)
+ the native blit effects (`flash`/`tint`/`dither`/`shadow`) cover most of this for ~free.
**Safety:** never flash the full screen faster than **3 Hz** (≥10 frames apart @30fps), and watch for
clustered hit-flashes aggregating past that — it's a seizure risk; prefer localized `sprite.flash`.
Keep effect intensity in a **named constant at the top of the file** (e.g. `SHAKE = 1.0`) — on
CircuitPython the game's source sits on disk and is directly editable, so that fully stands in for
an "effects setting"; no menu needed.

### 1.4 Difficulty, flow & fairness
Keep the player in the **flow channel** — challenge tracking rising skill. For a 1–3 min handheld run:
- `[TASTE]` **Prefer ramping by speed / density / variety to HP inflation** (HP is fine when the
  fantasy is a siege or a boss). Tetris speeds up; Pac-Man adds pressure.
- **Give the ramp a shape** — don't climb monotonically (flat = boring by minute two). One shape
  that works: a **sawtooth** — build tension 20–40 s → *release* at a milestone (wave clear,
  checkpoint) → re-engage ~10–15 % harder, first real spike around **~60–90 s**, every spike
  earning a moment of relief. Those numbers come from wave-based games; a genre with no waves has
  its own shape (an endless runner ramps continuously from second one, a puzzle ramps per level).
  Take the principle — *shaped, not monotone; every rise repaid* — and set the timings from YOUR
  loop. NOTE the difference between the first **threat** (often immediate: Flappy's first pipe
  arrives in ~2 s, and that is the baseline challenge) and the first **spike** (a step up from it).
- **Announce every threat in advance** — a readable wind-up, a flash, a sound (telegraphing); no
  unavoidable damage. The player must always feel
  "my fault." Human reaction floor ≈ **250 ms (~8 frames @30fps)** — give at least that to react.
- **Generosity mechanics** make games feel fair: a small window where the game reads what the
  player MEANT instead of what the input strictly was. **Name your genre's own** — the canonical
  four are platformer-shaped and are examples, not a checklist: **coyote time 3–8 frames** (jump
  shortly after leaving a ledge), **jump buffer 3–6 frames** (honor a jump pressed just before
  landing) — both in `picogame_input.Timer`; **i-frames** after a hit (mercy window so one hit
  can't chain-kill); **hitbox smaller than the sprite**. What that becomes elsewhere, each derived
  by a builder who found nothing in the list above: **lock delay** (falling-block: ~0.5 s of grace
  after a piece lands, re-armed by a move); **turn buffering** (maze: a turn entered just before
  the junction still takes); **corner assist** (top-down: slide along a wall instead of catching on
  it); **arming delay** (asteroids: fresh fragments can't kill for a few frames); **held-walk
  break** (first-person: a held direction doesn't stick you to a wall). Frame counts are @ 30 fps —
  the baseline; scale up for 60.
- **Instant restart** (< ~0.5 s, re-init in place) — failure must cost almost nothing.
- **Keep tuning parameters as named constants at the top of the file** (enemy speed, spawn rate,
  i-frames, shake strength). On CircuitPython the game's source sits on disk, so anyone can edit
  difficulty and effect intensity right in the code — that's the local equivalent of a settings menu
  and the **default path** (accessibility for free). Add a difficulty menu
  (`picogame_options.OptionsMenu` + `picogame_save`) only where a game genuinely wants one on the
  title screen — not out of obligation.

### 1.5 The "one more go" (retention — ethically)
Reward **skill** and keep the rules **readable** — the player must know what killed them. No hidden
probability, no behind-the-scenes difficulty they can't read.
- **Give the player a reason to come back that fits the fantasy.** Score chase + personal best
  (rising, legible: +1 per X beats opaque scoring) is the arcade answer; par, a clear time, secret
  exits, alternate endings or a place that changes are others.
- **Near-miss** tension and **peak-end**: a run is remembered by its peak and its end — end on a high,
  whatever *this* game's flourish is (a death flourish + the score front-and-center is the arcade one).
- The hook is a **short, self-restarting loop** with escalating stakes — make restarting effortless.
- `[TASTE]` **A pass/fail game has no score axis — consider giving it one.** Level-based designs (puzzle
  rooms, escape, "reach the exit") are binary: you cleared it or you didn't, so there is nothing to
  beat and no reason for a second attempt at a level already solved. Add ONE continuous measure over
  the top — optional collectibles placed off the safe route, a clear time, or a move/shot count —
  so a solved level still has a better run in it. Keep it optional: it must not gate progress, or
  the puzzle becomes a chore.

### 1.6 Game-state flow (most of a game's shape)
Wrap the loop in a small **state machine** — decide the states up front; it's most of the game's
shape. The DEFAULT shape: **BOOT → TITLE/attract → PLAY → GAME-OVER → (restart)**, plus **PAUSE** if
needed — name the states for *your* game (a puzzle has LEVEL-DONE, a story has SCENE). Keep ONE
`state` variable; each frame branch on it for what you update and draw. How TITLE / the outcome
screen *present* — a HUD line, an attract loop via `Script`, a diegetic title in the world, straight
into play with a hint, a score card — is a design choice (§1.8), not the skeleton's; what they carry
is the name, one line of controls, the best score. The skeleton:

```python
import picogame as pg
import picogame_game, picogame_input, picogame_clock

scene, bufA, bufB = picogame_game.setup()       # engine objects = module globals (built ONCE)
btn = picogame_input.Buttons()
clock = picogame_clock.Clock(30)

TITLE, PLAY, OVER = 0, 1, 2                     # int states: cheaper compares than strings

st = State()                                    # all mutable game state in ONE object (see below);
                                                # State.__init__ sets st.state = TITLE
def new_game():
    st.reset()                                  # score/lives = start; reset positions, clear pools
    btn.clear()                                 # flush the A that started the run - just_pressed
    st.state = PLAY                             #  edges outlive the transition (a phantom jump)

def main():                                     # the per-frame loop lives in a FUNCTION, not module
    poll = btn.poll; pressed = btn.just_pressed  # hoist hot lookups -> locals
    refresh = scene.refresh; tick = clock.tick
    A = btn.A
    while True:
        poll()
        if st.state == PLAY:                    # most-frequent state first
            # ... move, collide, score; on death: ...
            if st.lives <= 0: st.state = OVER
        elif pressed(A):                        # TITLE and OVER: A = (re)start. The `elif` is
            new_game()                          #  LOAD-BEARING: just_pressed is stable for the
        #                                          whole frame, so with a second `if` the A that
        #                                          landed the killing blow would also dismiss the
        #                                          game-over screen before the player saw it.
        refresh()
        tick()

main()                                          # module bottom: kick it off (starts in TITLE)
```
- Engine mapping: build the `Scene` **once and keep it across states** (rebuilding churns RAM); on
  TITLE/GAME-OVER hide gameplay sprites (`visible=False`) and show an overlay on a **fixed (HUD)
  layer** (`picogame_ui`); `picogame_fx.Fade` for clean transitions. Keep the state machine SIMPLE —
  a `state` var + the branches above is enough. Don't build a class with states, transitions and
  enter/exit hooks; don't over-engineer.
- **State storage — rule of thumb:** **hold mutable game state in ONE `State` object** (`st.px`,
  `st.score`; `st.reset()` re-inits in place — a **never-rebound singleton**, so `from x import st`
  stays valid across restarts). A trivial game (≤3-4 vars) can use bare module globals, but the object
  is the default because it's what makes the loop-in-function pattern (below) both **safe** and
  **clean**. Every field documented in `__init__`; no name collisions with sprites/loop vars. Never a
  bare `S={}` dict (string keys are typo-prone + slower). Keep engine objects (Sprites/Tilemap/Canvas/
  pools/`clock`/`btn`/audio) and cross-run/persistent values (NVM best score) as module globals, not in `State`.
- **Name things in words — the game code gets read by a human next.** Whoever picks this up did not
  watch you write it, and one- to three-letter names (`tf`, `n`, `on`, `dx` outside a tight math
  block) force them to re-derive what each holds. Spend the characters: `tile_flags`, `alive`,
  `speed`. **Exceptions, all
  narrow:** the established module aliases (`import picogame_fx as fx`), loop counters (`i`, `x`, `y`),
  and a local `dx`/`dy` next to the arithmetic that defines them.
- **Put the per-frame loop in a FUNCTION, not at module scope** (the skeleton above) — a measured
  perf lever, not style (−33 % logic on device: globals-dict lookups become array-indexed locals;
  hoisted locals faster still), and a safe mechanical wrap as long as state lives in the `State`
  object rather than bare rebound globals. Numbers + the full style guide:
  `engine-capabilities.md` §"Measured hot-loop style guide".

### 1.7 Audio — the cheapest feedback channel
A beep on the key action confirms what the eye is doing and is the best fun-per-byte juice.
- **Minimal SFX set** = main verb + hit/score + pickup + death + menu blip — and
  **`picogame_sfx.Kit` ships exactly this, hardware-tuned**: build once at boot, call `kit.jump()`
  etc. on events, `kit.tick()` once per frame. Reach for it FIRST; on audioless builds it degrades
  to a no-op, no guards needed.
- **Same-frame** as the event; **never audio alone** — always pair with a visual.
- **You have no ears — so the Kit IS the audio plan.** It is pre-tuned and hardware-validated:
  use it and move on; there is nothing to audition, tune or approve. Do NOT design bespoke
  `picogame_synth` voices unless the user asked for them (a held engine/siren tone, music) — the
  sim cannot demonstrate those and you cannot judge them. Never state how anything SOUNDS; when a
  game does carry bespoke audio, list it as unverified, like fun.
- **The sound DESIGN is still yours**: which events are voiced, which Kit voice each gets, and what
  stays silent — a cozy game may want two sounds, a tense one wants silence broken rarely. Write the
  event → voice map in the brief; the Kit is the palette, not the plan.
- Full recipes (chiptune palette, contour semantics, the crisp-not-rich lesson, music guidance):
  **`techniques.md` §Audio recipes**.

### 1.8 Handheld constraints & readability (UX)
The device decides what's possible — design within it:
- **Readability first**: the player, the threats, and the goal must always be findable. Strong
  **figure/ground contrast**; distinguish things by **shape AND colour** (colourblind-fair, and
  clear at small size) — never colour alone. Keep the screen uncluttered. Readability is also
  **identity**: give the player and each threat a distinct **silhouette** (recognizable as a black
  shape) and a small **signature palette** (typically 3–5 hues that *are* the game's look; fewer is
  a style, more needs a reason — one hue is the player, one is danger, the rest is ground; contrast
  by value first) — on this device legibility and visual identity are the same budget, so spend it
  once, deliberately, and *decide* it: palette, silhouettes, HUD placement and how the title
  presents are the "Look & identity" line of the brief, never inherited from the starter template.
- **Few buttons**: map the whole game to D-pad + A/B (+X/Y). Follow muscle memory — **A = confirm /
  primary action, B = cancel / back** (never swap them); X/Y = secondary. Context-sensitive buttons
  over chords; prefer one-button depth where it fits. On a USB-host board (Fruit Jam) a plugged-in
  **USB gamepad works automatically** (`picogame_input` OR-adds it as a source) — design to the same
  D-pad + A/B vocabulary either way.
- **Short sessions**: instant start, instant restart, no long unskippable intros — "pick up for 2
  minutes."
- **HUD** in reserved edge zones (`picogame_ui` fixed layer); tiny, legible.
- **Teach without a manual** — teach by play, not by a screen. One pattern that works, timed to
  your run length: **(1) safe intro** — one input, no threats, discover the controls exist; **(2)
  show it once → require it** — the mechanic fires harmlessly (e.g. a harmless enemy walks into a
  hazard) *before* the player must use it; **(3) contextual hint** — a button icon the first time an
  action unlocks, then gone. Puzzle, narrative and card games onboard by their first level/scene/hand
  instead. No tutorial screen to dismiss; affordances over text.

### 1.9 Scope discipline
The smaller, the more likely it's finished and fun.
- **MVP first**: build the minimum that makes the core loop fun (a vertical slice), then stop and
  feel it before adding. Take a genre's MVP feature set; defer the rest.
- Cut ruthlessly: if a feature doesn't change how the verb feels or what it's worth, drop it. If the
  design doesn't fit (RAM, fun, buttons), **go back and cut** — scope discipline is a feature.

### 1.10 Assets — cheap first
Prototype with **generated shapes** (`picogame_shapes`: circle/rect/ring/poly_frames/tileset_colors)
so you reach fun with no art. Add real art later via `tools/png2picogame.py` (PAL8 = 1 byte/px;
`--dither`, `--dedup` to save RAM). CC0 art (e.g. Kenney) is fine — attribute it. **AI-generated art
(PixelLab.ai), incl. animated sprites** — the full workflow + size floors + the `pg.rgb565` byte-order
gotcha live in `engine-capabilities.md §6` (generate big → downscale → bake; forced palette for cohesion).

### 1.11 The core mechanics every game wires up
Almost every small game is built from this short list — for a first game, this is the checklist of
"parts you'll need." This table maps mechanics → which module; for the **exact method names and
signatures see `engine-capabilities.md` §3 (the single source of truth)** — names below are only
enough to recognize the helper:

| Mechanic | What it is | Use |
|---|---|---|
| **Input → movement** | read buttons, move the player | `picogame_input.Buttons` (`is_pressed`/`just_pressed`; `.clear()` on state changes); move via `spr.x +=`/`spr.fx +=` (sub-pixel). Auto-adds a **USB gamepad and a USB keyboard** on USB-host boards (Fruit Jam) with no code change |
| **Collision / hit** | "did these two touch?" — the heart of most rules | `a.overlaps(b)` (box; `b` = sprite/point/rect) / `a.near(b, r)` (circular), or raw `pg.collide(...)`; on a grid, **which tile-property call depends on where the map came from**: a scene loaded by `picogame_scene` → `view.is_solid(tx,ty)` / `view.tile_has(tx,ty,"name")` (any name the editor painted); a hand-built `pg.Tilemap` → `picogame_tiles` bit flags |
| **Spawning many things** | bullets, enemies, coins, pipes | a fixed **`picogame_pool.Pool`** — never create/destroy sprites per frame (RAM) |
| **Rules: score / lives / win-lose** | the game's economy + end condition | plain Python ints; drive the state machine (§1.6); show via `picogame_ui` HUD |
| **Animation** | walk/idle/explode cycles | step `sprite.frame`, or `picogame_anim` for time-based; bake rotations as frames |
| **A board / level** | maze, bricks, terrain, tiles | `Tilemap` (read/write cells at runtime — eat-grids, destructible terrain) |
| **Camera / scrolling** | world bigger than the screen | `scene.set_view(ox, oy)` follow + clamp; HUD on a fixed layer |
| **Timing** | same speed on any framerate | `picogame_clock.Clock(fps)` → `dt`; `FixedStep` for deterministic physics |

Most first games = input → one verb + one collision rule + one outcome state. Get that loop fun
first (§ workflow), then add animation, juice, and a board.

---

## Part 2 — The references

Don't load everything up front — pull a file only when a step points to it:

| File | Pull it for |
|---|---|
| `engine-capabilities.md` | **the deep engine reference** — every building block and what it COSTS, the helper libs, idioms with code, the RAM budget, the asset pipeline, the sim loop, the example catalog, footguns. How to MAP a design onto picogame. |
| `api-reference.md` | **the full API — exact signatures** for the native C engine (`pg.Sprite`, `Scene`, `Canvas`, `Tilemap`, `StripDraw`, `Canvas.mode7`, `pg.raycast`, …) and every helper lib. Read it when you need a precise call signature (the C engine has no `.py` source to grep). |
| `genre-patterns.md` | **genre playbooks** — core loop, the one thing to get right, controls, tuning, pitfalls, MVP. **Read the "Cross-genre rules" header + only your genre's §:** 1 Breakout · 2 Shmup · 3 Asteroids · 4 Platformer · 5 Top-down/RPG · 6 Maze · 7 Puzzle · 8 Racing · 9 Endless/Arcade · 10 Tower defense · 11 Card/roguelite deckbuilder (also management/tycoon) · 12 First-person raycaster/dungeon crawler · 13 Narrative/dialogue adventure. |
| `debugging.md` | **symptom → first move** triage for typical picogame failures (byte order, stale `.mpy`, `touch()`, pool exhaustion, sim-vs-device gaps, GC churn) + the measurement ladder. Pull the moment something misbehaves — BEFORE guessing. |
| the repo's `docs/` | **the project's own documentation, in the checkout** — ~40 EN pages (plus Czech translations) including the API reference and `concepts/patterns.md`, whose recipes are executable and tested. Nothing here supersedes it; when the two differ, it wins. |
| `techniques.md` | **cross-genre technique recipes** mapped to picogame — state machines, enemy/AI patterns, parallax, collision, procedural generation, palette/raster effects, level authoring, ghosts. |

Templates in `templates/` (pull when the workflow says): `design-brief.md` — fill at step 1, before coding; `starter_game.py` — the skeleton to start step 7 from.

---

## Part 3 — The workflow

*No-repo environments* (web playground, "write me a code.py" chat): write a **single
self-contained file** — no sibling imports, inline art — per the playground contract.

1. **Frame the concept** (§1.0–1.2): who plays, how long, how a run *ends* (win / lose / both), what
   feeling; the one core verb; the loop in one sentence. **1b. Divergence pass** (§1.0b): three
   concepts, one pick, one reason. Fill `templates/design-brief.md`.
2. **Read your genre's grammar** → `genre-patterns.md` (read only your genre's § + the header, see Part
   2): its loop, the one-thing-to-get-right, the universal rules. Decide which MVP items *your* concept
   needs and which it replaces; take the essential input(s), not the whole map; turn one variation
   axis on purpose. Write what you are changing versus the classic. State the twist (§1.0) before building.
3. **Scope for the device** (§1.8–1.9) + the RAM budget in `engine-capabilities.md`.
4. **Choose engine blocks** → `engine-capabilities.md`: Sprite (+ `picogame_pool` for many), Tilemap
   for boards, StripDraw for full-frame effects, Canvas for rarely-changing panels, `set_view` camera,
   `picogame_ui` HUD. For a specific mechanic (**collision/projectiles**, AI, parallax, procedural, ghosts) → `techniques.md`. Collision is the one people re-derive instead of looking up: §5 has the stepped-mover rule (keep the LAST FREE position — that is where anything it spawns goes) and says when `pg.raycast` does and does not apply.
   **Level geometry is DATA — never prose.** The moment a request describes tiles in words ("a ceiling
   just below the HUD", "a wall three quarters of the way up"), stop translating it into coordinates in
   your head: put the map in an **ASCII grid** and show it. `picogame_scene` levels take
   `"legend": {".": 0, "#": 1}` + `"rows": ["....", "####"]` as a first-class alternative to the
   editor's int grid (identical after baking) and `techniques.md §8` does the same for a plain Tilemap.
   Then the geometry is visible to both of you: the user answers "that column, not that one" instead of
   re-describing, and the diff of a level change is a picture. For a big scrolling world the user can
   paint it in the **scene editor** (`tools/editor/` in the public repo; hosted at /editor/ on the docs site) and hand you the exported `scene.json` — which the editor
   can also re-open, so a level can go back and forth. It is turn-taking, not merging: say who is
   holding the file (see `techniques.md §8`).
5. **Plan assets cheap** (§1.10): generated shapes first — but decide the **look** (§1.8: palette,
   silhouettes, HUD placement, title presentation) *now*, in the brief, so the placeholders in
   `starter_game.py` get replaced rather than shipped.
6. **Structure the loop + state flow** (§1.6): set the state machine and the per-frame loop before
   layering rules.
7. **Build in the simulator** (start from `templates/starter_game.py`): core loop on screen FIRST,
   confirm with a screenshot, then add rules.
   **Starting from a shipped example instead?** (`demos/`, `games/`, a tutorial step — the usual way a
   jam starts.) **Copy it to a new file named for YOUR game and work there; never edit the example in
   place.** The user's starting point has to stay runnable so they can diff against it and fall back to
   it, and an example is also the reference other games are read against. If you do need a snapshot,
   put it next to the game (`my_game.py.orig`), never in `/tmp` — the user has to find it without you.
   ```sh
   python3 sim/run.py examples/my_game.py --frames 80 --hold RIGHT,A --shot /tmp/shot.png  # headless
   # --frames/--keys/--shot-at count GAME frames (one per clock.tick()), so a --keys timeline
   # lines up with your loop iterations no matter how often a frame presents.
   # --seed N        makes a run REPEAT (fixes picogame_rand + random) - required to compare two
   #                 screenshots, or to reproduce a difficulty complaint.
   # --tap A:30      taps a button for the whole run. A soak needs it: --hold A presses ONCE and
   #                 never releases, so a game whose restart is just_pressed(A) sits on its
   #                 game-over screen for 94% of the 3600 frames and proves nothing.
   # --strict-dirty  honours each always_dirty=False StripDraw's dirty bit, so a content change
   #                 you forgot to invalidate() FREEZES here as it does on device. Run it once
   #                 before you call a StripDraw-heavy UI done.
   # a BUTTON-driven feature: script the press instead of reasoning about it (FRAME:BTN[:HELD])
   python3 sim/run.py examples/my_game.py --keys "5:RIGHT,25:B:3" --shot-at 30 --shot /tmp/jump.png
   # live window FOR THE USER to actually play (don't run it yourself — you won't see it):
   python3 sim/run.py examples/my_game.py --backend pygame
   ```
   `--hold` presses for the whole run (movement); `--keys` is a timeline, so a *tap* (what
   `just_pressed` reads: shoot, jump, confirm) is testable — `40:X:2` taps X for 2 frames at frame 40.
   A bare `40:X` (no duration) HOLDS X until `-X` or the end of the run, and a second press on a
   button still held is not an edge (the sim warns) — write `40:X:2` for a tap, `40:X,60:-X` for a hold.
   Shoot at a screenshot a few frames later and you can SEE whether the feature fired. Never report a
   button-driven feature as verified from a run that never pressed the button.
8. **Feel & fairness pass** (§1.3–1.5, 1.7): add the feedback the fantasy calls for — pick from the
   §1.3 menu and say what each touch expresses (a touch you cannot justify is noise) — then make it
   fair (telegraphing, your genre's generosity mechanic, instant restart), then the return hook that
   fits (§1.5).
9. **Validate against the quality bar** (below) in the simulator.

---

## Quality bar (be self-critical — iterate until ALL hold)

Split by who can check it. **Self-certify the machine-verifiable items** below; **fun and feel you
CANNOT confirm from a static frame — surface those to the human, don't rubber-stamp them.** Declaring
"fun: done" off a screenshot is the failure mode to avoid.

**Machine-verifiable — the agent confirms these (sim run + screenshot + RAM estimate):**
1. **Runs clean** — N frames in the sim with no exception (`sim/run.py … --frames N`), not just
   "imports." Then a **`--frames 3600`** run must also finish clean — it catches the crashes
   a short run hides: an unbounded list, a pool that fills, a state the game only reaches after
   minutes. It does NOT catch per-frame *churn* (CPython's GC hides same-frame garbage that the
   device's non-moving heap would fragment — `engine-capabilities.md §5`), so read the hot loop for
   allocations too; `--profile` reports RETAINED growth only. A headless run skips the frame sleep
   by default (`dt` still reads the nominal 1/fps, so the game behaves identically), so the soak
   costs compute, not two minutes of waiting — and the same `--seed` reproduces the same frame.
2. It **reads at a glance** in the PNG — *name* the player's shape+colour and each threat's from the
   shot alone; if you can't tell them apart by **shape AND colour** (not colour alone), it fails. HUD legible.
   This applies to **every object you just added**, not only the player: find it in the shot and check
   it stands out from *the background it actually sits on*. "Present in the frame" is not the bar —
   a blue thing on a blue sky renders perfectly and is invisible, and the user will notice before you do.
3. It controls cleanly on **D-pad + A/B**; nothing needs a manual. Keep a **control manifest** — one
   row per button, what it does in each state, and what is deliberately unbound — and make it the
   input test plan: **every row gets fired via `--keys` and a screenshot**, so input coverage is
   systematic instead of "the ones I thought of". The unbound rows matter as much: they are where the
   next feature goes, and stating them stops the "A and X do nothing, or was it X and Y?" fumbling.
   ```
   btn   title      play              over     | UP/DOWN  -  aim      -     (unbound: A, Y)
   A     start      -                 restart  | LEFT/RGT move       move
   B     -          jump              -        | X        -  shoot   -
   ```
   Then drive the `--hold` edge cases: hold-fire 300 f (pool must not exhaust), idle (title must not
   crash), `LEFT,RIGHT` (no NaN/escape), A on frame 1.
4. Clean **game flow** — an entry state, play, an outcome state and a **fast way back in**, named
   for your game (§1.6). Prove it with a 3-shot sequence (`--shot` entry → `--hold A` play →
   `--shot-at <outcome>` outcome) showing *distinct* states — execution evidence, not just code
   that compiles.
5. It **fits the RAM target** (RP2040 is the primary budget; RP2350/Fruit Jam only adds slack) and uses
   `rgb565()` / `sprite.touch()` correctly. **Measure, don't estimate** — with the right tool for
   each environment:
   - **In the sim** (where you build): compute the asset RAM budget statically (bitmap bytes — see
     the RAM-budget § in `engine-capabilities.md`) and run `sim/run.py game.py --profile` — it prints
     a report of the game's/libs' retained allocations after warm-up. Allocation growing with frame
     count = a leak = a blocker.
   - **On the device**: `dbg.ram("tag")` from `picogame_debug` (after `dbg.enabled = True`) at frame
     10 and frame N/2 — a heap shrinking across the run is a blocker (free ≠ largest contiguous
     block); plus a `picogame_debug.Watch(scene)` FPS/FREE overlay. In the sim `dbg.ram` is silent
     (CPython has no `gc.mem_free`; it prints numbers only under `PYTHONTRACEMALLOC=1`, and even then
     they're CPython allocations — good for deltas/leaks, not an absolute budget). (Don't hand-roll a
     `gc.mem_free` guard — that's what `picogame_debug` is.)
6. The code is **≈ one example's length** (not a sprawling engine), commented like the examples, and starts from `picogame_game.setup()`.

**Human-verifiable — a single frame can't prove these; hand them to the player:**
- The **core loop is fun in the first 10 seconds** ("one more go"), not just "technically runs."
  *(Slower genres — puzzle, RPG, tower defense, card/roguelite — read "10 seconds" as **hooked/
  curious**, not **scoring**, and "instant restart / 1–3 min run" as a session shape that fits the
  genre, not a literal arcade timer. Don't warp a deckbuilder toward twitch pacing to satisfy the bar.)*
- The **feedback touches you chose** land and **difficulty feels fair** (telegraphing + a generosity mechanic).

**Hand these over as five questions, not as "is it fun?"** — an open ask gets "it's fine", which tells
you nothing and leaves you guessing. Each question targets a bar item above, so the answer is
actionable:
1. What did you try FIRST, without being told? *(legibility — §1.1)*
2. Where did you die, and did it feel like your fault? *(fairness — §1.4)*
3. What did you stop noticing after a while? *(dead or over-used feedback — §1.3)*
4. Did you want another go, and why? *(the hook — §1.5)*
5. One thing you'd change?

Report what came back verbatim before acting on it, and change ONE thing per round — with five
answers in hand it's tempting to fix everything at once and lose track of which change did what.

**The fun-proxy** (the strongest machine-checkable stand-in until a human plays — verify ALL five
and report them as the proxy, never as "fun confirmed"): (1) legible in ≤10 s from a screenshot,
(2) input acts the SAME frame it's read, (3) restart < 0.5 s, (4) every threat telegraphed ≥ 8 frames,
(5) a stated ramp shape with its first spike at a time you chose from your loop length — and one
sentence why.

To *infer* motion before handing off, drive `--shot-at` across several frames — the live window
(`--backend pygame`) you can neither launch nor see yourself; offer it to the USER so they can
actually play, and get the fun/feel verdict from them. Hand off with **numbers, not vibes** — a short list:
- **feedback chosen**: which touches (and their parameters: flash frames, shake `max_off`, hit-stop
  frames …) and what each expresses;
- **generosity mechanic** + its frame count;
- **difficulty ramp**: shape + spawn/speed curve + when the first threat and the first spike land —
  **flag any reaction window < 8 frames**;
- if it seeds `picogame_rand.Rand(seed)`: a fixed seed + `--hold` gives a reproducible run to judge difficulty.

---

## Case studies

Worked examples of the whole loop (racing ×2, endless-arcade Starfall — what the sim screenshots
revealed and what changed): **`references/case-studies.md`**. Load only when you want a modelled
end-to-end pass; the workflow above is self-sufficient. Their choices are those games' answers to
Part 1, not the method's defaults.
