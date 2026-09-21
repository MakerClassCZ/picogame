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

Engine je součástí samotného CircuitPythonu — `shared-bindings/picogame/` a
`shared-module/picogame/` žijí v adafruit/circuitpython, ve výchozím stavu vypnuté a zapínané po
deskách. Fork MakerClass nese už jen to, co upstream není (experimentální větve a desky čekající na
PR). Implementaci obsahují dva adresáře modulu a volby buildu zapínají samotný modul i volitelné
backendy.

| Cesta | Co |
|---|---|
| `shared-bindings/picogame/` | Python API + docstringy: `__init__`, `Scene`, `Sprite`, `Bitmap`, `Tilemap`, `Canvas`, `Particles`, `Display`, `Framebuffer` |
| `shared-module/picogame/` | **přenositelné** C jádro — implementace blit / scene / tilemap / particles / canvas, bez závislosti na portu |
| `ports/*/common-hal/picogame/Display.c` | volitelný rychlý backend konkrétního portu (mají ho raspberrypi, espressif a atmel-samd) |

Změny v systému buildu:

| Soubor | Změna |
|---|---|
| `py/circuitpy_mpconfig.mk` | registruje flagy `CIRCUITPY_PICOGAME*` — čtyři přepínače mají výchozí `0`; `CIRCUITPY_PICOGAME_FPU` se nenastavuje a řídí se architekturou |
| `py/circuitpy_defns.mk` | překládá `picogame/%` jen při `CIRCUITPY_PICOGAME = 1`; přidá `common-hal/picogame/Display.c` jen při `FAST_DISPLAY = 1` |
| `ports/*/boards/<deska>/mpconfigboard.mk` | desky, které engine zapínají — PicoPad, PicoSystem, Fruit Jam, Pico, Pico W (raspberrypi) a PyBadge (atmel-samd); konfigurace níže |

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
CIRCUITPY_PICOGAME_RGB444 = 1         # podpora COLMOD v panelu (viz Volby buildu)
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
| `CIRCUITPY_PICOGAME_FAST_DISPLAY` | `0` | použije `Display` s asynchronním DMA portu (raspberrypi, espressif, atmel-samd); ostatní desky zůstanou na přenositelném backendu přes `bus.send` |
| `CIRCUITPY_PICOGAME_RGB444` | `0` | deska oznámí podporu 12bitového RGB444 (COLMOD) přes `picogame.RGB444_SUPPORTED`, aby hra zapnula `Display(rgb444=True)` jen tam, kde to pomáhá. Obě desky PicoPad i PyBadge mají `1` (schopnost je přeložená dovnitř); jestli ji hra použije, se rozhoduje za běhu — `picogame_game.setup(rgb444=…)`, nebo `PICOGAME_RGB444` v `settings.toml` jako výchozí hodnota pro danou krabičku. Změřeno jako výhra na obou (PicoPad i 24MHz sběrnice PyBadge). |
| `CIRCUITPY_PICOGAME_FRAMEBUFFER` | `0` | backend s celoobrazovkovým framebufferem v RAM pro platformy s vlastním obrazovým výstupem (RP2350 DVI/HSTX, desktopový simulátor a WASM playground) místo SPI stripů |

Mapování souboru z flashe pro 0-copy přístup už není flag picogame: staré `pg.xip_map(path)`
nahradilo `storage.map_file(file)`, které bere **otevřený soubor** a míří do upstreamu místo do
enginu.

**Výška stripu.** Na SPI displeji se obrazovka skládá po `STRIP_H` řádcích.
`picogame_game.setup()` alokuje dva buffery o `šířka × STRIP_H × 2` bajtech. Framebufferový
backend je nealokuje a vrací pro oba hodnotu `None`. Výchozí hodnota SPI backendu závisí na
`FAST_DISPLAY`: **8** řádků s DMA a **24** bez DMA. Jde o výchozí hodnoty pro výkon měřených
backendů; menší hodnota vždy používá méně RAM. Nastavení pro desku změň přes
`-DPICOGAME_STRIP_H=N` a pro hru přes `picogame_game.setup(strip_h=N)`; za běhu čti
`picogame.STRIP_H`. Víc ve [Vejít se do RAM](memory.md).

---

## Dodatek: optimalizace překladače (vyladěné −O2)

rp2 port CircuitPythonu měl dřív výchozí `-O3`. Na Cortex-M0+ (bez SIMD, bez FPU, 16 KB XIP
cache) je většina toho, co `-O3` přidává, mrtvá váha — auto-vektorizéry nemají SIMD, na který
by mířily, a klonování funkcí i těžké rozvíjení smyček jen nafukuje flash. Od CircuitPythonu 10.4
je výchozí hodnotou **portu** `-O2` plus dva levné průchody (`ports/raspberrypi/Makefile`), takže
žádná deska už nenese vlastní řádek `OPTIMIZATION_FLAGS`:

```make
OPTIMIZATION_FLAGS ?= -O2 -funswitch-loops -fvect-cost-model=dynamic
```

Ty dva se nepřekrývají. `-funswitch-loops` patří sprite blitu a mode7 (blit 113 → 87 µs) a stojí
16 KB; `-fvect-cost-model=dynamic` — jediná věc, kterou `-O3` mění na vektorizaci, z `very-cheap`
na `dynamic` — patří výplním, kopiím paměti a AES (`fill_rect` 1163 → 732 µs, kopie 4 KB
`bytearray` 3857 → 2441 µs) a stojí 4 KB. Dohromady dosáhnou rychlosti `-O3` na každém měřeném
kernelu za **+20 664 bajtů proti `-O2` místo +151 020 u `-O3`** — tedy asi 130 KB flashe zpátky na
každé rp2 desce, ať picogame používá, nebo ne.

Starší verze této stránky doporučovala `-O2` plus pět průchodů. Měření po jednom (GCC 15.2,
`raspberry_pi_pico`) ukázalo, že si místo zasloužil jen `-funswitch-loops`;
`-fpredictive-commoning`, `-fgcse-after-reload`, `-ftree-partial-pre` a `-fsplit-paths` vyrobily
kód, který měřil stejně jako čisté `-O2`. Tabulka níž pochází z té starší **úrovňové** sady a
zůstává kvůli porovnání úrovní; její řádek `O2+` je vyřazený build s pěti průchody.

Jádro interpretu MicroPythonu (`gc.o`, `vm.o`) zůstává na `-O3` přes nastavení `SUPEROPT_*`,
takže rychlost běhu Pythonu tahle volba neovlivní. Nejteplejší jediná smyčka (základní sprite
blit) navíc nese `#pragma GCC unroll 4` — na M0+ ~6 % rychleji za +0,6 KB; `-funroll-loops`
přes celý firmware by přetekl flash oblast.

Naměřeno na zařízení; všechny buildy používají CircuitPython 10.3.0. **Méně = rychlejší** a nejlepší
ve sloupci **tučně**. **Engine** = `picogame_bench_hotpath.py` (108 spritů 32×32 přes 120
snímků na 320×240, ms/snímek min); **Python** = `bench_optlevel.py` (ms/op); **flash** = celý
velikost obrazu v KB. Řádek `O2+` je baseline (build s pěti průchody, který tahle stránka dřív
doporučovala); každé `🟢/🟡/🔴` značí, jak daleko buňka sedí od něj (lepší / ≤5 % horší / >5 % horší).

| | bg-fill<br><sub>ms</sub> | plain<br><sub>ms</sub> | plain+bg<br><sub>ms</sub> | tint<br><sub>ms</sub> | transpose<br><sub>ms</sub> | bignum<br><sub>ms</sub> | int<br><sub>ms</sub> | float<br><sub>ms</sub> | fib<br><sub>ms</sub> | ulab-py<br><sub>ms</sub> | ulab-np<br><sub>ms</sub> | flash<br><sub>KB</sub> |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `-O3` *(výchozí rp2)* | **24.9** 🟢<sub>−1.2%</sub> | 36.3 🟡<sub>+0.8%</sub> | 37.0 🟡<sub>+0.1%</sub> | **80.2** 🟢<sub>−0.5%</sub> | 46.1 🟡<sub>+0.3%</sub> | 98.8 🔴<sub>+8.8%</sub> | 20.84 🟡<sub>+2.1%</sub> | 40.80 🟡<sub>+1.3%</sub> | **657.8** 🟢<sub>−0.0%</sub> | **2.63** 🟢<sub>−2.2%</sub> | 0.76 🔴<sub>+17%</sub> | 1499 🔴<sub>+11%</sub> |
| `-O2` | 25.3 🟡<sub>+0.4%</sub> | 38.2 🔴<sub>+5.9%</sub> | 39.1 🔴<sub>+5.7%</sub> | 81.2 🟡<sub>+0.8%</sub> | 53.9 🔴<sub>+17%</sub> | 92.0 🟡<sub>+1.3%</sub> | **20.29** 🟢<sub>−0.6%</sub> | 40.34 🟡<sub>+0.1%</sub> | 660.2 🟡<sub>+0.3%</sub> | 3.77 🔴<sub>+40%</sub> | 0.66 🟡<sub>+1.5%</sub> | 1326 🟢<sub>−1.4%</sub> |
| `-Os` | 27.0 🔴<sub>+7.4%</sub> | 43.6 🔴<sub>+21%</sub> | 46.4 🔴<sub>+25%</sub> | 121.9 🔴<sub>+51%</sub> | 103.0 🔴<sub>+124%</sub> | 113.3 🔴<sub>+25%</sub> | 21.18 🟡<sub>+3.7%</sub> | 44.07 🔴<sub>+9.4%</sub> | 667.3 🟡<sub>+1.4%</sub> | 3.00 🔴<sub>+11%</sub> | 0.73 🔴<sub>+12%</sub> | **1167** 🟢<sub>−13%</sub> |
| `O3−` *(−O3 bez vektorizérů + klonování)* | 25.2 🟡<sub>+0.1%</sub> | 36.2 🟡<sub>+0.5%</sub> | 37.2 🟡<sub>+0.6%</sub> | 81.5 🟡<sub>+1.1%</sub> | 46.1 🟡<sub>+0.2%</sub> | 96.1 🔴<sub>+5.8%</sub> | 20.32 🟢<sub>−0.5%</sub> | 40.95 🟡<sub>+1.7%</sub> | 662.8 🟡<sub>+0.7%</sub> | 2.75 🟡<sub>+2.2%</sub> | 0.68 🟡<sub>+4.6%</sub> | 1480 🔴<sub>+10%</sub> |
| **`O2+`** *(pět průchodů — baseline)* | 25.2 | **36.0** | **37.0** | 80.6 | **46.0** | **90.8** | 20.42 | **40.28** | 658.0 | 2.69 | **0.65** | 1345 |

`-Os` zmenší flash nejvíc, ale rozbije affine/blend smyčky (`tint` +51 %, `transpose` +124 %);
`O3−` rychlost enginu sedí, přesto zůstává +134 KB, protože celofirmwarové inlinování `-O3`
přežije; sloupce Pythonu se téměř nemění, protože jádro interpretu je `-O3` v každém buildu.
(`bench_displayio.py` vyšel napříč úrovněmi plochý, tak je vynechaný.)
