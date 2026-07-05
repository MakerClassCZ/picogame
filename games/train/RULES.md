# Train — Snake on Rails

A logic puzzle for the PicoPad. Steer a runaway locomotive, collect every gem, and drive the whole
train out through the gate. The loco never stops and drags a snake of wagons through every turn —
**you don't drive it, you steer it.**

---

## English

### Goal
Each level is a walled **yard** scattered with **gems**. You control the **locomotive**, which moves
by itself. Collect **every gem** on the board; once the yard is clear the **gate opens**; drive the
loco's head through the gate to **finish the level**. There are **50 levels**.

### Controls
Works on any board with a D-pad + **A** and **B**.

| Input | Action |
|---|---|
| **←/→/↑/↓** | steer the locomotive (change its heading) |
| **A** | open the level-code entry (jump to any level) |

The loco starts **still**. The first arrow you press sets it rolling; after that it **keeps moving on
its own**, one step at a time, and the arrows only **turn** it. You can queue a turn a moment early
(two turns are buffered), so you can line up a corner before you reach it.

### How the train works
- **It never stops.** Once rolling, the loco takes one step every beat (about two steps a second).
  You can change its heading but you can't halt it or reverse it into itself.
- **It leaves a trail.** Every tile the head crosses records a direction, and each **wagon** follows
  that trail exactly like the tail of a snake. Turn a corner and the whole train snakes round it.
- **Collect to grow.** Drive the head over a **gem** and it becomes a **new wagon** on the tail
  (+10 points). The more gems you take, the **longer** the train and the harder it is to route.
- **The gate.** It stays **shut** until the last gem is gone, then **swings open**. Reach the open
  gate with the head to win. Reaching it while it's still shut is a **crash**.

### Crashing
The level **restarts** if the loco's head runs into:
- a **wall** (the yard border), or the edge of the board,
- the **gate while it's still closed** (gems remain), or
- **its own train** (any wagon of the tail).

A crash resets the layout of the current level; your **score carries on**. Finishing a level takes
you straight into the next one with your score intact — there are no transition screens.

### Level codes
Every level has a unique **5-letter code**, shown in the top bar (e.g. level 1 is `GOLEM`). Press
**A** at any time to open the code entry in the top bar and type a code to **jump to that level**.
There is no separate save file — **the code is your progress**, so note the code of a level you want
to come back to.

While entering a code:

| Input | Action |
|---|---|
| **↑/↓** | change the highlighted letter (A…Z) |
| **←/→** | move between the five letters |
| **A** | confirm — jump to that level (a valid code only) |
| **B** | cancel and return to the current level |

A wrong code leaves you in the editor; press an arrow to keep editing, or **B** to go back.

### Tips
- Look before you roll: plan a route that visits **every** gem, because you can't stop to think once
  the loco is moving.
- Keep your **tail** in mind — a long train can box the head into a dead end.
- Sweep gems in **lines and loops** rather than doubling back; you can never turn straight back on
  yourself.
- Stuck on a level? Note its **code** so a crash or a break doesn't cost you progress.

---

## Česky

### Cíl
Každá úroveň je ohrazený **dvůr** s rozsypanými **drahokamy**. Ovládáš **lokomotivu**, která jede
sama. Posbírej **všechny drahokamy** na hrací ploše; jakmile je dvůr čistý, **otevře se brána**;
projeď hlavou lokomotivy branou a **úroveň dokončíš**. Úrovní je **50**.

### Ovládání
Funguje na jakékoli desce s D-padem + **A** a **B**.

| Vstup | Akce |
|---|---|
| **←/→/↑/↓** | řízení lokomotivy (změna směru) |
| **A** | otevře zadání kódu úrovně (skok na libovolnou úroveň) |

Lokomotiva zpočátku **stojí**. První stisknutá šipka ji rozjede; potom už **jede sama**, krok za
krokem, a šipky ji jen **zatáčejí**. Zatáčku můžeš zadat s malým předstihem (dvě jsou uložené do
fronty), takže si roh připravíš dřív, než k němu dojedeš.

### Jak vlak funguje
- **Nikdy nezastaví.** Jakmile se rozjede, udělá lokomotiva jeden krok každý takt (asi dva kroky za
  sekundu). Můžeš měnit směr, ale nemůžeš ji zastavit ani couvnout sama do sebe.
- **Nechává stopu.** Každé políčko, přes které hlava projede, si zapamatuje směr a každý **vagón** tu
  stopu sleduje přesně jako ocas hada. Zatočíš a celý vlak se za rohem svine.
- **Sbírej a rosteš.** Přejeď hlavou přes **drahokam** a stane se z něj **nový vagón** na ocase
  (+10 bodů). Čím víc drahokamů posbíráš, tím je vlak **delší** a tím hůř se řídí.
- **Brána.** Zůstane **zavřená**, dokud nezmizí poslední drahokam, pak se **otevře**. Dojeď k
  otevřené bráně hlavou a vyhráváš. Dojet k ní, když je ještě zavřená, znamená **náraz**.

### Náraz
Úroveň se **restartuje**, když hlava lokomotivy narazí do:
- **zdi** (okraj dvora) nebo mimo hrací plochu,
- **brány, dokud je zavřená** (zbývají drahokamy), nebo
- **vlastního vlaku** (kteréhokoli vagónu ocasu).

Náraz resetuje rozložení aktuální úrovně; tvé **skóre pokračuje dál**. Dokončení úrovně tě rovnou
přenese do další se zachovaným skóre — žádné mezidobrazovky nejsou.

### Kódy úrovní
Každá úroveň má jedinečný **5písmenný kód** zobrazený v horní liště (např. úroveň 1 je `GOLEM`).
Kdykoli stiskni **A**, otevře se zadávání kódu v horní liště, a napiš kód pro **skok na tu úroveň**.
Není žádný samostatný uložený soubor — **kód je tvůj postup**, takže si poznamenej kód úrovně, ke
které se chceš vrátit.

Při zadávání kódu:

| Vstup | Akce |
|---|---|
| **↑/↓** | změní zvýrazněné písmeno (A…Z) |
| **←/→** | pohyb mezi pěti písmeny |
| **A** | potvrdit — skok na úroveň (jen platný kód) |
| **B** | zrušit a vrátit se do aktuální úrovně |

Špatný kód tě nechá v editoru; šipkou pokračuj v úpravách, nebo se **B** vrať zpět.

### Tipy
- Rozmysli si trasu, než se rozjedeš: naplánuj cestu přes **každý** drahokam, protože jakmile
  lokomotiva jede, není čas přemýšlet.
- Mysli na svůj **ocas** — dlouhý vlak může hlavu zahnat do slepé uličky.
- Sbírej drahokamy v **liniích a smyčkách**, ne zpátky přes sebe; couvnout přímo do sebe nejde nikdy.
- Zaseklý na úrovni? Poznamenej si její **kód**, aby tě náraz nebo pauza nestály postup.
