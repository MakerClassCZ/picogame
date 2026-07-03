# Tutorial 3 — Quest (a top-down RPG in 8 steps)

A Zelda-ish overworld: walk a scrolling map, collect coins, talk to an NPC, fight
slimes, and complete a quest. Assumes you've done 01-bounce and 02-starship. This is
where the engine's **camera** and **tilemap-as-world** come in.

Run any step:
```
python3 sim/run.py tutorials/03-quest/stepN_name.py --hold DOWN --shot /tmp/out.png
```
**Tip:** the talk/quest steps (6–8) are best seen live with `--backend pygame` — a headless
`--shot` can catch a dialog box mid-draw (the overlay paints in several passes), so the box
may screenshot without its text even though it renders fine on device and in the live window.

---

### step 1 — `step1_world.py` · a world bigger than the screen
An ASCII map becomes a `Tilemap` (30×20 tiles = 480×320 px, larger than the 320×240
screen). `shp.tileset_colors` builds the tileset (grass/path/water/tree/wall/door/goal).
`scene.set_view(offset_x, offset_y)` chooses the visible window — that's the camera. The hero lives in
**world** coordinates; the view offset decides where it lands on screen. **You see:** a
patch of world with the hero centred. **Try it:** edit the `MAP` strings.

### step 2 — `step2_walk.py` · walk, camera follows
4-direction movement; after each move `follow()` re-centres the camera, **clamped** to the
world so you never see past the edges (near an edge the hero walks toward the screen edge
instead). The hero faces its movement direction (`sprite.frame`). No wall collision yet —
you can walk over water. **Try it:** change `SPEED`.

### step 3 — `step3_walls.py` · tile collision
`solid_at(pixel_x, pixel_y)` maps a world pixel to a tile and checks a `SOLID` set; `can_walk()`
probes the hero's four corners. We test the X and Y moves **separately**, so you slide
along a wall instead of sticking when pushing diagonally into it. **You see:** water, trees
and walls now block you. **Try it:** add a tile value to `SOLID` (or remove one).

### step 4 — `step4_anim.py` · walk animation
The hero becomes an 8-frame sheet (2 steps × 4 facings), driven by
`picogame_anim.AnimatedSprite`: `play(name)` picks the facing's animation, `tick(dt)`
advances it using the real `dt` from `clock.tick()` (so the walk speed is frame-rate
independent). Standing still shows the rest frame. **Try it:** change the animation `fps`.

### step 5 — `step5_items.py` · items + a fixed HUD
Coins are sprites placed from the map; being normal scene items, they **scroll with the
world**. We collect one when the hero is close, hide it, and count it. `picogame_ui.SceneLabel`
is a **fixed** layer — it does NOT scroll, so the counter stays pinned to the corner.
**Try it:** add more `*` coins to the map.

### step 6 — `step6_npc.py` · talk to an NPC
Stand next to the NPC and press **A** to enter a `dialog` state: the world keeps drawing
underneath while `picogame_ui.TextBox` overlays a message; movement is frozen until you
press a button. **You see:** a "PRESS A" prompt near the NPC, then a dialog box. **Try it:**
change the dialog `LINES`.

### step 7 — `step7_combat.py` · enemies + bump combat
Slimes chase the hero (slower than you, respecting walls). Touching one costs **HP** and
grants brief **i-frames**; press **B** to swing at the tile you're facing and defeat a
slime. HP shows in the HUD; reaching 0 sends you back to start. (A still talks.) **Try it:**
change the slime speed or your starting HP.

### step 8 — `step8_quest.py` · the quest (capstone)
Everything becomes a goal: the NPC asks for all the coins; once you have them, talking
again **opens the door** (we rewrite those tiles from "door" to "path" so collision lets you
through); stepping on the shrine tile **wins**. A small `stage` variable drives the dialog
and the door. **You see:** talk → collect → unlock → reach the shrine → "QUEST COMPLETE".
**Try it:** require defeating all slimes too before the door opens.

---

**The payoff:** you hand-built a whole RPG. You don't have to keep hand-coding maps — the
**editor** lets you paint this map, place the hero/NPC/coins, and flag tiles
(solid/coin/goal) visually, and `picogame_scene` loads it. Everything `step8` does by hand
becomes data. See `../README.md` and `examples/picogame_platformer_scene.py`.
