import picogame as pg, picogame_game
scene,_,_ = picogame_game.setup(background=pg.rgb565(10,10,20))
ps=pg.Particles(360,size=2,gravity=0.04,fade=True); scene.add(ps)
for (x,y,c) in ((100,130,pg.rgb565(250,170,80)),(215,120,pg.rgb565(120,210,255)),(160,80,pg.rgb565(245,220,80))):
    ps.emit(x,y,48,4,30,c)
while True:
    ps.tick(); scene.refresh()
