"""Metre-based airport map compositor; pavement, shoulder and paint are separate."""
import html
import math
from pathlib import Path
import scene_geometry as g
from pavement_geometry import corridor_parts,exclude_runways,crossings,fillets,turn_guides,offset,subtract_convex,shoulder_width
from marking_catalog import primitives,CATALOG,hatch_segments
from scene_rules import holding_plan
from common import check_size
from map_painter import draw_items,sprite_data_url

COLORS=dict(background='#e9eef2',runway='#454b53',taxiway='#737b83',apron='#9199a1',
            shoulder='#c7cbd0',marking='#ffdb64',white='#ffffff',red='#cf383e',text='#344c62',protected='#ddd4ed',equipment='#d4aa7a',closed='#d08891')

def runway_center_width(scene,runway):
    p=runway['props'];default=.9 if any(p.get(k) in ('2','3') for k in ('level_a','level_b')) else .45 if any(p.get(k) in ('0','1') for k in ('level_a','level_b')) else .3
    override=scene.data.get('generated_overrides',{}).get('AUTO:'+runway['id']+':RWY_CENTER',{})
    return override.get('props',{}).get('line_width',default)

def bounds(scene,include_bitmaps=False):
    from bitmap_layers46 import layers,corners
    pts=[point for row in layers(scene).values() for point in corners(row)] if include_bitmaps else []
    for a in scene.assets.values():
        margin=a['props']['width']/2+a['props']['shoulder']+65
        for x,y in a['points']:pts.extend([[x-margin,y-margin],[x+margin,y+margin]])
    for mid in scene.movements:
        for x,y in scene.movement_path(mid):pts.extend([[x-45,y-45],[x+45,y+45]])
        m=scene.movements[mid]
        if m.get('geometry')=='RAPID' and m.get('reverse_join_pavement',True):
            from route_geometry import reverse_join
            branch=reverse_join(scene,m)
            if branch:
                for x,y in branch['points']:pts.extend([[x-45,y-45],[x+45,y+45]])
    if not pts:return (-500,-300,500,600)
    return min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)

def surface_geometry(scene):
    """Reuse the pavement snapshot across render, signs and audit passes."""
    key=(id(scene.data),scene.revision)
    cached=getattr(scene,'_surface_geometry49',None)
    if not scene._transaction_depth and cached and cached[0]==key:
        return cached[1]
    surfaces=_build_surface_geometry(scene)
    if not scene._transaction_depth:scene._surface_geometry49=(key,surfaces)
    return surfaces

def _build_surface_geometry(scene):
    """Exact vector pieces outside runway rectangles; no raster boolean dependency."""
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY']
    aprons=[a['points'] for a in scene.assets.values() if a['kind']=='APRON']
    convex_aprons=[]
    for points in aprons:
        signs=[]
        for i,a in enumerate(points):
            b=points[(i+1)%len(points)];c=points[(i+2)%len(points)];signs.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
        if all(v>=-1e-8 for v in signs) or all(v<=1e-8 for v in signs):convex_aprons.append((points,(min(q[0] for q in points),min(q[1] for q in points),max(q[0] for q in points),max(q[1] for q in points))))
    stopping=[]
    for runway in runways:
        u=g.unit(*runway['points'])
        for end,sign,origin in (('a',-1,runway['points'][0]),('b',1,runway['points'][-1])):
            length=runway['props'].get('stopway_'+end,0)
            if length:
                tip=[origin[k]+sign*u[k]*length for k in (0,1)]
                stopping.append(g.rectangle([origin,tip],runway['props']['width']))
    def taxi_parts(poly):
        parts=exclude_runways(poly,runways)
        for footprint in stopping:
            parts=[piece for part in parts for piece in subtract_convex(part,footprint)]
        if not poly:return parts
        x0,y0=min(q[0] for q in poly),min(q[1] for q in poly)
        x1,y1=max(q[0] for q in poly),max(q[1] for q in poly)
        for apron,(ax0,ay0,ax1,ay1) in convex_aprons:
            if x1<ax0 or ax1<x0 or y1<ay0 or ay1<y0:continue
            parts=[x for part in parts for x in subtract_convex(part,apron)]
        return parts
    from pavement10 import clip_caps,runway_cap_planes,corridor_caps,runway_terminal
    def clipped_corridors(points,width,planes,kind):
        for outline in corridor_parts(points,width):
            poly=clip_caps(outline,planes)
            if poly:
                yield from ([poly] if kind=='RUNWAY' else taxi_parts(poly))

    caps=runway_cap_planes(scene)
    from pavement_geometry import rounded_terminal_joins,terminal_band
    junctions=crossings(scene)
    trims,bands=rounded_terminal_joins(scene,junctions)
    pavement=[];shoulders=[];patches=[]
    for a in scene.assets.values():
        kind=a['kind'];p=a['props'];aid=a['id']
        if kind in ('MARKING','PROTECTION','EQUIPMENT','CLOSED_AREA'):continue
        if kind=='APRON':
            if p.get('turn_pad'):
                from turn_pad import hull
                r=scene.assets[p['pad_runway']];shoulder=r['props'].get('shoulder',0)
                if shoulder:
                    outer=hull([[q[0]+shoulder*math.cos(i*math.pi/8),q[1]+shoulder*math.sin(i*math.pi/8)] for q in a['points'] for i in range(16)])
                    from pavement_geometry import halfplane
                    start,end=r['points'];u=g.unit(start,end);v=[-u[1],u[0]]
                    outer=halfplane(outer,start,[start[0]-v[0],start[1]-v[1]])
                    outer=halfplane(outer,end,[end[0]+v[0],end[1]+v[1]])
                    shoulders.extend(dict(oid=aid,points=poly,kind='APRON') for poly in exclude_runways(outer,runways))
            for poly in exclude_runways(a['points'],runways):pavement.append(dict(oid=aid,points=poly,kind='APRON'))
            continue
        if kind=='STAND':continue
        shoulder=shoulder_width(kind,p)
        total=p['width']+2*shoulder
        planes=corridor_caps(a['points'],caps.get(aid,()))
        points=g.subpath(a['points'],*trims[aid]) if aid in trims else a['points']
        if shoulder:
            shoulders.extend(dict(oid=aid,points=x,kind=kind)
                             for x in clipped_corridors(points,total,planes,kind))
        pavement.extend(dict(oid=aid,points=x,kind=kind)
                        for x in clipped_corridors(points,p['width'],planes,kind))
    for mid,m in scene.movements.items():
        if not m.get('pavement_visible',True):continue
        connector_kind=m.get('taxiway_kind39','CONNECTOR')
        a=scene.assets[m['from']['asset']];b=scene.assets[m['to']['asset']]
        if m['role'] in ('PUSHBACK','STAND_ENTRY') and a['props'].get('parent_id')==b['props'].get('parent_id') and a['props'].get('parent_id'):continue
        pts=scene.movement_path(mid)
        if g.length(pts)<.1:continue
        shoulder=shoulder_width(connector_kind,m,max(shoulder_width(a['kind'],a['props']),shoulder_width(b['kind'],b['props'])))
        planes=corridor_caps(pts,caps.get(mid,()))
        shoulder_planes=list(planes)
        from pavement_geometry import area
        for port,approach in ((a,pts[-1]),(b,pts[0])):
            if port['kind']!='RUNWAY':continue
            start,finish=port['points']
            # Keep the connector shoulder on the approach side of its runway.
            if abs(area([start,finish,approach]))<1e-7:continue
            if area([start,finish,approach])<0:start,finish=finish,start
            shoulder_planes.append((start,finish))
        if shoulder:
            shoulders += [dict(oid=mid,points=x,kind=connector_kind) for x in clipped_corridors(pts,m['width']+2*shoulder,shoulder_planes,connector_kind)]
        pavement += [dict(oid=mid,points=x,kind=connector_kind) for x in clipped_corridors(pts,m['width'],planes,connector_kind)]
        from junction_routes import branches,fork_polygon
        for branch in branches(scene,m):
            if not m.get('reverse_join_pavement',True):continue
            if m.get('geometry')=='RAPID':
                from smart_routes import reverse_surface
                branch=reverse_surface(scene,m,branch)
            oid=branch['oid'];bp=branch['points']
            if shoulder:shoulders += [dict(oid=oid,points=x,kind=connector_kind) for x in clipped_corridors(bp,m['width']+2*shoulder,shoulder_planes,connector_kind)]
            pavement += [dict(oid=oid,points=x,kind=connector_kind) for x in clipped_corridors(bp,m['width'],(),connector_kind)]
            # The area enclosed by two forks and the receiving taxiway is bearing pavement.
            fill=fork_polygon(scene,m,branch)
            if len(fill)>2:
                pavement += [dict(oid=mid+':fork',points=x,kind=connector_kind) for x in taxi_parts(fill)]
    def store_arc(oid,arc,points,planes):
        if not planes:
            patches.append(dict(oid=oid,arc=arc,points=points))
            return
        from geometry11 import LineString,lines
        # Keep just the exposed curve pieces; do not recreate the cut-off circumference.
        route=LineString(arc)
        for start,end in planes:
            dx,dy=end[0]-start[0],end[1]-start[1]
            span=max(g.distance(start,p) for p in arc)+1
            shell=[[start[0]+dx*span,start[1]+dy*span],[start[0]-dx*span,start[1]-dy*span],
                   [start[0]+(-dx-dy)*span,start[1]+(-dy+dx)*span],
                   [start[0]+(dx-dy)*span,start[1]+(dy+dx)*span]]
            from geometry11 import polygon
            route=route.intersection(polygon(shell))
        for piece in lines(route):
            patches.append(dict(oid=oid,arc=[list(q) for q in piece.coords],points=clip_caps(points,planes)))

    for j in junctions:
        if j['id'] in bands:
            band=bands[j['id']]
            for outer,dest in ((False,pavement),(True,shoulders)):
                if outer and any(a['kind']=='APRON_TAXIWAY' for a in band[1]):continue
                shape=terminal_band(*band,outer)
                if shape:
                    dest.extend(dict(oid=j['id'],points=p,kind='FILLET') for p in taxi_parts(shape))
            shape=terminal_band(*band,False)
            n=len(band[0])
            patches.extend(dict(oid=j['id'],arc=edge,points=shape) for edge in (shape[:n],shape[n:]))
            continue
        planes=[end[:2] for aid,station in zip(j['assets'],j['stations'])
                if aid in scene.assets and scene.assets[aid]['kind']=='RUNWAY'
                and (end:=runway_terminal(scene.assets[aid],station))]
        # Butt-ended corridors need a bearing core at a shared endpoint (L/T joins).
        routes=__import__('pavement_geometry').route_objects(scene)
        apron_join=any(routes[aid]['kind']=='APRON_TAXIWAY' for aid in j['assets'])
        if any(min(st,g.length(routes[aid]['points'])-st)<.1 for aid,st in zip(j['assets'],j['stations'])):
            for outer in (True,False):
                if outer and apron_join:continue
                radius=max(routes[aid]['props']['width']/2+(shoulder_width(routes[aid]['kind'],routes[aid]['props']) if outer else 0) for aid in j['assets'])
                pts=[[j['point'][0]+radius*math.cos(i*math.pi/48),j['point'][1]+radius*math.sin(i*math.pi/48)] for i in range(96)]
                oid=j['id']+':core';dest=shoulders if outer else pavement
                dest.extend(dict(oid=oid,points=x,kind='FILLET') for x in taxi_parts(clip_caps(pts,planes)))
                if not outer:store_arc(oid,pts+[pts[0]],pts,planes)
        for outer in (True,False):
            if outer and apron_join:continue
            for p in fillets(scene,j,outer):
                parts=[piece for shape in (p['polygon'],*p.get('welds',()))
                       for piece in taxi_parts(clip_caps(shape,planes))]
                dest=shoulders if outer else pavement
                dest += [dict(oid=j['id'],points=x,kind='FILLET') for x in parts]
                if not outer:store_arc(j['id'],p['arc'],p['polygon'],planes)
    # Runways have their own material and are painted last, but taxi pieces have
    # already been subtracted geometrically (tested independently of draw order).
    pavement.sort(key=lambda x:x['kind']=='RUNWAY')
    from pavement11 import trim_shoulders
    return trim_shoulders(scene,dict(pavement=pavement,shoulders=shoulders,fillets=patches,runways=runways))

def synthetic(oid,key,points,**props):
    p=dict(CATALOG[key]['defaults']);p.update(props);p['mark_type']=key
    return dict(id=oid,kind='MARKING',points=points,props=p,name=CATALOG[key]['name'])

def runway_paint(a):
    from runway import aim_dimensions,pair_count,threshold_geometry
    p=a['props'];pts=a['points'];total=g.length(pts);aid=a['id'];out=[]
    def mark(key,origin,tangent,**props):
        out.extend(primitives(synthetic(aid,key,[origin,[origin[0]+tangent[0]*10,origin[1]+tangent[1]*10]],**props)))
    u=g.unit(*pts)
    center_width=.9 if any(p.get(k) in ('2','3') for k in ('level_a','level_b')) else .45 if any(p.get(k) in ('0','1') for k in ('level_a','level_b')) else .3
    da=p.get('displaced_a',0);db=p.get('displaced_b',0)
    if p.get('center_visible',True) and total-da-db>180:
        start=da+90;end=total-db-90
        out.extend(primitives(synthetic(aid,'RWY_CENTER',g.subpath(pts,start,end),line_width=center_width)))
    for end,sign,disp,other in (('a',1,da,db),('b',-1,db,da)):
        origin=disp if sign==1 else total-disp;t=[x*sign for x in u]
        def pos(s):return g.at(pts,max(0,min(total,origin+sign*s)))[0]
        if disp:
            q=pos(0);v=(-u[1]*p['width']/2,u[0]*p['width']/2)
            out.extend(primitives(synthetic(aid,'THRESHOLD_BAR',[[q[0]-v[0],q[1]-v[1]],[q[0]+v[0],q[1]+v[1]]])))
            for s in range(35,int(disp),60):mark('DISPLACED_ARROW',pos(-s-30),t)
        if total-disp<100:continue
        if p.get('show_thresholds',True):mark('RWY_THRESHOLD',pos(6),t,width=p['width'])
        if p.get('show_numbers',True):mark('RWY_NUMBER',pos(70),t,text=p.get('label_'+end,'09'),text_height=9)
        lda=p.get('lda_'+end) or total-disp
        distance,l,w,sep=aim_dimensions(lda)
        if p.get('show_aimpoints',True) and lda>=distance+l:mark('AIMING_POINT',pos(distance),t,lda=lda)
        tdz=p.get('level_'+end,'1')!='v' or p.get('code_number') in (3,4)
        if p.get('show_tdz',True) and tdz:
            for i in range(pair_count(total-da-db)):
                station=150*(i+1)
                if station+22.5>total-da-db or station<=distance+l+50 and station+22.5>=distance-50:continue
                mark('TDZ_CODED',pos(station),t,width=sep,bars=(3,3,2,2,1,1)[i])
    return out

def display_list(scene,labels=False,facilities=True,protection=True,board_enlarged=None,generated=None,chart_guides=False):
    from automatic_markings import generated_markings,holding_locations
    out=[];surfaces=surface_geometry(scene);runways=surfaces['runways'];junctions=crossings(scene)
    curves={mid:scene.movement_path(mid) for mid in scene.movements}
    def poly(oid,pts,fill=None,color=None,width=.15,dash=None):out.append(dict(type='polygon',oid=oid,points=pts,fill=fill,stroke=color,width=width,dash=dash))
    def line(oid,pts,color=COLORS['marking'],width=.15,dash=None,dash_offset=0):
        if len(pts)>1:out.append(dict(type='line',oid=oid,points=pts,stroke=color,width=width,dash=dash,dash_offset=dash_offset))
    def add_mark(oid,key,pts,**props):out.extend(primitives(synthetic(oid,key,pts,**props)))
    for a in scene.assets.values():
        if a['kind']=='PROTECTION' and protection:poly(a['id'],a['points'],COLORS['protected'],'#8b75b4',.3,[4,3])
        elif a['kind']=='EQUIPMENT' and not a['props'].get('building_role19'):poly(a['id'],a['points'],COLORS['equipment'])
    for s in surfaces['shoulders']:
        poly(s['oid'],s['points'],COLORS['shoulder'])
        out[-1].update(continuous_pavement=True,draw_band='surface')
    for s in surfaces['pavement']:
        poly(s['oid'],s['points'],COLORS['runway'] if s['kind']=='RUNWAY' else COLORS['apron'] if s['kind']=='APRON' else COLORS['taxiway'])
        out[-1]['draw_band']='surface'
        if s['kind']=='APRON':out[-1]['apron_base']=True
        if s['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','CONNECTOR','FILLET'):
            out[-1]['continuous_pavement']=True
    from roads10 import paint as road_paint
    from geometry11 import road_bend_patches, clip_extras
    road_patches=road_bend_patches(scene)
    for item in clip_extras(scene,road_patches)+__import__('bridge_snap20_5').road_on_apron(scene,road_patches):
        out.append(dict(item,draw_band='surface') if item['type']=='polygon' and item.get('fill') else item)
    from project10 import stopways
    for runway in runways:
        for item in stopways(runway):
            out.append(dict(item,draw_band='surface') if item['type']=='polygon' and not item.get('stroke') else item)
    if generated is None:generated=generated_markings(scene)
    holds={}
    for a in (list(generated.values()) if facilities else [])+[a for a in scene.assets.values() if a['kind']=='MARKING']:
        if a['props']['mark_type'] not in ('HOLD_A','HOLD_B','INTERMEDIATE','INTERMEDIATE_POINT'):continue
        p=a['points'][0];u=g.unit(a['points'][0],a['points'][-1]);span=a['props']['width']
        if a['props']['mark_type']=='INTERMEDIATE':
            p,_=g.at(a['points'],g.length(a['points'])/2);u=(-u[1],u[0]);span=g.length(a['points'])
        holds[a['id']]=dict(point=p,tangent=u,span=span,half=1.05 if a['props']['mark_type'] in ('HOLD_A','HOLD_B') else .15)
    runway_boxes=[]
    for r in runways:
        a,b=r['points'];u=g.unit(a,b);p=r['props'];white=runway_center_width(scene,r)
        runway_boxes.append((a[0],a[1],u[0],u[1],g.length(r['points']),p['width']/2,white/2+.9+.075))
    def in_runway(p,extra=0):
        for x,y,ux,uy,length,half,gap in runway_boxes:
            dx,dy=p[0]-x,p[1]-y
            if -extra<=dx*ux+dy*uy<=length+extra and abs(-dx*uy+dy*ux)<=half+extra:return True
        return False
    def runway_center_gap(q):
        for x,y,ux,uy,length,half,gap in runway_boxes:
            dx,dy=q[0]-x,q[1]-y
            if 0<=dx*ux+dy*uy<=length and abs(-dx*uy+dy*ux)<gap:return True
        return False
    boxes=[]
    for s in surfaces['pavement']:
        if s['kind'] in ('RUNWAY','ROAD'):continue
        pts=s['points'];boxes.append((s,min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)))
    surface_index={};cell_size=100.
    for item in boxes:
        s,x0,y0,x1,y1=item
        if (x1-x0)*(y1-y0)>1e8:continue
        for ix in range(math.floor(x0/cell_size),math.floor(x1/cell_size)+1):
            for iy in range(math.floor(y0/cell_size),math.floor(y1/cell_size)+1):surface_index.setdefault((ix,iy),[]).append(item)
    large_boxes=[item for item in boxes if (item[3]-item[1])*(item[4]-item[2])>1e8]
    def other_pavement(p,oid,ignore_pad=False):
        candidates=surface_index.get((math.floor(p[0]/cell_size),math.floor(p[1]/cell_size)),())
        for s,x0,y0,x1,y1 in list(candidates)+large_boxes:
            if ignore_pad and s['oid'] in scene.assets and scene.assets[s['oid']]['props'].get('turn_pad'):continue
            if s['oid']!=oid and x0<p[0]<x1 and y0<p[1]<y1 and g.inside(p,s['points']):return True
        return False
    hold_data=[]
    for h in holds.values():
        x,y=h['point'];ux,uy=h['tangent'];half=h.get('half',1.05)+.9+.075;span=h['span']/2+.5
        rx=abs(ux)*half+abs(uy)*span;ry=abs(uy)*half+abs(ux)*span
        hold_data.append((x,y,ux,uy,half,span,rx,ry))
    def holding_gap(p):
        for x,y,ux,uy,half,span,rx,ry in hold_data:
            dx,dy=p[0]-x,p[1]-y
            if abs(dx)>rx or abs(dy)>ry:continue
            if abs(dx*ux+dy*uy)<half and abs(-dx*uy+dy*ux)<span:return True
        return False
    def clipped(oid,pts,blocked,color=COLORS['marking'],width=.15,dash=None,probe_offset=None):
        path=g.PathIndex(pts);length=path.length
        if length<.01:return
        def state(station):
            q,u=path.at(station)
            if probe_offset is None:return q,blocked(q)
            outside=[q[0]-u[1]*probe_offset,q[1]+u[0]*probe_offset]
            return q,blocked(q,outside)
        count=max(1,min(20000,math.ceil(length/1.5)));chunk=[];previous=None;chunk_station=0
        if len(pts)==2 and length>80:
            # Most long straight spans cannot intersect any blocker. Sample only
            # the broad-phase intervals around other pavement/holding/junctions.
            regions=[(x0-2,y0-2,x1+2,y1+2) for s,x0,y0,x1,y1 in boxes if s['oid']!=oid]
            for r in runways:
                if r['id']!=oid:
                    poly=g.rectangle(r['points'],r['props']['width']+.5);regions.append((min(p[0] for p in poly)-2,min(p[1] for p in poly)-2,max(p[0] for p in poly)+2,max(p[1] for p in poly)+2))
            for x,y,ux,uy,half,span,rx,ry in hold_data:regions.append((x-rx-2,y-ry-2,x+rx+2,y+ry+2))
            for j in junctions:
                if oid in j['assets'] or oid.startswith(j['id']):
                    cfg=scene.data.get('junctions',{}).get(j['id'],{});radius=cfg.get('radius',25)*1.4+2;x,y=j['point'];regions.append((x-radius,y-radius,x+radius,y+radius))
            active=[]
            for region in regions:
                interval=g.segment_box_interval(pts[0],pts[1],region)
                if interval:active.append((max(0,interval[0]*length),min(length,interval[1]*length)))
            active.sort();merged=[]
            for lo,hi in active:
                if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
                else:merged.append((lo,hi))
            stations=[0,length]
            for lo,hi in merged:
                n=max(1,math.ceil((hi-lo)/1.5));stations.extend(lo+(hi-lo)*i/n for i in range(n+1))
            stations=sorted(set(stations))
        else:stations=sorted(set(path.stations+[length*i/count for i in range(count+1)]))
        def flush():
            if len(chunk)>1:line(oid,g.simplify(chunk),color,width,dash,chunk_station)
        for station in stations:
            q,hidden=state(station)
            if previous is not None and hidden!=previous[2]:
                lo,hi=previous[0],station
                for _ in range(10):
                    mid=(lo+hi)/2
                    if state(mid)[1]==previous[2]:lo=mid
                    else:hi=mid
                boundary_station=(lo+hi)/2;boundary=path.at(boundary_station)[0]
                if hidden:chunk.append(boundary);flush();chunk=[]
                else:chunk=[boundary];chunk_station=boundary_station
            if not hidden:
                if not chunk:chunk_station=station
                chunk.append(q)
            previous=(station,q,hidden)
        flush()
    # Runway paint is independent of taxi surface geometry.
    from geometry11 import LineString,Point
    from guidance20 import junction_cuts
    routes=__import__('pavement_geometry').route_objects(scene)
    from lighting_closures import pavement_closures
    closed_routes=pavement_closures(scene)
    junction_guides={j['id']:turn_guides(scene,j) for j in junctions
                     if chart_guides or not any(aid in closed_routes for aid in j['assets'])}
    straight_cuts=junction_cuts(scene,junctions,routes,junction_guides)
    indexes={oid:LineString(routes[oid]['points']) for oid in straight_cuts}
    def junction_straight_hidden(oid,q):
        if oid not in straight_cuts:return False
        station=indexes[oid].project(Point(q))
        return any(lo+1e-5<station<hi-1e-5 or
                   (lo<=1e-6 and station<=lo) or
                   (hi>=indexes[oid].length-1e-6 and station>=hi)
                   for lo,hi in straight_cuts[oid])
    for a in []:  # Runway intersections are cut against every intersecting runway.
        if a['props'].get('edges_visible',True):
            w=.9 if a['props']['width']>=30 else .45
            for side in (-1,1):
                def mouth(q):
                    _,s,base=g.project(a['points'],q);_,u=g.at(a['points'],s)
                    outside=[base[0]-u[1]*side*(a['props']['width']/2+.4),base[1]+u[0]*side*(a['props']['width']/2+.4)]
                    return other_pavement(outside,a['id'],ignore_pad=True)
                clipped(a['id'],offset(a['points'],side*(min(30,a['props']['width']/2)-w/2)),mouth,COLORS['white'],w)
    for aid,a in scene.assets.items():
        kind=a['kind'];p=a['props'];pts=a['points']
        if kind in ('RUNWAY','APRON','PROTECTION','EQUIPMENT','CLOSED_AREA','MARKING','ROAD'):continue
        if not chart_guides and p.get('closed') and p.get('closure_kind')=='PERMANENT':continue
        if kind=='STAND':
            continue
        def straight_hidden(q):
            return junction_straight_hidden(aid,q)
        if p.get('center_visible',True):
            first=len(out)
            clipped(aid,__import__('rules13').asset_guide(scene,a),lambda q:holding_gap(q) or straight_hidden(q),COLORS['white'] if kind=='ROAD' else COLORS['marking'],.15,[1,1] if kind=='ROAD' else None)
            for item in out[first:]:item['chart_taxi_owners']=(aid,)
            if p.get('rapid_exit') or p.get('rapid_drawn_axis56'):
                for item in out[first:]:item['rapid_runway_guide']=True
        if False:  # Exact union boundaries are emitted below.
            for side in (-1,1):
                for inset in (.075,.375):
                    edge=offset(pts,side*(p['width']/2-inset))
                    clipped(aid,edge,lambda q,outside:in_runway(q,.2) or other_pavement(outside,aid) or holding_gap(q),COLORS['white'] if kind=='ROAD' else COLORS['marking'],probe_offset=side*(inset+.25))
        if p.get('shoulder_markings') and shoulder_width(kind,p)>0:
            length=g.length(pts);s=0;bar=min(7.5,p['shoulder'] if p['shoulder']<3.5 else p['shoulder']-1.5)
            while s<=length:
                q,u=g.at(pts,s)
                for side in (-1,1):
                    n=(-u[1]*side,u[0]*side);start=[q[k]+n[k]*p['width']/2 for k in (0,1)];end=[start[k]+n[k]*bar for k in (0,1)]
                    omit=any(h and 'point' in h and g.project([[h['point'][0]-h['tangent'][1]*h['span']/2,h['point'][1]+h['tangent'][0]*h['span']/2],[h['point'][0]+h['tangent'][1]*h['span']/2,h['point'][1]-h['tangent'][0]*h['span']/2]],start)[0]<=7.5 for h in holds.values())
                    if not omit and not in_runway(start):line(aid,[start,end],width=.9)
                s+=15
    # Curved exposed fillet edges match the rounded pavement, not straight arm caps.
    for patch in []:  # Replaced by the exact shared boundary.
        arc=patch['arc'];middle=arc[len(arc)//2]
        test=offset(arc,.1)[len(arc)//2];sign=1 if g.inside(test,patch['points']) else -1
        for inset in (.075,.375):clipped(patch['oid'],offset(arc,sign*inset),lambda q:in_runway(q,.2) or holding_gap(q) or other_pavement(q,patch['oid']))
    for mid,m in scene.movements.items():
        if not m.get('guide_visible',True):continue
        pts=curves[mid]
        if g.length(pts)<.1:continue
        # Guidance can enter a runway while its pavement has already been cut away.
        painted=list(map(list,pts))
        for key,index in (('from',0),('to',-1)):
            a=scene.assets[m[key]['asset']]
            if a['kind']=='RUNWAY':
                rapid=m.get('geometry')=='RAPID'
                direction=m[key].get('direction') if rapid else None
                if direction in (-1,1) and key=='to':direction=-direction
                painted=extend_runway_guidance(scene,painted,a,index,direction_hint=direction,rapid=rapid)
        first=len(out)
        clipped(mid,painted,lambda q:holding_gap(q) or junction_straight_hidden(mid,q),COLORS['white'] if m['role']=='PUSHBACK' else COLORS['marking'],.15,[1,1] if m['role']=='PUSHBACK' else None)
        if m['role']!='PUSHBACK':
            for item in out[first:]:item['chart_taxi_owners']=(mid,)
        if m.get('geometry')=='RAPID':
            for item in out[first:]:item['rapid_runway_guide']=True
        if False:  # Shared boundaries and reverse guides are handled independently. 
            for side in (-1,1):
                for inset in (.075,.375):clipped(mid,offset(pts,side*(m['width']/2-inset)),lambda q,outside:in_runway(q,.2) or other_pavement(outside,mid) or holding_gap(q),probe_offset=side*(inset+.25))
            from junction_routes import branches
            for branch in branches(scene,m):
                port = m.get(branch.get('side','to'),m['to'])
                if (m.get('join_reverse_visible',True) and m.get('geometry')!='RAPID'
                        and mid not in closed_routes and port['asset'] not in closed_routes):
                    clipped(branch['oid'],branch['points'],holding_gap)
                if m.get('reverse_join_pavement',True):
                    if m.get('geometry')=='RAPID':
                        from smart_routes import reverse_surface
                        branch=reverse_surface(scene,m,branch)
                    for side in (-1,1):
                        for inset in (.075,.375):clipped(branch['oid'],offset(branch['points'],side*(m['width']/2-inset)),lambda q,outside:in_runway(q,.2) or other_pavement(outside,branch['oid']) or holding_gap(q),probe_offset=side*(inset+.25))
    for j in junctions:
        for guide in junction_guides.get(j['id'],()):
            points=junction_guide_path(scene,j,guide)
            first=len(out)
            clipped(j['id'],points,holding_gap)
            for item in out[first:]:item['chart_taxi_owners']=tuple(j['assets'])
            if any(scene.assets.get(aid,{}).get('kind')=='RUNWAY' for aid in j['assets']):
                for item in out[first:]:item['runway_junction_guide32']=True
    if chart_guides:return [item for item in out if item.get('chart_taxi_owners')]
    for aid,a in generated.items():
        if not facilities and a['props']['mark_type'] in ('HOLD_A','HOLD_B','TWY_ENHANCED','MANDATORY'):continue
        if a['props']['mark_type']=='TWY_ENHANCED':
            out.extend(__import__('enhanced19').render(scene,a))
        elif a['props']['mark_type']=='TWY_CENTER':
            for item in primitives(a):
                clipped(aid,item['points'],holding_gap,item['stroke'],item['width'],item.get('dash'))
        else:out.extend(primitives(a))
    from automatic_markings import entry_mark_hidden
    manual_signs=None
    for aid,a in scene.assets.items():
        if a['kind']=='MARKING' and entry_mark_hidden(scene,a):continue
        if a['kind']=='MARKING' and a['props'].get('sign_axis21_2'):
            import signs21_2 as signs
            if manual_signs is None:manual_signs=signs.routes(scene)
            mark=signs.resolve(scene,a,manual_signs)
            if mark:out.extend(primitives(mark))
        elif a['kind']=='MARKING':out.extend(__import__('enhanced19').render(scene,a) if a['props']['mark_type']=='TWY_ENHANCED' else primitives(a))
        elif a['kind']=='CLOSED_AREA':poly(aid,a['points'],None,COLORS['closed'],.5,[3,2])

        if labels and a['kind']!='MARKING':
            q=[sum(x[k] for x in a['points'])/len(a['points']) for k in (0,1)]
            out.append(dict(type='text',oid=aid,points=[q],text=a['name'],fill=COLORS['text'],size=10,world_text=True))
    from turn_pad import paint
    white=[item for item in out if item.get('fill')==COLORS['white'] or item.get('stroke')==COLORS['white']]
    white_boxes=[]
    for item in white:
        margin=item.get('width',0)/2+.075;pts=item['points']
        white_boxes.append((item,min(p[0] for p in pts)-margin,min(p[1] for p in pts)-margin,max(p[0] for p in pts)+margin,max(p[1] for p in pts)+margin))
    def white_paint(q):
        for item,x0,y0,x1,y1 in white_boxes:
            if not x0<=q[0]<=x1 or not y0<=q[1]<=y1:continue
            if item['type']=='polygon' and item.get('fill') and g.inside(q,item['points']):return True
            if item['type']=='line' and g.project(item['points'],q)[0]<item.get('width',.15)/2+.075:return True
        return False
    for a in scene.assets.values():
        if a['props'].get('turn_pad'):
            for i,item in enumerate(paint(scene,a)):
                if i==0:clipped(a['id'],item['points'],white_paint)
                else:out.append(item)
    from shoulders17 import bars as shoulder_stripes
    from geometry11 import taxi_edges,runway_edges
    if len(surfaces['pavement'])>=120:
        from concurrent.futures import ThreadPoolExecutor
        # All three GEOS passes read the same immutable surface snapshot.
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='pavement-edge') as workers:
            shoulders_job=workers.submit(shoulder_stripes,scene,surfaces)
            taxi_job=workers.submit(taxi_edges,scene,surfaces,holds)
            runway_ink=runway_edges(scene,surfaces)
            shoulder_ink=shoulders_job.result()
            taxi_ink=taxi_job.result()
    else:
        shoulder_ink=shoulder_stripes(scene,surfaces)
        taxi_ink=taxi_edges(scene,surfaces,holds)
        runway_ink=runway_edges(scene,surfaces)
    for aid,asset in scene.assets.items():
        props=asset['props']
        if asset['kind']=='APRON' and props.get('destination_code23')=='RUNUP':
            points=asset['points']
            out.append(dict(type='line',oid=aid,points=points+[points[0]],
                            stroke=COLORS['marking'],width=.25,dash=[3,2]))
    out.extend(shoulder_ink)
    from stand_overlap9 import paint_boundaries,clip_merged_stand_lines
    from stand13 import merge_work_zone_outlines,clip_work_zones_at_stands
    markings={**{k:a for k,a in scene.assets.items() if a['kind']=='MARKING'},**generated}
    out=paint_boundaries(merge_work_zone_outlines(scene,out,markings),markings)
    out=clip_work_zones_at_stands(out,markings)
    out=clip_merged_stand_lines(scene,out,markings)
    out.extend(taxi_ink)
    out.extend(runway_ink)
    from paint12 import interrupt as interrupt_paint
    from intersections17 import runway_priority
    out.extend(road_paint(scene))
    out=__import__('roads11').separate_marks(scene,out,generated)
    from marks11 import finalize_items
    out=__import__('layout14').clip_apron_edges(scene,out,generated)
    out=__import__('layout14').solid_safety(out)
    if scene.data['meta'].get('hide_boards21_2'):
        out=[item for item in out if not item.get('sign_board21_2')]
    rendered=__import__('model20').apron_colors(scene,finalize_items(scene,runway_priority(scene,style_items(scene,interrupt_paint(scene,runway_priority(scene,__import__('rules13').closure_items(scene,out,generated),generated),generated),generated),generated),generated)+__import__('terminal19').items(scene))
    if any(item.get('sign_board21_2') for item in rendered):
        from boards24 import clear_boards, pavement, project_augmentation
        if board_enlarged is None:board_enlarged=scene.data['meta'].get('enlarge_boards26',False)
        mask=pavement(scene,surfaces)
        overrides = scene.data['generated_overrides']
        rendered = [dict(item,board_pose_locked=True)
                    if item.get('sign_board21_2') and any(overrides.get(item['oid'],{}).get(key)
                           for key in ('sign_fixed_pose','hp_fixed_pose'))
                    else item for item in rendered]
        rendered=clear_boards(rendered,mask)
        if board_enlarged:rendered=project_augmentation(scene,rendered,mask)
    from paint12 import top_runway_paint
    items=top_runway_paint(scene,rendered,generated)
    from papi21 import plan_items
    items.extend(plan_items(scene))
    from stand13 import ga_labels
    for asset in scene.assets.values():
        if asset['kind']=='STAND' and asset['props'].get('ga_stand'):
            items.extend(ga_labels(asset))
    styles=scene.data['meta'].get('object_display',{})
    items=ordered_draw_items(scene,items,generated)
    if not styles:return items
    visible=[]
    for item in items:
        oid=item['oid']
        owner=generated.get(oid,{}).get('owner') or oid.split(':')[0]
        style=styles.get(oid,{})
        parent=styles.get(owner,{}) if owner!=oid else {}
        if style.get('hidden') or parent.get('hidden'):continue
        opacity=style.get('opacity',1.)*parent.get('opacity',1.)
        if opacity>0:visible.append(dict(item,opacity=opacity) if opacity<1 else item)
    return visible

def draw_owner(item,generated):
    oid=item['oid']
    return generated.get(oid,{}).get('owner') or oid.split(':')[0]


def layer_ids(items,generated,band):
    return list(dict.fromkeys(draw_owner(item,generated) for item in items
                              if item.get('draw_band','object')==band))


def ordered_draw_items(scene,items,generated):
    order=scene.data['meta'].get('draw_order',{})
    base=[item for item in items if item.get('draw_band')=='surface']
    base.sort(key=lambda item:not item.get('apron_base'))
    objects=[item for item in items if item.get('draw_band')!='surface']
    for band,rows in (('surface',base),('object',objects)):
        if order.get(band):
            ids=layer_ids(rows,generated,band)
            ranks={oid:i for i,oid in enumerate(dict.fromkeys([*order[band],*ids]))}
            if band=='object':
                # Outlines are backing paint, even when their owner's layer is raised.
                rows.sort(key=lambda item:(not item.get('black_underlay'),ranks[draw_owner(item,generated)]))
            else:
                rows.sort(key=lambda item:ranks[draw_owner(item,generated)])
    return base+objects


def rapid_f6_guides(items):
    paths={}
    for item in items:
        if item.get('rapid_runway_guide') and item['type']=='line' and not item.get('black_underlay'):
            paths.setdefault(item['oid'],[]).append(item['points'])
    return paths


def junction_guide_path(scene,junction,guide):
    points=guide['points']
    for index,aid in enumerate(junction['assets']):
        runway=scene.assets.get(aid,{})
        if runway.get('kind')!='RUNWAY':continue
        edge=0 if index==0 else -1
        from pavement10 import runway_terminal
        end=runway_terminal(runway,junction['stations'][index])
        if end:
            from connection9 import runway_extension
            points=runway_extension(scene,points,runway,edge,direction_hint=-end[2])
        else:
            points=extend_runway_guidance(scene,points,runway,edge)
    return points

def extend_runway_guidance(scene,points,runway,index=0,**options):
    from rules13 import runway_extension
    return runway_extension(scene,points,runway,index,**options)


def export_png(scene,path,width=2400,labels=False,facilities=True,protection=False):
    box=bounds(scene);scale=width/(box[2]-box[0]);height=max(1,math.ceil((box[3]-box[1])*scale))
    check_size((width,height));items=display_list(scene,labels,facilities,protection)
    draw_items(items,(width,height),[-box[0]*scale,box[3]*scale],scale,COLORS['background']).save(path,'PNG')

def export_svg(scene,path,labels=False,facilities=True,protection=False):
    x0,y0,x1,y1=bounds(scene);w=x1-x0;h=y1-y0
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {w} {h}" width="1600" height="{max(1,round(1600*h/w))}">',
           '<metadata>Airport Scene Studio; design drawing, not a CAAC certification</metadata>',f'<rect width="100%" height="100%" fill="{COLORS["background"]}"/>']
    for e in display_list(scene,labels,facilities,protection):
        if e['type']=='text':
            data,tw,th=sprite_data_url(e);x,y=e['points'][0]
            parts.append(f'<image x="{x-x0-tw/2}" y="{y1-y-th/2}" width="{tw}" height="{th}" href="{data}"/>');continue
        coords=' '.join(f'{x-x0:.5f},{y1-y:.5f}' for x,y in e['points']);tag='polygon' if e['type']=='polygon' else 'polyline'
        dash=' stroke-dasharray="'+','.join(map(str,e['dash']))+'" stroke-dashoffset="'+str(e.get('dash_offset',0))+'"' if e.get('dash') else ''
        parts.append(f'<{tag} points="{coords}" fill="{e.get("fill") or "none"}" stroke="{e.get("stroke") or "none"}" stroke-width="{e.get("width",.15)}" stroke-linejoin="round"{dash}/>')
    parts.append('</svg>');Path(path).write_text('\n'.join(parts),encoding='utf-8')


def legacy_style_items(scene,items,generated=None):
    import re
    result=[]
    def owner(oid):
        if oid in scene.assets:return scene.assets[oid]
        mid=oid.split(':')[0]
        if mid in scene.movements:return dict(props=scene.movements[mid])
        if oid.startswith('J:'):
            for aid,a in scene.assets.items():
                if aid in oid:return a
        if oid.startswith('AUTO:'):
            owner_id=oid.split(':')[1];base=scene.assets.get(owner_id);props=dict(base['props']) if base else dict(scene.movements.get(owner_id,{}))
            if generated and oid in generated:props.update(generated[oid]['props'])
            return dict(props=props)
        return None
    for item in items:
        item=dict(item);surface=item['type']=='polygon' and item.get('fill') in (COLORS['runway'],COLORS['taxiway'],COLORS['apron'],COLORS['shoulder']);a=owner(item.get('oid',''));p=a['props'] if a else {}
        p=dict(p,black_outline=p.get('black_outline',False) or scene.data['meta'].get('guidance_black_outline',False))
        if item.get('fill') in (COLORS['runway'],COLORS['taxiway'],COLORS['apron']):item['fill']=p.get('pavement_color',item['fill'])
        elif item.get('fill')==COLORS['shoulder']:item['fill']=p.get('shoulder_color',item['fill'])
        for key in ('pavement_color','shoulder_color'):
            if key in p and not re.fullmatch(r'#[0-9a-fA-F]{6}',p[key]):raise ValueError('颜色请使用 #RRGGBB 格式')
        if p.get('black_outline',False):
            if item['type']=='line' and item.get('stroke') not in (None,'#101010','#151a20'):
                under=dict(item,stroke='#101010',width=item.get('width',.15)+.1)
                if item.get('stroke')==COLORS['marking']:
                    from editor6_geometry import outside_runways
                    result.extend(outside_runways(scene,under))
                else:result.append(under)
            elif item['type']=='text':item['black_outline']=True
            elif item['type']=='polygon' and not surface and (item.get('fill') or item.get('stroke')):
                result.append(dict(item,fill=None,stroke='#101010',width=(item.get('width',.1) if item.get('stroke') else 0)+.1))
        result.append(item)
    return result


from paint10 import style as style_items

