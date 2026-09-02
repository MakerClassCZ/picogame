---
title: "Audio a hudba"
description: "Přehrávej vzorky WAV, syntetizuj efekty a MIDI pomocí synthio nebo použij hotovou sadu picogame_sfx."
---

:::caution[Kde zvuk hraje: playground, simulátor, zařízení]
- **Zařízení** — všechno (skutečné synthio + PWM/I2S).
- **Webový playground** — pípnutí z `tone()` a sada `picogame_sfx` hrají přes WebAudio (nejdřív stiskni klávesu, aby se zvuk odemkl); vlastní hlasy `picogame_synth` ne (prohlížeč nemá synthio backend).
- **Desktopový simulátor, živé okno** (`--backend pygame`, výchozí) — `picogame_synth` SFX i hudba **hrají** přes `pygame.mixer`: aproximace pro ladění sluchem, ne bit-exact. Běh bez okna (`--shot` / CI) a přehrávání samplů přes `picogame_audio` zůstávají tiché.
- Synth SFX si předposlechni offline pomocí `tools/synth_preview.py` a výsledné vyvážení ověř na zařízení.
:::

picogame nabízí čtyři zvukové vrstvy. `picogame_audioout` vybere výstupní zařízení desky (PWM nebo I2S DAC).
`picogame_audio` směšuje soubory `.wav` a generované PCM tóny. `picogame_synth` vytváří noty za běhu přes
synthio a nepotřebuje samostatný PCM buffer pro každý efekt. `picogame_sfx` nad syntetizérem přidává hotovou
sadu pojmenovaných herních zvuků. Nastavení audia na desce popisuje stránka
[Spuštění na hardwaru](/cs/hardware/), signatury najdeš v [referenci](/cs/reference/).

## picogame_audioout — jeden výstup pro každou desku

`picogame_audio` i `picogame_synth` získají výstupní zařízení z `picogame_audioout.make_output()`, takže hra
nepotřebuje **žádný kód specifický pro desku**. Vybírá automaticky:

- **I2S DAC** (např. TLV320 na Fruit Jamu), když deska vystavuje `board.I2S_BCLK`,
- jinak **PWM** výstup na pinu reproduktoru desky (nebo na pinu, který předáš).

Přímo ho většinou nevoláš — vytvoříš `Audio()` / `Synth()` a stane se to za tebe. `make_output(sample_rate=22050, pin=None)` je k dispozici, když chceš samotné zařízení; předání explicitního `pin` **vynutí PWM**.

**Hlasitost (desky s I2S DAC):** výchozí hodnoty driveru TLV320 jsou schválně velmi tiché, takže na Fruit Jamu může zvuk působit jako vypnutý, dokud je nezvedneš v `settings.toml` — `PICOGAME_AUDIO_OUT` (`headphone`/`speaker`/`both`), `PICOGAME_DAC_VOLUME`, `PICOGAME_HP_VOLUME`, `PICOGAME_SPK_VOLUME` (celé dB, drž `<= 0`). Viz [reference settings.toml](/cs/custom-board/).

:::caution[Fruit Jam: nainstaluj DAC driver, jinak je ticho]
I2S audio potřebuje `adafruit_tlv320` **a** `adafruit_bus_device` v `CIRCUITPY/lib` (z Adafruit bundlu /
`circup`) — s picogame se **nedodávají**. Když chybí, audio tiše spadne zpět na PWM pin, který DVI deska
nemá, takže zvuk není. Nastav `PICOGAME_DEBUG = 1` a důvod se vypíše
(`[picogame] audioout: I2S DAC driver missing …`) na sériovou konzoli.
:::

## picogame_audio

Vrstva nad audio stackem CircuitPythonu (`audiocore` + `audiomixer`) postavená na výstupu
`picogame_audioout`. Použij ji pro soubory `.wav` nebo jednoduché generované tóny. Mixér má několik hlasů,
takže zvukové efekty mohou hrát současně s hudbou. Každý vzorek musí odpovídat formátu mixéru; výchozí
nastavení je 22 050 Hz, mono, 16 bitů se znaménkem.

### `Audio(pin=None, voices=4, sample_rate=22050, channels=1, bits=16, signed=True)`

Vytvoří zvukový výstup a okamžitě spustí mixér. `pin=None` nechá `picogame_audioout` vybrat zařízení
(I2S DAC nebo PWM pin reproduktoru desky); explicitní `pin` vynutí PWM na tom pinu. `voices` určuje počet
souběžných kanálů. Hlas 0 je vyhrazený pro hudbu a hlasy 1 až N−1 se pro efekty střídají dokola. Ostatní
argumenty určují formát všech přehrávaných vzorků.

- `load(path)` - otevře `.wav` jako znovu použitelný `WaveFile`. Objekt vytvoř jednou a drž
  jej po dobu používání; udržuje totiž soubor otevřený.
- `play(sample, *, voice=None, loop=False, volume=1.0)` - přehraje vzorek. `voice` lze předat
  pouze jako pojmenovaný argument; `None` vybere další hlas pro efekty. `volume` nastaví jeho
  hlasitost v rozsahu 0,0–1,0. Metoda vrátí index použitého hlasu.
- `sfx(sample, volume=1.0)` - přehraje efekt jednou na dalším hlasu a vrátí jeho index.
- `music(sample, loop=True, volume=1.0)` - přehraje na vyhrazeném hudebním hlasu (hlas 0), ve výchozím stavu ve smyčce.
- `stop(voice=None)` - zastaví jeden hlas, nebo všechny hlasy, pokud je `voice` `None`.
- `stop_music()` - zastaví jen hudební hlas.
- `is_playing` (vlastnost) - `True`, pokud zrovna hraje nějaký hlas.
- `deinit()` - uvolní zvukový výstup. Výstupní zařízení může používat jen jedna instance,
  proto tuto metodu zavolej před vytvořením dalšího `Audio()` (nebo `Synth()` sdílejícího pin).

### `tone(frequency=440, ms=120, sample_rate=22050, volume=0.6)`

Sestaví v RAM krátký `RawSample` s pravoúhlou vlnou. Hodí se pro prototypování a jednoduchá
pípnutí bez souboru `.wav`. Předej ho rovnou do `sfx()` nebo `play()`.

```python
import picogame_audio
import picogame_input

audio = picogame_audio.Audio()        # PWM audio, 4 voices
pew = picogame_audio.tone(880, 90)    # vysoké pípnutí, vytvořené jen jednou
boom = picogame_audio.tone(140, 200)  # low thud

btns = picogame_input.Buttons()
while True:
    btns.poll()
    if btns.just_pressed(btns.A):
        audio.sfx(pew)                # overlaps on a free voice
    if btns.just_pressed(btns.B):
        audio.sfx(boom, volume=0.8)
```

:::note[Pozor]
- Každý vzorek musí odpovídat formátu mixéru. Soubory `.wav` se 44 100 Hz nebo ve stereu
  nejdřív převeď na 22 050 Hz, mono a 16 bitů se znaménkem.
- Výsledky `load()` drž po dobu používání. Když garbage collector uvolní `WaveFile`, uzavře
  se i jeho soubor. Klipy načti jednou při startu, ne v každém snímku.
- `tone()` vytvoří `RawSample` v RAM o velikosti přibližně
  `sample_rate * ms / 1000 * 2` bajtů. Mnoho dlouhých tónů může vyčerpat haldu. Drž je krátké,
  sniž `sample_rate` mixéru i tónu, nebo použij `picogame_synth`, který nepotřebuje samostatný
  PCM buffer pro každý efekt.
- Pro efekty je dostupných `voices-1` hlasů. Při rychlém opakování nový efekt přeruší hlas,
  který na něj připadne při střídání.
:::

## picogame_synth

`picogame_synth` obaluje oscilátory synthio, ADSR obálky, LFO pro změnu výšky a dolní propust.
Nemusí uchovávat PCM buffer pro každý efekt, ale stále alokuje výstupní audio buffer, mixer,
průběhy a objekty not. Použij ho pro větší sadu SFX nebo MIDI hudbu, pokud by WAV samply zabraly
příliš mnoho RAM nebo flash.

Modul lze importovat i ve firmwaru bez zvuku. Když inicializace selže, jeho metody nic
nepřehrají a nevyhodí výjimku. `AVAILABLE` nebo `synth.available` kontroluj jen tehdy, když
podle dostupnosti zvuku měníš uživatelské rozhraní. Živé okno desktopového simulátoru přehrává
tyto `picogame_synth` hlasy přes `pygame.mixer` (aproximace pro ladění sluchem); běh bez okna zůstává
tichý. Tak či tak stejná část hry proběhne beze změny.

Vestavěné konstanty průběhů (jednocyklová, signed 16-bit pole, která sdílíš mezi notami): `SINE`, `SAW`, `TRIANGLE`, `SQUARE`, `NOISE`. Každá tabulka se postaví při prvním čtení (512 B, pár ms), takže na průběhy, které používáš, sáhni už při stavbě not na startu, ne z herní smyčky. Funkce `sine()`, `saw()`, `triangle()`, `square()`, `noise()` postaví čerstvé kopie, pokud je potřebuješ. Na svižný arkádový blikanec sáhni po krátké notě `SQUARE` (`SINE` a `TRIANGLE` znějí měkčeji a oblejší).

### `note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08, amplitude=0.6, bend=None, cutoff=None)`

Sestaví znovupoužitelnou notu/SFX/nástroj - základní stavební kámen. `midi` je číslo MIDI noty (60 = komorní C, 72 = C5). `waveform` je jedna z konstant výše. `attack`/`decay`/`sustain`/`release` tvarují ADSR obálku v sekundách (krátký decay se `sustain=0.0` dá perkusivní blikanec). `amplitude` je hlasitost (0.0-1.0). `bend` bere `pitch_bend` LFO pro pitch sweep (rychlé zavlnění; viz `pitch_bend`); `cutoff` přidá low-pass filtr na daném počtu Hz, aby zaoblil drsné tóny. Každou notu postav jednou a přehrávej znovu.

### `pitch_bend(semitones, ms, waveform=None, once=True)`

Vrátí `synthio.LFO` pro `bend` noty. S `once=True` je to **jednorázové sine zavlnění**: během `ms` výška vykývne k `semitones` a zpět - *zavlnění/swoop*, ne čistý monotónní glide. Drž `ms` krátké (zhruba `attack+decay` noty), ať je slyšet hlavně náběh (kladné = zap nahoru) nebo pokles (záporné = drop); dlouhé `ms` nechá vyznít i návrat a zní rozkolísaně.

### `Synth(pin=None, sample_rate=22050, buffer_size=2048, music_level=0.4, sfx_level=0.7)`

Nastaví výstup (přes `picogame_audioout` — I2S DAC nebo PWM, stejně jako `Audio`) a 2hlasý mixer: hlas 0 pro hudbu (`MidiTrack`), hlas 1 pro živý synth používaný pro SFX. `pin=None` vybere zařízení automaticky; explicitní `pin` vynutí PWM. `music_level`/`sfx_level` jsou počáteční úrovně mixu pro tyto dva hlasy.

- `sfx(n)` - přehraje notu `n` jako jednorázový efekt. Nejdřív znovu spustí LFO té noty (aby opakovaný zvuk zněl pokaždé stejně), pak zavolá `release_all_then_press`, takže SFX jdoucí těsně za sebou se uříznou čistě.
- `press(n)` / `release(n)` - podrž a uvolni notu ručně, pro zvuky, které trvají tak dlouho, dokud držíš tlačítko, místo aby cvakly jednou.
- `music(midi_track)` - přehraje `MidiTrack` (z `load_midi`) na hlasu 0, ve smyčce.
- `stop_music()` - zastaví hudební hlas.

### `Drone(synth, waveform=None, amplitude=0.35, attack=0.03, release=0.12)`

Souvisle **držená** nota pro zvuk motoru, sirény nebo dronu: spustíš ji jednou a potom za běhu řídíš její výšku a hlasitost. Zatímco `note()` a `sfx` přehrají jednorázový efekt, `Drone` drží jedinou notu na hlasu SFX. `synthio` čte živé hodnoty `.frequency` a `.amplitude` pro každý zvukový buffer, takže tón může sledovat například rychlost auta. `synth` je aktivní `Synth`; výchozí `waveform` je `SAW`.

- `.start()` - stiskne drženou notu (idempotentní - bezpečné volat znovu během hraní).
- `.set(frequency, amplitude=None)` - aktualizuje za běhu výšku v Hz a volitelně hlasitost.
- `.stop()` - uvolní notu (např. na obrazovce title nebo výsledků).

```python
eng = snd.Drone(s, waveform=snd.SAW)
eng.start()                                    # at race start
# každý snímek; rev = rychlost / nejvyšší rychlost v rozsahu 0..1:
eng.set(70 + 270 * rev, amplitude=0.2 + 0.5 * rev)
eng.stop()                                     # na titulní obrazovce nebo ve výsledcích
```

### `load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240)`

Načte soubor `.mid` jako `synthio.MidiTrack` pro `Synth.music`. `waveform` a `envelope` vyberou
hlas nástroje pro celou stopu; `tempo` (BPM) a `ppqn` nastaví rychlost přehrávání. Loader přijímá
standardní hlavičku SMF formátu 0.

```python
import picogame_synth as snd
import picogame_input

s = snd.Synth()
# Each SFX is a Note built ONCE (envelope + optional bend + filter).
blip = snd.note(72, snd.SQUARE, decay=0.10)
zap = snd.note(60, snd.SAW, decay=0.18, cutoff=4000, bend=snd.pitch_bend(12, 180))
boom = snd.note(45, snd.NOISE, attack=0.0, decay=0.30, amplitude=0.55, cutoff=2800)

btn = picogame_input.Buttons()
while True:
    btn.poll()
    if btn.just_pressed(btn.A):
        s.sfx(zap)
```

:::note[Pozor]
- Žádné hlídání importu není potřeba: modul běží jako tiché no-opy na firmwaru bez audia a `Synth()`, který selže uprostřed initu (těsný heap, obsazený pin), degraduje stejně, místo aby vyhodil výjimku.
- Každou `note()` vytvoř jednou při startu a potom ji přehrávej opakovaně; `sfx` se o nové spuštění postará. Vytváření not v každém snímku zbytečně spotřebovává čas a narušuje nové spuštění LFO.
- Živé okno simulátoru tyto hlasy aproximuje přes `pygame.mixer`; pro přesný náhled vyrenderuj SFX do WAV pomocí `tools/synth_preview.py`
  a výsledné vyvážení ověř na cílovém reproduktoru. Význam může nést průběh výšky: vzestupný pro zisk,
  sestupný pro ztrátu a střídání tónů pro varování.
- Zvuk vydává synthesizer, ne objekt noty - efekty hrají jen přes živý `Synth` a hlasy mixeru jsou jen dva (jeden hudba, jeden SFX), takže překrývající se synth SFX sdílejí jediný hlas.
:::

## picogame_sfx

`picogame_sfx` poskytuje ucelenou sadu pojmenovaných efektů nad `picogame_synth`. Použij ji, pokud
se ke hře hodí vestavěný arkádový zvuk. Pro událost, kterou sada nepokrývá, nebo pro jiný zvukový
styl sestav vlastní objekty přes `picogame_synth.note()`. Bez dostupného audia jsou všechna volání tichá.

### `Kit(synth)`

`Kit` při vytvoření sestaví všechny hlasy z předaného `picogame_synth.Synth()`. Efekty pak spouštíš
podle herní události a jednou za snímek voláš `tick()`. Sada používá jediný SFX hlas, proto události
řadí podle priority a důležité zvuky na krátkou dobu chrání před přerušením:

- `blip()` - pohyb v menu, výběr nebo potvrzení;
- `coin()` - sebrání mince nebo jiného bodovaného předmětu;
- `powerup()` - vylepšení, dokončení úrovně nebo vlny;
- `zap()` - akce hráče, například výstřel nebo dash;
- `pew()` - výstřel nepřítele, výš položený a tenčí než `zap()`;
- `jump()` - skok nebo odpálení;
- `hit(rotate=True)` - zásah nepřítele nebo objektu; při rychlé palbě střídá jas zvuku;
- `hurt()` - poškození hráče, tmavší a klesající zvuk odlišný od `hit()`;
- `boom()` - zničení objektu, nepřítele nebo řady;
- `explosion()` - velký výbuch s nejdelší ochranou před přerušením;
- `tick()` - posune arpeggia efektů `coin()` a `powerup()` a odpočítá ochranná okna.

Hlasitost a ztlumení nastavuje společný `Synth`. Metoda
`synth.set_levels(music=None, sfx=None)` mění úroveň hudby nebo efektů v rozsahu 0,0–1,0.
`synth.mute(on)` ztlumí oba hlasy a zapamatuje jejich nastavené úrovně.

```python
import picogame_synth as snd
import picogame_sfx as sfx
import picogame_input

s = snd.Synth()
kit = sfx.Kit(s)                       # hlasy sestaví jednou

btn = picogame_input.Buttons()
while True:
    btn.poll()
    if btn.just_pressed(btn.A):
        kit.zap()
    if btn.just_pressed(btn.B):
        kit.jump()
    # při zničení: kit.boom(); při zranění: kit.hurt(); při sebrání: kit.coin()
    kit.tick()                         # jednou za snímek
```

:::note[Pozor]
- Vytvoř `Kit` jednou při startu a znovu ho používej. Opakované sestavení zbytečně zatěžuje heap.
- `kit.tick()` volej v každém snímku. Bez něj se zastaví arpeggia a odpočítávání ochranných oken.
- Všechny efekty sdílejí jediný SFX hlas. Když se sejdou, priorita určí, který zazní.
- Živé okno simulátoru sadu přehrává (aproximace); pro přesný náhled ji vyrenderuj do WAV a konečné vyvážení ověř na zařízení.
:::
