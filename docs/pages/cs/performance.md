---
title: Výkon — udrž hru svižnou
description: Praktický checklist pro stabilní snímkovou frekvenci v picogame — herní smyčka ve funkci, dirty-rect-friendly pohyb, vrstvy bez RAM a žádné alokace za snímek.
sidebar:
  label: Výkon
  order: 7
---

Hry v picogame běží ustálených **30 FPS**, když se každý snímek vejde do zhruba **33 ms**. Většina
malých her se tam dostane bez námahy — vykreslování běží v nativním C a engine překresluje jen to, co
se pohnulo. Když hra začne cukat, níže jsou opravy, které reálně zaberou, zhruba podle přínosu. Každé
číslo je měřené na RP2040.

## 1. Dej herní smyčku do funkce

Tohle je největší jednotlivá páka. V MicroPythonu je čtení **globálu na úrovni modulu pokaždé
vyhledání ve slovníku** — a na desce je právě tohle vyhledání vůbec to nejžhavější, co interpret dělá.
Jména uvnitř **funkce jsou lokální**, což je mnohem levnější. Zabal proto smyčku do funkce a zavolej ji:

```python
def main():
    x = W // 2                 # lokální — rychlé
    while True:
        buttons.poll()
        if buttons.is_pressed(pi.RIGHT):
            x += 2
        ball.x = x
        scene.refresh()
        clock.tick()

main()
```

Na jedné reálné hře přesun smyčky do funkce zkrátil její čas v Pythonu z **~12 ms na ~8 ms na snímek
(−33 %)** — dost na to, aby se hra, která nestíhala cap, dostala na solidních 30 FPS.

## 2. Vytáhni lookupy ven z horké smyčky

Stejná myšlenka o úroveň níž. Když saháš na `self.player.x` nebo `sprite.move` mnohokrát za snímek,
přečti si to jednou do lokální proměnné:

```python
def main():
    px = ball.x                # cachni atribut
    poll = buttons.poll        # cachni navázanou metodu
    while True:
        poll()
        px += vx
        ball.x = px
        ...
```

Opakované `obj.attr` a `obj.metoda()` stojí pokaždé vyhledání; lokální proměnná skoro nic.

## 3. Hýbej málo věcmi

picogame je **retained, dirty-rect** vykreslování: překresluje jen obdélníky, které se změnily, a na
SPI panelu posílá jen ty pixely. **Statické pozadí s malým pohyblivým popředím** je ideál. Změna, která
zasáhne většinu obrazovky, stojí celý snímek tak jako tak — drž tedy počet pohyblivých objektů nízko a
nech pozadí stát. Viz [Kreslicí cesty](/cs/concepts/drawing-paths/).

## 4. Preferuj vrstvy bez RAM

- **StripDraw** kreslí efekty přes celou obrazovku (silnice, přechodové nebe, scanline HUD) **bez
  pixelového bufferu** — nula RAM navíc a nic, co držet v synchronu.
- **Tilemap** je **jeden bajt na buňku**, takže velký scrollující svět je levný.
- Po retained **Canvasu** sahej jen kvůli malému panelu, který se mění zřídka — Canvas přes celou
  obrazovku je velký buffer, který obvykle nepotřebuješ. Viz [Vejít se do RAM](/cs/memory/).

- **Dávkuj malování ve StripDraw.** Callback běží jednou na každý render-strip (desítky-krát za
  snímek), takže Python smyčka malých `fill_rect` volání uvnitř se násobí počtem stripů — změřeno,
  že raycaster zpomalila 8×. Předpočítej tvary jednou při *změně* do uint16 polí a předej celou dávku
  do C **jedním voláním na strip**: `view.vspans(...)` pro svislé spany (sloupce stěn, gradienty,
  bary) nebo `view.fill_triangles(...)` pro trojúhelníky.
## 5. Nealokuj každý snímek

Vytváření objektů ve smyčce krmí garbage collector a `gc.collect()` může stát desítky milisekund —
viditelné škubnutí. Takže:

- Střely, nepřátele a bonusy ber z pevného [`picogame_pool.Pool`](/cs/helpers/data/), nikdy
  `Sprite(...)` za snímek.
- Objekty a buffery recykluj, nestav je znovu; uprav textu labelu, nevytvářej ho nanovo.
- Vyhni se stavění dočasných seznamů, tuplů a řetězců uvnitř smyčky.

## 6. Posílej `.mpy`, ne velké `.py`

Zkompiluj hru přes `mpy-cross` (nebo to nech na balíčcích). Zkompilovaný bytecode startuje rychleji a
vyhne se churnu haldy z kompilace velkého zdrojáku na desce — což může samo hodit `MemoryError`. Viz
[Spuštění na zařízení](/cs/hardware/).

## Měř, nehádej

Některé „samozřejmé" úpravy nedělají nic — třeba zvednutí limitu dirty-rectů se naměřilo jako bez
rozdílu, protože dobře postavená scéna není limitovaná počtem obdélníků. Než začneš optimalizovat,
zjisti, kam čas reálně jde:

- V **[desktopovém simulátoru](/cs/simulator/)** `python3 sim/run.py tvojehra.py --profile` vypíše
  počty volání funkcí a alokace na snímek.
- Na hardwaru sleduj čas snímku přes FPS ukazatel (`picogame_debug`) a měň jednu věc po druhé.

Optimalizuj tu smyčku, kterou profil označí za horkou — ne tu, na kterou jsi tipoval.
