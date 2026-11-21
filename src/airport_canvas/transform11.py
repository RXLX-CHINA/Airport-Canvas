"""Whole-object affine edits committed once; drag previews never mutate scenes."""
import copy
import math
import scene_geometry as g
from scene_hierarchy import descendants

def owner(scene,oid,generated=None):
    generated=generated or {}
    a=generated.get(oid)
    if a and a.get('owner') in scene.assets and scene.assets[a['owner']]['kind']=='STAND':return a['owner']
    m=scene.movements.get(oid)
    if m and m.get('legacy_attachment'):return m['to']['asset']
    return oid

def members(scene,oids):
    ids=set(oids)
    for oid in oids:ids.update(descendants(scene,oid))
    again=True
    while again:
        # Entry binding is a geometric constraint, not ownership. Selecting,
        # framing or editing a taxiway must not swallow its attached stands.
        extra={aid for aid,a in scene.assets.items() if a['props'].get('road_id') in ids or a['props'].get('label_asset') in ids or a['props'].get('stand_id') in ids}
        extra.update(aid for aid,a in scene.assets.items() if a['props'].get('deice_parent') in ids)
        extra.update(mid for mid,m in scene.movements.items() if all(m[side]['asset'] in ids for side in ('from','to')))
        again=not extra<=ids;ids.update(extra)
    return ids

def point(q,center,angle,delta):
    c,s=math.cos(angle),math.sin(angle);x,y=q[0]-center[0],q[1]-center[1]
    return [center[0]+c*x-s*y+delta[0],center[1]+s*x+c*y+delta[1]]

def generated_signs_only(scene,oids,displayed):
    return bool(oids) and all(
        oid.startswith('AUTO:')
        and displayed.get(oid,{}).get('props',{}).get('information_profile20_18') in ('BOARD','PAVEMENT')
        and not scene.data['generated_overrides'].get(oid,{}).get('editable_nodes')
        for oid in oids
    )


def move_generated_signs(scene,oids,displayed,center,angle,delta,visual=()):
    offsets = {item['oid']:item['board_layout_delta'] for item in visual
               if item.get('board_layout_delta')
               and not displayed.get(item['oid'],{}).get('sign_preview_pose')}
    changes = {}
    for oid in oids:
        if oid not in displayed:
            continue
        old = scene.data['generated_overrides'].get(oid,{})
        origin = displayed[oid]['points'][0]
        offset = offsets.get(oid,(0,0))
        target = point([origin[i]+offset[i] for i in (0,1)],center,angle,delta)
        changes[oid] = dict(dx=old.get('dx',0)+target[0]-origin[0],
                            dy=old.get('dy',0)+target[1]-origin[1],
                            rotation=old.get('rotation',0)+math.degrees(angle))
    scene.move_generated_signs(changes)
    for oid in changes:
        mark = displayed[oid]
        offset = offsets.get(oid,(0,0))
        displayed[oid] = dict(mark,sign_preview_pose=True,points=[point([q[i]+offset[i] for i in (0,1)],center,angle,delta)
                                          for q in mark['points']])


def apply(scene,oids,center=(0,0),angle=0.,delta=(0,0)):
    ids=members(scene,oids);transform=lambda q:point(q,center,angle,delta)
    displayed = None
    if ids and all(oid.startswith('AUTO:') for oid in ids):
        from automatic_markings import generated_markings
        displayed = generated_markings(scene)
        if generated_signs_only(scene,ids,displayed):
            move_generated_signs(scene,ids,displayed,center,angle,delta)
            return ids
    with scene.transaction('移动或旋转整套对象'):
        if angle:
            for oid,data in scene.data['generated_overrides'].items():
                owner=oid.split(':')[1] if oid.startswith('AUTO:') else None
                if owner in ids and oid not in ids:
                    data['dx'],data['dy']=point([data.get('dx',0),data.get('dy',0)],(0,0),angle,(0,0))
        generated_ids=[oid for oid in ids if oid.startswith('AUTO:')]
        if generated_ids:
            from automatic_markings import generated_markings,update_generated
            displayed=displayed if displayed is not None else generated_markings(scene)
            for oid in generated_ids:
                if oid not in displayed:continue
                a=displayed[oid];old=copy.deepcopy(scene.data['generated_overrides'].get(oid,{}));points=[transform(q) for q in a['points']]
                if old.get('editable_nodes'):
                    original=generated_markings(scene,False)[oid];o=original['points'][0];u=g.unit(o,original['points'][-1]);v=[-u[1],u[0]];length=g.distance(o,original['points'][-1]);nodes=copy.deepcopy(old['editable_nodes']);rotation=math.radians(old.get('rotation',0));scale=old.get('scale',1)
                    first=nodes[0]['p'];pivot=[o[k]+u[k]*first[0]*length+v[k]*first[1] for k in (0,1)]
                    for node in nodes:
                        for field in ('p','incoming','outgoing'):
                            x,y=node[field];world=[o[k]+u[k]*x*length+v[k]*y for k in (0,1)];world=point(world,pivot,rotation,[old.get('dx',0),old.get('dy',0)])
                            if scale!=1:world=[pivot[k]+(world[k]-pivot[k]-old.get('dx' if k==0 else 'dy',0))*scale+old.get('dx' if k==0 else 'dy',0) for k in (0,1)]
                            world=transform(world);d=[world[k]-o[k] for k in (0,1)];node[field]=[sum(d[k]*u[k] for k in (0,1))/max(.01,length),sum(d[k]*v[k] for k in (0,1))]
                    scene.data['generated_overrides'][oid]=dict(old,editable_nodes=nodes,dx=0,dy=0,rotation=0,scale=1)
                else:update_generated(scene,oid,a['name'],points,a['props'])
        for aid in ids:
            if aid not in scene.assets:continue
            a=scene.assets[aid];original15=copy.deepcopy(a)
            for key in ('points','design_vertices','pad_guide'):
                if a.get(key):a[key]=[transform(q) for q in a[key]]
            for node in a.get('curve_nodes',[]):
                for key in ('p','incoming','outgoing'):node[key]=transform(node[key])
            # Whole-kit movement remains exact. If the entrance leaves its old
            # taxiway, keep the kit together and explicitly detach that entrance.
            parent=a['props'].get('entry_asset')
            if a['kind']=='STAND' and parent in scene.assets and parent not in ids:
                distance,station,q=g.project(scene.assets[parent]['points'],a['points'][0])
                a['props']['entry_station']=station;a['props']['entry_attached']=distance<.05
            __import__('stand15').maintain_binding(scene,a,original15,ids)
            p=a['props']
            if p.get('crossing_full13') and p.get('crossing_asset13') in scene.assets:
                parent=scene.assets[p['crossing_asset13']];_,station,_=g.project(parent['points'],a['points'][0]);_,axis=g.at(parent['points'],station);direction=g.unit(a['points'][0],a['points'][-1]);p['crossing_station13']=station
            if p.get('deice_layout12') and p.get('deice_parent') not in ids:
                parent=scene.assets[p['deice_parent']];center=[(a['points'][0][k]+a['points'][1][k])/2 for k in (0,1)];_,station,_=g.project(parent['points'],center);p['deice_station']=station
            if a['kind']=='MARKING' and p.get('label_asset') in scene.assets and p['label_asset'] not in ids and p.get('attached_mark'):
                parent=scene.assets[p['label_asset']];distance,station,q=g.project(parent['points'],a['points'][0]);p['attached_station']=station
                from marks11 import side_pose
                target,_=side_pose(scene,parent,station,p.get('axis_side','CENTER'))
                if g.distance(target,a['points'][0])>.1:p['attached_mark']=False;p['axis_placement11']=False
            if a['kind']=='MARKING' and p.get('road_id') in scene.assets and p['road_id'] not in ids:
                parent=scene.assets[p['road_id']];_,station,_=g.project(parent['points'],a['points'][0]);p['road_station']=station
                from roads10 import lane_pose
                target,_=lane_pose(scene,parent,station,p['lane_side']);p['road_attached']=g.distance(target,a['points'][0])<.1
        for mid,m in scene.movements.items():
            both=all(m[side]['asset'] in ids for side in ('from','to'))
            if both:
                if m.get('bezier_controls'):m['bezier_controls']=[transform(q) for q in m['bezier_controls']]
                for controls in m.get('branch_controls',{}).values():
                    for i,q in enumerate(controls):controls[i]=transform(q)
            elif mid in ids:
                path=scene.movement_path(mid);ends=[transform(path[0]),transform(path[-1])]
                from editor7_model import main_controls
                controls=[transform(q) for q in main_controls(scene,m)]
                for i,side in enumerate(('from','to')):m[side]['station']=g.project(scene.assets[m[side]['asset']]['points'],ends[i])[1]
                m.update(bezier_controls=controls,geometry='BEZIER',follow_existing=False)
            else:
                for i,side in enumerate(('from','to')):
                    if m[side]['asset'] in ids and m.get('bezier_controls'):m['bezier_controls'][i]=transform(m['bezier_controls'][i])
        for aid in ids:
            if aid not in scene.assets:continue
            a=scene.assets[aid]
            if a['kind']=='ROAD':
                from roads11 import refresh_attachments
                refresh_attachments(scene,aid)
            from editor7_model import refresh_attached_marks
            refresh_attached_marks(scene,aid)
            from marks11 import refresh_axis
            refresh_axis(scene,aid)
        __import__('deice12').refresh(scene)
    return ids

def item_owner(item,generated):
    oid=item.get('oid','')
    if oid in generated:return generated[oid].get('owner',oid)
    if oid.startswith('AUTO:'):return oid.split(':')[1]
    return oid

def visual_items(scene,oids,items,generated):
    ids=members(scene,oids)
    return [item for item in items if item_owner(item,generated) in ids or item.get('oid') in ids]

def bounds(items):
    points=[]
    for item in items:
        if item['type']=='text':
            from paint10 import plate
            points.extend(plate(item)['points'])
        else:points.extend(item['points'])
    if not points:return None
    return (min(q[0] for q in points),min(q[1] for q in points),max(q[0] for q in points),max(q[1] for q in points))
