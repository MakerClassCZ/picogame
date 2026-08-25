import picogame as pg, picogame_game, picogame_shapes as shp
scene,_,_ = picogame_game.setup()
cell=8; gw=320//cell; gh=240//cell; N=10
SH=[pg.rgb565(min(255,30+i*10),min(255,60+i*16),max(0,150-i*8)) for i in range(N)]
sky=pg.Tilemap(shp.color_frames(cell,cell,SH),gw,gh)
for gy in range(gh):
    for gx in range(gw):
        v=int(pg.fbm2d(gx*0.15,gy*0.13,octaves=3,seed=11)*(N-1))
        sky.set_tile(gx,gy,0 if v<0 else (N-1 if v>=N else v))
scene.add(sky)
while True: scene.refresh()
