"""Bridge-home pose with the taxiway entrance held at its original station."""
import copy,math
import scene_geometry as g
import terminal19 as terminal
from stand11 import frame

def pose(scene,a,target):
    original=a;a=copy.deepcopy(a)
    import model20
    parent=model20.axis(scene,a['props'].get('entry_asset'))
    if not parent:raise ValueError('请先将机位入口绑定到滑行道中线。')
    _,station,entry=g.project(parent['points'],a['points'][0]);shift=[entry[k]-a['points'][0][k] for k in (0,1)]
    a['points']=[[p[k]+shift[k] for k in (0,1)] for p in a['points']]
    anchor=a['points'][0];home=terminal.stand_home(scene,a);_,u,v=frame(a);length=g.distance(anchor,a['points'][-1])
    x=sum((home[k]-anchor[k])*u[k] for k in (0,1));y=sum((home[k]-anchor[k])*v[k] for k in (0,1));radius=g.distance(anchor,target)
    if radius<=abs(y):raise ValueError('目标太靠近固定入口，无法保持机位宽度。')
    forward=math.sqrt(radius*radius-y*y);new_length=forward-(x-length)
    if new_length<15:raise ValueError('机位入口至停止端至少需要15m。')
    angle=math.atan2(target[1]-anchor[1],target[0]-anchor[0])-math.atan2(y,forward)
    return dict(anchor=list(anchor),end=[anchor[k]+new_length*(math.cos(angle),math.sin(angle))[k] for k in (0,1)],angle=angle-math.atan2(u[1],u[0]),length_delta=new_length-length,old_length=length,new_length=new_length,entry_shift=shift,entry_station=station)

def target(scene,a,q,tolerance,shift=False):
    candidates=[]
    for b in terminal.buildings(scene):
        if b['props']['building_role19']!='BRIDGE':continue
        tip=terminal.bridge_tip(b)
        if g.distance(q,tip)<=tolerance:
            try:pose(scene,a,tip)
            except ValueError:continue
            candidates.append((g.distance(q,tip),b['id'],tip))
    if candidates:
        _,bid,q=min(candidates);return q,bid
    if shift:q=__import__('project10').constrain(a['points'][0],q)
    return q,None

def apply(scene,aid,q,bid=None):
    from transform11 import apply as transform,members
    a=scene.assets[aid];p=a['props'];plan=pose(scene,a,q);p['bridge_bound19']=False;p['entry_attached']=False
    if any(abs(v)>1e-9 for v in plan['entry_shift']):transform(scene,{aid},delta=plan['entry_shift'])
    # Rotate the whole kit. Its entrance stays at the same world point.
    transform(scene,{aid},center=plan['anchor'],angle=plan['angle'])
    a['points'][-1]=plan['end'];u=g.unit(plan['anchor'],plan['end']);delta=[u[k]*plan['length_delta'] for k in (0,1)]
    for childid in members(scene,{aid})-{aid}:
        child=scene.assets.get(childid)
        if child:
            for key in ('points','design_vertices','pad_guide'):
                if child.get(key):child[key]=[[q[k]+delta[k] for k in (0,1)] for q in child[key]]
            for node in child.get('curve_nodes',[]):
                for key in ('p','incoming','outgoing'):node[key]=[node[key][k]+delta[k] for k in (0,1)]
    a['points'][0]=plan['anchor'];p.update(bridge_bound19=bool(bid),bridge_anchor20_6=True,entry_attached=True,entry_station=plan['entry_station'])
    for movement in scene.movements.values():
        for side in ('from','to'):
            port=movement[side]
            if port['asset']==aid:port['station']=max(0,min(plan['new_length'],port['station']*plan['new_length']/max(.001,plan['old_length'])))
    if bid:p.update(gate_bridge19=bid,has_bridge=True)
    return plan

def preview(scene,aid,q):
    a=copy.deepcopy(scene.assets[aid]);plan=pose(scene,a,q);a['points'][0]=plan['anchor'];a['points'][-1]=plan['end'];return a
