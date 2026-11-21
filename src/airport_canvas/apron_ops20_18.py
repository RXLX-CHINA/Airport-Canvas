"""Undoable apron shapes and exact boolean regions, including holes/islands."""
import copy
from geometry11 import polygon,polygons,unary_union

def shape(kind,first,last):
    x0,x1=sorted((first[0],last[0]));y0,y1=sorted((first[1],last[1]))
    if x1-x0<1 or y1-y0<1:raise ValueError('机坪长宽至少1m。')
    inset=(x1-x0)*.175 if kind=='TRAPEZOID' else 0
    return [[x0,y0],[x1,y0],[x1-inset,y1],[x0+inset,y1]]

def simple_parts(geometry):
    from shapely.ops import triangulate
    result=[]
    for part in polygons(geometry):
        if not part.interiors:result.append(part);continue
        for triangle in triangulate(part):
            for clipped in polygons(triangle.intersection(part)):
                if clipped.area>.000001:result.append(clipped)
    if any(p.interiors for p in result):raise ValueError('此孔洞暂无法安全分解，原机坪未改变。')
    return result

def boolean(scene,primary,ids,operation):
    from scene_hierarchy import create_group
    ordered=list(dict.fromkeys([primary,*ids]))
    if len(ordered)<2 or (operation=='DIFFERENCE' and len(ordered)!=2):
        raise ValueError('请 Ctrl 多选对象；差集按顺序选两个对象。')
    selected=[scene.assets[aid] for aid in ordered]
    first=selected[0]
    terminal=all(a['props'].get('building_role19')=='TERMINAL' for a in selected)
    other_buildings = all(a['props'].get('building_role19')=='OTHER' for a in selected)
    building = terminal or other_buildings
    if not building and not all(a['kind']=='APRON' and not a['props'].get('turn_pad')
                               and not a['props'].get('deice_layout12') for a in selected):
        raise ValueError('请选择同一类对象：普通机坪或航站楼主体。')
    base=polygon(first['points'])
    others=[polygon(a['points']) for a in selected[1:]]
    if operation=='UNION':
        result=unary_union([base,*others],grid_size=.0001)
    elif operation=='INTERSECTION':
        result=base
        for other in others:result=result.intersection(other)
    elif operation=='DIFFERENCE':
        result=base.difference(others[0])
    else:
        raise ValueError('未知布尔运算。')
    parts=sorted(simple_parts(result),key=lambda shape:(-shape.area,shape.bounds))
    if not parts:
        raise ValueError('运算结果为空，原对象未改变。')

    title='航站楼' if terminal else '建筑' if other_buildings else '机坪'
    labels=[a['props'].get('terminal_number19') or a['name'] for a in selected]
    label='/'.join(dict.fromkeys(labels)) if operation=='UNION' else labels[0]
    taken={a['props'].get('terminal_number19') for a in scene.assets.values() if a['id'] not in ordered}
    with scene.transaction(title+'布尔运算'):
        group=create_group(scene,title+'布尔结果',first.get('container_id'))
        style=copy.deepcopy(first['props'])
        if building:style['building_shape19']='POLYGON'
        made=[]
        for index,part in enumerate(parts):
            points=[list(q) for q in part.exterior.coords][:-1]
            props=copy.deepcopy(style)
            name=first['name']
            if building:
                name=label if not index else f'{label}-{index+1}'
                candidate=name
                suffix=2
                while name in taken:
                    name=f'{candidate}-{suffix}'
                    suffix+=1
                taken.add(name)
                props['terminal_number19']=name
            if index==0:
                first.update(points=points,props=props,name=name)
                aid=primary
            else:
                aid=scene.create_asset(first['kind'],name,points,**props)
            scene.assets[aid]['container_id']=group
            scene.assets[aid]['props']['apron_boolean_group20_18']=group
            made.append(aid)
        removed=set(ordered[1:])
        for obj in scene.assets.values():
            props=obj['props']
            if props.get('parent_id') in removed:props['parent_id']=primary
            if obj.get('container_id') in removed:obj['container_id']=primary
            if terminal and props.get('terminal_root19') in removed:props['terminal_root19']=primary
        for aid in ordered[1:]:
            scene.delete(aid)
        if terminal and operation=='UNION':
            from terminal19 import buildings,renumber
            bridges=[a['id'] for a in buildings(scene) if a['props']['building_role19']=='BRIDGE'
                     and a['props'].get('terminal_root19')==primary]
            if bridges:renumber(scene,primary,bridges[0])
    return made
