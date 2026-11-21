"""Attached off-line deicing bay; no lights are generated."""
import math
import scene_geometry as g
from curve_model import rounded_nodes,evaluate

SEPARATION={'A':15.5,'B':20.,'C':26.,'D':37.,'E':43.5,'F':51.}

def layout(scene,a):
    p=a['props'];parent=scene.assets.get(p.get('deice_parent'))
    if not parent:raise ValueError('除冰等待坪须关联一条滑行道中线')
    o,u=g.at(parent['points'],min(g.length(parent['points']),p.get('deice_station',0)));side=p.get('deice_side',1);v=[-u[1]*side,u[0]*side]
    world=lambda x,y:[o[k]+u[k]*x+v[k]*y for k in (0,1)]
    w=p.get('deice_width',140);depth=p.get('deice_depth',95);R=p.get('deice_radius',20);clear=p.get('deice_clearance',4.5);length=p.get('deice_aircraft_length',40);span=p.get('deice_wingspan',36)
    code=p.get('deice_code','C')
    if code not in SEPARATION:raise ValueError('除冰坪净距类别必须为 A～F')
    minimum=SEPARATION[code];hold=p.get('deice_hold_distance',minimum)
    if hold<minimum:raise ValueError(f'{code}类滑行道出口等待位置距中线须不小于{minimum:g}m')
    if clear<4.5:raise ValueError('车辆活动区净宽不得小于4.5m')
    if min(w,depth,R)<=0 or w<length+2*clear+2*R or depth<hold+span+2*clear:raise ValueError('除冰坪不足以容纳出入口转弯、等待净距及飞机/车辆活动区域')
    half=w/2;bottom=depth-span/2-clear
    station=min(g.length(parent['points']),p.get('deice_station',0))
    if min(station,g.length(parent['points'])-station)<half+R:raise ValueError('除冰坪两侧出入口超出相邻滑行道端点；请向滑行道内部移动或延长滑行道')
    vertices=[[-half,0],[-half+R,0],[-half+R,bottom],[half-R,bottom],[half-R,0],[half,0]]
    nodes,_=rounded_nodes(vertices,R);route=[world(*q) for q in evaluate(nodes)]
    route[0]=g.at(parent['points'],station-half)[0];route[-1]=g.at(parent['points'],station+half)[0]
    near=parent['props']['width']/2
    left=[world(-half-R+R*math.sin(math.pi/2*i/32),near+R-R*math.cos(math.pi/2*i/32)) for i in range(33)]
    right=[world(half+R-R*math.sin(math.pi/2*i/32),near+R-R*math.cos(math.pi/2*i/32)) for i in range(33)]
    pavement=[world(-half-R,0),world(half+R,0)]+right+[world(half,depth),world(-half,depth)]+list(reversed(left))
    edge=left+[world(-half,depth-.15),world(half,depth-.15)]+list(reversed(right))
    count=int(p.get('deice_bays',1));cell=length+2*clear
    if count*cell>w-2*R:raise ValueError('相邻除冰机位车辆活动区不能重叠；请加宽除冰坪')
    bays=[]
    for i in range(count):
        x=(i-(count-1)/2)*cell
        box=lambda L,W:[world(x+dx,bottom+dy) for dx,dy in [(-L/2,-W/2),(L/2,-W/2),(L/2,W/2),(-L/2,W/2)]]
        bays.append(dict(inner=box(length,span),outer=box(length+2*clear,span+2*clear),axis=[world(x-length/2,bottom),world(x+length/2,bottom)],stop=world(x+length/2-4,bottom),u=u))
    return dict(pavement=pavement,route=route,edge=edge,hold=[world(-half,hold),world(half,hold)],bays=bays,origin=o,u=u,v=v)

def draft(scene,hit,corner,**props):
    _,parent,station,o=hit;taxi=scene.assets[parent];_,u=g.at(taxi['points'],station);n=[-u[1],u[0]];delta=[corner[k]-o[k] for k in (0,1)];x=abs(sum(delta[k]*u[k] for k in (0,1)));y=sum(delta[k]*n[k] for k in (0,1));code=props.get('deice_code','C');R=props.get('deice_radius',20);clear=props.get('deice_clearance',4.5)
    props=dict(props,deice_parent=parent,deice_station=station,deice_side=1 if y>=0 else -1,deice_width=max(2*x,props.get('deice_aircraft_length',40)+2*clear+2*R+10),deice_depth=max(abs(y),SEPARATION[code]+props.get('deice_wingspan',36)+2*clear+10),deice_layout12=True,role='DEICING')
    return dict(id='DRAFT',kind='APRON',name='除冰等待坪',points=[[0,0],[1,0],[1,1],[0,1]],props=props)

def create(scene,hit,corner,**props):
    a=draft(scene,hit,corner,**props);d=layout(scene,a)
    with scene.transaction('绘制滑行道旁除冰等待坪'):
        aid=scene.create_asset('APRON','除冰等待坪',d['pavement'],**a['props'])
    return aid

def upgrade(scene,aid):
    a=scene.assets[aid];center=[sum(q[k] for q in a['points'])/len(a['points']) for k in (0,1)];candidates=[]
    for tid,t in scene.assets.items():
        if t['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):
            distance,station,q=g.project(t['points'],center);candidates.append((distance,tid,station,q))
    if not candidates:raise ValueError('请先绘制相邻滑行道')
    planned=None
    for hit in sorted(candidates):
        parent=scene.assets[hit[1]];o=hit[3];_,u=g.at(parent['points'],hit[2]);v=[-u[1],u[0]];side=1 if sum((center[k]-o[k])*v[k] for k in (0,1))>=0 else -1
        xs=[sum((q[k]-o[k])*u[k] for k in (0,1)) for q in a['points']];ys=[sum((q[k]-o[k])*v[k]*side for k in (0,1)) for q in a['points']]
        props={key:value for key,value in a['props'].items() if key.startswith('deice_') and key not in ('deice_parent','deice_station','deice_side','deice_layout12','deice_depth','deice_width')}
        corner=[o[k]+u[k]*(max(xs)-min(xs))/2+v[k]*side*max(ys) for k in (0,1)];candidate=draft(scene,hit,corner,**props);half=candidate['props']['deice_width']/2+candidate['props'].get('deice_radius',20);total=g.length(parent['points'])
        if total<2*half:continue
        candidate['props']['deice_station']=min(total-half,max(half,hit[2]))
        try:layout(scene,candidate)
        except ValueError:continue
        planned=candidate;break
    if planned is None:raise ValueError('没有足够长的相邻滑行道可以容纳除冰等待坪两侧出入口')
    with scene.transaction('按参考图重建除冰等待坪'):
        a['props'].update(planned['props']);a['points']=layout(scene,a)['pavement']
    return aid

def refresh(scene):
    for a in scene.assets.values():
        if a['props'].get('deice_layout12'):
            try:a['points']=layout(scene,a)['pavement']
            except ValueError:pass

def generated(scene):
    from automatic_markings import synthetic
    out={}
    for aid,a in scene.assets.items():
        if not a['props'].get('deice_layout12'):continue
        try:d=layout(scene,a)
        except ValueError:continue
        for key,pts,suffix,props in [('TWY_CENTER',d['route'],'GUIDE',{}),('TWY_EDGE',d['edge'],'EDGE',{}),('INTERMEDIATE',d['hold'],'EXIT_HOLD',dict(line_width=.3,dash=.9,gap=.9))]:
            m=synthetic(aid,key,pts,'DEICE12:'+suffix,**props);out[m['id']]=m
    return out
