# picogame — co použít na co

Jedna stránka, jeden úkol: víš, co chceš postavit — tenhle rejstřík říká, **kterou část použít**,
a odkazuje na stránku, která ji vysvětluje. (Jsi v enginu nový? Přečti si nejdřív
[Jak picogame funguje](/cs/concepts/how-it-works/).)

## Kreslení & obrazovka

RAM ve zkratce: uchovávaný celoobrazovkový `Canvas` ≈ 150 KB; `StripDraw` / `Tilemap` ≈ 0 — úplné ceny v [Kreslicích cestách](/cs/concepts/drawing-paths/).

| Chci… | Použij | Detaily |
|---|---|---|
| zobrazit pohybující se objekt (hráč, nepřítel, střela) | `Sprite` | [Reference](../reference.md) |
| nakreslit mapu / velký scrollující svět | `Tilemap` (1 B na buňku) | [Kreslicí cesty](/cs/concepts/drawing-paths/) |
| levně nakreslit animovaný celoobrazovkový efekt (obloha, silnice, gradient) | `StripDraw` (bez uchovávaného pixelového bufferu) | [Kreslicí cesty](/cs/concepts/drawing-paths/) |
| panel, který se mění zřídka (orámovaný box, ukazatel) | `Canvas` (uchovává `w*h*2` B) | [Kreslicí cesty](/cs/concepts/drawing-paths/) |
| stavový řádek / HUD / dialog / menu | widgety `picogame_ui` — vyber podle rozhodovací matice | [Kreslicí cesty](/cs/concepts/drawing-paths/) · [Text a UI](/cs/helpers/text-ui/) |
| rotovat / škálovat sprite za běhu | `Sprite.scale` / `Sprite.angle`; pro mnoho stále rotujících objektů připrav snímky předem | [Sestavování scén](/cs/helpers/building-scenes/) |
| přebarvit / bliknout / zprůhlednit sprite bez bitmap navíc | blit efekty `flash` / `tint` / `dither` / `shadow` (vždy jeden naráz) | [Reference](../reference.md) |
| ostrá otočka o 90° bez blikotání | `transpose` + flipy (všech 8 orientací) | [Reference](../reference.md) |
| sledovat hráče kamerou | `scene.set_view(ox, oy)` + HUD vrstvy s `fixed=True` | [Herní vzory](/cs/concepts/patterns/) |
| otřes obrazovky / přechod / plynulá kamera | `picogame_fx` | [Efekty a odezva](/cs/helpers/effects/) |
| animovaná voda/láva, cyklování palety | `picogame_palette` | [Efekty & juice](/cs/helpers/effects/) |
| spousta malých jisker / úlomků | `Particles` | [Reference](../reference.md) |
| terén / obloha s přirozenou variací | šum počítaný v C: `value2d` / `fbm2d` | [Reference](../reference.md) |
| pseudo-3D podlaha nebo first-person stěny | `Canvas.mode7` (podlaha, přes `picogame_mode7`) / `picogame_ray` (stěny) — obojí do `StripDraw` | [Pseudo-3D](/cs/helpers/pseudo-3d/) |
| skutečné flat-shaded polygonové 3D (blocky světy, low-poly) | `pg.project` (dávková projekce, float/fixed podle `pg.FPU`) + `pg.Triangles` (C-kompozitovaná dávková vrstva; na canvas cestě `Canvas.fill_triangles`) | [Pseudo-3D](/cs/helpers/pseudo-3d/) · [Reference](/cs/reference/) |
| izometrická deska (RPG / taktiky / builder) | `picogame_iso.IsoView` (celočíselná projekce + painter's klíč + dávka `emit_blocks`) | [Pseudo-3D](/cs/helpers/pseudo-3d/) |
| závodní silnice ve stylu OutRun ve 30 fps | `pg.road_edges` + `Canvas.road` (per-scanline smyčka v C, do `StripDraw`) | [Reference](/cs/reference/) |

## Hratelnost

| Chci… | Použij | Detaily |
|---|---|---|
| detekovat zásahy | `a.overlaps(b)` (box), `a.near(b, r)` (kruh), `picogame_tiles` (sonda do mřížky) | [Matematika & kolize](/cs/helpers/math/) |
| vystřelit hodně střel / vytvářet nepřátele | `picogame_pool.Pool` — často používané sprity znovu využívej | [Úryvky kódu](/cs/snippets/) |
| animovat sprite (chůze, klid, výbuch) | `sprite.frame` ručně, nebo časový modul `picogame_anim` | [Animace](/cs/helpers/animation/) |
| meziscéna / titulní obrázek bez framebufferu | `picogame_cutscene` (čte postupně z flash) | [Animace](/cs/helpers/animation/) |
| číst tlačítka přes stejné API | `picogame_input.Buttons` | [Vstup a ovládání](/cs/helpers/input/) |
| hrát s USB gamepadem nebo klávesnicí (desky s USB hostem, např. Fruit Jam) | `picogame_usbpad` / `picogame_usbkbd` (připojené automaticky přes `Buttons`) | [Vstup a ovládání](/cs/helpers/input/) |
| dát každému hráči vlastní ovladač (lokální multiplayer) | jeden `Buttons(sources=[pad])` na hráče + `find_pads()` | [Vstup a ovládání](/cs/helpers/input/#lokální-multiplayer) |
| tolerovat skok krátce po opuštění hrany nebo stisk před dopadem | `picogame_input.Timer` | [Spuštění a herní smyčka](/cs/helpers/boot-loop/) · [Úryvky kódu](/cs/snippets/) |
| pohyb nezávislý na snímkové frekvenci | `picogame_clock.Clock` (dt) / `FixedStep` (deterministický) | [Boot a herní smyčka](/cs/helpers/boot-loop/) |
| opakovatelné náhodné hodnoty a rovnoměrné generování objektů | `picogame_rand` | [Matematika a kolize](/cs/helpers/math/) |
| přehrávat zvuky (samply vs. synth vs. MIDI) | `picogame_audio` (WAV) / `picogame_synth` (synthio) | [Audio a hudba](/cs/helpers/audio/) |
| hotová sada charakteristických efektů bez ladění not | `picogame_sfx` (`Kit` nad `picogame_synth`) | [Audio a hudba](/cs/helpers/audio/#picogame_sfx) |
| uložit nejvyšší skóre (pro *zobrazení* skóre na obrazovce viz [Text a UI](/cs/helpers/text-ui/)) | `picogame_save` (NVM) | [Ukládání & paměť](/cs/helpers/data/) |
| tvořit mnoho úrovní | deklarativní formát scény + editor; malé úrovně napiš ručně | [Formát scény](../scene-format.md) · [Sestavování scén](/cs/helpers/building-scenes/) |
| pauza / menu nad živou scénou | `picogame_game.overlay()` | [Snippety](/cs/snippets/) |

## Vejít se do zařízení

| Chci… | Použij | Detaily |
|---|---|---|
| vejít se do RAM | rozpočet → měření → optimalizace | [Vejít se do paměti](../memory.md) |
| udržet stálý frame rate | herní smyčka ve funkci, dirty-rect-friendly pohyb, 0-RAM vrstvy | [Výkon](/cs/performance/) |
| uložit velkou grafiku / mnoho snímků | zmrazená data vs. soubor→RAM vs. postupné čtení (`picogame_stream`) | [Vejít se do paměti](../memory.md) |
| zmenšit tileset | `png2picogame.py --dedup` (sloučí otočené a zrcadlené tily) | [Průvodce enginem](../engine.md) |
| pochopit rychlé DMA a přenositelné vykreslování | `pg.Display` vs. běžný busdisplay | [Průvodce enginem](../engine.md) |
| běžet v 640×480 přes HDMI (Fruit Jam) | `CIRCUITPY_DISPLAY_COLOR_DEPTH = 8` (RGB332, řeší `setup()` automaticky) | [Spuštění na hardwaru](../hardware.md) |
| běžet na desce, kterou sis sám zapojil | předpřipravený generický firmware + `settings.toml` (`PICOGAME_BUTTONS`, displej, matice, USB klíče) | [Vlastní deska](../custom-board.md) |
| nasadit na zařízení / řešit problémy | `.mpy`, lib bundle, sériová konzole | [Spuštění na hardwaru](../hardware.md) |

Stránka *Detaily* u každého řádku nese chování, náklady i záludnosti — tahle stránka
schválně nic z toho neopakuje.
