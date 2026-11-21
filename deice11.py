"""MH5001-2021 4.14: internal aircraft bays and separate vehicle clearance."""
import math
import scene_geometry as g

def bays(a):
    p=a['props'];o=a['points'][0];u=g.unit(o,a['points'][1]);v=[-u[1],u[0]]
    project=lambda q:[sum((q[k]-o[k])*axis[k] for k in (0,1)) for axis in (u,v)]
    coords=[project(q) for q in a['points']];lo=[min(q[k] for q in coords) for k in (0,1)];hi=[max(q[k] for q in coords) for k in (0,1)]
    length=p.get('deice_aircraft_length',40);span=p.get('deice_wingspan',36);clear=p.get('deice_clearance',4.5);count=int(p.get('deice_bays',1));cell=span+2*clear;depth=length+2*clear
    if clear<4.5 or count<1:raise ValueError('除冰车辆外围净宽宜不小于4.5m，机位数至少1')
    if hi[0]-lo[0]<depth or hi[1]-lo[1]<count*cell:raise ValueError('除冰坪不足以容纳飞机内区与各机位独立的车辆活动区')
    world=lambda q:[o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    out=[]
    for i in range(count):
        center=[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2+(i-(count-1)/2)*cell]
        box=lambda l,w:[world([center[0]+x,center[1]+y]) for x,y in [(-l/2,-w/2),(l/2,-w/2),(l/2,w/2),(-l/2,w/2)]]
        out.append(dict(inner=box(length,span),outer=box(depth,cell),axis=[world([lo[0]+clear,center[1]]),world([hi[0]-clear,center[1]])],stop=world([center[0]+length/2-4,center[1]]),u=u))
    return out

def generated(scene):
    from automatic_markings import synthetic
    out={}
    for aid,a in scene.assets.items():
        if a['props'].get('role')!='DEICING' or a['props'].get('deice_layout12'):continue
        try:layout=bays(a)
        except ValueError:continue
        for i,bay in enumerate(layout):
            mark=synthetic(aid,'TWY_CENTER',bay['axis'],f'DEICE:{i}:CENTER');out[mark['id']]=mark
            q=bay['stop'];u=bay['u'];mark=synthetic(aid,'STAND_STOP',[q,[q[k]+u[k]*10 for k in (0,1)]],f'DEICE:{i}:STOP',width=2,aircraft='',stop_shape='T');out[mark['id']]=mark
    from deice12 import generated as attached
    out.update(attached(scene));return out

def checks(scene):
    out=[]
    for aid,a in scene.assets.items():
        p=a['props']
        if p.get('role')!='DEICING':continue
        def issue(rule,status,text):out.append(dict(object_id=aid,rule=rule,status=status,message=text,source='MH5001—2021 4.14',actual=None,required=None))
        try:
            if p.get('deice_layout12'):__import__('deice12').layout(scene,a)
            else:bays(a)
            issue('DEICE_SPACE','PASS','二维停机内区与各机位外围车辆活动净宽检查通过；未代替真实机型包络')
        except ValueError as exc:issue('DEICE_SPACE','FAIL',str(exc))
        limit=1.5 if p.get('deice_crossfall_mode','SINGLE')=='SYMMETRIC' else 1.0
        if p.get('deice_crossfall') is None:issue('DEICE_SLOPE','UNKNOWN','请提供横坡；单面坡不大于1.0%，对称双面坡不大于1.5%')
        elif p['deice_crossfall']>limit:issue('DEICE_SLOPE','FAIL','所设横坡超过当前坡型限值')
        if p.get('deice_vehicles',2)<2:issue('DEICE_VEHICLES','REVIEW_REQUIRED','外围场地须考虑两部及以上车辆运行')
        issue('DEICE_OPERATION','REVIEW_REQUIRED','需核对保持时间、进出/旁通路线、相邻滑行道净距、承载与除冰液收集处理方案')
    return out
