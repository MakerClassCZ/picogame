# Design brief — <game name>

Fill this in BEFORE writing code. If you can't fill a line, the design isn't ready — keep cutting
or deciding until you can. (Workflow steps 1–4 in SKILL.md.)

## 1. Concept (design backward from a feeling)
- **Who plays & for how long:** <e.g. anyone, 1–3 minute runs on the handheld>
- **Fantasy (what the player gets to BE — pick before the verb):** <e.g. star-catcher / short-order cook>
- **Target feeling (MDA aesthetic):** <e.g. tense reflexes / cozy puzzle / speed thrill>
- **Core verb (one):** <bounce / dodge / jump / steer / match / shoot>
- **Core loop in ONE sentence:** <e.g. "dodge falling rocks, grab gems, survive as it speeds up">
- **Identity — "It's $GENRE, and also ___":** <the ONE twist that earns the clone>
- **Anti-pillars (what this game is NOT):** <1–2 lines guarding scope & tone>

## 2. Genre & grammar
- **Genre:** <Breakout / shmup / platformer / racer / puzzle / endless …>
- **The one thing to get right (from genre-patterns.md):** <e.g. the jump arc / the paddle angle trick>
- **MVP features (build these):** <3–5 bullets>
- **Deferred (nice-to-have, cut for now):** <bullets>

## 3. Fits the device?
- **Target board / RAM:** <RP2040 ~138 KB | RP2350 ~520 KB>
- **Controls (D-pad + A/B/X/Y):** <map every action>
- **Moving-object budget:** <static bg + how many moving sprites>
- **Readability:** <how the player / threats / goal stay findable on 320×240>

## 4. Engine building blocks
- **Surfaces:** <Sprite(s) / Tilemap / StripDraw / Canvas — and why>
- **Helpers:** <picogame_pool / picogame_ui / picogame_audio / picogame_save …>
- **Camera:** <fixed screen | set_view follow>
- **Assets:** <generated shapes first | real art via png2picogame>

## 5. Juice & difficulty plan
- **Feedback on the key action:** <flash / particle / beep>
- **Difficulty ramp (give it a shape):** <sawtooth — build → release at a milestone → re-engage ~10–15% harder; first spike ~60–90s; how it stays fair>
- **Restart:** <instant on death?>

## 6. Done when (quality bar)
- [ ] Core loop is fun in the first 10s (verified in sim)
- [ ] Reads at a glance · clean on few buttons
- [ ] One juice touch · fair difficulty
- [ ] Fits RAM target · uses rgb565()/touch() correctly
- [ ] Small, commented, starts from picogame_game.setup()

## Device budget (fill BEFORE coding — the design must prove it fits)

- Target board / resolution: (default RP2040 PicoPad 320×240; read `picogame_game.screen()` anyway)
- Target FPS: (30 default; 40 only with a measured frame budget)
- Asset RAM estimate: (bitmap bytes summed — PAL8 = w×h per frame; budget vs ~138 KB heap)
- Max simultaneous entities: (pool sizes; who despawns them)
- Camera: (static screen / `set_view` scroll — scroll = full-screen recomposite each frame)
- Full-frame StripDraw effects: (any `always_dirty=True`? that + scroll + many sprites = RED FLAG,
  bench first — see engine-capabilities §9)
- Save/persistence: (none / NVM best-score via `picogame_save`)
- Sound: (Kit only / bespoke synth → needs WAV preview + user approval)
- Hardware-verified items: (what MUST be checked on the real device before "done" — colors on the
  panel, audio, input feel)
