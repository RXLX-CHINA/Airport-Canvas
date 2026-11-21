"""Approach-aware runway signs and deduplication at compound runway crossings."""
import scene_geometry as g

def runway_text(scene,r,q,tangent):
    p=r['props'];u=g.unit(r['points'][0],r['points'][-1]);station=g.project(r['points'],q)[1];length=g.length(r['points'])
    if station<=max(60,p['width']):return p['label_a']
    if length-station<=max(60,p['width']):return p['label_b']
    v=[-tangent[1],tangent[0]]
    # Order the runway ends left to right as seen approaching the holding line.
    ordered=sorted([(sum((r['points'][0][k]-q[k])*v[k] for k in (0,1)),p['label_a']),(sum((r['points'][-1][k]-q[k])*v[k] for k in (0,1)),p['label_b'])],reverse=True)
    return '-'.join(x[1] for x in ordered)

def refine_generated(scene,result):
    from automatic_markings import holding_locations,synthetic
    holds=holding_locations(scene);clusters=[]
    def crossing_point(h):
        m=scene.movements.get(h['owner']);r=scene.assets[h['runway']]
        path=scene.movement_path(h['owner']) if m and not m.get('legacy_attachment') else scene.assets[next((m[s]['asset'] for s in ('from','to') if scene.assets[m[s]['asset']]['kind']!='RUNWAY'),h['owner'])]['points'] if m else scene.assets[h['owner']]['points']
        hits=[q for a,b in zip(path,path[1:]) for c,d in zip(r['points'],r['points'][1:]) if (q:=g.crossing(a,b,c,d))]
        return min(hits,key=lambda q:g.distance(q,h['point'])) if hits else h['point']
    origins={id(h):crossing_point(h) for h in holds}
    def same_route(x,y):
        def taxi(h):
            m=scene.movements.get(h['owner']);return next((m[s]['asset'] for s in ('from','to') if scene.assets[m[s]['asset']]['kind']!='RUNWAY'),h['owner']) if m else h['owner']
        return taxi(x)==taxi(y)
    for h in holds:
        group=next((c for c in clusters if same_route(c[0],h) and (g.distance(c[0]['point'],h['point'])<max(12,h['width']) or g.distance(origins[id(c[0])],origins[id(h)])<1) and sum(c[0]['tangent'][k]*h['tangent'][k] for k in (0,1))>.7),None)
        if group is None:clusters.append([h])
        else:group.append(h)
    for cluster in clusters:
        ordered=sorted(cluster,key=lambda h:-scene.assets[h['runway']]['props']['width']);unique=[]
        for h in ordered:
            if h['runway'] not in [v['runway'] for v in unique]:unique.append(h)
        texts=[runway_text(scene,scene.assets[h['runway']],h['point'],h['tangent']) for h in unique]
        master=max(cluster,key=lambda h:g.distance(h['point'],origins[id(h)]));prefix='AUTO:'+master['owner']+':'+master['key']+':'
        for h in ordered:
            if h is master:continue
            duplicate='AUTO:'+h['owner']+':'+h['key']+':'
            if duplicate==prefix:continue
            for oid in list(result):
                if oid.startswith(duplicate) and any(k in oid for k in ('HOLD_A','MANDATORY','TWY_ENHANCED')):del result[oid]
        for oid,a in result.items():
            if oid.startswith(prefix) and a['props']['mark_type']=='MANDATORY':
                text=' / '.join(texts[:2]);a['props']['text']=text
                if master['width']>=23 or a['props'].get('paired_mandatory20_2'):
                    q=master['point'];u=master['tangent'];v=[-u[1],u[0]];old=a['points'][0];side=1 if sum((old[k]-q[k])*v[k] for k in (0,1))>=0 else -1
                    oldoffset=sum((old[k]-q[k])*v[k] for k in (0,1));new=side*((len(text)*a['props']['text_height']*.4+1)/2+1.075)
                    a['points']=[[pt[k]+v[k]*(new-oldoffset) for k in (0,1)] for pt in a['points']]
        if len(texts)>2:
            q=master['point'];u=master['tangent'];v=[-u[1],u[0]];anchor=[q[k]-u[k]*15-v[k]*master['width']/4 for k in (0,1)]
            a=synthetic(master['owner'],'DIRECTION',[anchor,[anchor[k]+u[k]*10 for k in (0,1)]],master['key']+':OTHER_RUNWAYS',text=' / '.join(texts[2:]),text_height=2);result[a['id']]=a
    # Replace one centre-board with two flanking boards, including prefab exits.
    rapid_receivers=set()
    for mid,m in scene.movements.items():
        if m['role']!='RAPID_EXIT':continue
        if m.get('legacy_attachment'):
            receiver=m['to']['asset']
            if receiver in rapid_receivers:continue
            rapid_receivers.add(receiver)
        old=[(oid,a) for oid,a in result.items() if a.get('owner')==mid and a['props']['mark_type']=='NO_ENTRY']
        if not old:
            taxi=scene.assets[m['to']['asset']];station=m['to']['station'];total=g.length(taxi['points']);s=max(0,total-30) if station<total/2 else min(total,30);q,u=g.at(taxi['points'],s)
            if station<total/2:u=[-x for x in u]
            old=[('',synthetic(mid,'NO_ENTRY',[q,[q[k]+u[k]*10 for k in (0,1)]],text='NO ENTRY',text_height=4,character_ratio=.4,margin=.5))]
        for oid,a in old:
            result.pop(oid,None);q=a['points'][0];u=g.unit(q,a['points'][-1]);v=[-u[1],u[0]];h=a['props']['text_height'];distance=(8*h*.4+1)/2+1.075
            for side in (-1,1):
                anchor=[q[k]+v[k]*side*distance for k in (0,1)];b=synthetic(mid,'NO_ENTRY',[anchor,[anchor[k]+u[k]*10 for k in (0,1)]],'NO_ENTRY:'+str(side),**{k:v for k,v in a['props'].items() if k!='mark_type'});result[b['id']]=b
    return result
