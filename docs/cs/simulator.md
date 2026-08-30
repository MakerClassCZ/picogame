# Desktopový simulátor

Ve webovém [Playgroundu](/cs/playground/) si můžeš picogame vyzkoušet přímo v prohlížeči.
**Desktopový simulátor** nabízí stejné API hry na počítači a hodí se pro práci s místními
soubory, převedenou grafikou PNG, automatické ukládání snímků a skriptované běhy z příkazové řádky.

Je součástí repozitáře (`sim/`). Naklonuj [picogame](https://github.com/MakerClassCZ/picogame) a máš
všechno: simulátor, hry i pomocníky `picogame_*`.

```sh
git clone https://github.com/MakerClassCZ/picogame
cd picogame
```

## Instalace

Režim bez okna, který vykreslí snímky a uloží výsledný obrázek, funguje rovnou. Pro interaktivní
okno nainstaluj pygame:

```sh
pip install pygame
```

:::tip[Když to nefunguje]
- `pip` nenalezen? Použij místo toho `python3 -m pip install pygame`.
- Všechny příkazy spouštěj ze složky naklonovaného `picogame`, té, která obsahuje `sim/` a `lib/`.
- Bez pygame spusť simulátor s `--shot out.png`; proběhne bez okna a uloží poslední snímek.
:::

## Spuštění hry

Hraj v okně (výchozí, když je nainstalovaný pygame; při startu vypíše ovládání):

```sh
python3 sim/run.py demos/picogame_flappy.py
```

Vykresli několik snímků bez okna a ulož výsledný obrázek pro dokumentaci, testy nebo CI:

```sh
python3 sim/run.py demos/picogame_flappy.py --frames 80 --shot shot.png
```

### Přepínače

| Přepínač | Co dělá |
|---|---|
| `--backend pygame` / `pil` | vynutí interaktivní okno / běh bez okna. Ve výchozím nastavení se otevře okno, pokud je pygame nainstalovaný; jinak běží simulátor bez něj. `--shot` a `--profile` také okno neotevírají. |
| `--frames N` | vykreslí N snímků a skončí (výchozí 150) |
| `--shot FILE` | uloží PNG posledního snímku |
| `--shot-at N` | uloží ten PNG na snímku N místo na konci |
| `--hold RIGHT,A` | drží tyto klávesy po celý běh, takže hru řídíš bez klávesnice |
| `--profile` | vypíše časování jednotlivých fází |

V živém okně: šipky nebo **WASD** pohyb; `F` (nebo `Ctrl`) = A, `G` (nebo `Space`) = B, `R`/`Q` = X, `T`/`E` = Y.

## Web, nebo desktop?

Oba nabízejí stejné API směrem ke hře, takže stejný kód hry běží v obou. Pod kapotou se ale liší
(prohlížeč spouští nativní C modul zkompilovaný do WASM; desktopový simulátor je referenční
implementace v Pythonu), takže časování, chování RAM, zvuk a efekty panelu jsou jen aproximace —
tyhle věci si ověř na zařízení.

| | Webový Playground | Desktopový simulátor |
|---|---|---|
| Nastavení | žádné, běží v prohlížeči | naklonovat repo (plus pygame pro okno) |
| Nejlepší na | vyzkoušení nápadu, sdílení odkazu, první kroky | soubory s grafikou, snímky bez okna, automatizaci z příkazové řádky, místní vývoj |
| Grafika | tvary generované kódem | vlastní PNG a převedená grafika |

Až hra běží dobře, zkopíruj ji na desku a ověř časování, ovládání, zvuk a spotřebu paměti.
Viz [Spuštění na hardwaru](hardware.md).
