---
title: "Jen C engine (bez pomocných knihoven)"
description: "Knihovny picogame_* jsou ergonomie. Samotný C modul je kompletní engine - tady je celá malá hra postavená jen na `import picogame` a stock CircuitPythonu."
---

Python knihovny `picogame_*` jsou **ergonomie**. Samotný engine - `import picogame` - je nativní C
modul, který už dělá všechnu těžkou práci: rendering, kolize, transformace, šum, raycasting, polygonové
3D, DVI framebuffer. Postavíš na něm skutečnou hru **jen s C modulem a stock CircuitPythonem**. Tahle
stránka ukazuje jak, a co ke všemu přidává každý helper.

## Co je v C a co přidávají helpery

C modul (`import picogame as pg`) exportuje engine:

- **Typy:** `Scene`, `Sprite`, `Bitmap`, `Tilemap`, `Canvas`, `StripDraw`, `Particles`, `Triangles`,
  `Display`, `Framebuffer`.
- **Funkce:** `render` / `refresh_async`, `collide`, `raycast`, `project`, `road_edges`, `value2d` /
  `fbm2d` šum, `rgb565`, `vblank`, ROMFS streaming.

To je všechno výpočetně náročné a distinktivní - sprity s runtime scale/rotací a blit efekty,
dirty-rect kompozice, 0-RAM tilemapy a stripy, nativní text, kolize, procedurální šum, raycaster,
Mode-7, flat-shaded 3D, DVI výstup. Helper knihovny z toho **nedrží nic**:

| Helper | Co přidává | Ručně přes… |
|---|---|---|
| `picogame_game` | boot wiring (`Scene` + `Display` + strip buffery) a cross-platform kvirky (Fruit Jam DVI, RGB444, simulátor) | jeden `pg.Scene(pg.Display(board.DISPLAY), …)` |
| `picogame_input` | tlačítka → bitmaska, nad `keypad`/`digitalio`, s per-board profily pinů | stock `keypad` / `digitalio` |
| `picogame_clock` | `dt` / fixed-step časování | stock `time.monotonic()` |
| `picogame_ui` / `fx` / `anim` / `pool` / `rand` | HUD widgety, screen-shake/tween, časování animací, object pooly, seeded RNG | čistý Python |
| `picogame_audio` / `synth` / `sfx` / `save` / `music` | zvuk a ukládání | stock `audiocore` / `synthio` / `nvm` |

Dvě věci stojí za jasné vyřčení: **input, audio ani save nejsou v enginu vůbec** - to je stock
CircuitPython. Engine vždycky dostane jen *výsledek*: pozici spritu, naplněný buffer. Input je obzvlášť
úplně oddělená vrstva - přečteš tlačítka, v Pythonu rozhodneš, že se něco posune o N pixelů, a jen
nastavíš `sprite.x` / `sprite.y`. Engine tlačítko nikdy nevidí.

## Celá hra jen s C modulem

Nikde žádný `picogame_*` import - jen `picogame` plus `board`, `time`, `array`, `terminalio`,
`digitalio`. Hráč se hýbe D-padem, sbírá minci přes nativní kolizi, při sebrání blikne, a kreslí se
HUD s nativním textem.

![Engine-only hra: hráč, mince a HUD s nativním textem - bez pomocných knihoven](/img/engine-only.png)

```python
# Celá malá hra JEN na C modulu picogame.
import board, time, array
import terminalio, digitalio
import picogame as pg

W, H = picogame_game.screen()

# Jediný setup enginu: Scene na displeji + dva strip buffery, přes které renderuje.
# picogame_game.display() napřímo je portable všude - SPI panely, framebuffery i playground.
# (Obalení do pg.Display(...) přidá rychlou DMA cestu na SPI deskách; to i buffery
# vyřeší za tebe picogame_game.setup() podle desky.)
SH = getattr(pg, "STRIP_H", 8)
scene = pg.Scene(picogame_game.display(), bytearray(W * SH * 2), bytearray(W * SH * 2),
                 background=pg.rgb565(12, 14, 34))

# Bitmapa spritu vyrobená ručně (PAL8, 1 bajt/px).
def square(color, size=6):
    data = bytearray(b"\x01" * (size * size))
    pal = array.array("H", [0, color])
    return pg.Bitmap(data, size, size, format=pg.PAL8, palette=pal, frames=1, stride=size, transparent=0)

player = pg.Sprite(square(pg.rgb565(90, 230, 130)), W // 2, H // 2)
player.anchor = (0.5, 0.5); player.scale = 4.0; scene.add(player)
coin = pg.Sprite(square(pg.rgb565(250, 210, 70)), 40, 60)
coin.anchor = (0.5, 0.5); coin.scale = 4.0; scene.add(coin)

# Input: stock digitalio na tlačítkách desky - syrové zapojení, které picogame_input skrývá.
def button(name):
    io = digitalio.DigitalInOut(getattr(board, name))
    io.switch_to_input(pull=digitalio.Pull.UP)     # tlačítka PicoPadu jsou aktivně-nízká
    return io
LEFT, RIGHT, UP, DOWN = (button(n) for n in ("SW_LEFT", "SW_RIGHT", "SW_UP", "SW_DOWN"))
def held(b): return not b.value                    # aktivně-nízké: stisk -> False

# HUD: nativní Canvas.text do 0-RAM StripDraw. Callback běží jednou na render-strip,
# takže kresli na (y - vy) pro obrazovkový prostor; band >= 12px výška fontu.
score = 0
BAND = terminalio.FONT.get_bounding_box()[1] + 4   # 12 + 4 = 16
def hud(view, vx, vy, vw, vh):
    view.text(3, 2 - vy, "SCORE %d" % score, pg.rgb565(255, 230, 90), terminalio.FONT)
scene.add(pg.StripDraw(hud, 0, 0, W, BAND))

while True:
    if held(LEFT):  player.x -= 3
    if held(RIGHT): player.x += 3
    if held(UP):    player.y -= 3
    if held(DOWN):  player.y += 3
    player.x = min(max(player.x, 6), W - 6)        # drž na obrazovce
    player.y = min(max(player.y, BAND + 6), H - 6)
    if player.overlaps(coin):                      # nativní C kolize
        score += 1
        coin.x = 30 + (score * 47) % (W - 60)
        coin.y = BAND + 12 + (score * 31) % (H - BAND - 30)
        player.flash = pg.rgb565(255, 255, 255)    # nativní blit efekt
    else:
        player.flash = 0
    scene.refresh()                                # nativní dirty-rect kompozitor
    time.sleep(0.01)
```

[▶ **Vyzkoušej v prohlížeči**](/playground/?ex=engine-only)

`Scene` + `Sprite` + `overlaps` + `flash` + `Canvas.text` + `refresh` je celé C engine; `board`,
`digitalio`, `terminalio`, `time` je stock CircuitPython. Nic víc.

## Co helpery pohlcují

Ty fiddly části kódu výše jsou přesně to, co helper knihovny odeberou: umístění HUD textu přes
render-stripy (`picogame_ui.HudBar`), zapojení každého tlačítka podle desky (`picogame_input.Buttons`),
časování nezávislé na frameratu (`picogame_clock.Clock`) a výběr správných bufferů a backendu pro každou
platformu - SPI panel vs framebuffer, rychlé DMA kde je (`picogame_game.setup()`). Nic z toho nemění, co
engine umí; jen to maže boilerplate.

## Kdy sáhnout po enginu přímo

Po syrovém C API sáhni, když chceš co nejmenší footprint, plnou kontrolu nad smyčkou, pochopit, co
knihovny dělají, nebo si nad tím postavit vlastní framework. Pro všechno ostatní jsou helpery čistě
pohodlí - ušetří boilerplate a zahladí rozdíly mezi deskami, ale hra, kterou postavíš, je stejně
schopná tak i tak.
