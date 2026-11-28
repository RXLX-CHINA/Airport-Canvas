"""Component-sized signs, paired axis placements and editable reverse guides."""
import copy
import math
import uuid
import scene_geometry as g

BLOCKS={'LOCATION','DIRECTION','MAX_SPAN','MANDATORY','NO_ENTRY','HP'}

def side_pose(scene,a,station,side,source=None):
    from guidance20 import attachment_pose
    q,u=attachment_pose(scene,a,station,source);v=[-u[1],u[0]];right=side=='A';sign=-1 if right else 1
    if side!='CENTER':q=[q[k]+v[k]*sign*a['props']['width']/4 for k in (0,1)]
    if side!='CENTER' and (right!=(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):u=[-x for x in u]
    return q,u

def place_axis(scene,key,hit,side='CENTER',**extra):
    from marking_catalog import CATALOG
    from editor7_model import CROSS_POINTS,CROSS_PATHS
    _,aid,station,_=hit;a=scene.assets[aid];made=[];pair=uuid.uuid4().hex[:10]
    source=getattr(hit,'source',None)
    if source and not source[0].startswith('G20-'):source=None
    if source:extra['physical_axis_source']=list(source)
    with scene.transaction('沿中线放置标记'):
        for current in ('A','B') if side=='BOTH' else (side,):
            q,u=side_pose(scene,a,station,current,source);v=[-u[1],u[0]];p=dict(extra,label_asset=aid,attached_mark=True,attached_station=station,axis_side=current,pair_group=pair,axis_placement11=True)
            if key in CROSS_POINTS|CROSS_PATHS:p['width']=a['props']['width']/(1 if current=='CENTER' else 2)
            if key=='LOCATION':p['text']=a['props'].get('designation') or a['name']
            if key=='MAX_SPAN':p['maxspan']=a['props'].get('maxspan') or 36
            if key=='RWY_NUMBER' and a['kind']=='RUNWAY':
                end='a' if station<g.length(a['points'])/2 else 'b';p['text']=a['props']['label_'+end]
                if end=='b' and current=='CENTER':u=[-x for x in u];v=[-u[1],u[0]]
            if key in ('RWY_THRESHOLD','THRESHOLD_HEADS','AIMING_POINT','TDZ_BASIC','TDZ_CODED'):p['width']=a['props']['width']
            if key=='RWY_CIRCLE':p['width']=a['props']['width']/2
            if key in ('CLOSED_RWY','CLOSED_TWY'):p['width']=min(a['props']['width'],14.5 if key=='CLOSED_RWY' else 9.)
            width=p.get('width',a['props']['width']);points=[[q[k]-v[k]*width/2 for k in (0,1)],[q[k]+v[k]*width/2 for k in (0,1)]] if key in CROSS_PATHS else [q,[q[k]+u[k]*10 for k in (0,1)]]
            made.append(scene.create_marking(key,points,**p))
    return made

def refresh_axis(scene,aid):
    from editor7_model import CROSS_POINTS,CROSS_PATHS
    a=scene.assets[aid]
    for mark in scene.assets.values():
        p=mark['props']
        if p.get('axis_path11') and p.get('label_asset')==aid:
            from pavement_geometry import offset
            total=g.length(a['points']);lo=min(total,p['path_station_a']);hi=min(total,p['path_station_b']);side=p.get('axis_side','CENTER')
            if hi<=lo:continue
            pts=g.subpath(a['points'],lo,hi)
            if side!='CENTER':pts=offset(pts,(-1 if side=='A' else 1)*a['props']['width']/4)
            if side!='CENTER' and ((side=='A')!=(scene.data['meta'].get('traffic_side','RIGHT')=='RIGHT')):pts.reverse()
            mark['points']=pts;continue
        if not p.get('axis_placement11') or p.get('label_asset')!=aid:continue
        key=p['mark_type'];q,u=side_pose(scene,a,min(g.length(a['points']),p['attached_station']),p.get('axis_side','CENTER'),p.get('physical_axis_source'));v=[-u[1],u[0]]
        if key in CROSS_POINTS|CROSS_PATHS:p['width']=a['props']['width']/(1 if p.get('axis_side')=='CENTER' else 2)
        if key=='LOCATION':p['text']=a['props'].get('designation') or a['name']
        q=[q[k]+p.get('axis_offset19',[0,0])[k] for k in (0,1)]
        width=p.get('width',a['props']['width']);mark['points']=[[q[k]-v[k]*width/2 for k in (0,1)],[q[k]+v[k]*width/2 for k in (0,1)]] if key in CROSS_PATHS else [q,[q[k]+u[k]*10 for k in (0,1)]]

def legacy_reverse_routes(scene):
    cache=getattr(scene,'_reverse11',None)
    if cache and cache[0]==scene.revision and not scene._transaction_depth:return cache[1]
    result={}
    for aid,a in scene.assets.items():
        if not a['props'].get('rapid_exit') or a['props'].get('rapid_drawn_axis56') or not a['props'].get('join_reverse_visible',True):continue
        total=g.length(a['points']);links=[m for m in scene.movements.values() if m.get('legacy_attachment') and m['to']['asset']==aid]
        source=next((m for m in links if scene.assets[m['from']['asset']]['kind']=='RUNWAY'),None)
        receiver=next((m for m in links if scene.assets[m['from']['asset']]['kind'] in ('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')),None)
        if not source or not receiver or not source.get('join_reverse_visible',True):continue
        target=scene.assets[receiver['from']['asset']]
        if target['props'].get('flow','BOTH')!='BOTH':continue
        if a['props'].get('rapid_geometry39'):
            from rapid_editor39 import source
            from smart_routes import reverse_join
            state=source(scene,aid)
            if not state:continue
            branch=reverse_join(scene,state[0])
            if branch:
                points=branch['points'];oid=aid+':reverse11'
                result[oid]=dict(id=oid,kind='TAXIWAY',name=a['name'],points=points,props=dict(a['props']),
                                 owner=aid,source_path=a['points'],
                                 start_station=g.project(a['points'],points[0])[1],
                                 target=target['id'],target_from=receiver['from']['station'],target_to=branch['station'])
            continue

        path=a['points'] if source['to']['station']<total/2 else list(reversed(a['points']))
        station=receiver['from']['station'];_,axis=g.at(target['points'],station);incoming=g.unit(path[-2],path[-1]);direction=1 if sum(incoming[k]*axis[k] for k in (0,1))>=0 else -1
        reach=min(150,total*.55);available=station if direction>0 else g.length(target['points'])-station;delta=min(100,available-.1)
        if delta<max(20,a['props']['width']):continue
        dest=station-direction*delta;q,v=g.at(target['points'],dest);v=[-direction*x for x in v]
        start=max(0,total-reach);p,u=g.at(path,start);handle=min(70,g.distance(p,q)*.45)
        points=g.cubic(p,q,u,v,handle,steps=64)
        oid=aid+':reverse11';result[oid]=dict(id=oid,kind='TAXIWAY',name=a['name']+'反向引导',points=points,props=dict(a['props']),owner=aid,source_path=path,start_station=start,target=target['id'],target_from=station,target_to=dest)
    if not scene._transaction_depth:scene._reverse11=(scene.revision,result)
    return result

def refine(scene,result):
    from automatic_markings import synthetic
    from junction_routes import branches
    for mid,m in scene.movements.items():
        if m.get('legacy_attachment') or m.get('geometry')=='RAPID' or not m.get('guide_visible',True) or not m.get('join_reverse_visible',True):continue
        for branch in branches(scene,m):
            key='AUTO:'+mid+':REVERSE:'+branch['side']
            mark=synthetic(mid,'TWY_CENTER',branch['points'],'REVERSE:'+branch['side']);result[key]=mark
    for oid,a in legacy_reverse_routes(scene).items():
        mark=synthetic(a['owner'],'TWY_CENTER',a['points'],'RAPID_REVERSE');mark['name']='快速脱离道接收端反向引导线';result[mark['id']]=mark
    no_entry={}
    for mark in result.values():
        if mark['props']['mark_type']=='NO_ENTRY':no_entry.setdefault(mark.get('owner'),[]).append(mark)
    no_entry_centers={owner:[sum(row['points'][0][k] for row in rows)/len(rows) for k in (0,1)] for owner,rows in no_entry.items()}
    # Keep mandatory panels inside the actual pavement. Multiple runways use
    # separate rows instead of one enormous concatenated string.
    for mark in result.values():
        p=mark['props']
        if p['mark_type'] not in ('MANDATORY','NO_ENTRY'):continue
        if p['mark_type']=='MANDATORY' and 'mandatory_width21_2' in p:
            continue  # The holding-position fitter owns these panels.
        owner=mark.get('owner');a=scene.assets.get(owner);m=scene.movements.get(owner)
        if m:
            if not m.get('legacy_attachment'):a=dict(points=scene.movement_path(owner),props=dict(width=m['width']))
            else:a=next((scene.assets[m[s]['asset']] for s in ('to','from') if scene.assets[m[s]['asset']]['kind']!='RUNWAY'),None)
        if not a:continue
        width=a['props']['width'];paired_no_entry=p['mark_type']=='NO_ENTRY' and len(no_entry.get(owner,[]))==2;dual=paired_no_entry or p['mark_type']=='MANDATORY' and (width>=23 or p.get('paired_mandatory20_2',False));rows=[text.strip() for text in p.get('text','').split(' / ')];h=p.get('text_height',4);available=width/2-1.275 if dual else width-.4;ratio=p.get('character_ratio',.4);margin=p.get('margin',.5)
        required=max(len(text)*h*ratio for text in rows)+2*margin
        if required>available:
            old_height=h;h=max(.5,(available-2*margin)/max(1,max(len(text) for text in rows)*ratio));p.update(text_height=h,auto_scaled=True,design_text_height=old_height)
        p['text_lines']=rows
        q=mark['points'][0];u=g.unit(q,mark['points'][-1]);v=[-u[1],u[0]];_,station,axispoint=g.project(a['points'],q);offset=sum((q[k]-axispoint[k])*v[k] for k in (0,1));side=1 if offset>=0 else -1
        if dual:
            board=max(len(text)*h*ratio for text in rows)+2*margin
            if paired_no_entry:
                center=no_entry_centers[owner];side=1 if sum((q[k]-center[k])*v[k] for k in (0,1))>=0 else -1;anchor=[center[k]+v[k]*side*(1.075+board/2) for k in (0,1)];mark['points']=[anchor,[anchor[k]+u[k]*10 for k in (0,1)]]
            else:
                target=side*(1.075+board/2);delta=target-offset;mark['points']=[[pt[k]+v[k]*delta for k in (0,1)] for pt in mark['points']]
        if len(rows)>1:
            extra=(len(rows)-1)*(h+.5)/2;mark['points']=[[pt[k]-u[k]*extra for k in (0,1)] for pt in mark['points']]
    return result

def finalize_items(scene,items,generated):
    # White road paint is below aircraft guidance, never erasing taxi edges.
    road_ids={aid for aid,a in scene.assets.items() if a['kind']=='ROAD'}
    def road(item):
        oid=item.get('oid','');return oid in road_ids or oid.startswith('AUTO:') and oid.split(':')[1] in road_ids or generated.get(oid,{}).get('owner') in road_ids or scene.assets.get(oid,{}).get('props',{}).get('road_id') in road_ids
    surfaces=[];threshold_under=[];thresholds=[];under=[];road_ink=[];ink=[];number_under=[];numbers=[]
    for item in items:
        if item.get('surface11') or item.get('surface10') or item['type']=='polygon' and item.get('fill') in ('#454b53','#737b83','#9199a1','#c7cbd0') and not item.get('black_underlay'):surfaces.append(item)
        elif generated.get(item.get('oid'),scene.assets.get(item.get('oid'),{})).get('props',{}).get('mark_type') in ('RWY_THRESHOLD','THRESHOLD_BAR'):
            (threshold_under if item.get('black_underlay') else thresholds).append(item)
        elif generated.get(item.get('oid'),scene.assets.get(item.get('oid'),{})).get('props',{}).get('mark_type')=='RWY_NUMBER':
            (number_under if item.get('black_underlay') else numbers).append(item)
        elif item.get('black_underlay') or item['type']=='polygon' and item.get('fill') in ('#151a20','#101010'):under.append(item)
        elif road(item):road_ink.append(item)
        else:ink.append(item)
    return surfaces+threshold_under+thresholds+under+road_ink+ink+number_under+numbers
