"""Dependency-free vector pavement clipping and intersection fillets.

All geometry is computed in metres, independently of viewport zoom.
Runway rectangles are subtracted from taxi pavement, never from guidance.
"""
import math
import scene_geometry as g

def offset(points,value):
    out=[]
    for i,p in enumerate(points):
        before=g.unit(points[max(0,i-1)],p) if i else g.unit(p,points[1])
        after=g.unit(p,points[i+1]) if i<len(points)-1 else before
        a=[p[0]-before[1]*value,p[1]+before[0]*value]
        b=[p[0]-after[1]*value,p[1]+after[0]*value]
        hit=line_intersection(a,before,b,after)
        out.append(hit if hit and g.distance(hit,p)<max(.01,abs(value)*4) else [(a[0]+b[0])/2,(a[1]+b[1])/2])
    return out

def corridor_parts(points,width):
    ring=offset(points,width/2)+list(reversed(offset(points,-width/2)))
    if len(points)<3:return [ring]
    from geometry11 import LineString,Polygon,polygons
    if Polygon(ring).is_valid:return [ring]
    # When the inside radius collapses, the swept footprint has no inside
    # offset loop. Rebuild the outline from the path instead of polygonizing
    # the intersecting offset segments into phantom islands.
    swept=LineString(points).buffer(width/2,cap_style=2,join_style=1)
    return [[list(q) for q in part.exterior.coords][:-1] for part in polygons(swept)]

def corridor(points,width):
    """Return the main outline for callers that consume one ring."""
    return max(corridor_parts(points,width),key=lambda ring:abs(area(ring)),default=[])

def area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2

def halfplane(poly,a,b,keep_inside=True):
    if not poly:return []
    def value(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    sign=1 if keep_inside else -1;result=[]
    previous=poly[-1];v0=value(previous)*sign
    for current in poly:
        v1=value(current)*sign
        if (v0>=-1e-9)!=(v1>=-1e-9):
            t=v0/(v0-v1)
            result.append([previous[0]+t*(current[0]-previous[0]),previous[1]+t*(current[1]-previous[1])])
        if v1>=-1e-9:result.append(list(current))
        previous=current;v0=v1
    return result if len(result)>=3 and abs(area(result))>1e-8 else []

def subtract_convex(poly,clip):
    """Partition polygon outside a convex clip into non-overlapping pieces."""
    clip=list(clip) if area(clip)>0 else list(reversed(clip));remaining=list(poly);result=[]
    for a,b in zip(clip,clip[1:]+clip[:1]):
        outside=halfplane(remaining,a,b,False)
        if outside:result.append(outside)
        remaining=halfplane(remaining,a,b,True)
        if not remaining:break
    return result

def exclude_runways(poly,runways):
    pieces=[poly]
    for r in runways:
        clip=g.rectangle(r['points'],r['props']['width'])
        pieces=[piece for p in pieces for piece in subtract_convex(p,clip)]
    return pieces

def circle_arc(center,start,end,steps=30):
    a=math.atan2(start[1]-center[1],start[0]-center[0]);b=math.atan2(end[1]-center[1],end[0]-center[0])
    delta=(b-a+math.pi)%(2*math.pi)-math.pi;r=g.distance(center,start)
    return [[center[0]+r*math.cos(a+delta*i/steps),center[1]+r*math.sin(a+delta*i/steps)] for i in range(steps+1)]

def line_intersection(p,u,q,v):
    den=u[0]*v[1]-u[1]*v[0]
    if abs(den)<1e-9:return None
    d=(q[0]-p[0],q[1]-p[1]);t=(d[0]*v[1]-d[1]*v[0])/den
    return [p[0]+t*u[0],p[1]+t*u[1]]

def corner_patch(center,ua,ub,half_a,half_b,radius):
    """Concave pavement corner bounded by two outward rays and tangent arc."""
    na=(-ua[1],ua[0]);nb=(-ub[1],ub[0])
    # Pick offset edge of each arm facing the other arm.
    sa=1 if na[0]*ub[0]+na[1]*ub[1]>0 else -1
    sb=1 if nb[0]*ua[0]+nb[1]*ua[1]>0 else -1
    pa=[center[0]+na[0]*half_a*sa,center[1]+na[1]*half_a*sa]
    pb=[center[0]+nb[0]*half_b*sb,center[1]+nb[1]*half_b*sb]
    c=line_intersection(pa,ua,pb,ub)
    if c is None:return None
    dot=max(-.99999,min(.99999,ua[0]*ub[0]+ua[1]*ub[1]));angle=math.acos(dot)
    if angle<math.radians(15) or angle>math.radians(165):return None
    tangent=radius/math.tan(angle/2)
    a=[c[0]+ua[0]*tangent,c[1]+ua[1]*tangent];b=[c[0]+ub[0]*tangent,c[1]+ub[1]*tangent]
    bis=(ua[0]+ub[0],ua[1]+ub[1]);size=math.hypot(*bis)
    cc=[c[0]+bis[0]/size*radius/math.sin(angle/2),c[1]+bis[1]/size*radius/math.sin(angle/2)]
    arc=circle_arc(cc,a,b)
    # Extend the hidden tangent edges into each adjoining corridor. The
    # exposed arc stays unchanged, while independently sampled faces overlap.
    overlap=.025
    def inset(point,normal,side):
        return [point[k]-normal[k]*side*overlap for k in (0,1)]
    welds=[[c,a,inset(a,na,sa),inset(c,na,sa)],
           [c,b,inset(b,nb,sb),inset(c,nb,sb)]]
    return dict(polygon=[c]+arc,arc=arc,corner=c,welds=welds)

def shoulder_width(kind,props,default=0.):
    return 0. if kind=='APRON_TAXIWAY' else props.get('shoulder',default)


def route_objects(scene):
    cache=getattr(scene,'_route_cache',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth:return cache[1]
    routes={k:a for k,a in scene.assets.items() if a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')}
    for mid,m in scene.movements.items():
        if m.get('legacy_attachment') or not m.get('pavement_visible',True):continue
        if m['role'] in ('STAND_ENTRY','PUSHBACK'):
            a=scene.assets[m['from']['asset']];b=scene.assets[m['to']['asset']]
            if a['props'].get('parent_id') and a['props'].get('parent_id')==b['props'].get('parent_id'):continue
        points=scene.movement_path(mid)
        if g.length(points)<.1:continue
        routes[mid]=dict(id=mid,name=m['name'],kind=m.get('taxiway_kind39','TAXIWAY'),points=points,props=dict(width=m['width'],shoulder=m.get('shoulder',7.5),fillet_radius=m.get('fillet_radius',25),turn_radius=m.get('turn_radius',25)))
    if not scene._transaction_depth:scene._route_cache=(scene.revision,routes)
    return routes

def crossings(scene):
    cache=getattr(scene,'_cross_cache',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth:return cache[1]
    routes=list(route_objects(scene).values())
    boxes={a['id']:(min(p[0] for p in a['points']),min(p[1] for p in a['points']),max(p[0] for p in a['points']),max(p[1] for p in a['points'])) for a in routes}
    found=[]
    bindings={}
    for movement in scene.movements.values():
        if movement.get('legacy_attachment'):
            names=frozenset(movement[side]['asset'] for side in ('from','to'))
            bindings.setdefault(names,[]).append(movement)
    endpoint_tolerance=.02
    for i,a in enumerate(routes):
        for b in routes[i+1:]:
            if a['kind']==b['kind']=='RUNWAY':continue
            x0,y0,x1,y1=boxes[a['id']];xx0,yy0,xx1,yy1=boxes[b['id']]
            linked=bindings.get(frozenset((a['id'],b['id'])),())
            if not linked and (x1+endpoint_tolerance<xx0 or xx1+endpoint_tolerance<x0
                               or y1+endpoint_tolerance<yy0 or yy1+endpoint_tolerance<y0):continue
            pair=[];oa=0
            for p,q in zip(a['points'],a['points'][1:]):
                ob=0
                for r,s in zip(b['points'],b['points'][1:]):
                    hit=g.crossing(p,q,r,s)
                    if hit is not None and not any(g.distance(hit,x['point'])<.2 for x in pair):
                        attached=False
                        for first,other in ((a,b),(b,a)):
                            if first['id'] in scene.movements:
                                m=scene.movements[first['id']]
                                if other['id'] in (m['from']['asset'],m['to']['asset']) and min(g.distance(hit,first['points'][0]),g.distance(hit,first['points'][-1]))<1:attached=True
                        if not attached:
                            pair.append(dict(point=hit,assets=[a['id'],b['id']],stations=[oa+g.distance(p,hit),ob+g.distance(r,hit)],tangents=[g.unit(p,q),g.unit(r,s)]))
                    ob+=g.distance(r,s)
                oa+=g.distance(p,q)
            if a['id'] in scene.assets and b['id'] in scene.assets:
                def add_contact(stations,limit,child_index=None):
                    poses=[g.at(route['points'],station) for route,station in zip((a,b),stations)]
                    if g.distance(poses[0][0],poses[1][0])>limit:return
                    point=poses[1-child_index][0] if child_index is not None else poses[0][0]
                    if any(g.distance(point,j['point'])<.2 for j in pair):return
                    pair.append(dict(point=point,assets=[a['id'],b['id']],stations=stations,
                                     tangents=[pose[1] for pose in poses],endpoint_contact62=True))
                for link in linked:
                    ports={link[k]['asset']:link[k] for k in ('from','to')}
                    child=0 if link['to']['asset']==a['id'] else 1
                    stations=[ports[route['id']]['station'] for route in (a,b)]
                    length=g.length((a,b)[child]['points'])
                    if min(stations[child],length-stations[child])<=.15:
                        add_contact(stations,.25,child)
                for index,(route,other) in enumerate(((a,b),(b,a))):
                    length=g.length(route['points'])
                    for station,point in ((0.,route['points'][0]),(length,route['points'][-1])):
                        distance,target,_=g.project(other['points'],point)
                        if distance>endpoint_tolerance:continue
                        stations=[station,target] if index==0 else [target,station]
                        add_contact(stations,endpoint_tolerance,index)
            pair.sort(key=lambda x:x['stations'][0])
            for idx,item in enumerate(pair):item['id']='J:'+a['id']+':'+b['id']+':'+str(idx);found.append(item)
    if not scene._transaction_depth:scene._cross_cache=(scene.revision,found)
    return found

def junction_arm(points,station,sign,half_width=0.):
    """Find the outward tangent and usable reach before the offset edge bends."""
    end=0. if sign<0 else g.length(points)
    path=g.subpath(points,station,end)
    origin=path[0]
    previous=origin
    heading=None
    reach=0.
    for point in path[1:]:
        length=g.distance(previous,point)
        if length<1e-6:continue
        direction=g.unit(previous,point)
        if heading is None:heading=direction
        cosine=max(-1.,min(1.,sum(x*y for x,y in zip(heading,direction))))
        angle=math.acos(cosine)
        if angle>math.radians(10):
            # The inside edge of a miter turns before the centreline vertex.
            setback=half_width*math.tan(min(angle,math.radians(170))/2)
            return heading,max(0.,reach-setback)
        drift=abs((point[0]-origin[0])*heading[1]-(point[1]-origin[1])*heading[0])
        if drift>.15:
            prior=abs((previous[0]-origin[0])*heading[1]-(previous[1]-origin[1])*heading[0])
            return heading,reach+length*max(0.,(.15-prior)/(drift-prior))
        reach+=length
        previous=point
    return heading or (1.,0.),reach


def fillets(scene,junction,outer=False):
    routes=route_objects(scene);a,b=[routes[k] for k in junction['assets']];r=min(a['props'].get('fillet_radius',25),b['props'].get('fillet_radius',25))
    pa,pb=a['props'],b['props'];shoulder=min(shoulder_width(a['kind'],pa),shoulder_width(b['kind'],pb))
    r=max(.5,r-shoulder) if outer else r
    wa=pa['width']/2+(shoulder_width(a['kind'],pa) if outer else 0)
    wb=pb['width']/2+(shoulder_width(b['kind'],pb) if outer else 0)
    patches=[]
    arms=[{sign:junction_arm(route['points'],station,sign,half)
           for sign in (-1,1)}
          for route,station,half in zip((a,b),junction['stations'],(wa,wb))]
    for sa in (-1,1):
        for sb in (-1,1):
            ua,reach_a=arms[0][sa];ub,reach_b=arms[1][sb]
            available=(reach_a,reach_b)
            if min(available)<.01:continue
            candidate=r
            for attempt in range(9):
                patch=corner_patch(junction['point'],ua,ub,wa,wb,candidate)
                if patch:
                    reach=[sum((point[k]-junction['point'][k])*ray[k] for k in (0,1)) for point,ray in ((patch['arc'][0],ua),(patch['arc'][-1],ub))]
                    if all(0<=reach[i]<=available[i]+1e-6 for i in (0,1)):
                        # Stitch each tangent edge to its actual centreline.
                        # The finite arms may curve away from the tangent line.
                        for i,(route,ray,sign,tip) in enumerate(((a,ua,sa,patch['arc'][0]),
                                                                 (b,ub,sb,patch['arc'][-1]))):
                            corner=patch['corner'];origin=junction['point']
                            start=max(0.,sum((corner[k]-origin[k])*ray[k] for k in (0,1)))
                            finish=reach[i]
                            if finish<=start:continue
                            inner=[g.at(route['points'],junction['stations'][i]+sign*d)[0]
                                   for d in (finish,start)]
                            patch['welds'].append([corner,tip,*inner])
                        patches.append(patch)
                        break
                candidate*=.5
    return patches

def turn_guides(scene,junction,visible_only=True,endpoint_budgets=None):
    if endpoint_budgets is None and any(scene.assets.get(aid,{}).get('props',{}).get('terminal_backup13') for aid in junction['assets']):
        candidate=rounded_terminal_joins(scene,crossings(scene))[1].get(junction['id'])
        if candidate:
            arc,assets,_,_=candidate
            key=':'.join('1' if s<g.length(a['points'])/2 else '-1' for s,a in zip(junction['stations'],assets))
            if visible_only and not scene.data.get('junctions',{}).get(junction['id'],{}).get('guides',{}).get(key,True):return []
            return [dict(key=key,points=arc,label=' / '.join(a['name'] for a in assets))]

    # An explicit connector already describes this movement. Synthesizing an
    # additional turn at its own parent anchor creates the spurious return loop.
    for oid in junction['assets']:
        m=scene.movements.get(oid)
        if m and any(other in (m['from']['asset'],m['to']['asset']) for other in junction['assets'] if other!=oid):return []
    routes=route_objects(scene);a,b=[routes[k] for k in junction['assets']];result=[]
    config=scene.data.get('junctions',{}).get(junction['id'],{})
    radius=config.get('radius',min(a['props'].get('turn_radius',25),b['props'].get('turn_radius',25)))
    visible=config.get('guides',{})
    for side_a in (-1,1):
        for side_b in (-1,1):
            key=f'{side_a}:{side_b}'
            if visible_only and not visible.get(key,True):continue
            from pavement10 import runway_terminal
            if any(route['kind']=='RUNWAY' and (end:=runway_terminal(route,station))
                   and side!=end[2] for route,station,side in zip(
                       (a,b),junction['stations'],(side_a,side_b))):continue
            oa,reach_a=junction_arm(a['points'],junction['stations'][0],side_a)
            ob,reach_b=junction_arm(b['points'],junction['stations'][1],side_b)
            angle=math.acos(max(-.99999,min(.99999,sum(x*y for x,y in zip(oa,ob)))))
            if not math.radians(15)<angle<math.radians(178):continue
            available=[reach_a,reach_b]
            if min(available)<.01:continue
            if endpoint_budgets:
                available=[min(room,endpoint_budgets.get(route['id'],room)) for room,route in zip(available,(a,b))]
            local_radius=radius
            tangent=local_radius/math.tan(angle/2)
            if min(available)<tangent:
                tangent=min(available)*.98
                local_radius=tangent*math.tan(angle/2)
            c=junction['point'];p=[c[i]+oa[i]*tangent for i in (0,1)];q=[c[i]+ob[i]*tangent for i in (0,1)]
            bis=[oa[i]+ob[i] for i in (0,1)];size=math.hypot(*bis)
            cc=[c[i]+bis[i]/size*local_radius/math.sin(angle/2) for i in (0,1)]
            arc=circle_arc(cc,p,q)
            arc_length=g.length(arc)
            for index,(route,station,side) in enumerate(zip((a,b),junction['stations'],(side_a,side_b))):
                endpoint=0 if index==0 else -1
                target=g.at(route['points'],station+side*tangent)[0]
                delta=[target[k]-arc[endpoint][k] for k in (0,1)]
                displacement=math.hypot(*delta)
                if displacement<1e-6:
                    arc[endpoint]=target
                    continue
                span=min(arc_length*.45,max(3*displacement,arc_length*.18))
                distance=0.
                indices=range(len(arc)) if index==0 else range(len(arc)-1,-1,-1)
                previous=None
                for i in indices:
                    point=arc[i]
                    if previous is not None:distance+=g.distance(previous,point)
                    if distance>=span:break
                    previous=point
                    t=1-distance/span
                    weight=t*t*(3-2*t)
                    arc[i]=[point[k]+weight*delta[k] for k in (0,1)]
            # A curved arm can turn appreciably between the intersection and
            # the contact station. Match the live centreline tangent there.
            contacts=[]
            for route,station,side,travel in ((a,junction['stations'][0],side_a,-side_a),
                                              (b,junction['stations'][1],side_b,side_b)):
                _,direction=g.at(route['points'],station+side*tangent)
                contacts.append([travel*value for value in direction])
            tangents=(g.unit(arc[0],arc[1]),g.unit(arc[-2],arc[-1]))
            from shapely.geometry import LineString
            if (not LineString(arc).is_simple or
                any(sum(x*y for x,y in zip(actual,wanted))<.995
                    for actual,wanted in zip(tangents,contacts))):
                handle=min(g.distance(arc[0],arc[-1])*.45,arc_length/3)
                for scale in (1,.5,.25,.125):
                    candidate=g.cubic(arc[0],arc[-1],*contacts,handle*scale,steps=48)
                    if LineString(candidate).is_simple:
                        arc=candidate
                        break
                else:continue
            result.append(dict(key=key,points=arc,label=f'{a["name"]} {"起点侧" if side_a<0 else "终点侧"} ↔ {b["name"]} {"起点侧" if side_b<0 else "终点侧"}'))
    return result



def rounded_terminal_joins(scene,junctions):
    routes=route_objects(scene)
    trims={}
    bands={}
    candidates=[]
    endpoint_usage={}
    for junction in junctions:
        ids=junction['assets']
        assets=[routes[aid] for aid in ids]
        if any(a['kind']=='RUNWAY' or a['id'] not in scene.assets for a in assets):continue
        if not any(a['props'].get('terminal_backup13') for a in assets):continue
        lengths=[g.length(a['points']) for a in assets]
        stations=junction['stations']
        if any(min(s,L-s)>.1 for s,L in zip(stations,lengths)):continue
        directions=[1 if s<L/2 else -1 for s,L in zip(stations,lengths)]
        candidates.append((junction,ids,assets,lengths,directions))
        for aid,direction in zip(ids,directions):endpoint_usage.setdefault(aid,set()).add(direction)
    for junction,ids,assets,lengths,directions in candidates:
        budgets={aid:L*.495 for aid,L in zip(ids,lengths) if len(endpoint_usage[aid])==2}
        guides=turn_guides(scene,junction,visible_only=False,endpoint_budgets=budgets)
        if len(guides)!=1:continue
        arc=guides[0]['points']
        ends=[g.project(a['points'],point)[1] for a,point in zip(assets,(arc[0],arc[-1]))]
        if any(aid in trims and (direction==1 and trims[aid][0]>0 or direction<0 and trims[aid][1]<L)
               for aid,L,direction in zip(ids,lengths,directions)):continue
        for aid,L,station,direction in zip(ids,lengths,ends,directions):
            lo,hi=trims.get(aid,(0,L))
            trims[aid]=(station,hi) if direction==1 else (lo,station)
        _,tangent_a=g.at(assets[0]['points'],ends[0])
        _,tangent_b=g.at(assets[1]['points'],ends[1])
        entry=[-directions[0]*n for n in tangent_a]
        exit=[directions[1]*n for n in tangent_b]
        bands[junction['id']]=(arc,assets,entry,exit)
    return trims,bands


def terminal_band(arc,assets,entry,exit,outer):
    widths=[a['props']['width']/2+(shoulder_width(a['kind'],a['props']) if outer else 0) for a in assets]
    if outer and all(not shoulder_width(a['kind'],a['props']) for a in assets):return []
    left,right=[],[]
    for i,p in enumerate(arc):
        t=i/(len(arc)-1)
        width=(1-t)*widths[0]+t*widths[1]
        u=entry if i==0 else exit if i==len(arc)-1 else g.unit(arc[i-1],arc[i+1])
        # Join both adjoining corridors through a small tangent overlap.
        shift=-.004 if i==0 else .004 if i==len(arc)-1 else 0.
        x,y=p[0]+shift*u[0],p[1]+shift*u[1]
        left.append([x-u[1]*width,y+u[0]*width])
        right.append([x+u[1]*width,y-u[0]*width])
    return left+list(reversed(right))
