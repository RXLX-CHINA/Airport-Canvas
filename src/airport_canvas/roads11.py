"""Lane-sized non-overlapping road signs and exact crossing edge transitions."""
import copy
import math
import uuid
import scene_geometry as g

def intersections(scene,a):
    from geometry11 import LineString,Point,parts,aircraft_routes
    cache=getattr(scene,'_intersections11',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth and a['id'] in cache[1]:return cache[1][a['id']]
    if not cache or cache[0]!=scene.revision:cache=(scene.revision,{});scene._intersections11=cache
    own=LineString(a['points']);out=[];targets={aid:b for aid,b in scene.assets.items() if b['kind']=='ROAD' and aid!=a['id']};targets.update(aircraft_routes(scene))
    for b in targets.values():
        other=LineString(b['points']);hits=own.intersection(other)
        points=parts(hits,('Point',))
        if b['kind']=='ROAD':
            from roads10 import road_endpoint_contacts
            points.extend(Point(q) for q in road_endpoint_contacts(a,b))
        for point in points:
            q=[point.x,point.y];station=own.project(point)
            if b['kind']=='ROAD' and __import__('roads13').is_smooth_bend(a,b,q):continue
            if any(v['other']['id']==b['id'] and abs(v['station']-station)<2 for v in out):continue
            _,u=g.at(a['points'],station);_,v=g.at(b['points'],other.project(point));sine=abs(u[0]*v[1]-u[1]*v[0])
            if sine>.05:out.append(dict(station=station,point=q,other=b,half=b['props']['width']/2/sine))
    if not scene._transaction_depth:cache[1][a['id']]=out
    return out

def size_props(key,lane_width):
    from marking_catalog import CATALOG
    p=copy.deepcopy(CATALOG[key]['defaults'])
    if key=='SPEED':p.update(width=min(1.5,lane_width*.65),text_height=min(1,lane_width*.4))
    elif key=='JET_BLAST':p.update(width=min(.7,lane_width*.65*math.sqrt(3)/2),text_height=min(.12,lane_width*.1))
    elif key in ('PEDESTRIAN','ROAD_STOP'):p['width']=lane_width*.9
    elif key=='ROAD_ARROW':p.update(width=min(1.5,lane_width*.6),arrow_length=4.)
    return p

def occupied(scene,aid,lane,exclude=()):
    return [(a['props'].get('road_station',0),a['props']['mark_type']) for oid,a in scene.assets.items() if oid not in exclude and a['kind']=='MARKING' and a['props'].get('road_id')==aid and a['props'].get('lane_side')==lane]

def clear_station(scene,a,station,lane,occupied_rows):
    total=g.length(a['points']);jjs=intersections(scene,a);gap=scene.data['meta'].get('road_mark_gap',6.)
    for shift in [0]+[sign*step for step in range(2,51,2) for sign in (-1,1)]:
        s=station+shift
        if not 2<s<total-2:continue
        if any(abs(s-old)<gap for old,_ in occupied_rows):continue
        if any(j['other']['kind']=='ROAD' and abs(s-j['station'])<j['half']+3 for j in jjs):continue
        return s
    raise ValueError('此处附近没有不重叠的标记位置；请选择更远的车道站位')

def place(scene,key,h,lanes='BOTH'):
    from roads10 import lane_pose
    _,aid,station,_=h;a=scene.assets[aid];made=[];pair=uuid.uuid4().hex[:10]
    with scene.transaction('按车道放置标记'):
        for lane in ('A','B') if lanes=='BOTH' else (lanes,):
            s=clear_station(scene,a,station,lane,occupied(scene,aid,lane));q,u=lane_pose(scene,a,s,lane)
            p=size_props(key,a['props']['width']/2);p.update(road_id=aid,road_station=s,lane_side=lane,pair_group=pair,axis_placement11=True,axis_side=lane)
            made.append(scene.create_marking(key,[q,[q[k]+u[k]*10 for k in (0,1)]],**p))
    return made

def refresh_attachments(scene,aid):
    from roads10 import lane_pose
    a=scene.assets[aid]
    for b in scene.assets.values():
        p=b['props']
        if p.get('divider_road')==aid:
            total=g.length(a['points']);lo=min(total,p['divider_start']);hi=min(total,p['divider_end'])
            if hi>lo:b['points']=g.subpath(a['points'],lo,hi)
        if p.get('road_id')!=aid or not p.get('road_attached',True):continue
        q,u=lane_pose(scene,a,min(g.length(a['points']),p['road_station']),p['lane_side']);b['points']=[q,[q[k]+u[k]*10 for k in (0,1)]]
        defaults=size_props(p['mark_type'],a['props']['width']/2)
        if p['mark_type'] in ('SPEED','JET_BLAST'):p['width']=min(p.get('width',defaults['width']),defaults['width'])

def generated(scene):
    cache=getattr(scene,'_road_signs11',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth:return copy.deepcopy(cache[1])
    from roads10 import roads,lane_pose
    from automatic_markings import synthetic
    out={}
    for a in roads(scene):
        if a['props'].get('closed') or not a['props'].get('auto_jet_blast'):continue
        for lane in ('A','B'):
            taken=occupied(scene,a['id'],lane);candidates=[]
            for j in intersections(scene,a):
                if j['other']['kind']=='ROAD':continue
                _,u=lane_pose(scene,a,j['station'],lane);_,axis=g.at(a['points'],j['station']);sign=1 if sum(u[k]*axis[k] for k in (0,1))>0 else -1
                station=j['station']-sign*(j['half']+scene.data['meta'].get('jet_warning_distance',12));candidates.append((station,sign,j))
            for i,(station,sign,j) in enumerate(sorted(candidates,key=lambda row:row[0])):
                if not 2<station<g.length(a['points'])-2:continue
                # A single warning can cover nearby aircraft branches. It must
                # remain upstream: never relocate through the crossing itself.
                if any(abs(station-old)<scene.data['meta'].get('road_mark_gap',6.) for old,_ in taken):continue
                for step in range(20):
                    s=station-sign*step*2
                    if not 2<s<g.length(a['points'])-2:break
                    if any(abs(s-old)<6 for old,_ in taken):continue
                    if any(v['other']['kind']=='ROAD' and abs(s-v['station'])<v['half']+3 for v in intersections(scene,a)):continue
                    q,u=lane_pose(scene,a,s,lane);p=size_props('JET_BLAST',a['props']['width']/2)
                    mark=synthetic(a['id'],'JET_BLAST',[q,[q[k]+u[k]*10 for k in (0,1)]],f'JET:{i}:{lane}',road_id=a['id'],road_station=s,lane_side=lane,**p);out[mark['id']]=mark;taken.append((s,'JET_BLAST'));break
    if not scene._transaction_depth:scene._road_signs11=(scene.revision,copy.deepcopy(out))
    return out

def arrow(owner,q,u,width=1.2,length=4.,turns=None):
    v=[-u[1],u[0]];stem=width*.24;tip=length/2;base=tip-length*.35
    local=[(-length/2,-stem/2),(base,-stem/2),(base,-width/2),(tip,0),(base,width/2),(base,stem/2),(-length/2,stem/2)]
    if turns and set(turns)!={'STRAIGHT'}:
        from geometry11 import LineString,Polygon,unary_union,polygons
        shapes=[LineString([[-length/2,0],[0,0]]).buffer(stem/2,cap_style=2,join_style=1)]
        if 'STRAIGHT' in turns:shapes.append(Polygon(local))
        for label,sign in [('LEFT',1),('RIGHT',-1)]:
            if label not in turns:continue
            head=width/2;neck=max(.1,head-.4);shapes.append(LineString([[-.3,0],[0,0],[0,sign*neck]]).buffer(stem/2,cap_style=2,join_style=1));shapes.append(Polygon([[0,sign*head],[-.4,sign*neck],[.4,sign*neck]]))
        merged=polygons(unary_union(shapes))
        if merged:local=[list(p) for p in max(merged,key=lambda p:p.area).exterior.coords][:-1]
    return dict(type='polygon',oid=owner,points=[[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in local],fill='#ffffff',road_arrow11=True)

def paint(scene,stand_designs=None):
    from geometry11 import road_union,aircraft_union,LineString,Point,polygon,unary_union,lines,polygons
    from roads10 import roads,lane_pose
    from automatic_markings import synthetic
    from marking_catalog import primitives
    aa=roads(scene)
    if not aa:return []
    from roads18 import checker_mask
    union=road_union(scene);aircraft=checker_mask(scene,stand_designs);out=[]
    axes=[LineString(road['points']) for road in aa]
    def owner(point):
        query=Point(point)
        distances=[axis.distance(query) for axis in axes]
        nearest=min(distances)
        candidates=[road for road,d in zip(aa,distances) if d<=nearest+1e-8]
        if len(candidates)==1:
            return candidates[0]['id']
        return min(candidates,key=lambda road:g.project(road['points'],point)[0])['id']
    warnings=generated(scene).values()
    # Heal sub-centimetre tessellation seams at two exact Bezier halves before
    # deriving the exterior; these are not road end caps.
    edge=union.buffer(.02,join_style=1).buffer(-.095,join_style=1).boundary
    # A free end stays a solid transverse line across the checker transition.
    caps=[]
    for road in aa:
        axis=road['points']
        for end,neighbor in ((axis[0],axis[1]),(axis[-1],axis[-2])):
            u=g.unit(end,neighbor)
            v=(-u[1],u[0])
            half=road['props']['width']/2+.1
            face=LineString([[end[k]+u[k]*.075+sign*v[k]*half for k in (0,1)]
                             for sign in (-1,1)])
            caps.append(face.buffer(.002,cap_style=2))
    checker_zone=aircraft.difference(unary_union(caps))
    for line in lines(edge.difference(checker_zone)):
        from geometry11 import ownership_vertices
        pts=ownership_vertices(list(line.coords),aa);chunk=[];last=None
        for p,q in zip(pts,pts[1:]):
            current=owner([(p[k]+q[k])/2 for k in (0,1)])
            if chunk and current!=last:
                if scene.assets[last]['props'].get('edges_visible',True):out.append(dict(type='line',oid=last,points=chunk,stroke='#ffffff',width=.15,road_edge11=True))
                chunk=[]
            if not chunk:chunk=[p]
            chunk.append(q);last=current
        if len(chunk)>1 and scene.assets[last]['props'].get('edges_visible',True):out.append(dict(type='line',oid=last,points=chunk,stroke='#ffffff',width=.15,road_edge11=True))
    for line in lines(edge.intersection(checker_zone)):
        pts=[list(q) for q in line.coords]
        if line.length>.1:
            mid=line.interpolate(line.length/2);before=line.interpolate(max(0,line.length/2-.01));after=line.interpolate(min(line.length,line.length/2+.01));u=g.unit([before.x,before.y],[after.x,after.y]);left=[-u[1],u[0]];inside=union.covers(Point(mid.x+left[0]*.1,mid.y+left[1]*.1));shifted=line.offset_curve(.075 if inside else -.075)
            road_id=owner(pts[0])
            for path in lines(shifted):
                marks=primitives(synthetic(road_id,'ROAD_STAGGER',[list(q) for q in path.coords],'CHECKER',line_width=.15,spacing=0))
                for mark in marks:mark['road_checker11']=True
                if scene.assets[road_id]['props'].get('edges_visible',True):out.extend(marks)
    for a in aa:
        if a['props'].get('closed'):continue
        total=g.length(a['points']);axis=LineString(a['points']);junctions=intersections(scene,a)
        mask=unary_union([Point(j['point']).buffer(max(a['props']['width'],j['other']['props']['width'])) for j in junctions if j['other']['kind']=='ROAD'])
        for path in lines(axis.difference(mask)):
            if not a['props'].get('road_center_visible',True):continue
            pts=[list(q) for q in path.coords];station=axis.project(Point(pts[0]))
            if axis.project(Point(pts[-1]))<station:pts.reverse();station=axis.project(Point(pts[0]))
            out.append(dict(type='line',oid=a['id'],points=pts,stroke='#ffffff',width=.15,dash=[3,3],dash_offset=station+a['props'].get('road_dash_phase13',0),road_divider11=True))
        # Reserve sign footprints and one arrow station per approach, not a pile
        # of overlapping heads on every generated turn curve.
        for lane in ('A','B'):
            reserved=occupied(scene,a['id'],lane)+[(m['props'].get('road_station',0),'JET_BLAST') for m in warnings if m['props'].get('road_id')==a['id'] and m['props'].get('lane_side')==lane]
            positions=[]
            for j in junctions:
                if j['other']['kind']!='ROAD':continue
                _,u=lane_pose(scene,a,j['station'],lane);_,t=g.at(a['points'],j['station']);sign=1 if sum(u[k]*t[k] for k in (0,1))>0 else -1
                s=j['station']-sign*(j['half']+10)
                if 3<s<total-3 and all(abs(s-old)>8 for old in positions) and all(abs(s-old)>6 for old,_ in reserved):positions.append(s)
            for point in a.get('design_vertices',[])[1:-1]:
                s=axis.project(Point(point))
                if all(abs(s-old)>8 for old in positions) and all(abs(s-old)>6 for old,_ in reserved):positions.append(s)
            if not positions and total>45:positions=[total/2] if all(abs(total/2-old)>6 for old,_ in reserved) else []
            for s in positions:
                if not a['props'].get('road_auto_arrows',True):continue
                q,u=lane_pose(scene,a,s,lane);turns=['STRAIGHT']
                nearby=next((j for j in junctions if j['other']['kind']=='ROAD' and abs(abs(s-j['station'])-(j['half']+10))<1),None)
                if nearby:
                    _,baseaxis=g.at(a['points'],nearby['station']);direction=1 if sum(u[k]*baseaxis[k] for k in (0,1))>0 else -1
                    turns=['STRAIGHT'] if (total-nearby['station'] if direction>0 else nearby['station'])>a['props']['width'] else []
                    other=nearby['other'];sb=g.project(other['points'],nearby['point'])[1];_,other_axis=g.at(other['points'],sb);n=g.length(other['points'])
                    for sign in (-1,1):
                        if (n-sb if sign>0 else sb)<=other['props']['width']:continue
                        cross=u[0]*other_axis[1]*sign-u[1]*other_axis[0]*sign
                        if abs(cross)>.1:turns.append('LEFT' if cross>0 else 'RIGHT')
                out.append(arrow(a['id'],q,u,min(1.4,a['props']['width']*.22),turns=turns))
        # Curve lane guidance at road/road intersections; filled arrow heads are
        # placed only on approaches above, so the junction core stays legible.
        from curve_model import rounded_nodes,evaluate
        from pavement_geometry import line_intersection
        for j in junctions:
            if a['props'].get('road_turn_guides')=='HIDDEN':continue
            b=j['other']
            if b['kind']!='ROAD':continue
            sb=g.project(b['points'],j['point'])[1];R=max(6,min(a['props']['width'],b['props']['width'])*1.5)
            for incoming in (-1,1):
                sa=j['station']-incoming*R*2
                if not 0<sa<total:continue
                lane='A' if (incoming==1)==(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT') else 'B';p,ui=lane_pose(scene,a,sa,lane)
                for outgoing in (-1,1):
                    target=sb+outgoing*R*2
                    if not 0<target<g.length(b['points']):continue
                    lane2='A' if (outgoing==1)==(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT') else 'B';q,uo=lane_pose(scene,b,target,lane2)
                    if abs(sum(ui[k]*uo[k] for k in (0,1)))>.98:continue
                    # Default public-road layout: only the near-side turning
                    # guides; do not fill the core with every conflicting path.
                    cross=ui[0]*uo[1]-ui[1]*uo[0]
                    interior=min(j['station'],total-j['station'])>R*2 and min(sb,g.length(b['points'])-sb)>R*2
                    if interior and a['props'].get('road_turn_guides','NEAR_SIDE')!='ALL' and ((cross<0)!=(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):continue
                    corner=line_intersection(p,ui,q,uo)
                    if corner:
                        nodes,_=rounded_nodes([p,corner,q],R);out.append(dict(type='line',oid=a['id'],points=evaluate(nodes),stroke='#ffffff',width=.15,dash=[1,1],road_turn11=True))
    return out

def separate_marks(scene,items,generated):
    """Keep clear pavement around priority markings before adding road arrows."""
    from geometry11 import LineString, Point, polygon, unary_union
    marks = {}
    arrows = []
    for index,item in enumerate(items):
        oid = item.get('oid')
        if item.get('road_arrow11'):
            arrows.append(index)
            continue
        mark = scene.assets.get(oid) or generated.get(oid)
        if mark and mark['props'].get('mark_type') in ('ROAD_STOP','PEDESTRIAN','ROAD_ARROW','SPEED','JET_BLAST'):
            marks.setdefault(oid,[]).append(index)

    def footprint(item):
        points = item['points']
        if item['type']=='polygon':
            return polygon(points)
        if item['type']=='line':
            return LineString(points).buffer(max(.025,item.get('width',.1)/2))
        if item['type']=='text':
            from shapely.geometry import box
            from shapely.affinity import rotate
            x,y = points[0]
            height = item['size']
            width = item.get('text_width') or height*max(1,len(item.get('text','')))*.6
            return rotate(box(x-width/2,y-height/2,x+width/2,y+height/2),
                          item.get('rotation',0),origin=(x,y))
        return Point(points[0])

    blocked = []
    hidden = set()
    priority = {'PEDESTRIAN':0,'ROAD_STOP':1,'SPEED':2,'JET_BLAST':3,'ROAD_ARROW':4}
    order = sorted(marks,key=lambda oid:(oid not in scene.assets,
                   priority[(scene.assets.get(oid) or generated[oid])['props']['mark_type']]))
    for oid in order:
        indices = marks[oid]
        shape = unary_union([footprint(items[index]) for index in indices])
        if oid not in scene.assets and any(shape.intersects(old) for old in blocked):
            hidden.update(indices)
        else:
            blocked.append(shape.buffer(.25))
    for index in arrows:
        shape = footprint(items[index])
        if any(shape.intersects(old) for old in blocked):
            hidden.add(index)
        else:
            blocked.append(shape.buffer(.25))
    return [item for index,item in enumerate(items) if index not in hidden]
