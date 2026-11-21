"""Two-way service roads, lane-specific attachments and crossing warnings."""
import math
import scene_geometry as g
from pavement_geometry import offset,corridor

ROAD_MARKS={'PEDESTRIAN','SPEED','JET_BLAST','ROAD_STOP','ROAD_ARROW'}

def roads(scene):return [a for a in scene.assets.values() if a['kind']=='ROAD']

def hit(scene,p,tolerance=12):
    candidates=[]
    for a in roads(scene):
        d,s,q=g.project(a['points'],p)
        if d<=max(tolerance,a['props']['width']/2):candidates.append((d,a['id'],s,q))
    return min(candidates,key=lambda x:x[0]) if candidates else None

def lane_pose(scene,a,station,lane):
    q,u=g.at(a['points'],station);v=[-u[1],u[0]];sign=-1 if lane=='A' else 1
    q=[q[k]+sign*v[k]*a['props']['width']/4 for k in (0,1)]
    forward=(lane=='A') == (scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')
    return q,[x*(1 if forward else -1) for x in u]

def place(scene,key,h,lanes='BOTH'):
    _,aid,s,_=h;a=scene.assets[aid];made=[]
    with scene.transaction('车道中线吸附标记'):
        for lane in ('A','B') if lanes=='BOTH' else (lanes,):
            q,u=lane_pose(scene,a,s,lane)
            made.append(scene.create_marking(key,[q,[q[k]+u[k]*10 for k in (0,1)]],road_id=aid,road_station=s,lane_side=lane,width=a['props']['width']/2))
    return made

def refresh_attachments(scene,aid):
    a=scene.assets[aid]
    for b in scene.assets.values():
        p=b['props']
        if p.get('divider_road')==aid:
            total=g.length(a['points']);lo=min(total,p['divider_start']);hi=min(total,p['divider_end'])
            if hi>lo:b['points']=g.subpath(a['points'],lo,hi)
            continue
        if p.get('road_id')!=aid:continue
        q,u=lane_pose(scene,a,min(g.length(a['points']),p['road_station']),p['lane_side'])
        b['points']=[q,[q[k]+u[k]*10 for k in (0,1)]];p['width']=a['props']['width']/2

def road_endpoint_contacts(a,b,tolerance=.02):
    # Projected points can land a few micrometres off a curved road segment.
    for source,target in ((a,b),(b,a)):
        for point in (source['points'][0],source['points'][-1]):
            distance,_,projected=g.project(target['points'],point)
            if distance<=tolerance:yield projected


def intersections(scene,a):
    cache=getattr(scene,'_road10_cache',None)
    if not cache or cache[0]!=scene.revision:cache=(scene.revision,{});scene._road10_cache=cache
    if not scene._transaction_depth and a['id'] in cache[1]:return cache[1][a['id']]
    out=[]
    for b in scene.assets.values():
        if b['id']==a['id'] or b['kind'] not in ('ROAD','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):continue
        for x,y in zip(a['points'],a['points'][1:]):
            for c,d in zip(b['points'],b['points'][1:]):
                ux,uy=y[0]-x[0],y[1]-x[1];vx,vy=d[0]-c[0],d[1]-c[1];den=ux*vy-uy*vx
                if abs(den)<1e-9:continue
                t=((c[0]-x[0])*vy-(c[1]-x[1])*vx)/den;s=((c[0]-x[0])*uy-(c[1]-x[1])*ux)/den
                if -.00001<=t<=1.00001 and -.00001<=s<=1.00001:
                    q=[x[0]+t*ux,x[1]+t*uy];station=g.project(a['points'],q)[1]
                    sine=abs(den)/max(1e-9,math.hypot(ux,uy)*math.hypot(vx,vy))
                    if not any(v['other']['id']==b['id'] and abs(v['station']-station)<2 for v in out):out.append(dict(station=station,point=q,other=b,half=b['props']['width']/2/max(.15,sine)))
        if b['kind']=='ROAD':
            for q in road_endpoint_contacts(a,b):
                _,station,_=g.project(a['points'],q)
                if any(j['other']['id']==b['id'] and abs(j['station']-station)<.1 for j in out):continue
                _,other_station,_=g.project(b['points'],q)
                _,u=g.at(a['points'],station)
                _,v=g.at(b['points'],other_station)
                sine=abs(u[0]*v[1]-u[1]*v[0])
                if sine>.05:
                    out.append(dict(station=station,point=q,other=b,half=b['props']['width']/2/sine))
    if not scene._transaction_depth:cache[1][a['id']]=out
    return out

def raw_surface_extras(scene):
    cache=getattr(scene,'_road10_surfaces',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth:return cache[1]
    # Rounded junction patches are made before paint. No dead-end bulb/end caps.
    from curve_model import rounded_nodes,evaluate
    out=[];seen=set()
    for a in roads(scene):
        for j in intersections(scene,a):
            b=j['other']
            if b['kind']!='ROAD' or __import__('roads13').is_smooth_bend(a,b,j['point']):continue
            token=tuple(sorted((a['id'],b['id'])))+tuple(round(x,1) for x in j['point'])
            if token in seen:continue
            seen.add(token);sa=j['station'];sb=g.project(b['points'],j['point'])[1];r=max(a['props']['width'],b['props']['width'])*1.5
            for sign in (-1,1):
                for direction in (-1,1):
                    p,_=g.at(a['points'],max(0,min(g.length(a['points']),sa+sign*r*2)))
                    q,_=g.at(b['points'],max(0,min(g.length(b['points']),sb+direction*r*2)))
                    center=j['point']
                    if min(g.distance(p,center),g.distance(q,center))<.05:continue
                    u,v=g.unit(center,p),g.unit(center,q)
                    if abs(u[0]*v[1]-u[1]*v[0])<.1:continue
                    nodes,_=rounded_nodes([p,center,q],r)
                    for polygon in [corridor(evaluate(nodes),min(a['props']['width'],b['props']['width']))]:
                        out.append(dict(type='polygon',oid=a['id'],points=polygon,fill=a['props'].get('pavement_color','#737b83'),surface10=True))
    if not scene._transaction_depth:scene._road10_surfaces=(scene.revision,out)
    return out

def generated(scene):
    from automatic_markings import synthetic
    out={}
    for a in roads(scene):
        if a['props'].get('closed'):continue
        for i,j in enumerate(intersections(scene,a)):
            if j['other']['kind']=='ROAD' or not a['props'].get('auto_jet_blast'):continue
            for lane in ('A','B'):
                _,u=lane_pose(scene,a,j['station'],lane);_,axis=g.at(a['points'],j['station']);sign=1 if sum(u[k]*axis[k] for k in (0,1))>0 else -1
                s=j['station']-sign*(j['half']+scene.data['meta'].get('jet_warning_distance',12))
                if not 0<s<g.length(a['points']):continue
                q,u=lane_pose(scene,a,s,lane)
                mark=synthetic(a['id'],'JET_BLAST',[q,[q[k]+u[k]*10 for k in (0,1)]],f'JET:{i}:{lane}',width=a['props']['width']/2,road_id=a['id'],lane_side=lane)
                out[mark['id']]=mark
    return out

def paint(scene):
    from marking_catalog import primitives
    from automatic_markings import synthetic
    from marking_standards import outside_segments
    out=[];patches=surface_extras(scene);road_polys=[corridor(a['points'],a['props']['width']+.05) for a in roads(scene)]
    def line(a,pts,width=.15,dash=None):
        if len(pts)>1:out.append(dict(type='line',oid=a['id'],points=pts,stroke='#ffffff',width=width,dash=dash))
    for a in roads(scene):
        if a['props'].get('closed'):continue
        pts=a['points'];w=a['props']['width'];total=g.length(pts);jj=intersections(scene,a)
        blockers=[corridor(b['points'],b['props']['width']+.05) for b in scene.assets.values() if b['id']!=a['id'] and b['kind'] in ('ROAD','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')]
        blockers += [patch['points'] for patch in patches]
        for side in (-1,1):
            path=offset(pts,side*(w/2-.075))
            for segment,_ in outside_segments(path,blockers):line(a,segment)
            for i,j in enumerate(jj):
                if j['other']['kind']=='ROAD':continue
                segment=g.subpath(pts,max(0,j['station']-j['half']),min(total,j['station']+j['half']))
                if len(segment)>1:out.extend(primitives(synthetic(a['id'],'ROAD_STAGGER',offset(segment,side*(w/2-.15)),f'CHECK:{i}:{side}',line_width=.15,spacing=0)))
        # Global path phase in metres, unchanged at any zoom.
        for s in range(0,math.ceil(total),6):
            if not any(abs(s-j['station'])<j['half']+2 for j in jj):line(a,g.subpath(pts,s,min(total,s+3)))
        for station in (0,total):
            q,u=g.at(pts,station);v=[-u[1],u[0]]
            connected=any(b['id']!=a['id'] and g.project(b['points'],q)[0]<b['props']['width']/2+.5 for b in roads(scene))
            if not connected:line(a,[[q[k]+v[k]*w/2 for k in (0,1)],[q[k]-v[k]*w/2 for k in (0,1)]])
        stations={max(8,min(total-8,j['station']-j['half']-10)) for j in jj}
        for node in a.get('design_vertices',[])[1:-1]:stations.add(g.project(pts,node)[1])
        if not stations and total>35:stations={total/2}
        for s in stations:
            for lane in ('A','B'):
                q,u=lane_pose(scene,a,s,lane);v=[-u[1],u[0]]
                line(a,[[q[k]-u[k]*3 for k in (0,1)],[q[k]+u[k]*2 for k in (0,1)]],.2)
                line(a,[[q[k]+u[k]*.4+v[k]*.7 for k in (0,1)],[q[k]+u[k]*2 for k in (0,1)],[q[k]+u[k]*.4-v[k]*.7 for k in (0,1)]],.2)
        # Lane-to-lane turning paths at road junctions, respecting the project's
        # driving side. These are road curves, independent of taxi guidance.
        from curve_model import rounded_nodes,evaluate
        for j in jj:
            b=j['other']
            if b['kind']!='ROAD':continue
            sb=g.project(b['points'],j['point'])[1];radius=max(6,min(w,b['props']['width'])*1.5)
            for incoming in (-1,1):
                sa=j['station']-incoming*radius*2
                if not 0<sa<total:continue
                lane='A' if (incoming==1)==(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT') else 'B'
                p,ui=lane_pose(scene,a,sa,lane)
                for outgoing in (-1,1):
                    target=sb+outgoing*radius*2
                    if not 0<target<g.length(b['points']):continue
                    lane2='A' if (outgoing==1)==(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT') else 'B'
                    q,uo=lane_pose(scene,b,target,lane2)
                    if abs(sum(ui[k]*uo[k] for k in (0,1)))>.98:continue
                    from pavement_geometry import line_intersection
                    corner=line_intersection(p,ui,q,uo)
                    if not corner:continue
                    nodes,_=rounded_nodes([p,corner,q],radius);curve=evaluate(nodes)
                    line(a,curve,.1,[1,1])
                    at,ut=g.at(curve,min(5,g.length(curve)/2));vt=[-ut[1],ut[0]]
                    line(a,[[at[k]-ut[k]*1.5+vt[k]*.5 for k in (0,1)],at,[at[k]-ut[k]*1.5-vt[k]*.5 for k in (0,1)]],.15)
    # Only exposed boundaries of the rounded junction union receive edge paint.
    for index,patch in enumerate(patches):
        blockers=road_polys+[p['points'] for i,p in enumerate(patches) if i!=index]
        pts=patch['points']+[patch['points'][0]]
        for segment,_ in outside_segments(pts,blockers):
            if g.length(segment)>.05:out.append(dict(type='line',oid=patch['oid'],points=segment,stroke='#ffffff',width=.15))
    return out

def surface_extras(scene):
    from geometry11 import clip_extras
    return clip_extras(scene,raw_surface_extras(scene))

from roads11 import paint,generated,place,refresh_attachments,intersections
