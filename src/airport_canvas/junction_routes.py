"""Shared fork branches and the enclosed pavement between their centreline paths."""
import scene_geometry as g

def branches(scene,m):
    if m.get('legacy_attachment') or not m.get('pavement_visible',True) or not m.get('auto_branches',True):return []
    if m.get('geometry')=='RAPID':
        from route_geometry import reverse_join
        b=reverse_join(scene,m)
        if not b:return []
        result=[dict(b,side='to',oid=m['id']+':reverse')]
        return apply_controls(scene,m,result)
    if m.get('role') not in ('TAXIWAY_JOIN','APRON_ACCESS','ENTRY','EXIT','EXIT_ONLY','RAPID_EXIT'):return []
    original=scene.movement_path(m['id']);result=[]
    for side in ('from','to'):
        port=m[side];a=scene.assets[port['asset']]
        if a['kind'] not in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE') or a['props'].get('flow','BOTH')!='BOTH':continue
        path=original if side=='to' else list(reversed(original))
        length=g.length(path);reach=min(length*.7,max(100,m.get('join_radius',25)*5))
        if reach<10:continue
        direction=-port['direction'] if side=='to' else port['direction']
        available=(g.length(a['points'])-port['station']) if direction>0 else port['station']
        delta=min(max(80,m.get('join_radius',25)*5,reach),available-.1);station=port['station']+direction*delta
        if delta<max(m['width'],m.get('join_radius',25)):continue
        if not 0<=station<=g.length(a['points']):continue
        q,v=g.at(a['points'],station);v=[x*direction for x in v]
        from connection9 import dot,safe_controls,path_with_controls
        from shapely.geometry import LineString

        stem=LineString(path)
        target=LineString(a['points'])
        for i in range(24,0,-1):
            s=length-reach*i/24
            p,u=g.at(path,s)
            chord=g.unit(p,q)
            if dot(u,chord)<-.01 or dot(v,chord)<-.01:continue
            handle=min(reach*.6,g.distance(p,q)*.4)
            controls=safe_controls(p,q,u,v,handle)
            pts=path_with_controls(p,q,controls)
            branch=LineString(pts)
            if (not branch.is_simple or branch.intersection(stem).length>.01
                    or branch.intersection(target).length>.01):continue
            result.append(dict(points=pts,station=station,direction=direction,side=side,
                               oid=m['id']+':reverse:'+side,controls=controls))
            break
    return apply_controls(scene,m,result)

def apply_controls(scene,m,result):
    from curve_model import node,evaluate
    for b in result:
        anchors=m.get('branch_anchors',{}).get(b['side'],{})
        if anchors:
            source=scene.movement_path(m['id'])
            if b['side']=='from':source=list(reversed(source))
            target=scene.assets[m[b['side']]['asset']]['points'];old=b['points'];_,start_station,_=g.project(source,old[0])
            p,u=g.at(source,anchors.get('from_station',start_station));q,v=g.at(target,anchors.get('to_station',b['station']));v=[x*b['direction'] for x in v];h=g.distance(p,q)*.45
            b['points']=g.cubic(p,q,u,v,h,steps=64);b['station']=anchors.get('to_station',b['station']);b['controls']=[[p[k]+u[k]*h for k in (0,1)],[q[k]-v[k]*h for k in (0,1)]]
        pts=b['points'];h=g.distance(pts[0],pts[-1])*.5;u=g.unit(pts[0],pts[1]);v=g.unit(pts[-2],pts[-1])
        b.setdefault('controls',[[pts[0][k]+u[k]*h for k in (0,1)],[pts[-1][k]-v[k]*h for k in (0,1)]])
        controls=m.get('branch_controls',{}).get(b['side'])
        if controls:
            a=node(pts[0]);z=node(pts[-1]);a['outgoing']=controls[0];z['incoming']=controls[1];b['points']=evaluate([a,z]);b['controls']=controls
    return result

def fork_polygon(scene,m,branch):
    path=scene.movement_path(m['id'])
    if branch['side']=='from':path=list(reversed(path))
    bp=branch['points'];_,s,_=g.project(path,bp[0]);main=g.subpath(path,s,g.length(path))
    port=m[branch['side']];target=scene.assets[port['asset']]['points']
    # Project the actual endpoints: analytical fitting can move the live
    # connection station relative to its preferred authoring anchor.
    _,main_station,main_end=g.project(target,main[-1])
    _,branch_station,branch_end=g.project(target,bp[-1])
    if g.distance(main[-1],main_end)>.15 or g.distance(bp[-1],branch_end)>.15:
        return []
    lo,hi=sorted((main_station,branch_station))
    across=g.subpath(target,lo,hi)
    if main_station>branch_station:across.reverse()
    candidate=main+across[1:]+list(reversed(bp))[1:]
    from geometry11 import Polygon
    shape=Polygon(candidate)
    # A fork crossing an existing junction may fold back onto its stem.
    # Skip this artificial fill; the independently drawn corridors still meet.
    return candidate if shape.is_valid and shape.area>.01 else []


def terminal_stub_reach(scene,junction,aid):
    """A taxi arm ending on a runway turns at its tangent; a true crossing stays straight."""
    if aid not in junction['assets'] or aid not in scene.assets:return 0.
    index=junction['assets'].index(aid);other=junction['assets'][1-index]
    if other not in scene.assets:return 0.
    a=scene.assets[aid];s=junction['stations'][index];total=g.length(a['points'])
    if min(s,total-s)>1:return 0.
    from pavement_geometry import turn_guides
    guides=turn_guides(scene,junction)
    if not guides:return 0.
    return max(g.distance(junction['point'],x['points'][0 if index==0 else -1]) for x in guides)

def terminal_stub(scene,junction,aid,q):
    return g.distance(q,junction['point'])<terminal_stub_reach(scene,junction,aid)-1e-4
