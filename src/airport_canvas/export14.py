"""Explicit bounded export resolution, DPI, extent and background options."""
import math,json
from pathlib import Path
def dimensions(box,width):
    if isinstance(width,bool) or int(width)!=width or width<1:raise ValueError('像素宽度必须为正整数')
    h=max(1,math.ceil((box[3]-box[1])*width/max(.001,box[2]-box[0])));return int(width),h
def extent_with_boards(scene,items):
    from scene_render import bounds
    from boards24 import group_faces,face_bounds
    extents=[bounds(scene),*(face_bounds(rows,2) for rows in group_faces(items).values())]
    return (min(e[0] for e in extents),min(e[1] for e in extents),
            max(e[2] for e in extents),max(e[3] for e in extents))


def export(scene,path,kind='png',width=2400,dpi=150,transparent=False,box=None,labels=False,facilities=True,protection=False,scale_bar=False,progress=None,board_enlarged=False,mode="MAP",bundle=False,project_name="机场项目"):
    import scene_render as sr
    from export_modes21 import MODES,mode_items
    if bundle:
        from tempfile import TemporaryDirectory
        from zipfile import ZipFile,ZIP_DEFLATED
        with TemporaryDirectory() as directory, ZipFile(path,'w',ZIP_DEFLATED) as archive:
            for index,key in enumerate(MODES):
                file = Path(directory)/('output.'+kind)
                callback = (lambda n,label,i=index:progress((i+n/100)*100/len(MODES),label)) if progress else None
                size = export(scene,file,kind,width,dpi,transparent,box,labels,facilities,
                              protection,scale_bar,callback,board_enlarged,key)
                archive.write(file,export_filename(project_name,key,size,kind))
        return size
    if mode=='F8':
        import chart_f8 as chart
        regular=sr.display_list(scene) if chart.settings(scene).get('visible',{}).get('MARKING') else ()
        items,kinds=chart.chart_items(scene,regular)
        region=box or chart.saved_region(scene,items)
        config=chart.settings(scene).get('page',{})
        region=chart.adjust_region(region,config)
        box=chart.page_box(region,config)
        size=dimensions(box,width)
        items=chart.page_items(scene,items,kinds,region,box)
        box=chart.center_page_vertically(box,items)
        items=list(chart.pixel_items(items,width/(box[2]-box[0]),width/1000))
        animated=[]
        background='#ffffff'
        scale_bar=False
    else:
        items=sr.display_list(scene,labels,facilities,protection,board_enlarged=board_enlarged)
        items,animated = mode_items(scene,mode,items)
        box=box or mode_extent(scene,items);size=dimensions(box,width)
        background = '#101922' if mode=='F7' else sr.COLORS['background']
    if not 36<=dpi<=1200:raise ValueError('DPI应为36～1200')
    if progress:progress(5,'计算机场几何')
    scale=size[0]/(box[2]-box[0]);origin=[-box[0]*scale,box[3]*scale]
    for item in items:
        if item.get('screen_line'):
            item['width'] = 1/scale
        if 'lamp_center' in item:
            x,y = item['lamp_center']
            radius = item['lamp_radius']
            factor = min(12.,max(2.,radius*scale))/(radius*scale)
            item['points'] = [[x+(qx-x)*factor,y+(qy-y)*factor] for qx,qy in item['points']]
    if scale_bar:
        from layout14 import nice_length
        length,_=nice_length(scale);x=box[0]+20/scale;y=box[1]+30/scale
        for unit,factor,dy in [('m',1,0),('ft',.3048,20/scale)]:
            n,_=nice_length(scale,factor);end=x+n*factor
            items.append(dict(type='line',oid='EXPORT_SCALE',points=[[x,y+dy],[end,y+dy]],stroke='#29495c',width=2/scale))
            items.append(dict(type='text',oid='EXPORT_SCALE',points=[[(x+end)/2,y+dy+8/scale]],text=f'{n:g} {unit}',fill='#29495c',size=10/scale,rotation=0,world_text=True))
    if progress:progress(25,'绘制图面')
    if kind in ('psd','pdf','pptx'):
        from layered_export21 import write
        write(path,kind,items,size,origin,scale,None if transparent else background,dpi,progress)
    elif kind=='png':
        image=sr.draw_items(items,size,origin,scale,(0,0,0,0) if transparent else background,progress=(lambda value:progress(25+value*60,'绘制图面')) if progress else None)
        if progress:progress(90,'编码PNG文件')
        image.save(path,'PNG',dpi=(dpi,dpi));image.close()
    elif kind=='gif':
        from PIL import ImageDraw
        frame_count = 100 if animated else 1
        if size[0]*size[1]*frame_count > 120_000_000:
            raise ValueError('GIF 画面过大，请降低导出宽度或缩小范围')
        dynamic = {id(item) for item,*_ in animated}
        image = sr.draw_items([item for item in items if id(item) not in dynamic],size,origin,scale,background).convert('RGB')
        frames = []
        for index in range(frame_count):
            frame = image.copy()
            draw = ImageDraw.Draw(frame)
            now = index*.02
            for item,fixture,phase,count,config in animated:
                slot = min(count-1,int((now%.5)*2*count)) if fixture=='flash' else int(now*(31 if config=='GUARD_B' else 48)/30)%2
                if slot==phase:
                    draw.polygon([(origin[0]+x*scale,origin[1]-y*scale) for x,y in item['points']],fill=item['fill'])
            frames.append(frame.quantize())
            frame.close()
            if progress:progress(25+60*(index+1)/frame_count,'生成 GIF 帧')
        frames[0].save(path,format='GIF',save_all=True,append_images=frames[1:],duration=20,loop=0)
        for frame in frames:
            frame.close()
        image.close()
    elif kind=='svg':
        from html import escape
        x0,y0,x1,y1=box;parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {x1-x0} {y1-y0}">','<metadata>'+escape(json.dumps(dict(software='Airport Canvas',dpi=dpi,units='m')))+'</metadata>']
        if not transparent:parts.append(f'<rect width="100%" height="100%" fill="{background}"/>')
        for e in items:
            if e['type']=='text':
                x,y=e['points'][0]
                angle=-e.get('rotation',0)
                transform=f' transform="rotate({angle} {x-x0} {y1-y})"' if angle else ''
                length=f' textLength="{e["text_width"]}" lengthAdjust="spacingAndGlyphs"' if e.get('text_width') else ''
                outline=' stroke="#101010" stroke-width=".1" paint-order="stroke fill"' if e.get('black_outline') else ''
                family={'caac':'CAAC Runway Code','stencil':'Allerta Stencil','hei':'SimHei'}.get(e.get('font'),'Microsoft YaHei UI')
                parts.append(f'<text x="{x-x0}" y="{y1-y}"{transform}{length}{outline} text-anchor="middle" dominant-baseline="central" font-family="{family}, sans-serif" font-size="{e["size"]}" fill="{e["fill"]}">{escape(e["text"])}</text>')
                continue
            coords=' '.join(f'{x-x0:.5f},{y1-y:.5f}' for x,y in e['points']);tag='polygon' if e['type']=='polygon' else 'polyline';dash=' stroke-dasharray="'+','.join(map(str,e['dash']))+'" stroke-dashoffset="'+str(e.get('dash_offset',0))+'"' if e.get('dash') else ''
            parts.append(f'<{tag} points="{coords}" fill="{e.get("fill") or "none"}" stroke="{e.get("stroke") or "none"}" stroke-width="{e.get("width",.15)}" stroke-linejoin="round"{dash}/>')
        parts.append('</svg>');Path(path).write_text('\n'.join(parts),encoding='utf8')
    else:raise ValueError('未知导出格式')
    if progress:progress(100,'导出完成')
    return size


def mode_extent(scene,items):
    box = extent_with_boards(scene,items)
    points = [point for item in items for point in item['points']]
    if not points:
        return box
    x,y = zip(*points)
    return min(box[0],min(x)-2),min(box[1],min(y)-2),max(box[2],max(x)+2),max(box[3],max(y)+2)


def export_filename(project_name,mode,size,kind):
    import re
    from export_modes21 import MODES
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(project_name)).strip(' .') or '机场项目'
    return f'{name}_{MODES[mode]}.{kind}' if kind=='svg' else f'{name}_{MODES[mode]}_{size[0]}x{size[1]}.{kind}'
