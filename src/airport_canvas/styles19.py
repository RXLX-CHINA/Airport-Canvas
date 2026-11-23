"""Live labels, airport-wide sign sizing and editable label anchors."""
import scene_geometry as g
from marking_catalog import CATALOG

def standard_no_entry_height(scene):
    letters=[a['props'].get('code_letter') for a in scene.assets.values() if a['kind']=='RUNWAY' and a['props'].get('code_letter')]
    letters.append(scene.data['meta'].get('code_letter') or scene.scenario.get('code_letter') or (max(letters) if letters else 'C'))
    return 4. if any(x in ('C','D','E','F') for x in letters) else 2.

def no_entry_height(scene):
    standard=standard_no_entry_height(scene);meta=scene.data['meta']
    return min(standard,meta.get('no_entry_height20',standard)) if meta.get('no_entry_mode20')=='FIT' else standard

def normalize(scene,marks,reposition=False):
    height=no_entry_height(scene);groups={}
    for a in marks.values():
        p=a['props'];key=p.get('mark_type')
        if key=='NO_ENTRY':
            if 'closure_entry_width' in p:
                p.update(text='NO ENTRY',character_ratio=.4,margin=.5)
                continue
            p.update(text='NO ENTRY',text_height=p.get('sign_text_height',height),character_ratio=.4,margin=.5,auto_scaled=False)
            groups.setdefault((a.get('owner'),p.get('reverse_site31',p.get('reverse_entry13',False))),[]).append(a)
        root=scene.assets.get(a.get('owner') or p.get('label_asset'))
        if key=='RWY_CIRCLE' and root and root['kind']=='RUNWAY':
            from scene_render import runway_center_width
            p.update(width=root['props']['width']/2,line_width=runway_center_width(scene,root))
        if key=='ROAD_STOP':p['red_background']=True
        if key=='BRIDGE_COMPOSITE' and a.get('owner') in scene.assets:
            p['home_white19']=scene.assets[a['owner']]['props'].get('home_white19',False)
        owner=scene.assets.get(p.get('label_asset'))
        if key=='LOCATION' and a.get('owner') in scene.movements:
            movement=scene.movements[a['owner']];p['text']=movement.get('designation') or movement['name']
            if ':LOCATION18:' in a['id']:
                part=a['id'].split(':LOCATION18:')[1];axis=__import__('segments18').route(scene,a['owner']);p['text']=next((v['name'] for v in __import__('segments18').pieces(axis) if v['id']==part),p['text'])
        if key=='LOCATION' and a.get('owner') in scene.assets:
            owner=scene.assets[a['owner']]
            if ':LOCATION18:' in a['id']:
                part=a['id'].split(':LOCATION18:')[1]
                from segments18 import pieces
                p['text']=next((v['name'] for v in pieces(owner) if v['id']==part),p.get('text',''))
                owner=None
            else:p['text']=owner['props'].get('designation') or owner['name'];owner=None
        if owner and key=='LOCATION':
            from segments18 import piece_at
            station=p.get('attached_station',g.project(owner['points'],a['points'][0])[1])
            if owner['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE'):p['text']=piece_at(owner,station)['name']
        if key and a.get('owner'):
            text=p.get('text','');a['name']=CATALOG[key]['name']+(' · '+text if text else '')
    for owner,rows in groups.items():
        if reposition and owner[0] and len(rows)==2:
            center=[sum(a['points'][0][k] for a in rows)/2 for k in (0,1)]
            board=8*height*.4+1
            for a in rows:
                u=g.unit(a['points'][0],a['points'][-1]);v=[-u[1],u[0]]
                sign=1 if sum((a['points'][0][k]-center[k])*v[k] for k in (0,1))>=0 else -1
                q=[center[k]+sign*v[k]*(1.075+board/2) for k in (0,1)]
                a['points']=[q,[q[k]+u[k]*10 for k in (0,1)]]
    return marks

def sync(scene):
    normalize(scene,{k:a for k,a in scene.assets.items() if a['kind']=='MARKING'})
    for group in scene.data.get('groups',{}).values():
        aid=group.get('stand_root13') or group.get('stand_root')
        if aid in scene.assets:group['name']=scene.assets[aid]['name']+' · 成套机位'
    for a in scene.assets.values():
        p=a['props']
        role=p.get('building_role19')
        if role in ('TERMINAL','OTHER','BRIDGE'):
            name=p.get('terminal_number19',a['name']) if role in ('TERMINAL','OTHER') else '廊桥 '+p.get('bridge_number19','')
            if a['name']==p.get('auto_name19',name):a['name']=name
            p['auto_name19']=name

def move_label(scene,aid,point):
    from automatic_markings import generated_markings,update_generated
    mark=scene.assets.get(aid) or generated_markings(scene).get(aid)
    if not mark:raise ValueError('文字已不存在')
    delta=[point[k]-mark['points'][0][k] for k in (0,1)]
    points=[[q[k]+delta[k] for k in (0,1)] for q in mark['points']]
    if aid not in scene.assets:
        update_generated(scene,aid,mark['name'],points,mark['props']);return
    with scene.transaction('移动位置文字'):
        mark['points']=points;p=mark['props'];owner=scene.assets.get(p.get('label_asset'))
        if owner and p.get('axis_placement11'):
            from marks11 import side_pose
            _,station,_=g.project(owner['points'],point);base,u=side_pose(scene,owner,station,p.get('axis_side','CENTER'))
            p['attached_station']=station;p['axis_offset19']=[point[k]-base[k] for k in (0,1)]

def checks(scene):
    from automatic_markings import generated_markings
    from geometry11 import LineString,Polygon,unary_union
    from marking_catalog import primitives
    surfaces=[LineString(a['points']).buffer(a['props']['width']/2,cap_style=2) for a in scene.assets.values() if a['kind'] in ('RUNWAY','TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')]
    surfaces += [Polygon(a['points']) for a in scene.assets.values() if a['kind']=='APRON']
    pavement=unary_union(surfaces);out=[]
    for a in list(generated_markings(scene).values())+list(scene.assets.values()):
        if a['props'].get('mark_type')!='NO_ENTRY':continue
        boards=[Polygon(i['points']) for i in primitives(a) if i['type']=='polygon' and i.get('fill')=='#cf383e']
        if any(board.difference(pavement).area>.01 for board in boards):out.append(dict(object_id=a['id'],status='REVIEW_REQUIRED',rule='NO_ENTRY_FOOTPRINT19',message='统一尺寸的 NO ENTRY 超出已知道面，请调整位置或道面；未自动缩小字高。',source='MH5001—2021 6.2.12',actual=no_entry_height(scene),required='符合指标字高，背景边距≥0.5m，并核对实际道面'))
    return out
