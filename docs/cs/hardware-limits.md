# Hardwarové limity: hodiny, SPI a displej

Jak spolu souvisí takt jádra, takt periferií a SPI displeje na deskách RP2, jaké mají
limity a jak je měřit. Údaje vycházejí z měření na
PicoPadu (RP2040) a na PicoPadu s čipem vyměněným za RP2350 (Pico 2).

Rozpočet RAM a nasazení popisuje **[HARDWARE.md](../hardware.md)**. Rychlý a přenositelný
backend vysvětluje **[průvodce enginem](../engine.md#pod-kapotou)**.

Hledáš, co engine *ve hře* umí a neumí — RAM, snímková frekvence, funkce? Viz
**[Přicházíš z jiného enginu](/cs/concepts/coming-from/)** a **[Vejít se do paměti](memory.md)**. Tahle
stránka je ladění firmwarových hodin / SPI / displeje.

---

## 1. Řetězec hodin (co řídí co)

```text
        PLL_SYS ──> clk_sys ──> jádra CPU
                        └─────> clk_peri ──> SPI, UART, …  (CircuitPython: clk_peri = clk_sys, neděleno)
        takt flash XIP/QMI se také odvozuje z clk_sys (samostatná dělička)
        PLL_USB ──> 48 MHz USB  (nezávislé — USB-CDC REPL není overclockingem ovlivněn)
```

Dva důsledky, které řídí vše níže:

1. **`clk_peri` následuje `clk_sys`.** V CircuitPythonu odpovídá takt periferií systémovému taktu
   bez dalšího dělení. **Změna taktu jádra proto mění vstupní takt SPI**, a tím i
   takt displeje. Obě hodnoty musíš posuzovat společně.
2. **Výchozí `clk_sys` se liší podle čipu:** RP2040 = **125 MHz**, RP2350 = **150 MHz**. Konstanta
   vyladěná pro jeden čip dopadne na druhém jinak (viz §3).

---

## 2. Jak se odvozuje takt SPI displeje

Displej ST7789 používá čtyřvodičovou sběrnici SPI. Jeho takt pochází z periferie PL022 SPI,
která dělí `clk_peri` **sudým celým číslem** (`CPSDVSR × (1+SCR)`), a SDK vybírá
děličku tak, aby výsledný takt byl **nejvyšší dosažitelný, který nepřekročí požadavek**:

```text
actual_spi_hz = clk_peri / even_divider     # největší výsledek <= požadovaný baudrate
```

Požadovanou přenosovou rychlost nastavíš v `board.c` (`common_hal_fourwire_fourwire_construct(... baudrate ...)`).
Požadavek je **strop**, ne přesná hodnota: pokud přesná hodnota není sudým dělením
`clk_peri`, použije se nejbližší nižší hodnota.

Propočtené příklady (ve všech případech požadavek 62,5 MHz):

| clk_peri (= clk_sys) | sudé dělitele kolem 62,5 | vybráno | skutečné SPI |
|---|---|---|---|
| 125 MHz (RP2040 stock) | /2 = 62,5 | /2 | **62,5 MHz** (přesně) |
| 150 MHz (RP2350 stock) | /2 = 75 (> 62,5, zamítnuto), /4 = 37,5 | /4 | **37,5 MHz** |
| 200 MHz | /2 = 100 (zam.), /4 = 50 | /4 | **50 MHz** |
| 225 MHz | /2 = 112,5 (zam.), /4 = 56,25 | /4 | **56,25 MHz** |
| 250 MHz | /2 = 125 (zam.), /4 = 62,5 | /4 | **62,5 MHz** (přesně) |

**Klíčová past:** stejný požadavek 62,5 MHz dá 62,5 na RP2040 (125/2), ale jen **37,5** na
výchozím 150MHz RP2350, protože 150/2 = 75 překročí požadavek a dělička přejde na 150/4. Pro vhodný
takt displeje na RP2350 zvol `clk_sys`, jehož sudé dělení odpovídá cílové hodnotě,
např. **250 MHz → /4 = přesně 62,5 MHz**, maximum v rámci specifikace (viz §3, §4).

Pro požadovaný takt SPI nastav `request = actual` nebo vyšší hodnotu menší než `2×actual`.
Nejpřehlednější je požadovat cílový takt a ověřit zvolenou děličku.

---

## 3. Limit z datasheetu a jeho překračování

**Datasheet ST7789** udává minimální periodu sériového zápisu **tSCYCW = 16 ns**, tedy nejvýše **62,5 MHz**
(čtení je mnohem pomalejší, ~6,6 MHz, ale displej je zde jen pro zápis). Takže **62,5 MHz je
strop v rámci specifikace** pro posílání pixelů.

V praxi panel na dané desce často běží **nad** specifikací:

- Na tomto PicoPadu **75 MHz** SPI (RP2350 na 150 MHz, /2) vytvořilo **čistý obraz**, ~20 % nad
  specifikací, na tomto kusu funguje při pokojové teplotě.
- „Funguje tady" **není** „garantováno všude": takt nad specifikací může selhat na jiném panelu,
  při teplotních extrémech, jiném napětí nebo na delší či horší kabeláži. Ber to jako
  experiment na konkrétním kusu, ne jako nasaditelný výchozí stav.

Protože PL022 dělí jen sudými celými čísly, z daného `clk_sys` máš obvykle jen
dvě volby ohraničující specifikaci, např. ze 150 MHz: **75** (nad) nebo **37,5** (hluboko pod),
nic na 62,5. Vhodnou hodnotu v rámci specifikace lze trefit volbou `clk_sys` (250 → 62,5).

Takt SPI je jediná přenosová hodnota, kterou určuje dělička. Druhou nezávislou možností pro
platformu **omezenou přenosem** je **`Display(rgb444=True)`** (12bitové balené pixely, ~25 % méně
dat SPI na snímek, řízeno `picogame.RGB444_SUPPORTED`). Balení pixelů po pásech stojí část času CPU,
ale po sběrnici se přenese méně bajtů. Vyplatí se tedy jen tam, kde je úzkým hrdlem panel. Ve firmwaru
na PicoPadu je schopnost ZAKOMPILOVANÁ (`pg.RGB444_SUPPORTED` je True) — jen se za běhu ve výchozím stavu nezapíná, protože na tomto CPU-vyváženém panelu náklad na per-strip pack sní úsporu SPI. Viz [Build firmwaru](firmware.md).

---

## 4. Zvyšování taktu jádra

> **Naměřený závěr pro tuto desku: vyšší takt výkon zhoršil, proto ho nepoužívej.** Teoreticky
> by 250 MHz zrychlilo práci CPU a zároveň nastavilo SPI na přesných 62,5 MHz, ale ve všech měřených
> režimech byl výsledek přibližně **2× pomalejší** než s výchozími 150 MHz:
>
> | režim | výchozích 150 MHz | zvýšených 225 MHz |
> |---|---|---|
> | HEAVY (vázáno na CPU/blit) | ~31 fps | **~15 fps** |
> | STRESS (celosnímkové, vázáno na SPI) | ~44 fps | **~16 fps** |
> | výchozí (dirty-rect) | ~95 fps | **~42 fps** |
>
> **Příčina:** zvýšení `clk_sys` bez přeladění časování flash QMI/XIP způsobí, že se
> kód vykonává z flash s více čekacími stavy. Jádro tiká rychleji, ale propustnost instrukcí
> klesá a převáží zisk z vyššího taktu. CircuitPythonové `set_sys_clock_khz`
> (ať přes `microcontroller.cpu.frequency` nebo volání `board_init`) flash **nepřeladí**;
> implementace, které vyšší takt používají, například PicoDVI na 252 MHz, spouštějí kritickou smyčku z
> RAM, ne z XIP. Přeladění časování QMI pro nový takt je specifické pro daný flash čip,
> a navíc 250 MHz nezávisle rozházelo displej (§4b), takže praktická odpověď
> proto **ponech výchozí takt a rychlost displeje nastav děličkou SPI (§2/§3).**

Následující poznámky platí pro experimentální build s vyšším taktem a pomáhají omezit chyby displeje.

### Dvě pravidla pro experimentální build

**(a) Nastav takt při startu v `board.c board_init()`, před vytvořením SPI displeje,
ne za běhu.** Změna `microcontroller.cpu.frequency` za běhu naruší obraz na aktivním ST7789:
skok napětí VREG (CircuitPython zvyšuje napětí jádra pro >133 MHz) a krátký výpadek při rekonfiguraci
PLL naruší `clk_peri`, zatímco je panel uprostřed transakce, a rozhází ho. Naměřeno: změna za běhu
na *jakoukoli* hodnotu ≥133 MHz rozházela displej; ≤120 MHz (bez změny VREG) bylo v pořádku.
Provedení v `board_init` před existencí displeje glitch zcela odstraní:

```c
#include "hardware/clocks.h"
#include "hardware/vreg.h"
#include "hardware/timer.h"

void board_init(void) {
    vreg_set_voltage(VREG_VOLTAGE_1_20);   // vyžadováno pro >133 MHz
    busy_wait_us(10000);                    // nech napětí ustálit
    set_sys_clock_khz(225000, true);        // teprve potom zvyš takt
    // ... teprve teď konstruuj display SPI (inicializuje se na finálním clk_peri) ...
}
```

Napěťové úrovně VREG, které CircuitPython používá: ≤133 MHz → 1,10 V, >133 MHz → 1,20 V, ≥300 MHz → 1,20 V,
≥400 MHz → 1,30 V.

**(b) Nejprve narazilo časování příkazů displeje, ne čip.** RP2350 nabootoval a běžel na
250 MHz (jednoduchá hra jako Train byla čistá), ale náročné renderování ukázalo **artefakty kolem
dirty regionů**: na 250 MHz vydává CPU příkazy nastavení okna pro jednotlivé obdélníky (CASET / RASET /
RAMWR plus přepínání GPIO DC/CS) rychleji, než je ST7789 spolehlivě zachytí, takže občas okno dopadne
špatně a strip se zapíše mírně mimo. Jde o důsledek **taktu jádra**, ne
datové rychlosti SPI; objevil se na 250 MHz/62,5 MHz SPI, zatímco 150 MHz/75 MHz SPI bylo čisté (pomalejší
SPI, rychlejší jádro → stejně se to rozbilo). Projevuje se všude, kde je mnoho nastavení okna na snímek
(spousta dirty rectů, celosnímkové překreslení), a sotva u lehkých dirty-rect her.

Postupné měření na této desce našlo hranici časování displeje: při **150, 200 a 225 MHz** byl obraz
bez artefaktů, při **250 MHz** už ne. I při 200 a 225 MHz však deska běžela celkově přibližně
dvakrát pomaleji kvůli flash/XIP, takže se dodává s **výchozími 150 MHz**. Pro rychlost displeje
je zde rozhodující dělička SPI, ne vyšší takt jádra.

### Kompromis

Vyšší takt CPU kvůli sudé děličce často snižuje takt SPI v rámci specifikace:

| Build | jádro | SPI displeje | výsledek |
|---|---|---|---|
| **výchozí + „spi75" (dodávaný)** | 150 MHz | 75 MHz (nad specifikací, zde čisté) | **celkově nejrychlejší na této desce** |
| boot-225 (zamítnuto) | 225 MHz | 56,25 MHz (v rámci specifikace) | ~2× pomalejší (flash/XIP, viz rámeček v §4) |

Nižší takt SPI *i* čekací stavy flash výkon zhoršovaly, takže
doporučená konfigurace RP2350 PicoPadu je **výchozích 150 MHz s požadavkem 75 MHz SPI** (`/2`).

Vazba taktu a děličky SPI popsaná výše je obecný kompromis; z jedné sudé děličky nelze
maximalizovat obojí. Na měřené desce vyšší takt nikdy nevyhrál, protože
čekací stavy XIP (§4) dominovaly u každé zátěže. Na tomto hardwaru ponech výchozí
frekvenci a vyber děličku SPI; zvýšení taktu pro hru omezenou CPU ber jako hypotézu
k přeměření na jiných deskách, ne jako radu.

---

## 5. Jak to testovat

Spusť benchmark, jehož přepínače oddělují jednotlivé režimy:

| Přepínač | Izoluje | Čtení |
|---|---|---|
| `FAST = True/False` | rychlá DMA vs. přenositelný backend | rozdíl se projeví jen u přenosu více stripů |
| `STRESS = True` | vynutí celosnímkové překreslení každý snímek | strop **vázaný na SPI** (∝ takt SPI) |
| `HEAVY = True` | několik velkých škálovaných a otočených spritů | případ **vázaný na CPU/blit** (∝ takt jádra) |
| `OVERCLOCK = …` | takt jádra za běhu | **na PicoPadu ponech None**: změna za běhu naruší displej; vyšší takt nastavuj při startu ve firmwaru |

Čtení výsledků:

- **Výchozí režim s malými sprity je špatná metrika:** 25 rozesetých spritů překročí limit
  šesti dirty regionů. Dvojice s nejmenším nárůstem plochy se pak slučují, dokud nezůstane šest
  regionů, a jejich celková plocha se během pohybu mění. FPS proto závisí na rozmístění spritů.
  Pro opakovatelnou zátěž celé obrazovky použij `STRESS`, pro zátěž CPU režim `HEAVY`.
- **`STRESS` má zvýraznit případ omezený přenosem.** Pokud se jeho FPS mění přibližně úměrně
  taktu SPI, je v daném buildu úzkým hrdlem přenos přes SPI.
- **`HEAVY` má zvýraznit případ omezený CPU a blitem.** Porovnej ho mezi buildy a ověř,
  zda změna taktu jádra na dané desce skutečně zvýšila propustnost instrukcí.

Příznaky taktu, který je pro displej příliš vysoký:

- **Artefakty kolem nebo na okrajích dirty regionů**, rozmazání či posunuté stripy při náročném
  renderování, zatímco lehká scéna (nebo jednoduchá hra) stále vypadá dobře. To je strop časování
  příkazů okna (§4b), ne pád.
- Takt příliš vysoký pro **čip nebo flash** selže výrazněji: deska buď nenabootuje, nebo skončí
  hard faultem.
- **Obnova přes BOOTSEL:** pokud firmware po změně taktu nenabootuje, podrž BOOTSEL a nainstaluj
  znovu ověřený soubor `.uf2`.

Při hledání limitu sestav firmware s postupně nižším taktem jádra (250 → 225 → 200 → …), každý nainstaluj,
spusť `STRESS` a `HEAVY` a ponech **nejvyšší takt bez artefaktů v dirty regionech**. Takt měň
jen v `board.c board_init`, ne za běhu, a znovu zkontroluj, kterou SPI děličku nový
`clk_peri` vybral (§2).
