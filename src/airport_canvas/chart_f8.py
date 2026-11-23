"""Simulation parking chart geometry and page composition."""
from interface_language import tr
import math
import textwrap

import scene_geometry as g

DISCLAIMER = 'Air Canvas生成模拟航图，仅供学习，不用于任何实际导航使用'
# Dominant colors sampled from the supplied ZSQD parking chart.
TYPES = {
    'RUNWAY': ('跑道', '#4d4d4d', '#4d4d4d'),
    'STOPWAY': ('停止道', '#4d4d4d', '#cccccc'),
    'TAXIWAY': ('滑行道', '#cccccc', '#cccccc'),
    'APRON': ('机坪', '#cccccc', '#cccccc'),
    'STAND': ('机位', '#262626', '#cccccc'),
    'OTHER': ('建筑', '#808080', '#808080'),
    'TERMINAL': ('航站楼', '#808080', '#808080'),
    'PIER': ('指廊', '#808080', '#808080'),
    'BRIDGE': ('廊桥', '#262626', '#fcfcfc'),
    'ROAD': ('服务车道', '#808080', '#fcfcfc'),
    'RUNWAY_SHOULDER': ('跑道道肩', '#aaaaaa', '#eeeeee'),
    'TAXI_SHOULDER': ('滑行道道肩', '#cccccc', '#fcfcfc'),
    'EQUIPMENT': ('设备', '#262626', '#fcfcfc'),
    'PROTECTION': ('保护区', '#808080', '#fcfcfc'),
    'CLOSED_AREA': ('关闭区域', '#aa2525', '#fcfcfc'),
    'MARKING': ('其他标线', '#262626', '#fcfcfc'),
    'ARP': ('机场基准点', '#ffffff', None),
    'WIND': ('风向标', '#262626', '#ffffff'),
    'TOWER': ('控制塔','#262626',None),
    'VOR': ('VOR','#262626',None),
    'NDB': ('NDB','#262626',None),
    'DME': ('DME','#262626',None),
    'AIM': ('瞄准点','#262626',None),
    'DISPLACED': ('内移入口','#262626','#ffffff'),
    'ELEV': ('跑道端海拔','#262626',None),
    'PAPI': ('PAPI','#262626',None),
    'HS': ('热点', '#e6780a', '#ffffff'),
}
DEFAULT_VISIBLE = set(list(TYPES)[:9])
SYMBOLS = ('ARP','WIND','HS','TOWER','VOR','NDB','DME')
NAV_SYMBOLS = ('TOWER','VOR','NDB','DME')
HOTSPOTS = {'rounded_polygon':'自动圆角多边形','polygon':'普通多边形','rectangle':'矩形','rounded_rectangle':'圆角矩形','circle':'圆形'}
UNITS = {'m':1, 'ft':1/.3048, 'km':.001}
FIELDS = (
    ('ident','机场四字代码'), ('airport','机场名称'), ('atis','D-ATIS'),
    ('tower','TWR'), ('ground','GND'), ('delivery','CLR'),
    ('chart_no','航图编号'), ('edition','生效编号'), ('date','生效日期'),
    ('changes','变更内容'),
)


def settings(scene):
    return scene.data['meta'].get('chart_f8', {})


def line(oid, points, color, width=.3, dash=None):
    return dict(oid=oid, type='line', points=list(points), stroke=color, width=width, dash=dash)


def polygon(oid, points, stroke, fill):
    return dict(oid=oid, type='polygon', points=list(points), stroke=stroke, fill=fill, width=.3)


def label(oid, point, text, size=11, color='#262626', dx=0, dy=0):
    return dict(oid=oid, type='text', points=[point], text=str(text), fill=color,
                chart_px=size, chart_offset=(dx,dy), rotation=0, world_text=True)


def category(asset):
    role=asset['props'].get('building_role19')
    if role in ('OTHER','TERMINAL','PIER','BRIDGE'):
        return role
    kind=asset['kind']
    return 'TAXIWAY' if kind in ('APRON_TAXIWAY','STAND_TAXILANE','CONNECTOR','FILLET') else kind


def colors(config, kind, oid=None):
    _,stroke,fill=TYPES[kind]
    base=config.get('palette',{}).get(kind,{})
    style=config.get('objects',{}).get(oid,{})
    legacy=config.get('palette',{}).get('SHOULDER',{}) if kind.endswith('_SHOULDER') else {}
    return style.get('stroke',base.get('stroke',legacy.get('stroke',stroke))),None if kind=='ARP' else style.get('fill',base.get('fill',legacy.get('fill',fill)))


def runway_end_center(scene):
    endpoints=[point for asset in scene.assets.values() if asset['kind']=='RUNWAY'
               for point in (asset['points'][0],asset['points'][-1])]
    if not endpoints:return None
    return [sum(axis)/len(axis) for axis in zip(*endpoints)]


def symbol_point(scene, item):
    if item.get('auto_runway_center'):
        return runway_end_center(scene) or item['point']
    runway=scene.assets.get(item.get('runway'))
    if runway and runway['kind']=='RUNWAY':
        return g.at(runway['points'],g.length(runway['points'])/2)[0]
    return item['point']


def shoulder_kind(piece):
    return 'RUNWAY_SHOULDER' if piece['kind']=='RUNWAY' else 'TAXI_SHOULDER'


def is_visible(config,kind):
    fallback=config.get('visible',{}).get('SHOULDER',False) if kind.endswith('_SHOULDER') else kind in DEFAULT_VISIBLE or kind in SYMBOLS or kind in ('PAPI','AIM','DISPLACED','ELEV')
    return config.get('visible',{}).get(kind,fallback)


def hotspot_path(mode,points):
    if mode in ('polygon','rounded_polygon'):
        if len(points)<3:return points
        vertices=points
    else:
        if len(points)<2:return points
        a,b=points[0],points[-1]
        if mode=='circle':
            radius=math.dist(a,b)
            ring=[(a[0]+radius*math.cos(i*math.tau/64),a[1]+radius*math.sin(i*math.tau/64)) for i in range(64)]
            return [*ring,ring[0]]
        vertices=[a,(b[0],a[1]),b,(a[0],b[1])]
    if mode in ('polygon','rectangle'):
        return [*vertices,vertices[0]]
    result=[]
    for i,b in enumerate(vertices):
        a,c=vertices[i-1],vertices[(i+1)%len(vertices)]
        ratio=min(.20,min(math.dist(a,b),math.dist(c,b))/max(.001,math.dist(a,b))* .22)
        u=[b[k]+(a[k]-b[k])*ratio for k in (0,1)]
        ratio=min(.20,min(math.dist(a,b),math.dist(c,b))/max(.001,math.dist(c,b))* .22)
        v=[b[k]+(c[k]-b[k])*ratio for k in (0,1)]
        for j in range(9):
            t=j/8
            result.append(tuple((1-t)**2*u[k]+2*t*(1-t)*b[k]+t*t*v[k] for k in (0,1)))
    return [*result,result[0]]


def present_types(scene):
    from project10 import stopway_axes
    from scene_render import surface_geometry
    result={category(asset) for asset in scene.assets.values()}
    surfaces=surface_geometry(scene)
    result.update(shoulder_kind(piece) for piece in surfaces['shoulders'])
    if any(surfaces['pavement']):
        result.update(category(dict(kind=piece['kind'],props={})) for piece in surfaces['pavement'])
    if any(any(stopway_axes(asset)) for asset in scene.assets.values() if asset['kind']=='RUNWAY'):
        result.add('STOPWAY')
    from papi21 import rows as papi_rows
    if any(papi_rows(scene)):result.add('PAPI')
    result.update(item['kind'] for item in settings(scene).get('symbols',{}).values())
    return result


def runway_normal(u):
    side=-1 if -u[1]>0 or abs(u[1])<1e-8 and u[0]<0 else 1
    return -u[1]*side,u[0]*side


def runway_side_label(oid,origin,text,u,normal,edge,obstacles,clearance):
    from shapely.geometry import Polygon
    x,y=origin
    nx,ny=normal
    ax,ay=u
    half_length=clearance*max(1.35,len(text)*.44)
    half_width=clearance*.65
    # Search outwards from the edge. Try along-axis displacements only when
    # they put the caption closer to its symbol than a further outward move.
    candidates=sorted((math.hypot(along,distance+edge),abs(along),along,distance)
                      for along in [0,*[sign*clearance*k for k in range(1,11) for sign in (-1,1)]]
                      for distance in [clearance*(1.1+k) for k in range(22)])
    for _,_,along,distance in candidates:
        point=(x+ax*along+nx*(edge+distance),y+ay*along+ny*(edge+distance))
        footprint=Polygon([(point[0]+a*ax+b*nx,point[1]+a*ay+b*ny)
                           for a,b in [(-half_length,-half_width),(half_length,-half_width),
                                       (half_length,half_width),(-half_length,half_width)]])
        if not obstacles.intersects(footprint):break
    else:
        if not obstacles.is_empty:
            x0,y0,x1,y1=obstacles.bounds
            distance=max((a-x)*nx+(b-y)*ny for a in (x0,x1) for b in (y0,y1))+clearance*1.5
            point=(x+distance*nx,y+distance*ny)
    theta=math.atan2(ay,ax)
    return dict(label(oid,point,text,10,'#000000'),rotation=(math.degrees(theta)+90)%180-90,
                axis_angle=theta,normal=normal,chart_normal_px=0)


def hotspot_label_pose(row,half_width,half_height,symbol_radius,units_per_pixel=None):
    from shapely.geometry import Point, Polygon, box
    from shapely.ops import nearest_points
    x,y=row['points'][0]
    paved=row['chart_pavement']
    from map_painter import text_sprite
    label_boxes=[]
    for text in row.get('chart_terminal_labels',()):
        factor=units_per_pixel if units_per_pixel is not None else symbol_radius/9
        sprite=text_sprite(text['text'],text['fill'],100)
        h=text['chart_px']*factor
        w=h*sprite.width/sprite.height
        px,py=text['points'][0]
        dx,dy=text['chart_offset']
        px+=dx*factor
        py-=dy*factor
        label_boxes.append(box(px-w/2-factor*2,py-h/2-factor*2,px+w/2+factor*2,py+h/2+factor*2))
    boundary=row.get('chart_hotspot_boundary')
    hotspot=Polygon(boundary.coords) if boundary is not None else Point(x,y).buffer(symbol_radius)
    step=max(half_width,half_height)*1.15
    candidates=[(x+math.sin(i*math.tau/16)*step*k,y+math.cos(i*math.tau/16)*step*k)
                for k in range(1,33) for i in range(16)]
    for qx,qy in candidates:
        footprint=box(qx-half_width,qy-half_height,qx+half_width,qy+half_height)
        if not paved.intersects(footprint) and not hotspot.intersects(footprint) and not any(b.intersects(footprint) for b in label_boxes):
            break
    else:
        top=max(hotspot.bounds[3],paved.bounds[3] if not paved.is_empty else y)
        qx,qy=x,max(y,top,*(b.bounds[3] for b in label_boxes))+half_height+step
    if boundary is not None:
        edge=nearest_points(boundary,Point(qx,qy))[0]
        start=(edge.x,edge.y)
    else:
        distance=max(.001,math.hypot(qx-x,qy-y))
        start=(x+(qx-x)*symbol_radius/distance,y+(qy-y)*symbol_radius/distance)
    return (qx,qy),start


def box_edge(center,target,half_width,half_height):
    dx,dy=target[0]-center[0],target[1]-center[1]
    ratio=1/max(abs(dx)/half_width,abs(dy)/half_height,1.)
    return center[0]+dx*ratio,center[1]+dy*ratio


CLOSURE_RED = '#bd252c'
CLOSURE_LABEL = '关闭道面'
CLOSURE_NOTES = {
    'red': '红色中线表示关闭道面。',
    'cross': '与道面同色的一串 × 表示关闭道面。',
}


def closure_style(config):
    return 'cross' if config.get('closure',{}).get('style')=='cross' else 'red'


def closure_marks(points, span):
    length=g.length(points)
    count=max(1,math.ceil(length/max(15,span*4)))
    size=min(span*.35,length/(4*count))
    for i in range(count):
        (x,y),(ux,uy)=g.at(points,length*(i+.5)/count)
        for sign in (-1,1):
            dx,dy=(ux-sign*uy)*size,(uy+sign*ux)*size
            yield [(x-dx,y-dy),(x+dx,y+dy)]


def chart_items(scene, regular=None):
    from model20 import axes
    from project10 import stopway_axes
    from scene_render import surface_geometry
    from stand_profiles import lead_design, safety_profile

    from marking_standards import closure_routes
    if regular is None:
        from scene_render import display_list
        regular=display_list(scene)
    config=settings(scene)
    closed_assets,closed=closure_routes(scene)
    use_cross=closure_style(config)=='cross'
    guides=regular
    if closed or not regular:
        from scene_render import display_list
        guides=display_list(scene,chart_guides=True)
    from pavement_geometry import crossings
    junction_owners={j['id']:j['assets'] for j in crossings(scene)} if closed and use_cross else {}
    axes_map=axes(scene)
    assets={**scene.assets,**axes_map}
    hidden=scene.data['meta'].get('object_display',{})
    rows=[]
    kinds=set()
    def show(kind,oid):
        return kind in TYPES and is_visible(config,kind) and not hidden.get(oid,{}).get('hidden')
    def add(kind,item):
        kinds.add(kind)
        rows.append(item)
    surfaces=surface_geometry(scene)
    physical_points=[point for piece in surfaces['pavement'] for point in piece['points']]
    extent=max((max(axis)-min(axis) for axis in zip(*physical_points)),default=1000)
    stand_size=max(3.,min(24.,extent*.006))
    from geometry11 import polygon as shape_polygon, unary_union
    obstacles={}
    def paved(all_pavement=False):
        if all_pavement not in obstacles:
            pieces=[shape_polygon(p['points']) for band in (('pavement','shoulders') if all_pavement else ('pavement',)) for p in surfaces[band] if all_pavement or show(category(
                assets.get(p['oid'],dict(kind=p['kind'],props={}))),p['oid'])]
            pieces.extend(shape_polygon(g.rectangle([outside,origin],asset['props']['width']))
                          for asset in scene.assets.values() if asset['kind']=='RUNWAY' and (all_pavement or show('STOPWAY',asset['id']))
                          for _,outside,origin,_ in stopway_axes(asset))
            if all_pavement:
                pieces.extend(shape_polygon(row['points']) for row in rows
                              if row['type']=='polygon' and row.get('chart_terminal'))
            obstacles[all_pavement]=unary_union(pieces)
        return obstacles[all_pavement]
    clearance=max(3.,min(22.,extent*.005))
    for band in ('shoulders','pavement'):
        for piece in surfaces[band]:
            oid=piece['oid']
            owner=oid if oid in assets else oid.split(':')[0]
            if use_cross and (owner in closed or any(aid in closed for aid in
                              junction_owners.get(oid.removesuffix(':core'),()))):
                continue
            asset=assets.get(owner)
            kind=shoulder_kind(piece) if band=='shoulders' else category(asset) if asset else category({'kind':piece['kind'],'props':{}})
            if show(kind,owner):
                oid=f'{owner}:shoulder:{kind}' if band=='shoulders' else owner
                stroke,fill=colors(config,kind,oid)
                add(kind,dict(polygon(oid,piece['points'],stroke,fill),chart_kind=kind))
    for aid,asset in assets.items():
        kind=category(asset)
        props=asset['props']
        points=asset['points']
        if kind=='RUNWAY' and show('STOPWAY',aid) and not (use_cross and aid in closed):
            for end,outside,origin,_ in stopway_axes(asset):
                oid=f'{aid}:stopway:{end}'
                add('STOPWAY',polygon(oid,g.rectangle([outside,origin],props['width']),*colors(config,'STOPWAY',oid)))
        if not show(kind,aid):
            continue
        stroke,fill=colors(config,kind,aid)
        if kind in ('OTHER','TERMINAL','PIER','BRIDGE','PROTECTION','CLOSED_AREA','EQUIPMENT'):
            if len(points)>=3:
                add(kind,dict(polygon(aid,points,stroke,fill),chart_terminal=kind in ('TERMINAL','PIER','BRIDGE')))
            elif len(points)==2:
                add(kind,line(aid,points,stroke,width=1))
        if kind=='STAND':
            if fill!=TYPES[kind][2] or 'fill' in config.get('objects',{}).get(aid,{}):
                envelope=safety_profile(scene,asset)
                if len(envelope)>=3:add(kind,polygon(aid,envelope,None,fill))
            for guide in lead_design(asset,scene)['paths']:
                add(kind,line(aid,guide['points'],stroke,dash=[2,1.5]))
            if props.get('remote_stand'):
                from stand15 import remote_exit_lines
                for path in remote_exit_lines(asset,scene):
                    add(kind,line(aid,path,stroke,dash=[2,1.5]))
        if kind=='RUNWAY':
            length=g.length(points)
            midpoint,u=g.at(points,length/2)
            nx,ny=runway_normal(u)
            offset=props['width']/2
            anchor=[midpoint[0]+nx*offset,midpoint[1]+ny*offset]
            unit=config.get('units',{}).get(aid,'m')
            if unit not in UNITS:unit='m'
            decimals=2 if unit=='km' else 0
            angle=(math.degrees(math.atan2(u[1],u[0]))+90)%180-90
            suffix='' if unit=='m' else f' {unit}'
            material=config.get('surfaces',{}).get(aid,'')
            dimensions=f"{length*UNITS[unit]:.{decimals}f}×{props['width']*UNITS[unit]:.{decimals}f}{suffix}"
            if material in SURFACES and material:dimensions+=' '+material
            add(kind,dict(label(aid,anchor,dimensions,12,dx=nx*12,dy=-ny*12),
                          rotation=angle,axis_angle=math.atan2(u[1],u[0]),normal=(nx,ny)))
            for side,point in zip('ab',(points[0],points[-1])):
                designation=props.get('label_'+side)
                if designation:
                    row=runway_side_label(aid,point,designation,u,(nx,ny),offset,paved(),clearance*1.5)
                    row.update(rotation=(angle+180)%180-90,angle_delta=90,
                               runway_end=side,runway_axis=points)
                    add(kind,row)
        elif kind in ('TAXIWAY','STAND','TERMINAL'):
            point=points[-1] if kind=='STAND' else g.at(points,g.length(points)/2)[0]
            name=props.get('stand_number') or props.get('designation') or ('TML' if kind=='TERMINAL' else asset['name'])
            row=label(aid,point,name,10,dy=-7)
            if kind=='STAND':
                row.update(chart_world_size=stand_size,chart_offset=(0,0),
                           points=[(point[0],point[1]+stand_size*.75)])
            if kind=='TERMINAL':row['chart_terminal']=True
            add(kind,row)
    for item in guides:
        owners=item.get('chart_taxi_owners',())
        taxi_owners=[oid for oid in owners if oid in assets and category(assets[oid])=='TAXIWAY']
        if (item['type']!='line' or not taxi_owners or item.get('black_underlay')
                or not all(show('TAXIWAY',oid) for oid in taxi_owners)):
            continue
        closed_owner=next((oid for oid in owners if oid in closed),None)
        if closed_owner is None:
            add('TAXIWAY',line(taxi_owners[0],item['points'],'#000000',width=.45))
        elif use_cross:
            asset=assets[closed_owner]
            span=asset['props'].get('width',15)
            stroke,fill=colors(config,category(asset),closed_owner)
            for mark in closure_marks(item['points'],span):
                add('CLOSURE',line(taxi_owners[0],mark,fill or stroke,width=1.2))
        else:
            add('CLOSURE',line(taxi_owners[0],item['points'],CLOSURE_RED,width=.45))
    for oid in sorted(closed):
        asset=closed_assets.get(oid)
        if not asset:continue
        kind=category(asset)
        if kind not in ('RUNWAY','APRON','ROAD') or not show(kind,oid):continue
        points=asset['points']
        span=asset['props'].get('width',15)
        if kind=='APRON':
            from shapely.geometry import LineString
            from geometry11 import lines
            area=shape_polygon(points)
            x0,y0,x1,y1=area.bounds
            x,y=area.representative_point().coords[0]
            axis=[(x0,y),(x1,y)] if x1-x0>=y1-y0 else [(x,y0),(x,y1)]
            paths=[list(part.coords) for part in lines(area.intersection(LineString(axis)))]
            span=min(x1-x0,y1-y0)
        else:
            paths=[points]
        color=(colors(config,kind,oid)[1] or colors(config,kind,oid)[0]) if use_cross else CLOSURE_RED
        for path in paths:
            if g.length(path)<=0:continue
            marks=closure_marks(path,span) if use_cross else [path]
            for mark in marks:
                rows.append(line(oid,mark,color,width=1.2))
                kinds.add('CLOSURE')
    if show('MARKING',''):
        for item in regular:
            if item.get('oid') in scene.assets and scene.assets[item['oid']]['kind']=='MARKING' and show('MARKING',item['oid']):
                add('MARKING',item.copy())
    from papi21 import rows as papi_rows
    for runway,end,lamps,_ in papi_rows(scene):
        if show('PAPI',runway['id']):
            ink,_=colors(config,'PAPI',runway['id'])
            center=tuple((a+b)/2 for a,b in zip(lamps[0],lamps[-1]))
            add('PAPI',dict(label(runway['id'],center,'',13,ink),chart_symbol='PAPI',symbol_fill=None))
    terminal_labels=[row for row in rows if row['type']=='text' and row.get('chart_terminal')]
    for oid,item in config.get('symbols',{}).items():
        kind=item['kind']
        if kind not in NAV_SYMBOLS and show(kind,oid):
            point=symbol_point(scene,item)
            stroke,_=colors(config,kind,oid)
            fill=colors(config,kind,oid)[1]
            runway=arp_runway(scene,point,item.get('runway')) if kind=='ARP' else None
            if kind=='ARP' and runway is None:stroke='#000000'
            if kind=='HS' and item.get('vertices'):
                path=hotspot_path(item.get('shape','polygon'),item['vertices'])
                add(kind,dict(line(oid,path,stroke),screen_line=True,cosmetic_pen=True,chart_kind=kind))
                point=max(path,key=lambda p:p[1])
            else:
                symbol=dict(label(oid,point,'',19,stroke),chart_symbol=kind,symbol_fill=fill)
                if runway is not None:symbol['chart_symbol_max']=arp_diameter(runway,point)
                add(kind,symbol)
            row=label(oid,point,item.get('label',kind),10,'#000000' if kind=='ARP' else stroke,dy=-16)
            if runway is not None:
                _,station,axis_point=g.project(runway['points'],point)
                _,u=g.at(runway['points'],station)
                nx,ny=runway_normal(u)
                side_offset=(point[0]-axis_point[0])*nx+(point[1]-axis_point[1])*ny
                edge=max(0,runway['props']['width']/2+side_offset)
                row=runway_side_label(oid,point,item.get('label','ARP'),u,(-nx,-ny),edge,paved(),clearance)
            if kind=='HS':
                from shapely.geometry import LineString
                row.update(chart_box=stroke,chart_pavement=paved(True),chart_terminal_labels=terminal_labels)
                if item.get('vertices'):row['chart_hotspot_boundary']=LineString(path)
            add(kind,row)
    from shapely.geometry import box
    from automatic_markings import runway_components
    occupied=[]
    text_footprints=[]
    def reserve(item):
        x,y=item['points'][0]
        unit=max(1,extent/1100)
        w=max(8,len(item.get('text',''))*4)*unit
        h=9*unit
        dx,dy=item.get('chart_offset',(0,0))
        footprint=box(x+dx*unit-w,y-dy*unit-h,x+dx*unit+w,y-dy*unit+h)
        occupied.append(footprint)
        if item.get('text'):text_footprints.append(footprint)
    for item in rows:
        if item['type']=='text':reserve(item)
    pavement=paved(True)
    def clear_position(origin,direction,half_width,half_height):
        for step in range(1,161):
            x,y=(origin[i]+direction[i]*step*clearance for i in (0,1))
            footprint=box(x-half_width,y-half_height,x+half_width,y+half_height)
            if not pavement.intersects(footprint) and not any(r.intersects(footprint) for r in occupied):
                occupied.append(footprint)
                return x,y
        return None

    for oid,item in config.get('symbols',{}).items():
        kind=item['kind']
        if kind not in NAV_SYMBOLS or not show(kind,oid):continue
        origin=symbol_point(scene,item)
        caption=item.get('label',kind)
        size=max(clearance,extent*.018)
        if kind=='TOWER' or item.get('manual_position'):
            point=origin
            caption_point=clear_position(origin,(0,-1),
                                         max(clearance,len(caption)*extent/220),clearance)
        else:
            point=clear_position((origin[0],origin[1]+clearance),(0,-1),
                                 max(size,len(caption)*extent/220),size*1.5)
            caption_point=point
            if point is None:point=origin
        if point:
            ink=colors(config,kind,oid)[0]
            add(kind,dict(label(oid,point,'',19,ink),chart_symbol=kind,
                          symbol_variant=item.get('variant'),symbol_fill=None,chart_symbol_max=size))
            if caption_point is not None:
                row=label(oid,caption_point,caption,10,ink,dy=0 if kind=='TOWER' or item.get('manual_position') else -16)
                add(kind,row)
                reserve(row)

    runway_pavement=unary_union(shape_polygon(g.rectangle(a['points'],a['props']['width']))
                                for a in scene.assets.values()
                                if a['kind']=='RUNWAY' and show('RUNWAY',a['id']))

    def elevation_position(threshold,direction,width,displaced,text):
        unit=max(1,extent/1100)
        half_width=max(8,len(text)*4)*unit
        half_height=9*unit
        normal=runway_normal(direction)
        routes=[(normal,width/2),((-normal[0],-normal[1]),width/2)]
        if not displaced:routes.insert(0,(direction,0.))
        steps=[]
        for priority,((ux,uy),edge) in enumerate(routes):
            initial=edge+abs(ux)*half_width+abs(uy)*half_height+unit
            steps.extend((initial+step*unit,priority,ux,uy) for step in range(160))
        # At an intersecting runway both lateral rays can stay blocked.
        # Search diagonally as a fallback while keeping the threshold as origin.
        if displaced:
            for lateral in (normal,(-normal[0],-normal[1])):
                for sign in (1,-1):
                    ux,uy=(2**-.5*(n+sign*d) for n,d in zip(lateral,direction))
                    initial=width/2+abs(ux)*half_width+abs(uy)*half_height+unit
                    steps.extend((initial+step*unit,2,ux,uy) for step in range(160))
        for distance,_,ux,uy in sorted(steps):
            x=threshold[0]+ux*distance
            y=threshold[1]+uy*distance
            footprint=box(x-half_width,y-half_height,x+half_width,y+half_height)
            if not runway_pavement.intersects(footprint) and not any(
                    obstacle.intersects(footprint) for obstacle in text_footprints):
                return x,y
        return None
    for oid,runway in scene.assets.items():
        if runway['kind']!='RUNWAY' or not show('RUNWAY',oid):continue
        props=runway['props']
        axis=g.unit(*runway['points'])
        width=props['width']
        for mark in runway_components(runway).values():
            key=mark['props']['mark_type']
            if key=='THRESHOLD_BAR' and show('DISPLACED',oid) and not (use_cross and oid in closed):
                a,b=mark['points']
                center=[(x+y)/2 for x,y in zip(a,b)]
                normal=(-axis[1],axis[0])
                half_depth=max(3.,width*.09)
                rectangle=[[center[i]+axis[i]*x+normal[i]*y for i in (0,1)]
                           for x,y in ((-half_depth,-width*.55),(half_depth,-width*.55),
                                       (half_depth,width*.55),(-half_depth,width*.55))]
                add('DISPLACED',polygon(oid,rectangle,*colors(config,'DISPLACED',oid)))
            elif key=='AIMING_POINT' and show('AIM',oid):
                origin,toward=mark['points']
                u=g.unit(origin,toward)
                normal=(-u[1],u[0])
                center=[origin[i]+u[i]*mark['props']['aim_length']/2 for i in (0,1)]
                edge=[center[i]+normal[i]*width/2 for i in (0,1)]
                point=clear_position(edge,normal,clearance,clearance)
                if point:
                    add('AIM',dict(label(oid,point,'',16,colors(config,'AIM',oid)[0]),
                                   chart_symbol='AIM',symbol_fill=None,chart_symbol_max=clearance*2))
        for end,point in zip('ab',(runway['points'][0],runway['points'][-1])):
            if not show('ELEV',oid):continue
            elevation=props.get('elevation_'+end)
            if elevation is None:elevation=scene.data['meta'].get('airport_elevation') or 0
            unit=props.get('elevation_unit','m')
            if unit not in ('m','ft'):unit='m'
            value=f"ELEV {elevation*UNITS[unit]:.0f}"+(' ft' if unit=='ft' else '')
            direction=(-axis[0],-axis[1]) if end=='a' else axis
            displacement=min(g.length(runway['points']),props.get('displaced_'+end,0) or 0)
            threshold=[point[i]-direction[i]*displacement for i in (0,1)]
            location=elevation_position(threshold,direction,width,displacement>0,value)
            if location:
                row=label(oid,location,value,10,colors(config,'ELEV',oid)[0])
                row['elevation_end']=end
                add('ELEV',row)
                reserve(row)
    # Draw the labels above all pavement and structural geometry.
    return [item for item in rows if item['type']!='text']+[item for item in rows if item['type']=='text'],kinds


def chart_extent(items):
    points=[point for item in items for point in item['points']]
    if not points:return (-50.,-50.,50.,50.)
    x,y=zip(*points)
    return min(x),min(y),max(x),max(y)


def fit_extent(items):
    x0,y0,x1,y1=chart_extent(items)
    pad=max(1.,max(x1-x0,y1-y0)*.025)
    return x0-pad,y0-pad,x1+pad,y1+pad


def arp_runway(scene,point,binding=None):
    def lateral_distance(runway):
        start,end=runway['points']
        ux,uy=g.unit(start,end)
        x,y=point[0]-start[0],point[1]-start[1]
        station=x*ux+y*uy
        lateral=abs(y*ux-x*uy)
        if (-1e-8<=station<=g.distance(start,end)+1e-8
                and lateral<=runway['props']['width']/2+1e-8):
            return lateral
        return None

    bound=scene.assets.get(binding)
    if bound and bound['kind']=='RUNWAY' and lateral_distance(bound) is not None:
        return bound
    matches=((distance,a) for a in scene.assets.values() if a['kind']=='RUNWAY'
             and (distance:=lateral_distance(a)) is not None)
    return min(matches,key=lambda pair:pair[0],default=(None,None))[1]

def arp_diameter(runway,point):
    lateral=g.project(runway['points'],point)[0]
    return max(0.,runway['props']['width']-2*lateral)*.92


def symbol_scale(item,zoom,pixel_factor=1.):
    diameter=item.get('chart_symbol_max')
    return pixel_factor if diameter is None else min(pixel_factor,diameter*zoom/20)


def symbol_parts(kind,variant=None):
    ring=[(9*math.cos(i*math.tau/32),9*math.sin(i*math.tau/32)) for i in range(32)]
    if kind=='AIM':
        return [('polygon',[(0,-9),(8,6),(-8,6)])]
    if kind=='TOWER':
        if variant=='tower':
            return [('polygon',[(-8,-8),(8,-8),(5,-2),(-5,-2)]),
                    ('line',[(-3,-2),(-5,9),(5,9),(3,-2)])]
        return [('polygon',[(r*math.sin(i*math.pi/5),-r*math.cos(i*math.pi/5))
                            for i,r in enumerate((9,4)*5)])]
    if kind in ('VOR','DME','NDB'):
        def dot(x,y):
            return 'polygon',[(x+math.cos(i*math.tau/8),y+math.sin(i*math.tau/8)) for i in range(8)]
        if kind=='NDB':
            return [dot(0,0)]+[dot(r*math.cos(i*math.tau/count),r*math.sin(i*math.tau/count))
                               for r,count in ((4,8),(8,14)) for i in range(count)]
        outer=[(9*math.cos(i*math.tau/6),9*math.sin(i*math.tau/6)) for i in range(6)] if kind=='VOR' else [(-8,-8),(8,-8),(8,8),(-8,8)]
        return [('polygon',outer),dot(0,0)]
    if kind=='PAPI':
        return [('polygon',ring),('line',[(-2.5,4.5),(-2.5,-4.5)]),
                ('line',[(-2.5,-4.5),(1,-4.5),(3,-3),(3,-1),(1,.5),(-2.5,.5)])]
    if kind=='HS':
        return [('polygon',ring)]
    if kind=='ARP':
        return [('polygon',ring),('line',[(-9,0),(9,0)]),('line',[(0,-9),(0,9)])]
    return [('line',[(-5,8),(-5,-9)]),('polygon',[(-5,-9),(8,-4),(8,0),(-5,0)])]


def pixel_items(items,scale,pixel_factor=1):
    for item in items:
        row=item.copy()
        if row.get('screen_line'):row['width']=1.5*pixel_factor/scale
        if 'chart_px' in row:
            x,y=row['points'][0]
            if 'chart_symbol' in row:
                factor=symbol_scale(row,scale,pixel_factor)
                if factor<=0:continue
                for typ,points in symbol_parts(row['chart_symbol'],row.get('symbol_variant')):
                    shape=[[x+dx*factor/scale,y-dy*factor/scale] for dx,dy in points]
                    yield (dict(polygon(row['oid'],shape,row['fill'],row['symbol_fill']),width=pixel_factor/scale)
                           if typ=='polygon' else line(row['oid'],shape,row['fill'],pixel_factor/scale))
                continue
            dx,dy=row['chart_offset']
            row.update(points=[[x+dx*pixel_factor/scale,y-dy*pixel_factor/scale]],
                       size=row.get('chart_world_size',row['chart_px']*pixel_factor/scale))
            if 'chart_box' in row:
                from map_painter import text_sprite
                x,y=row['points'][0]
                size=row['size']
                sprite=text_sprite(row['text'],row['fill'],100)
                half_width=size*(sprite.width/sprite.height/2+.28)
                half_height=size*.72
                if 'chart_pavement' in row:
                    (x,y),source=hotspot_label_pose(item,half_width,half_height,9*pixel_factor/scale)
                    row['points']=[(x,y)]
                    yield line(row['oid'],[source,box_edge((x,y),source,half_width,half_height)],
                               row['chart_box'],pixel_factor/scale)
                corners=[(x-half_width,y-half_height),(x+half_width,y-half_height),
                         (x+half_width,y+half_height),(x-half_width,y+half_height)]
                yield dict(polygon(row['oid'],corners,row['chart_box'],None),width=pixel_factor/scale)
        yield row


def saved_region(scene,items):
    region=settings(scene).get('region')
    if (isinstance(region,(list,tuple)) and len(region)==4
            and all(isinstance(v,(float,int)) and math.isfinite(v) for v in region)
            and region[2]>region[0] and region[3]>region[1]):
        return region
    return fit_extent(items)


PAPERS={'auto':None,'A3':(297,420),'A4':(210,297),'A5':(148,210),'Letter':(215.9,279.4)}
PAGE_MOVABLE={'note','legend','scale','north'}
FOOTER_MARGIN=.075
SURFACES={'':'未标注','ASPH':'沥青','CONC':'混凝土','GRASS':'草地','GRVL':'砾石'}
SCALE_UNITS={'m':1.,'km':1000.,'ft':.3048,'NM':1852.}


def paper_size(info):
    paper=PAPERS.get(info.get('paper','auto'))
    if paper and info.get('orientation')=='landscape':return paper[::-1]
    return paper


def frequency_lines(info,key):
    return [piece for row in info.get(key,'').splitlines()
            for piece in textwrap.wrap(row.strip(),width=24)]


def header_extra(info):
    return max(0,sum(len(frequency_lines(info,key)) for key,_ in FIELDS[2:6])-3)*.016


def frame_aspect(info):
    paper=paper_size(info)
    if not paper:return None
    return .90/max(.12,paper[1]/paper[0]-.24-FOOTER_MARGIN-header_extra(info))


def adjust_region(region,info,crop=None):
    ratio=frame_aspect(info)
    if ratio is None:return tuple(region)
    x0,y0,x1,y1=region
    center=(x0+x1)/2,(y0+y1)/2
    w,h=x1-x0,y1-y0
    crop=info.get('fit')=='crop' if crop is None else crop
    width=min(w,h*ratio) if crop else max(w,h*ratio)
    height=width/ratio
    return center[0]-width/2,center[1]-height/2,center[0]+width/2,center[1]+height/2


def page_box(region,info=None):
    x0,y0,x1,y1=region
    paper=paper_size(info or {})
    if paper:
        width=(x1-x0)/.90
        height=width*paper[1]/paper[0]
        bottom=y0-width*FOOTER_MARGIN
        return x0-width*.05,bottom,x1+width*.05,bottom+height
    width=max(1.,x1-x0,(y1-y0)*.30)
    center=(x0+x1)/2
    return center-width*.55,y0-width*FOOTER_MARGIN,center+width*.55,y1+width*(.24+header_extra(info or {}))


def center_page_vertically(page,items):
    from map_painter import text_sprite

    x0,y0,x1,y1=page
    scale=1000/(x1-x0)
    lower,upper=math.inf,-math.inf
    for row in pixel_items(items,scale):
        if row['type']=='text':
            y=row['points'][0][1]
            sprite=text_sprite(row['text'],row['fill'],round(row['size']*scale),
                               row.get('rotation',0),row.get('font','normal'))
            half=sprite.height/(2*scale)
            lo,hi=y-half,y+half
        else:
            if not row['points']:continue
            ys=[p[1] for p in row['points']]
            half=row.get('width',0)/2 if row.get('stroke') else 0
            lo,hi=min(ys)-half,max(ys)+half
        lower,upper=min(lower,lo),max(upper,hi)
    if lower>upper:return page
    offset=(lower+upper-y0-y1)/2
    return x0,y0+offset,x1,y1+offset


def page_items(scene, items, kinds, region, page, info=None):
    from geometry11 import LineString, Polygon, lines, polygons
    from shapely.geometry import box
    config=settings(scene)
    if info is None:info=config.get('page',{})
    x0,y0,x1,y1=region
    left,bottom,right,top=page
    width=right-left
    pane=box(*region)
    result=[]
    group='frame'
    from map_painter import text_sprite
    def text_width(value,size):
        sprite=text_sprite(value,'#262626',100)
        return sprite.width/sprite.height*size
    def text(x,y,value,size=13,color='#262626',angle=0,align='center',indent=0,dy=0):
        if not value:return
        dx=indent
        if align!='center':dx+=(1 if align=='left' else -1)*text_width(value,size)/2
        result.append(dict(label('F8_PAGE:'+group,[x,y],value,size,color,dx=dx,dy=dy),rotation=angle))
    def rule(points,color='#262626',weight=1):
        result.append(line('F8_PAGE:'+group,points,color,width*.0013*weight))
    def swatch(points,stroke,fill):
        result.append(polygon('F8_PAGE:'+group,points,stroke,fill))
    # Intersect the map geometry itself so the header/footer stay clear.
    for item in items:
        points=item['points']
        if item['type']=='text':
            if 'runway_end' in item:
                from shapely.geometry import Point
                axis=LineString(item['runway_axis'])
                if not pane.covers(Point(axis.coords[0 if item['runway_end']=='a' else -1])):
                    # Project the cut endpoints back onto the runway to preserve end identity.
                    stations=sorted(axis.project(Point(q)) for part in lines(axis.intersection(pane))
                                    for q in (part.coords[0],part.coords[-1]))
                    if not stations:continue
                    low,high=stations[0],stations[-1]
                    station=low if item['runway_end']=='a' else high
                    margin=min((high-low)/3,width*.012)
                    station+=margin if item['runway_end']=='a' else -margin
                    q=axis.interpolate(station)
                    nx,ny=item['normal']
                    original=axis.coords[0 if item['runway_end']=='a' else -1]
                    anchor=item['points'][0]
                    lateral=(anchor[0]-original[0])*nx+(anchor[1]-original[1])*ny
                    inset=min(width*.010,(x1-x0)/4,(y1-y0)/4)
                    x=min(x1-inset,max(x0+inset,q.x+nx*lateral))
                    y=min(y1-inset,max(y0+inset,q.y+ny*lateral))
                    item=dict(item,points=[(x,y)])
            x,y=item['points'][0]
            if x0<=x<=x1 and y0<=y<=y1:result.append(item)
        elif item['type']=='line' and len(points)>=2:
            for part in lines(LineString(points).intersection(pane)):
                result.append(dict(item,points=list(part.coords)))
        elif item['type']=='polygon' and len(points)>=3:
            for part in polygons(Polygon(points).buffer(0).intersection(pane)):
                result.append(dict(item,points=list(part.exterior.coords)[:-1]))
    rule([(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)])
    header=header_extra(info)
    group='title'
    heading_size=22
    header_gap=10
    heading_dy=-(header_gap+heading_size/2)
    text(x0,y1,'AIRCRAFT PARKING/DOCKING',heading_size,align='left',dy=heading_dy-heading_size-4)
    text(x0,y1,'CHART — ICAO',heading_size,align='left',dy=heading_dy)
    group='channels'
    channels=[(caption if not index else '',value)
              for key,caption in FIELDS[2:6]
              for index,value in enumerate(frequency_lines(info,key))]
    if channels:
        size=10
        dy=-(header_gap+size/2)
        def label_width(value):
            return text_sprite(value,'#262626',size,font='chart_header').width
        name_width=max(label_width(name) for name,_ in channels if name)
        value_width=max(label_width(value) for _,value in channels)
        gap=5
        center=(x0+x1)/2
        left_px=-(name_width+gap+value_width)/2
        for index,(caption,value) in enumerate(channels):
            y=y1
            line_dy=dy-(len(channels)-1-index)*(size+5)
            if caption:
                result.append(dict(label('F8_PAGE:'+group,[center,y],caption,size,
                                    dx=left_px+name_width-label_width(caption)/2,dy=line_dy),font='chart_header'))
            result.append(dict(label('F8_PAGE:'+group,[center,y],value,size,
                                dx=left_px+name_width+gap+label_width(value)/2,dy=line_dy),font='chart_header'))
    group='airport'
    text(x1,y1,' '.join(filter(None,(info.get('ident'),info.get('airport')))),heading_size,align='right',dy=heading_dy)
    group='disclaimer'
    text(x1,y0,DISCLAIMER,9,align='right',indent=-7,dy=-8)
    group='footer'
    rule([(x0,y0-width*.017),(x1,y0-width*.017)])
    footer_y=y0-width*.042
    text(x0,footer_y,info.get('chart_no'),10,align='left')
    text((x0+x1)/2,footer_y,info.get('author'),10)
    text(x1,footer_y,'    '.join(filter(None,(info.get('edition'),info.get('date')))),10,align='right')
    if info.get('changes'):text(x0,y0-width*.061,'Changes: '+info['changes'],8,align='left')
    note_rows=[]
    import re
    hanging=0
    for raw in info.get('note','').splitlines():
        match=re.match(r'^\s*(\d+[.、)])\s*(.*)',raw)
        if match:
            prefix,content=match.groups()
            hanging=text_width(prefix+' ',10)+3
            lines_=textwrap.wrap(content,width=44) or ['']
            note_rows.append((0,prefix+' '+lines_[0]))
            note_rows.extend((hanging,value) for value in lines_[1:])
        else:
            note_rows.extend((hanging,value) for value in (textwrap.wrap(raw.strip(),width=44) or ['']))
    if 'CLOSURE' in kinds:
        note_rows.extend((0,value) for value in textwrap.wrap(tr(CLOSURE_NOTES[closure_style(config)]),width=44))
    if note_rows:
        group='note'
        x=x0+(x1-x0)*.055
        spacing=min(width*.017,(y1-y0)*.45/max(1,len(note_rows)))
        note_y=y0+(y1-y0)*.105+spacing*len(note_rows)
        text(x,note_y,'Note：',10,align='left')
        for index,(indent,value) in enumerate(note_rows,1):
            text(x,note_y-index*spacing,value,10,align='left',indent=indent)
    if info.get('legend',True):
        group='legend'
        entries=[kind for kind in (*TYPES,'CLOSURE') if kind in kinds]
        count=max(1,min(6,int(info.get('legend_count',2))))
        vertical=info.get('legend_direction')=='vertical'
        columns=count if vertical else max(1,math.ceil(len(entries)/count))
        rows=max(1,math.ceil(len(entries)/columns)) if vertical else count
        for index,kind in enumerate(entries):
            col,row=(index//rows,index%rows) if vertical else (index%columns,index//columns)
            x=(x0+(x1-x0)*((col+.66)/columns)) if not vertical else x0+width*(.065+col*.135)
            y=y1+width*(.216+header-row*.016) if not vertical else y1-width*(.04+row*.019)
            a=x-min(width*.045,(x1-x0)*.15/columns)
            half_width=width*.012
            half_height=width*.004
            if kind=='ELEV':
                text(a,y,'ELEV',8)
                text(x,y,tr(TYPES[kind][0]),9)
                continue
            if kind=='CLOSURE':
                if closure_style(config)=='cross':
                    ink=colors(config,'TAXIWAY')[1]
                    for position in (-.65,0,.65):
                        cx=a+position*half_width
                        for sign in (-1,1):
                            rule([(cx-half_height,y-sign*half_height),(cx+half_height,y+sign*half_height)],ink,1.2)
                else:
                    rule([(a-half_width,y),(a+half_width,y)],CLOSURE_RED)
                text(x,y,tr(CLOSURE_LABEL),9)
                continue
            stroke,fill=colors(config,kind)
            if kind in ('ARP','WIND','PAPI','AIM',*NAV_SYMBOLS):
                ink='#000000' if kind=='ARP' else stroke
                variant=next((item.get('symbol_variant') for item in items
                              if item.get('chart_symbol')=='TOWER'),None) if kind=='TOWER' else None
                for typ,points in symbol_parts(kind,variant):
                    shape=[(a+dx*half_height/9,y-dy*half_height/9) for dx,dy in points]
                    if typ=='polygon':swatch(shape,ink,None if kind=='ARP' else fill)
                    else:rule(shape,ink)
            else:
                swatch([(a-half_width,y-half_height),(a+half_width,y-half_height),
                        (a+half_width,y+half_height),(a-half_width,y+half_height)],stroke,fill)
            text(x,y,tr(TYPES[kind][0]),9)
    if info.get('scale',True):
        group='scale'
        unit=info.get('scale_unit','m')
        factor=SCALE_UNITS.get(unit,1.)
        raw=(x1-x0)*.19/factor
        magnitude=10**math.floor(math.log10(max(raw,1e-9)))
        value=max((v*magnitude for v in (.5,1,2,5) if v*magnitude<=raw),default=raw)
        length=value*factor
        y=y0+(y1-y0)*.033
        x=x0+(x1-x0)*.045
        tick=width*.006
        style=info.get('scale_style','line')
        if style=='numeric':
            print_width=(paper_size(info) or (210,297))[0]
            denominator=max(1,round(width*1000/print_width))
            text(x+length/2,y+tick,f'1:{denominator:,}  ·  1 cm = {denominator*.01/factor:.4g} {unit}',10)
        elif style=='rail':
            for i in range(4):
                a=x+i*length/4
                b=a+length/4
                for j in range(2):
                    c=y+j*tick/2
                    d=c+tick/2
                    swatch([(a,c),(b,c),(b,d),(a,d)],'#262626','#262626' if (i+j)%2==0 else '#ffffff')
            text(x+length/2,y+tick*2.6,f'{value:g} {unit}',10)
        else:
            rule([(x,y+tick),(x,y),(x+length,y),(x+length,y+tick)])
            text(x+length/2,y+tick*2.6,f'{value:g} {unit}',10)
    if info.get('true_north',True) or info.get('magnetic_north',True):
        group='north'
        x=x1-(x1-x0)*.12
        y=y1-(y1-y0)*.17
        true=-float(scene.data['meta'].get('grid_north_true_heading',0))
        decl=float(scene.data['meta'].get('magnetic_declination') or 0)
        for heading,tag,ray in ((true,'N',.064),(true+decl,'MN',.048)):
            if tag=='MN' and not info.get('magnetic_north',True):continue
            if tag=='N' and not info.get('true_north',True):continue
            angle=math.radians(heading)
            tip=(x+math.sin(angle)*width*ray,y+math.cos(angle)*width*ray)
            rule([(x,y),tip])
            for side in (-1,1):
                point=(tip[0]-math.sin(angle+side*.6)*width*.006,tip[1]-math.cos(angle+side*.6)*width*.006)
                rule([point,tip])
            if tag=='N':
                text(tip[0]+math.sin(angle)*width*.010,tip[1]+math.cos(angle)*width*.010,tag,10)
            else:
                caption=f'VAR {abs(decl):g}°'+('E' if decl>0 else 'W' if decl<0 else '')
                side=1 if decl>=0 else -1
                distance=width*.017*side
                text((x+tip[0])/2+math.cos(angle)*distance,
                     (y+tip[1])/2-math.sin(angle)*distance,caption,10,angle=(-heading)%180-90)
    offsets=info.get('positions',{})
    for row in result:
        oid=row['oid']
        if oid.startswith('F8_PAGE:') and oid[8:] in PAGE_MOVABLE and oid[8:] in offsets:
            dx,dy=offsets[oid[8:]]
            row['points']=[(x+dx*width,y+dy*(top-bottom)) for x,y in row['points']]
    return result
