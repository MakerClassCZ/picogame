---
title: Slovníček pojmů
description: Srozumitelné definice herních pojmů, které se v dokumentaci objevují — psané pro lidi, kteří znají CircuitPython, ale s hrami teprve začínají.
sidebar:
  order: 2
---

Tento slovníček vysvětluje herní pojmy používané v dokumentaci. Kde to pomůže, propojuje je
s podobnými pojmy z CircuitPython `displayio`.

## Sprite

Pohyblivý obrázek: hráč, nepřítel, střela, mince. Obaluje `Bitmap` a má pozici, kterou každý snímek
měníš. Nejbližší obdoba v `displayio`: jeden `TileGrid`, který přesouváš, jenže sprite v picogame navíc
umí překlápět, škálovat, rotovat a animovat.

## Vrstva (Layer)

Jedna věc, kterou scéna kreslí. Vrstvy leží nad sebou jako průhledné fólie a vykreslují se
v pořadí, ve kterém je přidáš. Vrstvou může být sprite, tilemapa, Canvas nebo StripDraw.

## Tilemap

Velká plocha poskládaná z malé sady opakujících se dlaždicových obrázků (pozadí, cihlová zeď,
mřížka úrovně) uložená jako **1 bajt na buňku** (číslo dlaždice), takže je mnohem levnější než jeden
sprite na buňku. Jako mřížka buněk `displayio` `TileGrid`.

## Scene a retained režim

picogame pracuje v **retained režimu**: objekty přidáš jednou pomocí `scene.add(...)` a engine si je
pamatuje. V každém snímku změníš jejich stav a zavoláš `scene.refresh()`. `Scene` je kontejner,
který drží všechny vrstvy.

V **immediate režimu** naopak vyvoláš kreslení přímo a engine si výsledný stav nepamatuje.

## Dirty region

Oblast, která se od minulého snímku změnila a potřebuje překreslit. Protože si scéna pamatuje
stav vrstev, může překreslit jen tyto oblasti místo celé obrazovky.

## Blit

Zkopírovat pixely obrázku na obrazovku (nebo do jiného kreslicího povrchu). `displayio` to schovává
za Groupy a TileGridy, takže jsi to možná nikdy nenapsal; v picogame je to základní operace
„otiskni sem tuhle bitmapu".

## Herní smyčka (Game loop)

Opakující se sled kroků: **přečti vstup → aktualizuj svět → vykresli → chvíli počkej**.
Všechny hry v picogame používají tuto základní strukturu.

## Snímek (Frame)

Slovo *frame* se používá ve dvou významech:

- **snímek obrazovky** — jeden průchod herní smyčkou a jedno vykreslení;
- **snímek animace** — jeden obrázek v atlasu bitmapy, vybraný přes `sprite.frame`.

## Kotevní bod (Anchor)

Bod otáčení, kolem kterého sprite škáluje a rotuje, zadaný jako zlomky jeho velikosti: `(0.5, 0.5)`
je střed, `(0.5, 1.0)` střed spodní hrany. Pozice a rotace sprite se měří vůči tomuto bodu.

## AABB

Test překryvu obdélníků, zkratka pro *axis-aligned bounding box*, prostý (nerotovaný) obdélník
nakreslený kolem sprite. „Překrývají se tyhle dva AABB?" je nejlevnější způsob, jak zjistit, jestli
do sebe dvě věci narazily.

## Pool objektů

Pevná sada spritů, kterou vytvoříš **jednou** a znovu používáš. Průběžné vytváření a rušení objektů
zatěžuje garbage collector a může fragmentovat RAM. `picogame_pool.Pool` se hodí pro střely,
nepřátele, mince a další objekty, které se často objevují a mizí.

## Barva v pořadí pro přenos (Wire-order colour)

Pořadí bajtů, které panel očekává při přenosu přes SPI. Není to totéž jako zápis `0xRRGGBB`.
Barvy vždy vytvářej přes `pg.rgb565(r, g, b)`; nezapisuj je jako surové hexadecimální hodnoty.

## Herní odezva (Juice)

Drobné efekty, které dávají hráči okamžitou odezvu: záblesk při zásahu, otřes obrazovky, jiskra
nebo zvuk u důležité akce. V anglických materiálech se pro ně používá výraz *juice*.

## Parallax

Vrstvy pozadí, které scrollují **pomaleji** než popředí, čímž vytvářejí iluzi hloubky (představ si
vzdálené kopce plující kolem pomaleji než krajnice silnice).

## Coyote time a předregistrace skoku

Dvě techniky pro vstřícnější ovládání. **Coyote time** dovolí skočit ještě několik snímků po opuštění
hrany. **Jump buffering** si zapamatuje skok stisknutý těsně před dopadem. Obě můžeš vytvořit pomocí
`picogame_input.Timer`.

## Záznam nejlepšího kola (Ghost lap)

V závodních hrách průsvitné přehrání tvého nejlepšího kola zobrazené na trati, takže můžeš závodit
proti vlastnímu rekordu.

## Stavový automat (State machine)

Hra přepíná mezi pojmenovanými režimy, například titulní obrazovkou, hraním a koncem hry.
Proměnná `state` určuje, která část smyčky se aktualizuje a vykresluje.

## Stride

Kolik **pixelů** zabírá jeden řádek zdrojových dat bitmapy. Nech ho `0` a engine předpokládá, že
data jsou těsně zabalená (jeden řádek je `šířka × frames` pixelů, celý horizontální atlas); nastav
ho jen tehdy, když míříš na **podokno většího obrázku**, kde je každý řádek v paměti širší než ta
část, kterou kreslíš. Argument konstruktoru `Bitmap(...)`.

## StripDraw a Canvas

Dva způsoby, jak kreslit vlastní pixely, vyvážené pamětí (celý obrázek viz
[Drawing paths](/cs/concepts/drawing-paths/)):

- **Canvas** — retained pixelový buffer (`šířka × výška × 2` bajty), do kterého kreslíš a znovu ho
  používáš; správná volba pro panel, který se mění jen zřídka.
- **StripDraw** — vrstva bez vlastního pixelového bufferu, která kreslí do právě zpracovávaného
  pruhu. Neuchovává žádná pixelová data, ale její callback spotřebuje CPU při každém překreslení.
  Hodí se pro celosnímkové efekty a dynamický HUD nebo text.
