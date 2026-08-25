---
title: "Ukládání a práce s pamětí"
description: "Uložení hodnot do NVM, opakované využití předalokované paměti a načítání snímků animace z flash paměti."
---

Tyto moduly ukládají malé hodnoty, rezervují znovu použitelnou paměť a načítají snímky animace z flash paměti. Signatury najdeš v [/cs/reference/](/cs/reference/) a paměťový model posledních dvou modulů v [/cs/memory/](/cs/memory/).

## picogame_save

Toto strukturované úložiště používá `microcontroller.nvm`, tedy vyhrazenou oblast flash paměti zapisovatelnou z `code.py`. Hodí se pro nejlepší skóre, odemčenou úroveň nebo nastavení, která mají přežít vypnutí. Na podporovaných sestaveních pro RP2040 má oblast 4 KiB; třída při vytvoření kontroluje skutečnou dostupnou velikost.

NVM je jedna oblast sdílená všemi programy v zařízení, proto každá hra předává vlastní `key`. Jeho otisk se uloží do hlavičky a při načítání zkontroluje. Pokud oblast obsahuje data jiné hry nebo starší záznam, `load()` vrátí výchozí hodnoty.

Data popiš uspořádaným slovníkem `name -> (formát struct, výchozí hodnota)`. Běžné formáty jsou `"B"` pro 0–255, `"H"` pro 0–65535 a `"I"` pro 0 až 2^32−1. Malá písmena `b`, `h` a `i` označují hodnoty se znaménkem.

- `Save(key, schema, *, offset=0)` - vytvoří úložiště. `key` je název hry jako `str` nebo `bytes`. Parametr `offset` lze zadat pouze jménem; změň ho jen tehdy, když více instalovaných her potřebuje oddělené části NVM. Pokud NVM není dostupná, metoda vyvolá `RuntimeError`; pokud se schéma nevejde, vyvolá `ValueError`.
- `load()` - vrátí slovník uložených hodnot, nebo čerstvou kopii výchozích hodnot, pokud je slot prázdný, poškozený nebo zapsaný jinou hrou (neshoda klíče). Na špatná data nikdy nevyhodí výjimku.
- `save(values)` - uloží slovník. Chybějící klíče se doplní výchozí hodnotou ze schématu. Zapíše kontrolní součet, aby ho pozdější `load()` mohl detekovat jako poškozený.
- `reset()` - zapíše výchozí hodnoty zpět pod klíčem této hry.
- `defaults()` - čerstvý slovník pouze s výchozími hodnotami, bez čtení NVM.

```python
import picogame_save

# uchová nejlepší čas kola v sekundách i po restartu
store = picogame_save.Save("ghostrace", {"best_t": ("H", 0)})
best_t = store.load()["best_t"]              # 0 = zatím bez rekordu

# později, při novém rekordu:
if best_t == 0 or secs < best_t:
    best_t = secs
    store.save({"best_t": best_t})           # zůstane uložený i po vypnutí
```

:::note[Pozor]
každé `save()` zapisuje do flash paměti, proto ho nevolej v každém snímku. Ukládej při významné události, například na konci hry, při novém rekordu nebo po změně nastavení. Celý záznam včetně hlavičky a kontrolního součtu se musí vejít do NVM.
:::

## picogame_arena

Aréna si na začátku vyhradí jeden souvislý blok a později z něj vydává menší části. Použij ji, když různé scény nebo režimy potřebují velké buffery `Canvas`, ale ne současně. Garbage collector v MicroPythonu heap nepřesouvá, takže opakované vytváření a rušení velkých bufferů může nechat dost volné paměti celkem, ale žádný dostatečně velký souvislý blok.

- `Arena(pixels)` - alokuje arénu. Velikost je v pixelech; rezervuje `pixels * 2` bajtů (RGB565). Udělej to brzy, než se halda fragmentuje.
- `canvas(w, h, transparent=None)` - vrátí `pg.Canvas` nad další částí arény. Začátek automaticky zarovná na 16 bitů.
- `alloc(nbytes, align=1)` - vrátí část typu `memoryview` o délce `nbytes`, například pro čtení souboru, pracovní data parseru nebo zvukový blok. `align` zarovná začátek; použij `align=2` pro 16bitová data nebo `align=4` pro přístup po slovech. Pokud se data nevejdou, metoda vyvolá `MemoryError`.
- `mark()` - vrátí aktuální pozici v aréně. Ulož si ji při vstupu do dočasného režimu nebo scény.
- `release(mark)` - vrátí arénu na dřívější značku a uvolní všechny pozdější části. Vnořené značky uvolňuj v opačném pořadí. Objekty nad uvolněnými částmi už nepoužívej.
- `reset()` - uvolní všechny dosud vydané části. Objekty vytvořené před resetem už nepoužívej.
- `free()` - bajty stále dostupné v aréně.

```python
import picogame_arena

# jedna aréna pro velké plochy, rezervovaná ještě na souvislé haldě;
# scény, které neběží současně, sdílejí stejnou paměť
ARENA = picogame_arena.Arena(320 * 80)       # 320x80 px = 51 200 bytes

def big_canvas(w, h, transparent=None, first=False):
    if first:
        ARENA.reset()                        # použije arénu znovu pro tuto scénu
    return ARENA.canvas(w, h, transparent=transparent)
```

:::note[Pozor]
aréna vyžaduje firmware `Canvas` s argumentem `buffer=`. Simulátor si nyní vytváří vlastní úložiště plátna, takže omezení fragmentace se projeví na [hardwaru](/cs/hardware/). Po `reset()` nebo `release()` nepoužívej objekty nad uvolněnými částmi; nové alokace mohou jejich data přepsat.
:::

## picogame_stream

`StreamSheet` drží v RAM jediný snímek PAL8 a požadovaný snímek čte ze souboru ve flash paměti. Animace 64×100 s 11 snímky tak potřebuje 6 400 bajtů obrazových dat místo 70 400 bajtů pro všechny snímky. V souboru musí být vždy souvisle uloženo `w*h` bajtů jednoho snímku. Vytvoř ho pomocí `tools/pack_sheet.py`.

- `StreamSheet(pg, path, w, h, frames, palette, transparent=None)` - otevře `path`, alokuje buffer pro jeden snímek, sestaví `pg.Bitmap` (PAL8) nad ním a načte snímek 0. `palette` je tabulka barev pro PAL8 data.
- `.bitmap` - jediný `pg.Bitmap`, jehož pixely se přepisují na místě. Použij ho při vytvoření `pg.Sprite`.
- `use(i)` - načte snímek `i`, přičemž index obalí modulo `frames`, do sdíleného bufferu a vrátí bitmapu. Ze souboru čte jen při změně indexu.
- `close()` - zavře podkladový soubor.

```python
import picogame_stream

sheet = picogame_stream.StreamSheet(pg, "jill.bin", 64, 100, 11, PAL, transparent=0)
player = pg.Sprite(sheet.bitmap, x, y)
# při každém posunu animace:
sheet.use(frame_index)        # načte snímek do sdíleného bufferu
player.touch()                # pixely se změnily na místě; vyžádá překreslení
```

:::note[Pozor]
po `use()` vždy zavolej `sprite.touch()`. Metoda přepisuje pixely bitmapy na místě, což nezmění žádnou vlastnost sledovanou vykreslovačem dirty regionů. Bez `touch()` může nehybný sprite dál zobrazovat předchozí snímek. Simulátor překresluje celou scénu, takže se tato chyba může projevit až na hardwaru. Princip překreslování popisuje [/cs/scene-format/](/cs/scene-format/).
:::
