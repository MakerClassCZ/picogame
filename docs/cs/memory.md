# Správa RAM a fragmentace haldy v CircuitPythonu

Nejdřív zjisti dostupnou paměť a cenu největších položek, potom změř svou hru. Aréna na
konci stránky pomáhá až tehdy, když opakované velké alokace skutečně tříští haldu.

:::note[Opravu jsi nasadil, ale nic se nezměnilo?]
Zastaralý `.mpy` ležící DŘÍV na sys.path (`['', '/', '.frozen', '/lib']`) **zastíní** upravený `.py` — typicky bundle `.mpy` v kořeni CIRCUITPY porazí `/lib/<jméno>.py`; ve STEJNÉM adresáři vyhrává `.py`. Po každé změně libu bundle smaž nebo přegeneruj (viz [Spuštění na hardwaru](hardware.md)).
:::

:::tip[Triáž při MemoryError — začni tady]
`MemoryError` uprostřed hry skoro vždy znamená **žádný dost velký souvislý blok**, ne „došla RAM". Projdi seznam a zastav se u první opravy, která zabere:

1. **Změř největší _souvislý_ blok, ne celkové volno** — `micropython.mem_info(1)` nebo [pomocná funkce `largest_block()` níže](#měř-nehádej). To je číslo, do kterého se velká alokace musí vejít.
2. **Přesuň HUD / text / panely z uchovávaných bufferů** do `StripDraw` (skládej `Canvas.text` do pohledu stripu) — viz [Kreslicí cesty](/cs/concepts/drawing-paths/).
3. **Velké buffery alokuj jednou při startu; ty churnující dej do arény** — [předalokovaná aréna](#aréna-pro-opakovaně-používané-velké-buffery).
4. **Fondy pro spawny každého snímku** místo churnu create/destroy — [`picogame_pool`](/cs/helpers/building-scenes/).
5. **Velké prostředky zmraz nebo čti postupně** místo kopírování na haldu — [zmrazená data vs soubor vs postupné čtení](#umístění-grafiky-zmrazená-data-soubor-v-ram-a-postupné-čtení).
6. **`gc.collect()` na hranicích scény / úrovně** pro sloučení uvolněných bloků.
7. **Po opravě to stále padá?** Zastaralý `.mpy` ležící dřív na sys.path možná **zastiňuje tvůj `.py`** — viz poznámka výše.
:::

## Rozpočet a jeho hlavní položky

Halda Pythonu bývá na malé desce omezujícím zdrojem. Ve hře s výraznou grafikou zabírají
velkou část bitmapy a uchovávané kreslicí plochy. Obvyklé náklady jsou:

| Položka | Cena | Poznámka |
|---|---|---|
| Uchovávaná plocha `Canvas` | `w * h * 2` | panel 320×80 = 51 200 B |
| PAL8 bitmapa (sprity, pozadí) | `w * h` (+ paleta) | RGB565 bitmapa stojí dvojnásobek |
| Strip buffery (ze `setup()`) | `2 × šířka × strip_h × 2` | např. 320×8 ≈ 10 KB za pár |
| Fond spritů | přibližná velikost objektu × kapacita | bitmapy se sdílejí; fond omezuje nejvyšší počet |
| Bitmapa textového popisku | plocha textu × 1–2 B/px | `Canvas.text` v `StripDraw` se obejde bez uchovávané plochy textu |

Celková čísla se liší podle desky a buildu firmwaru, proto změř vlastní build.
Největší plochy naplánuj jako první: RGB565 plocha 320×240 má 150 KB, což přesahuje největší
souvislý blok naměřený v současném buildu pro RP2040 PicoPad.

## Umístění grafiky: zmrazená data, soubor v RAM a postupné čtení

Pixely bitmapy musí být uložené ve flash nebo v RAM. Disk CIRCUITPY je souborový systém ve
flash, ale není přímo mapovaný do adresního prostoru procesoru. Import velkého `.mpy` nebo
načtení souboru proto může zkopírovat data na haldu. Zmrazená data lze číst přímo z flash,
ale jejich objekty a další stav stále používají část RAM.

| Přístup | Cena heapu | Výměna artu bez reflashe? | Nejlepší pro |
|---|---|---|---|
| **Zmrazená data** (`FROZEN_MPY_DIRS`) | pixelová data mohou zůstat ve flash | ne | stálá grafika ve vlastním firmwaru |
| **Soubor → RAM** (`readinto` jednou) | celý atlas `w*h*frames` | ano | atlasy, které se vejdou, a časté změny grafiky |
| **Postupné čtení** (`picogame_stream.StreamSheet`) | buffer `w*h` bajtů + objekty a paleta | ano | několik velkých atlasů PAL8, které se celé nevejdou |

- **Zmrazená data:** modul s konstantou `bytes` (`DATA = b'...'`) je součástí firmwaru a
  `pg.Bitmap(DATA, ...)` může číst pixely na místě. Změna grafiky vyžaduje nový firmware.
- **Soubor → RAM:** nahraj `.bin` na CIRCUITPY a při načtení jej přečti pomocí `f.readinto(blob)`
  do jednoho připraveného `bytearray`. Tím nevznikne druhý velký objekt `bytes` jako u `read()`.
- **Postupné čtení:** `StreamSheet` drží v RAM buffer jednoho snímku; `use(i)` vyhledá jeho
  pozici a přečte jej přes `readinto`. Čtení při každé změně se hodí pro několik velkých
  spritů, ne pro stovky malých. `.bin` musí mít snímky uložené za sebou
  (`tools/pack_sheet.py`).

Způsob vyber pro každý prostředek zvlášť. Zmrazená data se hodí pro stálý firmware,
postupné čtení pro několik velkých atlasů PAL8 a malé často používané atlasy bývá
jednodušší ponechat v RAM.

## Měř, nehádej

- `gc.mem_free()` — celkový volný heap. Měř po `gc.collect()`, ve fixních bodech (po
  importech, po `setup()`, v herní smyčce), aby šla měření porovnat.
- **Největší souvislý blok** — to, co velká alokace skutečně potřebuje; vestavěná funkce
  není, najdi ho binárním hledáním:

```python
import gc
def largest_block():
    gc.collect()
    lo, hi = 0, gc.mem_free()
    while hi - lo > 256:
        m = (lo + hi) // 2
        try:
            b = bytearray(m); del b; lo = m
        except MemoryError:
            hi = m
        gc.collect()
    return lo
```

- `import micropython; micropython.mem_info(1)` vypíše celou mapu heapu (co žije a kde) na
  firmwaru s povolenou diagnostikou — nástroj na otázku, *proč* je heap fragmentovaný.

## Běžné optimalizace (v pořadí, v jakém je zkoušet)

1. **Neuchovávej pixelovou plochu, pokud ji nepotřebuješ.** Text a obsah HUDu nebo panelů lze
   skládat přímo do stripu (`Canvas.text` v pohledu `StripDraw`; stejně pracují
   některé prvky `picogame_ui`). Podrobnosti najdeš v [Kreslicích cestách](/cs/concepts/drawing-paths/).
2. **Fullscreen pozadí ukládej jako tilemapu, ne jako bitmapu.** 320×240 PAL8 pozadí je ~75 KB
   (RGB565 dvojnásobek) — na RP2040 často moc. Rozřež obrázek na tily 8×8, nech si jen *unikátní*
   tily (malý tileset) plus mřížku indexů a vykresli to vrstvou [`Tilemap`](engine.md). Pozadí se
   hodně opakují, takže tileset + mřížka indexů je zlomek plné bitmapy. `png2picogame.py --dedup`
   sloučí shodné (i otočené/zrcadlené) tily za tebe; přesně tak port MoonMineru na Fruit Jamu vejde
   fullscreen scény na RP2040.
3. **Velké a dlouho žijící buffery alokuj na začátku** a znovu je používej. Nevytvářej je
   opakovaně pro každou úroveň nebo obrazovku.
4. **Buffery na vyžádání připrav na nejširší očekávaný obsah.** Textový popisek vytvořený
   krátký a později nastavený na delší řetězec si *uprostřed běhu* alokuje větší buffer; na
   fragmentovaném heapu je to `MemoryError`. (HUD labely vytvářej na nejširší řetězec;
   `SceneLabel.reserve(chars)` předdimenzuje banner zobrazený až při game-over.)
5. **Fondy objektů** použij pro mnoho malých objektů se stejnou životností, například sprity
   nebo požadavky. [`picogame_pool`](/cs/helpers/building-scenes/) je znovu používá místo opakované alokace a uvolnění.
6. **`recv_into` / `readinto`** (a další `*_into` API) čtou do existujícího bufferu místo
   alokace nového bytes objektu při každém volání.
7. **`gc.collect()` na přirozených hranicích** (konec požadavku nebo úrovně) sloučí sousední volné
   bloky; nutné, ale nestačí (živé objekty přesunout neumí). `gc.threshold(n)` spouští GC
   dřív a drží heap uklizenější.
8. **Velké importy nedělej během časově citlivé části hry.** Import může alokovat objekty a
   spustit GC. Známé závislosti načti při startu nebo na řízené hranici scény a potom změř
   největší volný blok. GC objekty nepřesouvá.

## Fragmentace: celkové volno není největší blok

MicroPython/CircuitPython používají **nepřesouvající** mark-and-sweep GC: uvolní
nedosažitelné objekty, ale **živé nikdy nepřesouvá** (objekty se odkazují syrovými
pointery a C stack se skenuje konzervativně, takže bezpečné přemístění není možné).
Sousední volné bloky se při `gc.collect()` slučují, ale volné místo rozdělené **živými**
objekty rozdělené zůstane.

Důsledek: poté, co program naalokoval a uvolnil mnoho různě velkých bufferů, heap se
fragmentuje. Můžeš mít **spoustu celkové volné RAM, ale žádný souvislý blok** dost velký
pro další velkou alokaci:

```text
gc.mem_free() -> 90000      # 90 KB volných...
bytearray(51200)            # ...ale tohle vyhodí MemoryError (žádný souvislý 51KB úsek)
```

`gc.mem_free()` hlásí celkové volno; velká alokace potřebuje **největší souvislý volný
blok**, který může být mnohem menší a s fragmentací session se zmenšuje.

### Kdy se problém projeví

Každý vzor, který **opakovaně alokuje a uvolňuje velký buffer** během jednoho běhu:

- **Síť / web:** čtení HTTP odpovědi, JSON/MQTT payloadu, TLS záznamu, stažení obrázku,
  kdy si každý request bere (a uvolňuje) čerstvý kilobajtový buffer.
- **Soubory / streamy:** čtení souboru po kusech, dekomprese, parsování.
- **Audio:** sample buffery per klip.
- **Grafika:** (skoro)celoobrazovkové kreslicí plochy (např. `displayio`/`picogame`
  Canvas) vytvářené per obrazovka/level.

Jeden velký buffer alokovaný poblíž startu tříští haldu méně než buffer opakovaně vytvářený
a zahazovaný. I tak se musí vejít do souvislého bloku dostupného v okamžiku alokace.

## Aréna pro opakovaně používané velké buffery

Na začátku vyhraď jeden velký buffer a potom
z něj rozdávej řezy pro velké přechodné buffery. Ty už za běhu nikdy nealokují/neuvolňují,
takže nemají co fragmentovat. Stejné bajty arény znovu použij pro práci, která se nepřekrývá
v čase.

[`lib/picogame_arena.py`](/cs/helpers/data/) je drobná obecná implementace (žije v picogame libu, ale třída
`Arena` není herně specifická):

```python
import picogame_arena
AR = picogame_arena.Arena(2048)        # kapacita je v RGB565 pixelech: zde 4096 bajtů

# --- síťový příklad: znovupoužij JEDEN buffer odpovědi místo churnu ---
buf = AR.alloc(4096)                   # memoryview řez, žádná alokace per request
while True:
    AR.reset()                         # stejné bajty pro každý request
    n = sock.recv_into(buf)            # čti rovnou do řezu arény
    process(buf[:n])                   # parsuj bez alokace dalšího velkého bufferu
```

```python
# --- grafický příklad (picogame): podlož velké Canvasy pamětí arény ---
AR = picogame_arena.Arena(320 * 80)    # pixely (x2 bajty); největší plocha, kterou potřebuješ
AR.reset(); road = AR.canvas(320, 80)          # velká plocha jedné obrazovky
# později jiná obrazovka (nežijí současně) použije stejnou arénu:
AR.reset(); shapes = AR.canvas(320, 44); btn = AR.canvas(160, 48)
```

API: `Arena(pixels)` (alokuje `pixels*2` bajtů), `alloc(nbytes) -> memoryview`,
`canvas(w, h, transparent=None) -> Canvas` (potřebuje firmware argument
`Canvas(..., buffer=)`), `reset()` (přetočí kurzor, volej na začátku každého
nepřekrývajícího se použití), `free()`.

Aréna vytvoří velký podkladový buffer jednou a jeho bajty znovu používá. Pythonové objekty a
řezy `memoryview` mají stále malou režii na haldě, ale velké pixelové nebo vstupní buffery už
nevyžadují opakované souvislé alokace.

## Proč nelze haldu jednoduše zkompaktovat?

Kompaktující GC nelze doplnit jako samostatnou funkci: objekty MicroPythonu se
navzájem odkazují **přímými ukazateli** (v Pythonu, C modulech i bytecode) a GC skenuje
C stack **konzervativně**, takže nemůže bezpečně objekt přesunout a přepsat každý odkaz na
něj. To by vyžadovalo jiný objektový model v jádru virtuálního stroje. Praktickou možností
je proto znovu používat velké buffery, například pomocí arény.

Viz také argument `Canvas(..., buffer=)`, který podloží kreslicí plochu [pamětí arény](/cs/helpers/data/), a
pomocný modul [`picogame_pool`](/cs/helpers/building-scenes/) pro fondy objektů. Spotřebu RAM měř na cílové desce;
desktopový simulátor její haldu nenapodobuje.
