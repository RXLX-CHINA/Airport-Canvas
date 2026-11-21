"""Associative labels, cross-pavement placements and editable guide anchors."""
import copy
import math
import re
import scene_geometry as g
from curve_model import node,evaluate

CROSS_POINTS={'HOLD_A','HOLD_B','INTERMEDIATE_POINT','RWY_THRESHOLD','THRESHOLD_HEADS','RWY_CIRCLE'}
CROSS_PATHS={'INTERMEDIATE','THRESHOLD_BAR'}
PATH_SNAPS={'RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'}
GUIDE_KEYS={'TWY_CENTER','TWY_ENHANCED','TURN_PAD_GUIDE','LEAD_IN','LEAD_OUT','AUX_LEAD','ALIGNMENT','PUSHBACK'}
AXIS_MARKS=CROSS_POINTS|CROSS_PATHS|GUIDE_KEYS|{'RWY_NUMBER','RWY_CENTER','RWY_EDGE','LOCATION','DIRECTION','MAX_SPAN','MANDATORY','NO_ENTRY','HP','PRETHRESHOLD','AIMING_POINT','TDZ_BASIC','TDZ_CODED','CLOSED_RWY','CLOSED_TWY','VOR','VOR_DIRECTION','DISPLACED_ARROW','TURN_PAD_GUIDE','TWY_EDGE','ROAD_STOP'}

def snap_path(scene,p,tolerance=15,exclude=None):
    from guidance20 import snap_axis
    assets={aid:a for aid,a in scene.assets.items() if aid!=exclude and a['kind'] in PATH_SNAPS}
    return snap_axis(scene,p,assets,tolerance,pavement=True)


def place_mark(scene,key,hit):
    _,aid,station,q=hit;a=scene.assets[aid];u=getattr(hit,'tangent',None) or g.at(a['points'],station)[1];width=a['props']['width'];v=[-u[1],u[0]]
    props=dict(label_asset=aid,attached_station=station,attached_mark=True)
    if getattr(hit,'source',None) and hit.source[0].startswith('G20-'):props['physical_axis_source']=list(hit.source)
    if key in CROSS_POINTS|CROSS_PATHS|{'PRETHRESHOLD','CLOSED_RWY','CLOSED_TWY','ROAD_STOP'}:props['width']=width
    if key=='RWY_CIRCLE':props['width']=width/2
    if key in CROSS_PATHS:
        points=[[q[k]-v[k]*width/2 for k in (0,1)],[q[k]+v[k]*width/2 for k in (0,1)]]
    else:points=[q,[q[k]+u[k]*10 for k in (0,1)]]
    if key=='MAX_SPAN':props.update(maxspan=a['props'].get('maxspan') or 36,text='')
    if key=='LOCATION':props['text']=a['props'].get('designation') or a['name']
    if key=='RWY_NUMBER' and a['kind']=='RUNWAY':
        end='a' if station<g.length(a['points'])/2 else 'b';props['text']=a['props'].get('label_'+end,'09')
        if end=='b':points=[q,[q[k]-u[k]*10 for k in (0,1)]]
    if key in {'LOCATION','DIRECTION','MAX_SPAN','MANDATORY','NO_ENTRY','HP'} and a['kind']!='RUNWAY':
        distance=width/4;points=[[pt[k]-v[k]*distance for k in (0,1)] for pt in points];props['right_offset']=distance
    return scene.create_marking(key,points,**props)

def refresh_attached_marks(scene,aid):
    from guidance20 import attachment_pose
    a=scene.assets[aid]
    for mark in scene.assets.values():
        p=mark['props']
        if mark['kind']!='MARKING' or p.get('label_asset')!=aid or not p.get('attached_mark') or p.get('axis_placement11'):continue
        key=p['mark_type'];station=min(g.length(a['points']),p.get('attached_station',0));q,u=attachment_pose(scene,a,station,p.get('physical_axis_source'));v=[-u[1],u[0]];width=a['props']['width']
        if key in CROSS_POINTS|CROSS_PATHS|{'PRETHRESHOLD','CLOSED_RWY','CLOSED_TWY','ROAD_STOP'}:p['width']=width
        if key=='RWY_CIRCLE':p['width']=width/2
        if key=='RWY_NUMBER' and a['kind']=='RUNWAY':
            end='a' if station<g.length(a['points'])/2 else 'b';p['text']=a['props'].get('label_'+end,'09')
            if end=='b':u=[-x for x in u]
        if p.get('right_offset'):
            q=[q[k]-v[k]*width/4 for k in (0,1)];p['right_offset']=width/4
        mark['points']=[[q[k]-v[k]*width/2 for k in (0,1)],[q[k]+v[k]*width/2 for k in (0,1)]] if key in CROSS_PATHS else [q,[q[k]+u[k]*10 for k in (0,1)]]

def sync_name(scene,aid,name):
    a=scene.assets[aid];network=a['props'].get('network_id');affected={aid}
    # A shared historic network ID is connectivity, not rename permission.
    # Batch naming is performed explicitly by the merge command.
    for key in affected:
        obj=scene.assets[key];obj['name']=name
        group=obj['props'].get('network_group')
        if group in scene.data['groups']:scene.data['groups'][group]['name']=name+' · 滑行道'
        if obj['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):obj['props']['designation']=name
        if obj['kind']=='STAND':obj['props']['stand_number']=name
        for gid,override in scene.data.get('generated_overrides',{}).items():
            if gid.startswith('AUTO:'+key+':') and (gid.endswith(':LOCATION') or ':STAND_NUMBER' in gid):override.get('props',{}).pop('text',None)
    for obj in scene.assets.values():
        if obj['kind']=='MARKING' and obj['props'].get('label_asset') in affected and obj['props'].get('mark_type') in ('LOCATION','STAND_NUMBER'):obj['props']['text']=name

def directions(scene,first,second):
    from connection9 import port_directions
    return port_directions(scene,first,second)

def preview_connection(scene,first,second):
    from connection9 import preview
    ports,path,_=preview(scene,first,second)
    return ports,path


def main_controls(scene,m):
    path=scene.movement_path(m['id']);p,q=path[0],path[-1]
    if m.get('bezier_controls'):return copy.deepcopy(m['bezier_controls'])
    result=[]
    for field,point,sign in (('from',p,1),('to',q,-1)):
        port=m[field];_,u=g.at(scene.assets[port['asset']]['points'],port['station']);result.append([point[k]+u[k]*port['direction']*m['handle']*sign for k in (0,1)])
    return result

def _legacy_move_anchor(scene,mid,branch,index,p):
    from junction_routes import branches
    m=scene.movements[mid]
    with scene.transaction('移动曲线交汇点'):
        if branch=='MAIN':
            side=('from','to')[index];port=m[side];points=scene.assets[port['asset']]['points'];_,station,q=g.project(points,p);old,_=g.at(points,port['station']);controls=main_controls(scene,m)
            port['station']=station
            if m.get('follow_existing'):
                from connection9 import existing_plan
                plan=existing_plan(scene,m['from'],m['to'])
                if plan:m['bezier_controls']=plan['controls']
                else:raise ValueError('移动后的连接不符合现有中线流向')
                return
            if m.get('lock_tangents',True):
                _,axis=g.at(points,station);sign=port['direction']*(1 if index==0 else -1);size=g.distance(controls[index],old)
                controls[index]=[q[k]+axis[k]*sign*size for k in (0,1)]
                m['bezier_controls']=controls
            if m.get('auto_tangent',True) and not m.get('bezier_controls'):
                ds=directions(scene,m['from'],m['to']);m['from']['direction'],m['to']['direction']=ds
            else:
                
                if not m.get('lock_tangents',True):controls[index]=[controls[index][k]+q[k]-old[k] for k in (0,1)]
                m['bezier_controls']=controls
            if m.get('geometry')=='RAPID':m['geometry']='BEZIER'
        else:
            b=next(b for b in branches(scene,m) if b['side']==branch);source=scene.movement_path(mid)
            if branch=='from':source=list(reversed(source))
            target=scene.assets[m[branch]['asset']]['points'];path=source if index==0 else target
            _,station,q=g.project(path,p);old=b['points'][0 if index==0 else -1]
            m.setdefault('branch_anchors',{}).setdefault(branch,{})['from_station' if index==0 else 'to_station']=station
            if branch in m.get('branch_controls',{}):m['branch_controls'][branch][index]=[b['controls'][index][k]+q[k]-old[k] for k in (0,1)]

def move_anchor(scene,mid,branch,index,p):
    from project10 import move_endpoint
    return move_endpoint(scene,mid,branch,index,p)

def curve_nodes_for(points):
    """Fit one cubic using chord parameters; editing handles never exposes samples."""
    p,q=points[0],points[-1];total=g.length(points);walk=0;aa=ab=bb=0.;rhs=[[0.,0.],[0.,0.]]
    for i,point in enumerate(points):
        if i:walk+=g.distance(points[i-1],point)
        t=walk/max(total,1e-9);a=3*(1-t)**2*t;b=3*(1-t)*t*t
        aa+=a*a;ab+=a*b;bb+=b*b
        for k in (0,1):
            value=point[k]-(1-t)**3*p[k]-t**3*q[k];rhs[0][k]+=a*value;rhs[1][k]+=b*value
    det=aa*bb-ab*ab;first=node(p);last=node(q)
    if det>1e-12:
        first['outgoing']=[(rhs[0][k]*bb-rhs[1][k]*ab)/det for k in (0,1)];last['incoming']=[(rhs[1][k]*aa-rhs[0][k]*ab)/det for k in (0,1)]
    else:
        first['outgoing']=[p[k]+(q[k]-p[k])/3 for k in (0,1)];last['incoming']=[p[k]+2*(q[k]-p[k])/3 for k in (0,1)]
    return [first,last]

def edit_generated_curve(scene,oid,nodes):
    from automatic_markings import generated_markings
    original=generated_markings(scene,False)[oid];origin=original['points'][0];u=g.unit(origin,original['points'][-1]);v=[-u[1],u[0]];length=max(.01,g.distance(origin,original['points'][-1]))
    local=copy.deepcopy(nodes)
    for n in local:
        for field in ('p','incoming','outgoing'):
            d=[n[field][k]-origin[k] for k in (0,1)];n[field]=[sum(d[k]*u[k] for k in (0,1))/length,sum(d[k]*v[k] for k in (0,1))]
    with scene.transaction('单独编辑生成引导线'):
        override=scene.data['generated_overrides'].setdefault(oid,{});override.update(editable_nodes=local,dx=0,dy=0,rotation=0,scale=1)

def parse_aircraft(text):
    rows=[]
    for line in re.split(r'[\n;,；，/]+',text):
        value=line.strip()
        if value and value not in rows:rows.append(value)
    return rows

def set_aircraft_list(scene,aid,stop_id,values):
    from editor6_geometry import stop_rows
    values=[str(v).strip() for v in values if str(v).strip()]
    with scene.transaction('自定义停止线适用机型'):
        a=scene.assets[aid];rows=copy.deepcopy(stop_rows(a));row=next(r for r in rows if r['id']==stop_id)
        row['aircraft_types']=list(dict.fromkeys(values));row['aircraft']=' / '.join(row['aircraft_types']);a['props']['stops']=rows

def split_route(scene,aid,station,keep_name=True):
    old=copy.deepcopy(scene.assets[aid]);parent=old.get('container_id')
    with scene.transaction('滑行道分段'):
        bid=scene.split_asset(aid,station)
        if keep_name:
            scene.assets[bid]['name']=old['name'];scene.assets[bid]['props']['designation']=old['props'].get('designation',old['name'])
            scene.assets[bid]['props']['network_id']=old['props'].get('network_id') or aid
            scene.assets[aid]['props']['network_id']=scene.assets[bid]['props']['network_id']
        if parent:scene.reparent(bid,parent)
        for obj in scene.assets.values():
            p=obj['props']
            if p.get('label_asset')==aid and p.get('attached_station',0)>station:p.update(label_asset=bid,attached_station=p['attached_station']-station)
    return bid
