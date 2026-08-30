---
title: Herní vzory
description: Krátké recepty pro stav, úrovně, kameru, skóre, kolize a odezvu.
sidebar:
  order: 3
---

Tyto recepty ukazují *podobu* kódu používaného v různých žánrech — strukturu a proč. Hotový kód
k vložení pro konkrétní úlohu (HUD, fondy, restart, míchání, časování vstupu) najdeš v
[Úryvcích](/cs/snippets/); přesné signatury v [referenci API](/cs/reference/) a úplné hry
v [příkladech](/cs/examples/). Aktéry odlišuj tvarem i barvou, aby zůstali čitelní na malém displeji
a bez rozlišení barev.

## Struktura hry: stavový automat + restart
Drž všechen měnitelný stav hry v jednom **`State`** objektu, herní smyčku dej do **funkce** (`main`)
a větvi podle `st.mode`. Funkce udrží vyhledávání jmen ve smyčce rychlé (lokální proměnné místo
vyhledávání v globálním slovníku — na zařízení měřitelný zisk) a jeden objekt dělá z restartu jednořádek.
```python
class State:
    def __init__(self): self.reset()
    def reset(self):
        self.mode = "title"          # "title" -> "play" -> "over"
        self.score = 0; self.lives = 3

st = State()

def new_game():
    st.reset(); st.mode = "play"     # re-inicializace NA MÍSTĚ (vyčisti pooly, zobraz sprity)

def main():                          # smyčka žije ve funkci -> její jména jsou rychlé lokály
    poll, refresh, tick = btn.poll, scene.refresh, clock.tick   # vytáhni horké volání do lokálů
    while True:
        poll()
        if st.mode == "play":
            ...                      # pohyb, kolize, skóre; při smrti: st.mode = "over"
        elif btn.just_pressed(btn.A):
            new_game()               # title / game-over -> okamžitý restart, bez reloadu
        refresh(); tick()

main()
```
Malá hra (pár stavových proměnných) může zůstat na úrovni modulu, ale tvar `State` + `main()` škáluje
čistě a je doporučeným výchozím řešením. Hotová kostra k spuštění: [vyzkoušej v prohlížeči](/playground/?ex=game-skeleton).

## Pool objektů
Pro krátce žijící objekty, jako jsou střely, mince, kostky a jiskry, používej pevný pool.
```python
pool = picogame_pool.Pool(scene, BMP, 16, anchor=(0.5, 0.5))
s = pool.spawn()                 # None když plno; .visible je příznak "žije"
if s: s.move(x, y); s.data = ... # pool.free(s) pro recyklaci
```

## Úroveň v tilemapě
Deska pro bludiště, cihly, plošiny, RPG mapy: 1 bajt/buňku, čtená i zapisovaná za běhu.
```python
level = pg.Tilemap(tileset, cols, rows); scene.add(level)
level.set_tile(cx, cy, EMPTY)             # zápis buňky: sněz pelet, rozbij cihlu
hit = level.get_tile(cx, cy) in WALLS     # čtení buňky pro kolizi
```

## Kolize s pevnými dlaždicemi (po osách)
U plošinovkových zdí a podlah hýbej a řeš kolizi **vždy po jedné ose** (X, pak Y), aby se tělo nezaseklo
v rozích; sonduj náběžnou hranu ve dvou bodech a rychlý pád krokuj po pixelu, aby velké `vy` neproletělo
podlahou. Je to čistý Python per objekt: levné, žádné speciální volání enginu.
```python
def move_x(x, y, dx, hw):                       # krokuj jako move_y: sondovat jen SOUČASNOU hranu
    step = 1 if dx > 0 else -1                  # a pak se posunout o dx nechá tělo uvnitř zdi
    for _ in range(abs(int(dx))):
        e = x + step + (hw if dx > 0 else -hw)  # hrana PO tomto pixelu pohybu
        if solid(e, y - 2) or solid(e, y - 14):
            return x                            # těsně u zdi
        x += step
    return x

def move_y(x, y, vy, hw):                        # řeš ve SMĚRU POHYBU, po jednom pixelu, ať velké
    step = 1 if vy > 0 else -1                   # vy neproletí podlahou ANI stropem
    probe = 1 if vy > 0 else -15                 # náběžná hrana: při pádu nohy, při stoupání hlava
    for _ in range(abs(int(vy))):
        if solid(x, y + probe) or solid(x - hw, y + probe) or solid(x + hw, y + probe):
            return y, 0, vy > 0                  # zablokováno: y drženo, vy nula; na zemi jen dolů
        y += step
    # Malé vy neposune o celý pixel, takže smyčka vůbec nesondovala. Při stání je gravitace hluboko
    # pod 1 px/snímek - bez tohohle by příznak obden blikal. Skoku to nevadí (schová to coyote
    # timer), zvuku kroků nebo animaci stání ano.
    on_ground = vy > 0 and (solid(x, y + 1) or solid(x - hw, y + 1) or solid(x + hw, y + 1))
    return y, (0 if on_ground else vy), on_ground
```

**Jeden resolver, ne dvě větve.** Krokovat jen při pádu dá *jednosměrnou plošinku* — hráč jí proskočí
zdola a přistane na ní, což je legitimní návrh a ten nejlevnější. Jenže jakmile level dostane strop,
šachtu nebo uzavřenou místnost z téže dlaždice, jde jimi zdola projít a působí to jako chyba. Přilepit
vedle padací větve zvláštní stoupací se rychle rozpadne: padací půlka zůstane napevno pro `+y` a zdi
i šachty si vyžádají třetí případ. Vezmi směr ze znaménka jako výše a jednosměrnost se scvrkne na
jedinou podmínku u sondy (`solid(...) and vy > 0`) místo paralelní cesty.

## Posouvající se kamera
Když je svět větší než obrazovka: sleduj a omez pohled; HUD nech na `fixed` vrstvě.
```python
scene.set_view(clamp(player.x - W // 2, 0, world_w - W), 0)
```

## Tahová smyčka
Logická hra, taktika nebo RPG: čekej na vstup, vyřeš jeden tah a překresli. Ve většině snímků se nic nemění, takže je tento režim levný.
```python
if btn.just_pressed(btn.A):
    resolve_move()               # posuň přesně o jeden tah
scene.refresh()                  # překreslí se jen změněné buňky
```

## Odezva na zásah
Podle síly události zkombinuj zvuk, krátký záblesk, mírný otřes, [hit-stop](/cs/helpers/effects/) nebo částice.
```python
spr.flash = WHITE                # plná barva - a sama se NEZHASNE
flash_t = 2                      # odpočítej ji a vypni, jinak sprite zůstane bílý
shake.add(0.4)                   # picogame_fx.Shake; shake.tick() každý snímek
if audio: audio.sfx(picogame_audio.tone(150, 70))

# ... každý snímek:
if flash_t:
    flash_t -= 1
    if not flash_t: spr.flash = 0
```

## Vstřícný hitbox a dočasná nezranitelnost
U akčních her pomůže hitbox menší než grafika a krátká nezranitelnost po zásahu.
```python
if inv:                                    # okno odpočítej a po dobu jeho běhu blikej
    inv -= 1
    player.visible = not (inv >> 2) & 1
elif threat.near(player, 12):              # hitbox < grafika spritu
    inv = 45                               # dočasná nezranitelnost: jeden zásah nesmí řetězit
    player.visible = True
```

## Řetěz skóre
Odměň chamtivost: po sobě jdoucí zásahy zvyšují násobič; chyba ho resetuje.
```python
# při zásahu: chain += 1; mult = 1 + chain // 5; score += pts * mult
# při chybě:  chain = 0;  mult = 1
```
Pro *zobrazení* skóre na obrazovce viz [Text a uživatelské rozhraní](/cs/helpers/text-ui/).

## Stupňování obtížnosti
Zvyšuj rychlost nebo hustotu a mezi náročnějšími úseky nech krátké zklidnění.
```python
interval = max(11, 30 - t // 160)            # spawny časem zrychlují
if (t % 600) >= 54 and t % interval == 0:    # s ~1,8s oddechem každých ~20s
    spawn()
```

## Posouvající se pozadí
Několik spritů vracených na začátek vytvoří nekonečné paralaxní pozadí bez celoobrazovkové bitmapy.
```python
for s in stars:
    s.fy += s.speed
    if s.fy > H: s.fy = -2; s.fx = rng.below(W)   # wrap nahoru
```

---
Návrhové důvody vysvětluje [Jak udělat hru zábavnou](/cs/concepts/making-it-fun/), základ enginu
[Jak picogame funguje](/cs/concepts/how-it-works/). [Tutoriály](/cs/tutorials/) staví Breakout,
střílečku a RPG krok za krokem.
