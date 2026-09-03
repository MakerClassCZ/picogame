# Design brief — <game name>

Fill this in BEFORE writing code. If you can't fill a line, the design isn't ready — keep cutting
or deciding until you can. (Workflow steps 1–4 in SKILL.md.)

## 1. Concept (design backward from a feeling)
- **Who plays & for how long:** <who, session length, and how a run ENDS — win / lose / both>
- **Fantasy (what the player gets to BE — pick before the verb):** <one line — what will they brag about?>
- **Target feeling (MDA aesthetic):** <name the emotion, not the genre>
- **Core verb (one):** <one word — the thing the player does most>
- **Core loop in ONE sentence:** <verb + what it acts on + what ends it>
- **Concepts considered (3) and why this one (§1.0b):** <three one-liners; the pick + the reason it beat the other two>
- **Identity:** <what makes this game NOT the nearest existing one — "It's $GENRE, and also ___" or "It's ___, played through $VERB">
- **Anti-pillars (what this game is NOT):** <1–2 lines guarding scope & tone>

## 2. Genre & grammar
- **Genre:** <one of genre-patterns.md's sections … or your own § written here (see its header)>
- **The one thing to get right (from genre-patterns.md):** <e.g. the jump arc / the paddle angle trick>
- **Variation axis turned on purpose:** <which knob, and what it is set to>
- **MVP features (build these):** <3–5 bullets — the least that proves YOUR loop, not the classic's spec>
- **Deferred (nice-to-have, cut for now):** <bullets>

## 3. Fits the device?
- **Target board / RAM:** <RP2040 ~138 KB | RP2350 ~520 KB>
- **Controls (D-pad + A/B/X/Y):** <map every action>
- **Moving-object budget:** <static bg + how many moving sprites>
- **Readability:** <how the player / threats / goal stay findable on 320×240>
- **Look & identity (§1.8):** <palette (which hue is the player, which is danger), silhouettes, HUD placement, how the title/outcome screens present — decided, not inherited from the starter>

## 4. Engine building blocks
- **Surfaces:** <Sprite(s) / Tilemap / StripDraw / Canvas — and why>
- **Helpers:** <picogame_pool / picogame_ui / picogame_audio / picogame_save …>
- **Camera:** <fixed screen | set_view follow>
- **Assets:** <generated shapes first | real art via png2picogame>

## 5. Juice & difficulty plan
- **Feedback (§1.3 is a menu):** <which touches, on which events, and why each fits the feeling — a touch you can't justify is noise>
- **Sound design:** <event → Kit voice map; what stays silent>
- **Difficulty ramp (give it a shape):** <name the shape · when the first spike lands and why (from YOUR loop length) · how it stays fair>
- **Restart:** <instant on death?>

## 6. Done when (quality bar)
- [ ] Fun-proxy (5 items) reported · the 5 human questions handed over — fun itself is NOT claimed
- [ ] Reads at a glance · clean on few buttons
- [ ] The chosen feedback touches land · fair difficulty
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
