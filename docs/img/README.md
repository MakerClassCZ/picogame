# FEATURES.md illustrations

Screenshots used in `../../FEATURES.md`, rendered from the simulator (320x240).
Regenerate any with (the sim chdir's to the script's dir, so use an absolute --shot path):

    PYTHONPATH="examples:lib:sim" python sim/run.py docs/img/gen_transforms.py \
        --frames 2 --shot "$PWD/docs/img/transforms.png"

- stripdraw.png        <- examples/picogame_stripdraw_demo.py
- transforms.png       <- gen_transforms.py   (runtime angle + scale)
- background_noise.png <- gen_background_noise.py
- particles.png        <- gen_particles.py    (shot at frame 9, after a few ticks)
- tilemap.png          <- gen_tilemap.py
- hud_bars.png         <- gen_hud_bars.py     (§9: the four status-bar approaches stacked)
- asset_storage.png    <- gen_asset_storage.py (§15: relative heap cost of the three tiers)

Text / UI widgets (used on `/helpers/text-ui/`), each rendered with `--frames 3` unless noted:

- ui_label.png         <- gen_ui_label.py     (picogame_font.Label - immediate HUD text; render with `--frames 8`)
- ui_bitfont.png       <- gen_ui_bitfont.py   (picogame_bitfont - outlined/transparent text over a scene)
- ui_hudbar.png        <- gen_ui_hudbar.py    (picogame_ui.HudBar - reserved edge status bar, score + icons)
- ui_dialog.png        <- gen_ui_dialog.py    (picogame_ui.SceneBox - bordered multi-line dialog box)
- ui_menu.png          <- gen_ui_menu.py      (picogame_ui.SceneMenu - cursor menu with selection cursor)
- ui_options.png       <- gen_ui_options.py   (picogame_options.OptionsMenu - editable settings rows)

## Animated showcase GIFs (gameplay / capture)

Unlike the `gen_*.py` stills above, these are **captured gameplay** recorded from the simulator
with the sim->GIF harness (runs a game headless, drives the controller, subsamples frames, encodes an
animated GIF). They are a universal set for the docs site, the GitHub README, and the chiptron.cz
article. All are 320x240. Recorded via `tools/gen_gif.py GAME OUT --script SCRIPT.py --frames N
--start F --every K --fps N`; large photographic gifs post-shrunk with an ffmpeg shared palette.

The `game_*.gif` are driven by a **scripted input recipe** `sc_<name>.py` (co-located here) rather than
a single held button: each defines `def play(pad)` — a `picogame_seq` generator that presses/releases
buttons over frames (`pad.hold`, `pad.tap`, `pad.rest`), so the clip shows realistic play (a submarine
that hunts and turns back before the wall, a car that corrects instead of spinning off, a runner that
jumps on a rhythm) instead of a button held constant. Read each game's control scheme from the header
docstring of `games/picogame_<name>.py` before editing a recipe. Paths must be **absolute** (the harness
chdir's into the game's directory).

A few clips instead use a **closed-loop** driver `ctl_<name>.py` (run with `--control` not `--script`):
`def control(g, fr, pad, st)` is called each frame with the game's live module globals `g` (READABLE — the
state machine, sprites, pools, heat) and sets the held buttons directly with `pad.set("A,LEFT")`, so it
reacts to what the game is actually doing rather than firing blind on a timer. Use this when the play has
to HIT a moving target or follow the game's state (`ctl_picoracer.py` steers to stay on the tarmac;
`ctl_picowing.py` locks + kills raiders; `ctl_starcluster.py` sequences market -> map -> combat by
`g["state"]`). Single-frame button pulses generate the menu's `just_pressed` edges; held keys feed
`repeat` (market buy/sell).

### The gameplay-GIF standard (2026-07-21)

All 16 `game_*.gif` are rendered to ONE consistent standard so the set reads as a family:

- **Capture `--every 2`, play `--fps 30`** → 60-66 ms/shown-frame. Each shown frame = 2 sim-frames of
  motion at the sim's 30 fps, i.e. **real-time and smooth** (NOT the old choppy every-3-then-played-slow look).
- **Length ~6-7 s** = ~180-210 CAPTURED sim frames after the start point (so `--frames = start + ~196`).
  Each `sc_<name>.py` was extended to run that long with **calm, deliberate motion** (longer holds, fewer
  rapid direction flips).
- **Size < ~400 KB.** Most games encode small as-is. `game_pictor.gif` (photographic full-screen parallax,
  near-incompressible) is the sole exception: it uses **`--every 4 --fps 30`** (~133 ms/frame, still
  real-time, slightly choppier) plus a gifsicle 24-colour `--lossy=500` pass to land at ~377 KB — even
  `--every 3` at 16 colours could not get under 400 KB without ugly sky banding.
- Puzzle/turn games (conduit, flatline, picatro, picotris, train) show **fewer stored frames** than the
  action games: PIL's `optimize=True` collapses identical consecutive frames and extends their duration,
  so a static "thinking" hold becomes one long-duration frame. Total playback is still ~6-6.5 s.

Two games are stochastic (RNG seeded from OS entropy, so each run differs) and are captured with a
retry-until-clean loop: **dinorun** (dense hop rhythm; re-run until no crash white-flash appears, so it
never shows GAME OVER) and **bangbang** (AI-vs-AI DEMO duel; re-run until the duel fills the whole clip
with no static "P2 WINS" hold — proxy: ~95+ stored frames, max single-frame hold ≤200 ms).

Flagship gameplay (`game_*.gif`), each driven by its `sc_<name>.py` script (standard `--every 2 --fps 30` unless noted):

- game_pictor.gif       <- games/picogame_pictor.py       + sc_pictor.py       (`--start 6 --every 4 --fps 30 --frames 202`; run RIGHT with timed UP jumps + A shots, then turn around LEFT; parallax meadow platformer; re-encoded gifsicle 24-colour `--lossy=500` — the ONE game forced off the every-2 standard to fit under 400 KB)
- game_picowing.gif     <- games/picogame_picowing.py     + **ctl_picowing.py** (CLOSED-LOOP `--control`; `--start 84 --frames 284`; the old scripted glide MISSED every raider — this reads the live globals (`st`, `plane`, `enemies`) and actually PLAYS: locks the nearest raider above the ship, slides under it, and autofires on a `st.heat`-aware duty cycle so shots CONNECT — raiders explode, chain + score climb 0->300, gun never overheat-locks. Window starts at the first raider spawn to skip the ~2 s of empty sky)
- game_picobike.gif     <- demos/picogame_picobike_hill.py + ctl_picobike.py (CLOSED-LOOP; `--start 20 --frames 216`; throttle held, climbs gears (A) for racing speed, steers st.lateral->0 to hold the winding pseudo-3D road; OutRun-style StripDraw racer)
- game_wyrmfall.gif     <- review/wyrmfall/picogame_wyrmfall_game.py (REAL flagship, dark palette). ASSET FIX (permanent): scenes/scene_pal.py 39->40 colours. Capture toggles (temp, reverted): AUTOPLAY=True + AUTO_SKIP=(0,) + movement DEADZONE (skip an axis within SPEED, else it sways) + town wants-visit->True (so the hero WALKS to the village) + the interaction dispatch excludes town under AUTOPLAY (so it does NOT auto-rest = NO hearth cutscene, just HOLDS at the village with the 'A: rest' prompt). `--start 20 --every 3` -> PIL walk + hold the rest-prompt frame -> `convert -colors 32 -fuzz 6%` -> ~123 KB. Ends on the overworld 'A: rest (mend the band)' dialog box.
- game_picoracer.gif    <- games/picogame_picoracer.py    + ctl_picoracer.py (CLOSED-LOOP; `--start 48 --frames 284`; countdown -> RACES: wide-fan road.at_px steering reads the 90-degree corners; throttle floors the straights (~4.7) and brakes into corners (~2.2) then accelerates out — a racing accelerate/brake-turn rhythm, 100% on-road)
- game_corona.gif       <- games/picogame_corona.py       + sc_corona.py       (`--start 14 --frames 210`; A clears the title, then roam a slow RIGHT/DOWN/LEFT/UP lap so the torch light sweeps + one X dash per lap; torch-lit dark survival)
- game_squest_full.gif  <- games/picogame_squest_full.py  + sc_squest_full.py  (`--start 6 --frames 202`; A begins play, dive DOWN off the surface, swim RIGHT firing one B torpedo at a time, weave, turn back LEFT before the wall — two laps)
- game_dinorun.gif      <- games/picogame_dinorun.py      + sc_dinorun.py      (`--start 4 --frames 200`; dense UP hop rhythm keeps the dino airborne; STOCHASTIC — retry until a run has no crash white-flash so it never ends on GAME OVER)

Remaining game set (`game_*.gif`), same `sc_<name>.py` recipe (standard `--every 2 --fps 30`). NOTE: several boot through a `title_splash()` that AUTO-HOLDS ~90 frames in headless runs — for those the script begins with `pad.rest(95)` and capture uses `--start 96`, else the scripted taps are eaten by the splash:

- game_bangbang.gif     <- games/picogame_bangbang.py     + sc_bangbang.py     (`--start 4 --frames 200`; X starts DEMO mode = AI-vs-AI auto-duel — barrels aim, shells arc, terrain craters + shake; STOCHASTIC — retry until the duel fills the clip with no static P2-WINS hold)
- game_boxshmup.gif     <- games/picogame_boxshmup.py     + sc_boxshmup.py     (`--start 12 --frames 208`; A clears the 1-bit title, then D-pad weaves + A fires cannons over the scrolling noise terrain, picowing-style; + --setup neuter_watch.py to HIDE the shipped FPS/FREE-RAM Watch overlay for a clean capture)
- game_cavern.gif       <- games/picogame_cavern.py       + sc_cavern.py       (`--start 4 --frames 200`; boots straight in; LEFT/RIGHT run, UP hop between platforms, B blow orbs at the robots)
- game_conduit.gif      <- games/picogame_conduit.py      + sc_conduit.py      (`--start 4 --frames 200`; A enters build board B1, A opens the transistor gate, B POWERs -> current floods VCC->LED, LED lights, then on to the AND board)
- game_flatline.gif     <- games/picogame_flatline.py     + sc_flatline.py     (`--start 4 --frames 200`; D-pad moves the probe, A measures each node H/L/F — probe count ticks down — Y accuse a part + confirm the failure -> REVEAL -> new board, then probe again)
- game_picatro.gif      <- games/picogame_picatro.py      + sc_picatro.py      (`--start 4 --frames 200`; A dismisses the how-to, UP selects cards along the L/R cursor, A PLAY runs the chips x mult SLAM tally, A continue, then a second hand)
- game_picotris.gif     <- games/picogame_picotris.py     + sc_picotris.py     (`--start 4 --frames 200`; boots straight in; A rotate, L/R move, DOWN soft-drop — places several pieces so the well fills)
- game_salvo.gif        <- games/picogame_salvo.py        + sc_salvo.py        (`--start 96 --frames 292`; rest(95) past the title splash; PLAN: A builds Sentinels along the row, Y releases the wave; then the enemy bloom flows the path while towers auto-fire)
- game_starcluster.gif  <- games/picogame_starcluster.py  + **ctl_starcluster.py** (CLOSED-LOOP `--control`; `--start 8 --frames 204`; the old clip was almost all combat — this one LEADS WITH THE TRADE and keeps combat a short tail, sequenced by `g["state"]` at ~40% market / ~35% map / ~25% combat: dock at Vetis and BUY a run of FOOD then SELL it back (cargo + credits visibly move), B to the galaxy MAP and tour the node network (UP Fepha / LEFT Vetis / DOWN Raron, risk-lit links), then A jumps Vetis->Raron — a "!!" DANGER hop that on day 1 is a GUARANTEED ambush (precomputed from the deterministic galaxy seed) — for a brief cockpit crosshair-sweep-and-fire tail, ending before the victory banner)
- game_train.gif        <- games/picogame_train.py        + sc_train.py        (`--start 96 --frames 292`; rest(95) past the splash; the loco auto-moves ~1 tile / ~14 frames, hold RIGHT to eat the row-5 items then DOWN + LEFT to sweep row 8 — the train grows + score climbs; no 180-degree turns or it self-crashes)

Engine-capability gifs (`cap_*.gif`, complement the existing fx_* set: camera/fade/invertflash/palette/particles/shake/tween):

- cap_tilemap.gif       <- examples/picogame_scroll_demo.py  (`--start 4 --every 3 --hold UP,LEFT`; scrolling tilemap world larger than the screen, camera follows)
- cap_transforms.gif    <- scratchpad/anim_transforms.py     (runtime per-sprite angle + scale animated over time; throwaway sim script based on gen_transforms.py)
- cap_stripdraw.gif     <- examples/picogame_stripdraw_demo.py (0-RAM StripDraw pseudo-3D road + sky gradient, animated curve)

Hero reel:

- hero.gif              <- PIL concat of game_*.gif slices at 66 ms/frame, ending on the Wyrmfall village scene (order: picoracer, picobike, picowing, boxshmup, squest_full, corona, picatro, train, dinorun, wyrmfall[walk->village, LAST]); ~349 KB, ~11 s.
