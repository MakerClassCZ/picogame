# Level editor — standalone copy

This is the same app the docs site serves at
[picogame.makerclass.cz/editor/](https://picogame.makerclass.cz/editor/): a **static** page, no
backend, no build step. Everything (project state, PNG import, PAL8 baking, the scene bake) runs in
your browser.

Run it locally:

```sh
python3 -m http.server -d tools/editor 8000    # then open http://localhost:8000/
```

Serving it over http:// (rather than opening index.html from disk) matters only so the bundled demo
projects can be fetched. Host it anywhere static — GitHub Pages works.

`node test.js` runs the headless tests for the model + exporters + the Tiled import.

Files: `index.html` + `style.css` (UI), `core.js` (project model, exporters, scene bake, Tiled
import, PAL8 quantizer), `render.js`/`viewport.js`/`minimap.js` (canvas), `history.js` (undo),
`app.js` (everything interactive). `README.md` is the user guide.
