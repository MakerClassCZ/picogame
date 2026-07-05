# Picotris — Falling Blocks on the Pico

A Tetris-style block-stacker for the PicoPad. Slide and rotate the seven tetrominoes to pack
complete rows, clear them, and survive as the pieces fall faster and faster. **The big multi-line
clears are where the points are.**

---

## English

### Goal
There's no finish line — Picotris is an **endless** score chase. Keep the well from filling up,
clear as many rows as you can, and push your **level** (and your speed) as high as you dare. When a
new piece can't fit at the top, it's **game over** and a fresh well begins.

The well is **10 columns wide** and **18 rows tall**.

### Controls
Works on any board with a D-pad + **A** (no B/X/Y needed).

| Input | Action |
|---|---|
| **←/→** | move the current piece left / right |
| **A** | rotate the piece clockwise |
| **↓** | **soft-drop** — the piece falls one cell per frame while held |

There is no hard-drop, no hold-piece, and no counter-clockwise rotation — just the classic stack.
Rotation only happens if the piece actually fits (no wall-kicks).

### The pieces
All seven standard tetrominoes appear: **I, O, T, S, Z, J, L**. They're dealt by a **7-bag**
randomiser — each shape comes out exactly once per shuffled batch of seven, so you never get long
runs of the same piece or a maddening drought.

Two helpers make planning easy:
- **Ghost piece** — a dim outline showing exactly where the current piece will land if it drops
  straight down.
- **NEXT box** — previews the piece coming after this one.

### How scoring works
You score by **clearing rows** — filling a horizontal line all the way across (all 10 columns).
Full rows **flash white**, then vanish, and everything above drops down.

The payout depends on **how many rows you clear in a single drop**, multiplied by your level:

| Rows cleared at once | Name | Base points |
|---:|---|---:|
| 1 | Single | **40** |
| 2 | Double | **100** |
| 3 | Triple | **300** |
| 4 | **Picotris** | **1200** |

> **Score gained = base points × (level + 1).**

Because a 4-row *Picotris* (1200) pays far more than four separate singles (4 × 40 = 160), the whole
strategy is building a flat stack with one deep gap and dropping an **I-piece** to clear four rows at
once.

### Levels & speed
Every **10 lines cleared** raises your **level by 1**. Each level makes gravity faster — there are
ten speed steps, then it holds at maximum:

| Level | Gravity (frames per cell) | ≈ seconds per cell |
|---:|---:|---:|
| 0 | 24 | 0.80 |
| 1 | 20 | 0.67 |
| 2 | 16 | 0.53 |
| 3 | 13 | 0.43 |
| 4 | 10 | 0.33 |
| 5 | 8 | 0.27 |
| 6 | 6 | 0.20 |
| 7 | 5 | 0.17 |
| 8 | 4 | 0.13 |
| 9+ | 3 | 0.10 |

(The game runs at 30 frames per second; holding **↓** soft-drops at one cell per frame regardless of
level.)

### Tips
- Keep the stack **flat** and leave a single column open for an **I-piece** to score a Picotris.
- Use the **ghost** to line pieces up before they land — no guessing.
- Read the **NEXT** box: don't cap the gap you're saving for that I-piece.
- **Soft-drop** to place pieces quickly when you're confident; it also keeps a fast level moving.
- Rotate *before* you slide into a tight spot — rotation is refused if the piece doesn't fit.

---

## Česky

### Cíl
Žádná cílová čára — Picotris je **nekonečná** honba za skóre. Zabraň zaplnění jámy, vyčisti co
nejvíc řádků a vyžeň svůj **level** (a rychlost) tak vysoko, jak si troufneš. Když se nová kostka
nahoře už nevejde, je **konec hry** a začíná čerstvá jáma.

Jáma je **10 sloupců** široká a **18 řádků** vysoká.

### Ovládání
Funguje na jakékoli desce s D‑padem + **A** (B/X/Y netřeba).

| Vstup | Akce |
|---|---|
| **←/→** | posuň aktuální kostku vlevo / vpravo |
| **A** | otoč kostku po směru hodinových ručiček |
| **↓** | **soft‑drop** — kostka padá o jednu buňku za snímek, dokud držíš |

Není žádný hard‑drop, žádné odložení kostky ani otáčení proti směru — jen klasické skládání.
Otočení proběhne, jen pokud se kostka skutečně vejde (bez wall‑kicků).

### Kostky
Objevuje se všech sedm standardních tetromin: **I, O, T, S, Z, J, L**. Rozdává je **7‑bag**
randomizér — každý tvar vypadne přesně jednou za zamíchanou sedmičku, takže nikdy nedostaneš dlouhé
série stejné kostky ani úmorné čekání.

Dva pomocníci usnadňují plánování:
- **Ghost (duch)** — matný obrys, kde kostka přistane, když spadne rovnou dolů.
- **NEXT** — náhled kostky, která přijde po té aktuální.

### Jak funguje bodování
Boduješ **čištěním řádků** — zaplněním celého vodorovného řádku napříč (všech 10 sloupců). Plné
řádky **blikne bíle**, pak zmizí a vše nad nimi spadne dolů.

Odměna závisí na tom, **kolik řádků vyčistíš jedním dopadem**, násobeno tvým levelem:

| Řádků najednou | Název | Základní body |
|---:|---|---:|
| 1 | Single | **40** |
| 2 | Double | **100** |
| 3 | Triple | **300** |
| 4 | **Picotris** | **1200** |

> **Získané skóre = základní body × (level + 1).**

Protože čtyřřádkový *Picotris* (1200) vynese mnohem víc než čtyři samostatné singly (4 × 40 = 160),
celá strategie je postavit plochý sloupec s jednou hlubokou mezerou a spustit do ní **I‑kostku**, co
vyčistí čtyři řádky naráz.

### Levely a rychlost
Každých **10 vyčištěných řádků** zvýší **level o 1**. Každý level zrychlí gravitaci — je deset
rychlostních stupňů, pak drží na maximu:

| Level | Gravitace (snímků na buňku) | ≈ sekund na buňku |
|---:|---:|---:|
| 0 | 24 | 0,80 |
| 1 | 20 | 0,67 |
| 2 | 16 | 0,53 |
| 3 | 13 | 0,43 |
| 4 | 10 | 0,33 |
| 5 | 8 | 0,27 |
| 6 | 6 | 0,20 |
| 7 | 5 | 0,17 |
| 8 | 4 | 0,13 |
| 9+ | 3 | 0,10 |

(Hra běží na 30 snímcích za sekundu; držení **↓** soft‑dropuje o jednu buňku za snímek bez ohledu na
level.)

### Tipy
- Drž sloupec **plochý** a nech jednu kolonu volnou pro **I‑kostku** na Picotris.
- Využij **ducha** k zarovnání kostek před dopadem — žádné hádání.
- Sleduj **NEXT**: nezastav si mezeru, kterou si šetříš na I‑kostku.
- **Soft‑drop** pokládá kostky rychle, když si věříš; udrží i tempo na vysokém levelu.
- Otoč kostku *dřív*, než ji zasuneš do těsného místa — otočení se odmítne, pokud se nevejde.
