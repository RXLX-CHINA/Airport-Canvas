"""Small, transparent desktop glyphs; no platform font dependency."""
from PIL import Image,ImageDraw
from collections import deque
KEYS={'AUX_STAND19','HANGAR19','TERMINAL19','OTHER_BUILDING19','PIER19','BRIDGES19','NUMBER_BRIDGES19','ENHANCED19','NO_ENTRY20'}
def tool(key):
    im=Image.new('RGBA',(72,40),(0,0,0,0));d=ImageDraw.Draw(im);blue='#28647b';yellow='#d9a82a'
    if key in ('AUX_STAND19','HANGAR19'):
        d.polygon([(18,29),(18,16),(9,9),(63,9),(54,16),(54,29)],outline=blue,width=2)
        for y in range(10,39,7):d.line((36,y,36,min(39,y+4)),fill=yellow,width=3)
        d.polygon([(30,9),(36,3),(42,9),(42,17),(30,17)],fill='#ffda63',outline=blue)
        if key=='HANGAR19':d.line((10,15,36,1,62,15),fill=blue,width=3);d.line((13,14,13,35,59,35,59,14),fill=blue,width=2)
    elif key=='TERMINAL19':
        d.rectangle((7,17,65,35),fill='#b9d0de',outline=blue,width=2)
        for x in (14,28,42,56):d.rectangle((x,23,x+5,29),fill=blue)
        d.line((7,17,36,5,65,17),fill=blue,width=2)
    elif key=='OTHER_BUILDING19':
        d.rectangle((17,6,42,35),fill='#c5d6e0',outline=blue,width=2)
        d.rectangle((42,17,59,35),fill='#dbe6ec',outline=blue,width=2)
        for y in (12,20):
            for x in (22,32):
                d.rectangle((x,y,x+5,y+4),fill=blue)
        d.rectangle((46,22,54,26),fill=blue)
        d.rectangle((26,28,33,34),fill=blue)
        d.line((12,36,63,36),fill=blue,width=2)
    elif key in ('PIER19','BRIDGES19','NUMBER_BRIDGES19'):
        d.rectangle((4,28,68,37),fill='#b9d0de',outline=blue);d.rectangle((30,3,42,28),fill='#b9d0de',outline=blue,width=2)
        if key=='PIER19':d.line((36,24,36,8),fill=yellow,width=3);d.polygon([(31,12),(36,4),(41,12)],fill=yellow)
        else:
            for y in (8,20):d.line((17,y,30,y),fill=blue,width=3);d.line((42,y,55,y),fill=blue,width=3)
            if key=='NUMBER_BRIDGES19':
                d.text((8,1),'1',fill=yellow);d.text((57,1),'2',fill=yellow);d.arc((13,-1,60,28),190,345,fill=yellow,width=2)
    elif key=='ENHANCED19':
        d.arc((8,-18,68,40),10,160,fill=yellow,width=3)
        for x in (8,22,36,50):d.line((x,30,x+7,30),fill=blue,width=2);d.line((x,36,x+7,36),fill=blue,width=2)
    else:
        d.rectangle((4,8,68,32),fill='#c72d3e');d.text((10,13),'NO ENTRY',fill='white')
    return im

def transparent(image):
    im=image.convert('RGBA');pix=im.load();w,h=im.size;bg=pix[0,0][:3];queue=deque([(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]+[(0,y) for y in range(h)]+[(w-1,y) for y in range(h)]);seen=set()
    while queue:
        x,y=queue.popleft()
        if (x,y) in seen or not 0<=x<w or not 0<=y<h:continue
        seen.add((x,y))
        if max(abs(pix[x,y][k]-bg[k]) for k in range(3))>3:continue
        pix[x,y]=(0,0,0,0);queue.extend(((x-1,y),(x+1,y),(x,y-1),(x,y+1)))
    return im
