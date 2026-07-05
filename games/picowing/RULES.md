# Pico Wing

A vertical shmup for the PicoPad. Hold the sky against raiders falling from above, build a kill-chain
multiplier, and don't let anything slip past you. **Your streak is your score — one escapee breaks it.**

---

## English

### Goal
Survive as long as you can and score as high as you can. You have **3 lives**. Raiders descend from
the top of the screen; shoot them before they reach you, and keep your **kill chain** alive to pump
your score multiplier. There's no "win" screen — it's a high-score chase. Your **best** score is kept.

### Controls
Works on any board with a D-pad + **A** and **B** (no X/Y needed).

| Input | Action |
|---|---|
| **←/→/↑/↓** | fly the ship — full 8-directional movement |
| **A** (hold) | **autofire** (gated by gun heat — see below) |
| **B** | **panic bomb** — clear every raider on screen |
| **A** | start the game, on the title screen |
| **A** | restart instantly, on the game-over screen |

### The kill chain (how scoring works)
Every raider you shoot adds one link to your **chain**. The chain drives a **score multiplier**:

> **multiplier = 1 + (chain ÷ 5)**

So 5 kills in a row → **x2**, 10 → **x3**, 15 → **x4**, and so on. Each kill scores:

> **50 × your current multiplier**

The chain **resets to zero** (multiplier back to **x1**) whenever:
- a **raider slips off the bottom** of the screen (no life lost — just your streak), **or**
- your **ship is hit** (you also lose a life).

That's the whole tension: a long chain is worth many times more than the same kills scattered, but
the longer you let it run, the more it hurts when one raider gets through. **Greed versus safety.**

### Gun heat — fire in bursts
Holding **A** autofires, but the gun **overheats**. The heat gauge in the top HUD fills as you shoot;
when it maxes out the gun **locks** and you must **release the trigger** to cool it down. A running
chain cools the gun a little faster. So you can't just hold A and wall off every raider — timing your
bursts is part of the game. (A **panic bomb** also vents a big chunk of heat, so it can rescue you
from a lockout.)

### The panic bomb
Press **B** to detonate a bomb: it **clears every raider currently on screen**, kicks the screen with
a shake and a flash, and vents your gun heat.
- You **start with 2** bombs.
- You **earn one more every 10 000 points**, up to a **cap of 3**.
- Spend them when a wave is about to overrun you — that's exactly what they're for.

### Lives and mercy
You have **3 lives**. If a raider touches your ship you lose a life and your chain — but you get a
short window of **invulnerability** afterwards (your ship blinks) so you don't get chain-killed. Your
hitbox is **forgiving** — smaller than the ship sprite — so clipping a wingtip won't kill you. Lose
all three lives and it's game over; press **A** to restart instantly.

### The raiders
Raiders descend from the top and drift sideways, bouncing off the screen edges. Over time they **spawn
faster and move faster**, with a short breather between waves. Some raiders are **divers** — instead
of falling straight, they bank toward your ship. Divers get more common the longer you survive.

### Tips
- **Play goalie, not hunter.** Prioritise raiders about to reach the bottom — one escapee wipes your
  multiplier.
- **Burst-fire.** Tap A in short bursts; don't hold it into a lockout mid-swarm.
- **Bank your bomb for the overrun**, or to break a gun lockout when a wave is on top of you.
- **Weave, don't camp.** Sit still and a diver will find you; keep moving.
- A **fresh multiplier is fragile** — once you're at x3 or x4, tighten up and let nothing through.

---

## Česky

### Cíl
Přežij co nejdéle a nasbírej co nejvíc bodů. Máš **3 životy**. Nájezdníci sestupují z horního okraje;
sestřel je dřív, než k tobě doletí, a udržuj naživu svůj **kill chain**, který ti zvedá násobitel
skóre. Není žádná „výherní" obrazovka — jde o honbu za nejvyšším skóre. Tvé **nejlepší** skóre se
uchovává.

### Ovládání
Funguje na jakékoli desce s D‑padem + **A** a **B** (X/Y netřeba).

| Vstup | Akce |
|---|---|
| **←/→/↑/↓** | řízení lodi — plný pohyb do 8 směrů |
| **A** (držet) | **autofire** (omezený přehřátím zbraně — viz níže) |
| **B** | **panická bomba** — smete všechny nájezdníky na obrazovce |
| **A** | spustit hru, na úvodní obrazovce |
| **A** | okamžitý restart, na obrazovce game over |

### Kill chain (jak funguje bodování)
Každý sestřelený nájezdník přidá jeden článek do tvého **řetězce (chain)**. Řetězec pohání
**násobitel skóre**:

> **násobitel = 1 + (chain ÷ 5)**

Takže 5 sestřelů v řadě → **x2**, 10 → **x3**, 15 → **x4** a tak dál. Každý sestřel boduje:

> **50 × aktuální násobitel**

Řetězec se **vynuluje** (násobitel zpět na **x1**), kdykoli:
- **nájezdník propadne spodním okrajem** obrazovky (bez ztráty života — jen tvá série), **nebo**
- je **loď zasažena** (navíc přijdeš o život).

V tom je celé napětí: dlouhý řetězec má mnohonásobně vyšší cenu než stejné sestřely roztroušené, ale
čím déle ho necháš běžet, tím víc bolí, když jeden nájezdník projde. **Chamtivost versus bezpečí.**

### Přehřátí zbraně — střílej v dávkách
Držení **A** střílí automaticky, ale zbraň se **přehřívá**. Ukazatel tepla v horním HUDu se plní, jak
střílíš; při maximu se zbraň **zablokuje** a musíš **uvolnit spoušť**, aby vychladla. Běžící řetězec
chladí zbraň o trochu rychleji. Nemůžeš tedy jen držet A a odclonit každého nájezdníka — načasování
dávek je součástí hry. (**Panická bomba** také odvětrá velký kus tepla, takže tě může zachránit
z blokace.)

### Panická bomba
Stiskem **B** odpálíš bombu: **smete všechny nájezdníky aktuálně na obrazovce**, otřese obrazovkou
s bleskem a odvětrá teplo zbraně.
- **Začínáš se 2** bombami.
- **Za každých 10 000 bodů** získáš jednu navíc, až do **stropu 3**.
- Šetři si je na chvíli, kdy tě vlna začne přehlcovat — přesně na to jsou.

### Životy a milost
Máš **3 životy**. Když se tě nájezdník dotkne, přijdeš o život a o řetězec — ale poté dostaneš krátké
okno **nezranitelnosti** (loď bliká), abys nebyl sestřelen v řadě. Tvůj zásahový bod je **shovívavý** —
menší než sprite lodi — takže o špičku křídla nezemřeš. Ztratíš všechny tři životy a je konec; stiskem
**A** okamžitě restartuješ.

### Nájezdníci
Nájezdníci sestupují shora a uhýbají do stran, odrážejí se od okrajů obrazovky. Postupem času se
**objevují rychleji a pohybují rychleji**, s krátkým oddechem mezi vlnami. Někteří nájezdníci jsou
**stíhači** — místo aby padali rovně, natáčejí se k tvé lodi. Stíhačů přibývá, čím déle přežíváš.

### Tipy
- **Hraj brankáře, ne lovce.** Přednostně řeš nájezdníky, kteří se blíží ke spodku — jeden únik smaže
  tvůj násobitel.
- **Střílej v dávkách.** Ťukej A krátce; nedrž ho až do zablokování uprostřed vlny.
- **Šetři bombu na přehlcení**, nebo na prolomení blokace zbraně, když je vlna na tobě.
- **Kličkuj, nekempuj.** Když stojíš na místě, stíhač si tě najde; buď v pohybu.
- **Čerstvý násobitel je křehký** — jakmile jsi na x3 nebo x4, přitáhni obranu a nepusť nic skrz.
