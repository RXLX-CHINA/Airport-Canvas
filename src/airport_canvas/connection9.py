"""Local-tangent connections with bounded handles and finite runway ends."""
import math
import scene_geometry as g

def dot(a,b):return sum(x*y for x,y in zip(a,b))

def safe_controls(p,q,u,v,handle=None):
    d=g.distance(p,q)
    if d<.05:return [list(p),list(q)]
    chord=g.unit(p,q);h=min(handle if handle is not None else d*.4,d*.45)
    # Control projections must be ordered on the chord. This prevents a default
    # cubic turning backwards after an existing corner or creating a loop.
    a=max(0,dot(u,chord));b=max(0,dot(v,chord))
    hu=min(h,d*.45/max(a,.001));hv=min(h,d*.45/max(b,.001))
    return [[p[k]+u[k]*hu for k in (0,1)],[q[k]-v[k]*hv for k in (0,1)]]

def path_with_controls(p,q,controls):
    from curve_model import node,evaluate
    a=node(p);b=node(q);a['outgoing'],b['incoming']=controls
    return evaluate([a,b])

def port_directions(scene,first,second):
    ports=[first,second];points=[];axes=[]
    for port in ports:
        q,u=g.at(scene.assets[port['asset']]['points'],port['station']);points.append(q);axes.append(u)
    chord=g.unit(*points);result=[]
    for i,(port,u) in enumerate(zip(ports,axes)):
        a=scene.assets[port['asset']];flow=a['props'].get('flow','BOTH')
        sign=1 if flow=='FORWARD' else -1 if flow=='REVERSE' else 1 if dot(chord,u)>=0 else -1
        if a['kind']=='RUNWAY':
            length=g.length(a['points']);guard=min(60,length*.1)
            # Travel from a start-end anchor goes into the runway; travel into a
            # terminal anchor arrives from its interior. Never head off the end.
            if port['station']<=guard:sign=1 if i==0 else -1
            elif length-port['station']<=guard:sign=-1 if i==0 else 1
        result.append(sign)
    return result

def preview(scene,first,second):
    import copy
    ports=copy.deepcopy([first,second]);directions=port_directions(scene,*ports)
    points=[];tangents=[]
    for port,sign in zip(ports,directions):
        port['direction']=sign;q,u=g.at(scene.assets[port['asset']]['points'],port['station']);points.append(q);tangents.append([sign*x for x in u])
    if not needs_pavement(scene,*ports):
        plan=existing_plan(scene,*ports)
        if plan:
            for port,direction in zip(ports,plan['directions']):port['direction']=direction
            ports[0]['_follow_existing']=True
            return ports,plan['points'],plan['controls']
        raise ValueError('现有中线流向不允许该连接；请调整连接点或路线流向')
    controls=safe_controls(*points,*tangents)
    return ports,path_with_controls(*points,controls),controls

def existing_plan(scene,first,second,controls=None,radius=25):
    a=scene.assets[first['asset']]['points'];b=scene.assets[second['asset']]['points']
    def allowed(port,direction):
        flow=scene.assets[port['asset']]['props'].get('flow','BOTH')
        return flow=='BOTH' or direction==(1 if flow=='FORWARD' else -1)
    if first['asset']==second['asset']:
        path=g.subpath(a,first['station'],second['station']);direction=1 if second['station']>first['station'] else -1
        if not allowed(first,direction):return None
        from editor7_model import curve_nodes_for
        nodes=curve_nodes_for(path);c=[nodes[0]['outgoing'],nodes[-1]['incoming']]
        return dict(points=path,controls=c,directions=[direction,direction])
    hits=[]
    for p,q in zip(a,a[1:]):
        for u,v in zip(b,b[1:]):
            hit=g.crossing(p,q,u,v)
            if hit:
                sa=g.project(a,hit)[1];sb=g.project(b,hit)[1]
                if not allowed(first,1 if sa>=first['station'] else -1) or not allowed(second,1 if second['station']>=sb else -1):continue
                hits.append((abs(sa-first['station'])+abs(sb-second['station']),sa,sb))
    if not hits:return None
    _,sa,sb=min(hits);left=g.subpath(a,first['station'],sa);right=g.subpath(b,sb,second['station']);L=g.length(left);R=g.length(right)
    if min(L,R)<.1:
        path=right if L<.1 else left
        if g.length(path)<.05:return None
        tangent=g.unit(path[0],path[1]);end=g.unit(path[-2],path[-1])
        return dict(points=path,controls=safe_controls(path[0],path[-1],tangent,end),directions=[1 if sa>=first['station'] else -1,1 if second['station']>=sb else -1])
    _,u=g.at(left,L);_,v=g.at(right,0);angle=math.acos(max(-1,min(1,dot(u,v))))
    if angle<1e-5:return dict(points=left+right[1:],controls=safe_controls(left[0],right[-1],g.unit(left[0],left[1]),g.unit(right[-2],right[-1])),directions=[1 if sa>first['station'] else -1,1 if second['station']>sb else -1])
    from pavement_geometry import junction_arm
    from shapely.geometry import LineString

    _,left_reach=junction_arm(left,L,-1)
    _,right_reach=junction_arm(right,0,1)
    tangent_factor=math.tan(angle/2)
    reach=min(radius*tangent_factor,L*.49,R*.49,left_reach*.98,right_reach*.98)
    for scale in (1.,.5,.25,.125):
        d=reach*scale
        if d<.001:break
        start,us=g.at(left,L-d)
        end,vs=g.at(right,d)
        if g.distance(start,end)<.001:continue
        h=4/3*(d/tangent_factor)*math.tan(angle/4)
        automatic=[[start[k]+us[k]*h for k in (0,1)],[end[k]-vs[k]*h for k in (0,1)]]
        options=(controls,automatic) if controls and scale==1. else (automatic,)
        for c in options:
            middle=path_with_controls(start,end,c)
            path=g.subpath(left,0,L-d)[:-1]+middle+g.subpath(right,d,R)[1:]
            if LineString(path).is_simple:
                return dict(points=path,controls=c,directions=[1 if sa>first['station'] else -1,1 if second['station']>sb else -1])
    # Even with too little room for a fillet, an intersecting pair can
    # still carry guidance through its shared node.
    path=left+right[1:]
    if LineString(path).is_simple:
        return dict(points=path,controls=safe_controls(path[0],path[-1],u,v),
                    directions=[1 if sa>first['station'] else -1,1 if second['station']>sb else -1])

def needs_pavement(scene,first,second):
    """Existing intersecting parents need a painted movement, not another road."""
    if first['asset']==second['asset']:return False
    a=scene.assets[first['asset']];b=scene.assets[second['asset']]
    if a['kind']=='RUNWAY' or b['kind']=='RUNWAY':return True
    return not any(g.crossing(p,q,u,v) is not None for p,q in zip(a['points'],a['points'][1:]) for u,v in zip(b['points'],b['points'][1:]))

def pushback_ports(scene,first,second):
    import copy
    ports=copy.deepcopy([first,second])
    if scene.assets[ports[1]['asset']]['kind']=='STAND':ports.reverse()
    stand=scene.assets[ports[0]['asset']]
    if stand['kind']!='STAND':raise ValueError('推出路径必须从停机位开始')
    ports[0].update(station=g.length(stand['points']),direction=-1)
    q,u=g.at(stand['points'],ports[0]['station']);target=scene.assets[ports[1]['asset']]
    end,v=g.at(target['points'],ports[1]['station']);flow=target['props'].get('flow','BOTH');chord=g.unit(q,end)
    ports[1]['direction']=1 if flow=='FORWARD' else -1 if flow=='REVERSE' else 1 if dot(chord,v)>=0 else -1
    controls=safe_controls(q,end,[-x for x in u],[ports[1]['direction']*x for x in v])
    return ports,path_with_controls(q,end,controls),controls

def runway_extension(scene,points,runway,index=0,direction_hint=None,preserve_exterior=False,keep_direction=False):
    """Keep the parallel lead and all yellow paint between physical runway ends."""
    from scene_render import runway_center_width
    reverse=index==-1;pts=list(reversed(points)) if reverse else [list(p) for p in points]
    axis=g.unit(*runway['points']);length=g.length(runway['points']);start=runway['points'][0]
    station=dot([pts[0][k]-start[k] for k in (0,1)],axis)
    tangent=g.unit(pts[0],pts[1]);travel=direction_hint if direction_hint in (-1,1) else 1 if dot(tangent,axis)>=0 else -1
    # Extension precedes the tangent. Close to a physical end choose the
    # available interior, rather than unconditionally adding 60 m outside.
    needed=30 if runway['props'].get('code_number') in (1,2) else 60
    if not keep_direction:
        if station<needed and travel>0:travel=-1
        if length-station<needed and travel<0:travel=1
    u=[travel*x for x in axis];normal=[-axis[1],axis[0]]
    lateral=dot([pts[-1][k]-pts[0][k] for k in (0,1)],normal);side=1 if lateral>=0 else -1
    taper=30.
    if preserve_exterior:
        boundary=g.rectangle(runway['points'],runway['props']['width'])
        travelled=0.
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            if g.inside(b,boundary):
                travelled+=g.distance(a,b)
                continue
            intersections=[hit for x,y in zip(boundary,boundary[1:]+boundary[:1])
                           if (hit:=g.crossing(a,b,x,y)) is not None and g.distance(a,hit)>1e-7]
            if intersections:
                edge=min(intersections,key=lambda point:g.distance(a,point))
                taper=min(taper,travelled+g.distance(a,edge))
                pts=pts[:i+1]+[edge]+pts[i+1:]
            else:taper=min(taper,travelled)
            break
        taper=min(taper,g.length(pts))
        if taper>1e-7:
            head=g.subpath(pts,0,taper)
            tail=g.subpath(pts,taper,g.length(pts))
            pts=head+tail[1:]
    gap=runway_center_width(scene,runway)/2+.9+.075;walk=0;paint=[]
    for i,q in enumerate(pts):
        if i:walk+=g.distance(pts[i-1],q)
        t=min(1,walk/max(taper,1e-7));weight=1-3*t*t+2*t*t*t
        shifted=[q[k]+normal[k]*side*gap*weight for k in (0,1)]
        s=dot([shifted[k]-start[k] for k in (0,1)],axis)
        # Clamping the longitudinal coordinate preserves lateral geometry.
        if (not preserve_exterior or weight>0) and abs(dot([shifted[k]-start[k] for k in (0,1)],normal))<=runway['props']['width']/2:
            shifted=[shifted[k]+axis[k]*(max(0,min(length,s))-s) for k in (0,1)]
        if not paint or g.distance(paint[-1],shifted)>1e-8:paint.append(shifted)
        if preserve_exterior and i==0 and taper<=1e-7 and g.distance(shifted,q)>1e-8:
            paint.append(q)
    # Use the painted attachment station, which may differ from an
    # imported or edited endpoint outside the physical runway.
    lead_station=dot([paint[0][k]-start[k] for k in (0,1)],axis)
    available=lead_station if travel>0 else length-lead_station
    extension=min(needed,max(0,available-.075))
    if extension>1e-7:
        # For a diagonal arrival, round the lead-to-connector corner within
        # the runway instead of leaving a hard angle at the centerline.
        outgoing=g.unit(paint[0],paint[1]) if len(paint)>1 else u
        alignment=dot(outgoing,u)
        if .05<alignment<.98:
            length_before=min(12.,extension*.4,g.length(paint)*.3,taper*.4)
            while length_before>.1:
                tap,_=g.at(paint,length_before)
                lateral=dot([tap[k]-start[k] for k in (0,1)],normal)
                if abs(lateral)<runway['props']['width']/2:break
                length_before*=.5
            if length_before>.1:
                tap,tangent=g.at(paint,length_before)
                begin=[paint[0][k]-u[k]*length_before for k in (0,1)]
                bend=g.cubic(begin,tap,u,tangent,length_before*.6,steps=16)
                paint=g.subpath(paint,length_before,g.length(paint))
                paint=bend+paint[1:]
        lead=[start[k]+axis[k]*(lead_station-travel*extension)
              +normal[k]*dot([paint[0][j]-start[j] for j in (0,1)],normal)
              for k in (0,1)]
        paint.insert(0,lead)
    from shapely.geometry import LineString
    if len(paint)>1 and not LineString(paint).is_simple:
        # Avoid adding a return loop when the incoming guide already doubles
        # back close to the runway axis.
        if extension>1e-7 and len(paint)>2 and LineString(paint[1:]).is_simple:
            paint=paint[1:]
        elif len(pts)>1 and LineString(pts).is_simple:
            paint=pts
    return list(reversed(paint)) if reverse else paint
