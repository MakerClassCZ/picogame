---
title: "Text a uživatelské rozhraní"
description: "Bitmapový text, popisky HUD, dialogová okna, nabídky s kurzorem a upravitelné volby."
---

Tyto moduly vykreslují bitmapový text a nabízejí HUD, dialogy, nabídky, kurzor v mřížce a upravitelné volby. Signatury najdeš v [referenci](/cs/reference/) a úplné příklady v tutoriálech.

## picogame_font

Modul vykreslí font typu `fontio`, obvykle `terminalio.FONT`, do bitmapy PAL8. Použij ho pro text, který se má stát spritem nebo okamžitě vykresleným popiskem.

Pokud chceš jen skóre v rohu, nejjednodušší volbou je `Label`; širší přehled widgetů (vrstvy scény vs. okamžité widgety) najdeš níže v části [picogame_ui](#picogame_ui).

- `render_text(pg, font, text, fg, bg=None)` - sestaví z `text` bitmapu PAL8 a vrátí `(bmp, w, h)`. `fg` a `bg` jsou barvy z `pg.rgb565(...)` v pořadí pro přenos. `bg=None` ponechá index palety 0 průhledný; neprůhledné pozadí při překreslení zakryje předchozí text.
- `render_text_pal(pg, font, text, fg, bg=None)` - vrátí navíc paletu jako `(bmp, w, h, palette)`. Změnou `palette[1]` můžeš změnit barvu popředí bez nového sestavení bitmapy.
- `Label(pg, font, x, y, fg, bg)` - okamžitě vykreslovaný popisek pro obrazovku, jejíž obnovování řídíš sám.
  - `.set(text)` - překreslí jen tehdy, když se text změnil; vrátí `True`, pokud ano, `False`, pokud přeskočil. Ne-řetězce převede přes `str()`.
  - `.move(x, y)` - přemístí a vynutí překreslení na novém místě při dalším `set`/`draw`.
  - `.draw(display, buffer)` - překreslí obdélník popisku jedním voláním `pg.render()`.
  - `.w`, `.h` - rozměr posledního vykresleného textu v pixelech.

```python
import picogame_font, terminalio
hud = picogame_font.Label(pg, terminalio.FONT, 4, 4,
                          pg.rgb565(255, 255, 255), BG)
shown_score = -1                # stínová int: poslední hodnota popisku
# každý snímek po vykreslení obrazovky:
if score != shown_score:        # formátuj jen při změně čísla
    shown_score = score
    hud.set("SCORE %06d" % score)
hud.draw(picogame_game.display(), bufA)   # překreslí jen oblast popisku
```

![picogame_font.Label — okamžitý HUD text](/img/ui_label.png)

:::note[Pozor]
po změně `bmp.palette` nebo pole vráceného z `render_text_pal()` se nová barva projeví při následujícím překreslení. Nad živou scénou použij `picogame_ui.SceneLabel`; okamžitý `Label` není součástí `scene.refresh()`.
:::

### Glyfy navíc: `ExtraFont`

`terminalio.FONT` umí jen ASCII. `picogame_font.ExtraFont` ho rozšíří o glyfy z jednoho či více malých
BDF souborů, hledaných jako **fallback** — nejdřív vestavěný font, pak každý BDF v pořadí, takže soubory
navíc glyfy jen *přidávají* a s běžným textem splývají. V `lib/fonts/` jsou dvě sady (vyříznuté z vlastního
Terminus buildu CircuitPythonu, ze kterého pochází i `terminalio.FONT`):

- **`picogame_cz.bdf`** — česká diakritika (á č ď é ě í ň ó ř š ť ú ů ý ž a velká písmena).
- **`picogame_symbols.bdf`** — herní symboly: šipky, srdíčka, výplně block/shade, trojúhelníky, ✓/✗, ♥ ♫ ☼, ° ½ × ÷ a další:

![Sada herních glyfů picogame_symbols.bdf, u každého jeho Unicode kód](/img/extrafont_symbols.png)

```python
import picogame_font
font = picogame_font.ExtraFont("/lib/fonts/picogame_cz.bdf", "/lib/fonts/picogame_symbols.bdf")
bmp, w, h = picogame_font.render_text(pg, font, "Život 3  ♥♥♥  →", fg)
```

`ExtraFont` předej všude, kde tento modul bere font (`render_text`, `render_text_pal`, `Label` a widgety
`picogame_ui` na nich postavené). Glyfy se načtou hned (~20 B na glyf; sada 30 glyfů je pod 1 KB).

**Omezení:** `ExtraFont` je font *na straně Pythonu* jen pro render cesty tohoto modulu. **Nativní C cesta
textu** (`picogame.Canvas.text`, a tedy `picogame_ui.SceneLabel` / `HudBar` a `view.text` u `StripDraw`)
ověřuje ve firmwaru `fontio.BuiltinFont` a `ExtraFont` **nepřijme** — pro glyfy navíc použij cestu
`render_text`/`Label`. Vlastní sadu vyrobíš přes `tools/make_bdf_subset.py`.

## picogame_bitfont

Tento bitmapový font 8×8 používá čtyři odstíny a v kódech 0–31 obsahuje šipky, srdce, hvězdu, notu a znaky pro rámečky. Kódy od 32 pokrývají ASCII. Obtažení zvyšuje čitelnost průhledného textu nad herním světem.

- `render_text(pg, text, fg=None, outline=None, mid=None, bg=None)` - vykreslí `text` do bitmapy PAL8 a vrátí `(bitmap, w, h)`. Čtyři odstíny odpovídají `0 -> bg` nebo průhlednost, `1 -> outline`, `2 -> mid` a `3 -> fg`. Výchozí barvy jsou bílá, černá a středně šedá ve formátu RGB565 pro přenos. Více řádků oddělíš `\n`.
- Konstanty symbolů (jednoznakové řetězce, které zřetězíš do textu): `ARROW_U`, `ARROW_D`, `ARROW_R`, `ARROW_L`, `BOXX`, `STAR`, `HEART`, `BALL`, `NOTE`.
- `GLYPH_W`, `GLYPH_H` - obě mají hodnotu `8` a udávají rozměr buňky znaku.

```python
import picogame_bitfont as bf
bmp, w, h = bf.render_text(pg, "LIVES " + bf.HEART * 3)  # bílý, obtažený, průhledný
spr = pg.Sprite(bmp, x, y)                               # umísti kamkoli
spr.scale = 2                                            # zvětší text
```

![picogame_bitfont — obrysový průhledný text nad světem](/img/ui_bitfont.png)

:::note[Pozor]
modul vrací bitmapu, ale nemá třídu popisku. Příslušný `Sprite` vytvoř a spravuj sám. Každý vykreslený řetězec má vlastní pixelový buffer PAL8; volbu mezi trvalým textovým spritem a okamžitým textem popisuje [paměť](/cs/memory/).
:::

## picogame_ui

Widget vyber podle toho, kdo spravuje jeho pixely:

- `SceneLabel`, `SceneBox` a `SceneMenu` jsou pevné vrstvy scény. `scene.refresh()` je podle potřeby překreslí, proto je použij uvnitř živé nebo posouvané scény.
- `picogame_font.Label`, `TextBox` a `Menu` kreslí okamžitě přes `pg.render()`. Patří na obrazovku, jejíž obnovování řídíš sám. `HudBar` také kreslí okamžitě, ale používá okraj rezervovaný mimo scénu.

Vyber podle toho, kdo spravuje pixely:

| Situace | Třída |
|---|---|
| Statická obrazovka, kterou překreslíš sám (titulek, konec hry, HUD, který sám obnovuješ) | `Label` |
| Živá, posouvaná scéna, kde se HUD posouvat **nesmí** | `SceneLabel` |
| Rezervovaný okrajový bar / stavový pruh | `HudBar` |
| Přechodný dialog / okno se zprávou nad živým světem | `SceneBox` |
| Dialogové, soubojové nebo nabídkové okno na statické obrazovce | `TextBox` |

Widgety s metodou `tick()` vracejí vybraný index nebo buňku po stisku **A**, `ui.CANCEL` (`-2`) po stisku **B** a během pohybu `None`. Pevnou vrstvu popisuje [formát scény](/cs/scene-format/) a tlačítka [hardware](/cs/hardware/).

**`SceneLabel(scene, pg, font, x, y, fg, bg)`** - jednořádkový text připnutý k obrazovce nad posouvaným světem.
- `.set(text)` - při změně vymění bitmapu spritu. Prázdný řetězec sprite skryje a scéna překreslí jeho původní dirty region.
- `.reserve(chars)` - předem rezervuje buffer až pro `chars` znaků. Hodí se pro dlouhý text, který se poprvé zobrazí až po možné fragmentaci heapu. Samo nic nezobrazí. Viz [paměť](/cs/memory/).

**`SceneBox(scene, pg, font, x, y, w, h, fg, bg, nlines=3, key=None, border=None)`** - víceřádkový dialogový nebo stavový panel nad živou scénou. Callback `StripDraw` skládá panel, rám a text bez trvalé pixelové plochy. Parametr `border` přidá vystouplý rám. Geometrie: 8 px odsazení vlevo i vpravo, 7 px nahoře, řádky po `LINE_H` (12 px) - do řádku se vejde `(w - 16) // 6` znaků vestavěného 6px fontu (`(200 - 16) // 6 = 30`) a box potřebuje `h >= 14 + 12 * nlines`. Delší řádek se **neořízne** - přeteče přes pravý okraj (simulátor upozorní); zalom ho nebo box rozšiř.
- `.show(lines)` - nastaví řádky a zobrazí panel. Volej při změně obsahu, ne v každém snímku. Vejde se jen prvních `nlines` řádků, další se zahodí (simulátor upozorní) - vytvoř box s větším `nlines`, nebo text rozděl.
- `.hide()` - udělá panel úplně průhledný a vymaže řádky.
- `.visible` - `True`, dokud je panel zobrazený; přiřazení ho přepne jako `show()`/`hide()`, ale text nechá být.
- `.set_line(i, text)` - aktualizuje jeden řádek na místě (bez překreslení Canvasu/rámu).

![picogame_ui.SceneBox — dialogový box nad živou scénou](/img/ui_dialog.png)

**`HudBar(pg, display, buffer, x, y, w, h, bg)`** - okamžitě vykreslený HUD v okraji rezervovaném pomocí `Scene(..., top=/bottom=)`. `draw()` volej pouze po změně obsahu. Objekt drží texty popisků a odkazy na ikony, ale ne pixelovou plochu velikosti panelu. `buffer` je vykreslovací buffer ze setupu na SPI cílech; na framebufferu může být `None`.
- `.add(sprite)` - uloží ikonový sprite (srdíčka, ukazatele) do baru; vrátí ho. Při `draw()` se vykreslí na svém x/y.
- `.label(font, x, y, fg, text=" ")` - přidá textové pole a vrátí objekt `_HudLabel`, nikoli sprite. Text změň přes `handle.set(text)`.
- `.draw()` - vykreslí pozadí, ikony a text jedním `pg.render()`. Displej, buffer a rozměry si objekt uložil při vytvoření.

```python
hud = ui.HudBar(pg, picogame_game.display(), bufA, 0, 0, W, BAR, pg.rgb565(10, 12, 24))
hud_l = hud.label(terminalio.FONT, 4, 3, INK, "SCORE 0   LIVES 3")
hud.draw()
# později, jen při změně:
hud_l.set("SCORE %d   LIVES %d" % (score, lives))
hud.draw()
```

![picogame_ui.HudBar — stavový pruh v rezervovaném pásu](/img/ui_hudbar.png)

**`TextBox(pg, font, x, y, w, h, fg, bg, maxlines=6)`** - víceřádkový panel pro statický dialog, soubojovou obrazovku nebo nabídku.
- `.draw(display, buffer, lines, force=False)` - přeskočí překreslení, když se `lines` nezměnily; když už kreslí, jdou bg a každý řádek ven v **jednom** `pg.render` (bez probliknutí prázdné výplně). Předej `force=True` poté, co se obrazovka pod ním vymazala (např. celoobrazovkový `pg.render`).
- `.draw_line(display, buffer, i, text)` - překreslí jeden řádek na místě, atomicky.

**`Menu(pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None, paged=True)`** - okamžitá nabídka s kurzorem postavená nad `TextBox`. Tlačítka UP a DOWN se automaticky opakují. `rows=None` zobrazí všechny položky; menší hodnota vytvoří posouvané okno. S `paged=True` se při překročení okraje posune o celou stránku. Argumenty za `*` lze zadat pouze jménem.
- `.tick(btn)` - vrátí vybraný index na A, `ui.CANCEL` na B, jinak `None`.
- `.draw(display, buffer, force=False)` - překreslí jen to, co se změnilo (nic / 2 dotčené řádky při pohybu kurzoru / celý box při scrollu). `force=True` překreslí bezpodmínečně po vymazání.

```python
bmenu = ui.Menu(pg, terminalio.FONT, 8, H - 72,
                ["ATTACK", "MAGIC", "HEAL", "FLEE"], WHITE, NAVY)
# každý snímek:
act = bmenu.tick(btn)          # index po A, ui.CANCEL po B, jinak None
bmenu.draw(picogame_game.display(), bufA)
```

**`SceneMenu(scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None, border=None, paged=True)`** - stejná nabídka postavená na `SceneBox` pro živou scénu, například pro bojové akce. Navigace a stránkování odpovídají `Menu`.
- `.show(sel=0)` - zobrazí ho (resetuje kurzor). Od té chvíle ho vykresluje scéna - žádné volání `draw()`.
- `.hide()` - skryje ho.
- `.tick(btn)` - stejný kontrakt návratu jako `Menu`; překreslí jen řádky, které se změnily.

![picogame_ui.SceneMenu — kurzorová nabídka nad scénou](/img/ui_menu.png)

**`GridCursor(cols, rows, tx=0, ty=0, wrap=False)`** - logický 2D kurzor pro bojiště, inventář nebo hru typu match-3. Řídí pohyb, potvrzení a zrušení; mřížku a zvýraznění na `(cursor.tx, cursor.ty)` vykresli sám. `wrap=True` přechází přes okraj na opačnou stranu, jinak polohu omezí.
- `.tick(btn)` - vrátí n-tici `(tx, ty)` na A, `ui.CANCEL` na B, jinak `None`.
- `.tx`, `.ty` - aktuální buňka.
- `.index` (property) - `ty * cols + tx`, šikovné pro indexování plochého seznamu.

```python
cur = ui.GridCursor(N, N)               # herní plocha N × N
# každý snímek:
pick = cur.tick(btn)                    # (tx, ty) po A, ui.CANCEL po B, jinak None
# zvýraznění na (cur.tx, cur.ty) vykresli sám
```

:::note[Pozor]
okamžité `Menu` nebo `TextBox` není součástí scény a pozdější `scene.refresh()` ho může přepsat. Nad živou scénou použij odpovídající widget `Scene*`. Výchozí šířka nabídky odhaduje přibližně 11 pixelů na znak; pro úzký font nebo dlouhé texty zadej `width=`. `SceneBox.show()` volej při změně obsahu, ne v každém snímku.
:::

## picogame_options

`OptionsMenu` doplňuje do `SceneBox` upravitelné řádky. Hodí se pro nastavení, obchod nebo výběrovou obrazovku, která kombinuje volby, číselné kroky, přepínače a akce. Jde o vrstvu scény, takže změny hodnot zobrazí `scene.refresh()`.

- `OptionsMenu(scene, pg, font, x, y, w, rows, fg, bg, title=None, border=None)` - `rows` je seznam slovníků, každý s `kind`:
  - `choice` - `{"key", "label", "kind": "choice", "choices": [...]}`; prochází seznam voleb. Prázdné `choices` vyvolá `ValueError`.
  - `stepper` - `{"key", "label", "kind": "stepper", "value", "min", "max"}`; podporuje volitelné `"step"` s výchozí hodnotou 1 a omezuje výsledek na `min` až `max`.
  - `toggle` - `{"key", "label", "kind": "toggle", "value": True/False}`.
  - `action` - `{"key", "label", "kind": "action"}`; nemá hodnotu a po stisku A vrátí svůj `key`.
- `.show(sel=0)` - zobrazí a vykreslí (volej jednou); `scene.refresh()` ho pak vykresluje.
- `.hide()` - skryje panel.
- `.tick(btn)` - UP a DOWN posouvají kurzor, LEFT a RIGHT mění hodnotu vybraného řádku. Volby a číselné kroky se při držení opakují, přepínač reaguje pouze na nový stisk. Na **A** vrátí `key` řádku, na **B** `ui.CANCEL`, jinak `None`.
- `.value(key)` - vrátí aktuální hodnotu řádku: řetězec pro `choice`, celé číslo pro `stepper`, `bool` pro `toggle` nebo `None` pro neznámý klíč.

```python
import picogame_options as opt
menu = opt.OptionsMenu(scene, pg, font, 40, 40, 240, [
    {"key": "diff", "label": "Difficulty", "kind": "choice", "choices": ["Easy", "Normal", "Hard"]},
    {"key": "vol",  "label": "Volume",     "kind": "stepper", "value": 7, "min": 0, "max": 10},
    {"key": "snd",  "label": "Sound",      "kind": "toggle",  "value": True},
    {"key": "done", "label": "Start",      "kind": "action"},
], WHITE, NAVY, title="OPTIONS")
menu.show()
while True:
    btn.poll()
    k = menu.tick(btn)
    if k == "done":
        diff = menu.value("diff")          # přečte aktuální hodnotu při potvrzení
    elif k == opt.CANCEL:
        menu.hide()
    scene.refresh()                        # nabídku kreslí scéna, draw() se nevolá
```

![picogame_options.OptionsMenu — editovatelné řádky nastavení](/img/ui_options.png)

:::note[Pozor]
`opt.CANCEL` a `ui.CANCEL` označují stejnou hodnotu `-2`. Protože nabídka používá `SceneBox`, zobrazí ji až `scene.refresh()`; samostatné okamžité `pg.render()` ji nevykreslí.
:::
