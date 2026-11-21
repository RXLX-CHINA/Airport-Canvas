"""Two terminal road arms form one rounded bend, not a fictitious four-way fork."""
import copy,math
import scene_geometry as g

def reverse(nodes):
    nodes=copy.deepcopy(list(reversed(nodes)))
    for n in nodes:n['incoming'],n['outgoing']=n['outgoing'],n['incoming']
    return nodes

def is_smooth_bend(a,b,point):
    if not (a['props'].get('rounded_join13') and b['props'].get('rounded_join13')):return False
    vectors=[]
    for road in (a,b):
        i=0 if g.distance(road['points'][0],point)<.05 else -1 if g.distance(road['points'][-1],point)<.05 else None
        if i is None or not road.get('curve_nodes'):return False
        n=road['curve_nodes'][i];handle=n['outgoing'] if i==0 else n['incoming'];vectors.append(g.unit(n['p'],handle))
    return abs(sum(vectors[0][k]*vectors[1][k] for k in (0,1)))>.995

def reconcile(scene):
    from curve_model import nodes_for,split_curve_nodes,rounded_nodes,evaluate
    roads=[a for a in scene.assets.values() if a['kind']=='ROAD'];done=set()
    for a in roads:
        pts=a['points']
        if 2<len(pts)<=16 and not a.get('curve_nodes') and min(g.distance(p,q) for p,q in zip(pts,pts[1:]))>a['props']['width']*1.5:
            nodes,_=rounded_nodes(pts,a['props'].get('corner_radius',12));a.update(design_vertices=copy.deepcopy(pts),curve_nodes=nodes,points=evaluate(nodes))
    for i,a in enumerate(roads):
        for b in roads[i+1:]:
            if a['id'] in done or b['id'] in done or abs(a['props']['width']-b['props']['width'])>.05:continue
            hits=[(g.distance(a['points'][ia],b['points'][ib]),ia,ib) for ia in (0,-1) for ib in (0,-1)];distance,ia,ib=min(hits)
            if distance>.05:continue
            corner=a['points'][ia]
            if any(c['id'] not in (a['id'],b['id']) and g.project(c['points'],corner)[0]<max(1,c['props']['width']/2) for c in roads):continue
            pa=a['points'] if ia==-1 else list(reversed(a['points']));pb=b['points'] if ib==0 else list(reversed(b['points']));ua=g.unit(pa[-2],pa[-1]);ub=g.unit(pb[0],pb[1]);angle=math.acos(max(-1,min(1,sum(ua[k]*ub[k] for k in (0,1)))))
            if not math.radians(15)<angle<math.radians(165):continue
            R=max(a['props'].get('corner_radius',12),b['props'].get('corner_radius',12),a['props']['width']*.8);la=g.length(pa);lb=g.length(pb);reach=min(R*2.5,la*.8,lb*.8)
            if reach<max(a['props']['width'],R*.5):continue
            an=nodes_for(a);bn=nodes_for(b)
            if ia==0:an=reverse(an)
            if ib==-1:bn=reverse(bn)
            prefix,_=split_curve_nodes(an,la-reach);_,suffix=split_curve_nodes(bn,reach)
            local,_=rounded_nodes([prefix[-1]['p'],corner,suffix[0]['p']],R);merged=prefix;merged[-1]['outgoing']=local[0]['outgoing'];merged.extend(local[1:]);merged[-1]['outgoing']=suffix[0]['outgoing'];merged.extend(suffix[1:])
            path=evaluate(merged);station=g.project(path,corner)[1];left,right=split_curve_nodes(merged,station)
            if ia==0:left=reverse(left)
            if ib==-1:right=reverse(right)
            a.update(points=evaluate(left),curve_nodes=left);b.update(points=evaluate(right),curve_nodes=right)
            a.pop('design_vertices',None);b.pop('design_vertices',None)
            canonical_a=g.length(a['points']);total=canonical_a+g.length(b['points']);a['props']['road_dash_phase13']=(3-canonical_a)%6 if ia==0 else 0.;b['props']['road_dash_phase13']=(3-total)%6 if ib==-1 else canonical_a%6
            for road in (a,b):road['props']['rounded_join13']=True
            done.update((a['id'],b['id']))

def zebra(scene,hit):
    _,aid,station,q=hit;a=scene.assets[aid];q,u=g.at(a['points'],station)
    return scene.create_marking('PEDESTRIAN',[q,[q[k]+u[k]*10 for k in (0,1)]],width=a['props']['width'],crossing_asset13=aid,crossing_station13=station,crossing_skew13=0.,crossing_full13=True,crossing_depth14=4,stripe_width14=.4,spacing=.6)

def refresh_zebra(scene,aid=None):
    for a in scene.assets.values():
        p=a['props'];parent=scene.assets.get(p.get('crossing_asset13'))
        if not parent or aid and parent['id']!=aid:continue
        q,u=g.at(parent['points'],min(g.length(parent['points']),p['crossing_station13']));a['points']=[q,[q[k]+u[k]*10 for k in (0,1)]];p['width']=parent['props']['width']
