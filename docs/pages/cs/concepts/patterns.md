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
def move_x(x, y, dx, hw):                       # zastav u zdi, nevjeď do ní
    e = x + (hw if dx > 0 else -hw)
    return x if solid(e, y - 2) or solid(e, y - 14) else x + dx

def move_y(x, y, vy, hw):                        # krokuj dolů, ať velké vy neproletí podlahou
    if vy > 0:
        for _ in range(vy):
            if solid(x, y + 1) or solid(x - hw, y + 1) or solid(x + hw, y + 1):
                return y, 0, True                # přistání: y drženo, vy vynulováno, na zemi
            y += 1
    return y + vy, vy, False
```

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
spr.flash = WHITE                # plná barva na 1–3 snímky
shake.add(0.4)                   # picogame_fx.Shake; shake.tick() každý snímek
if audio: audio.sfx(picogame_audio.tone(150, 70))
```

## Vstřícný hitbox a dočasná nezranitelnost
U akčních her pomůže hitbox menší než grafika a krátká nezranitelnost po zásahu.
```python
if inv == 0 and threat.near(player, 12):   # hitbox < grafika spritu
    inv = 45                     # dočasná nezranitelnost; blikej, dokud inv > 0
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
