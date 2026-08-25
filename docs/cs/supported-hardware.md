# Podporovaný hardware

picogame je nativní modul uvnitř forku CircuitPythonu, takže běží na deskách, pro které existuje
**picogame firmware** — ten potřebuje SPI displej, pár tlačítek a (volitelně) PWM reproduktor.
Pro desky níže existují hotové buildy; jiné desky CircuitPythonu s SPI displejem lze přidat (viz
[Postav si vlastní desku](CUSTOM_BOARD.md)). Referenční zařízení, na kterém se všechno ladí a
měří, je PicoPad.

## Zařízení

| Zařízení | MCU | Poznámky |
|---|---|---|
| **Pajenicko PicoPad** | RP2040 | **Primární / referenční zařízení.** 320×240 ST7789, D-pad + A/B/X/Y, reproduktor, SD, NVM. K dispozici je hotový firmware a profil tlačítek. |
| PicoPad 2 / desky s RP2350 | RP2350 | Pouze build, na tomto hardwaru zatím neověřené. Stejné rozložení a větší halda než u buildu pro RP2040. |
| Desky s ESP32-S3 (např. Feather TFT) | ESP32-S3 | Pouze build, na tomto hardwaru zatím neověřené. Tlačítka zapoj podle konkrétní desky. |
| Desktopový simulátor | tvůj počítač | Vývojový nástroj, ne cílové zařízení. Nabízí stejné API hry, ale nereprodukuje omezení RAM ani časování desky. |

Engine je nativní C modul ve forku CircuitPythonu. PicoPad má **hotový firmware**; pro ostatní desky
si fork pro danou desku sestavíš, viz [Build firmwaru](/cs/firmware/).

## Firmware ke stažení

Každý odkaz níže vede na build firmwaru pro jednu desku. Nahraj jej a potom zkopíruj
`code.py` a potřebné moduly v `lib/` z [picogame-libs](https://github.com/MakerClassCZ/picogame-libs).

:::caution[Zkontroluj stav své desky]
Firmware pro **PicoPad** je referenční build testovaný na zařízení. Buildy bez výslovného
označení „testováno“ v tabulce jsou experimentální a mohou vyžadovat úpravy pro konkrétní desku.
Pro opakovatelné vydání sestav fork CircuitPythonu pro přesnou desku a commit, který používáš
(viz [Build firmwaru](/cs/firmware/)).
:::

| Deska | Firmware |
|---|---|
| **Pajenicko PicoPad** (RP2040) — *testováno* | [`picopad.uf2`](/firmware/picopad.uf2) |
| PicoPad 2 (RP2350) — *DIY* | [`picopad2.uf2`](/firmware/picopad2.uf2) |
| PicoPad 2 W (RP2350) — *DIY* | [`picopad2w.uf2`](/firmware/picopad2w.uf2) |
| Pimoroni PicoSystem (RP2040) | [`picosystem.uf2`](/firmware/picosystem.uf2) |
| µGame22 (RP2040) | [`ugame22.uf2`](/firmware/ugame22.uf2) |
| Raspberry Pi Pico (RP2040) | [`pico.uf2`](/firmware/pico.uf2) |
| Raspberry Pi Pico W (RP2040) | [`pico_w.uf2`](/firmware/pico_w.uf2) |
| Raspberry Pi Pico 2 (RP2350) | [`pico2.uf2`](/firmware/pico2.uf2) |
| Raspberry Pi Pico 2 W (RP2350) | [`pico2_w.uf2`](/firmware/pico2_w.uf2) |
| TinyCircuits Thumby Color (RP2350) | [`thumby_color.uf2`](/firmware/thumby_color.uf2) |
| **Adafruit Fruit Jam** (RP2350B, **DVI/HDMI výstup**) — *testováno: DVI displej, audio TLV320, USB vstup, launcher* | [`fruitjam.uf2`](/firmware/fruitjam.uf2) |
| ESP32-S3 — obecné (Adafruit Feather TFT) | [`feather_s3.uf2`](/firmware/feather_s3.uf2) |
| µGame S3 (ESP32-S3) | [`ugame_s3.uf2`](/firmware/ugame_s3.uf2) |
| VIDI X (ESP32) | [`vidi_x.bin`](/firmware/vidi_x.bin) |

*Oba **PicoPad 2** buildy jsou **DIY / neoficiální**, pro PicoPad, kterému byl Pico modul vyměněn
za Pico 2 / Pico 2 W (RP2350). Oficiální Pico 2 PicoPad produkt neexistuje a není pro něj oficiální
CircuitPython: stejný hardware PicoPadu, jen víc RAM (~520 KB heap). Na vlastní riziko.*

*Build pro **Fruit Jam** vykresluje přes DVI framebuffer místo SPI panelu a je to dobře otestovaná
platforma — DVI vykreslování, audio TLV320, USB gamepad/klávesnice i launcher běží na hardwaru. Nastav
ho v `settings.toml`
(`CIRCUITPY_DISPLAY_WIDTH`/`_HEIGHT`/`_ROTATION`) s jednou ze dvou barevných hloubek — `setup()` zvládne
obě automaticky: `CIRCUITPY_DISPLAY_COLOR_DEPTH=16` pro plnobarevné RGB565 (např. 320×240), nebo `=8` pro
RGB332, jedinou hloubku, kterou picodvi nabízí při **640×480** (plné rozlišení). Detaily o
framebufferu a barevné hloubce viz [Spuštění na hardwaru](/cs/hardware/).
**Zvuk** na Fruit Jamu je I2S DAC TLV320 — nainstaluj `adafruit_tlv320` + `adafruit_bus_device` do
`CIRCUITPY/lib` (nedodávají se) a zvedni volume klíče, jinak je ticho; `PICOGAME_DEBUG=1` vypíše proč.
**Vstup** je USB gamepad nebo klávesnice (deska nemá herní tlačítka) — viz
[Vstup a ovládání](/cs/helpers/input/).*

**Flashování:** přepni desku do bootloaderu. Pico/PicoPad: drž **BOOTSEL** při připojení USB (nebo 2×
**RESET**) → objeví se USB disk `RPI-RP2` → přetáhni na něj `.uf2` → deska se restartuje jako `CIRCUITPY`. Pak
zkopíruj `code.py` + `lib/` moduly, které importuje. Na holém Picu ještě zapoj displej + tlačítka a
sestav displej v kódu (viz *Postav si vlastní* níže).

**K `.mpy` souborům:** složka hry může mít podsložku **`mpy/`**. To jsou **zkompilované MicroPython
moduly** (datové a grafické moduly hry přeložené přes `mpy-cross`): importují se rychleji, zaberou méně úložiště
a, hlavně na desce s málo RAM, vynechají nárazovou spotřebu RAM při parsování, kterou velký `.py`
při importu způsobí. **Na zařízení kopíruj soubory z `mpy/` vedle `code.py`** (ne zdrojové `.py` moduly s grafikou);
volné `.py` jsou zdroj, který přímo spouští **simulátor**. Stejný princip jako přibalené `lib/*.mpy`.

**Klasický ESP32** (VIDI X) se distribuuje jako `.bin` a flashuje přes `esptool` (nemá UF2 bootloader);
desky ESP32-**S3** používají běžné kopírování souboru UF2 na připojený disk.

:::note[Nastavení displeje, zvuku a tlačítek]
**Displej a zvuk se mapují samy** všude, kde je firmware desky vystavuje; picogame vezme obrazovku, kterou deska poskytuje (`picogame_game.screen()`), a výstup vybraný přes `picogame_audioout` (PWM pin reproduktoru, nebo I2S DAC tam, kde ho deska má), což handheldy s vestavěným displejem zde (PicoSystem, µGame22, µGame S3, Thumby Color, VIDI X) definují. Na nich tedy displej naběhne bez nastavování; zvuk funguje, když deska pojmenuje pin reproduktoru (jinak ho předej: `picogame_audio.Audio(pin)`). Na **desce s I2S DAC (Fruit Jam)** nainstaluj `adafruit_tlv320` + `adafruit_bus_device` a nastav volume klíče, jinak zůstane ticho — viz [Audio a hudba](/cs/helpers/audio/).

**Tlačítka** se mapují automaticky na deskách s profilem picogame: **PicoPad, PicoSystem,
µGame22, µGame S3 a Thumby Color**. **VIDI X** potřebuje zvláštní obsluhu, protože jeho D-pad
používá analogový odporový dělič. Neuvedené desky vyžadují vlastní mapu. Na **desce s USB hostem
(Fruit Jam)** je vstupem USB gamepad nebo klávesnice (připojí se automaticky; viz
[Vstup a ovládání](/cs/helpers/input/)). GPIO mapu nastav v `settings.toml` bez nového buildu
firmwaru; profily v `picogame_input.py` slouží jako vzory:

```toml
PICOGAME_BUTTONS = "UP=GP4 DOWN=GP5 LEFT=GP3 RIGHT=GP2 A=GP7 B=GP6 X=GP9 Y=GP8"
```

Na desce **bez vestavěného displeje** (holý Pico) navíc sestavíš displej v kódu. Oba kroky ukazuje *Postav si vlastní → Oživení* níže.
:::

## Co deska potřebuje

- **MCU podporované CircuitPythonem** — testované rodiny jsou RP2040, RP2350 a ESP32-S3.
- **RAM** obvykle určuje rozpočet na grafiku. Aktuálně měřené buildy poskytují přibližně
  **190 KB** haldy na RP2040 a **520 KB** na RP2350. Největší souvislý blok je menší a mění se
  podle konfigurace firmwaru, proto svůj build změř (viz [Vejít se do paměti](/cs/memory/)).
- **SPI displej** ovládaný přes `displayio` (nebo DVI/HSTX framebuffer na RP2350 deskách jako Fruit Jam).
- **Pár tlačítek** na GPIO — základ je D-pad + A/B; X/Y jsou volitelné. Nebo USB gamepad/klávesnice na desce s USB hostem.
- **Volitelně: pin s PWM** pro malý reproduktor, **nebo I2S DAC** (zvuk je opt-in).

## Displeje

picogame používá SPI vrstvu `displayio`. Níže uvedené řadiče jsou současné testované nebo
podporované cíle; jiné SPI displeje podporované v `displayio` je potřeba ověřit.

- **Rozlišení je flexibilní, pokud si ho hra přečte.** 320×240 je referenční velikost. Engine a `Scene`
  vykreslí na jakoukoli velikost, kterou displej hlásí, ale hra se z té velikosti musí *rozvrhnout* sama,
  ne mít 320×240 napevno: přečti `picogame_game.screen()` a layout z toho odvoď. Příklad `arkanoid`
  to dělá přesně tak (šířka cihly = šířka displeje ÷ počet sloupců), takže **stejný soubor běží na 240px
  i 320px** obrazovce. Menší šířka/výška jen znamená menší hrací plochu.
- **Řadiče:** **ST7789** je referenční (PicoPad). Fungují i **ST7735** (menší panely) a **ILI9341**, stejně
  jako další SPI řadiče podporované `displayio`.
- **12bitová barva (RGB444):** firmware umí posílat 12 bitů místo 16, aby snížil provoz na SPI u scén
  omezených přenosem. Jde o volitelnou schopnost danou při kompilaci: výchozí je všude RGB565 a hra
  12 bitů zapne jen tam, kde to deska inzeruje (`picogame.RGB444_SUPPORTED`, např.
  `rgb444="auto"` v `picogame_game.setup`). Požadavek `rgb444=True` v buildu bez podpory vyvolá
  chybu, místo aby špatně řídil panel (ST7789/ST7735 mají COLMOD 12-bit, ILI9341 ne). Detaily v
  [Hodiny, SPI a limity displeje](/cs/hardware-limits/).

## Postav si vlastní na nepájivém poli

Žádná deska ze seznamu? Vlastní picogame konzoli si postavíš levně sám. Minimum je:

- **Raspberry Pi Pico** — funguje Pico 1, Pico W i **Pico 2**;
- **displej 320×240 po SPI** s řadičem **ST7789** nebo **ILI9341**;
- **aspoň 6 tlačítek** — D-pad + A/B (přidej X/Y pro další dvě);
- malý **piezo bzučák** na zvuk (volitelně).

To stačí na všechno na tomhle webu. Kompletní pinovou mapu, tři způsoby, jak získat `board.DISPLAY`,
konfiguraci tlačítek v `settings.toml` a ladění orientace/barev najdeš v **[Postav si vlastní
desku](CUSTOM_BOARD.md)**.

![Zapojení na nepájivém poli — Raspberry Pi Pico, displej 320×240 ST7789/ILI9341, šest tlačítek a piezo bzučák](../img/breadboard.png)

Zapoj `vcc / gnd / cs / res / dc / mosi / sck / bl` displeje, šest tlačítek a piezo podle schématu.
Konkrétní GPIO piny a odpovídající mapu tlačítek v `settings.toml` najdeš na stránce
[Postav si vlastní desku](CUSTOM_BOARD.md); video s postavením chystáme.
