"""Shared editor geometry, apron appearance, gate clearances and sign sizing."""
import math,copy
import scene_geometry as g
from geometry11 import Point,LineString,Polygon,polygon,polygons,unary_union
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')

def axis(scene,aid):
    a=scene.assets.get(aid)
    if a and a['kind'] in TAXIS+('RUNWAY',):return a
    m=getattr(scene,'movements',{}).get(aid)
    if m and not m.get('legacy_attachment') and m.get('pavement_visible',True) and m.get('role') not in ('PUSHBACK','STAND_ENTRY'):
        return dict(id=aid,kind=m.get('taxiway_kind39','APRON_TAXIWAY' if m.get('role')=='APRON_ACCESS' else 'TAXIWAY'),name=m.get('designation') or m['name'],points=scene.movement_path(aid),props=m)

def axes(scene):
    return {aid:a for aid in list(scene.assets)+list(scene.movements) if (a:=axis(scene,aid))}

def snap(scene,q,tolerance=3.,parent=None):
    from guidance20 import snap_axis
    return snap_axis(scene,q,{aid:a for aid,a in axes(scene).items() if parent is None or aid==parent},tolerance)


def entry_point(scene,a):
    parent=axis(scene,a['props'].get('entry_asset'))
    return g.at(parent['points'],max(0,min(g.length(parent['points']),a['props'].get('entry_station',g.project(parent['points'],a['points'][0])[1]))))[0] if parent else None

def slide_entry(scene,aid,q,parent_id=None):
    a=scene.assets[aid];p=a['props'];parent=axis(scene,parent_id or p.get('entry_asset'))
    if not parent:raise ValueError('先将机位绑定到一条滑行道中线')
    _,station,target=g.project(parent['points'],q)
    if g.distance(target,a['points'][-1])<15:raise ValueError('入口连接点距停止端应至少15m')
    with scene.transaction('沿中线移动机位入口连接点'):
        a['points'][0]=target;p.update(entry_asset=parent['id'],entry_station=station,entry_attached=True)
        p['entry_bindings15']={key:True for key in ('ENTRY:0','ENTRY:1','ENTRY:-1')}
    return target

def sync(scene):
    used={m.get('designation') for m in scene.movements.values() if m.get('designation')}
    for mid,m in scene.movements.items():
        if not axis(scene,mid):continue
        if not m.get('designation'):
            name=m.get('name','')
            if name in ('TAXIWAY_JOIN','APRON_ACCESS','ENTRY','EXIT','EXIT_ONLY','RAPID_EXIT',''):
                n=1
                while 'C'+str(n).zfill(2) in used:n+=1
                name='C'+str(n).zfill(2);m['name']=name
            m['designation']=name;used.add(name)
        elif m.get('name')!=m.get('last_name20',m['name']):m['designation']=m['name']
        elif m.get('designation')!=m.get('last_designation20',m['designation']):m['name']=m['designation']
        m['last_name20']=m['name'];m['last_designation20']=m['designation'];m.setdefault('inherit_apron_color20',True)
    for a in scene.assets.values():
        p=a['props']
        if a['kind'] in TAXIS:p.setdefault('inherit_apron_color20',True)
        if a['kind']=='STAND' and p.get('entry_attached',False):
            target=entry_point(scene,a)
            if target:a['points'][0]=target

def locations(scene,result):
    from automatic_markings import synthetic
    for mid,m in scene.movements.items():
        a=axis(scene,mid)
        if not a or not m.get('auto_signs',True):continue
        q,u=g.at(a['points'],g.length(a['points'])/2);v=[-u[1],u[0]];q=[q[k]-v[k]*m['width']/4 for k in (0,1)]
        mark=synthetic(mid,'LOCATION',[q,[q[k]+u[k]*10 for k in (0,1)]],'LOCATION20',text=m.get('designation') or m['name'],text_height=4)
        result[mark['id']]=mark
    return result

def apron_colors(scene,items):
    aprons=[(polygon(a['points']),a['props'].get('pavement_color','#9199a1')) for a in scene.assets.values() if a['kind']=='APRON' and not a['props'].get('turn_pad')]
    if not aprons:return items
    routes=axes(scene);out=[]
    for item in items:
        oid=item.get('oid','');a=routes.get(oid)
        if not a and oid.startswith('J:'):
            parents=[routes[k] for k in oid.split(':')[1:3] if k in routes]
            if parents:a=dict(kind='TAXIWAY',props=dict(inherit_apron_color20=all(x['props'].get('inherit_apron_color20',True) for x in parents)))
        if not a and ':' in oid:a=routes.get(oid.split(':')[0])
        if not a or a['kind'] in ('RUNWAY','ROAD') or item.get('road_priority20_5') or not a['props'].get('inherit_apron_color20',True) or item['type']!='polygon' or not item.get('fill') or item.get('black_underlay') or item.get('fill') not in ('#737b83',a['props'].get('pavement_color')):
            out.append(item);continue
        remaining=polygon(item['points'])
        for area,color in aprons:
            if not remaining.intersects(area):continue
            inside=remaining.intersection(area)
            for part in polygons(inside):out.append(dict(item,points=[list(q) for q in part.exterior.coords][:-1],fill=color,apron_color20=True))
            remaining=remaining.difference(area)
        for part in polygons(remaining):out.append(dict(item,points=[list(q) for q in part.exterior.coords][:-1]))
    return out

def bridge_clearances(scene):
    import terminal19 as t
    bridges=[a for a in t.buildings(scene) if a['props']['building_role19']=='BRIDGE'];out=[]
    for i,a in enumerate(bridges):
        ua=t.bridge_direction(a);va=[-ua[1],ua[0]];q=t.bridge_tip(a);span=a['props'].get('gate_span20',scene.scenario.get('aircraft_wingspan',36));length=a['props'].get('gate_length20',scene.scenario.get('aircraft_length',40));clear=a['props'].get('gate_clearance20',4.5)
        for b in bridges[i+1:]:
            ub=t.bridge_direction(b)
            if sum(ua[k]*ub[k] for k in (0,1))<.9:continue
            z=t.bridge_tip(b);delta=[z[k]-q[k] for k in (0,1)];across=abs(sum(delta[k]*va[k] for k in (0,1)));depth=abs(sum(delta[k]*ua[k] for k in (0,1)));required=(span+b['props'].get('gate_span20',scene.scenario.get('aircraft_wingspan',36)))/2+max(clear,b['props'].get('gate_clearance20',4.5))
            if depth<length and across<required:
                out.append(dict(object_id=a['id'],rule='GATE_SPACING20',status='REVIEW_REQUIRED',message=f'廊桥 {a["props"].get("bridge_number19","")} 与 {b["props"].get("bridge_number19","")} 同侧间距 {across:.1f}m，按当前机型至少需 {required:.1f}m；可能放不下机位。',source='按项目翼展与净距作二维预检查，需机位设计复核',actual=round(across,3),required=round(required,3)))
    return out

def no_entry_limits(scene):
    from automatic_markings import generated_markings
    marks=[a for a in list(generated_markings(scene).values())+list(scene.assets.values()) if a['props'].get('mark_type')=='NO_ENTRY'];group={};routes=axes(scene)
    for a in marks:group.setdefault((a.get('owner'),a['props'].get('reverse_site31',a['props'].get('reverse_entry13',False))),[]).append(a)
    from scene_render import surface_geometry
    from marking_catalog import primitives, TAXI_MARKING_EDGE_CLEARANCE
    surfaces=surface_geometry(scene);pavement=unary_union([polygon(x['points']) for x in surfaces['pavement']]).buffer(-TAXI_MARKING_EDGE_CLEARANCE)
    rows=[]
    for a in marks:
        p=a['props'];aid=a.get('owner') or p.get('label_asset');base=routes.get(aid)
        if not base:
            hit=snap(scene,a['points'][0],100)
            if hit:base=routes[hit[1]];aid=hit[1]
        if not base:continue
        width=base['props']['width'];paired=bool(a.get('owner') and len(group[(a.get('owner'),p.get('reverse_site31',p.get('reverse_entry13',False)))])==2)
        if paired:maximum=(width/2-TAXI_MARKING_EDGE_CLEARANCE-1.075-1)/(8*.4)
        else:
            d,_,_=g.project(base['points'],a['points'][0]);maximum=(width-2*TAXI_MARKING_EDGE_CLEARANCE-2*d-1)/(8*.4)
        maximum=max(0,maximum)
        def fits(height):
            probe=copy.deepcopy(a);probe['props'].update(text_height=height,character_ratio=.4,margin=.5)
            if paired:
                pair=group[(a.get('owner'),p.get('reverse_site31',p.get('reverse_entry13',False)))];center=[sum(v['points'][0][k] for v in pair)/2 for k in (0,1)];u=g.unit(*[a['points'][i] for i in (0,-1)]);v=[-u[1],u[0]];sign=1 if sum((a['points'][0][k]-center[k])*v[k] for k in (0,1))>=0 else -1;board=8*.4*height+1;q=[center[k]+sign*v[k]*(board/2+1.075) for k in (0,1)];probe['points']=[q,[q[k]+u[k]*10 for k in (0,1)]]
            boards=[polygon(x['points']) for x in primitives(probe) if x['type']=='polygon' and x.get('fill')=='#cf383e']
            return bool(boards) and all(pavement.covers(board) for board in boards)
        if not fits(maximum):
            lo,hi=0.,maximum
            for _ in range(24):
                middle=(lo+hi)/2
                if fits(middle):lo=middle
                else:hi=middle
            maximum=lo
        rows.append(dict(id=a['id'],owner=aid,name=base['name'],width=width,maximum=maximum))
    return rows

def uniform_no_entry(scene,mode='STANDARD'):
    import styles19
    rows=no_entry_limits(scene);standard=styles19.standard_no_entry_height(scene);maximum=min(r['maximum'] for r in rows) if rows else standard;height=min(standard,maximum) if mode=='FIT' else standard
    height=math.floor(height*10000)/10000
    if height<.05:raise ValueError('有标志的现位置连最小尺寸也容纳不下，请先移动标志')
    with scene.transaction('统一全机场 NO ENTRY 尺寸'):
        scene.data['meta'].update(no_entry_mode20=mode,no_entry_height20=round(height,4),no_entry_limit20=round(maximum,4),no_entry_limiting20=[r for r in rows if abs(r['maximum']-maximum)<.001])
    return dict(height=height,standard=standard,maximum=maximum,count=len(rows),limiting=scene.data['meta']['no_entry_limiting20'])

def checks(scene):
    rows=bridge_clearances(scene);meta=scene.data['meta']
    for a in scene.assets.values():
        if a['props'].get('enhanced_orphan20'):rows.append(dict(object_id=a['id'],rule='ENHANCED_SOURCE20',status='REVIEW_REQUIRED',message='原增强中线连接已消失，已隐藏旧线；请重新选择可见中线。',source='几何依赖检查',actual=a['props'].get('enhanced_source20'),required='有效的可见中线连接'))
    if meta.get('no_entry_mode20')=='FIT':
        from styles19 import standard_no_entry_height
        if meta.get('no_entry_height20',4)<standard_no_entry_height(scene)-.001:rows.append(dict(object_id=None,rule='NO_ENTRY_FIT20',status='REVIEW_REQUIRED',message='NO ENTRY 按最窄处统一后字高低于指标要求；请核对标志位置与道面，不能直接视为规范通过。',source='MH5001—2021 6.2.12',actual=meta['no_entry_height20'],required=standard_no_entry_height(scene)))
    return rows

def validate(scene):
    for aid,a in axes(scene).items():
        if aid in scene.movements:__import__('segments18').validate_asset(a)
    for a in list(scene.assets.values())+list(scene.movements.values()):
        p=a.get('props',a)
        for key in ('gate_span20','gate_length20','enhanced_length19'):
            if key in p and (not isinstance(p[key],(int,float)) or not math.isfinite(p[key]) or p[key]<=0):raise ValueError(key+' 必须是大于0的有限数')
        if 'gate_clearance20' in p and (not isinstance(p['gate_clearance20'],(int,float)) or not math.isfinite(p['gate_clearance20']) or p['gate_clearance20']<0):raise ValueError('相邻机位净距必须是非负有限数')
        for key in ('inherit_apron_color20','intersection_relocate20'):
            if key in p and type(p[key]) is not bool:raise ValueError(key+' 必须是开关值')
        if p.get('enhanced_anchor19') and p.get('enhanced_direction19') not in ('START','END'):raise ValueError('增强中线方向只能为 START 或 END')
