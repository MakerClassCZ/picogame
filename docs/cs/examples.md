# picogame ukázkové hry

Klikni na hru a spusť ji rovnou v prohlížeči — nebo si ji zkopíruj do PicoPadu. Tohle jsou hry, které jsou součástí picogame.

## Jak si hru pustit

**▶ V prohlížeči — nejjednodušší, nic se neinstaluje.** Klikni na kteroukoli hru níže. Otevře se v
[Playgroundu](/cs/playground/) a hned se rozběhne. Ovládání: **šipky** (nebo WASD) pohyb, **F** (nebo Ctrl) =
tlačítko A, **G** = tlačítko B.

**💻 Na počítači.** Jednou si stáhni kód a spusť jeden řádek — otevře se okno desktopového simulátoru:

```bash
git clone https://github.com/MakerClassCZ/picogame
cd picogame
python3 sim/run.py games/snake/code.py      # kterákoli hra
```

Potřebuješ Python 3 (pro živé okno přidej `pip install pygame`; bez něj se běh jen uloží jako screenshot).

**🎮 Na skutečném hardwaru.** Tyhle hry rozběhne jakékoli Raspberry Pi Pico s malým displejem, pár
tlačítky a bzučákem — hotový **PicoPad**, nebo [vlastní stavba](hardware.md). Nahraješ firmware,
zkopíruješ soubory hry, hotovo.

## Hry

<div class="pg-cards">
  <a class="pg-card" href="/cs/playground/?game=cavern"><span class="thumb"><img src="../docs/img/genre_cavern.png" alt="Plošinovka"/><span class="play"></span></span><span class="meta"><b>Plošinovka</b><small><code>picogame_cavern</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=picobike"><span class="thumb"><img src="../docs/img/genre_picobike.png" alt="Pseudo-3D závody"/><span class="play"></span></span><span class="meta"><b>Pseudo-3D závody</b><small><code>picogame_picobike</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=squest_full"><span class="thumb"><img src="../docs/img/genre_squest_full.png" alt="Vertikální střílečka"/><span class="play"></span></span><span class="meta"><b>Vertikální střílečka</b><small><code>picogame_squest_full</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=picowing"><span class="thumb"><img src="../docs/img/genre_picowing.png" alt="Letadlová střílečka"/><span class="play"></span></span><span class="meta"><b>Letadlová střílečka</b><small><code>picogame_picowing</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=quest"><span class="thumb"><img src="../docs/img/genre_quest.png" alt="Top-down RPG"/><span class="play"></span></span><span class="meta"><b>Top-down RPG</b><small><code>picogame_quest</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=picatro"><span class="thumb"><img src="../docs/img/genre_picatro.png" alt="Karetní roguelite"/><span class="play"></span></span><span class="meta"><b>Karetní roguelite</b><small><code>picogame_picatro</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=train"><span class="thumb"><img src="../docs/img/genre_train.png" alt="Logická hra"/><span class="play"></span></span><span class="meta"><b>Logická hra</b><small><code>picogame_train</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=corona"><span class="thumb"><img src="../docs/img/genre_corona.png" alt="Survivor aréna"/><span class="play"></span></span><span class="meta"><b>Survivor aréna</b><small><code>picogame_corona</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=salvo"><span class="thumb"><img src="../docs/img/genre_salvo.png" alt="Tower defense"/><span class="play"></span></span><span class="meta"><b>Tower defense</b><small><code>picogame_salvo</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=platformer"><span class="thumb"><img src="../docs/img/genre_platformer.png" alt="Plošinovka s posunem"/><span class="play"></span></span><span class="meta"><b>Plošinovka s posunem</b><small><code>picogame_platformer</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=pacman"><span class="thumb"><img src="../docs/img/genre_pacman.png" alt="Honička v bludišti"/><span class="play"></span></span><span class="meta"><b>Honička v bludišti</b><small><code>picogame_pacman</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=picotris"><span class="thumb"><img src="../docs/img/genre_picotris.png" alt="Padající bloky"/><span class="play"></span></span><span class="meta"><b>Padající bloky</b><small><code>picogame_picotris</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=arkanoid"><span class="thumb"><img src="../docs/img/genre_arkanoid.png" alt="Breakout"/><span class="play"></span></span><span class="meta"><b>Breakout</b><small><code>picogame_arkanoid</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=asteroids"><span class="thumb"><img src="../docs/img/genre_asteroids.png" alt="Asteroids"/><span class="play"></span></span><span class="meta"><b>Asteroids</b><small><code>picogame_asteroids</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=snake"><span class="thumb"><img src="../docs/img/genre_snake.png" alt="Had"/><span class="play"></span></span><span class="meta"><b>Had</b><small><code>picogame_snake</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=picoracer"><span class="thumb"><img src="../docs/img/topracer.png" alt="Závody z ptačí perspektivy"/><span class="play"></span></span><span class="meta"><b>Závody z ptačí perspektivy</b><small><code>picogame_picoracer</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=soccer"><span class="thumb"><img src="../docs/img/genre_soccer.png" alt="Sport"/><span class="play"></span></span><span class="meta"><b>Sport</b><small><code>picogame_soccer</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=pinball"><span class="thumb"><img src="../docs/img/genre_pinball.png" alt="Pinball"/><span class="play"></span></span><span class="meta"><b>Pinball</b><small><code>picogame_pinball</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=match3"><span class="thumb"><img src="../docs/img/genre_match3.png" alt="Match-3"/><span class="play"></span></span><span class="meta"><b>Match-3</b><small><code>picogame_match3</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=dinorun"><span class="thumb"><img src="../docs/img/genre_dinorun.png" alt="Nekonečný běh"/><span class="play"></span></span><span class="meta"><b>Nekonečný běh</b><small><code>picogame_dinorun</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=flappy"><span class="thumb"><img src="../docs/img/genre_flappy.png" alt="Flappy"/><span class="play"></span></span><span class="meta"><b>Flappy</b><small><code>picogame_flappy</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=starfall"><span class="thumb"><img src="../docs/img/genre_starfall.png" alt="Chytací arkáda"/><span class="play"></span></span><span class="meta"><b>Chytací arkáda</b><small><code>picogame_starfall</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=missile"><span class="thumb"><img src="../docs/img/genre_missile.png" alt="Raketová obrana"/><span class="play"></span></span><span class="meta"><b>Raketová obrana</b><small><code>picogame_missile</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
  <a class="pg-card" href="/cs/playground/?game=zoom"><span class="thumb"><img src="../docs/img/genre_zoom.png" alt="Pseudo-3D brány"/><span class="play"></span></span><span class="meta"><b>Pseudo-3D brány</b><small><code>picogame_zoom</code></small><span class="run">▶ spustit v prohlížeči</span></span></a>
</div>

Každá hra je jeden samostatný program a její úvodní komentář přesně vypisuje, co používá — takže
slouží i jako šablona: začni od nejbližší a přetvoř ji. Všechny najdeš v
[repozitáři picogame](https://github.com/MakerClassCZ/picogame).

## Nahrání hry do zařízení

1. Nahraj `firmware.uf2` — postup na stránce [Spuštění na hardwaru](hardware.md).
2. Zkopíruj `code.py` hry na disk CIRCUITPY, plus pomocné moduly a případné asset soubory, které
   importuje (úvodní komentář každé hry je vypisuje).

Restartuj napájení a hra běží.
