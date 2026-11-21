"""Organizational hierarchy, independent of physical apron associations."""
import uuid

CONTAINERS={'RUNWAY','TAXIWAY','APRON','APRON_TAXIWAY','STAND_TAXILANE','STAND','ROAD','EQUIPMENT','PROTECTION','CLOSED_AREA'}

def all_objects(scene):return dict(scene.data['groups'],**scene.assets,**scene.movements)

def parent_of(scene,oid):
    obj=all_objects(scene)[oid]
    if 'container_id' in obj:return obj['container_id']
    return obj.get('props',{}).get('parent_id')

def validate_hierarchy(scene):
    if set(scene.data['groups'])&set(scene.assets) or set(scene.data['groups'])&set(scene.movements) or set(scene.assets)&set(scene.movements):raise ValueError('Object identities must be unique across groups, assets and connections')
    objects=all_objects(scene)
    for oid,obj in objects.items():
        if oid in scene.data['groups'] and (obj.get('id')!=oid or not isinstance(obj.get('name'),str) or not obj['name'].strip()):raise ValueError('Invalid group')
        parent=parent_of(scene,oid);seen={oid}
        while parent is not None:
            if parent not in objects:raise ValueError('Container no longer exists')
            if parent in scene.movements or parent in scene.assets and scene.assets[parent]['kind'] not in CONTAINERS:raise ValueError('Select a group or pavement container')
            if parent in seen:raise ValueError('Cannot nest an object inside itself or its descendants')
            seen.add(parent);parent=parent_of(scene,parent)

def descendants(scene,oid):
    children={}
    for key in all_objects(scene):children.setdefault(parent_of(scene,key),[]).append(key)
    result=[];queue=list(children.get(oid,[]))
    while queue:
        key=queue.pop();result.append(key);queue.extend(children.get(key,[]))
    return result

def create_group(scene,name,parent=None):
    gid='G-'+uuid.uuid4().hex[:10]
    with scene.transaction('新建道面组'):scene.data['groups'][gid]=dict(id=gid,name=name,container_id=parent)
    return gid

def reparent(scene,oid,parent=None):
    with scene.transaction('移入道面组'):all_objects(scene)[oid]['container_id']=parent
