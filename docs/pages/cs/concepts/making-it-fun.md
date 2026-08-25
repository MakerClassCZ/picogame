---
title: Jak udělat hru zábavnou
description: Jak doladit fungující herní smyčku pomocí jasné akce, okamžité odezvy, tempa obtížnosti a rozumného rozsahu.
sidebar:
  order: 5
---

Až herní smyčka funguje, dolaď čtyři věci: hlavní akci hráče, odezvu, obtížnost a rozsah.
Laťka není „běží to" — je to **zábava v prvních 10 sekundách**. Stránka
[Herní vzory](/cs/concepts/patterns/) ukazuje k těmto myšlenkám kód.

## Začni hlavní akcí

Než pojmenuješ sloveso, rozhodni fantazii — čím hráč *je*. „Chytání" je jiná hra jako uspěchaný kuchař,
brankář, nebo někdo, kdo zachraňuje padající hvězdy. Vyber fantazii, pak sloveso na jedno slovo: skok,
střelba, řízení, spojování, uhýbání. Postav kolem něj cyklus: **akce → výsledek → reakce hráče → další
akce v nových podmínkách**.

Takhle těsná smyčka má být čitelná pouhým *pozorováním* po deset sekund a zábavná bez grafiky a zvuku.
Vyzkoušej ji s tvary z `picogame_shapes` dřív, než uděláš finální grafiku — pokud není zábavná jako
obdélník honící kolečko, lepší grafika ji nezachrání. Uprav nejdřív pravidla a odezvu.

## Dej akcím okamžitou odezvu

Odezva propojí vstup nebo kolizi s výsledkem, který hráč vidí a slyší, a spustí se ve stejné aktualizaci,
která událost zpracovala — opožděná odezva působí těžkopádně i při 30 fps. Ne každá odezva je stejně
levná. Zhruba v pořadí zábavy získané za utracený bajt:

1. **Zvuk u hlavní akce** — nejvíc muziky za nejmíň kódu; pípnutí potvrdí, co oko už vidělo.
   Nejjednodušší pípnutí nepotřebuje `.wav`:

   ```python
   beep = picogame_audio.tone(880, 90)   # krátký vysoký blip, vytvořený jednou
   audio.sfx(beep)                       # spusť ho ve snímku, kdy nastane chycení
   ```

   Význam nese *průběh* — vysoký zní jako dobře, nízký jako špatně. Hotový kit
   [`picogame_sfx`](/cs/helpers/audio/) dá obojí:

   Chycení (lehký blip): <audio controls preload="none" src="/audio/sfx_blip.mp3"></audio><br/>
   Minutí (nízký, klesající tón): <audio controls preload="none" src="/audio/sfx_hurt.mp3"></audio>

2. **Krátký záblesk při zásahu** — nastav opaque pixely spritu na plochou bílou na 1–3 snímky a pak
   zhasni. Skoro zdarma:

   ```python
   spr.flash = pg.rgb565(255, 255, 255)   # při nárazu
   spr.flash = 0                          # o 2 snímky později: zpět do normálu
   ```

   ![Tvor problikne bíle ve snímku, kdy dopadne střela](/img/fx_hitflash.gif)

3. **Mírný otřes obrazovky** — `picogame_fx.Shake`, pár pixelů, rychle doznívající. Víc už působí jako
   šum, ne náraz:

   ```python
   shaker.add(0.6)      # při zásahu — trauma se umocňuje, malé události sotva zatřesou
   shaker.tick(0, 0)    # každý snímek (sem vlož offset kamery, pokud ji máš)
   ```

   ![Krátký kop otřesu, který doznívá](/img/fx_shake.gif)

4. **Krátké pozastavení (hit-stop)** — zmraz simulaci na 2–8 snímků při velkém zásahu; náraz pak
   *sedne*. Engine na to nemá primitivum — přeskočíš vlastní ticky:

   ```python
   freeze = 4               # při velkém nárazu
   if freeze > 0:           # na začátku smyčky, dokud mrzneme:
       freeze -= 1; clock.tick(); continue
   ```

5. **Malý výtrysk částic** — pop nebo prstenec při chycení či skóre:

   ```python
   ps.emit(x, y, 16, 4, 24, pg.rgb565(255, 210, 120))   # výtrysk při události
   ps.tick()                                            # každý snímek
   ```

   ![Výtrysk částic, který se rozpíná a slábne](/img/fx_particles.gif)


Utrať první položku dřív než pátou — jeden dobrý zvuk překoná pět slabých částicových efektů. Sílu
efektu přizpůsob události a zachovej čitelnost hrací plochy; `picogame_fx` a nativní blit efekty pokryjí
většinu, viz [Efekty](/cs/helpers/effects/) a stránku [vzory](/cs/concepts/patterns/).

:::caution[Bezpečnost blikání]
Nikdy neblikej celou obrazovkou rychleji než ~3 Hz (≥10 snímků od sebe při 30 fps) a hlídej shluky
záblesků při zásahu nad tuto mez — je to riziko záchvatu. Dej přednost lokálnímu `sprite.flash` před
celoobrazovkovým bílým snímkem a nabídni přepínač omezených efektů.
:::

## Obtížnost, která dýchá

Výzva má stoupat jako **pila**, ne po přímce: buduj napětí 20–40 sekund, uvolni ho u milníku (vyčištěná
vlna, kontrolní bod), pak znovu přitáhni asi o 10 % víc. Plochý nárůst začne nudit do druhé minuty;
monotónní stoupání hráči nedá vydechnout.


- **Nejdřív zvyšuj rychlost, hustotu nebo pestrost, ne životy.** Změní to způsob hraní místo prodlužování
  stejné situace.
- **Hrozby oznam předem.** Čitelný náběh a dost času na reakci — lidský práh je asi 250 ms (zhruba
  8 snímků při 30 fps). Pod ním přestane zásah působit jako hráčova chyba.
- **Buď velkorysý** — tohle dělá hru *férovou*, ne snadnou: coyote time a jump buffer
  (`picogame_input.Timer`), i-frames po zásahu, aby jedna chyba nezřetězila smrt, hitbox menší než
  sprite hráče.
- **Restartuj pod půl sekundy.** Obnov běh na místě; nikdy neposílej hráče přes menu, aby to zkusil znovu.

## Drž rozsah pod kontrolou

Postav nejmenší úplnou verzi hlavní smyčky, zahraj si ji a teprve potom přidávej. Funkci vynech, pokud
nemění hráčova rozhodnutí ani sílu odezvy — čtvrtý typ nepřítele, který hraje přesně jako první tři, není
hloubka. Omezení [RAM](/cs/memory/) a [časování](/cs/performance/) cílového zařízení jsou užitečná hranice, ne jen
překážka.

## Co si hráči pamatují

Pokus se pamatuje podle vrcholu a konce, ne podle průměrného snímku. Dej každému běhu zřetelný vrchol
a promyšleně zakonči: po neúspěchu ukaž výsledek, přidej poslední vizuální nebo zvukovou tečku a nabídni
restart bez prodlevy. Tečka při smrti stojí málo a je to ona, kvůli které hráč znovu sáhne po tlačítku.

## Před → po: hra na chytání

Jednotlačítková hra — pohyb vlevo/vpravo, chytej padající tvary, tři minutí a končíš. Mdlá verze: ticho,
tvary padají pořád stejnou rychlostí, text „GAME OVER", žádná nápověda na restart. Po aplikaci myšlenek
výše, od nejlevnějšího:

- **Zvuk** — blip při každém chycení, výrazný nízký žuchnutí při každém minutí. Jedno volání
  `picogame_sfx.Kit`; okamžitě mění, jak každé chycení *působí*.
- **Záblesk** — chycený tvar problikne bíle na 2 snímky, než opustí pool.
- **Otřes** — 3–4px `picogame_fx.Shake` jen při minutí, doznívající půl sekundy — ne při každém chycení,
  jinak dobrou odezvu utopí v šumu.
- **Férovost** — hitbox chytače je o pár pixelů užší než jeho sprite a tvar, který zavadí o okraj, se
  stále počítá. Bez toho působí minutí jako chyba hry, ne pomalá reakce.
- **Pila obtížnosti** — rychlost pádu a spawn rate se zvýší každých 5 chycení, každý krok ~10 % těžší,
  přičemž dvě sekundy po zrychlení necháš beze změny, ať se nová rychlost usadí.
- **Peak-end** — nejlepší série běhu se ukáže velká nahoře na game-over obrazovce, nad skóre; A okamžitě
  spustí nový běh.

Nic z toho nezměnilo pravidla chytání. Změnilo to, jak chytání *působí* — a o tom je celá tahle stránka.

---

Dál: [vzory](/cs/concepts/patterns/) převádějí tyto principy do kódu; [tutoriály](/cs/tutorials/)
je používají ve třech hrách.
