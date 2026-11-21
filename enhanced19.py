"""Bounded directed propagation of enhanced guidance through physical branches."""
import heapq,math,copy
import scene_geometry as g
from geometry11 import LineString,Point
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')

def interval(scene,aid,s,length,direction):
    a=scene.assets[aid];L=g.length(a['points']);lo,hi=(s,min(L,s+length)) if direction=='END' else (max(0,s-length),s)
    holds=[g.project(a['points'],m['points'][0])[1] for m in scene.assets.values() if m['kind']=='MARKING' and m['props'].get('mark_type') in ('HOLD_A','HOLD_B') and g.project(a['points'],m['points'][0])[0]<.5]
    from automatic_markings import holding_locations
    holds += [h['station'] for h in holding_locations(scene) if h['owner']==aid and 'station' in h]
    if direction=='END':hi=min([hi]+[v for v in holds if s+.01<v<hi])
    else:lo=max([lo]+[v for v in holds if lo<v<s-.01])
    return lo,hi

def select(scene,aid,station,length=47.,direction='END'):
    if aid not in scene.assets or scene.assets[aid]['kind'] not in TAXIS:raise ValueError('请选择滑行道中线')
    if not math.isfinite(length) or length<=0:raise ValueError('增强长度必须大于0')
    a=scene.assets[aid];station=max(0,min(g.length(a['points']),station));lo,hi=interval(scene,aid,station,length,direction)
    if hi-lo<.01:raise ValueError('所选方向没有可用中线')
    return scene.create_marking('TWY_ENHANCED',g.subpath(a['points'],lo,hi),enhanced_anchor19=True,label_asset=aid,enhanced_station19=station,enhanced_length19=length,enhanced_direction19=direction)

def sync(scene):
    for a in scene.assets.values():
        p=a['props']
        if not p.get('enhanced_anchor19'):continue
        __import__('guidance20').sync_mark(scene,a)

def refine(scene,result):
    key=(id(scene.data),scene.revision)
    cached=getattr(scene,'_enhanced_cache19',None)
    if not scene._transaction_depth and cached and cached[0]==key:
        for oid in cached[1]:result.pop(oid,None)
        result.update(copy.deepcopy(cached[2]));return result
    before=set(result);result=_refine(scene,result)
    if not scene._transaction_depth:scene._enhanced_cache19=(key,before-set(result),copy.deepcopy({k:v for k,v in result.items() if v['props'].get('enhanced_network19')}))
    return result

def network(scene,routes,marks,anchors):
    from guidance20 import project_visible,visible_intervals
    axes={aid:LineString(a['points']) for aid,a in routes.items()};stations={aid:{0.,g.length(a['points'])} for aid,a in routes.items()};cross=[];stops=set()
    for mark in marks:
        if mark['props'].get('mark_type') not in ('HOLD_A','HOLD_B'):continue
        for aid,axis in axes.items():
            q=Point(mark['points'][0])
            if axis.distance(q)<.5:
                s=axis.project(q);stations[aid].add(s);stops.add((aid,round(s,6)))
    windows={aid:list(visible_intervals(a)) for aid,a in routes.items()}
    for aid,ranges in windows.items():
        for lo,hi in ranges:stations[aid].update((lo,hi))
    # Turn endpoints have known parents. A projection is more reliable than
    # intersecting sampled lines at a rounded, oblique tangent point.
    arcs_by_junction={}
    for aid,axis in routes.items():
        parents=axis['props'].get('guidance_parents')
        if not parents:continue
        junction=axis['props'].get('junction20')
        if junction:arcs_by_junction[junction]=frozenset(parents)
        for bid,point in zip(parents,(axis['points'][0],axis['points'][-1])):
            if bid is None:continue
            hit=project_visible(routes[bid],point)
            if not hit or hit[0]>1e-5:continue
            x=axes[aid].project(Point(point));y=hit[1]
            stations[aid].add(x);stations[bid].add(y)
            cross.append((aid,x,bid,y))
    from pavement_geometry import crossings
    rounded={}
    for junction in crossings(scene):
        pair=arcs_by_junction.get(junction['id'])
        if pair:rounded.setdefault(pair,[]).append(Point(junction['point']))
    ids=list(routes)
    from geometry11 import STRtree
    tree=STRtree([axes[aid] for aid in ids])
    for i,aid in enumerate(ids):
        for j in tree.query(axes[aid]):
            if int(j)<=i:continue
            bid=ids[int(j)]
            parents_a=routes[aid]['props'].get('guidance_parents')
            parents_b=routes[bid]['props'].get('guidance_parents')
            if parents_a or parents_b:continue
            shape=axes[aid].intersection(axes[bid]);points=[shape] if shape.geom_type=='Point' else list(shape.geoms) if shape.geom_type=='MultiPoint' else []
            # Exact welded endpoint and crossing topology; no visual near-miss links.
            rounded_points=rounded.get(frozenset((aid,bid)),())
            for q in points:
                if any(q.distance(point)<1e-5 for point in rounded_points):continue
                x=axes[aid].project(q);y=axes[bid].project(q)
                if not all(any(lo-1e-6<=s<=hi+1e-6 for lo,hi in windows[k])
                           for k,s in ((aid,x),(bid,y))):continue
                stations[aid].add(x);stations[bid].add(y);cross.append((aid,x,bid,y))
    for aid,s in anchors:
        if aid in stations:stations[aid].add(s)
    neighbors={};ordered={a:sorted(v) for a,v in stations.items()}
    node=lambda a,s:(a,round(s,6))
    for aid,ss in ordered.items():
        for x,y in zip(ss,ss[1:]):
            if y-x<=1e-6 or not any(lo-1e-6<=x and y<=hi+1e-6 for lo,hi in windows[aid]):continue
            for p,q in [(x,y),(y,x)]:neighbors.setdefault(node(aid,p),[]).append((node(aid,q),abs(q-p),aid,p,q))
    for a,x,b,y in cross:
        neighbors.setdefault(node(a,x),[]).append((node(b,y),0,None,0,0));neighbors.setdefault(node(b,y),[]).append((node(a,x),0,None,0,0))
    return neighbors,stops

def between(scene,first,last):
    """Trace the visible centerline between two selected points."""
    from guidance20 import routes as guidance_routes
    routes=guidance_routes(scene)
    start=(first[1],round(first[2],6))
    finish=(last[1],round(last[2],6))
    neighbors,_=network(scene,routes,(),(start,finish))
    queue=[(0.,start)]
    distance={start:0.}
    previous={}
    while queue:
        cost,current=heapq.heappop(queue)
        if current==finish:break
        if cost>distance[current]:continue
        for target,length,route,x,y in neighbors.get(current,()):
            new_cost=cost+length
            if new_cost>=distance.get(target,math.inf):continue
            distance[target]=new_cost
            previous[target]=(current,route,x,y)
            heapq.heappush(queue,(new_cost,target))
    if finish not in previous:
        raise ValueError('两点之间没有连通的可见中线')
    pieces=[]
    while finish!=start:
        finish,route,x,y=previous[finish]
        if route:
            points=g.subpath(routes[route]['points'],min(x,y),max(x,y))
            pieces.append(points if x<y else points[::-1])
    path=[]
    for piece in reversed(pieces):
        if path and g.distance(path[-1],piece[0])<1e-5:piece=piece[1:]
        path.extend(piece)
    if not pieces or len(path)<2:raise ValueError('请选择两个不同的中线位置')
    return path

def _refine(scene,result):
    from automatic_markings import synthetic,entry_mark_hidden
    seeds=[];manual={};automatic=set();legacy={}
    from guidance20 import project_visible,routes as guidance_routes
    routes=guidance_routes(scene)
    for mark in list(result.values())+list(scene.assets.values()):
        p=mark['props']
        if entry_mark_hidden(scene,mark):continue
        if p.get('mark_type')!='TWY_ENHANCED' or p.get('enhanced_orphan20') or p.get('enhanced_two_point'):continue
        aid=p.get('enhanced_source20') or p.get('label_asset') or mark.get('owner')
        if aid not in routes:
            m=scene.movements.get(aid)
            if not m or not m.get('legacy_attachment'):continue
            aid=next((m[side]['asset'] for side in ('to','from') if scene.assets[m[side]['asset']]['kind'] in TAXIS),None)
        if aid not in routes:continue
        a=routes[aid];s0=g.project(a['points'],mark['points'][0])[1];s1=g.project(a['points'],mark['points'][-1])[1]
        # The automatic line ends at the holding position; user selection starts at it.
        if p.get('enhanced_anchor19'):start=s0 if p.get('enhanced_direction19')=='END' else s1;sign=1 if p.get('enhanced_direction19')=='END' else -1;limit=p['enhanced_length19']
        else:
            hit=project_visible(a,mark['points'][-1])
            if not hit:continue
            start=hit[1];sign=1 if s0>s1 else -1;limit=47.
            automatic.add(mark['id'])
            if mark.get('owner') in scene.movements and mark.get('owner')!=aid:
                legacy.setdefault(aid,[]).append((start,mark))
        seeds.append((aid,start,sign,limit,mark['id'] in automatic))
        if p.get('enhanced_anchor19'):manual.setdefault(aid,[]).append(sorted((s0,s1)))
    if not seeds:return result
    neighbors,stops=network(scene,routes,(*result.values(),*scene.assets.values()),
                            ((aid,station) for aid,station,_,_,_ in seeds))
    node=lambda aid,station:(aid,round(station,6))
    intervals={}
    for aid,s,sign,limit,is_automatic in seeds:
        if aid not in routes:continue
        queue=[(0.,node(aid,s))];dist={node(aid,s):0.}
        while queue:
            d,current=heapq.heappop(queue)
            if d>dist[current]+1e-6:continue
            if current in stops and current!=node(aid,s):continue
            for target,cost,route,x,y in neighbors.get(current,[]):
                if current==node(aid,s) and route==aid and (y-x)*sign<=0:continue
                # Travel is away from the hold: reverse permitted aircraft travel.
                if route:
                    flow=routes[route]['props'].get('flow','BOTH')
                    # A runway-side marking explicitly enabled for a rapid exit
                    # follows its own axis even if the taxi route is exit-only.
                    own_rapid_exit = is_automatic and route == aid and routes[route]['props'].get('rapid_exit')
                    against_approach = (flow in ('FORWARD','A_TO_B') and y>x
                                        or flow in ('REVERSE','B_TO_A') and y<x)
                    if against_approach and not own_rapid_exit:continue
                remain=limit-d
                if remain<=.001:continue
                if route:
                    end=x+(y-x)*min(1,remain/max(cost,1e-9));intervals.setdefault(route,[]).append(sorted((x,end)))
                nd=d+cost
                if nd<limit and nd<dist.get(target,float('inf')):dist[target]=nd;heapq.heappush(queue,(nd,target))
    for oid in automatic:result.pop(oid,None)
    for aid,ranges in intervals.items():
        merged=[]
        for lo,hi in sorted(ranges):
            if merged and lo<=merged[-1][1]+.01:merged[-1][1]=max(hi,merged[-1][1])
            else:merged.append([lo,hi])
        # Replace automatic base lines with the unified network result, avoiding duplicates.
        for oid,m in list(result.items()):
            if m.get('owner')==aid and m['props'].get('mark_type')=='TWY_ENHANCED':del result[oid]
        remaining=merged
        for start,end in manual.get(aid,[]):
            new=[]
            for lo,hi in remaining:
                if end<=lo or start>=hi:new.append([lo,hi])
                else:
                    if lo<start:new.append([lo,start])
                    if hi>end:new.append([end,hi])
            remaining=new
        for i,(lo,hi) in enumerate(remaining):
            if hi-lo<.01:continue
            points=g.subpath(routes[aid]['points'],lo,hi)
            mapped=next((m for station,m in legacy.get(aid,())
                         if lo-1e-5<=station<=hi+1e-5 and m['id'] not in result),None)
            if mapped:
                mark=dict(mapped,points=points,props=dict(mapped['props'],enhanced_network19=True))
            else:
                mark=synthetic(aid,'TWY_ENHANCED',points,'ENHANCED19:'+str(i),enhanced_network19=True)
            result[mark['id']]=mark
    return result

def render(scene,mark):
    """Keep the solid axis; interrupt side dashes at through crossings and holds."""
    if mark['props'].get('enhanced_orphan20'):return []
    from marking_catalog import primitives
    from geometry11 import unary_union,lines
    items=primitives(mark);p=mark['props'];axis=LineString(mark['points']);cuts=[];merge_points=[]
    owner=p.get('label_asset') or mark.get('owner')
    source_assets = {owner}
    movement = scene.movements.get(owner, {})
    if movement.get('legacy_attachment'):
        source_assets.update(movement[side]['asset'] for side in ('from','to'))
    for aid,a in scene.assets.items():
        if aid in source_assets:continue
        if a['kind'] in TAXIS:
            other=LineString(a['points']);hit=axis.intersection(other)
            points=[hit] if hit.geom_type=='Point' else list(hit.geoms) if hit.geom_type=='MultiPoint' else []
            for point in points:
                station=other.project(point)
                if 1<station<other.length-1 and 1<axis.project(point)<axis.length-1:cuts.append(other.buffer(a['props']['width']/2,cap_style=2))
                else:merge_points.append(point)
        elif a['kind']=='MARKING' and a['props'].get('mark_type') in ('HOLD_A','HOLD_B'):
            q,u=g.at(a['points'],0);v=[-u[1],u[0]];half=a['props'].get('width',23)/2
            cuts.append(LineString([[q[k]-v[k]*half for k in (0,1)],[q[k]+v[k]*half for k in (0,1)]]).buffer(2))
    mask=unary_union(cuts);out=[]
    for item in items:
        if not item.get('dash'):out.append(item);continue
        original=LineString(item['points'])
        for line in lines(original.difference(mask)):
            out.append(dict(item,points=[list(q) for q in line.coords],dash_offset=original.project(Point(line.coords[0]))%4))
        # Three metres of continuous inner guidance at a merge avoids a tiny final dash.
        for point in merge_points:
            s=original.project(point);lo=max(0,min(s-1.5,original.length-3));hi=min(original.length,lo+3)
            if hi-lo>=2.999:
                for line in lines(LineString(g.subpath(item['points'],lo,hi)).difference(mask)):out.append(dict(item,points=[list(q) for q in line.coords],dash=None))
    return out
