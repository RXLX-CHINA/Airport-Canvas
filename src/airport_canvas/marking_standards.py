"""Shared physical geometry and checks for hand-drawn and derived markings.

Sources: MH5001-2021 6.2 and user supplied 2013 8.2 article. Checks do not
replace aircraft swept paths, ILS-sensitive areas or operational approval.
"""
import math
import scene_geometry as g


def permanently_closed(scene,oid):
    a=scene.assets.get(oid)
    if a:
        if a['props'].get('turn_pad'):return permanently_closed(scene,a['props'].get('pad_runway'))
        return a['props'].get('closed',False) and a['props'].get('closure_kind')=='PERMANENT'
    m=scene.movements.get(oid)
    return bool(m and any(permanently_closed(scene,m[k]['asset']) for k in ('from','to')))


def closure_routes(scene):
    from lighting_closures import pavement_closures
    from model20 import axes
    closed = pavement_closures(scene)
    return {**scene.assets,**axes(scene)} if closed else scene.assets,closed


def closure_components(scene):
    from automatic_markings import synthetic
    result={}
    assets,closed = closure_routes(scene)
    for aid in sorted(closed):
        a = assets.get(aid)
        if not a or a['kind'] not in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
        # CLOSED_AREA is an explicit partial closure, not a whole-route closure.
        key='CLOSED_RWY' if a['kind']=='RUNWAY' else 'CLOSED_TWY';total=g.length(a['points']);width=a['props']['width']
        mark_width=min(14.5 if key=='CLOSED_RWY' else 9,width)
        extent=36*mark_width/14.5 if key=='CLOSED_RWY' else mark_width/math.sqrt(2)+mark_width/6/math.sqrt(2)
        lo=min(total/2,extent/2);hi=max(total/2,total-extent/2);count=max(1,math.ceil((hi-lo)/300))
        stations=[lo+(hi-lo)*i/count for i in range(count+1)] if hi>lo+.01 else [total/2]
        for i,s in enumerate(stations):
            q,u=g.at(a['points'],s)
            mark=synthetic(aid,key,[q,[q[k]+u[k]*10 for k in (0,1)]],'CLOSURE:'+str(i),width=mark_width)
            result[mark['id']]=mark
    return result


def closure_entries(scene):
    from automatic_markings import synthetic
    from geometry11 import LineString, Point, parts, polygon
    from pavement_geometry import corridor
    kinds={'RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD','APRON','CLOSED_AREA'}
    routes_by_id,derived = closure_routes(scene)
    assets=[a for a in routes_by_id.values() if a['kind'] in kinds]
    closed={a['id'] for a in assets if a['id'] in derived
            or a['kind']=='CLOSED_AREA' or (a['props'].get('turn_pad') and scene.is_closed(a['props']['pad_runway']))}
    if not closed:return {}
    route_lines = [(a,LineString(a['points'])) for a in assets if a['kind'] not in ('APRON','CLOSED_AREA')]
    routes = [(a,line) for a,line in route_lines if a['id'] not in closed]
    explicit = set(scene.scenario['closed_assets'])
    result={}
    for asset in assets:
        aid=asset['id']
        if aid not in closed:continue
        pts=asset['points']
        area=asset['kind'] in ('APRON','CLOSED_AREA')
        mask=polygon(pts if area else corridor(pts,asset['props']['width']))
        entries=[]
        approaches=routes
        if asset['kind'] in ('RUNWAY','APRON'):
            # Retain boundary warnings when a connecting taxiway also closes.
            approaches = [(a,line) for a,line in route_lines if a['id']!=aid
                          and a['id'] not in explicit and not a['props'].get('closed')]
        if asset['kind']=='RUNWAY':
            from junction_routes import branches
            for mid,m in scene.movements.items():
                if not m.get('enabled',True) or not m.get('pavement_visible',True) or m.get('legacy_attachment'):continue
                if aid not in (m['from']['asset'],m['to']['asset']):continue
                paths=[(mid,scene.movement_path(mid))]
                paths.extend((b['oid'],b['points']) for b in branches(scene,m)
                             if m.get('reverse_join_pavement',True))
                for oid,points in paths:
                    if len(points)>1 and g.length(points)>.05:
                        approaches.append((dict(id=oid,points=points,props={'width':m['width']}),LineString(points)))
        boundary=mask.boundary
        touch_mask=mask.buffer(.001)
        for route,line in approaches:
            hits=line.intersection(boundary)
            stations={line.project(hit) for hit in parts(hits,('Point',))}
            for overlap in parts(hits,('LineString',)):
                stations.update(line.project(Point(overlap.coords[i])) for i in (0,-1))
            for index,station in enumerate(sorted(stations)):
                for travel in (1,-1):
                    outside=station-travel*2
                    inside=station+travel*.35
                    if not 0<=outside<=line.length:continue
                    inside=max(0,min(line.length,inside))
                    if mask.covers(line.interpolate(outside)) or not touch_mask.covers(line.interpolate(inside)):continue
                    p=g.at(route['points'],station-travel*min(5,station if travel>0 else line.length-station))[0]
                    _,u=g.at(route['points'],station)
                    heading=[x*travel for x in u]
                    if any(g.distance(p,q)<1 and sum(x*y for x,y in zip(heading,v))>.95 for _,q,v,_ in entries):
                        continue
                    entries.append((f"{route['id']}:{index}:{travel}",p,heading,route['props']['width']))
        if not entries and not area:
            length=g.length(pts)
            for index,travel in enumerate((1,-1)):
                q,u=g.at(pts,min(7,length/4) if travel>0 else length-min(7,length/4))
                entries.append((str(index),q,[x*travel for x in u],asset['props']['width']))
        if not entries and area and not mask.is_empty:
            from shapely.geometry.polygon import orient
            for index,part in enumerate(parts(mask,('Polygon',))):
                ring=list(orient(part,sign=1.).exterior.coords)
                a,b=max(zip(ring,ring[1:]),key=lambda pair:g.distance(*pair))
                u=g.unit(a,b)
                normal=[-u[1],u[0]]
                point=[(a[k]+b[k])/2+2*normal[k] for k in (0,1)]
                if not part.covers(Point(point)):point=list(part.representative_point().coords[0])
                entries.append((f'area:{index}',point,normal,min(23,g.distance(a,b))))
        for key,q,u,width in entries:
            height=max(.25,min(2.,(width-1)/3.2))
            mark=synthetic(aid,'NO_ENTRY',[q,[q[k]+10*u[k] for k in (0,1)]],
                           'CLOSURE_ENTRY:'+key,text_height=height,closure_entry_width=width)
            result[mark['id']]=mark
    return result


def no_entry_boards(scene,marks):
    from automatic_markings import synthetic
    from signs21_2 import sign_props
    result={}
    sites={}
    for mark in marks:
        p=mark['props']
        if p.get('mark_type')!='NO_ENTRY' or p.get('hidden'):continue
        if scene.data['generated_overrides'].get(mark['id'],{}).get('hidden'):continue
        owner=mark.get('owner') or p.get('label_asset') or mark['id']
        key=(owner,p.get('reverse_site31','REVERSE')) if p.get('reverse_entry13') else (owner,mark['id'])
        sites.setdefault(key,[]).append(mark)
    if not sites:return result
    from boards24 import pavement
    from shapely import Point
    mask=pavement(scene)
    accepted=[]
    for (owner,_),rows in sites.items():
        mark=min(rows,key=lambda item:item['id'])
        p=mark['props']
        q=[sum(row['points'][0][k] for row in rows)/len(rows) for k in (0,1)]
        u=g.unit(mark['points'][0],mark['points'][-1])
        v=(-u[1],u[0])
        asset=scene.assets.get(owner)
        axis=asset if asset and asset['kind'] in ('TAXIWAY','RUNWAY','ROAD','APRON_TAXIWAY','STAND_TAXILANE') else None
        if p.get('reverse_width31') is not None:
            width=p['reverse_width31']
        elif p.get('closure_entry_width') is not None:
            width=p['closure_entry_width']
        elif owner in scene.movements:
            width=scene.movements[owner]['width']
        elif axis:
            width=axis['props']['width']
            if not mark.get('owner'):_,_,q=g.project(axis['points'],q)
        else:
            width=p.get('width',23)
        # Ground inscriptions at the same mouth share one board layout.
        if any(abs(sum((q[k]-old[k])*u[k] for k in (0,1)))<3
               and abs(sum((q[k]-old[k])*v[k] for k in (0,1)))<min(width,old_width)/2
               and sum(u[k]*heading[k] for k in (0,1))>.97
               for old,heading,old_width in accepted):
            continue
        accepted.append((q,u,width))
        for side,sign in (('LEFT',1),('RIGHT',-1)):
            props=sign_props('',[],True,side,width)
            props.update(sign_role23='NO_ENTRY_BOARD',standard_clause20_18='8.3.8')
            # A merge can have no local verge on one side. Limit the
            # transverse search to the approach so a board stays with it.
            distance=width/2+1
            limit=width/2+max(12,width*.55)
            while distance<=limit:
                anchor=[q[k]+sign*v[k]*distance for k in (0,1)]
                if mask.distance(Point(anchor))>=1.25:
                    break
                distance+=.5
            else:
                continue
            board=synthetic(owner,'DIRECTION',[anchor,[anchor[k]+10*u[k] for k in (0,1)]],
                            'NO_ENTRY_BOARD:'+mark['id']+':'+side,**props)
            result[board['id']]=board
    return result


def outside_segments(points,polygons,margin=0):
    """Exact segment/polygon boundary cuts, retaining world-distance dash phase."""
    if margin:
        from pavement_geometry import area,line_intersection
        expanded=[]
        for poly in polygons:
            sign=-1 if area(poly)>0 else 1;ring=[]
            for i,q in enumerate(poly):
                before=g.unit(poly[i-1],q);after=g.unit(q,poly[(i+1)%len(poly)])
                a=[q[0]-before[1]*margin*sign,q[1]+before[0]*margin*sign]
                b=[q[0]-after[1]*margin*sign,q[1]+after[0]*margin*sign]
                ring.append(line_intersection(a,before,b,after) or [(a[k]+b[k])/2 for k in (0,1)])
            expanded.append(ring)
        yield from outside_segments(points,expanded)
        return
    travelled=0
    for a,b in zip(points,points[1:]):
        length=g.distance(a,b)
        if length<1e-10:continue
        cuts={0.,1.};u=g.unit(a,b)
        for poly in polygons:
            for c,d in zip(poly,poly[1:]+poly[:1]):
                hit=g.crossing(a,b,c,d)
                if hit:
                    t=max(0,min(1,((hit[0]-a[0])*u[0]+(hit[1]-a[1])*u[1])/length))
                    cuts.add(t)
        values=sorted(cuts)
        for lo,hi in zip(values,values[1:]):
            if hi-lo<1e-10:continue
            mid=[a[k]+(b[k]-a[k])*(lo+hi)/2 for k in (0,1)]
            if any(g.inside(mid,p) for p in polygons):continue
            yield [[a[k]+(b[k]-a[k])*lo for k in (0,1)],[a[k]+(b[k]-a[k])*hi for k in (0,1)]],travelled+lo*length
        travelled+=length


def interrupt_paint(scene,items,generated):
    """Taxi guidance yields to white runway paint; bridge zone keeps priority."""
    from marking_catalog import YELLOW,WHITE,RED
    marks={k:a for k,a in scene.assets.items() if a['kind']=='MARKING'};marks.update(generated)
    white=[];bridges=[];holds=[]
    for item in items:
        mark=marks.get(item.get('oid'))
        if item['type']=='polygon' and item.get('fill')==WHITE:
            if mark and mark['props']['mark_type'] in ('RWY_THRESHOLD','AIMING_POINT','TDZ_BASIC','TDZ_CODED','THRESHOLD_HEADS','DISPLACED_ARROW'):white.append(item['points'])
        elif item['type']=='line' and item.get('stroke')==WHITE and mark and mark['props']['mark_type'] in ('THRESHOLD_BAR','DISPLACED_ARROW','THRESHOLD_HEADS','RWY_CENTER'):
            from pavement_geometry import corridor
            white.append(corridor(item['points'],item.get('width',.15)))
    for mark in marks.values():
        key=mark['props']['mark_type']
        if key in ('BRIDGE_AREA','BRIDGE_COMPOSITE'):bridges.append(mark['points'])
        if key in ('HOLD_A','HOLD_B','INTERMEDIATE_POINT'):
            q=mark['points'][0];u=g.unit(*[mark['points'][i] for i in (0,-1)]);half=1.05 if key in ('HOLD_A','HOLD_B') else .15
            holds.append(g.rectangle([[q[k]-u[k]*half for k in (0,1)],[q[k]+u[k]*half for k in (0,1)]],mark['props']['width']))
        elif key=='INTERMEDIATE':holds.append(__import__('pavement_geometry').corridor(mark['points'],.3))
    # Spatial culling avoids checking each tiny segment against every paint polygon.
    white_boxes=[(min(p[0] for p in x),min(p[1] for p in x),max(p[0] for p in x),max(p[1] for p in x),x) for x in white+holds]
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY']
    def rank(a):
        levels=[a['props'].get('level_'+end,'1') for end in ('a','b')]
        return max(0 if x=='v' else 1 if x=='0' else 2 for x in levels)
    output=[]
    for item in items:
        mark=marks.get(item.get('oid'));key=mark['props']['mark_type'] if mark else ''
        owner=(mark.get('owner') or mark['props'].get('label_asset')) if mark else item.get('oid')
        if (permanently_closed(scene,owner) and key not in ('CLOSED_RWY','CLOSED_TWY','NO_ENTRY')
                and (mark or {}).get('props',{}).get('sign_role23')!='NO_ENTRY_BOARD'):
            # Pavement polygons remain, all normal route paint is suppressed.
            if not (mark is None and item['type']=='polygon' and item.get('fill') not in (None,YELLOW,WHITE,RED)):continue
        runway=scene.assets.get(owner)
        if runway and runway['kind']=='RUNWAY' and (item.get('stroke')==WHITE or item.get('fill')==WHITE):
            higher=[g.rectangle(r['points'],r['props']['width']) for r in runways if rank(r)>rank(runway)]
            if higher:
                if item['type']=='line':
                    for points,station in outside_segments(item['points'],higher):output.append(dict(item,points=points,dash_offset=item.get('dash_offset',0)+station))
                elif item['type']=='polygon':
                    from pavement_geometry import subtract_convex
                    pieces=[item['points']]
                    for polygon in higher:pieces=[q for x in pieces for q in subtract_convex(x,polygon)]
                    output.extend(dict(item,points=x) for x in pieces)
                elif not any(g.inside(item['points'][0],x) for x in higher):output.append(item)
                continue
        if item['type']!='line':output.append(item);continue
        polygons=[];margin=0
        guidance=(item.get('stroke')==YELLOW and (not key or key in ('LEAD_IN','LEAD_OUT','AUX_LEAD','ICAO_AUX_LEAD','TURN_PAD_GUIDE','TWY_CENTER','TWY_ENHANCED','ALIGNMENT')))
        if guidance:
            pts=item['points'];x0=min(p[0] for p in pts)-1;y0=min(p[1] for p in pts)-1;x1=max(p[0] for p in pts)+1;y1=max(p[1] for p in pts)+1
            polygons=[poly for a,b,c,d,poly in white_boxes if a<=x1 and c>=x0 and b<=y1 and d>=y0];margin=.9+item.get('width',.15)/2
        if key in ('STAND_SAFETY','WINGTIP','ROAD_EDGE','ROAD_STAGGER'):polygons+=bridges
        if not polygons:output.append(item);continue
        for points,station in outside_segments(item['points'],polygons,margin):
            output.append(dict(item,points=points,dash_offset=item.get('dash_offset',0)+station))
    return output


def marking_checks(scene,generated=None):
    """Actionable failures for all catalog objects; no blanket compliance PASS."""
    from marking_catalog import CATALOG
    from automatic_markings import generated_markings
    if generated is None:generated=generated_markings(scene)
    marks=[a for a in scene.assets.values() if a['kind']=='MARKING']+list(generated.values());issues=[]
    def fail(a,rule,message,actual,required,clause):
        issues.append(dict(object_id=a['id'],status='FAIL',rule=rule,message=message,actual=actual,required=required,source=clause))
    mins={'TWY_CENTER':.15,'LEAD_IN':.15,'LEAD_OUT':.15,'AUX_LEAD':.15,'ICAO_AUX_LEAD':.15,'ALIGNMENT':.15,'TURN_PAD_GUIDE':.15,'STAND_SAFETY':.1}
    fixed={'TWY_EDGE':.15,'WINGTIP':.15,'HOLD_A':.3,'HOLD_B':.3,'INTERMEDIATE':.3,'INTERMEDIATE_POINT':.3,'TWY_SHOULDER':.9,'VOR':.15,'VOR_DIRECTION':.15,'SPEED':.15,'CHOCKS':.15,'ROAD_STAGGER':.15}
    for a in marks:
        p=a['props'];key=p['mark_type'];spec=CATALOG[key];lw=p.get('line_width',.15)
        minimum=mins.get(key)
        if minimum and lw<minimum:fail(a,'MARK_WIDTH', '标志线宽不足',lw,minimum,spec['clause'])
        if key in fixed and abs(lw-fixed[key])>1e-6:fail(a,'MARK_WIDTH','标志线宽不符',lw,fixed[key],spec['clause'])
        if key in ('TWY_EDGE','WINGTIP') and abs(p['spacing']-(.15 if key=='TWY_EDGE' else .1))>1e-6:fail(a,'DOUBLE_CLEAR_GAP','双线净距不符',p['spacing'],.15 if key=='TWY_EDGE' else .1,spec['clause'])
        if key=='RWY_NUMBER' and p['text_height']<9:fail(a,'NUMBER_HEIGHT','跑道号码字高不足',p['text_height'],'>=9 m',spec['clause'])
        if p.get('information_profile20_18')!='BOARD' and key in ('MANDATORY','NO_ENTRY','LOCATION','DIRECTION','MAX_SPAN','HP') and p['text_height']<2:fail(a,'LABEL_HEIGHT','地面文字标志字高不足',p['text_height'],'>=2 m; normally 4 m',spec['clause'])
        if key=='SPEED' and (p['width']<1.5 or abs(p['text_height']-1)>1e-6):fail(a,'SPEED_SIZE','限速标志直径/字高不符',[p['width'],p['text_height']],'>=1.5 m / 1 m',spec['clause'])
        if key in ('VOR','VOR_DIRECTION') and abs(p['width']-6)>1e-6:fail(a,'VOR_SIZE','VOR圆外径应为6m',p['width'],6,spec['clause'])
        if key=='TWY_SHOULDER' and (p['width']>7.5 or p['spacing']>15):fail(a,'SHOULDER_SIZE','道肩条带长度/间距超限',[p['width'],p['spacing']],'<=7.5 m / <=15 m',spec['clause'])
        if key=='ROAD_STAGGER' and not .5<=p.get('dash',.75)<=1:fail(a,'ROAD_DASH','服务车道交错线长度不符',p.get('dash'),'.5..1 m',spec['clause'])
        if key in ('CLOSED_RWY','CLOSED_TWY') and p['width']<(14.5 if key=='CLOSED_RWY' else 9):fail(a,'CLOSED_SIZE','关闭标志小于标准最小尺寸',p['width'],14.5 if key=='CLOSED_RWY' else 9,spec['clause'])
        if key in ('AIMING_POINT','TDZ_BASIC','TDZ_CODED') and p.get('label_asset') in scene.assets:
            surface=scene.assets[p['label_asset']];ink=__import__('marking_catalog').primitives(a)
            if any(g.project(surface['points'],q)[0]>surface['props']['width']/2+.001 for x in ink for q in x['points']):fail(a,'MARK_PAVEMENT','标志条块越出关联道面',None,'条块完全位于道面内',spec['clause'])
    return issues
