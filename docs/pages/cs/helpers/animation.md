---
title: "Animace a sekvence"
description: "Animace spritů, časované sekvence a obrázky přes celou obrazovku s moduly picogame_anim, picogame_seq a picogame_cutscene."
---

Tyto tři moduly řeší animaci spritů, časované sekvence a statické obrázky přes celou obrazovku. `picogame_anim` posouvá animaci podle uplynulého času, `picogame_seq` zapisuje sekvence jako generátory a `picogame_cutscene` načítá obrázek po částech, takže nemusí držet celý snímek v Python heapu. Signatury najdeš v [/cs/reference/](/cs/reference/).

## picogame_anim

Třídě `FrameAnim` předej sekvenci a hodnotu `fps`. V každém herním snímku pak zavolej `tick(dt)` s uplynulým časem v sekundách. Položkou sekvence může být index snímku ve spritesheetu nebo samostatný objekt `Bitmap`. Animace se tak řídí časem, ne počtem průchodů smyčkou.

Modul obsahuje dvě třídy:

- **`FrameAnim(sprite, frames, *, fps=8, loop=True)`** - přehraje jednu sekvenci. `frames` je seznam nebo n-tice indexů snímků, případně objektů `Bitmap`. Sekvence se nekopíruje, proto ji za běhu neměň. `fps` určuje rychlost a `loop` lze zadat pouze jménem. Pokud sekvence není prázdná, konstruktor zobrazí `frames[0]`.
  - **`.tick(dt)`** - posune o `dt` skutečných sekund. Akumuluje čas a přepne snímek, když uplynulo dost. Pokud neloopující animace skončila nebo je `frames` prázdný, nedělá nic. Nic nevrací.
  - **`.configure(frames, fps=8, loop=True)`** - přesměruje tuto instanci na novou sekvenci a resetuje ji. Vrací `self`. Umožní ti znovu použít jednu `FrameAnim` místo alokace nové při každém přepnutí.
  - **`.reset()`** - vrátí na snímek 0, smaže příznak `done` a akumulátor času.
  - Atributy ke čtení: **`.done`** (True, když neloopující animace dosáhla posledního snímku), `.i` (aktuální index do `frames`), `.frames`, `.fps`, `.loop`.
- **`AnimatedSprite(sprite, anims)`** - sprite s pojmenovanými stavy. `anims` je slovník `{name: (frames, fps, loop)}`. Třída používá jednu instanci `FrameAnim`, takže při změně animace nealokuje další.
  - **`.play(name)`** - přepne na pojmenovanou animaci. Vyhledá `anims[name]` a přenastaví interní `FrameAnim`. Pokud už daná animace běží, nic neudělá, takže metodu můžeš volat v každém snímku.
  - **`.tick(dt)`** - posune aktuální animaci.

```python
import picogame_anim

hero = picogame_anim.AnimatedSprite(self.spr, {
    "run":  (DINO_RUN, 12, True),
    "jump": ((DINO_JUMP,), 1, False),
})
hero.play("run")
# každý snímek; dt je skutečný počet sekund od minulého snímku:
hero.play("jump" if self.jumping else "run")  # lze levně volat každý snímek
hero.tick(dt)
```

Pro jedinou sekvenci, například rotující minci, použij `FrameAnim` přímo: `spin = picogame_anim.FrameAnim(sprite, list(range(COIN_FRAMES)), fps=15)`.

:::note[Pozor]
předej skutečné `dt` v sekundách, například z `picogame_clock`, ne počet snímků. Při hodnotě `1` se animace posune o `fps` snímků při každém volání. Sekvenci `frames` za běhu neměň. `.done` se nastaví na `True` pouze pro `loop=False`.
:::

## picogame_seq

`picogame_seq` zapisuje časovanou logiku jako generátory. Každý `yield` pozastaví běh do dalšího herního snímku a každé volání `tick()` posune jeden generátor k následujícímu `yield`. Hodí se pro úvody, postupnou logiku protivníků a další děje s pevným pořadím. Menší sekvence skládej pomocí `yield from`.

Pomocníci pro generátory (volej přes `yield from`):

- **`wait(frames)`** - počká `frames` snímků.
- **`over(frames, fn)`** - v každém snímku zavolá `fn(t)`, přičemž `t` roste od `0` do `1` (přesněji `i/frames` pro `i` v `1..frames`).
- **`move_over(sprite, x, y, frames)`** - lineárně posune sprite z jeho aktuální pozice na `(x, y)` za `frames` snímků přes `sprite.move(...)`.

Spouštění sekvence:

- **`Seq(gen=None)`** - obalí jeden generátor. Pokud je `gen` `None`, začíná jako `.done`.
  - **`.start(gen)`** - nasměruje ho na (nový) generátor a smaže `done`. Vrací `self`, takže je znovu použitelný.
  - **`.tick()`** - posune na další `yield`. Zachytí `StopIteration` a nastaví `.done`. **Vrací** příznak `done` (True po skončení), takže se na něj můžeš větvit.
  - **`.done`** - True, když sekvence skončila.

```python
import picogame_seq as seq

def intro(hero, label):
    yield from seq.wait(30)
    label.set("GO!")
    yield from seq.move_over(hero, 120, hero.y, 20)   # přesun během 20 snímků

s = seq.Seq(intro(player, hud))
# každý snímek:
if not s.tick():        # posune o krok; po skončení úvodu vrátí True
    ...                 # sekvence ještě běží
```

:::note[Pozor]
`tick()` posune sekvenci k dalšímu `yield`, proto ho volej jednou za herní snímek. Vše mezi dvěma `yield` se provede v jediném snímku. Náročnější práci rozděl dalšími `yield`. Jedna instance `Seq` spouští jeden generátor; pro souběžné sekvence použij více instancí nebo je slož pomocí `yield from`.
:::

## picogame_cutscene

`picogame_cutscene` zobrazí statický obrázek přes celou obrazovku, aniž by celý zdroj načetl do Python heapu. Zdroj o rozměrech 320x240 zabere 153 600 bajtů v RGB565 nebo 76 800 bajtů v PAL8. Modul proto čte surový soubor z flash paměti po **pásech** řádků a každý pás vykreslí přes zobrazovací backend.

Dočasný zdrojový pás zabere `w * band` bajtů v PAL8 nebo `w * band * 2` bajtů v RGB565. Pro výchozí `w=320` a `band=24` je to 7 680, respektive 15 360 bajtů nad rámec vykreslovacího bufferu předaného do `show()`. Pokud se alokace nevejde, zmenši `band`. Po vykreslení už není potřeba žádný další Python objekt s celým snímkem. Ostatní náklady popisuje stránka [/cs/memory/](/cs/memory/).

Zdrojový soubor nejprve vytvoř pomocí `tools/bake_cutscene.py`. Nástroj převádí PNG na PAL8 s modulem palety nebo na řádky RGB565 v pořadí pro přenos. Formáty bitmap enginu najdeš v [/cs/scene-format/](/cs/scene-format/) a informace o displeji a tlačítkách v [/cs/hardware/](/cs/hardware/).

- **`palette(pg, rgb)`** - vytvoří paletu pro zařízení (`array('H')` barev v pořadí pro přenos) z modulu palety od `bake_cutscene.py`, seznamu trojic `(r, g, b)` nebo hotových číselných hodnot. Vytvoř ji jednou při inicializaci a dále ji používej; jinak ji `show()` sestaví při každém volání.
- **`show(pg, display, buffer, path, pal=None, w=320, h=240, scale=None, band=24, bg=0)`** - načítá obrázek z `path` po pásech a každý pás vykreslí pomocí vykreslovacího bufferu `buffer`. `pal` vybírá vstup PAL8 (1 B/px); `None` vybírá RGB565 (2 B/px). `scale=None` odvodí celočíselné zvětšení z displeje (`width // w`) a odmítne zdroj, který nevyplní obě osy. Krátký poslední pás dočistí barvou `bg`. Vrací použité zvětšení.
- **`play(pg, display, buffer, btn, path, pal=None, w=320, h=240, scale=None, band=24, caption=None, caption_lines=None, auto_hold=0, clock=None, bg=0)`** - zobrazí obrázek, doplní volitelné řádky popisku v tmavém pruhu a počká na stisk **A** nebo **B**. S `auto_hold > 0` pokračuje po daném počtu průchodů čekací smyčkou a `btn` může být `None`. Smyčku můžeš časovat instancí `picogame_clock` předanou jako `clock`.

```python
import picogame_cutscene as cut
import board

PAL = cut.palette(pg, intro_pal)                       # jednou při inicializaci
cut.play(pg, picogame_game.display(), bufA, btn, "intro.raw", pal=PAL,
         caption="Chapter 1", clock=clock)
scene.invalidate()                                     # obrázek přepsal obsah displeje
```

:::note[Pozor]
tato funkce používá immediate cestu mimo scénu. Scénu nejprve pozastav nebo zatemni a po návratu z `play()` zavolej `scene.invalidate()`, aby ji následující `refresh()` překreslil. Vstupem musí být surový soubor s řádky za sebou vytvořený nástrojem `bake_cutscene.py`; PNG nelze předat přímo. `play()` během čekání blokuje herní smyčku.
:::
