# Nastavení editoru (VS Code / Pylance)

Našeptávání a typová kontrola pro picogame hry na PC — jde o dvě věci, protože picogame program
používá dva druhy modulů:

1. **Pomocné knihovny `picogame_*`** jsou čistý Python. Pylance je najde přes
   `python.analysis.extraPaths` — musí ale ukazovat na složku se **zdrojovými `.py`**, např. klon
   repa [`picogame-libs`](https://github.com/MakerClassCZ/picogame-libs) — **ne** na `/lib` na desce,
   kde jsou `.mpy` bytecode soubory, které Pylance nepřečte.
2. **Nativní moduly** (`picogame` — C engine — a `board`, `displayio`, `synthio`, … z CircuitPythonu)
   nemají Python zdroj, takže potřebují **stubs**:
   - `pip install circuitpython-stubs` pokrývá všechny upstream moduly CircuitPythonu;
   - `picogame` samotný zatím v upstreamu není, jeho stub proto vychází zvlášť jako **`picogame-stubs`**
     — wheel připojený ke každému [release picogame-libs](https://github.com/MakerClassCZ/picogame-libs/releases)
     (generovaný z docstringů enginu, stejný zdroj jako [reference](/cs/reference/)).

## Nastavení

```bash
git clone https://github.com/MakerClassCZ/picogame-libs ~/picogame-libs
pip install circuitpython-stubs
pip install https://github.com/MakerClassCZ/picogame-libs/releases/latest/download/picogame_stubs-latest-py3-none-any.whl
```

(nebo přímo z repa: `pip install "git+https://github.com/MakerClassCZ/picogame-libs#subdirectory=stubs"`)

`.vscode/settings.json` ve složce hry:

```json
{
  "python.analysis.extraPaths": ["~/picogame-libs"],
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.diagnosticSeverityOverrides": { "reportMissingModuleSource": "none" }
}
```

Poslední řádek je důležitý: `picogame-stubs` je balík **jen se stuby** (žádné `picogame.py`
neexistuje — modul je ve firmwaru), takže Pylance sice našeptává `pg.Sprite` i `pg.rgb565` ze
stubu, ale řádek `import picogame` přesto podtrhne hláškou *„could not be resolved from source"*.
Je to varování o chybějícím *runtime* zdroji, ne o typech; tenhle override ho skryje. Totéž platí
pro `board`, `displayio` a další z `circuitpython-stubs`.

Potom `import picogame as pg` našeptává `pg.Sprite`, `pg.Scene`, `pg.rgb565(...)` se signaturami
a docstringy, `import picogame_input` se vyřeší a překlep jako `sprite.frmae` se označí.

### Bez pipu

Když chceš stub nakopírovat ručně, dej pozor, **kam** cesta míří — na search path musí ležet složka
`picogame-stubs` samotná (konvence PEP 561 `<modul>-stubs`), takže:

- `"python.analysis.extraPaths": [".../stubs"]` — složka, která **obsahuje** `picogame-stubs/`. ✅
- `"python.analysis.extraPaths": [".../stubs/picogame-stubs"]` — cesta *dovnitř*. ❌
  `import picogame` se nevyřeší (`picogame-stubs` není název modulu).

Druhá ruční možnost je výchozí složka stubů ve VS Code: zkopíruj `.pyi` do
`typings/picogame/__init__.pyi` ve svém workspace — Pylance ji použije bez jakéhokoli nastavení.

Pyright / mypy: stejné stubs fungují (`pyrightconfig.json` → `extraPaths`, nebo wheel nainstaluj do
prostředí, které Pyright analyzuje).

## Odkud stub pochází

`picogame-stubs/__init__.pyi` generuje `tools/extract_pyi.py` z CircuitPythonu z `//|` docstringů
v `shared-bindings/picogame` — stejný text, který nesou docs i `help()` ve firmwaru, takže stub
nemůže enginu ujet. Regenerace proti stromu firmwaru: `stubs/regen.sh /cesta/k/circuitpython`
v repu picogame-libs.
