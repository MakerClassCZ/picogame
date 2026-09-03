---
title: "Matematika, náhoda a kolize"
description: "Číselné funkce, opakovatelné náhodné posloupnosti a kolizní testy zabudované ve Sprite."
---

Tato stránka popisuje číselné funkce, generátor náhodných čísel s počáteční hodnotou a kolizní metody třídy `Sprite`. Ani jeden z pomocných modulů nevyžaduje inicializaci enginu. Signatury najdeš v [/cs/reference/](/cs/reference/).

## picogame_math

`picogame_math` nabízí funkce `clamp`, `lerp`, `approach` a `wrap`, výpočty s 2D vektory a trigonometrii vyjádřenou v otáčkách. Funkce končící na `_t` používají pro celou otáčku interval `[0,1)`, což se hodí pro uložený směr nebo míření. Modul také převzal vektorové funkce ze staršího `picogame_vec`.

API:

- `clamp(v, lo, hi)` - omezí `v` na interval `[lo, hi]`, například pro pozici na obrazovce nebo počet životů.
- `mid(a, b, c)` - vrátí medián tří hodnot; pokud je prostředním argumentem omezovaná hodnota, chová se podobně jako `clamp`.
- `lerp(a, b, t)` - lineární interpolace `a + (b-a)*t`. Opakované volání s malým `t` vytváří plynulé přibližování.
- `inv_lerp(a, b, v)` - inverze `lerp`: kde leží `v` v `[a,b]` jako `0..1`. Vrátí `0.0`, pokud `a == b`.
- `remap(v, a, b, c, d)` - převede `v` z rozsahu `[a,b]` na `[c,d]`. Pokud `a == b`, vrátí `c`.
- `sgn(x)` - znaménko jako `-1`, `0` nebo `1`.
- `approach(v, target, step)` - posune `v` k `target` nejvýše o `step`, bez překročení cíle. Hodí se pro zrychlování a zpomalování.
- `wrap(v, lo, hi)` - zabalí `v` do polootevřeného rozsahu `[lo, hi)`. Degenerované nebo obrácené rozsahy vrátí `lo` (žádné dělení nulou, nikdy mimo rozsah).
- `sin_t(turns)` / `cos_t(turns)` - sinus/kosinus úhlu v OTÁČKÁCH (`1.0` = celý kruh). Kladná hodnota je po směru hodinových ručiček na obrazovce s osou y dolů.
- `atan2_t(dy, dx)` - úhel vektoru `(dx, dy)` v otáčkách, normalizovaný do `0..1`. Použij na míření.
- `length(dx, dy)` - velikost vektoru.
- `distance(x1, y1, x2, y2)` - vzdálenost mezi dvěma body.
- `normalize(dx, dy)` - jednotkový vektor; pro vstup nulové délky vrátí `(0.0, 0.0)`.
- `angle_rad(dx, dy)` - úhel v RADIÁNECH (surový `atan2`); `from_angle_rad(a, mag=1.0)` - vektor délky `mag` pod radiánovým úhlem `a`.
- `TAU` - konstanta `2*pi`, kterou interně používá trigonometrie s `_t`.

Příklad otočení lodi a tahu ve směru její přídě:

```python
import picogame_math as m

ang = 0.0                       # heading, in turns 0..1
TURN = 0.01
ang = (ang + TURN) % 1.0        # rotate right
dx, dy = m.sin_t(ang), -m.cos_t(ang)   # nose-up direction
vx += dx * 0.25
vy += dy * 0.25
sp = m.length(vx, vy)           # current speed
x = m.clamp(x, 8, W - 8)        # udrží objekt na obrazovce
```

:::note[Pozor]
- Na obrazovce s osou y dolů roste úhel funkcí `_t` po směru hodinových ručiček. Směr nahoru odpovídá `-cos_t`, proto u svislé složky změň znaménko jako v příkladu.
- `wrap` je polootevřený: `wrap(hi, lo, hi)` vrátí `lo`, ne `hi`. Pro obrácený nebo nulový rozsah prostě vrátí `lo`, místo aby vyhodil chybu.
- Otáčky (`sin_t`/`cos_t`/`atan2_t`) a radiány (`angle_rad`/`from_angle_rad`) používej konzistentně; pro stejný úhel je nemíchej dohromady.
:::

## picogame_rand

Tento generátor (kombinovaný 30bitový Lehmer: dva MLCG proudy s prvočíselným modulem, perioda ≈ 2^58; každý mezivýsledek je malé celé číslo MicroPythonu, takže losování nic nealokuje) podporuje vážený výběr, zamíchání seznamu na místě a losovací sáček. Pevná počáteční hodnota vytváří opakovatelnou posloupnost pro záznamy hry, testy nebo generování úrovní. `Rand()` bez argumentu použije aktuální čas. `Bag` v každém zamíchaném cyklu vydá každou položku jednou, takže omezuje dlouhé série stejného výsledku.

`Rand(seed=None)`:

- `Rand(1234)` použije pevnou počáteční hodnotu; `Rand()` ji odvodí z hodin. Jako seed funguje jakékoli celé číslo včetně `0` (použije se spodních 30 bitů).
- `seed(s)` - nastaví novou počáteční hodnotu existujícího generátoru.
- `below(n)` - celé číslo v `0 .. n-1`. Vrátí `0`, pokud `n <= 0`.
- `randint(a, b)` - celé číslo v `a .. b` včetně. Vyhodí `ValueError`, pokud `b < a`.
- `random()` - float v `[0.0, 1.0)`.
- `chance(p)` - `True` s pravděpodobností `p` (kde `p` je `0..1`).
- `choice(seq)` - jeden prvek ze `seq`. Vyhodí `ValueError` u prázdné sekvence.
- `shuffle(lst)` - zamíchá `lst` algoritmem Fisher–Yates přímo v původním seznamu a vrátí `None`.
- `weighted(weights)` - vrátí index `0..len-1` vybraný úměrně k `weights`. Vyhodí `ValueError`, pokud je součet `<= 0`. Bez řízení šňůr (nezávislé tahy).

`Bag(items, rng)`:

- Losovací sáček neboli „7-bag“ vydá každou položku jednou za cyklus v zamíchaném pořadí. Pro herní dílky nebo výskyt objektů tak nevznikají dlouhé série ani období bez určité položky.
- `next()` - vrátí další položku, na začátku každého cyklu automaticky zamíchá. Vyhodí `ValueError` při konstrukci, pokud je `items` prázdné.

Příklad jednoho generátoru a losovacího sáčku:

```python
import picogame_rand

rng = picogame_rand.Rand(0x1234)      # seeded -> reproducible
x = rng.randint(40, W - 40)           # 40 .. W-40 inclusive
if rng.chance(0.25):
    spawn_powerup(x)
kind = rng.weighted([5, 3, 1])        # index 0 most likely
bag = picogame_rand.Bag([0, 1, 2, 3, 4, 5, 6], rng)
piece = bag.next()                    # každá hodnota jednou za cyklus
```

:::note[Pozor]
- Sáhni po `picogame_rand` (nebo prostém `random.randint`) místo `random.shuffle`, `random.sample` či `random.choices`: ty existují jen v desktopovém CPythonu, takže hra, která je používá, běží v [simulátoru](/cs/simulator/), ale na zařízení i v prohlížeči (obojí MicroPython) spadne s `AttributeError: module 'random' has no attribute 'shuffle'`. `Rand.shuffle` je přímá náhrada.
- `shuffle` mění původní seznam a vrací `None`, proto nepiš `lst = rng.shuffle(lst)`.
- `Bag` si bere do vlastnictví kopii `items`; `next()` přemíchává tento vnitřní seznam, takže pořadí, které jsi předal, se nezachová.
- `weighted` vrací index, ne hodnotu - indexuj jím do svého vlastního seznamu.
- Stejná počáteční hodnota a stejné pořadí volání vytvoří stejné výsledky. Sdílený generátor proto také propojí náhodné posloupnosti dvou herních systémů.
:::

## Kolize spritů

Každý `Sprite` nabízí kolizi obdélníků a test vzdálenosti středů. Metody pracují s vykreslenými hranicemi po započtení kotevního bodu, měřítka a rotace a nealokují návratový objekt. `overlaps()` použij pro průnik spritů nebo obdélníků, `near()` pro kruhový test vzdálenosti.

API (metody na každém `Sprite`):

- `a.overlaps(b, inset=0)` - testuje včetně dotyku překryv osově zarovnaných obdélníků. `b` může být jiný `Sprite`, bod `(x, y)` nebo obdélník `(x1, y1, x2, y2)`. Parametr `inset` zmenší kolizní obdélník prvního spritu o N pixelů na každé straně. Vrací `bool`.
- `a.near(b, r)` - kruhový test: je střed tohoto spritu do `r` px od středu `b`? Používá kvadrát vzdálenosti, takže žádný `sqrt`. `b` může být `Sprite` nebo bod `(x, y)`.

Obdélníky a středy vycházejí z vykreslené plochy spritu, včetně kotevního bodu, měřítka a rotace. Kotevní body popisuje [/cs/scene-format/](/cs/scene-format/).

Pro dva vypočtené obdélníky bez spritů použij `pg.collide(x1, y1, x2, y2, ax1, ay1[, ax2, ay2])`. U zdí a terénu v mřížce se dotazuj na vlastnosti přes `picogame_tiles` místo testování každé dlaždice.

Příklad kruhové kolize střel s kameny a obdélníkové kolize hráče:

```python
for b in bullets:
    for r in rocks:
        if b.visible and b.near(r, 18):   # kruhový test bez odmocniny
            kill(b, r)

if player.overlaps(enemy):                # překryv obdélníků se započtením kotev
    take_damage()

if not ship.overlaps((0, 0, W, H)):       # mimo obrazovku? odeber ho
    pool.free(ship)
```

:::note[Pozor]
- Metody čtou aktuální celočíselnou pozici spritu. Pokud pohyb ukládáš jako desetinné číslo v `data["x"]`, zavolej před testem `sprite.move(int(x), int(y))`.
- `overlaps` testuje obdélníky, ne jednotlivé pixely. Pomocí `inset` můžeš omezit zásahy v průhledných rozích grafiky.
- Viditelnost ani stav entity se nekontrolují. Neaktivní objekty před testem přeskoč, například pomocí `if sprite.visible`. Opakované použití objektů popisuje [/cs/memory/](/cs/memory/).
:::
