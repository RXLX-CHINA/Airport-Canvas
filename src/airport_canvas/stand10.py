"""Associative stand prefabs: origin on taxi axis, outward-facing envelopes."""
import copy
import math
import scene_geometry as g

def design(a,scene=None):
    from stand_layout9 import design as legacy
    result=legacy(a);p=a['props'];aid=p.get('entry_asset')
    if not scene or aid not in scene.assets:return result
    parent=scene.assets[aid];station=min(g.length(parent['points']),p.get('entry_station',0));q,t=g.at(parent['points'],station)
    origin=a['points'][0];u=g.unit(origin,a['points'][-1]);v=[-u[1],u[0]]
    # Warp only near the transverse baseline onto the real taxiway, preserving
    # A/D's mirrored nominal construction away from a curved parent axis.
    def adjust(point):
        delta=[point[k]-origin[k] for k in (0,1)];x=sum(delta[k]*u[k] for k in (0,1));y=sum(delta[k]*v[k] for k in (0,1));direction=1 if sum(v[k]*t[k] for k in (0,1))>=0 else -1
        qq,_=g.at(parent['points'],max(0,min(g.length(parent['points']),station+direction*y)))
        linear=[q[k]+v[k]*y for k in (0,1)];weight=max(0,1-x/max(1,p.get('lead_radius',20)))
        return [point[k]+(q[k]-origin[k])+(qq[k]-linear[k])*weight for k in (0,1)]
    result['paths']=[dict(part,points=[adjust(q) for q in part['points']]) for part in result['paths'] if part['key']!='TAXI_BASE']
    for n in result['numbers']:n['point']=adjust(n['point'])
    return result

def safety(scene,a):
    from stand_layout9 import safety as legacy
    points=legacy(scene,a)
    if not a['props'].get('outward',True):return points
    q=a['points'][-1];u=g.unit(a['points'][0],q)
    return [[x[k]-2*sum((x[j]-q[j])*u[j] for j in (0,1))*u[k] for k in (0,1)] for x in points]

def attached_stand(scene,hit,end,name='101',lead='A',bridge=False):
    _,aid,station,start=hit
    if g.distance(start,end)<15:raise ValueError('机位引入线长度至少15m')
    with scene.transaction('绘制成套机位'):
        sid=scene.create_asset('STAND',name,[start,end],entry_asset=aid,entry_station=station,lead_type=lead,outward=True,has_bridge=bridge,show_safety=True,stand_number=name)
        parent=scene.assets[aid].get('container_id')
        if parent:scene.reparent(sid,parent)
    return sid

def refresh_entries(scene,aid):
    parent=scene.assets[aid]
    for a in scene.assets.values():
        if a['kind']!='STAND' or a['props'].get('entry_asset')!=aid or not a['props'].get('entry_attached',True):continue
        s=min(g.length(parent['points']),a['props'].get('entry_station',0));q,_=g.at(parent['points'],s);delta=[q[k]-a['points'][0][k] for k in (0,1)]
        a['points']=[[point[k]+delta[k] for k in (0,1)] for point in a['points']];a['props']['entry_station']=s

def bridge(a):
    from automatic_markings import synthetic
    if not a['props'].get('has_bridge'):return {}
    q=a['points'][-1];u=g.unit(a['points'][0],q);v=[-u[1],u[0]]
    poly=[[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in [(8,6),(26,6),(26,14),(8,14)]]
    mark=synthetic(a['id'],'BRIDGE_COMPOSITE',poly,'BRIDGE');return {mark['id']:mark}

# Editor11 keeps the whole stand in a common physical approach frame.
from stand13 import safety,bridge
from stand15 import design
