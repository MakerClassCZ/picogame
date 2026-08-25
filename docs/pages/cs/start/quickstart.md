---
title: Nahraj si to do zařízení
description: Nahraj firmware picogame a pak si stáhni hotový balíček her pro svou desku — naběhne launcher, ve kterém hru vybereš D-padem.
sidebar:
  label: Nahraj si to do zařízení
  order: 5
---

Dva kroky a máš na handheldu menu hotových her: jednou nahraješ firmware a pak nakopíruješ balíček pro
svou desku na disk. Nic se neprogramuje — naběhne [launcher](/cs/launcher/), ve kterém hru vybereš
D-padem.

## 1. Nahraj firmware

Firmware **je** ten engine picogame — build CircuitPythonu s vestavěným nativně-C modulem. Nahraješ ho
jednou na desku.

Stáhni `.uf2` pro svou desku z [Podporovaného hardwaru](/cs/supported-hardware/#firmware-ke-stažení),
podrž **BOOTSEL** při zapojení desky a přetáhni `.uf2` na disk, který se objeví. Deska se restartuje a
naběhne jako disk **`CIRCUITPY`**.

## 2. Stáhni balíček pro svou desku

Každý balíček je hotový obsah disku `CIRCUITPY` — launcher, hry a dema (zkompilované `.mpy`), pomocné
knihovny a fonty. Vyber ten pro svou desku a **rozbal ho na disk `CIRCUITPY`**.

- **[RP2040 — PicoPad, holé Pico](/download/picogame-rp2040.zip)** — sada pro úzkou RAM (8 her +
  10 dem) vyladěná, aby se vešla do RP2040. Tady začni na PicoPadu nebo holém Picu.
- **[RP2350 — PicoPad 2, Pico 2](/download/picogame-rp2350.zip)** — celé portfolio (všechny hry i dema)
  s intry, pro desky třídy RP2350 s rezervou RAM.
- **[Fruit Jam](/download/picogame-fruitjam.zip)** — celé portfolio plus `settings.toml`, který nastaví
  hlasitosti audia a DVI displej Fruit Jamu.

Nevíš, jaký čip má tvoje deska? Podívej se na [Podporovaný hardware](/cs/supported-hardware/).

## 3. Hraj

Odpoj disk a restartuj desku. Launcher vypíše hry — **NAHORU/DOLŮ** posun, **A** spustit, tlačítko
**RESET** na desce návrat do menu.

## Dál

- Přidat vlastní hru do menu, nebo jak launcher hry hledá → [Herní menu](/cs/launcher/).
- Chceš spíš hru postavit než hrát balíčky? → [Tvoje první hra](/cs/start/first-game/) a
  [Spuštění na zařízení](/cs/hardware/).
