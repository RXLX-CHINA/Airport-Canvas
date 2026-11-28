"""Complete unbroken axes; symmetric arc stationing; persistent parent binding."""
import copy,math
import scene_geometry as g
from stand14 import local,world,baseline
from stand11 import frame,uses_drawn_lead

def remote_exit_hit(scene,point,tolerance,visible=None):
    from model20 import axes,TAXIS
    from guidance20 import snap_axis
    return snap_axis(scene,point,{oid:axis for oid,axis in axes(scene).items() if axis['kind'] in TAXIS and (visible is None or visible(oid))},tolerance)

def draw_exit_snap(editor,hit,tag):
    from interface_language import tr
    x,y=editor.screen(hit[3])
    color='#35bbd3'
    editor.canvas.create_oval(x-5,y-5,x+5,y+5,outline=color,width=2,tags=tag)
    editor.canvas.create_text(x,y-12,text=tr('引出线吸附至滑行道中线'),
                              fill=color,anchor='s',tags=tag)


def remote_stand_props(hit):
    return dict(remote_stand=True,has_bridge=False,show_safety=True,
                exit_asset=hit[1],exit_station=hit[2])

def drawn_remote_exit_props(a,vertices,hit=None):
    stop=a['points'][-1]
    _,forward,normal=frame(a)
    offsets=[[sum((q[k]-stop[k])*axis[k] for k in (0,1)) for axis in (forward,normal)] for q in vertices]
    return dict(remote_stand=True,has_bridge=False,show_safety=True,exit_vertices69=offsets,
                **(dict(exit_asset=hit[1],exit_station=hit[2]) if hit else {}))

def remote_exit_vertices(a,scene):
    from model20 import axis
    p=a['props']
    stop=a['points'][-1]
    _,forward,normal=frame(a)
    points=[[stop[k]+forward[k]*x+normal[k]*y for k in (0,1)] for x,y in p.get('exit_vertices69',())]
    target=axis(scene,p.get('exit_asset'))
    if points and target:
        points[-1]=g.at(target['points'],p.get('exit_station',0.))[0]
    return points


def remote_exit_fork_props(a,point):
    stop=a['points'][-1]
    _,forward,normal=frame(a)
    offset=[sum((point[k]-stop[k])*axis[k] for k in (0,1)) for axis in (forward,normal)]
    return dict(a['props'],exit_fork_offset=offset)


def remote_exit_lines(a,scene):
    from model20 import axis
    p=a['props']
    vertices=remote_exit_vertices(a,scene)
    if vertices:
        points=[a['points'][-1],*vertices]
        return [rounded_lead(dict(points=points,props=p))] if g.length(points)>.01 else []
    target=axis(scene,p.get('exit_asset'))
    if not target:return []
    path=target['points'];length=g.length(path)
    station=min(length,max(0.,p.get('exit_station',0.)))
    stop=a['points'][-1];_,heading,normal=frame(a)
    join,_=g.at(path,station)
    reach=min(25.,g.distance(stop,join)*.55)
    x,y=p.get('exit_fork_offset',(reach,0.))
    fork=[stop[k]+heading[k]*x+normal[k]*y for k in (0,1)]
    branch_heading=g.unit(stop,fork) if g.distance(stop,fork)>.01 else heading
    arms=[]
    _,axis_direction=g.at(path,station)
    left_sign=1 if sum(u*v for u,v in zip(axis_direction,normal))>=0 else -1
    direction=p.get('exit_direction','BOTH')
    signs=(left_sign,) if direction=='LEFT' else (-left_sign,) if direction=='RIGHT' else (-1,1)
    for sign in signs:
        end_station=min(length,max(0.,station+sign*reach))
        if abs(end_station-station)<.5:continue
        end,tangent=g.at(path,end_station)
        tangent=[sign*x for x in tangent]
        arms.append(g.cubic(fork,end,branch_heading,tangent,g.distance(fork,end)*.35))
    return [[stop,fork],*arms] if arms else [[stop,join]]

def remote_exit_handles(a,scene):
    vertices=remote_exit_vertices(a,scene)
    if vertices:return list(enumerate(vertices))
    paths=remote_exit_lines(a,scene)
    return [('FORK',paths[0][-1])] if len(paths)>1 else []


def reflected(a,q):
    x,y=local(a,q);return world(a,[x,-y])
def rounded_lead(a):
    from curve_model import evaluate,rounded_nodes
    points=a['points']
    if len(points)<3:return points
    try:
        nodes,_=rounded_nodes(points,a['props'].get('lead_radius',20.))
        return evaluate(nodes)
    except ValueError:
        # Old projects can contain coincident vertices or near reversals.
        return points

def approach_frame(a):
    if uses_drawn_lead(a):
        return dict(a,points=a['points'][:2],props=dict(a['props'],stand_polyline=False))
    return a


def geometry(a,scene=None):
    drawn=uses_drawn_lead(a)
    kind=a['props'].get('lead_type','A')
    if kind=='ICAO':
        path=rounded_lead(a) if drawn else a['points']
        return {'paths':[],'numbers':[]},[dict(key='1',points=path,
                number={},index=0,default_station=min(g.length(path)*.4,8.))]
    if drawn and kind=='C':
        path=rounded_lead(a)
        length=g.length(path)
        station=min(length*.35,18.)
        q,u=g.at(path,station)
        number=dict(point=q,direction=list(u),text_rotation_offset=0)
        return {'paths':[],'numbers':[]},[dict(key='1',points=path,number=number,index=0,default_station=station)]
    from stand14 import geometry as previous
    alignment=rounded_lead(a) if drawn else None
    a=approach_frame(a)
    base,raw=previous(a,None)
    p=a['props']
    if not raw:return base,[]
    positive=next((b for b in raw if b['key']=='1'),raw[0]);path=copy.deepcopy(positive['points'])
    if positive['key']=='-1':path=[reflected(a,q) for q in path]
    scale=1.
    if alignment:
        merge=local(a,path[-1])[0]
        # Merge on the straight portion before the first rounded bend.
        first_leg=g.distance(*alignment[:2])
        if merge>first_leg*.9:
            scale=first_leg*.9/merge
        path=[world(a,[x*scale,y]) for x,y in (local(a,q) for q in path)]
        tail=g.subpath(alignment,merge*scale,g.length(alignment))
        base['paths']=[part for part in base['paths'] if part['key']!='ALIGN']
        base['paths'].append(dict(key='ALIGN',points=tail))
    allowed=(1,) if p.get('lead_direction')=='LEFT' else (-1,) if p.get('lead_direction')=='RIGHT' else (-1,1);branches=[]
    for side in allowed:
        pts=copy.deepcopy(path) if side==1 else [reflected(a,q) for q in path]
        key='ENTRY:'+str(side);parent=__import__('model20').axis(scene,p.get('entry_asset')) if scene else None
        if kind=='C':key='ENTRY:0'
        if parent and p.get('entry_bindings15',{}).get(key,p.get('entry_attached',True)):
            from stand14 import deform
            _,station,q=g.project(parent['points'],pts[0])
            pts=deform(pts,[(0,[q[k]-pts[0][k] for k in (0,1)])])
            if kind=='B':
                axis=g.at(parent['points'],station)[1]
                end=pts[-1]
                offsets=[axis[0]*(y-q[1])-axis[1]*(x-q[0]) for x,y in pts]
                wanted=offsets[-1]
                if wanted and any(value*wanted<-.001 for value in offsets):
                    forward=frame(a)[1]
                    toward=tuple(end[i]-q[i] for i in (0,1))
                    if sum(axis[i]*toward[i] for i in (0,1))<0:axis=tuple(-v for v in axis)
                    along=max(0.,(axis[0]*forward[1]-axis[1]*forward[0])
                              * math.copysign(1.,axis[0]*toward[1]-axis[1]*toward[0]))
                    handle=g.distance(q,end)/3
                    if along>1e-8:handle=min(handle,abs(wanted)/along)
                    pts=g.cubic(q,end,axis,forward,handle,steps=64)
        number=next((b['number'] for b in raw if b['key']==str(side)),positive['number']);x,y=local(a,number['point']);default=g.project(pts,world(a,[x*scale,y]))[1]
        branches.append(dict(key=str(side),points=pts,number=number,index=len(branches),default_station=default))
    return base,branches

def design(a,scene=None):
    from geometry11 import polygon,LineString,unary_union,lines
    from marking_catalog import primitives
    base,branches=geometry(a,scene);p=a['props'];kind=p.get('lead_type','A');kind='C' if kind=='ICAO' else kind;numbers=[];full=[];h=p.get('number_height',4);margin=p.get('number_clearance15',1.)
    if not branches:return base
    fraction=p.get('label_station14',{}).get('paired')
    canonical=next((b for b in branches if b['key']=='1'),branches[0])
    first_fraction=None
    for b in branches:
        path=b['points']
        path_index=g.PathIndex(path)
        length=path_index.length
        station=b['default_station'] if fraction is None else fraction*length
        limit=min(h+margin,length/2)
        station=max(limit,min(length-limit,station))
        if numbers:
            clearance=max(2*h+2*margin,.65*h*len(str(p.get('stand_number') or a.get('name','101')))+2*margin)
            stagger=min(h,length*.2)
            if (abs(station-first_fraction*length)<stagger
                    or g.distance(numbers[0]['point'],path_index.at(station)[0])<clearance):
                candidates=[station]+[limit+(length-2*limit)*i/32 for i in range(33)]
                station=min(candidates,key=lambda s:(
                    max(0,clearance-g.distance(numbers[0]['point'],path_index.at(s)[0])),
                    max(0,stagger-abs(s-first_fraction*length)),abs(s-station)))
        else:
            first_fraction=station/max(.01,length)
        q,u=g.at(path,station)
        numbers.append(dict(point=q,direction=list(u),text_rotation_offset=0))
        full.append(dict(key='BRANCH:'+b['key'],points=path))
    align=next((copy.deepcopy(x) for x in base['paths'] if x['key']=='ALIGN'),None)
    if align and kind!='C':
        align['points'][0]=branches[0]['points'][-1]
        if g.distance(*[align['points'][i] for i in (0,-1)])>.01:full.append(align)
    if kind=='C':full=[dict(key='DIRECT',points=canonical['points'])]
    if p.get('ga_stand') or not p.get('show_number',True):
        base.update(paths=full,numbers=[],full_paths15=full)
        return base
    if p.get('single_lead_number'):
        path=align['points'] if align and align in full else canonical['points']
        length=g.length(path)
        fraction=p.get('label_station14',{}).get('center',.5)
        q,u=g.at(path,max(0.,min(1.,fraction))*length)
        numbers=[dict(point=q,direction=list(u),text_rotation_offset=0)]
    masks=[]
    for index,n in enumerate(numbers):
        if scene is not None:
            mark_id='AUTO:'+a['id']+':STAND_NUMBER'+(':'+str(index) if index else '')
            if scene.data['generated_overrides'].get(mark_id,{}).get('hidden'):
                continue
        m=dict(id='plate',points=[n['point'],[n['point'][k]+n['direction'][k]*10 for k in (0,1)]],props=dict(mark_type='STAND_NUMBER',text=p.get('stand_number',a.get('name','101')),text_height=h))
        shape=next(x for x in primitives(m) if x['type']=='polygon');masks.append(polygon(shape['points']).buffer(margin,join_style=2))
    mask=unary_union(masks);paths=[]
    for part in full:
        axis=LineString(part['points']);pieces=sorted(lines(axis.difference(mask)),key=lambda line:axis.project(__import__('geometry11').Point(line.coords[0])))
        for i,line in enumerate(pieces):
            key=part['key']
            if key.startswith('BRANCH:'):key=('ENTRY:' if i==0 and len(pieces)>1 else 'TURN:')+key.split(':')[1]+(':'+str(i) if i>1 else '')
            elif i:key+=':'+str(i)
            if line.length>.01:paths.append(dict(key=key,points=[list(x) for x in line.coords]))
    base.update(paths=paths,numbers=numbers,full_paths15=full);return base

def handles(a,scene=None):
    _,branches=geometry(a,scene);out=[]
    for b in branches:
        key='ENTRY:0' if a['props'].get('lead_type') in ('C','ICAO') else 'ENTRY:'+b['key']
        if not any(h['key']==key for h in out):out.append(dict(key=key,point=b['points'][0],kind='JUNCTION'))
    if branches:out.append(dict(key='MERGE',point=branches[0]['points'][-1],kind='JUNCTION'))
    for i,n in enumerate(design(a,scene)['numbers']):out.append(dict(key=str(i),point=n['point'],kind='NUMBER'))
    return out

def slide_number(scene,aid,index,q):
    a=scene.assets[aid];_,branches=geometry(a,scene)
    if not branches:return
    b=branches[min(index,len(branches)-1)];canonical=next((x for x in branches if x['key']=='1'),branches[0])
    path=b['points']
    key='paired'
    if a['props'].get('single_lead_number'):
        base,_=geometry(a,scene)
        align=next((part['points'] for part in base['paths'] if part['key']=='ALIGN'),None)
        path=align if align and g.length(align)>.01 and a['props'].get('lead_type') not in ('C','ICAO') else canonical['points']
        key='center'
    station=g.project(path,q)[1]
    a['props'].setdefault('label_station14',{})[key]=station/max(.01,g.length(path))
    for oid in list(scene.data['generated_overrides']):
        if oid.startswith('AUTO:'+aid+':STAND_NUMBER'):scene.data['generated_overrides'].pop(oid)

def move_junction(scene,aid,key,q,tolerance=None):
    a=scene.assets[aid];p=a['props'];parent=__import__('model20').axis(scene,p.get('entry_asset'));bound=False
    tolerance=p.get('snap_tolerance15',2.) if tolerance is None else tolerance
    if key.startswith('ENTRY'):
        if parent:
            d,s,target=g.project(parent['points'],q)
            if d<=tolerance:q=target;bound=True
        p.setdefault('entry_bindings15',{})[key]=bound
    value=local(a,q)
    if key=='MERGE':value[1]=0.
    edits=p.setdefault('junction_edits14',{});edits[key]=value;p['junction_type14']=p.get('lead_type','A')
    if key in ('ENTRY:1','ENTRY:-1'):
        other='ENTRY:-1' if key=='ENTRY:1' else 'ENTRY:1';edits[other]=[value[0],-value[1]];p.setdefault('entry_bindings15',{})[other]=bound
    p['entry_attached']=any(p.get('entry_bindings15',{}).values()) if p.get('entry_bindings15') else p.get('entry_attached',True)

def maintain_binding(scene,a,old,ids):
    p=a['props'];parent=p.get('entry_asset')
    if a['kind']=='STAND' and parent in scene.assets and parent not in ids and old['props'].get('entry_attached',True):
        a['points'][0]=copy.deepcopy(old['points'][0]);p['entry_station']=old['props'].get('entry_station',g.project(scene.assets[parent]['points'],old['points'][0])[1]);p['entry_attached']=True

def snap_delta(scene,roots,delta,tolerance):
    from transform11 import members
    import model20
    rows=[]
    ids=members(scene,roots)
    for aid in ids:
        a=scene.assets.get(aid)
        if not a or a['kind']!='STAND' or not a['props'].get('move_snap14',True):continue
        q=[a['points'][0][k]+delta[k] for k in (0,1)]
        for parent,axis in model20.axes(scene).items():
            if parent in ids:continue
            distance,station,target=g.project(axis['points'],q)
            if distance<=tolerance:rows.append((distance,aid,parent,station,target))
    if not rows:return list(delta),None
    _,aid,parent,station,q=min(rows,key=lambda row:(row[0],row[1],row[2]))
    return [q[k]-scene.assets[aid]['points'][0][k] for k in (0,1)],(aid,parent,station,q)
from stand14 import combine


class LeadCrossings:
    """Find interior crossings using the same axes available for stand snapping."""
    def __init__(self,scene):
        from model20 import axes,TAXIS
        from shapely.geometry import LineString
        from shapely import STRtree
        self.axes=[a for a in axes(scene).values()
                   if a['kind'] in TAXIS and not a['props'].get('closed')
                   and a['props'].get('center_visible',True)]
        self.lines=[LineString(a['points']) for a in self.axes]
        self.tree=STRtree(self.lines)

    def curves(self,stand,paths):
        from shapely.geometry import LineString
        default_radius=max(0.,stand['props'].get('lead_radius',20.))
        settings=stand['props'].get('lead_crossing_settings',{})
        for part in paths:
            lead=part['points']
            stem=LineString(lead)
            for index in sorted(self.tree.query(stem,predicate='intersects')):
                axis=self.axes[index]
                taxi=axis['points']
                intersection=stem.intersection(self.lines[index])
                points=intersection.geoms if intersection.geom_type=='MultiPoint' else (intersection,)
                crossings=sorted((stem.project(point),point) for point in points
                                 if point.geom_type=='Point' and not point.is_empty)
                for number,(lead_station,point) in enumerate(crossings):
                    if min(lead_station,stem.length-lead_station)<.1:
                        continue
                    taxi_station=self.lines[index].project(point)
                    group=f"STAND_CROSS:{part['key']}:{axis['id']}:{number}"
                    config=settings.get(group,{})
                    radius=config.get('radius',default_radius)
                    for side_a in (-1,1):
                        for side_b in (-1,1):
                            taxi_room=taxi_station if side_b<0 else self.lines[index].length-taxi_station
                            lead_room=lead_station if side_a<0 else stem.length-lead_station
                            _,u=g.at(taxi,taxi_station)
                            _,v=g.at(lead,lead_station)
                            dot=-side_a*side_b*sum(a*b for a,b in zip(u,v))
                            angle=math.acos(max(-1.,min(1.,dot)))
                            if not math.radians(10)<angle<math.radians(170):continue
                            reach=min(radius*math.tan(angle/2),taxi_room*.9,lead_room*.9)
                            if reach<.2:continue
                            start,u=g.at(taxi,taxi_station+side_b*reach)
                            end,v=g.at(lead,lead_station+side_a*reach)
                            handle=reach*(4/3)*math.tan(angle/4)/math.tan(angle/2)
                            path=g.cubic(start,end,[-side_b*x for x in u],
                                         [side_a*x for x in v],handle,steps=24)
                            if not LineString(path).is_simple:continue
                            key=f'{group}:{side_a}:{side_b}'
                            yield key,path,side_a>0,dict(
                                group=group,point=[point.x,point.y],radius=radius,
                                side=(side_a,side_b),visible=config.get('guides',{}).get(key,True))
