# picogame StripDraw demo: a per-scanline pseudo-3D road + sky gradient drawn with
# ZERO pixel buffer (no Canvas surface). On the RP2040 the same scene as a Canvas would
# cost 150 KB; as a StripDraw it costs 0 B. Runs in the sim and on real hardware.
import picogame as pg
import picogame_game

scene, _bufa, _bufb = picogame_game.setup(background=pg.rgb565(20, 20, 30))
W, H = 320, 240
HORIZON = 118
phase = 0  # advanced each frame so the dashed edges/center line scroll toward the viewer


def draw_road(v, vx, vy, vw, vh):
    # v is a Canvas view of THIS strip; v-local (0,0) == screen (vx, vy).
    for ly in range(vh):
        Y = vy + ly                                  # screen row
        if Y < HORIZON:
            t = Y / float(HORIZON)                   # sky gradient
            v.fill_rect(0, ly, vw, 1, pg.rgb565(int(50 + t * 60), int(120 + t * 90), 225))
        else:
            t = (Y - HORIZON) / float(H - HORIZON)
            half = int(18 + t * t * 150)
            cx = W // 2
            v.fill_rect(0, ly, vw, 1, pg.rgb565(45, int(120 + t * 70), 55))      # grass
            v.fill_rect(cx - half - vx, ly, half * 2, 1, pg.rgb565(95, 95, 100))  # road
            ew = max(1, half // 12)
            edge = pg.rgb565(230, 70, 70) if (int(Y * 0.4) + phase) % 2 else pg.rgb565(235, 235, 235)
            v.fill_rect(cx - half - vx, ly, ew, 1, edge)
            v.fill_rect(cx + half - ew - vx, ly, ew, 1, edge)
            if (int(Y * 0.5) + phase) % 2:
                v.fill_rect(cx - 2 - vx, ly, 4, 1, pg.rgb565(240, 240, 240))      # center line


road = pg.StripDraw(draw_road, 0, 0, W, H)
scene.add(road)

# a normal sprite on top, to prove StripDraw composites under other layers
import terminalio
import picogame_font
bm, _, _ = picogame_font.render_text(pg, terminalio.FONT, "StripDraw", pg.rgb565(255, 255, 80), None)
spr = pg.Sprite(bm, W // 2, 18)
spr.anchor = (0.5, 0.5)
spr.scale = 2.0
scene.add(spr)

while True:
    phase += 1  # scroll the dashes so the full-frame road animates under the sprite
    scene.refresh()
