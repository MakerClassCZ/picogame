---
title: "Pseudo-3D (Mode-7 a raycasting)"
description: "Fake-3D podlahy a chodby kreslené do bezbufferového StripDraw view - perspektivní podlaha přes C primitivum Canvas.mode7 a Python DDA raycaster."
---

Dva způsoby, jak z 2D enginu dostat 3D vzhled, oba kreslené do **bezbufferového `StripDraw` view**, takže stojí **nula retained RAM**. `picogame_mode7` dá ubíhající **podlahu** (trať závoďáku, létající koberec); `picogame_ray` dá **stěny a chodby** (dungeon, bludiště). Signatury najdeš v [/cs/reference/](/cs/reference/).

| Co chceš | Sáhni po | Jak to kreslí |
|---|---|---|
| Podlahu ubíhající k horizontu | `picogame_mode7.Camera` (řídí C `Canvas.mode7`) | C primitivum, per-scanline - rychlé |
| Stěny / first-person chodbu | `picogame_ray.Raycaster` | native DDA caster + temporal repaint |

Obojí kreslí jen řádky pod horizontem a oblohu nechává na tobě; řádky nad horizontem si vyplníš sám (plná barva, gradient nebo [`fx.Sky`](/cs/helpers/effects/)).

## picogame_mode7

![Mode-7 závoďák - silnice ubíhá, rumble pruhy se ženou k tobě](/img/mode7.gif)

**Mode-7 perspektivní podlaha**: každý řádek obrazovky pod horizontem navzorkuje jednu vzdálenost do textury, takže plochý top-down obrázek působí jako podlaha ubíhající k horizontu. Veškerá matematika je v tomto Python helperu; per-scanline vyplnění dělá C engine primitivum `Canvas.mode7`, takže je laciné.

`import picogame_mode7 as m7`

### `m7.Camera` - perspektivní podlaha

- `Camera(fov=0.66)` - drží zorné pole (vyšší = širší, víc rybí oko). Kameru vytvoř jednou a každý snímek jí předej pozici.
- `.draw(canvas, texture, x, y, angle, horizon, height, y_off=0)` - vyplní `canvas` (`Canvas` **nebo** `StripDraw` view) pod `horizon` ubíhajícím pohledem na `texture`. `x`/`y` je pozice kamery ve **světových (dlaždicových) jednotkách**, `angle` je směr v radiánech, `horizon` je řádek obrazovky s linií horizontu a `height` je výška kamery (vyšší = podlaha ubíhá pomaleji, vidíš dál). V `StripDraw` callbacku předej `y_off=vy`, aby perspektivní dělení použilo absolutní řádek obrazovky.

`texture` musí mít **rozměry mocninu dvou** a **jedna světová jednotka = jedna celá dlaždice textury**. Bezešvě dlaždicovatelná textura (tráva, silnice s rumble pruhy) může použít velký `height` a wrapovat donekonečna; jednorázový neopakující se obrázek (jeden uzavřený okruh) potřebuje malý `height`, jinak se vzdálenost začne opakovat.

```python
import picogame as pg
import picogame_mode7 as m7

cam = m7.Camera(fov=0.9)

def ground(view, vx, vy, vw, vh):
    for r in range(vh):                       # oblohu nad horizontem si vyplň sám
        if vy + r < HORIZON:
            view.fill_rect(0, r, vw, 1, SKY)
    cam.draw(view, TRACK, car.x, car.y, car.heading, HORIZON, 5.0, y_off=vy)

scene.add(pg.StripDraw(ground, 0, 0, W, H))   # 0 retained bajtů
# ...každý snímek: posuň car.x/y/heading, pak scene.refresh()
```

:::note[Na co pozor]
Kresli do **`StripDraw` view**, ne do celoobrazovkového `Canvas` - `Canvas` 320×240 má ~150 KB a na RP2040 se nevejde, kdežto `StripDraw` view je 0 retained RAM. Vždy předej `y_off=vy` v callbacku, jinak horizont skončí v každém stripu jinde. Rozměry textury musí být mocniny dvou. Pro nejnižší úroveň kontroly můžeš volat `Canvas.mode7(...)` přímo (10 fixed-point argumentů); helper `Camera` je jen dopočítá z přívětivé pozice.
:::

## picogame_ray

![First-person raycaster - chodba dungeonu s hloubkově stínovanými stěnami](/img/raycaster.gif)

**Raycaster ve stylu Wolfensteinu**: jeden DDA paprsek na sloupec obrazovky najde nejbližší stěnu a každý sloupec se vykreslí jako vzdáleností stínovaný svislý pruh. Render cesta je plně nativní: engine caster `pg.raycast` (integer 16.16 C na zařízení, Python verze v simu) udělá per-sloupcový DDA A rovnou emituje RLE-sloučené runy stěn; lib dělá trig jednou za snímek a runy maluje jednou dávkou `Canvas.vspans` na strip do `StripDraw` view.

`import picogame_ray`

### `picogame_ray.Raycaster` - first-person raycaster stěn

- `Raycaster(world, wall_colors, sky, floor, fov=0.66, stride=2)` - `world` je seznam stejně dlouhých řetězců (`'0'` = prázdno, `'1'`..`'9'` = typy stěn); `wall_colors` mapuje každý typ stěny na dvojici `(barva_čela, barva_boku)` (boční o kus tmavší = hloubkový cue zdarma); `sky`/`floor` jsou wire-RGB565 pozadí. `stride` vrhá jeden paprsek na N sloupců - **knoflík výkon/kvalita** (viz níže).
- `.cast(px, py, ang, sw, sh)` - vrhne paprsky pro pozici kamery `(px, py)` a směr `ang` a nakešuje rozsah stěny pro každý sloupec. Volej jednou za snímek **před** `scene.refresh()`.
- `.draw(view, vx, vy, vw, vh)` - `StripDraw` callback: vykreslí pásy oblohy/podlahy a pak předsloučené runy stěn jedním dávkovým voláním `Canvas.vspans`.
- `.solid(x, y)` - je buňka mapy na celočíselných `(x, y)` stěna? Použij pro kolizi pohybu (mimo mapu = stěna).
- `.attach(stripdraw)` - zapne **temporální rendering**: předej `StripDraw` (vytvořený `always_dirty=False`), který tenhle raycaster kreslí, a `cast()` invaliduje jen změněný pás sloupců od minulého snímku (nehybná kamera nepřekresluje nic). Velká výhra při stání / pomalém pohybu.
- `.zbuf` - po `cast()` vzdálenost stěny pro každý sloupec (16.16 fixed-point; hloubkový buffer, proti kterému testuje `project_sprite`).
- `.project_sprite(sx, sy, margin=0.2)` - promítne světový bod `(sx, sy)` na obrazovku pro poslední `cast()`. Vrátí `(screen_x, size, depth)`, nebo `None`, když je bod za kamerou nebo schovaný za bližší stěnou. `size` je výška na obrazovce v px ve škále stěn - nastav `sprite.scale = size / výška_bitmapy`; seřaď sprity podle `depth` od nejvzdálenějšího, aby ty bližší kreslily navrch. `margin` je vůle z-testu, aby sprite těsně u stěny nezmizel.

```python
import picogame as pg
import picogame_ray

MAP = ["1111111111", "1000000001", "1011100201", "1000000001", "1111111111"]
WALLS = {1: (pg.rgb565(150, 150, 160), pg.rgb565(95, 95, 110)),
         2: (pg.rgb565(170, 90, 60), pg.rgb565(110, 55, 35))}

rc = picogame_ray.Raycaster(MAP, WALLS, pg.rgb565(30, 30, 48), pg.rgb565(40, 34, 30), stride=2)
scene.add(pg.StripDraw(rc.draw, 0, 0, W, H))
# ...každý snímek:
rc.cast(px, py, ang, W, H)                    # nejdřív cast, pak vykreslení
scene.refresh()
# ...pohyb bez procházení stěnami:
if not rc.solid(int(nx), int(py)):
    px = nx
```

### Nepřátelé & pickupy - billboard sprity

Raycaster kreslí jen stěny; nepřátelé a pickupy jsou běžné `Sprite`, které se každý snímek zvětší a umístí podle `project_sprite` a depth-testují proti stěnám, takže se schovají za roh. Přidej sprity do scény **až za** `StripDraw`, ať kreslí navrch, a místo vytváření každý snímek použij [`picogame_pool.Pool`](/cs/helpers/math/).

```python
GUYS = [Enemy(3.5, 2.5), Enemy(6.5, 3.5)]        # pozice ve světě (dlaždice)
for g in GUYS:
    g.spr = pg.Sprite(DEMON_BMP, -40, -40)       # DEMON_BMP je 8 px vysoký
    g.spr.anchor = (0.5, 0.5)
    scene.add(g.spr)                             # AŽ ZA StripDraw -> navrch stěn

def frame():
    rc.cast(px, py, ang, W, H)                   # cast stěn (naplní rc.zbuf)
    GUYS.sort(key=lambda g: -((g.x - px) ** 2 + (g.y - py) ** 2))   # od nejvzdálenějšího
    for g in GUYS:
        p = rc.project_sprite(g.x, g.y)
        if p:
            sx, size, _ = p
            g.spr.move(sx, HORIZON)              # na řádek horizontu
            g.spr.scale = size / 8.0             # bitmapa je 8 px vysoká
            g.spr.visible = True
        else:
            g.spr.visible = False               # mimo obraz nebo za stěnou
    scene.refresh()
```

:::note[Na co pozor]
Render cesta je **plně nativní** (caster `pg.raycast` emituje sloučené runy stěn; `Canvas.vspans` je maluje - vyžaduje firmware s obojím), takže celoobrazovkový raycaster se stride 1 běží kolem **36 fps uncapped** na RP2040, ploché napříč úhly pohledu a nezávisle na `strip_h`, s nulovými alokacemi za snímek. Python páky navrch: **temporální rendering** - vytvoř `StripDraw` s `always_dirty=False` a zavolej `rc.attach(sd)`; `cast()` pak překreslí jen změněný pás sloupců od minulého snímku a nehybná kamera nic nerecastuje (pose-cache). A **`stride`** (1 = nejostřejší stěny, už ~36 fps; vyšší mění ostrost za ještě větší rezervu). U grazing úhlů občas blafne tenký sloupec („zub", inherentní DDA). `project_sprite` depth-testuje ve **středovém sloupci** spritu, takže billboard se zobrazí nebo schová jako celek - dobré pro jeden sprite, ale nezařízne se z poloviny za hranu stěny.
:::
