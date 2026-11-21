"""Logical station intervals share one unchanged physical path and its junctions."""
import copy,uuid
import scene_geometry as g
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
def ident():return uuid.uuid4().hex[:10]
def route(scene,aid):
    a=__import__('model20').axis(scene,aid)
    if not a or a['kind'] not in TAXIS:raise ValueError('请选择有效滑行道或连接道。')
    return a
def routes(scene):return {aid:a for aid,a in __import__('model20').axes(scene).items() if a['kind'] in TAXIS}
def pieces(a):
    return copy.deepcopy(a['props'].get('logical_segments18') or [dict(id=a['id'],lo=0.,hi=1.,name=a['props'].get('designation') or a['name'],network=a['props'].get('network_id') or a['id'])])
def piece_at(a,station):
    t=max(0.,min(1.,station/max(.001,g.length(a['points']))));ps=pieces(a)
    return next((p for p in ps if p['lo']-1e-8<=t<p['hi']-1e-8),ps[-1])
def sync_backup(a):
    p=a['props'];bounds=p.get('terminal_range18');old=p.get('terminal_logical_backup18')
    if bounds and old:
        lo,hi=bounds;result=[]
        for part in old:
            if part['lo']<lo:result.append(dict(part,id=ident(),hi=min(lo,part['hi'])))
            if part['hi']>hi:result.append(dict(part,id=ident(),lo=max(hi,part['lo'])))
        result += [dict(part,lo=lo+part['lo']*(hi-lo),hi=lo+part['hi']*(hi-lo)) for part in pieces(a)]
        p['terminal_logical_backup18']=sorted((x for x in result if x['hi']-x['lo']>1e-8),key=lambda x:x['lo'])
def prepare_backup(a):
    p=a['props'];backup=p.get('terminal_backup13')
    if backup and 'terminal_range18' not in p:
        path=backup['points'];L=max(.001,g.length(path));lo=g.project(path,a['points'][0])[1]/L;hi=g.project(path,a['points'][-1])[1]/L
        p['terminal_range18']=[lo,hi];p['terminal_logical_backup18']=[dict(id=ident(),lo=0.,hi=1.,name=p.get('designation') or a['name'],network=p.get('network_id') or a['id'])]
def split(scene,aid,station,name=None,keep=True):
    a=route(scene,aid);L=g.length(a['points'])
    if not __import__('math').isfinite(station) or L<=0:raise ValueError('分段位置无效。')
    t=station/L;part=piece_at(a,station)
    if min((t-part['lo'])*L,(part['hi']-t)*L)<1:raise ValueError('切口必须距当前逻辑段两端至少1m')
    if not keep and (not name or not name.strip() or name.strip()==part['name']):raise ValueError('请填写与当前段不同的新编号，或选择保留编号')
    with scene.transaction('逻辑分段（保持物理曲线和路口不变）'):
        prepare_backup(a)
        result=[]
        for p in pieces(a):
            if p['id']==part['id']:
                result += [dict(p,hi=t),dict(p,id=ident(),lo=t,name=p['name'] if keep else name.strip(),network=p['network'] if keep else ident())]
            else:result.append(p)
        a['props']['logical_segments18']=result;sync_backup(a);sync_signs(scene,aid)
    return aid
def rename(scene,aid,station,name):
    name=name.strip()
    if not name:raise ValueError('请输入编号')
    a=route(scene,aid);target=piece_at(a,station)
    with scene.transaction('逻辑段独立编号'):
        prepare_backup(a)
        ps=pieces(a)
        for p in ps:
            if p['id']==target['id']:p.update(name=name,network=ident())
        if len(ps)==1:
            obj=scene.assets.get(aid) or scene.movements.get(aid);obj['name']=name;a['props']['designation']=name
        a['props']['logical_segments18']=ps;sync_backup(a);sync_signs(scene,aid)
    return aid
def merge(scene,keys,name):
    if not name.strip() or not keys:raise ValueError('请填写编号并勾选逻辑段')
    network=ident()
    with scene.transaction('合并逻辑段编号（保持物理几何）'):
        for aid,a in routes(scene).items():
            if a['kind'] not in TAXIS:continue
            prepare_backup(a)
            ps=pieces(a);changed=False
            for p in ps:
                if (aid,p['id']) in keys:p.update(name=name.strip(),network=network);changed=True
            if changed:a['props']['logical_segments18']=ps;sync_backup(a);sync_signs(scene,aid)
        full={aid for aid,a in routes(scene).items() if all((aid,p['id']) in keys for p in pieces(a))}
        __import__('branch_selection20_15').merge_selection(scene,full)
def sync_signs(scene,aid):
    a=route(scene,aid)
    for m in scene.assets.values():
        p=m['props']
        if m['kind']=='MARKING' and p.get('label_asset')==aid and p.get('mark_type')=='LOCATION':p['text']=piece_at(a,p.get('attached_station',g.project(a['points'],m['points'][0])[1]))['name']
def delete_branch(scene,aid):
    with scene.transaction('删除指定岔路，不删除相邻主线'):
        for mid,m in list(scene.assets.items()):
            if m['kind']=='MARKING' and m['props'].get('label_asset')==aid:scene.delete(mid)
        scene.delete(aid)
        for a in scene.assets.values():
            backup=a['props'].get('terminal_backup13')
            if backup:
                backup['movements']={mid:m for mid,m in backup.get('movements',{}).items() if all(m[k]['asset'] in scene.assets for k in ('from','to'))}
                backup['marks']={mid:m for mid,m in backup.get('marks',{}).items() if m['props'].get('label_asset')!=aid}
            if a['kind']=='STAND' and a['props'].get('entry_asset')==aid:a['props']['entry_attached']=False;a['props'].pop('entry_asset',None)
        for key,values in scene.data['meta'].get('naming_groups',{}).items():scene.data['meta']['naming_groups'][key]=[x for x in values if x!=aid]
    return None
def terminal_station(scene,aid,station):
    from pavement_geometry import crossings,route_objects
    a=scene.assets[aid]
    total=g.length(a['points'])
    routes=route_objects(scene)
    candidates=[]
    for junction in crossings(scene):
        if aid not in junction['assets']:continue
        index=junction['assets'].index(aid)
        other=routes[junction['assets'][1-index]]
        s=junction['stations'][index]
        if not .1<s<total-.1:continue
        u,v=junction['tangents']
        sine=abs(u[0]*v[1]-u[1]*v[0])
        limit=min(12.,other['props']['width']/2/max(sine,.4))
        if abs(s-station)<=limit:candidates.append((abs(s-station),s))
    return min(candidates)[1] if candidates else station


def terminal(scene,aid,station,keep):
    if aid in scene.movements:
        if keep=='DELETE':
            with scene.transaction('删除独立连接道'):scene.delete(aid)
            return None
        raise ValueError('连接道的实体长度请通过端点编辑调整；编号分段不会改变几何。')
    if keep=='DELETE':return delete_branch(scene,aid)
    station=terminal_station(scene,aid,station)
    a=scene.assets[aid];ps=pieces(a);L=g.length(a['points']);t=station/L;lo,hi=(0.,t) if keep=='START' else (t,1.)
    with scene.transaction('物理末端截断并保留逻辑段归属'):
        a['props'].setdefault('terminal_logical_backup18',copy.deepcopy(ps));bounds=a['props'].get('terminal_range18',[0.,1.]);newbounds=[bounds[0]+lo*(bounds[1]-bounds[0]),bounds[0]+hi*(bounds[1]-bounds[0])]
        __import__('signs21_2').shift_stations(scene,aid,L,-station if keep=='END' else 0)
        __import__('interaction15').terminal(scene,aid,station,keep)
        a['props']['logical_segments18']=[dict(p,lo=(max(lo,p['lo'])-lo)/(hi-lo),hi=(min(hi,p['hi'])-lo)/(hi-lo)) for p in ps if min(hi,p['hi'])-max(lo,p['lo'])>1e-8]
        a['props']['terminal_range18']=newbounds;sync_signs(scene,aid)
    return aid
def restore(scene,aid):
    with scene.transaction('恢复截断道面及逻辑段'):
        a=scene.assets[aid];ps=a['props'].pop('terminal_logical_backup18',None);bounds=a['props'].pop('terminal_range18',None);length=g.length(a['points'])
        __import__('interaction15').terminal(scene,aid,0,enabled=False)
        if bounds:__import__('signs21_2').shift_stations(scene,aid,length,bounds[0]*g.length(a['points']))
        if ps:a['props']['logical_segments18']=ps
        sync_signs(scene,aid)
def locations(scene,result):
    from automatic_markings import synthetic
    for aid,a in routes(scene).items():
        if a['kind'] not in TAXIS or not a['props'].get('logical_segments18'):continue
        for oid in list(result):
            if result[oid].get('owner')==aid and result[oid]['props'].get('mark_type')=='LOCATION':result.pop(oid)
        closed=scene.is_closed(aid) if aid in scene.assets else (a['props'].get('closed',False) or any(scene.is_closed(a['props'][side]['asset']) for side in ('from','to')))
        if closed or not a['props'].get('auto_markings',True) or not a['props'].get('auto_signs',True):continue
        L=g.length(a['points'])
        for p in pieces(a):
            q,u=g.at(a['points'],L*(p['lo']+p['hi'])/2);v=[-u[1],u[0]];q=[q[k]-v[k]*a['props']['width']/4 for k in (0,1)]
            m=synthetic(aid,'LOCATION',[q,[q[k]+u[k]*10 for k in (0,1)]],'LOCATION18:'+p['id'],text=p['name'],text_height=4);result[m['id']]=m
    return result
def validate_asset(a):
    ps=a['props'].get('logical_segments18')
    if ps is None:return
    import math
    if a['kind'] not in TAXIS or not isinstance(ps,list) or not ps:raise ValueError('无效的逻辑分段表')
    end=0.;ids=set()
    for p in ps:
        if not isinstance(p,dict) or not isinstance(p.get('id'),str) or p['id'] in ids or not isinstance(p.get('name'),str) or not p['name'].strip():raise ValueError('逻辑段标识或编号无效')
        lo,hi=p.get('lo'),p.get('hi')
        if not isinstance(lo,(int,float)) or not isinstance(hi,(int,float)) or not math.isfinite(lo+hi) or abs(lo-end)>1e-7 or not lo<hi<=1+1e-7:raise ValueError('逻辑段须连续覆盖同一条物理路线')
        ids.add(p['id']);end=hi
    if abs(end-1)>1e-7:raise ValueError('逻辑段未覆盖路线终点')
