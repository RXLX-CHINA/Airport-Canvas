"""Stable sloping envelope, longitudinal bridge and editable stand subparts."""
import copy,math
import scene_geometry as g
from stand11 import frame,dimensions

def envelope(a,scene):
    d=dimensions(scene,a);d['neck_start']=d['front']-6.;d['nose_end']=d['neck_start']+max(.5,a['props'].get('safety_neck',15.))
    d=__import__('stand17').reserve_stops(a,scene,d)
    if a['props'].get('safety_slope15'):
        d['neck_start']=d['wing']+(d['wide']-d['narrow'])/a['props']['safety_slope15'];d['nose_end']=d['neck_start']+max(.5,a['props'].get('safety_neck',15.))
    return d

def safety(scene,a):
    d=envelope(a,scene);q=a['points'][-1];_,u,v=frame(a)
    pts=[(d['tail'],-d['wide']),(d['wing'],-d['wide']),(d['neck_start'],-d['narrow']),(d['nose_end'],-d['narrow']),
         (d['nose_end'],d['narrow']),(d['neck_start'],d['narrow']),(d['wing'],d['wide']),(d['tail'],d['wide'])]
    return [[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in pts]

def zone(a,scene,side):
    d=envelope(a,scene);q=a['points'][-1];_,u,v=frame(a);p=a['props'];extension=p.get('bridge_length',0);end=d['nose_end']+max(0,extension)
    # Two parallel longitudinal sides, one sloping side on the safety boundary.
    pts=[(d['wing'],side*d['wide']),(d['neck_start'],side*d['narrow']),(end,side*d['narrow']),(end,side*d['wide'])]
    return [[q[k]+u[k]*x+v[k]*y for k in (0,1)] for x,y in pts]

def bridge(a,scene=None):
    if not a['props'].get('has_bridge'):return {}
    from automatic_markings import synthetic
    scene=scene or type('Context',(),{'scenario':dict(aircraft_length=40,aircraft_wingspan=36)})();side=-1 if a['props'].get('bridge_side','LEFT')=='RIGHT' else 1
    a=synthetic(a['id'],'BRIDGE_COMPOSITE',zone(a,scene,side),'BRIDGE',stand_part=True)
    return {a['id']:a}

WORK_ZONES59=('常规作业区','临时作业区')

NO_WORK_ZONE='不设置'


def support(scene,a):
    if not a['props'].get('stand_support',True):return {}
    from automatic_markings import synthetic
    props=a['props']
    side=-1 if props.get('bridge_side','LEFT')=='LEFT' else 1
    choices=((-1,'work_zone_right'),(1,'work_zone_left')) if props.get('remote_stand') else ((side,'work_zone'),)
    if not props.get('remote_stand') and not props.get('has_bridge'):
        choices+=((-side,'work_zone_bridge_side'),)
    out={}
    for direction,key in choices:
        default=NO_WORK_ZONE if key=='work_zone_bridge_side' else WORK_ZONES59[0]
        if props.get(key,default)==NO_WORK_ZONE:continue
        kind='TEMP_WAIT' if props.get(key)==WORK_ZONES59[1] else 'WORK_WAIT'
        suffix='WORK_WAIT:'+key if key!='work_zone' else 'WORK_WAIT'
        mark=synthetic(a['id'],kind,zone(a,scene,direction),suffix,line_width=.1,spacing=2,stand_part=True)
        out[mark['id']]=mark
    if props.get('remote_stand'):return out
    d=envelope(a,scene);q=a['points'][-1];_,u,v=frame(a);c=[q[k]+u[k]*(d['nose_end']+2)+v[k]*side*(d['wide']-2) for k in (0,1)]
    mark=synthetic(a['id'],'CHOCKS',[c,[c[k]+u[k]*3 for k in (0,1)]],'CHOCKS',width=1.5,text='轮挡',text_height=.5,stand_part=True);out[mark['id']]=mark;return out

def merged_work_zone_hatches(zones,marks):
    from geometry11 import LineString,Polygon,STRtree,lines,polygons,unary_union
    from marking_catalog import hatch_segments
    regular=[(item,shape) for _,item,shape in zones if marks[item['oid']]['props']['mark_type']=='WORK_WAIT']
    if len(regular)<2:return {},set()
    shapes=[shape for _,shape in regular]
    index=STRtree(shapes)
    pending=set(range(len(shapes)))
    hatches={}
    suppressed=set()
    while pending:
        seed=min(pending)
        pending.remove(seed)
        component=[seed]
        for i in component:
            neighbors=pending.intersection(index.query(shapes[i],predicate='intersects'))
            pending.difference_update(neighbors)
            component.extend(sorted(neighbors))
        if len(component)<2:continue
        item,_=regular[seed]
        oid=item['oid']
        props=marks[oid]['props']
        p,q=item['points'][:2]
        angle=props.get('hatch_angle',math.degrees(math.atan2(q[1]-p[1],q[0]-p[0]))+45)
        width=item['width']
        pitch=props.get('spacing',2)+width
        fill=unary_union(shapes[i] for i in component)
        generated=[]
        for area in polygons(fill):
            holes=unary_union(Polygon(ring) for ring in area.interiors)
            for segment in hatch_segments(list(area.exterior.coords)[:-1],pitch,angle,props.get('hatch_phase',0)):
                clipped=lines(LineString(segment).difference(holes)) if not holes.is_empty else ()
                strokes=([list(q) for q in line.coords] for line in clipped) if not holes.is_empty else (segment,)
                generated.extend(dict(type='line',oid=oid,points=stroke,stroke=item['stroke'],width=width,dash=None)
                                 for stroke in strokes)
        hatches[oid]=generated
        suppressed.update(regular[i][0]['oid'] for i in component)
    return hatches,suppressed


def merge_work_zone_outlines(scene,items,marks):
    from geometry11 import Point,line_merge,lines,polygon,unary_union
    styles=scene.data['meta'].get('object_display',{})
    zones=[]
    for index,item in enumerate(items):
        mark=marks.get(item['oid'],{})
        if (item['type']!='polygon' or not item.get('stroke') or item.get('fill')
                or mark.get('props',{}).get('mark_type') not in ('WORK_WAIT','TEMP_WAIT')):
            continue
        visible=all(not styles.get(oid,{}).get('hidden') and styles.get(oid,{}).get('opacity',1)>0
                    for oid in (item['oid'],mark.get('owner',item['oid'])))
        if visible:
            shape=polygon(item['points'])
            if not shape.is_empty:zones.append((index,item,shape))
    if len(zones)<2:return items
    boundary=unary_union(shape for _,_,shape in zones).boundary
    removed_labels={item['oid'] for _,item,shape in zones
                    if shape.boundary.difference(boundary).length>1e-6}
    temporary={item['oid']:shape for _,item,shape in zones
               if marks[item['oid']]['props']['mark_type']=='TEMP_WAIT'}
    from shapely.ops import nearest_points
    retained_labels=set()
    seen=set()
    for index,item in enumerate(items):
        if item['type']!='text' or item['oid'] not in temporary:continue
        point=Point(item['points'][0])
        _,edge_point=nearest_points(point,temporary[item['oid']].boundary)
        if boundary.distance(edge_point)>1e-6:continue
        key=(round(point.x,3),round(point.y,3),item['text'],item.get('rotation',0)%180)
        if key not in seen:
            retained_labels.add(index)
            seen.add(key)
    replacements={}
    for index,item,shape in zones:
        edge=boundary.intersection(shape.boundary)
        replacements[index]=[dict(item,type='line',points=[list(q) for q in line.coords],work_zone_outline=True)
                             for line in lines(line_merge(edge))]
        boundary=boundary.difference(edge)
    if not boundary.is_empty:
        index,item,_=zones[0]
        replacements[index].extend(dict(item,type='line',points=[list(q) for q in line.coords],work_zone_outline=True)
                                   for line in lines(boundary))
    hatches,suppressed=merged_work_zone_hatches(zones,marks)
    for index,item,_ in zones:
        replacements[index].extend(hatches.get(item['oid'],()))
    return [part for index,item in enumerate(items)
            if (item['type']!='text' or (index in retained_labels if item['oid'] in temporary
                                        else item['oid'] not in removed_labels))
            and (item['type']!='line' or item['oid'] not in suppressed)
            for part in replacements.get(index,(item,))]


def clip_work_zones_at_stands(items,marks):
    from geometry11 import LineString,Point,STRtree,lines,polygon,unary_union
    shapes=[polygon(mark['points']) for mark in marks.values()
            if mark['props'].get('mark_type')=='STAND_SAFETY']
    if not shapes:return items
    tree=STRtree(shapes)
    result=[]
    for item in items:
        mark=marks.get(item['oid'],{})
        if mark.get('props',{}).get('mark_type') not in ('WORK_WAIT','TEMP_WAIT'):
            result.append(item)
            continue
        points=item['points']
        if item['type']=='text':
            x,y=points[0]
            height=item.get('size',1.)
            half_width=(item.get('text_width') or len(item['text'])*height)/2
            geometry=polygon([[x-half_width,y-height/2],[x+half_width,y-height/2],
                              [x+half_width,y+height/2],[x-half_width,y+height/2]])
            margin=0.
        else:
            geometry=LineString(points+[points[0]] if item['type']=='polygon' else points)
            margin=item.get('width',.1)/2
        nearby=tree.query(geometry.buffer(margin) if margin else geometry)
        blockers=[shapes[i] for i in nearby]
        if not blockers:
            result.append(item)
            continue
        mask=unary_union(blockers)
        if margin:mask=mask.buffer(margin)
        if not geometry.intersects(mask):
            result.append(item)
        elif item['type']!='text':
            for segment in lines(geometry.difference(mask)):
                coords=[list(q) for q in segment.coords]
                station=geometry.project(Point(coords[0]))
                result.append(dict(item,type='line',points=coords,fill=None,
                                   dash_offset=item.get('dash_offset',0)+station))
    return result


def design(a,scene=None):
    from stand12 import design as base
    result=base(a,scene);edits=a['props'].get('lead_edits13',{}) if a['props'].get('lead_edit_type13',a['props'].get('lead_type','A'))==a['props'].get('lead_type','A') else {};o,u,v=frame(a)
    world=lambda q:[o[k]+u[k]*q[0]+v[k]*q[1] for k in (0,1)]
    from curve_model import evaluate
    for part in result['paths']:
        nodes=edits.get(part['key'])
        if nodes:
            nodes=copy.deepcopy(nodes)
            for node in nodes:
                for field in ('p','incoming','outgoing'):node[field]=world(node[field])
            part['points']=evaluate(nodes)
    return result

def part_nodes(a,key,scene=None):
    from editor7_model import curve_nodes_for
    from curve_model import node
    part=next(p for p in design(a,scene)['paths'] if p['key']==key)
    if a['props'].get('lead_edit_type13',a['props'].get('lead_type','A'))==a['props'].get('lead_type','A') and key in a['props'].get('lead_edits13',{}):return copy.deepcopy(a['props']['lead_edits13'][key])
    # One cubic for short arcs/stubs, two for larger arcs; never tessellation nodes.
    pts=part['points'];nodes=curve_nodes_for(pts)
    o,u,v=frame(a)
    for n in nodes:
        for field in ('p','incoming','outgoing'):n[field]=[sum((n[field][k]-o[k])*axis[k] for k in (0,1)) for axis in (u,v)]
    return nodes

def save_nodes(scene,aid,key,nodes):
    with scene.transaction('编辑机位引导分支控制点'):
        scene.assets[aid]['props'].setdefault('lead_edits13',{})[key]=copy.deepcopy(nodes)
        scene.assets[aid]['props']['lead_edit_type13']=scene.assets[aid]['props'].get('lead_type','A')

def ensure_groups(scene):
    """Organizational group + procedural root + individually editable virtual children."""
    from scene_hierarchy import create_group
    pending=[a for a in scene.assets.values() if a['kind']=='STAND' and scene.data['groups'].get(a['props'].get('stand_group13'),{}).get('stand_root13')!=a['id'] and not (scene.data['groups'].get(a['props'].get('stand_group13'),{}).get('combined14') and a.get('container_id')==a['props'].get('stand_group13'))]
    if not pending:return
    with scene.transaction('建立成套机位组'):
        for a in pending:
            parent=a.get('container_id')
            if parent in scene.data['groups'] and scene.data['groups'][parent].get('stand_root13'):parent=scene.data['groups'][parent].get('container_id')
            gid=create_group(scene,'机位 '+a['name'],parent);scene.data['groups'][gid]['stand_root13']=a['id'];a['container_id']=gid;a['props']['stand_group13']=gid
