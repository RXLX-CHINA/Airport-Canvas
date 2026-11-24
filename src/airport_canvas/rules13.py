"""Explicit project choices, closure dependencies and stable runway entry leads."""
import copy,math
import scene_geometry as g

def refine(scene,result):
    from automatic_markings import synthetic
    from marks11 import legacy_reverse_routes
    for mark in result.values():
        p=mark['props'];owner=mark.get('owner');root=scene.assets.get(owner);m=scene.movements.get(owner)
        if p['mark_type']=='HOLD_A':
            taxi=root
            if m:taxi=next((scene.assets[m[k]['asset']] for k in ('from','to') if scene.assets[m[k]['asset']]['kind']!='RUNWAY'),None)
            if taxi:p['width']=taxi['props']['width']+2*taxi['props'].get('shoulder',0) if taxi['props'].get('hold_include_shoulders13',True) else taxi['props']['width']
        if p['mark_type']=='RWY_CIRCLE':
            runway=root or scene.assets.get(p.get('label_asset'))
            if runway and runway['kind']=='RUNWAY':
                from scene_render import runway_center_width
                p.update(width=runway['props']['width']/2,line_width=runway_center_width(scene,runway))
        if root and root['kind']=='STAND':p['stand_part13']=True
    # No entry applies to BOTH receiving-side approaches of an exit-only route.
    reverse=[dict(route,site=oid) for oid,route in legacy_reverse_routes(scene).items()]
    from junction_routes import branches
    for mid,movement in scene.movements.items():
        if movement.get('legacy_attachment') or movement.get('role')!='RAPID_EXIT' or not movement.get('join_reverse_visible',True) or not movement.get('auto_signs',True):continue
        for branch in branches(scene,movement):
            if branch.get('side')=='to':reverse.append(dict(owner=mid,site=branch['oid'],points=branch['points'],props=dict(width=movement['width'])))
    for a in reverse:
        path=a['points'];L=g.length(path)
        q,u=g.at(path,max(0,L-18));u=[-x for x in u]
        trunk=a.get('source_path')
        owner=a['owner']
        if trunk and a.get('start_station',0)>5:
            # Both receiving-side branches feed the same restricted trunk.
            # Paint on its common cross-section, clear of the diverging guides.
            station=a['start_station']
            port=next((m['to'] for m in scene.movements.values() if m.get('legacy_attachment')
                       and m['to']['asset']==owner and scene.assets[m['from']['asset']]['kind']=='RUNWAY'),None)
            owner_path=scene.assets[owner]['points']
            runway_at_start=not port or port['station']<=g.length(owner_path)/2
            runway_first=runway_at_start if trunk==owner_path else True
            q,u=g.at(trunk,station-5 if runway_first else station+5)
            if runway_first:u=[-x for x in u]
            for oid,mark in list(result.items()):
                movement=scene.movements.get(mark.get('owner'),{})
                if (mark['props']['mark_type']=='NO_ENTRY' and movement.get('legacy_attachment')
                        and any(movement[k]['asset']==owner for k in ('from','to'))):
                    result.pop(oid)
        v=[-u[1],u[0]];width=a['props']['width'];height=min(2,max(.6,(width-3)/9));board=8*height*.4+1
        for side in (-1,1):
            offset=side*(board/2+1.075);anchor=[q[k]+v[k]*offset for k in (0,1)];m=synthetic(a['owner'],'NO_ENTRY',[anchor,[anchor[k]+u[k]*10 for k in (0,1)]],'REVERSE_NO_ENTRY:'+str(side),text='NO ENTRY',text_height=height,character_ratio=.4,margin=.5,reverse_entry13=True,reverse_site31=a['site'],reverse_width31=width);result[m['id']]=m
    remove=[]
    for oid,mark in result.items():
        if mark['props']['mark_type'] not in ('TWY_CENTER','TWY_ENHANCED','LEAD_IN','LEAD_OUT','AUX_LEAD','ICAO_AUX_LEAD','ALIGNMENT','TURN_PAD_GUIDE'):continue
        owner=mark.get('owner');m=scene.movements.get(owner);a=scene.assets.get(owner)
        if a and a['props'].get('closed') or m and any(scene.assets[m[k]['asset']]['props'].get('closed') for k in ('from','to')):remove.append(oid)
    for oid in remove:result.pop(oid,None)
    return result

def runway_extension(scene,points,runway,index=0,preserve_exterior=False,direction_hint=None,rapid=False):
    from connection9 import runway_extension as previous
    reverse=index==-1
    path=list(reversed(points)) if reverse else points
    expected=direction_hint
    if expected not in (-1,1):
        axis=g.unit(*runway['points'])
        origin=path[0]
        probe,_=g.at(path,min(45,g.length(path)*.3))
        expected=1 if sum((probe[k]-origin[k])*axis[k] for k in (0,1))>=0 else -1
    result=previous(scene,path,runway,0,direction_hint=expected,preserve_exterior=preserve_exterior,
                    keep_direction=rapid)
    return list(reversed(result)) if reverse else result

def asset_guide(scene,a):
    points=a['points']
    manual=a['props'].get('rapid_drawn_axis56',False)
    for m in scene.movements.values():
        if not m.get('legacy_attachment'):continue
        own=next((m[k] for k in ('from','to') if m[k]['asset']==a['id']),None)
        other=next((m[k] for k in ('from','to') if scene.assets[m[k]['asset']]['kind']=='RUNWAY'),None)
        if own and other:
            points=runway_extension(scene,points,scene.assets[other['asset']],0 if own['station']<g.length(a['points'])/2 else -1,
                                    preserve_exterior=True,rapid=manual or bool(a['props'].get('rapid_exit')))
    return points

def closure_items(scene,items,generated):
    from geometry11 import polygon,LineString,Point,lines,unary_union
    from marking_catalog import YELLOW
    items=[item for item in items if not scene.assets.get(item.get('oid'),{}).get('props',{}).get('terminal_hidden13')]
    from marking_standards import closure_routes
    assets,closed_ids = closure_routes(scene)
    closed=[a for aid,a in assets.items() if aid in closed_ids
            and a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','APRON','ROAD')]
    if not closed:return items
    mask=unary_union([polygon(g.rectangle(a['points'],a['props']['width'])) if a['kind']=='RUNWAY' else polygon(a['points']) if a['kind']=='APRON' else LineString(a['points']).buffer(a['props']['width']/2,cap_style=2) for a in closed]);out=[]
    for item in items:
        mark=generated.get(item.get('oid')) or scene.assets.get(item.get('oid'));owner=mark.get('owner',item.get('oid')) if mark else item.get('oid');m=scene.movements.get(owner)
        guide=item.get('stroke')==YELLOW and item['type']=='line' and (not mark or mark['kind']!='MARKING' or mark['props']['mark_type'] in ('TWY_CENTER','TWY_ENHANCED','LEAD_IN','LEAD_OUT','AUX_LEAD','ICAO_AUX_LEAD','ALIGNMENT','TURN_PAD_GUIDE'))
        if not guide:out.append(item);continue
        if owner in closed_ids or m and any(m[k]['asset'] in closed_ids for k in ('from','to')):continue
        line=LineString(item['points'])
        for part in lines(line.difference(mask)):
            pts=[list(q) for q in part.coords];out.append(dict(item,points=pts,dash_offset=item.get('dash_offset',0)+line.project(Point(pts[0]))))
    return out

def trim_guide_backings(scene,items,generated):
    from geometry11 import polygon,LineString,lines,polygons,unary_union
    from marking_standards import closure_routes
    assets,closed_ids = closure_routes(scene)
    closed=[a for aid,a in assets.items() if aid in closed_ids
            and a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE','APRON','ROAD')]
    if not closed:return items
    mask=unary_union([polygon(g.rectangle(a['points'],a['props']['width'])) if a['kind']=='RUNWAY' else polygon(a['points']) if a['kind']=='APRON' else LineString(a['points']).buffer(a['props']['width']/2,cap_style=2) for a in closed]);out=[]
    for item in items:
        a=generated.get(item.get('oid')) or scene.assets.get(item.get('oid'));key=a.get('props',{}).get('mark_type') if a else None
        guide=key in ('TWY_ENHANCED','TWY_CENTER','LEAD_IN','LEAD_OUT','ALIGNMENT','TURN_PAD_GUIDE') or item.get('oid') in scene.movements or a and a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
        if not item.get('black_underlay') or not guide:out.append(item);continue
        if item['type']=='polygon':
            for p in polygons(polygon(item['points']).difference(mask)):out.append(dict(item,points=[list(q) for q in p.exterior.coords][:-1]))
        elif item['type']=='line':
            for p in lines(LineString(item['points']).difference(mask)):out.append(dict(item,points=[list(q) for q in p.coords]))
        else:out.append(item)
    return out

def set_terminal(scene,aid,station,keep='START',enabled=True,jid=None):
    from curve_model import node
    a=scene.assets[aid]
    with scene.transaction('设置滑行道路口为末端'):
        if not enabled:
            backup=a['props'].pop('terminal_backup13',None)
            if backup:
                for key in ('points','curve_nodes','design_vertices'):
                    if backup.get(key) is None:a.pop(key,None)
                    else:a[key]=backup[key]
                for mid,m in backup['movements'].items():scene.movements[mid]=m
                for markid,mark in backup.get('marks',{}).items():scene.assets[markid]=mark
            a['props'].pop('terminal_station13',None);return
        if not .1<station<g.length(a['points'])-.1:raise ValueError('请在滑行道内部选择终止路口')
        a['props'].setdefault('terminal_backup13',dict(points=copy.deepcopy(a['points']),curve_nodes=copy.deepcopy(a.get('curve_nodes')),design_vertices=copy.deepcopy(a.get('design_vertices')),movements={mid:copy.deepcopy(m) for mid,m in scene.movements.items() if any(m[k]['asset']==aid for k in ('from','to'))},marks={mid:copy.deepcopy(mark) for mid,mark in scene.assets.items() if mark['kind']=='MARKING' and mark['props'].get('label_asset')==aid}))
        total=g.length(a['points']);lo,hi=(0,station) if keep=='START' else (station,total);a['points']=g.subpath(a['points'],lo,hi);a.pop('design_vertices',None);a.pop('curve_nodes',None);a['props'].update(terminal_station13=station,terminal_keep13=keep,terminal_junction13=jid)
        for mid,m in list(scene.movements.items()):
            port=next((m[k] for k in ('from','to') if m[k]['asset']==aid),None)
            if not port:continue
            if not lo-1e-6<=port['station']<=hi+1e-6:scene.movements.pop(mid)
            else:port['station']-=lo
        for mark in scene.assets.values():
            p=mark['props']
            if mark['kind']!='MARKING' or p.get('label_asset')!=aid:continue
            if p.get('axis_path11'):
                x=max(lo,p['path_station_a']);y=min(hi,p['path_station_b']);p['terminal_hidden13']=y<=x
                if y>x:p.update(path_station_a=x-lo,path_station_b=y-lo)
            elif 'attached_station' in p:
                p['terminal_hidden13']=not lo<=p['attached_station']<=hi;p['attached_station']=max(0,min(hi-lo,p['attached_station']-lo))
        __import__('marks11').refresh_axis(scene,aid)

def checks(scene):
    out=[]
    for aid,a in scene.assets.items():
        if a['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE') and a['props'].get('shoulder',0)>0 and not a['props'].get('hold_include_shoulders13',True):out.append(dict(object_id=aid,rule='HOLD_SPAN_PROJECT_CHOICE',status='REVIEW_REQUIRED',message='项目选择A型等待标志仅覆盖道面；第四修订案要求道面加道肩全宽，可在属性启用含道肩',source='MH5001—2021第四修订案6.2.10',actual=a['props']['width'],required='pavement + shoulders'))
    return out

def sync_marks(scene):
    from scene_render import runway_center_width
    for mark in scene.assets.values():
        p=mark['props']
        if mark['kind']!='MARKING':continue
        runway=scene.assets.get(p.get('label_asset'))
        if p.get('mark_type')=='RWY_CIRCLE' and runway and runway['kind']=='RUNWAY':p.update(width=runway['props']['width']/2,line_width=runway_center_width(scene,runway))
        if (p.get('mark_type')=='HOLD_A' and not p.get('hold_width_manual') and runway
                and runway['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
                and not runway['props'].get('hold_include_shoulders13',True)):
            p['width']=min(p['width'],runway['props']['width'])
