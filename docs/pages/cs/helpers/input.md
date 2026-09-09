---
title: "Vstup a ovládání"
description: "Čti D-pad a tlačítka přes picogame_input a přidej ovládání USB gamepadem nebo klávesnicí na deskách s USB hostem — bez jediné změny kódu hry."
---

`picogame_input.Buttons` je jediný objekt vstupu, který používá každá hra. Čte fyzická tlačítka desky
do **bitové masky** s detekcí hran, takže kód hry nikdy neřeší zapojení znovu:

```python
import picogame_input as pi
btn = pi.Buttons()

# každý snímek:
btn.poll()
if btn.is_pressed(pi.LEFT):   px -= 2
if btn.just_pressed(pi.A):    jump()
if btn.repeat(pi.DOWN):       menu_move(+1)   # PICO-8 btnp auto-repeat, dobré pro menu
```

## Jeden virtuální ovladač, namapovaný na reálný hardware

Engine dává každé hře **stejný virtuální ovladač** — pevnou sadu logických tlačítek — a ty na něj
**namapuješ reálný hardware desky**. Hry vždy programují proti logickým názvům (`pi.A`, `pi.LEFT`),
nikdy proti pinům, takže *stejné `code.py`* běží na PicoPadu, breadboard Picu, klávesové matici i USB
gamepadu; mění se jen mapování.

Logická sada:

- **Základ (na tenhle se každá hra může spolehnout):** čtyřsměrný D-pad — `UP` `DOWN` `LEFT` `RIGHT` — plus `A` a `B`.
- **Volitelné navíc (namapuj, když je hardware má):** `X` `Y`, ramena `L1` `L2` `R1` `R2` a `START` `SELECT`.

Deska mapuje podmnožinu, kterou fyzicky má; chybějící tlačítka prostě nikdy nevystřelí. Dostupnost ověříš
přes `btn.has(pi.L1)`, aby hra mohla skrýt ovládání, které deska nemá. Mapování fyzické→logické je v
`settings.toml` (níže) — jeden soubor, bez reflashe — řešené podle zdroje: `PICOGAME_BUTTONS` pro GPIO,
`PICOGAME_MATRIX_*` pro klávesovou matici, `PICOGAME_USBPAD` / `PICOGAME_USBKBD` pro USB.

Metody `Buttons`: `poll() -> mask`, `is_pressed(mask)`, `just_pressed(mask)`, `just_released(mask)`,
`has(mask)`, `repeat(button, delay=15, interval=4)`, `clear()`. Pro okna vstupní tolerance (coyote
time, jump buffering) použij `pi.Timer(frames)` s `.feed(cond)` / `.is_active` / `.consume()`.

## Zdroje vstupu se ORují dohromady

```python
Buttons(profile=None, pull=None, prefer_keypad=True, debounce_s=0.02, matrix=None, usb=None, sources=None)
```

Objekt `Buttons` umí číst z **několika zdrojů najednou** a ORuje je do jedné masky, takže je hra čte
identicky:

- **Tlačítka na GPIO desky** — výchozí; mapování pinů je *profil* z `settings.toml`
  (`PICOGAME_BUTTONS`) nebo výchozí hodnota desky.
- **Skenovaná klávesová matice** (`matrix=`, nebo klíče `PICOGAME_MATRIX_*`) — pro desky s klávesnicí.
- **USB HID gamepad / klávesnice** (`usb=`, automaticky připojené na buildech s USB hostem) — viz níže.

Protože se vše ORuje, **nevětvíš podle zdroje**: stejné `btn.just_pressed(pi.A)` vystřelí, ať A přišlo
z GPIO tlačítka, buňky matice, USB padu nebo klávesy klávesnice.

## Namapuj hardware v `settings.toml`

Každý zdroj má vlastní mapovací klíč. Uprav `settings.toml` na disku `CIRCUITPY` a resetuj — bez nového
buildu firmwaru. [Reference settings.toml](/cs/custom-board/) vypisuje každý klíč a jeho přesný formát;
běžné případy:

**Přímá GPIO tlačítka** — tokeny `NÁZEV=GPpin`. Namapuj jen to, co máš:

```toml
# Pico se zapojeným D-padem + A/B, plus volitelné X/Y
PICOGAME_BUTTONS = "UP=GP2 DOWN=GP3 LEFT=GP4 RIGHT=GP5 A=GP6 B=GP7 X=GP8 Y=GP9"
PICOGAME_PULL = "up"    # tlačítka na GND, stisk čte low (výchozí)
```

**Skenovaná klávesová matice** — zadej piny řádků/sloupců, pak namapuj buňky matice na logická tlačítka
přes `NÁZEV=řádek,sloupec`. picogame mřížku skenuje a odzákmituje přes modul `keypad`:

```toml
PICOGAME_MATRIX_ROWS = "GP0 GP1 GP2 GP3"
PICOGAME_MATRIX_COLS = "GP4 GP5 GP6 GP7"
PICOGAME_MATRIX_MAP  = "UP=0,1 DOWN=2,1 LEFT=1,0 RIGHT=1,2 A=3,3 B=3,2 START=0,0 SELECT=0,3"
# PICOGAME_MATRIX_ANODES = "cols"   # přepni na "rows", je-li orientace diod opačná
```

**USB gamepad / klávesnice** — `PICOGAME_USBPAD` / `PICOGAME_USBKBD` (viz USB sekce níže).

Částečná mapa se sloučí přes výchozí hodnoty zdroje, takže pojmenuješ jen tlačítka, která měníš.
Nenamapovaná logická tlačítka zůstanou neaktivní (`btn.has(...)` je hlásí jako nepřítomná).

## USB gamepad (desky s USB hostem, např. Fruit Jam)

Na CircuitPython buildu s USB hostem `Buttons()` **automaticky připojí** zapojený USB HID gamepad —
takže pad funguje **bez jakékoli změny hry**. Na deskách bez USB hosta (PicoPad, …) se driver vůbec
nezavede (žádná režie RAM).

- Výchozí rozložení = běžný DragonRise `081f:e401` (SNES-style pad).
- Přemapuj kterýkoli pad ze `settings.toml` (bez reflashe):
  `PICOGAME_USBPAD = "A=5:0x20 B=5:0x40 X=5:0x10 Y=5:0x80 START=6:0x20 SELECT=6:0x10"`
  (`NÁZEV=report-bajt:maska`; částečný seznam se sloučí přes výchozí hodnoty). Report byty nového padu
  zjistíš přes `tools/usbpad_probe.py`, nebo spusť interaktivní `tools/usbpad_calibrate.py` — vyzve tě
  ke stisku každého tlačítka a vypíše hotový řádek `PICOGAME_USBPAD` / `PICOGAME_USBPAD_ID`.
- Vypni ho přes `PICOGAME_USB = 0`; konkrétní zařízení připni přes `PICOGAME_USBPAD_ID = "vid:pid"`.

Driver je `picogame_usbpad.UsbPad`; přímo se ho skoro nedotkneš — `Buttons` ho připojí za tebe.

## USB klávesnice (desky s USB hostem)

Dvojče gamepadu — také automaticky připojené, také ORované. Funguje s drátovými klávesnicemi i s
bezdrátovými přes 2,4GHz dongle (ne Bluetooth — CircuitPython nemá BT host stack).

- Výchozí rozložení: **šipky + WASD** → D-pad, **Z / mezerník** → A, **X** → B, **C** → X, **V** → Y,
  **Q** → L1, **E** → R1, **Enter** → START, **Esc** → SELECT.
- Přemapuj ze `settings.toml`: `PICOGAME_USBKBD = "A=0x2C B=0x1B START=0x28"` (`NÁZEV=HID-keycode`,
  hex nebo dekadicky; sloučí se přes výchozí).
- Vypni jen klávesnici (pad ponech) přes `PICOGAME_KBD = 0`.
- Některé combo dongly mají boot-keyboard rozhraní, které mlčí, zatímco skutečné klávesy jdou po
  sourozeneckém rozhraní. Nasměruj driver na živý kanál:
  `PICOGAME_USBKBD_EP = "2:0x83"` (`rozhraní:IN-endpoint`). Hodnotu najdeš spuštěním
  `tools/usbkbd_probe.py` jako `code.py` — vypíše přesný řádek.

Driver je `picogame_usbkbd.UsbKbd`.

## I2C gamepad (jakákoli deska s I2C, včetně PicoPadu)

Třetí rodina padů: „hloupé" I2C tlačítkové desky — GPIO expandéry (TCA9555, PCF8574, MCP23017) a pady
na nich postavené, například Pimoroni QwSTPad. **Nepotřebuje USB hosta**, takže právě takhle se
externí ovladač připojí k PicoPadu nebo k holému Picu. Jeden driver plus deklarativní recept pokrývají
celou rodinu — stejná filozofie jako u USB padu, ne knihovna na každé zařízení.

Na rozdíl od USB je to **opt-in**: expandér nemá identifikační registr, takže by oťukávání adres mohlo
sáhnout na cizí zařízení na tvé sběrnici. Pad pojmenuj v `settings.toml` a `Buttons()` ho naORuje jako
každý jiný zdroj, bez zásahu do hry:

```toml
PICOGAME_I2CPAD = "qwstpad"                  # preset na výchozí adrese
# PICOGAME_I2CPAD = "qwstpad@0x23"           # preset na konkrétní adrese
# PICOGAME_I2CPAD = "qwstpad;qwstpad@0x23"   # více padů = lokální multiplayer
# PICOGAME_I2C = "GP4,GP5"                   # SDA,SCL — jen holé desky; konektor
#                                            #  STEMMA/Qw-ST nepotřebuje nic. Jeden token
#                                            #  místo toho pojmenuje sběrnici desky:
#                                            #  PICOGAME_I2C = "I2C0"
```

Neznámé zařízení je jeden řádek bez kódu — **recept** z tokenů oddělených mezerou:

```toml
PICOGAME_I2CPAD = "addr=0x20 read=:1 inv=1 UP=0 DOWN=1 LEFT=2 RIGHT=3 A=4 B=5"
```

- `addr=0x21` — I2C adresa.
- `read=00:2` — jeden poll: zapiš registrový bajt `00`, přečti 2 bajty. `read=:1` čte bez registru
  (styl PCF8574).
- `init=063FF9,0206C0` — syrové hex rámce zapsané jednou při připojení (registr + data, doslova).
- `inv=1` — tlačítka jsou v SYROVÉM čtení aktivní v nule; vynech, když zařízení hlásí stisk jako 1.
- `UP=1 A=14 …` — logické tlačítko = index bitu ve čtených bajtech, little-endian
  (`index_bajtu * 8 + bit_v_bajtu`). Názvy jsou ty, které používá `PICOGAME_BUTTONS`.

Poll je jedna krátká transakce, zhruba půl milisekundy při 100 kHz. Neúspěšný poll (uvolněný kabel)
podrží poslední stav a po osmi minutích ohlásí vše puštěné, takže odpojení nemůže nechat tlačítko
zaseknuté. Sběrnice se také protaktuje po soft reloadu, což je jinak přesně to, co nechá expandér
uprostřed transakce.

Driver je `picogame_i2cpad`; `Buttons` ho připojí za tebe. Přímo po něm sáhneš jen když si chceš pad
postavit ručně (`I2CPad`) nebo vyjmenovat pady pro multiplayer (`find_pads`, níže).

:::tip[Když se vstup nepřipojí, nastav `PICOGAME_DEBUG = 1`]
Vypíše na sériovou konzoli důvody `[picogame] ...` (chybí driver, zařízení nenalezeno, špatný
endpoint) místo tichého selhání. Po vyřešení odeber.
:::

## Lokální multiplayer

Ve výchozím stavu `Buttons` slučuje všechny zdroje (výše). Když chceš dát každému hráči vlastní
ovladač, vytvoř **jeden `Buttons` na hráče** a každý naváž na jeho zařízení přes `sources=`:

```python
import picogame_input as pi

pads = pi.find_pads()                  # všechny připojené USB gamepady, v pořadí sběrnice
p1 = pi.Buttons(sources=pads[0:1])     # hráč 1 = první pad
p2 = pi.Buttons(sources=pads[1:2])     # hráč 2 = druhý pad
# nebo míchej zařízení — pi.Buttons(usb=False) je hráč na palubních tlačítkách.
```

`picogame_i2cpad.find_pads()` je I2C dvojče — všechny pady daného presetu na sběrnici v pořadí
adres, každý si rozsvítí LED se svým číslem. Preset QwSTPad pokrývá čtyři adresy, takže čtyři hráči
fungují i na desce úplně bez USB hosta:

```python
import picogame_i2cpad as i2c
pads = i2c.find_pads("qwstpad")        # až čtyři, v pořadí adres
p1 = pi.Buttons(sources=pads[0:1])
```

Každý hráč je nezávislý: pollni a čti je zvlášť (`p1.just_pressed(pi.A)` / `p2.just_pressed(pi.A)`).
`pi.find_pads()` vrátí `[]` na desce bez USB hostu a `i2c.find_pads()` vrátí `[]`,
když na sběrnici žádný pad neodpoví. Dva stejné pady se vrátí v pořadí enumerace — když je
hráči chtějí prohodit, prostě si vymění ovladače (engine si žádnou identitu padu nedrží). Viz vzor pro
dva hráče výše.

Kompletní seznam vstupních klíčů a jejich formát je v [referenci `settings.toml`](/cs/custom-board/).
