# FEATURES.md §15 illustration: relative heap cost of the three asset-storage tiers.
# Bars are schematic (not to exact scale) -- the point is the order of magnitude.
import picogame as pg, picogame_game, picogame_font, terminalio

F = terminalio.FONT
scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(14, 16, 30))

WHITE = pg.rgb565(235, 235, 245)
DIM = pg.rgb565(140, 150, 175)


def text(s, x, y, fg):
    bmp, _, _ = picogame_font.render_text(pg, F, s, fg, None)
    scene.add(pg.Sprite(bmp, x, y))


def bar(y, w, color):
    c = pg.Canvas(max(3, w), 26)
    c.clear(color)
    scene.add(c)
    c.move(8, y)


text("Where the art lives - relative heap cost", 8, 8, WHITE)

# (label, schematic width px, RAM note, colour)
rows = [
    ("Frozen (XIP from flash)", 5, "~0 bytes", pg.rgb565(70, 210, 120)),
    ("Streaming (StreamSheet)", 34, "~one frame", pg.rgb565(90, 160, 235)),
    ("File -> RAM (whole sheet)", 296, "w*h*frames", pg.rgb565(235, 180, 70)),
]
y = 40
for label, w, note, color in rows:
    text(label, 8, y, DIM)
    bar(y + 16, w, color)
    text(note, 8 + max(3, w) + 6 if w < 220 else 12, y + 22, WHITE)
    y += 64

while True:
    scene.refresh()
