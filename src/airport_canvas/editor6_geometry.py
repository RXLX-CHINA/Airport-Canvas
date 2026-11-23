"""Shared authoring helpers for waiting marks, shoulder stripes and stop lists."""
import math
import uuid
import scene_geometry as g

def stop_rows(asset):
    p=asset['props']
    return p.get('stops') if 'stops' in p else [dict(id='default',name='1',aircraft=p.get('aircraft_codes','C172' if p.get('ga_stand') else 'A320'),offset=0.,lateral=0.,rotation=0.,shape='T' if p.get('guidance')=='GUIDED' else 'UNGUIDED',length=p.get('stop_length',6 if p.get('guidance')=='UNGUIDED' else 2),width=p.get('stop_width',.15),visible=True)]

def add_stop(scene,aid):
    import copy
    with scene.transaction('增加机位停止线'):
        a=scene.assets[aid];rows=copy.deepcopy(stop_rows(a));row=dict(rows[-1] if rows else {},id=uuid.uuid4().hex[:8],name=str(len(rows)+1),offset=-3.*len(rows),aircraft='B737',shape='T',length=2.,width=.15,visible=True)
        rows.append(row);a['props']['stops']=rows
    return row['id']

def stop_components(a):
    from automatic_markings import synthetic
    p=a['props'];q=a['points'][-1];_,u,v=__import__('stand11').frame(a);out={}
    for row in stop_rows(a):
        if not row.get('visible',True):continue
        angle=math.radians(row.get('rotation',0));t=[u[k]*math.cos(angle)+v[k]*math.sin(angle) for k in (0,1)]
        point=[q[k]+u[k]*row.get('offset',0)+v[k]*row.get('lateral',0) for k in (0,1)]
        shape=row.get('shape','T');key='UNGUIDED_STOP' if shape=='UNGUIDED' else 'STAND_STOP'
        suffix=key if row['id']=='default' else 'STOP:'+row['id']
        mark=synthetic(a['id'],key,[point,[point[k]+t[k]*10 for k in (0,1)]],suffix,width=row.get('length',2),line_width=row.get('width',.15),stop_shape=shape,
                       aircraft_types=row.get('aircraft_types'),aircraft=row.get('aircraft',''),stop_code='',aircraft_outward=p.get('outward',True),aircraft_height=p.get('aircraft_text_height',.2),stop_board_offset={'A':8,'B':8,'C':11,'D':16,'E':16,'F':16}.get(p.get('code_letter','C'),11))
        mark['name']='停止线 '+row.get('name','')+' · '+row.get('aircraft','');out[mark['id']]=mark
    return out

def shoulder_stripes(scene,surfaces):
    from pavement_geometry import route_objects,offset
    from scene_render import COLORS
    out=[]
    from automatic_markings import holding_locations
    holds=[h for h in holding_locations(scene) if 'point' in h]
    for mark in scene.assets.values():
        if mark['kind']=='MARKING' and mark['props']['mark_type'] in ('HOLD_A','HOLD_B','INTERMEDIATE_POINT'):
            holds.append(dict(point=mark['points'][0],tangent=g.unit(mark['points'][0],mark['points'][-1]),span=mark['props']['width']))
    indices={}
    for collection in (surfaces['pavement'],surfaces['shoulders']):
        indices[id(collection)]=[(min(p[0] for p in x['points']),min(p[1] for p in x['points']),max(p[0] for p in x['points']),max(p[1] for p in x['points']),x['points']) for x in collection]
    def inside(p,collection):return any(x0<=p[0]<=x1 and y0<=p[1]<=y1 and g.inside(p,pts) for x0,y0,x1,y1,pts in indices[id(collection)])
    def bar(oid,start,n,shoulder):
        for h in holds:
            q=h['point'];u=h['tangent'];v=(-u[1],u[0]);axis=[[q[k]-v[k]*h['span']/2 for k in (0,1)],[q[k]+v[k]*h['span']/2 for k in (0,1)]]
            if g.project(axis,start)[0]<=7.5:return
        if inside(start,surfaces['pavement']):return
        length=min(7.5,shoulder if shoulder<3.5 else max(0,shoulder-1.5))
        if length<=0:return
        points=[]
        for i in range(max(2,math.ceil(length/.4))+1):
            d=length*i/max(2,math.ceil(length/.4));q=[start[k]+n[k]*d for k in (0,1)]
            if inside(q,surfaces['pavement']):
                if points:break
                continue
            if inside(q,surfaces['shoulders']):points.append(q)
            elif points:break
        if len(points)>1 and g.distance(points[0],points[-1])>=min(.5,length*.8):out.append(dict(type='line',oid=oid,points=[points[0],points[-1]],stroke=COLORS['marking'],width=.9))
    for aid,a in route_objects(scene).items():
        if a['kind']=='RUNWAY' or not a['props'].get('auto_shoulder_bars',True):continue
        p=a['props'];shoulder=p.get('shoulder',0)
        if shoulder<=0:continue
        pts=a['points'];total=g.length(pts);count=max(1,math.ceil(total/12))
        stations={total*i/count for i in range(count+1)}
        for node in a.get('curve_nodes',[]):stations.add(g.project(pts,node['p'])[1])
        for s in sorted(stations):
            q,u=g.at(pts,s);_,before=g.at(pts,max(0,s-6));_,after=g.at(pts,min(total,s+6))
            if sum(before[k]*after[k] for k in (0,1))>.9999:continue
            for sign in (-1,1):
                n=[-u[1]*sign,u[0]*sign];start=[q[k]+n[k]*(p['width']/2+.1) for k in (0,1)];bar(aid,start,n,shoulder)
    for patch in surfaces['fillets']:
        relevant=[a for aid,a in route_objects(scene).items() if aid in patch['oid']]
        if relevant and not any(a['props'].get('auto_shoulder_bars',True) for a in relevant):continue
        pts=patch['arc'];total=g.length(pts);count=max(1,math.ceil(total/12));shoulder=max((a['props'].get('shoulder',0) for a in relevant),default=7.5)
        for i in range(count+1):
            q,u=g.at(pts,total*i/count)
            for sign in (-1,1):
                n=[-u[1]*sign,u[0]*sign];start=[q[k]+n[k]*.1 for k in (0,1)]
                bar(patch['oid'],start,n,shoulder)
    unique=[]
    for item in sorted(out,key=lambda x:-g.length(x['points'])):
        a,b=item['points'];u=g.unit(a,b)
        if any(min(g.distance(a,x['points'][0]),g.distance(a,x['points'][-1]))<1 and abs(sum(u[k]*g.unit(*x['points'])[k] for k in (0,1)))>.95 for x in unique):continue
        unique.append(item)
    return unique

def validate_editor_data(scene):
    for a in scene.assets.values():
        ids=set()
        for row in a['props'].get('stops',[]):
            if row.get('id') in ids:raise ValueError('停止线编号标识重复')
            ids.add(row.get('id'))
            if row.get('shape','T') not in ('T','CROSS','BAR','UNGUIDED'):raise ValueError('未知停止线图形')
            for key in ('offset','lateral','rotation','length','width'):
                value=row.get(key,0)
                if not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('停止线参数须为有限数值')
            if row.get('length',2)<(6 if row.get('shape')=='UNGUIDED' else 2) or row.get('width',.15)<.15:raise ValueError('停止线长度或线宽不足')
    for m in scene.movements.values():
        sets=list(m.get('branch_controls',{}).values())
        if m.get('bezier_controls'):sets.append(m['bezier_controls'])
        for controls in sets:
            if len(controls)!=2:raise ValueError('连接应有两个贝塞尔控制点')
            for point in controls:
                if len(point)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e7 for v in point):raise ValueError('无效连接控制点')

def translate_selection(scene,ids,dx,dy):
    from scene_hierarchy import descendants
    ids=set(ids);expanded=ids|{child for oid in ids for child in descendants(scene,oid)}
    for aid in expanded:
        a=scene.assets.get(aid)
        if not a:continue
        shift=lambda p:[p[0]+dx,p[1]+dy]
        a['points']=[shift(p) for p in a['points']]
        for key in ('design_vertices','pad_guide'):
            if key in a:a[key]=[shift(p) for p in a[key]]
        for node in a.get('curve_nodes',[]):
            for key in ('p','incoming','outgoing'):node[key]=shift(node[key])
    for m in scene.movements.values():
        if all(m[k]['asset'] in expanded for k in ('from','to')):
            if m.get('bezier_controls'):m['bezier_controls']=[[p[0]+dx,p[1]+dy] for p in m['bezier_controls']]
            for key,controls in m.get('branch_controls',{}).items():m['branch_controls'][key]=[[p[0]+dx,p[1]+dy] for p in controls]

def clone_selection(scene,data,ids,dx=20,dy=-20):
    import copy
    selected={aid for aid in ids if aid in data['assets']};mapping={}
    with scene.transaction('粘贴框选对象'):
        for aid in selected:
            old=data['assets'][aid];p=copy.deepcopy(old['props']);p.pop('network_id',None);p.pop('network_group',None)
            new=scene.create_asset(old['kind'],old['name']+' 副本',copy.deepcopy(old['points']),**p);mapping[aid]=new
            for key in ('curve_nodes','design_vertices','pad_guide'):
                if key in old:scene.assets[new][key]=copy.deepcopy(old[key])
        for old,new in mapping.items():
            a=scene.assets[new]
            for field in ('parent_id','pad_runway'):
                if a['props'].get(field) in mapping:a['props'][field]=mapping[a['props'][field]]
        for mid,m in data['movements'].items():
            if all(m[k]['asset'] in mapping for k in ('from','to')):
                ports=[]
                for key in ('from','to'):ports.append(dict(m[key],asset=mapping[m[key]['asset']]))
                props={k:copy.deepcopy(v) for k,v in m.items() if k not in ('id','from','to','role','name','container_id')}
                scene.connect(*ports,role=m['role'],name=m['name']+' 副本',**props)
        translate_selection(scene,set(mapping.values()),dx,dy)
    return set(mapping.values())

def outside_runways(scene,item):
    """Interrupt yellow guidance's black border on runway pavement (6.2.8 figure note)."""
    out=[];walk=0.;chunk=[];chunk_offset=0.
    runways=[a for a in scene.assets.values() if a['kind']=='RUNWAY']
    for p,q in zip(item['points'],item['points'][1:]):
        length=g.distance(p,q);cuts={0.,1.}
        for a in runways:
            origin=a['points'][0];u=g.unit(*a['points']);half=a['props']['width']/2
            local=lambda x:[sum((x[k]-origin[k])*u[k] for k in (0,1)),-(x[0]-origin[0])*u[1]+(x[1]-origin[1])*u[0]]
            hit=g.segment_box_interval(local(p),local(q),(0,-half,g.length(a['points']),half))
            if hit:cuts.update(hit)
        values=sorted(cuts)
        for lo,hi in zip(values,values[1:]):
            middle=[p[k]+(q[k]-p[k])*(lo+hi)/2 for k in (0,1)]
            inside=any(g.inside(middle,g.rectangle(a['points'],a['props']['width'])) for a in runways)
            if inside:
                if len(chunk)>1:out.append(dict(item,points=chunk,dash_offset=item.get('dash_offset',0)+chunk_offset))
                chunk=[]
            else:
                start=[p[k]+(q[k]-p[k])*lo for k in (0,1)];end=[p[k]+(q[k]-p[k])*hi for k in (0,1)]
                if not chunk:chunk=[start];chunk_offset=walk+length*lo
                chunk.append(end)
        walk+=length
    if len(chunk)>1:out.append(dict(item,points=chunk,dash_offset=item.get('dash_offset',0)+chunk_offset))
    return out
