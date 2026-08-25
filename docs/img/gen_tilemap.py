import picogame as pg, picogame_game, picogame_shapes as shp
scene,_,_ = picogame_game.setup(background=pg.rgb565(8,10,22))
T=16; cols,rows=20,15
ts=shp.tileset_colors(T,T,[pg.rgb565(70,160,90),pg.rgb565(150,110,70),pg.rgb565(90,140,230),pg.rgb565(120,120,135)])
tm=pg.Tilemap(ts,cols,rows)
for ty in range(rows):
    for tx in range(cols):
        if tx==0 or ty==0 or tx==cols-1 or ty==rows-1: tm.set_tile(tx,ty,4)   # wall border
        elif (tx+ty)%2==0: tm.set_tile(tx,ty,1)
        elif tx%5==0 and ty%3==0: tm.set_tile(tx,ty,2)
        elif (tx*ty)%7==0: tm.set_tile(tx,ty,3)
scene.add(tm)
while True: scene.refresh()
