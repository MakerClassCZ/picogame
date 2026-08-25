---
title: Přicházíš z jiného enginu
description: Převod pojmů z Pygame, displayio, PICO-8 a Arcade do picogame.
sidebar:
  order: 2
---

Tabulka níže převádí pojmy z Pygame, `displayio`, PICO-8 a Arcade do picogame. Pokud znáš
`displayio`, pokračuj [převodem po jednotlivých pojmech](#přicházíš-z-displayio).
Základní princip vysvětluje [Jak picogame funguje](/cs/concepts/how-it-works/), přesné signatury
najdeš v [referenci API](/cs/reference/).

## Mapa konceptů

| Chceš… | Pygame | displayio (CircuitPython) | PICO-8 | **picogame** |
|---|---|---|---|---|
| Obrázek | `Surface` | `Bitmap` + `Palette` | sprite sheet | `pg.Bitmap(data, w, h, …)` (PAL8 nebo RGB565, vícesnímkový atlas) |
| Pohyblivý objekt | `sprite.Sprite` | `TileGrid` | `spr()` | `pg.Sprite(bitmap, x, y)` (kotevní bod, překlopení, snímek, **scale**, **angle**) |
| Scénu/svět | `Group`/ručně | `Group` | obrazovka | `pg.Scene(...)` — retained režim, dirty regions |
| Vykreslit to | `screen.blit()` | přidat do `Group` | `spr()`/`map()` | jednou `scene.add(obj)`; pak `scene.refresh()` na každý snímek |
| Dlážděnou úroveň | vlastní | `TileGrid`+`Bitmap` | `map()` | `pg.Tilemap(tiles, cols, rows)` — `tile(x, y, value)` |
| Posouvající se kameru | ruční offset | `Group.x/y` | `camera()` | `scene.set_view(ox, oy)` (svět větší než obrazovka) |
| Hlavní smyčku | `while`, `flip()` | `while`, `refresh()` | `_update()`/`_draw()` | `while: buttons.poll(); …; scene.refresh(); clock.tick()` |
| Vstup | `pygame.event` | `keypad`/piny | `btn()` | `picogame_input.Buttons` → `is_pressed()` / `just_pressed()` (`poll()` vrátí bitovou masku) |
| Zvuk | `mixer` | `audiocore`/`audiopwmio` | `sfx()`/`music()` | `picogame_audio` (`tone()`, `.wav`) |
| Kolize | `Rect.colliderect` | ručně | ručně | `pg.collide(...)` / `a.overlaps(b)` / `a.near(b, r)` (bez alokace) |
| Text | `font.render` | `label` | `print()` | `picogame_ui` HUD / `picogame_font` → Bitmap |
| Mnoho střel/nepřátel | sprite groups | ručně | ručně | `picogame_pool.Pool` (pevný pool, žádná alokace na snímek) |
| Transformace | `transform.rotate` | omezené | překlopení přes `spr` | `sprite.scale` (float) + `sprite.angle` (stupně), nejbližší soused |

## Přicházíš z displayio

Pokud znáš CircuitPython `displayio`, většina objektů ti bude povědomá. picogame používá názvy
zaměřené na hry a samo sleduje oblasti, které potřebují překreslit:

| V `displayio` jsi používal… | V picogame je to… |
|---|---|
| `displayio.TileGrid` — umístěná bitmapa | **[Sprite](/cs/concepts/glossary/)** — ale navíc se překlápí, škáluje, otáčí a animuje |
| `displayio.Group` — skupina objektů | **[Scene](/cs/concepts/glossary/)** — drží [vrstvy](/cs/concepts/glossary/) vykreslované v pořadí |
| `while True: display.refresh()` | **[herní smyčka](/cs/concepts/glossary/)**: čti vstup → aktualizuj → `scene.refresh()` → počkej |
| `bitmap` + `palette` + RGB565 | totéž, ale barvy vytvářej pomocí `pg.rgb565(r, g, b)` ([pořadí pro přenos](/cs/concepts/glossary/)), ne zápisem `0xRRGGBB` |
| ruční správa překreslování | nic — picogame je **[retained mode](/cs/concepts/glossary/)**: měníš objekty a on překreslí jen to, co se pohnulo |

Hlavní změna je v tom, že popisuješ scénu místo ručního řízení každého překreslení displeje.

## Hlavní rozdíl: retained režim a dirty regions

Mnoho 2D enginů funguje v **immediate mode**: každý snímek vymažeš obrazovku a překreslíš všechno.
picogame je **retained mode**: jednou postavíš `Scene` z objektů a pak je každý snímek jen *měníš*
a voláš `scene.refresh()`. Engine zjistí, které obdélníky se změnily, a **překreslí jen
je**. Na SPI displeji pošle na panel pouze tyto pixely. Framebufferové cíle, například Fruit Jam,
překreslí stejné oblasti v paměti používané pro obrazový výstup. V obou případech změny sleduje scéna.

Jeden důsledek: posun nebo výměna spritu se sleduje automaticky, ale úprava pixelů **na místě**
potřebuje `sprite.touch()`, aby se projevila (viz [efekty](/cs/helpers/effects/)).

## Co picogame umí

- **Sprity libovolné velikosti** s kotevními body, překlopením a vícesnímkovými animačními atlasy.
- **Změnu velikosti a rotaci za běhu** u každého spritu, kolem kotevního bodu.
- **Tilemapy**, které čteš i zapisuješ za běhu (používej je jako herní plány, ne jen pozadí).
- **Pohyblivou kameru** (`set_view`) nad světem větším než obrazovka, s pevnými (HUD) vrstvami.
- **Particles**, kreslicí **Canvas** a **StripDraw** pro celosnímkové efekty bez vlastního pixelového bufferu.
- **Audio** (PWM tóny + `.wav`), **ukládání do NVM** pro nejvyšší skóre/nastavení, přibalený **font** + HUD pomocníky.
- **Desktopový simulátor**: stejný herní kód běží na tvém PC (headless snímky obrazovky nebo živé okno), takže stavíš a ladíš bez hardwaru.

## Navrhuj s ohledem na omezení

- **Dostupná RAM závisí na desce a firmwaru.** Nejvíc paměti spotřebují velké pixelové buffery
  a atlasy spritů. Velké světy skládej z dlaždic, atlasy načítej po částech a StripDraw použij tam,
  kde nepotřebuješ uchovávat pixely. Naměřené rozpočty a varianty najdeš na stránce
  [Vejít se do RAM](/cs/memory/).
- **Jeden displej, žádné GPU.** Bez shaderů a prolínání alfa kanálem. Průhlednost určuje jediný průhledný
  index nebo barva; pro efekt ztmavení existuje režim `shadow`. Transformace používají nejbližšího souseda (ostré při
  celočíselném škálování, mihotavé při zlomkovém).
- **Paletová grafika.** PAL8 je 1 bajt/pixel (levné); RGB565 je 2 bajty/pixel. Barvy sestavuj pomocí
  `rgb565(r, g, b)`, nikdy ne syrově `0xRRGGBB`.
- **Málo tlačítek.** D-pad + A/B (a někdy X/Y). Ovládání navrhuj podle toho.
- **Dodávej `.mpy`, ne velké `.py`.** Kompilace velkého zdrojového souboru přímo na zařízení může skončit `MemoryError`; předkompiluj
  do `.mpy`. Viz [Spuštění na hardwaru](/cs/hardware/).

## Kde začít

1. Přečti si [Jak picogame funguje](/cs/concepts/how-it-works/) kvůli herní smyčce a dirty regions.
2. Spusť [první hru](/cs/start/first-game/) v prohlížeči nebo [desktopovém simulátoru](/cs/simulator/).
3. Při práci používej [tahák k API](/cs/reference/) a [průvodce funkcemi](/cs/features/).
4. Uprav vzor z [příkladů](/cs/examples/) podle svého žánru.
