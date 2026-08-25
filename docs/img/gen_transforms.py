import picogame as pg, picogame_game, picogame_shapes as shp
scene,_,_ = picogame_game.setup(background=pg.rgb565(18,22,38))
bar = shp.rect(34, 12, pg.rgb565(245,200,60))
for i,ang in enumerate((0,30,60,90)):
    s=pg.Sprite(bar,45+i*72,70); s.anchor=(0.5,0.5); s.angle=ang; scene.add(s)
for i,sc in enumerate((0.6,1.2,1.8,2.6)):
    s=pg.Sprite(bar,45+i*72,165); s.anchor=(0.5,0.5); s.scale=sc; scene.add(s)
while True: scene.refresh()
