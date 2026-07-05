# PicoRacer — Race Your Own Ghosts

A top-down arcade racer for the PicoPad. Drive 5 laps of one circuit and beat your own best lap —
while ghost replays of your earlier laps chase you around the track. **Your only rival is yourself.**

---

## English

### Goal
Finish a **5-lap** race and set the fastest **lap time** you can. There are no AI opponents — the
cars you race are **ghosts**: exact replays of your own earlier laps. Beat blind luck, beat the
corners, beat your past self.

### Controls
Works on any board with a D-pad + **A** and **B** (no X/Y needed).

| Input | Action |
|---|---|
| **←/→** | steer left / right |
| **B** | gas — accelerate up to top speed |
| **A** | brake; keep holding to **reverse** |
| **B** | START the race / race **AGAIN** (on the title & finish screens) |

Lift off **B** to coast — the car sheds speed on its own, which is often all you need to settle into a
corner.

### A race, lap by lap
1. Press **B** on the title screen. A **3 · 2 · 1 · GO!** countdown starts you on the bottom straight.
2. Drive the circuit **counter-clockwise**. The HUD shows **LAP x/5**, your **current lap time**, and
   your **BEST** lap so far.
3. A lap only counts when you do it properly: first reach the **checkpoint** at the far **left** of
   the track, *then* cross the **finish line** on the bottom straight **driving the right way**
   (rightward). This stops you from racking up laps by rolling back and forth over the line.
4. Cross the line and a **chime** plays, the lap banner pops up, and the next lap begins.
5. After **5 laps** the race ends: the finish banner shows your **total time** and **best lap**.
   Press **B** to race again.

### The ghosts — you race yourself
Every lap you complete is **recorded** and played back as a coloured **ghost car** on the following
laps:

| You finish… | …and this ghost joins |
|---|---|
| Lap 1 | 🔵 blue ghost of lap 1 |
| Lap 2 | 🟢 green ghost of lap 2 |
| Lap 3 | 🟡 yellow ghost of lap 3 |
| Lap 4 | ⚫ black ghost of lap 4 |

- You always drive the **red** car, drawn on top of the ghosts.
- Each ghost is the **exact line you drove** on that lap, looping around the track. It re-syncs to the
  start line each new lap so it always sets off with you.
- By the **final lap** all **5 cars** are on track at once — you plus four ghosts of laps 1–4.
- A ghost is a moving benchmark: a clean lap gives you a fast ghost to chase; a messy lap gives you an
  easy one to overtake.

### Handling & the track
- **Acceleration is gradual** — hold **B** to build up to top speed; you don't snap to full pace.
- **Grip falls at speed.** At low speed the car turns sharply; near top speed the steering weakens
  (**understeer**), so **lift off or brake** to rotate through tight corners.
- **Grass punishes you.** Run off the tarmac and the grass caps your speed low and drags you down —
  keep it on the road to keep your pace.
- **Reverse** with **A** if you spin or clip a wall and need to back up and line the corner up again.

### The best-lap flash
Beat your fastest lap and the game celebrates: your car **blinks white** for a moment and the lap
banner reads **BEST!**. Chasing that flash lap after lap is the whole game.

### Tips
- Smoothness beats mashing the gas — a clean, connected line is faster than braking into every corner.
- Coast (lift **B**) into corners instead of braking; one lift usually clears a 90° bend.
- Your lap-1 ghost is your first pace car — try to *stay ahead of it* on lap 2.
- Don't fight the grass. If you run wide, ease off, get back on tarmac, then get back on the gas.
- On the last lap, weave through your own ghosts — they follow fixed lines, so you can plan overtakes.

---

## Česky

### Cíl
Dojeď **5kolový** závod a zajeď co nejrychlejší **čas kola**. Nejsou tu žádní počítačoví soupeři —
auta, se kterými závodíš, jsou **duchové**: přesné záznamy tvých vlastních dřívějších kol. Poraz
náhodu, poraz zatáčky, poraz sám sebe z minula.

### Ovládání
Funguje na jakékoli desce s D‑padem + **A** a **B** (X/Y netřeba).

| Vstup | Akce |
|---|---|
| **←/→** | zatáčení vlevo / vpravo |
| **B** | plyn — zrychluj až na maximum |
| **A** | brzda; drž dál pro **couvání** |
| **B** | START závodu / jet **ZNOVU** (na úvodní a cílové obrazovce) |

Pusť **B** a auto vybíhá — samo ztrácí rychlost, což často stačí k usazení do zatáčky.

### Závod, kolo po kole
1. Na úvodní obrazovce stiskni **B**. Odpočet **3 · 2 · 1 · GO!** tě odstartuje na spodní rovince.
2. Jeď okruh **proti směru hodinových ručiček**. HUD ukazuje **LAP x/5**, aktuální **čas kola** a tvé
   dosavadní **BEST** (nejlepší) kolo.
3. Kolo se počítá jen když ho projedeš správně: nejdřív dosáhni **checkpointu** úplně **vlevo** na
   trati, *teprve pak* projeď **cílovou čárou** na spodní rovince **správným směrem** (doprava). Tím se
   zabrání sbírání kol popojížděním tam a zpět přes čáru.
4. Po projetí čáry zazní **zvonění**, objeví se banner kola a začne další kolo.
5. Po **5 kolech** závod končí: cílový banner ukáže tvůj **celkový čas** a **nejlepší kolo**. Stiskni
   **B** pro nový závod.

### Duchové — závodíš sám se sebou
Každé dokončené kolo se **nahraje** a přehraje jako barevné **auto‑duch** v následujících kolech:

| Dojedeš… | …a přidá se tento duch |
|---|---|
| Kolo 1 | 🔵 modrý duch kola 1 |
| Kolo 2 | 🟢 zelený duch kola 2 |
| Kolo 3 | 🟡 žlutý duch kola 3 |
| Kolo 4 | ⚫ černý duch kola 4 |

- Ty vždy řídíš **červené** auto, vykreslené přes duchy.
- Každý duch je **přesná stopa, kterou jsi jel** v daném kole, a točí se dokola po trati. Na začátku
  každého nového kola se srovná se startovní čárou, takže vyráží spolu s tebou.
- V **posledním kole** je na trati všech **5 aut** naráz — ty plus čtyři duchové kol 1–4.
- Duch je pohyblivé měřítko: čisté kolo ti dá rychlého ducha na dohánění, odbyté kolo snadného na
  předjetí.

### Jízdní model & trať
- **Zrychlení je pozvolné** — drž **B** a nabírej rychlost; na maximum nevyskočíš okamžitě.
- **Přilnavost klesá s rychlostí.** Při nízké rychlosti auto zatáčí ostře; blízko maxima řízení
  slábne (**nedotáčivost**), takže **pusť plyn nebo brzdi**, abys projel ostré zatáčky.
- **Tráva trestá.** Když sjedeš z asfaltu, tráva ti srazí rychlost na minimum a brzdí tě — drž se na
  trati, ať držíš tempo.
- **Couvání** přes **A**, když se roztočíš nebo škrtneš o mantinel a potřebuješ se vrátit a znovu
  najet do zatáčky.

### Blik za nejlepší kolo
Překonej své nejrychlejší kolo a hra to oslaví: auto na chvíli **zabliká bíle** a banner kola napíše
**BEST!**. Honit ten blik kolo za kolem je celá hra.

### Tipy
- Plynulost vítězí nad mačkáním plynu — čistá, spojená stopa je rychlejší než brzdit do každé zatáčky.
- Do zatáček spíš vybíhej (pusť **B**) než brzdi; jedno puštění obvykle projede 90° zatáčku.
- Tvůj duch z 1. kola je tvé první tempo — v 2. kole se snaž *zůstat před ním*.
- Nebojuj s trávou. Když sjedeš, uber, vrať se na asfalt a teprve pak zase přidej.
- V posledním kole se proplétej vlastními duchy — jezdí pevné stopy, takže si předjetí naplánuješ.
