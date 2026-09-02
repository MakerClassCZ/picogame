---
title: "Efekty a herní odezva"
description: "Třesení obrazovky, přechody, plynulé změny, kamera, rastrové efekty, částice a změny palety PAL8."
---

Tyto efekty doplňují vizuální odezvu a pohyb bez ploch přes celou obrazovku. Jejich paměťové náklady se liší: `Fade` kreslí přes callback `StripDraw`, `Sky` drží tabulku barev, `Scanlines` drží jeden řádek bitmapy a funkce pro palety mění existující palety PAL8. Signatury najdeš v [/cs/reference/](/cs/reference/).

Hledáš odezvu na herní událost? Tato tabulka tě nasměruje na správný efekt; podrobnosti jsou v sekcích níže.

| Událost | Sáhni po |
|---|---|
| Malý zásah / obdržené poškození | `flash` spritu (1–3 snímky) + slabý `Shake` (`add(~0.15)`) |
| Zabití nepřítele / velký náraz | výbuch `Particles` + silnější `Shake` (`add(~0.6)`) + [hit-stop](#hit-stop-zmrazení-snímku) |
| Sebrání / naskočení skóre | „pop" přes `Tween` (blip je na [stránce o zvuku](/cs/helpers/audio/)) |
| Změna obrazovky / scény | `Fade` |
| Pohyb v nabídce / rozhraní | `Tween` |

## picogame_fx

Tyto objekty vytvoř pro danou scénu a časované efekty aktualizuj jednou za herní snímek. `Shake` a `InvertFlash` zvýrazní náraz, `Fade` obslouží přechod, `Tween` vyhladí změnu hodnoty, `Camera` sleduje svět a `Sky` nebo `Scanlines` kreslí rastrové pozadí a překryvy.

`import picogame_fx as fx`

### `fx.Shake` - doznívající třesení obrazovky

![Třesení obrazovky, které postupně dozní](/img/fx_shake.gif)

`Shake` ukládá intenzitu nazvanou trauma. Volání `add()` ji zvýší a každý `tick()` přidá náhodný posun a uloženou hodnotu sníží. Běžný posun kamery předej do `tick()`, aby oba efekty použily jediné volání `scene.set_view()`.

- `Shake(scene, max_offset=6, decay=0.03, seed=0x9E37)` - `max_offset` je maximální posun v pixelech a `decay` úbytek intenzity za snímek. Výchozí hodnoty jsou určené pro obrazovku 320×240 a 30 FPS.
- `.add(amount)` - přidá intenzitu v rozsahu 0 až 1 a výsledek omezí na 1. Před výpočtem posunu se hodnota umocní na druhou, takže slabé události mají výrazně menší účinek.
- `.tick(cam_x=0, cam_y=0)` - přidá náhodný posun k `(cam_x, cam_y)` a zavolá `scene.set_view()` s výsledkem. Dokud třesení trvá, vrací `True`.

```python
import picogame_fx as fx

shaker = fx.Shake(scene, max_offset=6)
# ...při zásahu:
shaker.add(0.8)
# ...každý snímek (bez kamery, takže zadej 0,0):
shaker.tick(0, 0)
```

:::note[Pozor]
`Shake` volá `scene.set_view()`. Pokud pohled řídí také kamera, předej její posun do `tick(cam_x, cam_y)` místo druhého volání `set_view()`. Rozměry jednotlivých displejů najdeš v [/cs/hardware/](/cs/hardware/).
:::

### Hit-stop (zmrazení snímku)

Zmrazení obrazu při velkém nárazu je běžná technika herní odezvy, engine pro ni ale **nemá žádný primitiv** — sám přeskočíš N herních tiků / volání `scene.refresh()`. Drž počítadlo `freeze` a dokud je kladné, sniž ho a proveď `continue` ve smyčce (stále volej `clock.tick()`, aby časování zůstalo plynulé).

```python
freeze = 0
# ...při velkém nárazu:
freeze = 4
# ...na začátku herní smyčky:
if freeze > 0:
    freeze -= 1
    clock.tick()
    continue
```

### `fx.Fade` - rastrový přechod, ztmavení a záblesk

![Dither přechod do černé a zpět](/img/fx_fade.gif)

Překryv `StripDraw` nanáší barvu do obdélníku pomocí uspořádaného Bayerova rastru. Nedrží žádnou obrazovou plochu. Při úrovni 0 zmenší vykreslovací obdélník na 0×0, takže nepřidává další dirty region.

- `Fade(scene, width, height, x=0, y=0, color=0, cell=8)` - pokryje obdélník `(x, y, width, height)`. `color=0` znamená černou a `cell` určuje velikost buněk rastru. Vrstva je přidaná jako `fixed=True`, proto se neposouvá s kamerou.
- `.set(level)` - okamžitě nastaví `level`, kde 0 znamená průhledný a 16 plný překryv.
- `.to(target, speed=2.0)` - mění hodnotu k `target` rychlostí `speed` úrovní za snímek. Vrací `self`.
- `.out(speed=2.0)` / `.into(speed=2.0)` - zkratky pro `to(16)` (k neprůhledné) a `to(0)` (k průhledné).
- `.dim(level=8)` - nastaví částečné ztmavení, například pod nabídkou. `.clear()` nastaví 0.
- `.pulse(level=12, speed=2.0)` - vystoupá na `level` a pak automaticky zpět na 0; plynulý celoobrazovkový záblesk. Nech `level` pod 16, ať zůstane průhledný dither, nikdy plná zeď.
- `.tick()` - posune `level` k `target` o `speed`. Vrací `True`, když je cíl dosažen.
- `.is_done` (vlastnost) - `True`, když `level == target`.

```python
import picogame_fx as fx

fader = fx.Fade(scene, W, H)
# ...spusť fade do černé:
fader.out(speed=2)
# ...každý snímek; po dosažení černé spusť přechod zpět:
if fading and fader.tick():
    fader.into(speed=2)
```

:::note[Pozor]
`level` má rozsah 0 až 16, ne 0 až 255 ani 0.0 až 1.0. Bílý puls `Fade` funguje na všech zobrazovacích backendech. `InvertFlash` níže nevyžaduje překreslení, ale podporují ho pouze některé řadiče panelů.
:::

### `fx.Tween` - plynulé dojíždění skaláru k cíli

![Hodnota plynule dojíždí k cíli](/img/fx_tween.gif)

`Tween` v každém snímku exponenciálně přibližuje jednu hodnotu k cíli. Hodí se pro posun prvku rozhraní, změnu měřítka nebo plynule aktualizované číslo.

- `Tween(value=0.0, speed=0.2)` - `speed` je podíl zbývající vzdálenosti, který se uzavře v jednom snímku, v rozsahu 0 až 1.
- `.to(target, speed=None)` - nastav nový cíl (a volitelně novou rychlost). Vrací `self`.
- `.set(value)` - okamžitě nastaví hodnotu i cíl na `value`.
- `.tick()` - posune hodnotu o podíl `speed` k cíli a vrátí nový stav. Při rozdílu menším než 0,01 nastaví přesný cíl.
- `.is_done` (vlastnost) - `True`, jakmile se hodnota rovná cíli.

```python
import picogame_fx as fx

y = fx.Tween(0)
y.to(100)               # posuň panel dolů na y=100
# ...každý snímek:
panel.y = int(y.tick())
```

:::note[Pozor]
průběh cíl nikdy nepřekročí a nevytváří pružné odskočení. `tick()` vrací právě vypočtenou hodnotu.
:::

### `fx.Camera` - plynulá sledovací kamera

![Kamera sleduje napříč větším světem](/img/fx_camera.gif)

Kamera sleduje bod ve světě a vypočítává posun pohledu. Volitelně ho omezí tak, aby za hranou úrovně nebyla vidět prázdná plocha.

- `Camera(scene, w, h, lerp=0.18, world_w=0, world_h=0, top=0, bottom=0, left=0, right=0)` - `w` a `h` jsou rozměry obrazovky, `lerp` určuje vyhlazení v každém snímku a nenulové `world_w` a `world_h` omezí pohled na rozměry světa; `top`/`bottom`/`left`/`right` je vyhrazený pruh pro HUD (stejná čísla, jaká jsi dal `setup()` nebo `Scene`), aby kamera centrovala a omezovala pohled ve viditelné části obrazovky, ne pod HUDem.
- `.follow(tx, ty, snap=False)` - posune střed kamery k `(tx, ty)` o podíl `lerp`; s `snap=True` ho nastaví okamžitě. Vrací `self`.
- `.apply()` - vypočítá offset a přímo zavolá `scene.set_view`. Bez alokace; vrací `None`. Použij, když není žádný shake.
- `.offset()` - vypočítá a vrátí offset jako n-tici `(ox, oy)` (alokuje). Předej to do `Shake.tick(ox, oy)` pro složení obou efektů.

```python
import picogame_fx as fx

cam = fx.Camera(scene, W, H, world_w=bounds_w, world_h=bounds_h, top=BAR)   # stejný pruh jako setup(top=BAR)
# ...každý snímek:
cam.follow(player.x, player.y).apply()
```

:::note[Pozor]
`apply()` i `Shake` volají `scene.set_view()`. Pro kombinaci vypočítej `ox, oy = cam.follow(...).offset()` a předej je do `shaker.tick(ox, oy)`. Chování pohledu popisuje [/cs/scene-format/](/cs/scene-format/).

Pruh pro HUD předej jako `top=`/`bottom=`/…, ne přičtením k `h`. `Camera(scene, W, H + BAR, ...)` sice správně centruje, ale omezuje pohled podle zvětšené výšky, takže `BAR` pixelů světa na každém okraji se nikdy nedostane do záběru. Simulátor upozorní, když se pruh kamery liší od pruhu scény.
:::

### `fx.Sky` - vertikální gradientní pozadí

Svislý gradient se kreslí po řádcích přes `StripDraw`. Drží tabulku `h` barev v pořadí pro přenos, tedy `2 * h` bajtů, a při překreslení znovu vykreslí požadované řádky. Přidej ho před herní vrstvy.

- `Sky(scene, x, y, w, h, top, bottom)` - vyplní obdélník a interpoluje každý řádek od barvy `top` k `bottom`. Obě jsou RGB565 v pořadí pro přenos. Vrstva je `fixed=True`. Změnou `.top` a `.bottom` můžeš animovat denní dobu.

```python
import picogame as pg
import picogame_fx as fx

sky = fx.Sky(scene, 0, 0, W, HORIZON,
             pg.rgb565(60, 120, 240), pg.rgb565(200, 230, 255))
```

:::note[Pozor]
při každém překreslení volá `fill_rect` pro každý viditelný řádek. Náklady na CPU proto rostou s výškou překreslované oblasti.
:::

### `fx.Scanlines` - překryv s řádky CRT

Efekt ztmaví každý N-tý řádek pro vzhled CRT nebo mřížky LCD. Drží jeden řádek PAL8 o velikosti `w` bajtů a dvoupoložkovou paletu a blituje ho přes `StripDraw`. Přidej ho až po herních vrstvách.

- `Scanlines(scene, x, y, w, h, step=2, dark=pg.rgb565(0, 0, 0))` - `step=2` ztmaví každý druhý řádek a `dark` určuje barvu překryvu. Předpočítaný rastrový řádek jednou blitne na každý ztmavený řádek.

```python
import picogame_fx as fx

scanlines = fx.Scanlines(scene, 0, 0, W, H)   # přidej JAKO POSLEDNÍ, navrch všeho
```

:::note[Pozor]
záleží na pořadí - přidej ho až po všech herních vrstvách, jinak bude přemalováno.
:::

### `fx.InvertFlash` - záblesk pomocí inverze řadiče

![Celoobrazovkový invertovaný záblesk (emulováno v simu)](/img/fx_invertflash.gif)

Kompatibilní SPI panel na několik snímků přepne do negativu pomocí inverze barev řadiče (`pg.invert`). Scénu nepřekresluje ani nealokuje obrazový buffer. Použij ho s řadiči třídy ST7789 nebo ST7735; framebufferové výstupy, například Fruit Jam DVI, tuto funkci nepodporují. Simulátor efekt emuluje.

- `InvertFlash(display, frames=3, normal=None)` - `display` je displej desky, např. `picogame_game.display()`; `frames` je délka záblesku. `normal` je klidový stav inverze panelu. PicoPad posílá INVON při inicializaci, takže jeho klidový stav je `normal=None` (výchozí); předej `normal=False` jen pro panel, jehož init neprovádí inverzi.
- `.pulse(frames=None)` - přepne z klidového stavu, volitelně na vlastní počet snímků.
- `.tick()` - odpočítává a po skončení obnoví klidový stav. Dokud záblesk trvá, vrací `True`. Volej po `scene.refresh()`, aby INVON nebo INVOFF byla poslední operace na sběrnici v daném snímku.

```python
import board
import picogame_fx as fx

flash = fx.InvertFlash(picogame_game.display(), frames=6)
# ...při zásahu:
flash.pulse()
# ...po scene.refresh():
flash.tick()
```

:::note[Pozor]
klidový stav inverze musí odpovídat inicializaci panelu. Na PicoPadu nech `normal=None`, aby se použilo nastavení desky. Efekt nevytvářej pro framebufferový displej. Podporované řadiče popisuje [/cs/hardware/](/cs/hardware/).
:::

**Bezpečnost proti záchvatům:** u jakéhokoli celoobrazovkového záblesku (`InvertFlash`, `Fade.pulse`, rychlé blikání spritu) se vyhni trvalému blikání nad ~3 Hz (nejméně 10 snímků od sebe při 30 fps); celoobrazovkové inverze drž na 1–3 snímcích, jednorázově.

## picogame.Particles

![Částicový výbuch se rozlétá a fadeuje](/img/fx_particles.gif)

`pg.Particles` je základní vrstva enginu pro jiskry, exploze, efekt sebrání předmětu nebo prach. Předem vytvoří fond s pevnou kapacitou a během `emit()` ani `tick()` nevytváří nové objekty částic.

- `pg.Particles(capacity, *, size=1, gravity=0.0, fade=False)` - fond až `capacity` bodů o velikosti `size` pixelů. `gravity` je při každém kroku posouvá dolů a `fade=True` je s věkem ztmavuje. `size`/`gravity`/`fade` jsou keyword-only (předávej je jménem).
- `.emit(x, y, count, speed=1, life=30, color=0xFFFF)` - výbuch `count` teček z `(x, y)` s náhodnou rychlostí do `speed` px/tick, každá žije `life` ticků.
- `.tick()` - posune a zestárne živé tečky; volej jednou za snímek.

```python
import picogame as pg

ps = pg.Particles(180, size=2, gravity=0.0, fade=True)
scene.add(ps)                                        # přidej jednou, jako každou vrstvu
# ...při zásahu / killu / sebrání:
ps.emit(x, y, 16, 4, 24, pg.rgb565(255, 210, 120))   # 16 jisker, rychlost 4, život 24 ticků
# ...každý snímek:
ps.tick()
```

:::note[Pozor]
částice nad `capacity` se nevytvoří. Kapacita proto musí pokrýt největší souběh efektů. Krátká životnost s `fade=True` se hodí pro jiskry, delší životnost s `gravity > 0` pro padající úlomky.
:::

## picogame_palette

![Cyklování palety - vyhrazený barevný pás teče](/img/fx_palette.gif)

Grafika PAL8 může měnit barvy bez kopie obrazových indexů. `cycle` otáčí vybranou část palety, `swap` kopíruje jinou paletu a `fade` interpoluje položky k cílové barvě. Položky palety jsou celá čísla RGB565 v pořadí pro přenos, která vrací `pg.rgb565()`.

`import picogame_palette as palette`

- `snapshot(palette)` - vrátí kopii palety jako `array('H')`. Ulož ji před změnami, aby `fade` mohl interpolovat od původních barev a `restore` je obnovit.
- `restore(palette, base)` - zkopíruje `base` zpět do `palette` na místě.
- `cycle(palette, lo, hi, step=1)` - otočí položky `[lo..hi]` včetně o `step` přímo v původní paletě. Vyhrazená skupina barev tak může animovat například vodu.
- `swap(dst_palette, src_palette)` - zkopíruje jednu paletu do druhé až po délku kratší z nich. Jedna bitmapa PAL8 tak může mít více barevných variant.
- `fade(palette, base, t, target=0, skip=None)` - interpoluje položky `palette` od uložené `base` k barvě `target` podle `t`, kde 0.0 znamená původní barvu a 1.0 cíl. `skip` ponechá vybraný index beze změny, například průhlednou položku.

```python
import picogame_palette as palette

# ...každý snímek animuj vyhrazený rozsah barev vody:
palette.cycle(water_bmp.palette, 1, 6)
water.touch()                       # řekni rendereru, že se paleta změnila
```

:::caution[Na zařízení jeden blit slot]
Efekty spritu `flash`, `tint`, `dither` a `shadow` sdílejí na hardwaru **jeden** blit slot — nastavením jednoho se ostatní zruší (platí naposledy nastavený). Simulátor na počítači toto chování **nereprodukuje**; zobrazuje je jako nezávislé. Zkombinuj je sekvencí snímek po snímku nebo použij samostatnou vrstvu efektů; vždy ověř na hardwaru.
:::

Přebarvení spritu na **jasnější / jiný odstín** — co `sprite.tint` neumí (násobení jen ztmavuje).
Drž jednu PAL8 bitmapu a dej jí teplou paletu (např. zelený nepřítel → žhavě jantarová „elita"):

```python
import array, picogame_palette as palette

WARM = array.array("H", [0, pg.rgb565(150, 40, 30), pg.rgb565(255, 130, 45),
                         pg.rgb565(120, 45, 25), pg.rgb565(255, 215, 130),
                         pg.rgb565(235, 90, 45), pg.rgb565(255, 245, 190)])  # jedna položka na index
palette.swap(enemy.bitmap.palette, WARM)   # zkopíruj WARM do palety bitmapy, in place
enemy.touch()                              # renderer si změny palety sám nevšimne
# Variantu místo in-place? Postav druhou `pg.Bitmap(DATA, ..., palette=WARM)` a přiřaď ji do
# sprite `.bitmap` — viz examples/picogame_picowing.py, který takhle přebarvuje Kenney nepřítele.
```

:::note[Pozor]
renderer dirty regions čte paletu při blitu, ale její změnu sám nesleduje. Po `cycle`, `swap`, `fade` nebo `restore` zavolej `sprite.touch()` u spritů s danou bitmapou, případně `scene.invalidate()` nebo označ oblast tilemapy. Tím se dotčená grafika v daném snímku znovu vykreslí. Paměťové srovnání s další bitmapou najdeš v [/cs/memory/](/cs/memory/).
:::
