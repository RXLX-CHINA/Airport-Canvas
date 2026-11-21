"""Non-destructive designation view and independent branch naming."""
import copy,hashlib,uuid
import scene_geometry as g
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')
PALETTE=('#087eaa','#c44e52','#26835b','#9254b5','#c57b16','#c34189','#5372b5','#548d24')
def designation(a):return a['props'].get('designation') or a['name']
def color_name(name):
    return PALETTE[int(hashlib.sha256(name.encode()).hexdigest()[:8],16)%len(PALETTE)]


def color(a):return color_name(designation(a))


def colors(scene):
    return {name:color_name(name) for name in
            {designation(a) for a in scene.assets.values() if a['kind'] in TAXIS}}


def rename_branch(scene,aid,name):
    name=name.strip()
    if not name:raise ValueError('请输入分支编号')
    with scene.transaction('分支独立编号'):
        a=scene.assets[aid]
        if a['kind'] not in TAXIS:raise ValueError('请选择滑行道分支')
        old=a['props'].get('network_id');a['props']['network_id']='N-'+uuid.uuid4().hex[:10];a['props'].pop('network_group',None)
        group=scene.data['meta'].get('naming_groups',{}).get(old)
        if group is not None:scene.data['meta']['naming_groups'][old]=[x for x in group if x!=aid]
        __import__('editor7_model').sync_name(scene,aid,name)
    return aid
def split(scene,aid,station,name=None):
    with scene.transaction('分段并独立编号'):
        bid=__import__('editor7_model').split_route(scene,aid,station,keep_name=False)
        if scene.assets[aid].get('container_id'):scene.assets[bid]['container_id']=scene.assets[aid]['container_id']
        rename_branch(scene,bid,name or designation(scene.assets[aid])+'-1')
    return bid
def view(scene):
    out=[];palette=colors(scene)
    for a in scene.assets.values():
        if a['kind'] not in TAXIS+('RUNWAY',):continue
        taxi=a['kind'] in TAXIS;c=palette[designation(a)] if taxi else '#82929e'
        out.append(dict(type='line',oid=a['id'],points=copy.deepcopy(a['points']),stroke=c,width=max(1.,a['props']['width']*.22)))
        q,_=g.at(a['points'],g.length(a['points'])/2)
        out.append(dict(type='text',oid=a['id'],points=[q],text=designation(a),fill=c,size=4.,rotation=0,world_text=True))
    return out
