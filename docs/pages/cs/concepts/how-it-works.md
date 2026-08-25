---
title: Jak picogame funguje
description: Scény, herní smyčka a vykreslování změněných oblastí v picogame.
sidebar:
  order: 1
---

picogame si mezi snímky pamatuje objekty ve scéně. Ty změníš jejich stav, zavoláš
`scene.refresh()` a engine překreslí dotčené oblasti. Tato stránka vysvětluje tento princip
a herní smyčku, která ho používá.

Neznámé herní pojmy najdeš ve [slovníčku](/cs/concepts/glossary/).

## Hlavní myšlenka: popiš scénu, pak řekni, co se pohnulo

Většina obrazovky hry se mezi snímky nemění: pozadí zůstává na místě, pohybuje se jen pár
věcí. picogame je kolem toho postavený.

**Scénu popíšeš jednou** (tyhle sprity, tahle tilemapa, tohle pozadí) a pak každý snímek
jen **změníš to, co se pohnulo** (`ball.x += 3`) a zavoláš `scene.refresh()`. Engine zjistí,
které malé obdélníky se změnily (každý z nich je [dirty region](/cs/concepts/glossary/)),
a **překreslí jen je**. Nic se nepohnulo? Na displej se nic
neposílá.

Páky, které hru drží na stálých 30 FPS i jak roste, najdeš na [Výkon](/cs/performance/).

Množství práce proto obvykle odpovídá tomu, kolik se *změnilo*, ne velikosti obrazovky.
Posun kamery a vrstvy označené jako `always_dirty` jsou hlavní výjimky: překreslí celou hrací
plochu. Oblasti sleduje engine za tebe.

![Retained-mode: pohneš jedním spritem a refresh() překreslí jen dirty rectangle kolem něj — statické pozadí zůstává nedotčené](/img/howitworks_dirtyrect.png)

## Stavební díly, ze kterých skládáš scénu

Do scény můžeš vložit tyto hlavní objekty:

- **Sprite** — pohyblivý obrázek: hráč, nepřítel, střela, mince. Má pozici, lze ho
  překlopit, animovat po snímcích, zvětšovat a otáčet.
- **Tilemap** — velká mřížka složená z malé sady obrázků dlaždic: úroveň, dlážděné pozadí,
  cihlová zeď. Levná, protože mřížka ukládá jedno číslo na buňku místo každého pixelu.
- **Bitmap** — samotný obrázek, který sprite nebo dlaždice kreslí. Můžeš ho vygenerovat v kódu (kruh,
  obdélník) nebo ho převést z PNG.
- **Scene** — kontejner, který drží všechno výše uvedené a kreslí to v pořadí. Každá kreslená věc
  je [vrstva](/cs/concepts/glossary/) (jedna věc, kterou scéna kreslí, naskládaná zezadu dopředu);
  přidáváš do něj věci a každý snímek ho obnovíš.
- **Kamera** — scéna má pohled, kterým můžeš pohybovat (`set_view`), takže svět může být větší
  než obrazovka a posouvat se, jak hráč chodí.

Pro vlastní kreslení slouží **Canvas**, pro kreslení po pruzích **StripDraw** a pro částicové
efekty **Particles**. S výběrem pomůže [průvodce funkcemi](/cs/features/).

## Herní smyčka

Každá hra v picogame má stejný tvar:

1. **Čti vstup** — která tlačítka jsou stisknutá.
2. **Aktualizuj** — pohni věcmi, spusť herní pravidla, vytvoř a odeber objekty.
3. **Obnov** — `scene.refresh()` vykreslí změny.
4. **Počkej** — hodiny omezí snímkovou frekvenci, aby hra běžela stálou rychlostí.

```python
while True:
    buttons.poll()           # 1. vstup
    ball.x += speed            # 2. aktualizace
    scene.refresh()            # 3. vykresli, co se změnilo
    clock.tick()               # 4. udrž snímkovou frekvenci
```

![Herní smyčka: přečti vstup, aktualizuj, refresh() vykreslí změny, tick() udrží snímkovou frekvenci, a opakuj](/img/howitworks_loop.png)

Kolize, zvuk, skóre a ostatní herní pravidla patří do kroku 2.

Tenhle čtyřkrokový tvar je univerzální. Jakmile má hra víc obrazovek (title / hra / konec) a potřebuje
restart, drž její stav v jednom objektu a přesuň tuhle smyčku do funkce `main()` — ten tvar (a proč)
najdeš v [Herních vzorech](/cs/concepts/patterns/).

## Začni bez hardwaru

Stejný herní kód můžeš spustit i mimo zařízení. Bez instalace použij [Playground](/cs/playground/),
pro lokální práci [desktopový simulátor](/cs/simulator/). Prohlížeč, simulátor a zařízení sdílejí
API, ale liší se v limitech RAM, časování, vstupu, zvuku a efektech panelu. Proto hru během vývoje
pravidelně zkoušej také na cílovém hardwaru.

## Kam dál

Začínáš? Postav [první hru](/cs/start/first-game/) a pokračuj tutoriály. Průvodce funkcemi
a referenci otevři, když vybíráš nástroj nebo hledáš přesnou signaturu.

**Znáš jiný engine nebo `displayio`?** Přejdi na [mapu pojmů](/cs/concepts/coming-from/),
[slovníček](/cs/concepts/glossary/) a potom na [referenci](/cs/reference/).

- **[Vytvoř svou první hru](/cs/start/first-game/)** — vyzkoušej princip za pět minut.
- **[Tutoriály](/cs/tutorials/)** — tři hry, v každém kroku jedna nová myšlenka.
- **[Průvodce funkcemi](/cs/features/)** — vyber nástroj podle úkolu.
- **[Referenční příručka API](/cs/reference/)** — ověř přesnou signaturu.
