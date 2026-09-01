# Build firmwaru

Firmware pro PicoPad je build CircuitPythonu se zapnutým nativním modulem `picogame`.

## Build a nahrání

Předpoklady: **ARM GCC ≥ 14** a inicializované submoduly.

```bash
# z kořene forku CircuitPythonu
make -C ports/raspberrypi BOARD=pajenicko_picopad -j"$(nproc)"
```

Výstup: `ports/raspberrypi/build-pajenicko_picopad/firmware.uf2`. Nahraj přes **BOOTSEL**
(podrž BOOTSEL při zapojení, pak přetáhni `.uf2` na disk `RPI-RP2`) jako každý CircuitPython
firmware.

Viz [Spuštění na hardwaru](hardware.md) pro stranu zařízení a [Vejít se do RAM](memory.md)
pro RAM rozpočet.

## Kde picogame žije ve stromu

Engine je ve větvi `picogame` forku CircuitPythonu. Implementaci obsahují dva adresáře modulu
a volby buildu zapínají samotný modul i volitelné backendy.

| Cesta | Co |
|---|---|
| `shared-bindings/picogame/` | Python API + docstringy: `__init__`, `Scene`, `Sprite`, `Bitmap`, `Tilemap`, `Canvas`, `Particles`, `Display`, `Framebuffer` |
| `shared-module/picogame/` | **přenositelné** C jádro — implementace blit / scene / tilemap / particles / canvas, bez závislosti na portu |
| `ports/*/common-hal/picogame/Display.c` | volitelný rychlý backend konkrétního portu (raspberrypi a espressif ho mají) |

Změny v systému buildu:

| Soubor | Změna |
|---|---|
| `py/circuitpy_mpconfig.mk` | registruje pět flagů `CIRCUITPY_PICOGAME*` — všechny výchozí `0` |
| `py/circuitpy_defns.mk` | překládá `picogame/%` jen při `CIRCUITPY_PICOGAME = 1`; přidá `common-hal/picogame/Display.c` jen při `FAST_DISPLAY = 1` |
| `ports/raspberrypi/boards/pajenicko_picopad/` | deska, která engine zapíná (konfigurace níže) |

### Rychlý backend v portu

Přenositelné jádro v `shared-module/` skládá pixely do řádkového bufferu a předává jej
kompatibilnímu `busdisplay` přes `bus.send`. Tento backend mohou použít porty, které sestaví
picogame a zpřístupní podporovaný SPI displej. Každý `bus.send` **blokuje** CPU, dokud se
strip nepřenese přes SPI, takže vykreslování a přenos probíhají za sebou.

`ports/raspberrypi/common-hal/picogame/Display.c` je jediné místo, kde engine sahá do portu —
aby toto čekání omezil. Řídí SPI a DMA na RP2040 přímo:

- **Překryv.** Používá dva řádkové buffery a jeden strip přenáší pomocí DMA po SPI, *zatímco CPU skládá
  další*. Vykreslování a přenos tak běží souběžně. Na předchozí DMA čeká teprve těsně
  před znovupoužitím toho bufferu.
- **Přímý proud dat.** Otevře GRAM okno panelu jednou přes `busdisplay`, které nastaví DC pro
  první datový strip. Zbývající stripy potom přenáší přes DMA bez opakovaného nastavování a
  přepínání DC.
- **Znovu použitý DMA kanál.** Kanál se zabere jednou a zůstává přidělený přes měkké restarty
  i spouštění her. pico-SDK jej při měkkém restartu neuvolní, takže nové zabrání při každém
  vytvoření objektu by dostupné kanály postupně vyčerpalo.

`CIRCUITPY_PICOGAME_FAST_DISPLAY` zapíná typ `pg.Display` i příslušný soubor `common-hal`.
Bez této volby zůstává přenositelný backend přes `bus.send`. Překryv pomáhá při překreslení
více stripů, takže u malého dirty regionu je rozdíl malý a u celé obrazovky větší. Hodnota
25–30 % naměřená v benchmarku PicoPadu závisí na konfiguraci; podmínky popisuje stránka
[Takt, SPI a limity displeje](hardware-limits.md).

## Konfigurace desky

Deska zapíná engine ve svém `mpconfigboard.mk`:

```make
CIRCUITPY_PICOGAME = 1                # přelož engine dovnitř
CIRCUITPY_PICOGAME_FAST_DISPLAY = 1   # backend s asynchronním DMA pro port raspberrypi
CIRCUITPY_PICOGAME_RGB444 = 0         # podpora COLMOD v panelu (viz Volby buildu)
OPTIMIZATION_FLAGS = -O2 …            # vyladěné pro Cortex-M0+ (viz dodatek)
CFLAGS += -DCIRCUITPY_FIRMWARE_SIZE='(1536 * 1024)'   # + odpovídající změna linker skriptu
```

**SPI hodiny displeje (v `board.c`).** Požaduj **62,5 MHz** (125/2) pro ST7789, ne 60 —
dělička PL022 (jen sudá) zaokrouhlí 60 dolů na poloviční rychlost. Viz
[Hodiny, SPI a limity displeje](hardware-limits.md).

**Ponech firmware obecný.** Ponech plnou sadu modulů zapnutou; vypni jen to, co zařízení fyzicky
nemůže použít.

| Modul | Stav | Proč |
|---|---|---|
| `picogame` (+ rychlý DMA displej) | **zapnuto** | engine |
| nativní `_stage` (`CIRCUITPY_STAGE`) | zapnuto | umožní běh původních her ugame/stage vedle kompatibilní vrstvy **picogame-stage** |
| `ulab`, `synthio`, audio, `displayio`, `bitmaptools`, `vectorio`, Wi-Fi, `keypad`, … | zapnuto | obecné moduly se do firmwaru vejdou |
| `picodvi`, `_eve` | vypnuto | zařízení nemá DVI ani FT8xx hardware |
| `qrio` | vypnuto | *dekódování* QR vyžaduje kameru, kterou PicoPad nemá, a backend `quirc` zabírá přibližně 32 KB; *generování* QR přes `adafruit_miniqr` funguje dál |

Měřený build využil přibližně **88 %** firmwarové oblasti 1,5 MB. Hodnota se mění s
verzí CircuitPythonu a zapnutými moduly.

## Volby buildu

| Flag | Výchozí | Co dělá |
|---|---|---|
| `CIRCUITPY_PICOGAME` | `0` | přeloží engine dovnitř |
| `CIRCUITPY_PICOGAME_FAST_DISPLAY` | `0` | použije `Display` s asynchronním DMA pro porty raspberrypi a espressif; ostatní desky zůstanou na přenositelném backendu přes `bus.send` |
| `CIRCUITPY_PICOGAME_RGB444` | `0` | deska oznámí podporu 12bitového RGB444 (COLMOD) přes `picogame.RGB444_SUPPORTED`, aby hra zapnula `Display(rgb444=True)` jen tam, kde to pomáhá. Na PicoPadu je volba vypnutá, protože náklady na balení pixelů po stripech převážily úsporu přenosu SPI. |
| `CIRCUITPY_PICOGAME_FRAMEBUFFER` | `0` | backend s celoobrazovkovým framebufferem v RAM pro platformy s vlastním obrazovým výstupem (RP2350 DVI/HSTX, desktopový simulátor a WASM playground) místo SPI stripů |
| `CIRCUITPY_PICOGAME_XIP_MAP` | `0` | mapuje soubory z flashe pro 0-copy přístup (`pg.xip_map`); fork-only větev, ve stock buildech není | (`-romfs` varianty firmwaru (např. `64`) |

**Výška stripu.** Na SPI displeji se obrazovka skládá po `STRIP_H` řádcích.
`picogame_game.setup()` alokuje dva buffery o `šířka × STRIP_H × 2` bajtech. Framebufferový
backend je nealokuje a vrací pro oba hodnotu `None`. Výchozí hodnota SPI backendu závisí na
`FAST_DISPLAY`: **8** řádků s DMA a **24** bez DMA. Jde o výchozí hodnoty pro výkon měřených
backendů; menší hodnota vždy používá méně RAM. Nastavení pro desku změň přes
`-DPICOGAME_STRIP_H=N` a pro hru přes `picogame_game.setup(strip_h=N)`; za běhu čti
`picogame.STRIP_H`. Víc ve [Vejít se do RAM](memory.md).

---

## Dodatek: optimalizace překladače (vyladěné −O2)

rp2 port CircuitPythonu má výchozí `-O3`. Na Cortex-M0+ PicoPadu (bez SIMD, bez FPU, 16 KB XIP
cache) je většina toho, co `-O3` přidává, mrtvá váha — auto-vektorizéry nemají SIMD, na který
by mířily, a klonování funkcí / těžké rozvíjení smyček jen nafukuje flash. Deska proto dodává
**`-O2` plus pět levných smyčkových průchodů, které pixelovým smyčkám pomáhají**, což se
rychlostí enginu rovná `-O3` do ~1 % za ~150 KB méně flashe:

```make
OPTIMIZATION_FLAGS = -O2 -funswitch-loops -fpredictive-commoning -fgcse-after-reload \
                     -ftree-partial-pre -fsplit-paths
```

Jádro interpretu MicroPythonu (`gc.o`, `vm.o`) zůstává na `-O3` přes nastavení `SUPEROPT_*`,
takže rychlost běhu Pythonu tahle volba neovlivní. Nejteplejší jediná smyčka (základní sprite
blit) navíc nese `#pragma GCC unroll 4` — na M0+ ~8 % rychleji za +0,3 KB; `-funroll-loops`
přes celý firmware by přetekl flash oblast.

Naměřeno na zařízení; všechny buildy používají CircuitPython 10.3.0. **Méně = rychlejší** a nejlepší
ve sloupci **tučně**. **Engine** = `picogame_bench_hotpath.py` (108 spritů 32×32 přes 120
snímků na 320×240, ms/snímek min); **Python** = `bench_optlevel.py` (ms/op); **flash** = celý
velikost obrazu v KB. Řádek `O2+` je dodávaný referenční build; každé `🟢/🟡/🔴` značí, jak daleko buňka
sedí od něj (lepší / ≤5 % horší / >5 % horší).

| | bg-fill<br><sub>ms</sub> | plain<br><sub>ms</sub> | plain+bg<br><sub>ms</sub> | tint<br><sub>ms</sub> | transpose<br><sub>ms</sub> | bignum<br><sub>ms</sub> | int<br><sub>ms</sub> | float<br><sub>ms</sub> | fib<br><sub>ms</sub> | ulab-py<br><sub>ms</sub> | ulab-np<br><sub>ms</sub> | flash<br><sub>KB</sub> |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `-O3` *(výchozí rp2)* | **24.9** 🟢<sub>−1.2%</sub> | 36.3 🟡<sub>+0.8%</sub> | 37.0 🟡<sub>+0.1%</sub> | **80.2** 🟢<sub>−0.5%</sub> | 46.1 🟡<sub>+0.3%</sub> | 98.8 🔴<sub>+8.8%</sub> | 20.84 🟡<sub>+2.1%</sub> | 40.80 🟡<sub>+1.3%</sub> | **657.8** 🟢<sub>−0.0%</sub> | **2.63** 🟢<sub>−2.2%</sub> | 0.76 🔴<sub>+17%</sub> | 1499 🔴<sub>+11%</sub> |
| `-O2` | 25.3 🟡<sub>+0.4%</sub> | 38.2 🔴<sub>+5.9%</sub> | 39.1 🔴<sub>+5.7%</sub> | 81.2 🟡<sub>+0.8%</sub> | 53.9 🔴<sub>+17%</sub> | 92.0 🟡<sub>+1.3%</sub> | **20.29** 🟢<sub>−0.6%</sub> | 40.34 🟡<sub>+0.1%</sub> | 660.2 🟡<sub>+0.3%</sub> | 3.77 🔴<sub>+40%</sub> | 0.66 🟡<sub>+1.5%</sub> | 1326 🟢<sub>−1.4%</sub> |
| `-Os` | 27.0 🔴<sub>+7.4%</sub> | 43.6 🔴<sub>+21%</sub> | 46.4 🔴<sub>+25%</sub> | 121.9 🔴<sub>+51%</sub> | 103.0 🔴<sub>+124%</sub> | 113.3 🔴<sub>+25%</sub> | 21.18 🟡<sub>+3.7%</sub> | 44.07 🔴<sub>+9.4%</sub> | 667.3 🟡<sub>+1.4%</sub> | 3.00 🔴<sub>+11%</sub> | 0.73 🔴<sub>+12%</sub> | **1167** 🟢<sub>−13%</sub> |
| `O3−` *(−O3 bez vektorizérů + klonování)* | 25.2 🟡<sub>+0.1%</sub> | 36.2 🟡<sub>+0.5%</sub> | 37.2 🟡<sub>+0.6%</sub> | 81.5 🟡<sub>+1.1%</sub> | 46.1 🟡<sub>+0.2%</sub> | 96.1 🔴<sub>+5.8%</sub> | 20.32 🟢<sub>−0.5%</sub> | 40.95 🟡<sub>+1.7%</sub> | 662.8 🟡<sub>+0.7%</sub> | 2.75 🟡<sub>+2.2%</sub> | 0.68 🟡<sub>+4.6%</sub> | 1480 🔴<sub>+10%</sub> |
| **`O2+`** *(dodávaný — baseline)* | 25.2 | **36.0** | **37.0** | 80.6 | **46.0** | **90.8** | 20.42 | **40.28** | 658.0 | 2.69 | **0.65** | 1345 |

`-Os` zmenší flash nejvíc, ale rozbije affine/blend smyčky (`tint` +51 %, `transpose` +124 %);
`O3−` rychlost enginu sedí, přesto zůstává +134 KB, protože celofirmwarové inlinování `-O3`
přežije; sloupce Pythonu se téměř nemění, protože jádro interpretu je `-O3` v každém buildu.
(`bench_displayio.py` vyšel napříč úrovněmi plochý, tak je vynechaný.)
