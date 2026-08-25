# Grafika a herní prostředky

picogame drží **grafiku oddělenou od kódu**. Prototyp může používat tvary vytvořené v kódu a
později je můžeš nahradit pixel artem beze změny herní logiky. Tato stránka ukazuje, jak přidat vlastní
grafiku, kde ji sehnat zdarma a jak to dělají tutoriály.

Každý tutoriál končí souborem **`bonus_art.py`**, který používá volnou grafiku
[CC0](https://creativecommons.org/publicdomain/zero/1.0/). Porovnej ho se `step8` nebo `step9`;
herní logika zůstává stejná a mění se vytvoření bitmap.

| Tutoriál | bonus používá | z (CC0) |
|----------|-----------|------------|
| 01-bounce | cihlová zeď = CC0 cihlová textura **přebarvená** do 4 barev řádků (míček/pálka zůstávají generované) | Kenney **Tiny Dungeon** |
| 02-starship | loď v 16 předem otočených snímcích + laserová střela | Kenney **Pixel Shmup** |
| 03-quest | tileset (podlaha/láva/sud/cihla/dveře/truhla) + hrdina + sliz + mince | Kenney **Tiny Dungeon** |

Spuštění jednoho:
```bash
python3 sim/run.py tutorials/03-quest/bonus_art.py --shot /tmp/out.png
```

## Převod PNG na sprite picogame

`tools/png2picogame.py` převede PNG na Python modul s funkcí `bitmap(pg)`:
```bash
python3 tools/png2picogame.py hero.png -o hero_art.py --frames 8
```
poté ve hře:
```python
import hero_art
hero = pg.Sprite(hero_art.bitmap(pg), x, y)        # náhrada bitmapy vytvořené přes shp.*()
```
Možnosti:
- `--frames N` — PNG je **vodorovný pruh** N stejně širokých snímků zleva doprava.
- `--tile WxH` — PNG je **mřížka tiles** W×H; nástroj je přebalí do vodorovného atlasu.
- formát je automatický (PAL8 pokud ≤256 barev, jinak RGB565); transparentnost pochází z
  alfa kanálu PNG (alfa ≥128 = neprůhledné); barvy se ukládají ve wire order pro ST7789.

### Zkontroluj to před nasazením
Než cokoli nahraješ do desky, vlož nový sprite do testovacího souboru a spusť ho v desktopovém
simulátoru se snímkem obrazovky — je to nejrychlejší způsob, jak ověřit, že paleta, měřítko i
transparentnost vyšly správně:
```bash
python3 sim/run.py <tvuj_test>.py --frames 1 --shot /tmp/art.png
```
Pokud to vypadá špatně nebo je to příliš velké, tady je proč: měkké nebo vyhlazené okraje se
kvantizují špatně (kolem spritu uvidíš okraje nebo šum — překresli s tvrdou alfou) a zdroj s víc
než 256 barvami tiše přepne na RGB565, což zdvojnásobí spotřebu RAM u bitmapy (zmenši paletu, aby
zůstala PAL8).

## Pravidla rozvržení
- **Vodorovný pruh** stejně širokých snímků. Pro mřížku použij `--tile WxH`, nebo v Aseprite
  exportu nastav `Sheet Type: Horizontal` a vypni Trim.
- **Transparentnost = alfa kanál** bez částečného prolínání. Měkké okraje se při převodu kvantizují.
- **Tilesety:** engine kreslí hodnotu tile `v` jako snímek `v`, proto nastav **snímek 0 jako
  prázdný nebo průhledný** a grafiku tiles vlož na pozice 1, 2, 3…
- **Rotace:** pro stálé krokované otáčení můžeš směry připravit jako snímky; pro plynulou nebo občasnou rotaci použij `sprite.angle`. Loď ve Starship je
  předem otočená do 16 snímků a pak
  `ship.frame = angle`.

## Použití vlastní grafiky z Aseprite
`File → Export Sprite Sheet → Sheet Type: Horizontal`, **Trim OFF**, Padding 0 → to je
přesně ten pruh, který `png2picogame` chce. Navrhuj v režimu **Indexed** s malou paletou
(nebo RGBA s průhledným pozadím). Animační **Frame Tags** mohou určovat rozsahy snímků.

## Kde získat víc (zdarma)
- **[kenney.nl](https://kenney.nl)** — vše CC0, bez nutnosti uvádět autora. (Použili jsme Pixel Shmup a Tiny Dungeon.)
- **[Pixellab.ai](https://www.pixellab.ai/)** — generuje pixel-art sprity a tilesety z textového
  zadání. Hodí se pro zástupnou grafiku nebo vlastní styl. Před publikováním zkontroluj podmínky exportu.
- Grafiku CC0 můžeš přebarvit. Cihly v Bounce používají jeden šedý tile z Tiny Dungeon
  vynásobenou do čtyř barev odpovídajících paletě hry.
- **[itch.io](https://itch.io)** (filtr CC0) a **[OpenGameArt](https://opengameart.org)** (filtr CC0). Vyhni se grafice pod CC-BY-SA / GPL.

## Distribuce grafiky jako .mpy
Modul s převedenou grafikou je Python, takže ho můžeš zkompilovat do `.mpy` stejně jako
pomocné knihovny. Zařízení potom nemusí parsovat zdrojový soubor, což zmenší dočasnou spotřebu
RAM při importu a obvykle urychlí načtení:
```bash
mpy-cross your_assets.py -o your_assets.mpy
```
Potom zkopíruj `.mpy` do `CIRCUITPY/lib/`. Verze `mpy-cross` **musí odpovídat CircuitPythonu na
desce**; použitou verzi zjistíš v `tools/build_mpy.sh`. Pozor: zastaralé `.mpy` **stíní `.py`**
při importu, takže ho po každé úpravě znovu vygeneruj — jinak zařízení dál načítá starou grafiku.

## Jeden soubor s veškerou grafikou
U hry s několika sdílenými prostředky můžeš související bitmapy a palety držet v **jednom
modulu**, například `assets.py`. Hra jej importuje jednou a k distribuci stačí jedno `.mpy`.
- `tools/pack_assets.py` to provede jedním příkazem: předej mu masku souborů PNG nebo složku a
  zabalí je všechny do jednoho modulu s **jednou sdílenou paletou**, kterou znovu použije každá bitmapa
  (úspora RAM); každá je vystavena jako hotová pojmenovaná `Bitmap`. Přidej `--mpy` a vznikne i bytecode.
  ```bash
  python3 tools/pack_assets.py art/*.png -o assets.py --mpy   # pak: import assets; pg.Sprite(assets.ship)
  ```
  (Když součet barev překročí 255, přepne se na palety po jednotlivých assetech, a obrázek s víc než 255
  vlastními barvami vyjde jako RGB565 — stejné automatické chování jako u `png2picogame`.)
- `tools/png2picogame.py` převede jedno PNG na bitmapový modul — použij ho, když chceš jen jeden obrázek
  (má i `--frames`, `--tile`, `--rle`, dithering, dedup).
- Pro celou úroveň založenou na tiles/scéně `tools/scene_build.py` napeče grafiku **i** rozvržení
  do jednoho souboru `SCENE`, který čte `picogame_scene.load()` — jeden soubor pro celou úroveň.

## Licencování / kredity
Veškerá přibalená grafika je **CC0** (volné dílo, není vyžadováno uvádění autora). Zdrojová
PNG, která jsme použili, žijí v `assets/kenney/` se souborem `assets/kenney/CREDITS.txt`.
I u CC0 je slušnost ponechat poznámku s kredity, když hru zveřejníš.
