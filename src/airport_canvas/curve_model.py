"""Editable cubic nodes; sampled points are a backwards-compatible render cache."""
import copy
import math
import uuid
import scene_geometry as g

TAXI_KINDS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')

def editable_vertices(a):
    if a.get('design_vertices'):return a['design_vertices']
    if a.get('curve_nodes'):return [n['p'] for n in a['curve_nodes']]
    pts=a['points'];tolerance=.05
    while len(pts)>16:
        pts=g.simplify(a['points'],tolerance);tolerance*=1.7
    return pts

def sync_authoring(a,points):
    if not a.get('curve_nodes'):return
    cached=evaluate(a['curve_nodes'])
    if len(cached)==len(points) and all(g.distance(x,y)<1e-7 for x,y in zip(cached,points)):return
    old=a['points']
    if len(old)!=len(points):return
    delta=[points[0][k]-old[0][k] for k in (0,1)]
    if all(g.distance([q[k]+delta[k] for k in (0,1)],r)<1e-6 for q,r in zip(old,points)):
        transform=lambda p:[p[k]+delta[k] for k in (0,1)]
    elif len(old)==len(points)==2:
        u=g.unit(*old);v=g.unit(*points);scale=g.length(points)/g.length(old)
        def transform(p):
            d=[p[k]-old[0][k] for k in (0,1)];x=sum(d[k]*u[k] for k in (0,1))*scale;y=(-d[0]*u[1]+d[1]*u[0])*scale
            return [points[0][0]+x*v[0]-y*v[1],points[0][1]+x*v[1]+y*v[0]]
    else:return
    if a.get('design_vertices'):a['design_vertices']=[transform(p) for p in a['design_vertices']]
    for n in a['curve_nodes']:
        for key in ('p','incoming','outgoing'):n[key]=transform(n[key])

def rounded_nodes(vertices,radius=25,radii=None):
    """Circular fillets converted to cubic arcs; adjacent tangencies never overlap.

    Radius is a requested value. Tight legs constrain the effective radius;
    the editor reports this instead of silently moving a design vertex.
    """
    if not math.isfinite(radius) or radius<0:raise ValueError('圆角半径必须为有限非负数')
    if len(vertices)<2:raise ValueError('至少需要两个折线顶点')
    if any(g.distance(a,b)<.05 for a,b in zip(vertices,vertices[1:])):raise ValueError('相邻顶点过近')
    turns={};radii=radii or {}
    for i in range(1,len(vertices)-1):
        p=vertices[i];u=g.unit(vertices[i-1],p);v=g.unit(p,vertices[i+1]);angle=math.acos(max(-1,min(1,sum(u[k]*v[k] for k in (0,1)))))
        r=float(radii.get(str(i),radius))
        if not math.isfinite(r) or r<0:raise ValueError('顶点半径必须为有限非负数')
        if angle>math.radians(175):raise ValueError('折线接近原地掉头，请增加过渡顶点')
        if angle<1e-5 or r==0:continue
        d=min(r*math.tan(angle/2),g.distance(vertices[i-1],p)*.49,g.distance(p,vertices[i+1])*.49)
        effective=d/math.tan(angle/2);h=4/3*effective*math.tan(angle/4)
        a=[p[k]-u[k]*d for k in (0,1)];b=[p[k]+v[k]*d for k in (0,1)]
        turns[i]=(a,b,u,v,h,effective)
    nodes=[node(vertices[0])];effective={}
    for i in range(1,len(vertices)-1):
        if i in turns:
            a,b,u,v,h,r=turns[i];first=node(a);last=node(b)
            first['outgoing']=[a[k]+u[k]*h for k in (0,1)];last['incoming']=[b[k]-v[k]*h for k in (0,1)]
            nodes.extend([first,last]);effective[str(i)]=r
        else:nodes.append(node(vertices[i]))
    nodes.append(node(vertices[-1]));return nodes,effective

def rebuild_rounded(scene,aid,vertices=None,radius=None,radii=None):
    a=scene.assets[aid];p=a['props'];vertices=copy.deepcopy(vertices or a.get('design_vertices') or a['points'])
    radius=p.get('corner_radius',25) if radius is None else radius
    radii=copy.deepcopy(p.get('corner_radii',{}) if radii is None else radii)
    # Resolve each end once. A node shared by several taxiways cannot
    # independently slide along each axis in movement iteration order.
    length=g.length(a['points'])
    endpoint_links={}
    anchors=[]
    for movement in scene.movements.values():
        if not movement.get('legacy_attachment'):continue
        port,target=movement['to'],movement['from']
        if port['asset']!=aid:continue
        end=0 if port['station']<.01 else -1 if abs(port['station']-length)<.01 else None
        if end is not None:
            endpoint_links.setdefault(end,[]).append((movement['id'],target))
    for end,links in endpoint_links.items():
        if len(links)>1:
            vertices[end]=list(a['points'][end])
            continue
        mid,target=links[0]
        _,station,point=g.project(scene.assets[target['asset']]['points'],vertices[end])
        vertices[end]=point
        anchors.append((mid,'from',station))
    nodes,effective=rounded_nodes(vertices,radius,radii)
    with scene.transaction('修改折线与圆角'):
        set_nodes(scene,aid,nodes);a['design_vertices']=vertices
        a['props'].update(corner_radius=radius,corner_radii=radii,effective_radii=effective)
        for mid,side,station in anchors:scene.movements[mid][side]['station']=station
        follow_welds(scene,aid)

def follow_welds(scene,aid):
    """When a trunk changes, its snapped child endpoints follow the shared anchor."""
    for m in scene.movements.values():
        if not m.get('legacy_attachment'):continue
        for side,other in (('from','to'),('to','from')):
            port,target=m[side],m[other]
            if port['asset']!=aid or target['asset']==aid:continue
            child=scene.assets[target['asset']];total=g.length(child['points'])
            if child['kind']=='RUNWAY':continue
            index=0 if target['station']<.01 else -1 if abs(target['station']-total)<.01 else None
            if index is None:continue
            point,_=g.at(scene.assets[aid]['points'],port['station']);vertices=copy.deepcopy(child.get('design_vertices') or child['points']);vertices[index]=point
            nodes,effective=rounded_nodes(vertices,child['props'].get('corner_radius',25),child['props'].get('corner_radii'))
            pts=evaluate(nodes);new=g.length(pts)
            for link in scene.movements.values():
                for field in ('from','to'):
                    if link[field]['asset']==child['id']:link[field]['station']*=new/total
            child.update(points=pts,curve_nodes=nodes,design_vertices=vertices);child['props']['effective_radii']=effective

def create_rounded(scene,kind,name,vertices,radius=25,tolerance=2):
    vertices=copy.deepcopy(vertices)
    for i in (0,len(vertices)-1):
        hit=snap(scene,vertices[i],tolerance)
        if hit:vertices[i]=hit[3]
    nodes,effective=rounded_nodes(vertices,radius)
    with scene.transaction('绘制圆角折线滑行道'):
        aid=create_curve(scene,kind,name,nodes,tolerance)
        a=scene.assets[aid];a['design_vertices']=vertices
        a['props'].update(corner_radius=radius,corner_radii={},effective_radii=effective)
    return aid

def node(p,handle=None):
    d=handle or [0,0]
    return dict(p=list(p),incoming=[p[k]-d[k] for k in (0,1)],outgoing=[p[k]+d[k] for k in (0,1)],smooth=True)

def nodes_for(asset):
    return copy.deepcopy(asset.get('curve_nodes') or [node(p) for p in asset['points']])

def evaluate(nodes,tolerance=.03):
    """Adaptive subdivision, bounded error in metres, independent of zoom."""
    result=[list(nodes[0]['p'])]
    def walk(p,a,b,q,depth=0):
        chord=g.distance(p,q)
        if depth>=14 or (max(g.project([p,q],a)[0],g.project([p,q],b)[0])<=tolerance and g.distance(p,a)+g.distance(a,b)+g.distance(b,q)-chord<=tolerance):
            if g.distance(result[-1],q)>1e-8:result.append(list(q))
            return
        mid=lambda x,y:[(x[k]+y[k])/2 for k in (0,1)]
        pa,ab,bq=mid(p,a),mid(a,b),mid(b,q);x,y=mid(pa,ab),mid(ab,bq);z=mid(x,y)
        walk(p,pa,x,z,depth+1);walk(z,y,bq,q,depth+1)
    for a,b in zip(nodes,nodes[1:]):walk(a['p'],a['outgoing'],b['incoming'],b['p'])
    if len(result)<2:raise ValueError('至少需要两个不同的曲线节点')
    if len(result)>5000:raise ValueError('曲线过于复杂，请分段绘制')
    return result

def set_nodes(scene,aid,nodes):
    points=evaluate(nodes);previous=scene.assets[aid]['points']
    old=g.length(previous);new=g.length(points)
    with scene.transaction('编辑曲线节点'):
        for m in scene.movements.values():
            for side in ('from','to'):
                port=m[side]
                if port['asset']!=aid:continue
                station=port['station']
                if m.get('legacy_attachment') and .01<station<old-.01:
                    anchor,_=g.at(previous,station)
                    port['station']=g.project(points,anchor)[1]
                else:
                    port['station']=station*new/old
        scene.assets[aid]['curve_nodes']=copy.deepcopy(nodes)
        scene.update_asset(aid,points=points)

def snap(scene,p,tolerance,exclude=None,visible=None):
    from guidance20 import snap_axis
    kinds=('ROAD',) if exclude in scene.assets and scene.assets[exclude]['kind']=='ROAD' else TAXI_KINDS+('RUNWAY',)
    assets={aid:a for aid,a in scene.assets.items() if aid!=exclude and a['kind'] in kinds and (visible is None or visible(aid))}
    return snap_axis(scene,p,assets,tolerance)


def junction_connections(scene,aid,point):
    """Return other taxi axes meeting the same snapped junction."""
    from pavement_geometry import crossings
    stations={}
    nearby=[junction for junction in crossings(scene) if g.distance(junction['point'],point)<=.02]
    if not any(aid in junction['assets'] for junction in nearby):return ()
    for junction in nearby:
        for other,station in zip(junction['assets'],junction['stations']):
            asset=scene.assets.get(other)
            if other!=aid and asset and asset['kind'] in TAXI_KINDS and not asset['props'].get('closed'):
                _,actual,projected=g.project(asset['points'],point)
                if g.distance(projected,point)<=.02:stations[other]=actual
    return stations.items()


def create_curve(scene,kind,name,nodes,tolerance=2):
    """Branches retain editable geometry, sharing a taxiway identity and tree group."""
    nodes=copy.deepcopy(nodes);hits=[];secondary=set()
    for i in (0,len(nodes)-1):
        hit=snap(scene,nodes[i]['p'],tolerance)
        if hit:
            delta=[hit[3][k]-nodes[i]['p'][k] for k in (0,1)]
            for field in ('p','incoming','outgoing'):nodes[i][field]=[nodes[i][field][k]+delta[k] for k in (0,1)]
            hits.append((i,hit))
            if scene.assets[hit[1]]['kind'] in TAXI_KINDS:
                for other,station in junction_connections(scene,hit[1],hit[3]):
                    hits.append((i,(hit[0],other,station,hit[3])))
                    secondary.add((i,other))
    with scene.transaction('绘制曲线并吸附滑行道'):
        identity=None;group=None;designation=name
        taxi_hits=[hit for hit in hits if scene.assets[hit[1][1]]['kind'] in TAXI_KINDS]
        if taxi_hits:
            owner=scene.assets[taxi_hits[0][1][1]];identity=owner['props'].get('network_id') or 'N-'+uuid.uuid4().hex[:10]
            designation=owner['props'].get('designation') or owner['name']
            group=owner['props'].get('network_group')
            if group not in scene.data['groups']:group=scene.create_group(designation+' · 滑行道')
            owner['props'].update(network_id=identity,network_group=group,designation=designation)
            scene.reparent(owner['id'],group)
        style={}
        if taxi_hits:
            first=scene.assets[taxi_hits[0][1][1]]['props']
            style={k:first[k] for k in ('width','shoulder','pavement_color','shoulder_color','black_outline') if k in first}
        aid=scene.create_asset(kind,designation,evaluate(nodes),designation=designation,network_id=identity or 'N-'+uuid.uuid4().hex[:10],**style)
        a=scene.assets[aid];a['curve_nodes']=nodes
        if group:a['props']['network_group']=group;scene.reparent(aid,group)
        for index,hit in hits:
            owner=scene.assets[hit[1]]
            if owner['kind']=='RUNWAY':
                end=0. if index==0 else g.length(a['points'])
                scene.connect(dict(asset=hit[1],station=hit[2],direction=1),dict(asset=aid,station=end,direction=1),bidirectional=True,legacy_attachment=True,pavement_visible=False,guide_visible=False,name=designation+' · 跑道中线锚点',handle=1)
                continue
            if (index,hit[1]) not in secondary:
                other_id=owner['props'].get('network_id')
                # Joining two previously separate networks merges their designation.
                if other_id and other_id!=a['props']['network_id']:
                    for obj in scene.assets.values():
                        if obj['props'].get('network_id')==other_id:
                            obj['props'].update(network_id=a['props']['network_id'],network_group=group,designation=designation);obj['name']=designation
                            scene.reparent(obj['id'],group)
                owner['props'].update(network_id=a['props']['network_id'],network_group=group,designation=designation);owner['name']=designation
                scene.reparent(owner['id'],group)
            end=0. if index==0 else g.length(a['points'])
            scene.connect(dict(asset=hit[1],station=hit[2],direction=1),dict(asset=aid,station=end,direction=1),
                          bidirectional=True,legacy_attachment=True,pavement_visible=False,guide_visible=False,
                          name=designation+' · 吸附节点',handle=1)
    return aid

def runway_heading(scene,asset):
    u=g.unit(asset['points'][0],asset['points'][-1]);meta=scene.data['meta']
    true=(math.degrees(math.atan2(u[0],u[1]))+meta.get('grid_north_true_heading',0))%360
    decl=meta.get('magnetic_declination')
    magnetic=(true-(decl or 0))%360
    number=int(math.floor(magnetic/10+.5))%36 or 36
    return magnetic,f'{number:02d}',f'{(number+17)%36+1:02d}',decl is not None

def number_runway(scene,aid):
    a=scene.assets[aid];heading,first,second,known=runway_heading(scene,a)
    suffix=a['props'].get('runway_suffix','');opposite={'L':'R','R':'L','C':'C','':''}[suffix]
    a['props'].update(label_a=first+suffix,label_b=second+opposite,magnetic_heading=heading,
                      heading_status='MAGNETIC_INPUT' if known else 'DECLINATION_REQUIRED')

def move_node(nodes,index,field,p,mirror=True):
    n=nodes[index];old=n[field];delta=[p[k]-old[k] for k in (0,1)];n[field]=list(p)
    if field=='p':
        for key in ('incoming','outgoing'):n[key]=[n[key][k]+delta[k] for k in (0,1)]
    elif mirror and n.get('smooth',True):
        other='incoming' if field=='outgoing' else 'outgoing';n[other]=[2*n['p'][k]-p[k] for k in (0,1)]

def insert_node(nodes,segment,t=.5):
    a,b=nodes[segment:segment+2];mix=lambda p,q:[(1-t)*p[k]+t*q[k] for k in (0,1)]
    x,y,z=mix(a['p'],a['outgoing']),mix(a['outgoing'],b['incoming']),mix(b['incoming'],b['p'])
    u,v=mix(x,y),mix(y,z);p=mix(u,v);a['outgoing']=x;b['incoming']=z
    nodes.insert(segment+1,dict(p=p,incoming=u,outgoing=v,smooth=True))

def split_curve_nodes(nodes,station):
    total=0
    for i in range(len(nodes)-1):
        length=g.length(evaluate(nodes[i:i+2]))
        if total+length>=station:
            lo,hi=0.,1.
            for _ in range(24):
                t=(lo+hi)/2;temp=copy.deepcopy(nodes[i:i+2]);insert_node(temp,0,t)
                if g.length(evaluate(temp[:2]))<station-total:lo=t
                else:hi=t
            result=copy.deepcopy(nodes);insert_node(result,i,(lo+hi)/2)
            return result[:i+2],result[i+1:]
        total+=length
    raise ValueError('打断位置超出曲线')
