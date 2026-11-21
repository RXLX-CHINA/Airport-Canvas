"""Logical taxiway recombination; no re-sampling, welding or pavement edits."""
import uuid
import math
import scene_geometry as g
TAXIS=('TAXIWAY','APRON_TAXIWAY','STAND_TAXILANE')

def suggestions(scene,primary,tolerance=1.5):
    if primary not in scene.assets or scene.assets[primary]['kind'] not in TAXIS:raise ValueError('请选择主滑行道')
    found={primary};reason={primary:'主滑行道'};pending=True
    while pending:
        pending=False
        for aid,a in scene.assets.items():
            if aid in found or a['kind'] not in TAXIS:continue
            for bid in list(found):
                b=scene.assets[bid];best=None
                for own,other in [(a,b),(b,a)]:
                    for index in (0,-1):
                        point=own['points'][index];distance,station,q=g.project(other['points'],point)
                        if distance>tolerance:continue
                        ownu=g.unit(own['points'][0],own['points'][1]) if index==0 else g.unit(own['points'][-2],own['points'][-1]);_,otheru=g.at(other['points'],station)
                        cosine=abs(sum(ownu[k]*otheru[k] for k in (0,1)));ratio=min(a['props']['width'],b['props']['width'])/max(a['props']['width'],b['props']['width'])
                        if cosine>=math.cos(math.radians(15)) and ratio>=.75:best='端点相接且切线连续'
                if best:
                    found.add(aid);reason[aid]=best;pending=True;break
    return [(aid,reason[aid]) for aid in sorted(found,key=lambda key:(key!=primary,-g.length(scene.assets[key]['points'])))]

def merge(scene,primary,ids,name=None):
    selected=set(ids)|{primary}
    if any(aid not in scene.assets or scene.assets[aid]['kind'] not in TAXIS for aid in selected):raise ValueError('只能合并滑行路线的命名')
    target=scene.assets[primary];name=(name or target['props'].get('designation') or target['name']).strip()
    if not name:raise ValueError('请输入路线名称')
    network='N-'+uuid.uuid4().hex[:10]
    with scene.transaction('智能合并滑行道命名'):
        for aid in selected:
            a=scene.assets[aid];a['props'].update(network_id=network,designation=name);a['name']=name
        # Existing name-following signs update through the normal dependency.
        from editor7_model import sync_name
        for aid in selected:sync_name(scene,aid,name)
        scene.data['meta'].setdefault('naming_groups',{})[network]=sorted(selected)
        __import__('branch_selection20_15').merge_selection(scene,selected)
    return sorted(selected)
