# Picatro — The Pico Circus

A poker deckbuilder for the PicoPad. Play the best hands, bank bonuses with your discards,
and beat five rising score targets before you run out of hands. **The discard is your weapon.**

---

## English

### Goal
Beat **5 blinds**. Each blind has a **TARGET score** you must reach within **3 hands** (plus **3
discards**). Clear blind 5 and you beat the Pico Circus.

| Blind | 1 | 2 | 3 | 4 | 5 |
|------:|--:|--:|--:|--:|--:|
| Target | 800 | 1800 | 2800 | 3600 | 4200 |

Clearing 3 blinds is already a genuine run — the game is hard on purpose.

### Controls
Works on any board with a D-pad + **A** and **B** (no X/Y needed).

| Input | Action |
|---|---|
| **←/→** | move the cursor along your hand |
| **↑** | pick the card under the cursor (it lifts up) — up to 5 |
| **↓** | drop it back (deselect) |
| **A** | **PLAY** the picked cards (score them) |
| **B** | **DISCARD** the picked cards (bank a bonus — see below) |
| **Y** | *(optional)* toggle a **live score preview** of your current pick — a learning aid; boards without a Y button just skip it |
| **A** | continue / next, on the result screens |

### How scoring works
A played hand scores **CHIPS × MULT**.

- **CHIPS** = the hand's base chips + the *rank value* of each scoring card + **Grinder** (+3 per
  scoring card) + any **banked hearts**.
- **MULT** = the hand's base mult + any **banked diamonds** + **Steady** (+3) + **Harlequin**
  (+1 for each different suit in the five cards beyond the first). Then, if you banked clubs, the
  whole mult is multiplied by **×(1 + 0.5 × banked clubs)**.

Rank values (chips): 2→2, 3→3 … 9→9, 10/J/Q/K→10, A→11.

### Poker hands (base CHIPS × MULT)
| Hand | Base |
|---|---|
| High Card | 5 × 1 |
| Pair | 10 × 2 |
| Two Pair | 20 × 2 |
| Three of a Kind | 40 × 2 |
| Straight | 40 × 3 |
| Flush | 70 × 3 |
| Full House | 55 × 4 |
| Four of a Kind | 55 × 6 |
| Straight Flush | 110 × 8 |

The base values read as a poker ladder (a flush beats a straight, a straight flush beats four of a
kind). The monosuit hands (Flush, Straight Flush) carry high **chips** because they can never earn
Harlequin — so a well-mixed rainbow hand still out-scores a same-tier flush. That's the twist.

### The DISCARD is your weapon
Discarding cards doesn't just cycle them — each discarded card **banks a bonus onto your NEXT
hand**, by suit:

| Suit | Discard banks… |
|---|---|
| ♥ Heart | **+4 chips** each |
| ♦ Diamond | **+1 mult** each |
| ♣ Club | **× mult** — each club adds +0.5× (e.g. 2 clubs = ×2.0), applied to your next hand |
| ♠ Spade | **digs +1 card** — your hand grows to 9 for one action, then settles back to 8 |

Banks are spent by your **next PLAY**. Timing *when* you cash in a big bank is the core skill.

### The 3 Acts (always-on bonuses, shown top-left)
- **Grinder** — +3 chips per scoring card.
- **Steady** — +3 mult, every hand.
- **Harlequin** — +1 mult for every *different suit* in your played five (beyond the first). This
  rewards **variety** — it's the reason a rainbow hand can out-score a flush.

### Carry-hand
Cards you **don't play** carry over into the next blind (the deck reshuffles, banks reset). So you
can **hoard a great card for a hard blind** instead of wasting it early. There's no shop — your saved
cards *are* your economy.

### The Understudy (the wild card)
Once per run, a special **"?" card** appears — a masked circus understudy who steps into any act.
- It shows a **"?"** for its rank but keeps a **real suit** (its pip and colour), with a **gold edge**.
- When you PLAY it, it becomes whatever **rank** scores best for your hand — but it can **never make a
  Straight Flush** (it caps at Four of a Kind). Its **suit is fixed**, so it can't hand you a free
  flush or free suit-variety.
- If you DISCARD it, it banks its printed suit like any card — then it's gone.
- There is only **one, ever** — so decide: spend it on an easy blind, or carry it (don't pick it) to
  blind 4 or 5 and build a big hand around it.

### Worked example
You play **K♠ K♥ 7♦ 7♣ 2♠** = Two Pair. You had banked **3 hearts** and **2 clubs** last turn.
- CHIPS = 20 (Two Pair) + (10+10+7+7 rank) + 12 (Grinder, 4 scoring cards) + 12 (3 banked hearts) = **90**
- MULT = 2 (Two Pair) + 3 (Steady) + 3 (Harlequin: 4 suits → +3) = 8, then ×(1 + 0.5×2 clubs) = ×2.0 → **16**
- Score = 90 × 16 = **1440**

### Tips
- Discard early to build a big bank, then unleash it on one huge hand.
- Clubs are the multiplier — a few banked clubs turn a modest hand into a blind-clearer.
- Harlequin loves rainbows; don't tunnel on flushes.
- Save the Understudy for when you really need it.

---

## Česky

### Cíl
Poraz **5 blindů**. Každý blind má **cílové skóre**, které musíš dosáhnout během **3 rukou** (plus
**3 discardy**). Vyčisti blind 5 a porazil jsi Pico Circus.

| Blind | 1 | 2 | 3 | 4 | 5 |
|------:|--:|--:|--:|--:|--:|
| Cíl | 800 | 1800 | 2800 | 3600 | 4200 |

Zvládnout 3 blindy je už opravdový úspěch — hra je záměrně těžká.

### Ovládání
Funguje na jakékoli desce s D‑padem + **A** a **B** (X/Y netřeba).

| Vstup | Akce |
|---|---|
| **←/→** | pohyb kurzoru po ruce |
| **↑** | vyber kartu pod kurzorem (zvedne se) — max 5 |
| **↓** | vrať ji zpět (zruš výběr) |
| **A** | **PLAY** — zahraj vybrané karty (obodují se) |
| **B** | **DISCARD** — odhoď vybrané karty (nabankuješ bonus — viz níže) |
| **Y** | *(volitelné)* přepni **živý náhled skóre** aktuálního výběru — učební pomůcka; desky bez tlačítka Y ho prostě přeskočí |
| **A** | pokračovat / dále, na výsledkových obrazovkách |

### Jak funguje bodování
Zahraná ruka boduje jako **CHIPS × MULT**.

- **CHIPS** = základ ruky + *hodnota* každé bodující karty + **Grinder** (+3 za bodující kartu) +
  nabankovaná **srdce**.
- **MULT** = základ ruky + nabankované **kára** + **Steady** (+3) + **Harlequin** (+1 za každou
  další barvu v pěti kartách nad první). Pokud jsi bankoval **kříže**, celý mult se pak vynásobí
  **×(1 + 0,5 × počet křížů)**.

Hodnoty karet (chips): 2→2, 3→3 … 9→9, 10/J/Q/K→10, A→11.

### Pokerové ruce (základ CHIPS × MULT)
| Ruka | Základ |
|---|---|
| Vysoká karta | 5 × 1 |
| Pár | 10 × 2 |
| Dva páry | 20 × 2 |
| Trojice | 40 × 2 |
| Postupka | 40 × 3 |
| Barva (Flush) | 70 × 3 |
| Full House | 55 × 4 |
| Čtveřice | 55 × 6 |
| Postupka v barvě | 110 × 8 |

Základy tvoří pokerový žebříček (flush poráží postupku, postupka v barvě poráží čtveřici). Monobarevné
ruce (Flush, Postupka v barvě) mají vysoké **chips**, protože nikdy nedostanou Harlequin — takže dobře
namíchaná duhová ruka pořád přebije flush stejné úrovně. To je ten twist.

### DISCARD je tvoje zbraň
Odhození karet je nejen protočí — každá odhozená karta **nabankuje bonus na tvou DALŠÍ ruku** podle
barvy:

| Barva | Discard nabankuje… |
|---|---|
| ♥ Srdce | **+4 chips** za kus |
| ♦ Káro | **+1 mult** za kus |
| ♣ Kříž | **× mult** — každý kříž přidá +0,5× (např. 2 kříže = ×2,0) na příští ruku |
| ♠ Piky | **dokopání +1 karta** — ruka naroste na 9 pro jednu akci, pak se vrátí na 8 |

Banky se spotřebují **další rukou (PLAY)**. Načasování, *kdy* velký bank uplatníš, je klíčová dovednost.

### 3 Acts (stálé bonusy, vlevo nahoře)
- **Grinder** — +3 chips za bodující kartu.
- **Steady** — +3 mult, každou ruku.
- **Harlequin** — +1 mult za každou *další barvu* ve tvých pěti kartách (nad první). Odměňuje
  **pestrost** — proto duhová ruka může přebít flush.

### Carry‑hand (ruka se přenáší)
Karty, které **nezahraješ**, se přenesou do dalšího blindu (balíček se přemíchá, banky se vynulují).
Můžeš tak **schovat dobrou kartu na těžký blind** místo abys ji vyplýtval brzy. Není žádný obchod —
tvé uschované karty *jsou* tvá ekonomika.

### The Understudy (žolíková karta)
Jednou za hru se objeví speciální karta **„?"** — maskovaný cirkusový záskok, který zaskočí za
jakoukoli roli.
- Místo hodnoty ukazuje **„?"**, ale má **skutečnou barvu** (pip i barvu inkoustu) a **zlatý okraj**.
- Když ji zahraješ, stane se tou **hodnotou**, co ti dá nejvíc bodů — ale **nikdy neudělá Postupku v
  barvě** (strop je Čtveřice). Její **barva je pevná**, takže ti nedá flush ani pestrost zadarmo.
- Když ji odhodíš, nabankuje svou vytištěnou barvu jako každá karta — pak je pryč.
- Je jen **jedna, jednou** — takže se rozhodni: utratit ji na lehkém blindu, nebo ji donést
  (nevybírat ji) na blind 4 nebo 5 a postavit kolem ní velkou ruku.

### Příklad výpočtu
Zahraješ **K♠ K♥ 7♦ 7♣ 2♠** = Dva páry. Minulé kolo jsi nabankoval **3 srdce** a **2 kříže**.
- CHIPS = 20 (Dva páry) + (10+10+7+7 hodnoty) + 12 (Grinder, 4 bodující karty) + 12 (3 srdce) = **90**
- MULT = 2 (Dva páry) + 3 (Steady) + 3 (Harlequin: 4 barvy → +3) = 8, pak ×(1 + 0,5×2 kříže) = ×2,0 → **16**
- Skóre = 90 × 16 = **1440**

### Tipy
- Odhazuj brzy a nabankuj velký bonus, pak ho uvolni na jednu obří ruku.
- Kříže jsou násobitel — pár nabankovaných křížů promění slabou ruku ve vyčištění blindu.
- Harlequin miluje duhy; nezacyklíš se jen na flushích.
- Understudy si schovej na chvíli, kdy ho fakt potřebuješ.
