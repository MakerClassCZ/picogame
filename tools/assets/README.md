# Asset converter — standalone copy

The browser twin of `tools/png2picogame.py`, same as
[picogame.makerclass.cz/assets/](https://picogame.makerclass.cz/assets/): drop a PNG, pick the
layout (sprite sheet / tileset grid / single image), download a `.py` module with `bitmap(pg)`.
Static page, no backend; it loads `core.js` and `style.css` from `../editor/`, so keep the two
folders side by side.

```sh
python3 -m http.server -d tools 8000        # then open http://localhost:8000/assets/
```

The output is byte-identical to the CLI converter (a golden test in the picogame-web repo keeps
them in sync).
