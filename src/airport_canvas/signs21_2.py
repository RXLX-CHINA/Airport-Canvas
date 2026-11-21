"""Destination anchors and automatic information at apron boundaries and rapid exits."""
import math
import scene_geometry as g
from segments18 import routes, piece_at

# Clockwise from the direction of travel, in face-local (forward, right) coordinates.
ARROWS = {
    '↑': (1, 0), '↗': (.707107, .707107), '→': (0, 1), '↘': (-.707107, .707107),
    '↓': (-1, 0), '↙': (-.707107, -.707107), '←': (0, -1), '↖': (.707107, -.707107),
}
ORDER = '←↖↙↑↓↘↗→'
DESTINATIONS = ('APRON','CARGO','RUNUP','INTL','MIL','CIVIL','DEICING')


def apron_name(asset):
    p=asset['props']
    code=p.get('destination_code23') or ('DEICING' if p.get('deice_layout12') or p.get('role')=='DEICING' else 'APRON')
    return code if code in DESTINATIONS else 'APRON'


def source_axis(scene,aid,network):
    asset=network.get(aid) or scene.assets.get(aid)
    if asset and asset['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','RUNWAY','ROAD'):
        return asset
    return None


def station_at(props,axis,target=False):
    length=g.length(axis['points'])
    absolute='sign_target_station26' if target else 'sign_station26'
    fraction='sign_target_fraction21_2' if target else 'sign_fraction21_2'
    return max(0,min(length,props.get(absolute,length*props.get(fraction,0))))


def all_references(scene):
    for asset in scene.assets.values():
        p=asset['props']
        yield p
        yield from p.get('sign_extra_targets',[])


def remap_split(scene,old,new,cut,total):
    for p in all_references(scene):
        for ref,absolute,fraction in (
            ('sign_axis21_2','sign_station26','sign_fraction21_2'),
            ('sign_target21_2','sign_target_station26','sign_target_fraction21_2'),
        ):
            if p.get(ref)!=old:continue
            station=p.get(absolute,total*p.get(fraction,0))
            if station>cut:p[ref],station=new,station-cut
            p[absolute]=station
            length=g.length(scene.assets[p[ref]]['points'])
            p[fraction]=station/length if length else 0


def shift_stations(scene,aid,length,delta):
    for p in all_references(scene):
        for ref,absolute,fraction in (
            ('sign_axis21_2','sign_station26','sign_fraction21_2'),
            ('sign_target21_2','sign_target_station26','sign_target_fraction21_2'),
        ):
            if p.get(ref)==aid:
                p[absolute]=p.get(absolute,length*p.get(fraction,0))+delta


def bind_existing(scene,oid,axis,station,physical=None):
    from guidance20 import attachment_pose
    mark=scene.assets[oid]
    p=mark['props']
    _,u=attachment_pose(scene,axis,station,physical)
    direction=g.unit(*[mark['points'][i] for i in (0,-1)])
    travel=1 if sum(a*b for a,b in zip(u,direction))>=0 else -1
    with scene.transaction('重新绑定标记牌来源'):
        p.update(sign_axis21_2=axis['id'],sign_station26=station,sign_travel21_2=travel)
        p['physical_axis_source']=list(physical) if physical else None
        if not p.get('sign_target21_2'):p['sign_static_face26']=True
        if p.get('sign_role23')=='VACATED':p['sign_location_dynamic26']=True


def special(scene,source,station,kind,label,direction,sides,toward=None,**face):
    axis=source_axis(scene,source,routes(scene))
    if not axis:raise ValueError('标记牌没有有效的来源路线')
    from guidance20 import attachment_pose
    q,u=attachment_pose(scene,axis,station,face.get('physical_axis_source'))
    travel=-1 if toward and sum(u[k]*(toward[k]-q[k]) for k in (0,1))<0 else 1
    with scene.transaction('放置标记牌'):
        for side in sides:
            p=sign_props(label,[direction] if direction else [],kind!='FREQUENCY_PAVEMENT',
                         side,axis['props']['width'],location=False)
            if p is None:
                raise ValueError('滑行道宽度不足，无法放置 HP 道面标识')
            p.update(sign_role23=kind, sign_axis21_2=source,sign_station26=station,
                     sign_fraction21_2=station/max(.001,g.length(axis['points'])),
                     sign_travel21_2=travel,sign_static_face26=True)
            p['sign_location_dynamic26']=kind=='VACATED' or (kind=='LOCATION_BOARD' and label==piece_at(axis,station)['name']) or (
                kind=='RUNWAY_NUMBER' and face.get('location_name20_18')==piece_at(axis,station)['name'])
            p['standard_clause20_18']={'TAKEOFF':'9.7.4.7','HOLD_BOARD':'9.7.3.7','FREQUENCY':'9.7.3.10'}.get(kind,'9.7.3/9.7.4')
            p.update(face)
            scene.create_marking('DIRECTION',pose(axis,station,travel,p,scene),name=label,**p)



def arrow(u, v):
    angle = math.atan2(u[1]*v[0]-u[0]*v[1], u[0]*v[0]+u[1]*v[1])
    return tuple(ARROWS)[round(angle/(math.pi/4)) % 8]


def ordered(arrows):
    return [key for key in ORDER if key in arrows]


def sign_props(name, arrows, board, side, width, own='', location=True):
    arrows = ordered(arrows)
    height = .4 if board else min(2, (width/2-1.7)/max(1, len(name)*.58+len(arrows)*.88))
    if height < .5 and not board:
        return None
    return dict(text=name, text_height=height, information_profile20_18='BOARD' if board else 'PAVEMENT',
                direction_name20_18=name, direction_arrows20_18=arrows,
                location_name20_18=own if board and location else '',
                standard_clause20_18='9.7.2/9.7.4' if board else '8.2.13',
                direction_side21_2=side)


def pose(axis, station, travel, props, scene=None):
    from guidance20 import attachment_pose
    q,u=attachment_pose(scene,axis,station,props.get('physical_axis_source') if scene is not None else None)
    u = [x*travel for x in u]
    width = axis['props']['width']
    h = props['text_height']
    label = props['direction_name20_18']
    half = (len(label)*.6+len(props['direction_arrows20_18'])*.9)*h/2
    half=props.get('sign_ground_span',half*2)/2
    board = props['information_profile20_18']=='BOARD'
    offset = width/2+11+half if board else min(width/2-half-.25, half+.55)
    v = [-u[1],u[0]]
    side = 1 if props['direction_side21_2']=='LEFT' else -1
    o = [q[k]+v[k]*offset*side for k in (0,1)]
    return [o, [o[k]+10*u[k] for k in (0,1)]]


def target_name(scene, target, point, network):
    asset = network.get(target) or scene.assets.get(target)
    if not asset:
        raise ValueError('目的地不存在')
    if asset['kind']=='RUNWAY':
        end = 'a' if g.distance(point,asset['points'][0]) <= g.distance(point,asset['points'][-1]) else 'b'
        return asset['props'].get('label_'+end) or asset['name']
    if asset['kind']=='APRON':
        return apron_name(asset)
    return piece_at(asset,g.project(asset['points'],point)[1])['name']


def resolve(scene, mark, network, junctions=None):
    from guidance20 import attachment_pose
    p = mark['props']
    axis = source_axis(scene,p['sign_axis21_2'],network)
    target_id=p.get('sign_target21_2')
    target=network.get(target_id) or scene.assets.get(target_id)
    if not axis or target_id and not target:return None
    if not -.05<=p.get('sign_station26',station_at(p,axis))<=g.length(axis['points'])+.05:return None
    at=station_at(p,axis)
    updated=dict(p,sign_station26=p.get('sign_station26',at))
    custom=p.get('sign_custom_text')
    if p.get('sign_static_face26'):
        if p.get('sign_location_dynamic26'):
            location=piece_at(axis,at)['name']
            updated['location_name20_18']=custom if custom is not None and p.get('sign_role23')=='VACATED' else location
            if p.get('sign_role23') in ('VACATED','LOCATION_BOARD') and custom is None:
                updated.update(direction_name20_18=location,text=location)
        if p.get('sign_role23')=='TAKEOFF' and target:
            q,u=attachment_pose(scene,axis,at,p.get('physical_axis_source'))
            _,v=g.at(target['points'],0)
            sign=1 if p['sign_end21_2']==0 else -1
            updated['direction_arrows20_18']=[arrow([x*p['sign_travel21_2'] for x in u],[x*sign for x in v])]
        return dict(mark,points=pose(axis,at,p['sign_travel21_2'],updated,scene),props=updated)
    if not target:return None
    q, u = attachment_pose(scene,axis,at,p.get('physical_axis_source'))
    if target['kind']=='APRON':
        from geometry11 import polygon
        center = polygon(target['points']).representative_point()
        dest = [center.x,center.y]
    elif target['kind']=='RUNWAY':
        dest = target['points'][p['sign_end21_2']]
    else:
        if not -.05<=p.get('sign_target_station26',station_at(p,target,True))<=g.length(target['points'])+.05:return None
        target_station=station_at(p,target,True)
        updated['sign_target_station26']=p.get('sign_target_station26',target_station)
        dest, _ = g.at(target['points'],target_station)
    travel = p['sign_travel21_2']
    heading = [x*travel for x in u]
    direction = g.unit(q,dest) if g.distance(q,dest)>.001 else heading
    arrows = [arrow(heading,direction)]
    if target['id'] in network and target['id']!=axis['id']:
        from directions20_18 import outgoing
        from pavement_geometry import crossings
        for junction in crossings(scene) if junctions is None else junctions:
            ids=junction['assets']
            if len(ids)!=2 or set(ids)!={axis['id'],target['id']}:
                continue
            if g.distance(dest,junction['point'])>2:
                continue
            source_station=junction['stations'][ids.index(axis['id'])]
            target_station=junction['stations'][ids.index(target['id'])]
            distance_to_end=min(source_station,g.length(axis['points'])-source_station)
            if distance_to_end<=1 and (source_station-at)*travel>0:
                exits=[arrow(heading,v) for v in outgoing(target,target_station)]
                exits=[a for a in exits if a in ('←','↖','↙','→','↗','↘')]
                if len(exits)==2:arrows=exits
            break
    name = custom if custom is not None else target_name(scene,target['id'],dest,network)
    props = sign_props(name,arrows,p['information_profile20_18']=='BOARD',
                       p['direction_side21_2'],axis['props']['width'],
                       piece_at(axis,at)['name'],p.get('sign_location21_2',False))
    if props is None:
        return None
    if profile_height:=p.get('sign_text_height'):
        props['text_height']=profile_height
    rows=[dict(label=name,arrows=arrows)]
    for reference in p.get('sign_extra_targets',[]):
        extra=dict(p,**reference)
        extra.pop('sign_extra_targets',None)
        extra['sign_custom_text']=reference.get('sign_custom_text')
        resolved=resolve(scene,dict(mark,props=extra),network,junctions)
        if resolved:
            face=resolved['props']
            rows.append(dict(label=face['direction_name20_18'],arrows=face['direction_arrows20_18']))
    if len(rows)>1:
        updated['sign_ground_rows']=rows
        units=sum(len(row['label'])*.6+len(row['arrows'])*.9 for row in rows)+(len(rows)-1)*.35
        props['text_height']=min(props['text_height'],(axis['props']['width']/2-1.7)/units)
        if props['text_height']<.5:return None
        props['sign_ground_span']=units*props['text_height']
    else:
        updated.pop('sign_ground_rows',None)
        updated.pop('sign_ground_span',None)
    props=dict(updated,**props)
    return dict(mark,points=pose(axis,at,travel,props,scene),props=props)


def create(scene, source, station, target, point, profile, sides, existing=None, physical=None):
    from guidance20 import attachment_pose
    location = profile=='DIRECTION_BOARD'
    profile = 'PAVEMENT' if profile=='PAVEMENT' else 'BOARD'
    network = routes(scene)
    axis = network[source]
    asset = network.get(target) or scene.assets[target]
    length = g.length(axis['points'])
    end = 0 if g.distance(point,asset['points'][0]) <= g.distance(point,asset['points'][-1]) else -1
    target_fraction = (g.project(asset['points'],point)[1]/max(.001,g.length(asset['points']))
                       if target in network else 0)
    q,u=attachment_pose(scene,axis,station,physical)
    travel = 1 if sum(u[k]*(point[k]-q[k]) for k in (0,1)) >= 0 else -1
    if axis['props'].get('flow') in ('FORWARD','REVERSE'):
        travel = 1 if axis['props']['flow']=='FORWARD' else -1
    with scene.transaction('添加目的地与方向标识'):
        for side in sides:
            props = dict(information_profile20_18=profile, direction_side21_2=side,
                         sign_axis21_2=source, sign_fraction21_2=station/length,sign_station26=station,
                         sign_target21_2=target, sign_end21_2=end,
                         sign_target_fraction21_2=target_fraction, sign_travel21_2=travel,
                         sign_location21_2=location)
            props['physical_axis_source']=list(physical) if physical else None
            if target in network:props['sign_target_station26']=target_fraction*g.length(asset['points'])
            mark = resolve(scene,dict(id='',props=props),network)
            if mark is None:
                raise ValueError('滑行道空间不足，无法放置标识')
            opts = mark['props']
            if existing:
                scene.update_asset(existing,points=mark['points'],props=opts)
                scene.assets[existing]['name']=opts['direction_name20_18']
            else:
                scene.create_marking('DIRECTION',mark['points'],name=opts['direction_name20_18'],**opts)


def append_target(scene,oid,target,point):
    network=routes(scene)
    mark=scene.assets[oid]
    asset=network.get(target) or scene.assets[target]
    end=0 if g.distance(point,asset['points'][0])<=g.distance(point,asset['points'][-1]) else -1
    station=g.project(asset['points'],point)[1] if target in network else 0
    reference=dict(sign_target21_2=target,sign_end21_2=end,sign_target_station26=station,
                   sign_target_fraction21_2=station/max(.001,g.length(asset['points'])))
    updated=dict(mark['props'])
    updated['sign_extra_targets']=[*updated.get('sign_extra_targets',[]),reference]
    if not resolve(scene,dict(mark,props=updated),network):
        raise ValueError('滑行道空间不足，无法追加分支')
    with scene.transaction('追加目的地与方向标识分支'):
        mark['props']=updated


def sync(scene):
    marks=[m for m in scene.assets.values() if m['props'].get('sign_axis21_2')]
    if not marks:return
    from pavement_geometry import crossings
    network=routes(scene)
    junctions=crossings(scene)
    for mark in marks:
        result=resolve(scene,mark,network,junctions)
        if result:
            mark['points']=result['points']
            mark['props']=result['props']
            if not result['props'].get('sign_static_face26'):
                mark['name']=result['props']['direction_name20_18']


def extra(scene, network, ground, boards):
    from automatic_markings import synthetic
    from directions20_18 import closed
    from geometry11 import LineString, Point, parts, polygon
    from junction_routes import branches
    result = {}

    def emit(owner, axis, at, travel, name, arrows, suffix, destination=False):
        for board, enabled in ((False,ground),(True,boards)):
            if not enabled:
                continue
            props = sign_props(name,arrows,board,'LEFT' if board else 'RIGHT',
                               axis['props']['width'],piece_at(axis,at)['name'],not destination)
            if props:
                tag = ('BOARD21_2:' if board else 'DIRECTION21_2:')+suffix
                mark = synthetic(owner,'DIRECTION',pose(axis,at,travel,props),tag,**props)
                result[mark['id']] = mark

    aprons = [(a,polygon(a['points'])) for a in scene.assets.values()
              if a['kind']=='APRON' and not a['props'].get('turn_pad') and not scene.is_closed(a['id'])]
    for aid, axis in network.items():
        if closed(scene,aid) or not axis['props'].get('auto_direction20_18',True):
            continue
        if not aprons:
            break
        line = LineString(axis['points'])
        for apron, area in aprons:
            p = apron['props']
            if p.get('deice_layout12') and p.get('deice_parent')==aid:
                station = p['deice_station']-p['deice_width']/2
                if 0<=station<=line.length:
                    _,tangent = g.at(axis['points'],station)
                    normal = (-tangent[1]*p['deice_side'],tangent[0]*p['deice_side'])
                    for travel in (-1,1):
                        span = station if travel>0 else line.length-station
                        if span<3 or axis['props'].get('flow')==('REVERSE' if travel>0 else 'FORWARD'):
                            continue
                        at = station-travel*min(span*.6,max(9,axis['props']['width']))
                        direction = arrow(tuple(travel*v for v in tangent),normal)
                        emit(aid,axis,at,travel,apron_name(apron),[direction],
                             f"{apron['id']}:ATTACHED:{travel}",destination=True)
                continue
            hits = parts(line.intersection(area.boundary),('Point',))
            for index, pos in enumerate(sorted(line.project(p) for p in hits)):
                for travel in (-1,1):
                    if axis['props'].get('flow') == ('REVERSE' if travel>0 else 'FORWARD'):
                        continue
                    span = pos if travel>0 else line.length-pos
                    ahead = line.length-span
                    if span < 3:
                        continue
                    point, tangent = g.at(axis['points'],pos)
                    sample = (line.interpolate(pos+travel*min(2,ahead*.8)) if ahead>.25
                              else Point(*(point[k]+2*travel*tangent[k] for k in (0,1))))
                    inside = area.contains(sample)
                    behind = area.contains(line.interpolate(pos-travel*2))
                    if inside == behind:
                        continue
                    at = pos-travel*min(span*.6,max(9,axis['props']['width']))
                    name = apron_name(apron) if inside else piece_at(axis,pos+travel*.2)['name']
                    if not inside and ahead<=.25:
                        onward = []
                        for bid,other in network.items():
                            if aid==bid or closed(scene,bid):
                                continue
                            distance,other_station,_=g.project(other['points'],point)
                            if distance>1:
                                continue
                            other_line=LineString(other['points'])
                            for step in (-3,3):
                                probe=other_station+step
                                if 0<=probe<=other_line.length and not area.covers(other_line.interpolate(probe)):
                                    onward.append((distance,bid,probe))
                        if onward:
                            _,bid,probe=min(onward)
                            name=piece_at(network[bid],probe)['name']
                    emit(aid,axis,at,travel,name,['↑'],f"{apron['id']}:{index}:{travel}",destination=inside)
    def reverse_sign(owner, target, points, width, station, direction):
        length=g.length(points)
        if length<5:return
        axis=dict(target,points=points,props=dict(target['props'],width=width))
        at=length-min(length*.55,max(8,width))
        _,u=g.at(points,at)
        _,v=g.at(target['points'],station)
        label=piece_at(target,station)['name']
        emit(owner,axis,at,1,label,[arrow(u,[x*direction for x in v])],'reverse')

    for mid,movement in scene.movements.items():
        target=network.get(movement['to']['asset'])
        if (not target or movement.get('geometry')!='RAPID' or closed(scene,mid)
                or not movement.get('guide_visible',True) or not movement.get('join_reverse_visible',True)):
            continue
        for branch in branches(scene,movement):
            reverse_sign(mid,target,branch['points'],movement['width'],branch['station'],branch['direction'])
    from marks11 import legacy_reverse_routes
    for route in legacy_reverse_routes(scene).values():
        owner,target=route['owner'],route['target']
        if target in network and not closed(scene,owner) and not closed(scene,target):
            sign=1 if route['target_to']>route['target_from'] else -1
            reverse_sign(owner,network[target],route['points'],route['props']['width'],route['target_to'],sign)
    return result
