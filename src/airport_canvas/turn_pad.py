"""Parametric runway turn pad: design template requiring aircraft swept-path review."""
import math
import scene_geometry as g
from pavement_geometry import corridor

def hull(points):
    pts=sorted(set(tuple(p) for p in points))
    cross=lambda o,a,b:(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[];upper=[]
    for p in pts:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1]+upper[:-1]]

def geometry(scene,p):
    r=scene.assets[p['pad_runway']];R=p['pad_radius'];straight=p['pad_straight'];margin=p['pad_margin'];side=p['pad_side']
    if not all(math.isfinite(v) for v in (R,straight,margin,side)) or R<10 or straight<5 or margin<3 or side not in (-1,1):raise ValueError('半径≥10m，直线≥5m，余量≥3m，侧向为 1 或 -1')
    total=g.length(r['points']);station=p['pad_station'];direction=1 if station>=total/2 else -1
    u=g.unit(*r['points']);u=[v*direction for v in u];n=[-u[1]*side,u[0]*side]
    # Position the outermost nose-track extent within the runway ends.
    end=total-R-margin if direction==1 else R+margin
    q,_=g.at(r['points'],end);lead=30 if r['props'].get('code_number') in (1,2) else 60
    transition=6*R;start=-straight-transition
    if lead+transition+straight+2*R+2*margin>total:raise ValueError('跑道长度不足以容纳当前掉头坪参数')
    gap=.9+.075+(.9 if any(r['props'].get(k) in ('2','3') for k in ('level_a','level_b')) else .45)/2
    local=[[start-lead,gap],[start,gap]]
    # Zero tangent at both ends; max slope 0.5 <= tan(30 degrees).
    for i in range(1,61):
        t=i/60;local.append([start+transition*t,gap+2*R*(3*t*t-2*t*t*t)])
    local.append([0,gap+2*R])
    for i in range(1,81):
        angle=math.pi/2-math.pi*i/80;local.append([R*math.cos(angle),gap+R+R*math.sin(angle)])
    local.append([-lead,gap])
    world=lambda point:[q[k]+u[k]*point[0]+n[k]*point[1] for k in (0,1)]
    guide=[world(point) for point in local]
    # Filled pavement includes the inside of the turn, never a shoulder island.
    # Right trapezoid: runway-parallel base/top, perpendicular end, sloping entry.
    edge=r['props']['width']/2-1;top=gap+2*R+margin;right=R+margin
    top_left=-straight-margin;left=start-margin
    poly=[world(point) for point in [(left,edge),(right,edge),(right,top),(top_left,top)]]
    if __import__('pavement_geometry').area(poly)<0:poly.reverse()
    return poly,guide

def create_turn_pad(scene,runway,station):
    p=dict(pavement_color=scene.assets[runway]['props'].get('pavement_color','#454b53'),turn_pad=True,pad_runway=runway,pad_station=station,pad_radius=25.,pad_straight=30.,pad_margin=12.,pad_side=1,
           source_note='MH5001 4.3 / 6.2.9 参数化设计；轮迹、鼻轮转角和机轮净距待机型数据复核')
    poly,guide=geometry(scene,p)
    with scene.transaction('创建跑道掉头坪'):
        aid=scene.create_asset('APRON','跑道掉头坪',poly,**p);scene.assets[aid]['pad_guide']=guide
    return aid

def update_turn_pad(scene,aid,values):
    with scene.transaction('修改掉头坪'):
        a=scene.assets[aid];a['props'].update(values);a['points'],a['pad_guide']=geometry(scene,a['props'])

def paint(scene,a):
    from scene_render import COLORS
    from pavement_geometry import offset
    r=scene.assets[a['props']['pad_runway']];u=g.unit(*r['points']);origin=r['points'][0];total=g.length(r['points']);half=r['props']['width']/2
    outside=lambda p:abs(-(p[0]-origin[0])*u[1]+(p[1]-origin[1])*u[0])>half+.1
    out=[dict(type='line',oid=a['id'],points=a['pad_guide'],stroke=COLORS['marking'],width=.15)]
    pts=a['points']+[a['points'][0]]
    for inset in (.075,.375):
        # Offset closed edge towards its interior; hull is CCW.
        path=offset(pts,inset);chunk=[]
        normal=lambda p:-(p[0]-origin[0])*u[1]+(p[1]-origin[1])*u[0]
        for p,q in zip(path,path[1:]):
            cuts={0.,1.};v0,v1=normal(p),normal(q)
            if abs(v1-v0)>1e-9:
                for bound in (-half-.1,half+.1):
                    t=(bound-v0)/(v1-v0)
                    if 0<t<1:cuts.add(t)
            values=sorted(cuts)
            for lo,hi in zip(values,values[1:]):
                mid=[p[k]+(q[k]-p[k])*(lo+hi)/2 for k in (0,1)]
                if outside(mid):
                    if not chunk:chunk=[[p[k]+(q[k]-p[k])*lo for k in (0,1)]]
                    chunk.append([p[k]+(q[k]-p[k])*hi for k in (0,1)])
                else:
                    if len(chunk)>1:out.append(dict(type='line',oid=a['id'],points=chunk,stroke=COLORS['marking'],width=.15))
                    chunk=[]
        if len(chunk)>1:out.append(dict(type='line',oid=a['id'],points=chunk,stroke=COLORS['marking'],width=.15))
    return out
