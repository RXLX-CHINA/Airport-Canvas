"""Shared text and vector rasterizer for the canvas, thumbnails and PNG export."""
import base64
from functools import lru_cache
import io
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import scene_geometry as g

BASE=Path(__file__).resolve().parent
@lru_cache(maxsize=128)
def text_sprite(value,color,height,rotation=0,font='normal',target_width=None,black_outline=False):
    from font_paths import font_path
    path=font_path(font)
    try:f=ImageFont.truetype(str(path),160)
    except OSError:f=ImageFont.load_default(size=120)
    box=f.getbbox(value or ' ');w=max(1,box[2]-box[0]);h=max(1,box[3]-box[1])
    pad=8 if black_outline else 2
    mask=Image.new('RGBA',(w+2*pad,h+2*pad));ImageDraw.Draw(mask).text((pad-box[0],pad-box[1]),value,font=f,fill=color,stroke_width=5 if black_outline else 0,stroke_fill='#101010')
    if font=='chart_header':
        ink=f.getbbox('H')
        height=height*mask.height/max(1,ink[3]-ink[1])
    height=max(1,min(3000,int(height)));width=max(1,min(12000,round(mask.width*height/mask.height)))
    if target_width is not None:width=max(1,min(12000,int(target_width)))
    mask=mask.resize((width,height),Image.Resampling.LANCZOS)
    if rotation:mask=mask.rotate(rotation,expand=True,resample=Image.Resampling.BICUBIC)
    return mask

def draw_items(items,size,origin,scale,background='#e9eef2',grid=False,progress=None):
    mode='RGBA' if isinstance(background,(tuple,list)) and len(background)==4 else 'RGB'
    im=Image.new(mode,size,background);d=ImageDraw.Draw(im)
    def pp(p):return [origin[0]+p[0]*scale,origin[1]-p[1]*scale]
    if grid:
        step=100*scale
        if step>24:
            x=origin[0]%step
            while x<size[0]:d.line((x,0,x,size[1]),fill='#dce3e8');x+=step
            y=origin[1]%step
            while y<size[1]:d.line((0,y,size[0],y),fill='#dce3e8');y+=step
    for index,e in enumerate(items):
        if progress and index%max(1,len(items)//100)==0:progress(index/max(1,len(items)))
        pts=[pp(p) for p in e['points']]
        if not pts:continue
        if e['type']=='text':
            height=max(1,round(e['size']*scale));sprite=text_sprite(e['text'],e['fill'],height,e.get('rotation',0),e.get('font','normal'),None if not e.get('text_width') else round(e['text_width']*scale),e.get('black_outline',False))
            x,y=pts[0]
            at=(round(x-sprite.width/2),round(y-sprite.height/2))
            if mode=='RGBA':im.alpha_composite(sprite,at)
            else:im.paste(sprite,at,sprite)
            continue
        if e['type']=='polygon' and e.get('fill'):d.polygon(pts,fill=e['fill'])
        color=e.get('stroke')
        if not color:continue
        width=max(1,round(e.get('width',.15)*scale));path=pts+[pts[0]] if e['type']=='polygon' else pts
        dash=e.get('dash')
        if not dash:d.line(path,fill=color,width=width,joint='curve');continue
        pattern=[max(.05,x*scale) for x in dash];idx=0;remain=pattern[0]
        phase=(e.get('dash_offset',0)*scale)%sum(pattern)
        while phase>=remain:
            phase-=remain;idx=(idx+1)%len(pattern);remain=pattern[idx]
        remain-=phase
        for a,b in zip(path,path[1:]):
            length=g.distance(a,b);used=0;u=g.unit(a,b)
            while used<length-1e-9:
                take=min(remain,length-used)
                if idx%2==0:d.line([(a[0]+u[0]*used,a[1]+u[1]*used),(a[0]+u[0]*(used+take),a[1]+u[1]*(used+take))],fill=color,width=width)
                used+=take;remain-=take
                if remain<1e-8:idx=(idx+1)%len(pattern);remain=pattern[idx]
    return im

def sprite_data_url(e,resolution=12):
    image=text_sprite(e['text'],e['fill'],max(8,round(e['size']*resolution)),e.get('rotation',0),e.get('font','normal'),None if not e.get('text_width') else round(e['text_width']*resolution),e.get('black_outline',False))
    f=io.BytesIO();image.save(f,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(f.getvalue()).decode(),image.width/resolution,image.height/resolution
