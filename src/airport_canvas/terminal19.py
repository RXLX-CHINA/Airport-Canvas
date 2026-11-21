"""Parametric terminal bodies, edge-extruded piers and non-overlapping bridges."""
import math
import scene_geometry as g
from geometry11 import Polygon,LineString,Point,polygon,unary_union
ROLES=('TERMINAL','PIER','BRIDGE','OTHER')
def buildings(scene):return [a for a in scene.assets.values() if a['props'].get('building_role19') in ROLES]
def body(scene,q,width=140.,depth=90.,shape='RECTANGLE',points=None,number=None,role='TERMINAL'):
    if not all(math.isfinite(x) and x>0 for x in (width,depth)):raise ValueError('建筑尺寸必须是大于0的有限数')
    if points is None:
        if shape=='RECTANGLE':points=[[q[0]+x*width/2,q[1]+y*depth/2] for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        else:
            sides={'CIRCLE':64,'HEXAGON':6,'OCTAGON':8}.get(shape)
            if not sides:raise ValueError('请选圆形、矩形、六边形、八边形或自定义多边形')
            points=[[q[0]+width/2*math.cos(2*math.pi*i/sides),q[1]+depth/2*math.sin(2*math.pi*i/sides)] for i in range(sides)]
    raw=Polygon(points)
    if not raw.is_valid or raw.area<1:raise ValueError('建筑多边形不能自交，面积应大于1平方米')
    occupied = {a['props'].get('terminal_number19') for a in buildings(scene)
                if a['props']['building_role19']==role}
    if number is None:
        prefix = 'T' if role=='TERMINAL' else 'B'
        index = next(i for i in range(1,len(occupied)+2) if f'{prefix}{i:02d}' not in occupied)
        number = f'{prefix}{index:02d}'
    if number in occupied:
        raise ValueError('建筑编号已存在')
    if any(raw.intersection(polygon(a['points'])).area>.001 for a in buildings(scene)
           if not (role=='OTHER' and a['props']['building_role19']=='OTHER')):
        raise ValueError('建筑会与现有建筑重叠')
    return scene.create_asset('EQUIPMENT',number,[list(p) for p in points],
                              building_role19=role,terminal_number19=number,building_shape19=shape,width=1)
def edge(a,q):
    pts=a['points'];rows=[]
    for i,(p,z) in enumerate(zip(pts,pts[1:]+pts[:1])):
        d,s,target=g.project([p,z],q);rows.append((d,i,s,target))
    return min(rows)
def frame(a,index):
    p=a['points'][index];z=a['points'][(index+1)%len(a['points'])];u=g.unit(p,z);n=[u[1],-u[0]] if Polygon(a['points']).exterior.is_ccw else [-u[1],u[0]];return p,z,u,n
def quad(a,index,station,width,length,shear=0.):
    p,z,u,n=frame(a,index);L=g.distance(p,z)
    curved=a['props'].get('building_shape19')=='CIRCLE'
    if width<=0 or length<=0:raise ValueError('挤出尺寸必须大于0')
    if not curved and (width+2>L or not width/2+.5<=station<=L-width/2-.5):raise ValueError('此边长度或位置不足以挤出，请选择较长的边并避开拐角')
    q=[p[k]+u[k]*station for k in (0,1)]
    return [[q[k]+u[k]*(x+(shear if y else 0))+n[k]*y for k in (0,1)] for x,y in [(-width/2,0),(width/2,0),(width/2,length),(-width/2,length)]]
def root_id(a):return a['id'] if a['props'].get('building_role19')=='TERMINAL' else a['props']['terminal_root19']
def extrusion(a,index,station,target,perpendicular=False):
    origin,_,tangent,normal=frame(a,index)
    delta=[target[k]-origin[k]-tangent[k]*station for k in (0,1)]
    depth=sum(x*y for x,y in zip(delta,normal))
    if a['props'].get('building_role19')=='PIER':
        depth=abs(depth)
    return depth, (0. if perpendicular else sum(x*y for x,y in zip(delta,tangent)))

def extrude_pier(scene,aid,index,station,width=28.,length=160.,shear=0.):
    a=scene.assets[aid]
    if a['props'].get('building_role19')!='TERMINAL':raise ValueError('请先选择航站楼主体')
    if length<=0:raise ValueError('指廊长度必须大于0')
    pts=quad(a,index,station,width,length,shear);shape=Polygon(pts)
    if any(shape.intersection(polygon(b['points'])).area>.001 for b in buildings(scene)):raise ValueError('指廊与已有建筑或廊桥重叠')
    with scene.transaction('从主体边线挤出指廊'):
        pid=scene.create_asset('EQUIPMENT','指廊',pts,building_role19='PIER',terminal_root19=aid,body_edge19=index,width=1)
        scene.assets[pid]['container_id']=aid
    return pid
def extrude_bridge(scene,aid,index,station,width,length,shear=0.):
    pier=scene.assets[aid]
    if pier['props'].get('building_role19')!='PIER':raise ValueError('请先选择指廊。')
    points=quad(pier,index,station,width,length,shear)
    shape=Polygon(points)
    if any(shape.intersection(polygon(a['points'])).area>.001 for a in buildings(scene)):
        raise ValueError('廊桥与现有建筑重叠。')
    root=root_id(pier)
    used={a['props'].get('bridge_number19') for a in buildings(scene) if a['props'].get('terminal_root19')==root}
    number=next(str(i).zfill(2) for i in range(1,len(used)+2) if str(i).zfill(2) not in used)
    with scene.transaction('从指廊边缘挤出廊桥'):
        bridge=scene.create_asset('EQUIPMENT','廊桥 '+number,points,building_role19='BRIDGE',terminal_root19=root,pier_id19=aid,bridge_number19=number,width=1)
        scene.assets[bridge]['container_id']=aid
    return bridge

def eligible_edges(scene,a):
    root=scene.assets[root_id(a)];out=[]
    for i in range(len(a['points'])):
        p,z,u,n=frame(a,i);L=g.distance(p,z)
        if LineString([p,z]).intersection(polygon(root['points']).buffer(.01)).length>.1:continue
        if L>5:out.append((i,L))
    return out
def bridge_tip(a):return [(a['points'][2][k]+a['points'][3][k])/2 for k in (0,1)]
def bridge_direction(a):return g.unit([(a['points'][0][k]+a['points'][1][k])/2 for k in (0,1)],bridge_tip(a))
def bridges(scene,pier,count=6,width=3.5,length=26.):
    a=scene.assets[pier]
    if a['props'].get('building_role19')!='PIER':raise ValueError('请选择指廊')
    if not isinstance(count,int) or not 1<=count<=100 or min(width,length)<=0:raise ValueError('廊桥数量应为1～100，尺寸须为正值')
    edges=eligible_edges(scene,a);perimeter=sum(L for i,L in edges)
    if not perimeter:raise ValueError('指廊没有可用外边')
    obstacles=[polygon(b['points']).buffer(.05,join_style=2) for b in buildings(scene) if b['id']!=pier];chosen=None
    for phase in range(48):
        proposed=[]
        for j in range(count):
            pos=((j+.5+phase/48)*perimeter/count)%perimeter;cursor=0.;candidate=None
            for index,L in edges:
                if pos<cursor+L:
                    try:candidate=quad(a,index,pos-cursor,width,length)
                    except ValueError:pass
                    break
                cursor+=L
            if candidate is None:break
            shape=Polygon(candidate)
            if any(shape.intersection(ob).area>.001 for ob in obstacles) or any(shape.buffer(.5).intersects(Polygon(p)) for p in proposed):break
            proposed.append(candidate)
        if len(proposed)==count:chosen=proposed;break
    if chosen is None:raise ValueError('无法等距布置且避免碰撞；请减少数量、缩短廊桥或加长指廊。工程未改变。')
    result=[]
    with scene.transaction('等距垂直生成无重叠廊桥'):
        existing=sum(b['props'].get('building_role19')=='BRIDGE' and b['props'].get('terminal_root19')==root_id(a) for b in buildings(scene))
        for j,pts in enumerate(chosen):
            code=str(existing+j+1).zfill(2);bid=scene.create_asset('EQUIPMENT','廊桥 '+code,pts,building_role19='BRIDGE',terminal_root19=root_id(a),pier_id19=pier,bridge_number19=code,width=1)
            scene.assets[bid]['container_id']=pier;result.append(bid)
    return result
def renumber(scene,root,start_bridge,clockwise=True,start=1,digits=2):
    rows=[a for a in buildings(scene) if a['props']['building_role19']=='BRIDGE' and a['props']['terminal_root19']==root]
    if start_bridge not in {a['id'] for a in rows}:raise ValueError('请点击属于当前航站楼的起始廊桥')
    if start<0 or not 1<=digits<=8:raise ValueError('起始号须非负，位数为1～8')
    center=polygon(scene.assets[root]['points']).centroid;rows.sort(key=lambda a:math.atan2(bridge_tip(a)[1]-center.y,bridge_tip(a)[0]-center.x),reverse=clockwise);k=next(i for i,a in enumerate(rows) if a['id']==start_bridge);rows=rows[k:]+rows[:k];digits=max(digits,len(str(start+len(rows)-1)))
    with scene.transaction('从指定廊桥顺序编号'):
        for i,a in enumerate(rows):a['props']['bridge_number19']=str(start+i).zfill(digits);a['name']='廊桥 '+a['props']['bridge_number19']
    return [a['id'] for a in rows]
def stand_home(scene,a):
    from stand13 import zone
    side=-1 if a['props'].get('bridge_side','LEFT')=='RIGHT' else 1
    pts=zone(a,scene,side)
    return [sum(q[k] for q in pts)/len(pts) for k in (0,1)]

def align_stand(scene,a,tip):
    # Translate the entire kit, preserving its frame and the home circle's
    # position within that frame. Never move only the nose or the home circle.
    delta=[tip[k]-stand_home(scene,a)[k] for k in (0,1)]
    if math.hypot(*delta)<1e-8:return
    from transform11 import members
    for aid in members(scene,{a['id']}):
        child=scene.assets.get(aid)
        if not child:continue
        for key in ('points','design_vertices','pad_guide'):
            if child.get(key):child[key]=[[q[k]+delta[k] for k in (0,1)] for q in child[key]]
        for node in child.get('curve_nodes',[]):
            for key in ('p','incoming','outgoing'):node[key]=[node[key][k]+delta[k] for k in (0,1)]
    parent=scene.assets.get(a['props'].get('entry_asset'))
    if parent:
        distance,station,_=g.project(parent['points'],a['points'][0])
        a['props'].update(entry_station=station,entry_attached=distance<.05)

def snap_stand(scene,aid,tolerance=5.):
    a=scene.assets[aid];p=a['props'];choices=[];home=stand_home(scene,a)
    for b in buildings(scene):
        if b['props']['building_role19']!='BRIDGE':continue
        tip=bridge_tip(b);choices.append((g.distance(home,tip),b['id'],tip))
    if choices and min(choices)[0]<=tolerance:
        _,bid,q=min(choices)
        with scene.transaction('Align whole stand to bridge head'):
            align_stand(scene,a,q);p.update(gate_bridge19=bid,bridge_bound19=True,has_bridge=True)
        return bid
    p['bridge_bound19']=False;return None
def sync(scene):
    for a in scene.assets.values():
        p=a['props']
        if a['kind']=='STAND' and p.get('bridge_bound19'):
            bridge=scene.assets.get(p.get('gate_bridge19'))
            if bridge:
                if p.get('bridge_anchor20_6'):
                    if g.distance(stand_home(scene,a),bridge_tip(bridge))>1e-6:
                        try:__import__('bridge_handle20_6').apply(scene,a['id'],bridge_tip(bridge),bridge['id'])
                        except ValueError:p['bridge_bound19']=False
                else:align_stand(scene,a,bridge_tip(bridge))
            else:p['bridge_bound19']=False
def items(scene):
    result=[]
    for a in buildings(scene):
        p=a['props'];role=p['building_role19'];fill={'TERMINAL':'#bfd1de','PIER':'#d1dce5','BRIDGE':'#a4bccb','OTHER':'#c9c2b9'}[role];result.append(dict(type='polygon',oid=a['id'],points=a['points'],fill=p.get('building_color19',fill),stroke='#ffffff' if role=='BRIDGE' and p.get('white_outline',False) else None,width=.35,building19=True));q=polygon(a['points']).centroid;label=p.get('terminal_number19','') if role in ('TERMINAL','OTHER') else p.get('bridge_number19','') if role=='BRIDGE' else ''
        if label:result.append(dict(type='text',oid=a['id'],points=[[q.x,q.y]],text=label,fill='#15354b',size=p.get('building_text_height20_3',4 if role=='BRIDGE' else 10),rotation=0,world_text=True,building19=True))
    labels=[i for i in result if i['type']=='text'];result=[i for i in result if i['type']!='text']+__import__('terminal_style20_3').outlines(buildings(scene))+labels
    # Roof indication remains open so the stand guidance stays readable.
    for a in scene.assets.values():
        if a['kind']=='STAND' and a['props'].get('hangar19'):
            from stand13 import safety
            shape=polygon(safety(scene,a));x0,y0,x1,y1=shape.bounds;pts=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]];result += [dict(type='polygon',oid=a['id'],points=pts,fill=None,stroke='#405665',width=.4,hangar19=True),dict(type='line',oid=a['id'],points=[[x0,(y0+y1)/2],[x1,(y0+y1)/2]],stroke='#405665',width=.4,hangar19=True)]
    return result
def checks(scene):
    result=[]
    for a in buildings(scene):
        if a['props']['building_role19']=='BRIDGE':continue
        building=polygon(a['points'])
        for b in scene.assets.values():
            if b['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','ROAD'):surface=LineString(b['points']).buffer(b['props']['width']/2,cap_style=2)
            elif b['kind']=='APRON':surface=polygon(b['points'])
            else:continue
            if building.intersection(surface).area>.05:result.append(dict(object_id=a['id'],status='REVIEW_REQUIRED',rule='BUILDING_PAVEMENT19',message=a['name']+' 与道面 '+b['name']+' 重叠，请调整建筑或道面。',source='项目平面冲突检查；不含廊桥',actual=b['id'],required='建筑主体/指廊不穿越道面'))
    return result
