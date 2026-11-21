"""Semantic stand junction editing and arc-stationed identifier plates."""
import copy,math
import scene_geometry as g
from stand11 import frame
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')

def local(a,q):
    o,u,v=frame(a);return [sum((q[k]-o[k])*axis[k] for k in (0,1)) for axis in (u,v)]
def world(a,q):
    o,u,v=frame(a);return [o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
def baseline(a,scene=None):
    from stand13 import design as previous
    return previous(a,scene)
def deform(path,edits):
    if not edits:return path
    L=g.length(path);stations=[0.];out=[]
    for p,q in zip(path,path[1:]):stations.append(stations[-1]+g.distance(p,q))
    for q,s in zip(path,stations):
        delta=[0.,0.]
        for station,vector in edits:
            reach=max(station,L-station,.01);weight=max(0,1-abs(s-station)/reach);weight=weight*weight*(3-2*weight)
            for k in (0,1):delta[k]+=vector[k]*weight
        out.append([q[k]+delta[k] for k in (0,1)])
    return out
def geometry(a,scene=None):
    base=baseline(a,scene);paths={p['key']:p['points'] for p in base['paths']};branches=[];kind=a['props'].get('lead_type','A');edits=a['props'].get('junction_edits14',{}) if a['props'].get('junction_type14',kind)==kind else {}
    for n,number in enumerate(base['numbers']):
        # A/D entry and turn are separated by an identifier plate. Reconstruct
        # the continuous design axis first, then cut at the current plate station.
        side=1 if local(a,number['point'])[1]>0 else -1
        entry=paths.get('ENTRY_STUB:'+str(side),paths.get('ENTRY:'+str(side),[]));turn=paths.get('TURN:'+str(side),[])
        if kind=='C':path=paths.get('LABEL_STUB',[])+paths.get('ALIGN',[])
        elif entry and turn:
            reach=min(6.,g.length(entry)*.45,g.length(turn)*.3);left=g.subpath(entry,0,g.length(entry)-reach);right=g.subpath(turn,reach,g.length(turn));gap=g.cubic(left[-1],right[0],g.at(entry,g.length(entry)-reach)[1],g.at(turn,reach)[1],g.distance(left[-1],right[0])*.45,steps=128);path=left+gap[1:]+right[1:]
        else:path=turn
        if len(path)<2:continue
        path=copy.deepcopy(path);L=g.length(path);changes=[]
        for key,s in [('ENTRY:'+str(side),0.),('BEND:'+str(side),L*.55),('MERGE',L)]:
            if key in edits:
                old,_=g.at(path,s);target=world(a,edits[key]);changes.append((s,[target[k]-old[k] for k in (0,1)]))
        path=deform(path,changes)
        parent=scene.assets.get(a['props'].get('entry_asset')) if scene else None
        if parent and a['props'].get('entry_attached',True) and kind!='C':
            target=g.project(parent['points'],path[0])[2];path=deform(path,[(0,[target[k]-path[0][k] for k in (0,1)])])
        branches.append(dict(key=str(side),points=path,number=number,index=n,default_station=g.project(path,number['point'])[1]))
    return base,branches
def design(a,scene=None):
    base,branches=geometry(a,scene);kind=a['props'].get('lead_type','A');numbers=[];paths=[];h=a['props'].get('number_height',4);before=5*h/8+1;after=5*h/8+h/2+1
    fractions=a['props'].get('label_station14',{})
    for b in branches:
        path=b['points'];L=g.length(path);s=fractions.get('paired',b['default_station']/max(L,.01))*L;s=max(before,min(max(before,L-after),s));q,u=g.at(path,s)
        if kind=='C':
            # C plates are beside the alignment, not across it.
            number=dict(b['number']);old=local(a,number['point']);old[0]=local(a,q)[0];number['point']=world(a,old);numbers.append(number)
            continue
        numbers.append(dict(point=q,direction=list(u),text_rotation_offset=0))
        for suffix,lo,hi in [('ENTRY',0,s-before),('TURN',s+after,L)]:
            if hi>lo+.01:paths.append(dict(key=suffix+':'+b['key'],points=g.subpath(path,lo,hi)))
    if kind=='C':
        paths=copy.deepcopy(base['paths'])
        if numbers and base['numbers']:
            dx=local(a,numbers[0]['point'])[0]-local(a,base['numbers'][0]['point'])[0]
            for part in paths:
                index=-1 if part['key']=='LABEL_STUB' else 0
                q=local(a,part['points'][index]);q[0]+=dx;part['points'][index]=world(a,q)
    align=next((copy.deepcopy(p) for p in base['paths'] if p['key']=='ALIGN'),None)
    if align and kind!='C':
        if 'MERGE' in a['props'].get('junction_edits14',{}):align['points'][0]=world(a,a['props']['junction_edits14']['MERGE'])
        if g.distance(align['points'][0],align['points'][-1])>.05:paths.append(align)
    base.update(paths=paths,numbers=numbers);return base
def handles(a,scene=None):
    base,branches=geometry(a,scene);out=[]
    for b in branches:
        if a['props'].get('lead_type','A')!='C':
            for key,s in [('ENTRY:'+b['key'],0),('MERGE',g.length(b['points']))]:
                if not any(x['key']==key for x in out):out.append(dict(key=key,point=g.at(b['points'],s)[0],kind='JUNCTION'))
    for i,n in enumerate(design(a,scene)['numbers']):out.append(dict(key=str(i),point=n['point'],kind='NUMBER'))
    if a['props'].get('lead_type','A')=='C':
        for p in base['paths']:
            if p['key'] in ('LABEL_STUB','ALIGN'):out.append(dict(key='ENTRY:0' if p['key']=='LABEL_STUB' else 'MERGE',point=p['points'][0],kind='JUNCTION'))
    return out
def move_junction(scene,aid,key,q):
    a=scene.assets[aid];p=a['props'];parent=scene.assets.get(p.get('entry_asset'))
    if key.startswith('ENTRY') and parent and p.get('entry_attached',True):q=g.project(parent['points'],q)[2]
    p.setdefault('junction_edits14',{})[key]=local(a,q);p['junction_type14']=p.get('lead_type','A')
    if p.get('lead_type','A')=='C':
        # Direct-entry C has no turn arc: junction drag changes its axial gap.
        _,branches=geometry(a,scene)
        if branches:p['label_station14']={'paired':g.project(branches[0]['points'],q)[1]/max(.01,g.length(branches[0]['points']))}
def slide_number(scene,aid,index,q):
    a=scene.assets[aid];_,branches=geometry(a,scene)
    if not branches:return
    b=branches[min(index,len(branches)-1)];L=g.length(b['points']);station=g.project(b['points'],q)[1];a['props']['label_station14']={'paired':station/max(.01,L)}
    for oid in list(scene.data['generated_overrides']):
        if oid.startswith('AUTO:'+aid+':STAND_NUMBER'):scene.data['generated_overrides'].pop(oid)
def snap_delta(scene,roots,delta,tolerance):
    from transform11 import members
    ids=members(scene,roots)
    for aid in ids:
        a=scene.assets.get(aid)
        if not a or a['kind']!='STAND' or not a['props'].get('move_snap14',True):continue
        q=[a['points'][0][k]+delta[k] for k in (0,1)];hits=[]
        for tid,t in scene.assets.items():
            if t['kind'] in TAXIS:
                d,s,p=g.project(t['points'],q)
                if d<=tolerance:hits.append((d,tid,s,p))
        if hits:
            hit=min(hits);return [delta[k]+hit[3][k]-q[k] for k in (0,1)],(aid,hit[1],hit[2],hit[3])
    return list(delta),None
def combine(scene,aid,count=3,parallel=True,spacing=24.,angle=15.,primary='CENTER'):
    if count not in (2,3):raise ValueError('组合机位须为2套或3套')
    if spacing<=0 or not 0<=angle<60:raise ValueError('组合间距或角度无效')
    from stand13 import ensure_groups
    ensure_groups(scene);a=scene.assets[aid];gid=a['props']['stand_group13'];group=scene.data['groups'][gid]
    if group.get('combined14'):raise ValueError('此组已经是组合机位，请直接编辑组内机位')
    o,u,v=frame(a);L=g.length(a['points']);base=a['name'];made=[aid]
    with scene.transaction('建立组合机位'):
        group['combined14']=dict(count=count,parallel=parallel,primary=primary)
        choices=[('L',1),('R',-1)] if count==3 else [('R',-1)]
        if count==2:a['name']=base+'L';a['props']['stand_number']=a['name']
        for suffix,sign in choices:
            start=[o[k]+v[k]*sign*spacing for k in (0,1)];theta=0 if parallel else -sign*math.radians(angle);d=[u[0]*math.cos(theta)-u[1]*math.sin(theta),u[0]*math.sin(theta)+u[1]*math.cos(theta)];p=copy.deepcopy(a['props'])
            for key in ('stand_group13','lead_edits13','junction_edits14','label_station14','stops'):p.pop(key,None)
            p.update(stand_number=base+suffix,has_bridge=False,stand_support=False,auxiliary=primary=='CENTER',entry_attached=False,aircraft_length=a['props'].get('aircraft_length',scene.scenario['aircraft_length'])*.75,aircraft_span=a['props'].get('aircraft_span',scene.scenario['aircraft_wingspan'])*.75)
            new=scene.create_asset('STAND',base+suffix,[start,[start[k]+d[k]*L for k in (0,1)]],**p);scene.assets[new]['container_id']=gid;scene.assets[new]['props']['stand_group13']=gid
            parent=scene.assets.get(p.get('entry_asset'))
            if parent:distance,s,q=g.project(parent['points'],start);scene.assets[new]['points'][0]=q;scene.assets[new]['props'].update(entry_station=s,entry_attached=True)
            made.append(new)
        a['props']['auxiliary']=primary=='SIDES' and count==3
        for sid in made:scene.assets[sid]['props'].update(combination14=gid,excludes=[x for x in made if x!=sid and (count==2 or x==aid or sid==aid)])
    return made
